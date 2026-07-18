/** 隔离性能采样：核心页面冷缓存多样本 + 只读 API 顺序延迟。 */
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { performance } from 'node:perf_hooks';

const SCHEMA_VERSION = 1;
const RULE_VERSION = 4;
const require = createRequire(import.meta.url);
const playwrightVersion = require('@playwright/test/package.json').version;
const baseURL = process.env.PERFORMANCE_BASE_URL || 'http://127.0.0.1:8765';
const mode = process.env.PERFORMANCE_MODE || 'all';
const routes = JSON.parse(process.env.PERFORMANCE_ROUTES || '["/"]');
const apiEndpoints = JSON.parse(
  process.env.PERFORMANCE_API_ENDPOINTS ||
    '["/api/health","/api/entities","/api/articles?limit=10&min_score=0","/api/reports?type=daily&limit=5","/api/entities/openai"]',
);
const outputDir = path.resolve(
  process.env.PERFORMANCE_OUTPUT_DIR || 'output/performance-gate/manual',
);
const fixedTime =
  process.env.PERFORMANCE_FIXED_TIME || '2026-07-16T12:00:00.000Z';
const pageSamples = Number(process.env.PERFORMANCE_PAGE_SAMPLES || 3);
const apiSamples = Number(process.env.PERFORMANCE_API_SAMPLES || 20);
const baseOrigin = new URL(baseURL).origin;
const viewport = { width: 1440, height: 1000 };

function percentile(values, percent) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.max(0, Math.ceil((percent / 100) * sorted.length) - 1);
  return sorted[index];
}

function round(value, digits = 3) {
  return Number(Number(value || 0).toFixed(digits));
}

function aggregateNumber(samples, getter) {
  const values = samples.map(getter).filter(Number.isFinite);
  return {
    min: round(Math.min(...values)),
    p50: round(percentile(values, 50)),
    p95: round(percentile(values, 95)),
    max: round(Math.max(...values)),
  };
}

function isIgnoredFavicon(response) {
  const parsed = new URL(response.url);
  return parsed.pathname === '/favicon.ico' && response.status === 404;
}

async function samplePage(browser, route, sampleIndex) {
  const context = await browser.newContext({
    viewport,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  });
  await context.addInitScript(({ fixedTimeValue }) => {
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
    localStorage.setItem('theme', 'dark');
    localStorage.setItem('lang', 'zh');
    window.__perfAudit = { lcp: 0, layoutShifts: [], longTasks: [] };
    try {
      new PerformanceObserver(list => {
        const entries = list.getEntries();
        if (entries.length) {
          window.__perfAudit.lcp = entries[entries.length - 1].startTime;
        }
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch {}
    try {
      new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) {
            window.__perfAudit.layoutShifts.push({
              start: entry.startTime,
              value: entry.value,
            });
          }
        }
      }).observe({ type: 'layout-shift', buffered: true });
    } catch {}
    try {
      new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          window.__perfAudit.longTasks.push({
            start: entry.startTime,
            duration: entry.duration,
          });
        }
      }).observe({ type: 'longtask', buffered: true });
    } catch {}
  }, { fixedTimeValue: fixedTime });

  const externalRequests = [];
  const webSockets = [];
  const nonGetRequests = [];
  await context.route('**/*', async routeHandle => {
    const request = routeHandle.request();
    const url = request.url();
    const parsed = new URL(url);
    if (request.method() !== 'GET') {
      nonGetRequests.push({ url, method: request.method() });
      await routeHandle.abort('blockedbyclient');
      return;
    }
    if (
      parsed.origin !== baseOrigin &&
      !['data:', 'blob:', 'about:'].includes(parsed.protocol)
    ) {
      externalRequests.push(url);
      await routeHandle.abort('blockedbyclient');
      return;
    }
    await routeHandle.continue();
  });
  await context.routeWebSocket('**/*', async ws => {
    webSockets.push(ws.url());
    await ws.close({ code: 1008, reason: 'Performance gate blocks WebSocket' });
  });

  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
  let encodedBytes = 0;
  cdp.on('Network.loadingFinished', event => {
    encodedBytes += Number(event.encodedDataLength || 0);
  });

  const responses = [];
  const failedRequests = [];
  page.on('response', response => responses.push(response));
  page.on('requestfailed', request => {
    if (
      !externalRequests.includes(request.url()) &&
      !nonGetRequests.some(item => item.url === request.url())
    ) {
      failedRequests.push({
        url: request.url(),
        error: request.failure()?.errorText || '',
      });
    }
  });

  const started = performance.now();
  let response = null;
  let navigationError = '';
  try {
    response = await page.goto(`${baseURL}${route}`, {
      waitUntil: 'networkidle',
      timeout: 30000,
    });
    await page.waitForTimeout(300);
  } catch (error) {
    navigationError = error.message;
  }
  const wallMs = performance.now() - started;

  const responseDetails = await Promise.all(
    responses.map(async item => {
      let bodyBytes = 0;
      try {
        bodyBytes = (await item.body()).byteLength;
      } catch {}
      return {
        url: item.url(),
        status: item.status(),
        method: item.request().method(),
        resourceType: item.request().resourceType(),
        bodyBytes,
      };
    }),
  );
  const metrics = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const paints = Object.fromEntries(
      performance.getEntriesByType('paint').map(entry => [entry.name, entry.startTime]),
    );
    const audit = window.__perfAudit || {
      lcp: 0,
      layoutShifts: [],
      longTasks: [],
    };
    let cls = 0;
    let windowValue = 0;
    let windowStart = 0;
    let previousShift = 0;
    for (const shift of audit.layoutShifts) {
      const startsNewWindow =
        !windowStart ||
        shift.start - previousShift > 1000 ||
        shift.start - windowStart > 5000;
      if (startsNewWindow) {
        windowStart = shift.start;
        windowValue = shift.value;
      } else {
        windowValue += shift.value;
      }
      previousShift = shift.start;
      cls = Math.max(cls, windowValue);
    }
    return {
      ttfbMs: nav?.responseStart || 0,
      domContentLoadedMs: nav?.domContentLoadedEventEnd || 0,
      loadMs: nav?.loadEventEnd || 0,
      fcpMs: paints['first-contentful-paint'] || 0,
      lcpMs: audit.lcp || 0,
      cls,
      longTaskCount: audit.longTasks.length,
      longTaskTotalMs: audit.longTasks.reduce(
        (total, entry) => total + entry.duration,
        0,
      ),
      longTaskMaxMs: audit.longTasks.reduce(
        (maximum, entry) => Math.max(maximum, entry.duration),
        0,
      ),
      domNodes: document.getElementsByTagName('*').length,
      bodyTextLength: String(document.body?.innerText || '').trim().length,
    };
  });
  await context.close();

  return {
    route,
    sample: sampleIndex,
    status: response?.status() || 0,
    navigationError,
    wallMs: round(wallMs),
    ...Object.fromEntries(
      Object.entries(metrics).map(([key, value]) => [key, round(value)]),
    ),
    requestCount: responseDetails.length,
    encodedBytes: round(encodedBytes),
    decodedBytes: responseDetails.reduce((sum, item) => sum + item.bodyBytes, 0),
    badResponses: responseDetails.filter(
      item => item.status >= 400 && !isIgnoredFavicon(item),
    ),
    ignoredResponses: responseDetails.filter(isIgnoredFavicon),
    failedRequests,
    externalRequests,
    webSockets,
    nonGetRequests,
    responses: responseDetails,
  };
}

