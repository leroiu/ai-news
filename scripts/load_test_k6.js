// ============================================================
// load_test_k6.js — AI 观察室性能测试场景（k6）
//
// 由 scripts/load_test.sh 调用，不建议手动直接 k6 run。
// 全部参数通过环境变量注入。
//
// 环境变量：
//   PROFILE        smoke-load | rate-limit-load | normal-load |
//                  peak-load | spike-test | soak-test | limit-test
//   TARGET_URL     目标站点根地址
//   STATIC_PATHS   逗号分隔的静态页面路径
//   API_PATHS      逗号分隔的 API 路径（只读 GET）
//   REPORT_PATH    可选，报告阅读器路由
//   SUMMARY_JSON   结果 JSON 落盘路径
//   LIMIT_MAX_VUS  limit-test 并发上限（默认 200）
//
// 关键设计：
//   - 429（限流）和 5xx（系统错误）分开统计
//   - smoke-load 必须不触发 429；rate-limit-load 专门触发 429
//   - 熔断仅对 5xx 触发，429 不熔断
// ============================================================

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

// ---------- 参数解析 ----------
const PROFILE = (__ENV.PROFILE || 'smoke-load').trim();
const TARGET = (__ENV.TARGET_URL || 'http://121.43.80.221').replace(/\/+$/, '');
const LIMIT_MAX_VUS = parseInt(__ENV.LIMIT_MAX_VUS || '200', 10);

const STATIC_PATHS = (__ENV.STATIC_PATHS || '/,/reports,/my')
  .split(',').map((s) => s.trim()).filter(Boolean);
const API_PATHS = (__ENV.API_PATHS ||
  '/api/health,/api/reports?type=daily&limit=5,/api/articles?limit=10&min_score=4')
  .split(',').map((s) => s.trim()).filter(Boolean);
const REPORT_PATH = (__ENV.REPORT_PATH || '').trim();

if (REPORT_PATH) STATIC_PATHS.push(REPORT_PATH);

// ---------- 安全护栏：只允许只读 GET ----------
const FORBIDDEN = ['/api/pipeline', '/api/research', '/api/favorites',
  '/api/reading-history', '/api/embeddings/rebuild', '/api/migrations/run', '/api/entities'];
for (const p of [...STATIC_PATHS, ...API_PATHS]) {
  for (const bad of FORBIDDEN) {
    if (p.startsWith(bad)) {
      throw new Error(`拒绝压测可能有副作用的端点: ${p}（仅允许只读 GET）`);
    }
  }
}

// ---------- 自定义指标 ----------
const staticDur = new Trend('static_page_duration', true);
const apiDur = new Trend('api_duration', true);
// 429 限流 vs 真错误分开
const realErrorRate = new Rate('real_error_rate');    // 4xx(排除429) + 5xx
const rateLimitRate = new Rate('rate_limit_hit');     // 仅 429

// ---------- 各 profile 的并发曲线 ----------
// 后端限流 120 req/min ≈ 2 rps。
// 1 VU × 6 paths / iteration ≈ 6 req/iteration。
// think time 4s → 6/4.6 ≈ 1.3 rps ≈ 78 rpm → 安全
// think time 1s → 6/1.6 ≈ 3.75 rps ≈ 225 rpm → 会触发限流

function stagesFor(profile) {
  switch (profile) {
    case 'smoke-load':
      // 1 VU / 30s — 低强度健康检查，不触发限流
      return [{ duration: '5s', target: 1 }, { duration: '20s', target: 1 }, { duration: '5s', target: 0 }];

    case 'rate-limit-load':
      // 2→20 VUs / 120s — 专门测试限流，429 是预期结果
      return [
        { duration: '10s', target: 2 },
        { duration: '20s', target: 5 },
        { duration: '30s', target: 10 },
        { duration: '30s', target: 20 },
        { duration: '10s', target: 0 },
      ];

    case 'normal-load':
      // 3 VUs / 60s — 中等负载（会触发部分限流）
      return [{ duration: '10s', target: 3 }, { duration: '40s', target: 3 }, { duration: '10s', target: 0 }];

    case 'peak-load':
      // 10 VUs / 120s — 高峰（大量限流预期）
      return [{ duration: '20s', target: 10 }, { duration: '90s', target: 10 }, { duration: '10s', target: 0 }];

    case 'spike-test':
      // 1→50→1 突刺
      return [
        { duration: '10s', target: 1 },
        { duration: '5s', target: 50 },
        { duration: '30s', target: 50 },
        { duration: '5s', target: 0 },
      ];

    case 'soak-test':
      // 2 VUs / 30min 长稳
      return [{ duration: '1m', target: 2 }, { duration: '30m', target: 2 }, { duration: '1m', target: 0 }];

    case 'limit-test':
      // 阶梯递增找上限
      return buildLimitStages(LIMIT_MAX_VUS);

    default:
      throw new Error(`未知 PROFILE: ${profile}`);
  }
}

