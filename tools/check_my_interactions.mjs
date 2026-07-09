import { chromium } from '@playwright/test';

const baseUrl = process.env.AI_NEWS_BASE_URL || 'http://127.0.0.1:8765';
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await context.addInitScript(() => {
  const types = ['news', 'entity', 'report'];
  const items = Array.from({ length: 30 }, (_, index) => ({
    type: types[index % types.length],
    id: 'saved-' + index,
    title: index === 24 ? 'Agent Memory Architecture' : 'Saved intelligence ' + index,
    href: index % 3 === 1 ? '/entity/openai' : '/reports',
  }));
  localStorage.setItem('ai_observatory_favorites', JSON.stringify(items));
  localStorage.setItem('theme', 'dark');
  localStorage.setItem('lang', 'zh');
});
const page = await context.newPage();

try {
  await page.goto(baseUrl + '/my', { waitUntil: 'networkidle' });
  const search = page.locator('#my-search');
  await search.click();
  await search.pressSequentially('Agent Memory', { delay: 30 });
  if (!(await search.evaluate(el => document.activeElement === el))) {
    throw new Error('搜索列表更新后输入框丢失焦点');
  }
  const titles = await page.locator('.my-item__title').allTextContents();
  if (titles.length !== 1 || !titles[0].includes('Agent Memory')) {
    throw new Error('收藏搜索未稳定筛选目标内容');
  }

  await search.fill('');
  await page.waitForTimeout(100);
  await search.blur();
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = 'auto';
    window.scrollTo(0, 180);
  });
  const before = await page.evaluate(() => window.scrollY);
  await page.locator('.my-filter').nth(1).click();
  const after = await page.evaluate(() => window.scrollY);
  if (Math.abs(after - before) > 2) throw new Error('收藏类型筛选改变了滚动位置');
  if (!(await search.isVisible()) || !(await page.locator('#my-filter-controls').isVisible())) {
    throw new Error('筛选后搜索或筛选工具不可见');
  }
  const firstEditor = page.locator('.my-item__editor').first();
  if (await firstEditor.isVisible()) throw new Error('收藏整理控件未默认收起');
  await page.locator('.my-item').first().locator('.ui-button--ghost').first().click();
  if (!(await firstEditor.isVisible())) throw new Error('点击整理后编辑控件未展开');
  await page.screenshot({ path: 'output/playwright/my-populated.png', fullPage: true });
  console.log(JSON.stringify({ matched: titles, filterScrollDelta: after - before }, null, 2));
} finally {
  await browser.close();
}