function aggregatePage(route, samples) {
  return {
    route,
    samples: samples.length,
    statusErrors: samples.filter(item => item.status !== 200).length,
    navigationErrors: samples.filter(item => item.navigationError).length,
    failedRequests: samples.reduce((sum, item) => sum + item.failedRequests.length, 0),
    badResponses: samples.reduce((sum, item) => sum + item.badResponses.length, 0),
    externalRequests: samples.reduce((sum, item) => sum + item.externalRequests.length, 0),
    webSockets: samples.reduce((sum, item) => sum + item.webSockets.length, 0),
    nonGetRequests: samples.reduce((sum, item) => sum + item.nonGetRequests.length, 0),
    ttfbMs: aggregateNumber(samples, item => item.ttfbMs),
    domContentLoadedMs: aggregateNumber(samples, item => item.domContentLoadedMs),
    loadMs: aggregateNumber(samples, item => item.loadMs),
    fcpMs: aggregateNumber(samples, item => item.fcpMs),
    lcpMs: aggregateNumber(samples, item => item.lcpMs),
    cls: aggregateNumber(samples, item => item.cls),
    longTaskCount: aggregateNumber(samples, item => item.longTaskCount),
    longTaskTotalMs: aggregateNumber(samples, item => item.longTaskTotalMs),
    longTaskMaxMs: aggregateNumber(samples, item => item.longTaskMaxMs),
    requestCount: aggregateNumber(samples, item => item.requestCount),
    encodedBytes: aggregateNumber(samples, item => item.encodedBytes),
    decodedBytes: aggregateNumber(samples, item => item.decodedBytes),
    domNodes: aggregateNumber(samples, item => item.domNodes),
    bodyTextLength: aggregateNumber(samples, item => item.bodyTextLength),
    wallMs: aggregateNumber(samples, item => item.wallMs),
  };
}

function pageSampleErrors(sample) {
  return (
    (sample.status !== 200 ? 1 : 0) +
    (sample.navigationError ? 1 : 0) +
    sample.failedRequests.length +
    sample.badResponses.length +
    sample.externalRequests.length +
    sample.webSockets.length +
    sample.nonGetRequests.length
  );
}

