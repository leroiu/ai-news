import { chromium } from '@playwright/test';

const baseUrl = process.env.AI_NEWS_BASE_URL || 'http://127.0.0.1:8765';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
let attempts = 0;

await page.route('**/api/research', async route => {
  attempts += 1;
  if (attempts === 1) {
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'temporary failure' }) });
    return;
  }
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ report: {
      _meta: { topic: 'Agent Memory', entity_count: 3, article_count: 5, depth: 'standard' },
      summary: 'Recovered research result',
      key_findings: [],
    }}),
  });
});

try {
  await page.goto(baseUrl + '/research', { waitUntil: 'networkidle' });
  await page.locator('#research-topic').fill('Agent Memory');
  await page.locator('#research-btn').click();
  await page.locator('.error-box[data-ui-state="error"]').waitFor();
  if (!(await page.locator('.error-box button').isVisible())) throw new Error('错误状态缺少重试入口');

  await page.locator('.error-box button').click();
  await page.locator('#report-container.visible').waitFor();
  const saved = await page.evaluate(() => sessionStorage.getItem('ai_observatory_last_research'));
  if (!saved?.includes('Agent Memory')) throw new Error('成功结果未写入会话恢复存储');

  await page.reload({ waitUntil: 'networkidle' });
  await page.locator('#report-container.visible').waitFor();
  if (await page.locator('#output-placeholder').isVisible()) throw new Error('恢复报告后 Idle 占位仍可见');
  if ((await page.locator('#research-topic').inputValue()) !== 'Agent Memory') throw new Error('恢复报告后研究主题未回填');
  const status = await page.locator('#research-status').textContent();
  if (!status?.includes('恢复')) throw new Error('刷新后未恢复上次研究结果');
  await page.screenshot({ path: 'output/playwright/research-restored.png', fullPage: true });
  console.log(JSON.stringify({ attempts, restoredStatus: status }, null, 2));
} finally {
  await browser.close();
}
