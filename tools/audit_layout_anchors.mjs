import { chromium } from '@playwright/test';

const baseUrl = process.env.AI_NEWS_BASE_URL || 'http://127.0.0.1:8765';
const pages = [
  ['today', '/', '.home-heading', '#reports-hero'],
  ['topics', '/library', '.page-heading', '.library-tools'],
  ['timeline', '/timeline', '.timeline-heading', '.controls'],
  ['research', '/research', '.ui-page-header', '.research-layout'],
  ['my', '/my', '.ui-page-header', '.my-layout'],
];
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const results = [];

try {
  for (const [name, route, headingSelector, contentSelector] of pages) {
    await page.goto(baseUrl + route, { waitUntil: 'networkidle' });
    const metrics = await page.evaluate(({ headingSelector, contentSelector }) => {
      const rect = (element) => {
        const box = element?.getBoundingClientRect();
        return box ? { x: Math.round(box.x), y: Math.round(box.y), width: Math.round(box.width), height: Math.round(box.height) } : null;
      };
      return {
        frame: rect(document.querySelector('.app-shell') || document.body),
        nav: rect(document.querySelector('.nav')),
        heading: rect(document.querySelector(headingSelector)),
        title: rect(document.querySelector('h1')),
        content: rect(document.querySelector(contentSelector)),
      };
    }, { headingSelector, contentSelector });
    results.push({ name, route, ...metrics });
  }
} finally {
  await browser.close();
}

const spread = (key, axis) => {
  const values = results.map(item => item[key]?.[axis]).filter(Number.isFinite);
  return Math.max(...values) - Math.min(...values);
};
const failures = [];
if (spread('frame', 'x') > 2 || spread('frame', 'width') > 2) failures.push('普通页面宽度或水平起点不一致');
if (spread('nav', 'x') > 2 || spread('nav', 'y') > 2) failures.push('一级导航位置不一致');
if (spread('heading', 'x') > 2 || spread('heading', 'y') > 2) failures.push('页面标题区锚点不一致');

console.log(JSON.stringify({ results, spreads: {
  frameX: spread('frame', 'x'), frameWidth: spread('frame', 'width'),
  navX: spread('nav', 'x'), navY: spread('nav', 'y'),
  headingX: spread('heading', 'x'), headingY: spread('heading', 'y'),
  titleX: spread('title', 'x'), titleY: spread('title', 'y'),
}, failures }, null, 2));
if (failures.length) process.exitCode = 1;