async function sampleAPI(endpoint) {
  const url = `${baseURL}${endpoint}`;
  const warmup = {
    sample: 0,
    url,
    method: 'GET',
    durationMs: 0,
    status: 0,
    bodyBytes: 0,
    error: '',
  };
  const warmupStarted = performance.now();
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'cache-control': 'no-cache' },
    });
    const body = Buffer.from(await response.arrayBuffer());
    warmup.status = response.status;
    warmup.bodyBytes = body.byteLength;
  } catch (caught) {
    warmup.error = caught.message;
  }
  warmup.durationMs = round(performance.now() - warmupStarted);
  const samples = [];
  for (let index = 0; index < apiSamples; index += 1) {
    const started = performance.now();
    let status = 0;
    let bodyBytes = 0;
    let error = '';
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'cache-control': 'no-cache' },
      });
      const body = Buffer.from(await response.arrayBuffer());
      status = response.status;
      bodyBytes = body.byteLength;
    } catch (caught) {
      error = caught.message;
    }
    samples.push({
      sample: index + 1,
      url,
      method: 'GET',
      durationMs: round(performance.now() - started),
      status,
      bodyBytes,
      error,
    });
  }
  return {
    endpoint,
    warmup,
    samples,
    aggregate: {
      samples: samples.length,
      warmupErrors: warmup.error || warmup.status !== 200 ? 1 : 0,
      errors: samples.filter(item => item.error || item.status !== 200).length,
      durationMs: aggregateNumber(samples, item => item.durationMs),
      bodyBytes: aggregateNumber(samples, item => item.bodyBytes),
    },
  };
}

async function main() {
  if (!['all', 'pages', 'apis'].includes(mode)) {
    throw new Error('PERFORMANCE_MODE 必须是 all、pages 或 apis');
  }
  if (!Number.isInteger(pageSamples) || pageSamples < 3) {
    throw new Error('PERFORMANCE_PAGE_SAMPLES 必须是 >=3 的整数');
  }
  if (!Number.isInteger(apiSamples) || apiSamples < 20) {
    throw new Error('PERFORMANCE_API_SAMPLES 必须是 >=20 的整数');
  }
  await fs.mkdir(outputDir, { recursive: true });

  const pageResults = [];
  let browserVersion = '';
  if (mode !== 'apis') {
    const browser = await chromium.launch({ headless: true });
    browserVersion = browser.version();
    try {
      for (const route of routes) {
        const warmup = await samplePage(browser, route, 0);
        const samples = [];
        for (let index = 1; index <= pageSamples; index += 1) {
          samples.push(await samplePage(browser, route, index));
        }
        pageResults.push({
          route,
          warmup,
          warmupErrors: pageSampleErrors(warmup),
          samples,
          aggregate: aggregatePage(route, samples),
        });
      }
    } finally {
      await browser.close();
    }
  }

  const apiResults = [];
  if (mode !== 'pages') {
    for (const endpoint of apiEndpoints) {
      apiResults.push(await sampleAPI(endpoint));
    }
  }
  const audit = {
    schemaVersion: SCHEMA_VERSION,
    ruleVersion: RULE_VERSION,
    mode,
    generatedAt: new Date().toISOString(),
    fixedTime,
    baseOrigin,
    environment: {
      node: process.version,
      playwright: playwrightVersion,
      chromium: browserVersion,
      platform: `${process.platform}-${process.arch}`,
    },
    measurement: {
      viewport,
      colorScheme: 'dark',
      reducedMotion: 'reduce',
      cacheDisabled: true,
      pageWarmupsPerRoute: 1,
      apiWarmupsPerEndpoint: 1,
    },
    pageSamples,
    apiSamples,
    routes,
    apiEndpoints,
    pages: pageResults,
    apis: apiResults,
    summary: {
      pageRoutes: pageResults.length,
      pageSamples: pageResults.reduce((sum, item) => sum + item.samples.length, 0),
      apiEndpoints: apiResults.length,
      apiSamples: apiResults.reduce((sum, item) => sum + item.samples.length, 0),
      pageErrors: pageResults.reduce(
        (sum, item) =>
          sum +
          item.warmupErrors +
          item.aggregate.statusErrors +
          item.aggregate.navigationErrors +
          item.aggregate.failedRequests +
          item.aggregate.badResponses +
          item.aggregate.externalRequests +
          item.aggregate.webSockets +
          item.aggregate.nonGetRequests,
        0,
      ),
      apiErrors: apiResults.reduce(
        (sum, item) =>
          sum + item.aggregate.warmupErrors + item.aggregate.errors,
        0,
      ),
    },
  };
  await fs.writeFile(
    path.join(outputDir, 'audit.json'),
    JSON.stringify(audit, null, 2),
  );
  console.log(JSON.stringify(audit.summary, null, 2));
  process.exitCode =
    audit.summary.pageErrors || audit.summary.apiErrors ? 1 : 0;
}

main().catch(error => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