function buildLimitStages(maxVus) {
  const stages = [];
  for (let v = 5; v <= maxVus; v += 5) {
    stages.push({ duration: '30s', target: v });
  }
  stages.push({ duration: '10s', target: 0 });
  return stages;
}

// think time：smoke-load 长停顿确保不触发限流；高压场景短停顿
function thinkTimeFor(profile) {
  switch (profile) {
    case 'smoke-load': return 4.0;   // 6 paths / (6*0.1 + 4) ≈ 1.3 rps → 78 rpm < 120
    case 'rate-limit-load': return 0.5;
    case 'soak-test': return 2.0;
    default: return 0.5;             // peak/spike/limit/normal: 短停顿模拟真实
  }
}
const THINK = thinkTimeFor(PROFILE);

// ---------- k6 options ----------
// 阈值策略：按 profile 区分
// - smoke-load: 不允许限流(429)，不允许真错误
// - rate-limit-load: 允许限流，但不允许 5xx
// - 其他: 允许部分限流，不允许高真错误率
function thresholdsFor(profile) {
  const base = {
    'static_page_duration': ['p(95)<500'],
    'api_duration': ['p(95)<1500'],
    'http_req_duration': ['p(99)<3000'],
  };

  switch (profile) {
    case 'smoke-load':
      return {
        ...base,
        'real_error_rate': ['rate==0'],       // 不允许任何真错误
        'rate_limit_hit': ['rate==0'],         // 不允许触发限流
      };
    case 'rate-limit-load':
      return {
        ...base,
        'real_error_rate': [
          'rate<0.01',                                                       // 5xx < 1%
          { threshold: 'rate<0.15', abortOnFail: true, delayAbortEval: '20s' }, // 5xx 熔断
        ],
        // rate_limit_hit 无阈值 — 429 是预期结果
      };
    default:
      return {
        ...base,
        'real_error_rate': [
          'rate<0.01',
          { threshold: 'rate<0.15', abortOnFail: true, delayAbortEval: '20s' },
        ],
        'rate_limit_hit': ['rate<0.50'],  // 允许限流但不超过 50%
      };
  }
}

export const options = {
  scenarios: {
    default: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: stagesFor(PROFILE),
      gracefulRampDown: '10s',
    },
  },
  thresholds: thresholdsFor(PROFILE),
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  noConnectionReuse: false,
  discardResponseBodies: false,
};

// ---------- 单次迭代 ----------
function bucketStatus(status) {
  if (status >= 200 && status < 300) return '2xx';
  if (status === 429) return '429';
  if (status >= 400 && status < 500) return '4xx';
  if (status >= 500 && status < 600) return '5xx';
  return 'other';
}

function sampleBody(res) {
  if (!res.body) return '(empty body)';
  const s = typeof res.body === 'string' ? res.body : String(res.body);
  return s.replace(/\s+/g, ' ').slice(0, 120);
}

