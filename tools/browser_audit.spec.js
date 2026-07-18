/** 隔离浏览器门禁：真实 Chromium + 响应式截图 + 结构化证据。 */
const { chromium } = require('@playwright/test');
const fs = require('fs/promises');
const path = require('path');

const baseURL = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:8765';
const routes = JSON.parse(process.env.FRONTEND_ROUTES || '["/"]');
const outputDir = path.resolve(process.env.FRONTEND_OUTPUT_DIR || 'output/browser-gate/manual');
const allowedOrigins = new Set(JSON.parse(process.env.FRONTEND_ALLOWED_ORIGINS || '[]'));
const fixedTime = process.env.FRONTEND_FIXED_TIME || '2026-07-16T12:00:00.000Z';
const webSocketProbeURL = process.env.FRONTEND_WEBSOCKET_PROBE_URL || '';
const baseOrigin = new URL(baseURL).origin;
const baseParsed = new URL(baseURL);
const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
];

function slug(route) {
  return route.replace(/^\/+|\/+$/g, '').replaceAll('/', '-') || 'home';
}

function ignorableConsoleError(text) {
  return text.includes('/favicon.ico') && text.includes('404');
}

function isExternal(url) {
  const parsed = new URL(url);
  return parsed.origin !== baseOrigin && !['data:', 'blob:', 'about:'].includes(parsed.protocol);
}

function effectivePort(parsed) {
  if (parsed.port) return parsed.port;
  if (parsed.protocol === 'https:' || parsed.protocol === 'wss:') return '443';
  if (parsed.protocol === 'http:' || parsed.protocol === 'ws:') return '80';
  return '';
}

function isApplicationWebSocket(url) {
  const parsed = new URL(url);
  const compatibleProtocol =
    (baseParsed.protocol === 'http:' && parsed.protocol === 'ws:') ||
    (baseParsed.protocol === 'https:' && parsed.protocol === 'wss:');
  return compatibleProtocol &&
    parsed.hostname === baseParsed.hostname &&
    effectivePort(parsed) === effectivePort(baseParsed);
}

function isAllowedWebSocket(url) {
  const parsed = new URL(url);
  return isApplicationWebSocket(url) || allowedOrigins.has(parsed.origin);
}

async function visibleLoadingStates(page) {
  return page.evaluate(() => {
    const candidates = [
      ...document.querySelectorAll('[data-ui-state="loading"], .spinner, .loading'),
    ];
    return candidates
      .filter(node => {
        const style = getComputedStyle(node);
        const rect = node.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0;
      })
      .map(node => ({
        selector: node.id ? `#${node.id}` : node.className ? `.${String(node.className).trim().replace(/\s+/g, '.')}` : node.tagName,
        text: String(node.textContent || '').trim().slice(0, 120),
      }));
  });
}

