/** 收藏、已读、稍后在五星精选、报告阅读器和 My 之间的浏览器联动回归。 */
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';

const baseUrl = process.env.AI_NEWS_BASE_URL || 'http://127.0.0.1:8765';
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const outputDir = 'output/playwright/collection-flows';
await fs.mkdir(outputDir, { recursive: true });

const articles = Array.from({ length: 8 }, (_, index) => ({
  id: `star5-${index + 1}`,
  title: `Star Five ${index + 1}`,
  title_cn: `五星文章 ${index + 1}`,
  score: 5,
  source: '验收源',
  published: '2026-07-05',
  one_liner: `第 ${index + 1} 篇五星文章摘要`,
  url: `https://example.com/${index + 1}`,
}));

const expect = (condition, message) => {
  if (!condition) throw new Error(message);
};

try {
  await page.route('**/api/articles?**', route => route.fulfill({ json: articles }));
  await page.route('**/api/reports?**', route => route.fulfill({ json: [] }));
  await page.addInitScript(() => {
    if (sessionStorage.getItem('collection-flow-ready')) return;
    sessionStorage.setItem('collection-flow-ready', '1');
    localStorage.setItem('lang', 'zh');
    localStorage.removeItem('ai_observatory_favorites');
    localStorage.removeItem('ai_observatory_personal_meta');
  });

  await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.star5-item');
  expect(await page.locator('.star5-item').count() === 5, '五星精选首次加载不是 5 篇');
  await page.screenshot({ path: `${outputDir}/star5-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${outputDir}/star5-mobile.png`, fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });

  const firstId = await page.locator('.star5-item').first().locator('[data-kind="fav"]').getAttribute('data-id');
  await page.locator(`.star5-action[data-id="${firstId}"][data-kind="fav"]`).click();
  expect(await page.locator('.star5-item').count() === 5, '收藏后五星精选数量发生变化');
  expect(await page.locator(`.star5-action[data-id="${firstId}"]`).count() === 3, '收藏后当前文章被替换');

  await page.locator(`.star5-action[data-id="${firstId}"][data-kind="read"]`).click();
  expect(await page.locator('.star5-item').count() === 5, '已读后没有补足 5 篇');
  expect(await page.locator(`.star5-action[data-id="${firstId}"]`).count() === 0, '已读文章未退出五星精选');

  const laterId = await page.locator('.star5-item').first().locator('[data-kind="later"]').getAttribute('data-id');
  await page.locator(`.star5-action[data-id="${laterId}"][data-kind="later"]`).click();
  expect(await page.locator('.star5-item').count() === 5, '稍后操作后没有补足 5 篇');
  expect(await page.locator(`.star5-action[data-id="${laterId}"]`).count() === 0, '稍后文章未退出五星精选');

  await page.goto(`${baseUrl}/my`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.my-item');
  const homeItems = await page.locator('.my-item').allTextContents();
  expect(homeItems.some(text => text.includes('五星文章 1') && text.includes('已读')), '收藏/已读文章未联动到 My');
  expect(homeItems.some(text => text.includes('稍后')), '稍后文章未联动到 My');

  await page.goto(`${baseUrl}/report/2026-07-02.md`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.markdown-body h2');
  const actualHeadings = await page.locator('.markdown-body h2').count();
  const actualActions = await page.locator('.markdown-body .ra-actions').count();
  expect(actualHeadings > 0 && actualActions === actualHeadings, `真实日报逐篇操作缺失：${actualActions}/${actualHeadings}`);
  await page.screenshot({ path: `${outputDir}/actual-daily-actions-desktop.png`, fullPage: false });

  const report = `# 验收报告\n\n## ★★★★★ Report Alpha\n\nAlpha 摘要。\n\n[详情](/article/report-a)\n\n---\n\n## ★★★★★ Report Beta\n\nBeta 摘要。\n\n[详情](/article/report-b)`;
  await page.route('**/api/report-content/**', route => route.fulfill({ json: { content: report } }));
  await page.goto(`${baseUrl}/report/test.md`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.ra-actions');
  expect(await page.locator('.ra-actions').count() === 2, '报告文章操作组数量错误');
  expect(await page.locator('.ra-btn').count() === 6, '报告文章未各自显示三个操作');
  await page.screenshot({ path: `${outputDir}/report-actions-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${outputDir}/report-actions-mobile.png`, fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.locator('.ra-actions').nth(0).locator('[data-kind="fav"]').click();
  await page.locator('.ra-actions').nth(0).locator('[data-kind="read"]').click();
  await page.locator('.ra-actions').nth(1).locator('[data-kind="later"]').click();

  await page.goto(`${baseUrl}/my`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.my-item');
  const reportItems = await page.locator('.my-item').allTextContents();
  expect(reportItems.some(text => text.includes('Report Alpha') && text.includes('已读')), '报告收藏/已读未联动到 My');
  expect(reportItems.some(text => text.includes('Report Beta') && text.includes('稍后')), '报告稍后未联动到 My');
  await page.screenshot({ path: `${outputDir}/my-integration-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${outputDir}/my-integration-mobile.png`, fullPage: true });

  console.log(JSON.stringify({
    star5Initial: 5,
    favoriteKeepsList: true,
    readAndLaterRefill: true,
    reportActionGroups: 2,
    actualDailyActionGroups: actualActions,
    myIntegration: true,
  }, null, 2));
} finally {
  await context.close();
  await browser.close();
}