export default function () {
  group('static', function () {
    for (const path of STATIC_PATHS) {
      const url = `${TARGET}${path}`;
      const res = http.get(url, { tags: { type: 'static', path } });
      const bucket = bucketStatus(res.status);

      // 动态 check：每个路径按状态码区间计数（写入 data.root_group）
      check(res, {
        [`${path} → 2xx`]: (r) => r.status >= 200 && r.status < 300,
        [`${path} → 429`]: (r) => r.status === 429,
        [`${path} → 4xx`]: (r) => r.status >= 400 && r.status < 500 && r.status !== 429,
        [`${path} → 5xx`]: (r) => r.status >= 500 && r.status < 600,
      });

      // 分离限流 vs 真错误
      if (res.status === 429) {
        rateLimitRate.add(true);
        realErrorRate.add(false);
      } else if (res.status >= 400) {
        rateLimitRate.add(false);
        realErrorRate.add(true);
        console.log(`[REAL-ERROR] ${path} status=${res.status} body="${sampleBody(res)}"`);
      } else {
        rateLimitRate.add(false);
        realErrorRate.add(false);
      }

      // 非 2xx 都打印（429 也打印，方便观察限流时间点）
      if (res.status !== 200) {
        console.log(`[NON-2XX] ${path} status=${res.status} bucket=${bucket} body="${sampleBody(res)}"`);
      }

      staticDur.add(res.timings.duration);
    }
  });

  group('api', function () {
    for (const path of API_PATHS) {
      const url = `${TARGET}${path}`;
      const res = http.get(url, { tags: { type: 'api', path } });
      const bucket = bucketStatus(res.status);

      check(res, {
        [`${path} → 2xx`]: (r) => r.status >= 200 && r.status < 300,
        [`${path} → 429`]: (r) => r.status === 429,
        [`${path} → 4xx`]: (r) => r.status >= 400 && r.status < 500 && r.status !== 429,
        [`${path} → 5xx`]: (r) => r.status >= 500 && r.status < 600,
      });

      if (res.status === 429) {
        rateLimitRate.add(true);
        realErrorRate.add(false);
      } else if (res.status >= 400) {
        rateLimitRate.add(false);
        realErrorRate.add(true);
        console.log(`[REAL-ERROR] ${path} status=${res.status} body="${sampleBody(res)}"`);
      } else {
        rateLimitRate.add(false);
        realErrorRate.add(false);
      }

      if (res.status !== 200) {
        console.log(`[NON-2XX] ${path} status=${res.status} bucket=${bucket} body="${sampleBody(res)}"`);
      }

      apiDur.add(res.timings.duration);
    }
  });

  if (THINK > 0) sleep(THINK);
}

// ---------- 从 data.root_group 解析每个路径的状态码分布 ----------
function collectStatusStats(data) {
  const stats = {};
  function walk(node) {
    if (!node) return;
    if (node.checks) {
      for (const c of node.checks) {
        // c.name 形如 "/api/health → 2xx" 或 "/api/health → 429"
        const m = c.name.match(/^(.+?) → (2xx|429|4xx|5xx)$/);
        if (m) {
          const [, path, bucket] = m;
          if (!stats[path]) stats[path] = { total: 0, '2xx': 0, '429': 0, '4xx': 0, '5xx': 0 };
          stats[path][bucket] += c.passes;
          stats[path].total += c.passes + c.fails;
        }
      }
    }
    if (node.groups) {
      for (const g of node.groups) walk(g);
    }
  }
  walk(data.root_group);
  return stats;
}

function statusSummary(data) {
  const stats = collectStatusStats(data);
  const lines = ['  路径状态码统计：'];
  for (const path of [...STATIC_PATHS, ...API_PATHS]) {
    const s = stats[path] || { total: 0, '2xx': 0, '429': 0, '4xx': 0, '5xx': 0 };
    lines.push(`    ${path}`);
    lines.push(`      总请求: ${s.total} | 2xx: ${s['2xx']} | 429(限流): ${s['429']} | 4xx: ${s['4xx']} | 5xx: ${s['5xx']}`);
  }
  return lines.join('\n');
}

// ---------- 结果落盘 ----------
export function handleSummary(data) {
  const out = {};
  const jsonPath = __ENV.SUMMARY_JSON || '';
  if (jsonPath) {
    out[jsonPath] = JSON.stringify(data, null, 2);
  }
  out['stdout'] = textSummary(data);
  return out;
}

function metricVal(data, name, key) {
  const m = data.metrics[name];
  if (!m || !m.values) return null;
  return m.values[key] != null ? m.values[key] : null;
}

function textSummary(data) {
  const realErr = data.metrics.real_error_rate
    ? (data.metrics.real_error_rate.values.rate * 100).toFixed(2)
    : 'n/a';
  const rateLimit = data.metrics.rate_limit_hit
    ? (data.metrics.rate_limit_hit.values.rate * 100).toFixed(2)
    : 'n/a';
  const reqs = data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 'n/a';
  const staticP95 = metricVal(data, 'static_page_duration', 'p(95)');
  const apiP95 = metricVal(data, 'api_duration', 'p(95)');

  const lines = [
    '',
    '==================== k6 结果摘要 ====================',
    `  PROFILE          : ${PROFILE}`,
    `  TARGET           : ${TARGET}`,
    `  总请求数         : ${reqs}`,
    `  真错误率(4xx+5xx): ${realErr}%`,
    `  限流命中率(429)  : ${rateLimit}%`,
    `  静态页 P95       : ${staticP95 != null ? staticP95.toFixed(1) + 'ms' : 'n/a'}`,
    `  API P95          : ${apiP95 != null ? apiP95.toFixed(1) + 'ms' : 'n/a'}`,
    '',
    statusSummary(data),
    '',
    '====================================================',
    '',
  ];
  return lines.join('\n');
}