async function main() {
  await fs.mkdir(path.join(outputDir, 'screenshots'), { recursive: true });
  await fs.mkdir(path.join(outputDir, 'cases'), { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const cases = [];

  try {
    for (const route of routes) {
      for (const viewport of viewports) {
        const context = await browser.newContext({
          viewport: { width: viewport.width, height: viewport.height },
          colorScheme: 'dark',
          reducedMotion: 'reduce',
        });
        await context.addInitScript(value => {
          const RealDate = Date;
          const epoch = RealDate.parse(value);
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
          localStorage.setItem('theme', 'dark');
          localStorage.setItem('lang', 'zh');
        }, fixedTime);

        const externalRequests = [];
        const webSocketRequests = [];
        await context.route('**/*', async routeHandle => {
          const requestURL = routeHandle.request().url();
          if (isExternal(requestURL)) {
            const origin = new URL(requestURL).origin;
            const allowed = allowedOrigins.has(origin);
            externalRequests.push({ url: requestURL, origin, allowed });
            if (!allowed) {
              await routeHandle.abort('blockedbyclient');
              return;
            }
          }
          await routeHandle.continue();
        });
        await context.routeWebSocket('**/*', async webSocketRoute => {
          const requestURL = webSocketRoute.url();
          const parsed = new URL(requestURL);
          const allowed = isAllowedWebSocket(requestURL);
          webSocketRequests.push({
            url: requestURL,
            origin: parsed.origin,
            allowed,
          });
          if (!allowed) {
            await webSocketRoute.close({
              code: 1008,
              reason: 'Blocked by browser gate network policy',
            });
            return;
          }
          webSocketRoute.connectToServer();
        });

        const page = await context.newPage();
        const consoleErrors = [];
        const ignoredConsoleErrors = [];
        const pageErrors = [];
        const requestFailures = [];
        const badResponses = [];
        page.on('console', message => {
          if (message.type() !== 'error') return;
          const text = message.text();
          if (ignorableConsoleError(text)) ignoredConsoleErrors.push(text);
          else consoleErrors.push(text);
        });
        page.on('pageerror', error => pageErrors.push(error.message));
        page.on('requestfailed', request => {
          const url = request.url();
          const external = isExternal(url);
          if (!external || !externalRequests.some(item => item.url === url && !item.allowed)) {
            requestFailures.push({ url, error: request.failure()?.errorText || '' });
          }
        });
        page.on('response', response => {
          const status = response.status();
          const url = response.url();
          if (status >= 400 && !(status === 404 && url.endsWith('/favicon.ico'))) {
            badResponses.push({ url, status });
          }
        });

        let response = null;
        let navigationError = '';
        try {
          response = await page.goto(`${baseURL}${route}`, {
            waitUntil: 'networkidle',
            timeout: 30000,
          });
          await page.waitForTimeout(route.includes('graph') ? 2500 : 1200);
          if (webSocketProbeURL) {
            await page.evaluate(url => {
              window.__browserGateProbe = new WebSocket(url);
            }, webSocketProbeURL);
            await page.waitForTimeout(250);
          }
        } catch (error) {
          navigationError = error.message;
        }

        const metrics = await page.evaluate(() => {
          const root = document.documentElement;
          const body = document.body;
          const bodyText = String(body?.innerText || '').replace(/\s+/g, ' ').trim();
          return {
            title: document.title,
            lang: root.lang,
            bodyTextLength: bodyText.length,
            bodyTextSample: bodyText.slice(0, 180),
            viewportWidth: window.innerWidth,
            documentWidth: root.scrollWidth,
            bodyWidth: body?.scrollWidth || 0,
            documentHeight: root.scrollHeight,
            template: document.querySelector('[data-page-template]')?.getAttribute('data-page-template') || '',
          };
        });
        const loadingStates = await visibleLoadingStates(page);
        const shotBase = `${slug(route)}-${viewport.name}`;
        const fullPath = path.join(outputDir, 'screenshots', `${shotBase}-full.png`);
        const topPath = path.join(outputDir, 'screenshots', `${shotBase}-top.png`);
        const bottomPath = path.join(outputDir, 'screenshots', `${shotBase}-bottom.png`);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(100);
        await page.screenshot({ path: topPath });
        await page.screenshot({ path: fullPath, fullPage: true });
        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
        await page.waitForTimeout(150);
        await page.screenshot({ path: bottomPath });

        const failures = [];
        if (navigationError) failures.push(`navigation: ${navigationError}`);
        if (!response || !response.ok()) failures.push(`HTTP ${response?.status() || 0}`);
        if (metrics.documentWidth > metrics.viewportWidth + 1 || metrics.bodyWidth > metrics.viewportWidth + 1) {
          failures.push(`horizontal-overflow: viewport=${metrics.viewportWidth}, document=${metrics.documentWidth}, body=${metrics.bodyWidth}`);
        }
        if (metrics.bodyTextLength < 20) failures.push(`blank-body: ${metrics.bodyTextLength}`);
        if (loadingStates.length) failures.push(`persistent-loading: ${JSON.stringify(loadingStates)}`);
        if (consoleErrors.length) failures.push(`console-errors: ${consoleErrors.join(' | ')}`);
        if (pageErrors.length) failures.push(`page-errors: ${pageErrors.join(' | ')}`);
        if (requestFailures.length) failures.push(`request-failures: ${JSON.stringify(requestFailures)}`);
        if (badResponses.length) failures.push(`bad-responses: ${JSON.stringify(badResponses)}`);
        if (externalRequests.some(item => !item.allowed)) {
          failures.push(`blocked-external-requests: ${JSON.stringify(externalRequests.filter(item => !item.allowed))}`);
        }
        if (webSocketRequests.some(item => !item.allowed)) {
          failures.push(`blocked-websockets: ${JSON.stringify(webSocketRequests.filter(item => !item.allowed))}`);
        }

        const result = {
          route,
          viewport,
          status: response?.status() || 0,
          navigationError,
          metrics,
          loadingStates,
          consoleErrors,
          ignoredConsoleErrors,
          pageErrors,
          requestFailures,
          badResponses,
          externalRequests,
          webSocketRequests,
          screenshots: { full: fullPath, top: topPath, bottom: bottomPath },
          failures,
          passed: failures.length === 0,
        };
        cases.push(result);
        await fs.writeFile(
          path.join(outputDir, 'cases', `${shotBase}.json`),
          JSON.stringify(result, null, 2),
        );
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }

  const failures = cases.filter(item => !item.passed);
  const audit = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    baseURL,
    allowedExternalOrigins: [...allowedOrigins],
    fixedTime,
    webSocketProbeURL,
    cases,
    failures,
    summary: {
      total: cases.length,
      passed: cases.length - failures.length,
      failed: failures.length,
      screenshots: cases.length * 3,
    },
  };
  await fs.writeFile(path.join(outputDir, 'audit.json'), JSON.stringify(audit, null, 2));
  console.log(JSON.stringify(audit.summary, null, 2));
  process.exitCode = failures.length ? 1 : 0;
}

main().catch(error => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
