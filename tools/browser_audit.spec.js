const { test, expect } = require('@playwright/test');
const path = require('path');

const baseURL = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:8765';
const routes = JSON.parse(process.env.FRONTEND_ROUTES || '["/"]');
const outputDir = process.env.FRONTEND_OUTPUT_DIR || 'output/playwright';

function slug(route) {
  return route.replace(/^\/+|\/+$/g, '').replaceAll('/', '-') || 'home';
}

for (const route of routes) {
  for (const viewport of [
    { name: 'desktop', width: 1440, height: 1000 },
    { name: 'mobile', width: 390, height: 844 },
  ]) {
    test(`${route} ${viewport.name}`, async ({ page }) => {
      const errors = [];
      page.on('console', message => {
        if (message.type() === 'error') errors.push(`console: ${message.text()}`);
      });
      page.on('pageerror', error => errors.push(`pageerror: ${error.message}`));
      await page.setViewportSize(viewport);
      const response = await page.goto(`${baseURL}${route}`, { waitUntil: 'networkidle' });
      expect(response && response.ok(), `HTTP ${route}`).toBeTruthy();
      await page.waitForTimeout(2000);
      const overflow = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
      }));
      expect(overflow.document, `页面级横向溢出 ${JSON.stringify(overflow)}`).toBeLessThanOrEqual(overflow.viewport + 1);
      expect(errors, errors.join('\n')).toEqual([]);
      await page.screenshot({
        path: path.join(outputDir, `${slug(route)}-${viewport.name}.png`),
        fullPage: true,
      });
    });
  }
}
