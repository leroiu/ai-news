/** 真实 Chromium 轻量可访问性审计；违规由 Python 门禁与显式基线比较。 */
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const RULE_VERSION = 3;
const baseURL = process.env.ACCESSIBILITY_BASE_URL || 'http://127.0.0.1:8765';
const routes = JSON.parse(process.env.ACCESSIBILITY_ROUTES || '["/"]');
const outputDir = path.resolve(
  process.env.ACCESSIBILITY_OUTPUT_DIR || 'output/accessibility-gate/manual',
);
const fixedTime =
  process.env.ACCESSIBILITY_FIXED_TIME || '2026-07-16T12:00:00.000Z';
const cases = [
  { name: 'desktop-dark', width: 1280, height: 900, theme: 'dark' },
  { name: 'desktop-light', width: 1280, height: 900, theme: 'light' },
  { name: 'mobile-dark', width: 390, height: 844, theme: 'dark' },
];

function fingerprint(violation) {
  return [
    violation.rule,
    violation.route,
    violation.case,
    violation.selector,
  ].join('|');
}

async function main() {
  await fs.mkdir(path.join(outputDir, 'cases'), { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = [];
  const infrastructureFailures = [];

  try {
    for (const route of routes) {
      for (const testCase of cases) {
        const context = await browser.newContext({
          viewport: { width: testCase.width, height: testCase.height },
          colorScheme: testCase.theme,
          reducedMotion: 'reduce',
        });
        await context.addInitScript(
          ({ theme, fixedTimeValue }) => {
            const RealDate = Date;
            const epoch = RealDate.parse(fixedTimeValue);
            class FixedDate extends RealDate {
              constructor(...args) {
                super(...(args.length ? args : [epoch]));
              }
              static now() {
                return epoch;
              }
            }
            Date = FixedDate;
            localStorage.clear();
            localStorage.setItem('theme', theme);
            localStorage.setItem('lang', 'zh');
          },
          { theme: testCase.theme, fixedTimeValue: fixedTime },
        );

        const page = await context.newPage();
        let response = null;
        let navigationError = '';
        const pageErrors = [];
        page.on('pageerror', error => pageErrors.push(error.message));
        try {
          response = await page.goto(`${baseURL}${route}`, {
            waitUntil: 'networkidle',
            timeout: 30000,
          });
          await page.waitForTimeout(1200);
        } catch (error) {
          navigationError = error.message;
        }

        const raw = await page.evaluate(() => {
          function visible(node) {
            const style = getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            return (
              style.display !== 'none' &&
              style.visibility !== 'hidden' &&
              Number(style.opacity || 1) > 0 &&
              rect.width > 0 &&
              rect.height > 0
            );
          }

          function selector(node) {
            if (node.id) return `#${CSS.escape(node.id)}`;
            const parts = [];
            let current = node;
            while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 4) {
              let part = current.tagName.toLowerCase();
              const classes = [...current.classList].slice(0, 2);
              if (classes.length) part += `.${classes.map(CSS.escape).join('.')}`;
              const parent = current.parentElement;
              if (parent) {
                const siblings = [...parent.children].filter(
                  sibling => sibling.tagName === current.tagName,
                );
                if (siblings.length > 1) {
                  part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
                }
              }
              parts.unshift(part);
              current = parent;
            }
            return parts.join(' > ');
          }

          function textFromIds(ids) {
            return String(ids || '')
              .split(/\s+/)
              .filter(Boolean)
              .map(id => document.getElementById(id)?.textContent || '')
              .join(' ')
              .trim();
          }

          function accessibleName(node) {
            const ariaLabel = node.getAttribute('aria-label');
            if (ariaLabel?.trim()) return ariaLabel.trim();
            const labelled = textFromIds(node.getAttribute('aria-labelledby'));
            if (labelled) return labelled;
            const labels = [...(node.labels || [])]
              .map(label => label.textContent || '')
              .join(' ')
              .trim();
            if (labels) return labels;
            if (node.tagName === 'IMG') return (node.getAttribute('alt') || '').trim();
            if (
              node.tagName === 'INPUT' &&
              ['button', 'submit', 'reset'].includes(node.type)
            ) {
              return String(node.value || '').trim();
            }
            const title = node.getAttribute('title');
            if (title?.trim()) return title.trim();
            function contentName(current) {
              if (current.nodeType === Node.TEXT_NODE) {
                return current.textContent || '';
              }
              if (current.nodeType !== Node.ELEMENT_NODE) return '';
              if (current.getAttribute('aria-hidden') === 'true') return '';
              if (current.tagName === 'IMG') return current.getAttribute('alt') || '';
              return [...current.childNodes].map(contentName).join(' ');
            }
            return contentName(node).replace(/\s+/g, ' ').trim();
          }

          function isNativeInteractive(node) {
            if (['BUTTON', 'SELECT', 'TEXTAREA', 'SUMMARY'].includes(node.tagName)) {
              return true;
            }
            if (node.tagName === 'A' && node.hasAttribute('href')) return true;
            if (node.tagName === 'INPUT' && node.type !== 'hidden') return true;
            return false;
          }

          const findings = [];
          function add(rule, node, detail) {
            findings.push({
              rule,
              selector: node ? selector(node) : 'document',
              detail,
            });
          }

          if (!document.documentElement.lang.trim()) {
            add('document-lang', document.documentElement, 'html 缺少 lang');
          }
          if (!document.title.trim()) {
            add('document-title', document.head, '文档缺少非空 title');
          }
          const headings = document.querySelectorAll('h1');
          if (headings.length !== 1) {
            add('single-h1', document.body, `h1 数量为 ${headings.length}`);
          }
          const mains = document.querySelectorAll('main');
          if (mains.length !== 1) {
            add('single-main', document.body, `main 数量为 ${mains.length}`);
          }
          const primaryNavs = document.querySelectorAll('nav.nav[aria-label]');
          if (primaryNavs.length !== 1) {
            add(
              'single-primary-nav',
              document.body,
              `带名称的主导航数量为 ${primaryNavs.length}`,
            );
          }
          const currentPages = document.querySelectorAll(
            'nav.nav [aria-current="page"]',
          );
          if (currentPages.length !== 1) {
            add(
              'single-current-page',
              document.body,
              `当前导航项数量为 ${currentPages.length}`,
            );
          }

          const ids = [...document.querySelectorAll('[id]')]
            .map(node => node.id)
            .filter(Boolean);
          const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
          for (const id of duplicateIds) {
            add(
              'duplicate-id',
              document.querySelector(`#${CSS.escape(id)}`),
              `重复 id: ${id}`,
            );
          }

          const skipLink = document.querySelector('.skip-link[href^="#"]');
          if (!skipLink) {
            add('skip-link', document.body, '缺少跳转到正文的链接');
          } else {
            const target = document.querySelector(skipLink.getAttribute('href'));
            if (!target) {
              add('skip-link-target', skipLink, '跳转链接目标不存在');
            }
          }

          const namedControls = document.querySelectorAll(
            'button,input:not([type="hidden"]),select,textarea,summary',
          );
          for (const node of namedControls) {
            if (visible(node) && !node.disabled && !accessibleName(node)) {
              add('control-name', node, '可见控件缺少可访问名称');
            }
          }
          for (const node of document.querySelectorAll('a[href]')) {
            if (visible(node) && !accessibleName(node)) {
              add('link-name', node, '可见链接缺少可访问名称');
            }
          }
          for (const node of document.querySelectorAll('img')) {
            if (visible(node) && !node.hasAttribute('alt')) {
              add('image-alt', node, '可见图片缺少 alt 属性');
            }
          }
          for (const node of document.querySelectorAll('[onclick]')) {
            if (visible(node) && !isNativeInteractive(node)) {
              const role = String(node.getAttribute('role') || '').toLowerCase();
              const interactiveRole = ['button', 'link'].includes(role);
              const tabindex = node.getAttribute('tabindex');
              const focusable =
                tabindex !== null &&
                Number.isFinite(Number(tabindex)) &&
                Number(tabindex) >= 0;
              const keyboardSource = [
                node.getAttribute('onkeydown') || '',
                node.getAttribute('onkeyup') || '',
                node.getAttribute('onkeypress') || '',
              ].join(' ');
              const keyboardActivation =
                /Enter|Space|keyCode\s*={2,3}\s*(13|32)|which\s*={2,3}\s*(13|32)|\.key\s*={2,3}\s*['"] ['"]/.test(
                  keyboardSource,
                );
              const missing = [];
              if (!interactiveRole) missing.push('role=button/link');
              if (!focusable) missing.push('tabindex>=0');
              if (!keyboardActivation) missing.push('Enter/Space handler');
              if (missing.length) {
                add(
                  'clickable-keyboard',
                  node,
                  `非原生 onclick 缺少：${missing.join('、')}`,
                );
              }
            }
          }
          for (const node of document.querySelectorAll('[tabindex]')) {
            if (Number(node.getAttribute('tabindex')) > 0) {
              add('positive-tabindex', node, '不应使用正数 tabindex');
            }
          }

          return findings;
        });

        await page.evaluate(() => {
          document.activeElement?.blur();
          window.scrollTo(0, 0);
        });
        await page.keyboard.press('Tab');
        const focus = await page.evaluate(() => {
          const active = document.activeElement;
          return {
            tag: active?.tagName?.toLowerCase() || '',
            id: active?.id || '',
            className:
              typeof active?.className === 'string' ? active.className : '',
            isBody: !active || active === document.body,
          };
        });
        if (focus.isBody) {
          raw.push({
            rule: 'keyboard-focus',
            selector: 'document',
            detail: '按 Tab 后没有元素获得焦点',
          });
        }
        if (
          raw.some(item => item.rule === 'skip-link') === false &&
          !String(focus.className).split(/\s+/).includes('skip-link')
        ) {
          raw.push({
            rule: 'skip-link-first',
            selector: focus.id ? `#${focus.id}` : focus.tag || 'document',
            detail: '首个 Tab 焦点不是 skip-link',
          });
        }

        const violations = raw.map(item => ({
          ...item,
          route,
          case: testCase.name,
        }));
        violations.forEach(item => {
          item.fingerprint = fingerprint(item);
        });

        if (!response?.ok() || navigationError || pageErrors.length) {
          infrastructureFailures.push({
            route,
            case: testCase.name,
            status: response?.status() || 0,
            navigationError,
            pageErrors,
          });
        }
        const result = {
          route,
          case: testCase.name,
          viewport: { width: testCase.width, height: testCase.height },
          theme: testCase.theme,
          status: response?.status() || 0,
          navigationError,
          pageErrors,
          focus,
          violations,
        };
        results.push(result);
        await fs.writeFile(
          path.join(
            outputDir,
            'cases',
            `${route.replace(/^\/+|\/+$/g, '').replaceAll('/', '-') || 'home'}-${testCase.name}.json`,
          ),
          JSON.stringify(result, null, 2),
        );
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }

  const violations = results
    .flatMap(result => result.violations)
    .sort((a, b) => a.fingerprint.localeCompare(b.fingerprint));
  const audit = {
    schemaVersion: 1,
    ruleVersion: RULE_VERSION,
    generatedAt: new Date().toISOString(),
    fixedTime,
    routes,
    cases: cases.map(item => item.name),
    results,
    violations,
    infrastructureFailures,
    summary: {
      checks: results.length,
      violations: violations.length,
      infrastructureFailures: infrastructureFailures.length,
    },
  };
  await fs.writeFile(
    path.join(outputDir, 'audit.json'),
    JSON.stringify(audit, null, 2),
  );
  console.log(JSON.stringify(audit.summary, null, 2));
  process.exitCode = infrastructureFailures.length ? 1 : 0;
}

main().catch(error => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
