/** 核心页面轻量可访问性回归：语义地标、控件命名、重复 ID 与键盘焦点。 */
import { chromium } from '@playwright/test';

const baseUrl = process.env.AI_NEWS_BASE_URL || 'http://127.0.0.1:8765';
const routes = ['/', '/library', '/timeline', '/events', '/research', '/my', '/entity/openai'];
const themes = ['dark', 'light'];
const browser = await chromium.launch({ headless: true });
const results = [];

try {
  for (const route of routes) {
    for (const theme of themes) {
      const context = await browser.newContext({
        viewport: { width: 1280, height: 900 },
        colorScheme: theme,
        reducedMotion: 'reduce',
      });
      await context.addInitScript(value => {
        localStorage.setItem('theme', value);
        localStorage.setItem('lang', 'zh');
      }, theme);
      const page = await context.newPage();
      const response = await page.goto(baseUrl + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(800);
      const audit = await page.evaluate(() => {
        const duplicateIds = [...document.querySelectorAll('[id]')]
          .map(node => node.id)
          .filter((id, index, ids) => id && ids.indexOf(id) !== index);
        const unnamed = [...document.querySelectorAll('button,input,select,textarea')]
          .filter(node => !node.disabled && !node.hidden)
          .filter(node => {
            const label = node.labels?.[0]?.textContent || node.getAttribute('aria-label') ||
              node.getAttribute('aria-labelledby') || node.getAttribute('title') ||
              node.getAttribute('placeholder') || node.textContent;
            return !String(label || '').trim();
          })
          .map(node => `${node.tagName.toLowerCase()}#${node.id || ''}.${node.className || ''}`);
        return {
          lang: document.documentElement.lang,
          h1: document.querySelectorAll('h1').length,
          main: document.querySelectorAll('main').length,
          primaryNav: Boolean(document.querySelector('nav.nav[aria-label]')),
          currentPage: document.querySelectorAll('.nav [aria-current="page"]').length,
          skipLink: Boolean(document.querySelector('.skip-link[href^="#"]')),
          duplicateIds: [...new Set(duplicateIds)],
          unnamed,
        };
      });
      await page.keyboard.press('Tab');
      const focused = await page.evaluate(() => {
        const node = document.activeElement;
        return node && node !== document.body ? node.tagName.toLowerCase() : '';
      });
      results.push({ route, theme, status: response?.status() || 0, focused, ...audit });
      await context.close();
    }
  }
} finally {
  await browser.close();
}

const failures = results.filter(item => item.status !== 200 || !item.lang || item.h1 !== 1 ||
  item.main !== 1 || !item.primaryNav || item.currentPage !== 1 || !item.skipLink ||
  !item.focused || item.duplicateIds.length || item.unnamed.length);
console.log(JSON.stringify({ checks: results.length, failures }, null, 2));
if (failures.length) process.exitCode = 1;
