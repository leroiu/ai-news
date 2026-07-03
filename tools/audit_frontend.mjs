/** 全站响应式视觉矩阵：截图 + 溢出/控制台/模板检查。 */
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseUrl = process.env.AI_NEWS_BASE_URL || 'http://127.0.0.1:8765';
const outputDir = path.resolve('output/playwright/matrix');
const routes = [
  ['home', '/'], ['library', '/library'], ['timeline', '/timeline'],
  ['events', '/events'], ['reports', '/reports'], ['research', '/research'],
  ['my', '/my'], ['entity-openai', '/entity/openai'],
  ['graph', '/graph'], ['graph3d', '/graph3d'],
  ['article', '/article/5b811258271775ae27566e3f2d2d0751'],
  ['report-reader', '/report/2026-07-01.md'],
];
const cases = [
  { name: 'desktop-dark', width: 1440, height: 1000, theme: 'dark', screenshot: true },
  { name: 'tablet-light', width: 768, height: 1024, theme: 'light', screenshot: true },
  { name: 'mobile-480-light', width: 480, height: 900, theme: 'light', screenshot: false },
  { name: 'mobile-320-dark', width: 320, height: 900, theme: 'dark', screenshot: true },
];

await fs.mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const results = [];

try {
  for (const [slug, route] of routes) {
    for (const testCase of cases) {
      const context = await browser.newContext({
        viewport: { width: testCase.width, height: testCase.height },
        colorScheme: testCase.theme,
      });
      await context.addInitScript(theme => {
        localStorage.setItem('theme', theme);
        localStorage.setItem('lang', 'zh');
      }, testCase.theme);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(`page: ${error.message}`));
      page.on('console', message => {
        if (message.type() === 'error') errors.push(`console: ${message.text()}`);
      });
      const response = await page.goto(baseUrl + route, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(route.includes('graph') ? 2500 : 900);
      const metrics = await page.evaluate(() => {
        const root = document.documentElement;
        const template = document.querySelector('[data-page-template]')?.getAttribute('data-page-template') || '';
        const nav = document.querySelector('.nav');
        return {
          template,
          overflow: root.scrollWidth - root.clientWidth,
          navVisible: Boolean(nav && nav.getBoundingClientRect().height > 0),
          theme: document.documentElement.dataset.theme || localStorage.getItem('theme') || 'dark',
        };
      });
      if (testCase.screenshot) {
        await page.screenshot({ path: path.join(outputDir, `${slug}-${testCase.name}.png`), fullPage: true });
      }
      results.push({ slug, route, case: testCase.name, status: response?.status() || 0, ...metrics, errors });
      await context.close();
    }
  }
} finally {
  await browser.close();
}

const failures = results.filter(item => item.status !== 200 || item.overflow > 1 || !item.navVisible || !item.template || item.errors.length);
await fs.writeFile(path.join(outputDir, 'audit.json'), JSON.stringify({ generatedAt: new Date().toISOString(), results, failures }, null, 2));
console.log(JSON.stringify({ checks: results.length, screenshots: results.filter((_, index) => cases[index % cases.length].screenshot).length, failures }, null, 2));
process.exitCode = failures.length ? 1 : 0;
