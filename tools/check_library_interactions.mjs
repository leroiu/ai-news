import { chromium } from '@playwright/test';

const baseUrl = process.env.AI_NEWS_BASE_URL || 'http://127.0.0.1:8765';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

try {
  await page.goto(baseUrl + '/library', { waitUntil: 'networkidle' });

  await page.locator('.cat-tag[data-cat="company"]').click();
  await page.locator('#search').fill('Sam');
  await page.waitForTimeout(900);
  const samNames = await page.locator('.card-header .name').allTextContents();
  if (!samNames.some(name => name.includes('Sam Altman'))) {
    throw new Error('从其他分类输入 Sam 后未稳定显示 Sam Altman');
  }
  if (!(await page.locator('.cat-tag[data-cat="all"]').evaluate(el => el.classList.contains('active')))) {
    throw new Error('分类无匹配但全局有匹配时未自动回到全部');
  }
  await page.screenshot({ path: 'output/playwright/library-search-sam.png', fullPage: true });

  await page.locator('#search').fill('Sam Altman');
  await page.waitForTimeout(900);
  const exactNames = await page.locator('.card-header .name').allTextContents();
  if (!exactNames.some(name => name.includes('Sam Altman'))) {
    throw new Error('继续输入 Sam Altman 后目标卡片消失');
  }
  const href = await page.locator('.card').filter({ hasText: 'Sam Altman' }).first().getAttribute('onclick');
  if (!href?.includes('/entity/')) throw new Error('Sam Altman 卡片不可进入详情');

  await page.locator('#search').fill('');
  await page.waitForTimeout(250);
  const restoredState = await page.evaluate(() => ({
    cards: document.querySelectorAll('.card').length,
    scrollHeight: document.documentElement.scrollHeight,
    active: document.querySelector('.cat-tag.active')?.dataset.cat,
  }));
  await page.locator('#search').blur();
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = 'auto';
    window.scrollTo(0, 700);
  });
  await page.waitForTimeout(100);
  const scrollBeforeCategory = await page.evaluate(() => window.scrollY);
  await page.locator('.cat-tag[data-cat="company"]').click();
  const scrollAfterCategory = await page.evaluate(() => window.scrollY);
  if (Math.abs(scrollAfterCategory - scrollBeforeCategory) > 2) {
    throw new Error('分类筛选改变了用户滚动位置: ' + scrollBeforeCategory + ' → ' + scrollAfterCategory + ' state=' + JSON.stringify(restoredState));
  }
  const types = await page.locator('.card-header .type-badge').allTextContents();
  if (!types.length || types.some(type => !type.toLowerCase().includes('company') && !type.includes('公司'))) {
    throw new Error('Company 分类未正确筛选列表');
  }
  if (!(await page.locator('#search').isVisible()) || !(await page.locator('#category-nav').isVisible())) {
    throw new Error('分类筛选后搜索框或分类栏不可见');
  }
  await page.screenshot({ path: 'output/playwright/library-filter-company.png', fullPage: true });

  console.log(JSON.stringify({
    samNames, exactNames, companyCount: types.length,
    categoryScrollDelta: scrollAfterCategory - scrollBeforeCategory,
  }, null, 2));
} finally {
  await browser.close();
}
