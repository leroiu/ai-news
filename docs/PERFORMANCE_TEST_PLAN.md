# AI 观察室 — 性能测试计划

> 版本: v1.0
> 负责人: performance_tester Agent
> 上次更新: 2026-07-09

---

## 1. 背景与目标

### 1.1 为什么需要性能测试体系？

现有的 `qa_smoke_test.sh` 只验证服务"活着"，不回答以下问题：

- 系统能承受多少并发用户？
- 高负载下 API 响应会退化到多久？
- Nginx 和 Python 后端哪里是瓶颈？
- 长期运行会有内存泄漏吗？
- 发布新功能后性能是否退化？

本计划系统回答这些问题。

### 1.2 测试目标

1. 建立 6 个性能测试等级，覆盖轻量验证到极限探索
2. 每次测试产出可量化的数据，与验收指标对比
3. 检测服务退化，在部署前提前发现性能回退
4. 提供瓶颈定位和优化建议

---

## 2. 架构概览

### 2.1 拓扑

```
用户 ←→ Nginx (:80) ←→ uvicorn (:8765) ←→ SQLite / 其他服务
         │
         └→ 静态 HTML（/ /reports /my /report/*）
```

- **Nginx**: 反向代理 + 静态文件服务
- **uvicorn**: Python ASGI 服务（FastAPI）
- **ai-news.service**: systemd 管理的 uvicorn 进程
- **端口**: `:8765`（对外不暴露，通过 Nginx 代理 /api/ 路径）
- **服务器**: `admin@121.43.80.221`
- **部署目录**: `/home/admin/app`

### 2.2 工具栈

| 工具 | 用途 | 安装方式 |
|------|------|----------|
| [k6](https://k6.io/) | 压力生成 + 指标采集 | `winget install k6` 或 [GitHub Releases](https://github.com/grafana/k6/releases) |
| bash + SSH | 服务器监控 + 编排 | 自带 |
| jq（可选） | JSON 解析（无 jq 时 fallback 到 grep） | `winget install jqlang.jq` |

### 2.3 文件体系

```
.agents/
  performance_tester.md     ← 本 Agent 的 SOP

scripts/
  load_test.sh              ← 编排器（确认门 + 前置检查 + 调用 k6 + 后处理）
  load_test_k6.js           ← k6 压测场景脚本
  monitor_server.sh          ← 服务器指标采集（5s 间隔）
  performance_report.sh      ← 报告生成器（解析 JSON + CSV → 固定格式）
  qa_smoke_test.sh           ← 冒烟测试（压测后复检，不变）

docs/
  PERFORMANCE_TEST_PLAN.md   ← 本文件，计划总纲

output/loadtest/
  k6_summary_<timestamp>.json    ← k6 全量结果
  monitor_<timestamp>.csv         ← 服务器采样数据
```

---

## 3. 测试类型与配置矩阵

### 3.1 六种测试类型

| 类型 | PROFILE | 并发模型 | 持续时间 | 确认等级 | 用途 |
|------|---------|----------|----------|:--------:|------|
| **A — Smoke** | `smoke-load` | 5 VUs 固定 | 30s | 无需确认 | 部署后快速验证性能基线 |
| **B — Normal** | `normal-load` | 20 VUs 固定 | 60s | 一次确认 | 日常负载验证 |
| **C — Peak** | `peak-load` | 50 VUs 固定 | 120s | 一次确认 | 高峰流量模拟 |
| **D — Spike** | `spike-test` | 5→80→5 突刺 | ~50s | 确认+高亮 | 突发流量承受能力 |
| **E — Soak** | `soak-test` | 15 VUs 固定 | 30min | 一次确认 | 长稳+内存泄漏检测 |
| **F — Limit** | `limit-test` | 20→200+ 阶梯 | 逐级递增 | 二次确认（默认禁止） | 寻找系统上限 |

### 3.2 各类型并发曲线

**A. Smoke Load (5 VUs)**
```
  5 ┤ ██████████████
  0 ┤─╯              ╰─
     5s    25s      30s
```

**B. Normal Load (20 VUs)**
```
 20 ┤   ████████████████
  0 ┤─╯                  ╰─
     10s      50s       60s
```

**C. Peak Load (50 VUs)**
```
 50 ┤      ████████████████
  0 ┤─╯                     ╰─
     20s          110s     120s
```

**D. Spike Test (5→80 VUs)**
```
 80 ┤          ████████████
  5 ┤ █████████               ██
  0 ┤─╯                       ╰─
     10s 15s          45s    50s
```

**E. Soak Test (15 VUs)**
```
 15 ┤   ██████████████████████████████████████
  0 ┤─╯                                         ╰─
     1m                    31m                 32m
```

**F. Limit Test（阶梯递增，每次 +20 VUs）**
```
200 ┤                                               ██
    ⋮
 60 ┤                           ██
 40 ┤                     ██
 20 ┤ ████████████████████
  0 ┤─╯                                         ╰─
     30s  60s  90s  ...                        N*30s
```
Limit test 不会预先指定最高并发，而是靠阈值熔断自动停止。

---

## 4. 测试对象

### 4.1 静态页面（走 Nginx + 反向代理）

| 路由 | 对应功能 | 备注 |
|------|----------|------|
| `/` | Dashboard 首页 | 含 ★5 模块，触发 `/api/articles` 异步请求 |
| `/reports` | 报告列表 | 较轻量 |
| `/my` | 我的页面 | 含收藏/已读/稍后列表 |
| `/report/<filename>` | 报告阅读器 | 仅在有日报时加入，取最新日报 |

### 4.2 API（走 Nginx → uvicorn）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查，极轻量 |
| `/api/reports?type=daily&limit=5` | GET | 报告列表，含数据库查询 |
| `/api/articles?limit=10&min_score=4` | GET | 文章列表，含数据库查询 + 评分过滤 |

### 4.3 明确不测试的端点（有副作用或会触发 LLM）

| 端点 | 原因 |
|------|------|
| `POST /api/pipeline/run` | 触发全量采集流水线，消耗 LLM token |
| `POST /api/research` | 触发 AI 研究，消耗 LLM token |
| `POST /api/favorites` | 写数据库 |
| `POST /api/reading-history` | 写数据库 |
| `POST /api/embeddings/rebuild` | 重建向量索引，耗资源 |
| `POST /api/migrations/run` | 改数据库结构 |
| 所有 `POST /api/entities` | 写数据库 |

---

## 5. 验收指标

### 5.1 硬性阈值（破线 = FAIL）

| 指标 | 阈值 | 测量方式 |
|------|------|----------|
| 静态页面 p95 响应时间 | `< 500ms` | k6 `static_page_duration` |
| API p95 响应时间 | `< 1500ms` | k6 `api_duration` |
| HTTP 请求失败率 | `< 1%` | k6 `http_req_failed` |
| 502/504 响应 | 不允许任何大量出现 | k6 check + nginx 日志 |
| ai-news.service 崩溃 | 不允许 | monitor_server.sh 实时检测 |
| 压测后冒烟测试 | 全部 PASS | `qa_smoke_test.sh` |

### 5.2 警示阈值（触发则备注到报告，但不判 FAIL）

| 指标 | 阈值 | 意义 |
|------|------|------|
| CPU 使用率 | 不长期 > 90% | 可能资源不足 |
| 内存使用率 | 不持续上涨 | 排查内存泄漏 |
| 系统 Load | < CPU 核心数 × 2 | 负载合理范围 |

### 5.3 熔断阈值（保护线上服务）

| 条件 | 行为 |
|------|------|
| 失败率 > 15% 持续 20s | k6 自动 abort，立即停止压测 |
| ai-news.service 变为 inactive | monitor_server.sh 发出告警，load_test 自动终止 |
| 出现批量 5xx | 监控实时预警，报告重点标记 |

---

## 6. 执行流程（SOP）

### 6.1 完整流程

```
STEP 1: 确认门
  ├── smoke-load → 默认允许
  ├── normal-load → 确认一次
  ├── peak-load → 确认一次
  ├── spike-test → 确认一次 + 高亮风险提醒
  ├── soak-test → 确认一次（耗时较长）
  └── limit-test → 二次确认（文字确认 + URL 确认）

STEP 2: 前置检查（preflight.sh 的子集）
  ├── k6 是否安装
  ├── SSH admin@121.43.80.221 可达
  ├── curl http://121.43.80.221 → 200
  └── systemctl is-active ai-news → active

STEP 3: 启动服务器监控
  └── monitor_server.sh（5s 间隔，产出 CSV）

STEP 4: 执行 k6 压测
  ├── load_test_k6.js（通过 load_test.sh 调用）
  └── 阈值破线 → 退出码 99（但不 abort，除熔断外）

STEP 5: 停止监控
  └── kill monitor 进程

STEP 6: 压测后冒烟测试
  └── qa_smoke_test.sh
      ├── PASS → OK
      └── FAIL → 标记到报告

STEP 7: 生成报告
  └── performance_report.sh
      ├── 解析 k6 JSON
      ├── 解析 monitor CSV
      ├── 输出固定格式报告
      └── 瓶颈判断 + 下一步建议
```

### 6.2 触发词索引

| 你说 | 执行行为 | 最短安全间隔 |
|------|----------|:----------:|
| "轻压测" | smoke-load | 任意 |
| "标准压测" | normal-load | smoke-load 通过后 |
| "高峰压测" | peak-load | normal-load 通过后 |
| "突刺测试" | spike-test | 当前负载无异常 |
| "长稳测试" | soak-test | 建议夜间/低峰期 |
| "极限测试" | limit-test | 所有以上通过 + 书面确认 |

### 6.3 使用示例

```bash
# 交互式（load_test.sh 接管确认）
bash scripts/load_test.sh 轻压测

# 带一次确认的
bash scripts/load_test.sh 标准压测

# 跳过确认（仅用于自动化脚本）
bash scripts/load_test.sh 轻压测 --yes
```

---

## 7. 安全与风险控制

### 7.1 执行前的安全检查

每次压测前自动运行：
1. **k6 不可用** → 拒绝执行
2. **SSH 不可达** → 拒绝执行
3. **目标服务不可达** → 拒绝执行
4. **ai-news.service 不在运行** → 拒绝执行
5. **目标 URL 与配置不匹配** → 拒绝执行（limit-test 额外确认环节）

### 7.2 压测中的熔断

- 失败率 > 15% 持续 20s → k6 内置 `abortOnFail` 触发，所有活跃请求停止
- monitor 检测到服务变为 inactive → 实时输出 ⚠⚠⚠ 告警
- 出现批量 5xx → 每个采样周期标记 +output

### 7.3 压测后的恢复验证

- 每个压测后自动跑完整冒烟测试
- 即使压测因错误终止，也先生成可用报告
- 各脚本均使用 `set -euo pipefail`，任何意外失败立即中止

### 7.4 不可能出现的操作

- load_test_k6.js 硬编码只读 GET 白名单，拒绝任何 `/api/pipeline`、`/api/research`、POST 类端点
- load_test.sh 不调用任何 deploy 脚本
- performance_tester Agent 的规则文档明确禁止修改业务代码

---

## 8. 报告解读指南

### 8.1 报告格式示例

```
状态：FAIL
测试类型：peak-load
总请求数：1234
失败率：0.35%
静态页面 P95：423ms
API P95：1842ms           ← ❌ 越线
HTTP P99：2100ms

服务器状态：
  CPU 平均：65.2%
  CPU 峰值：91.1%         ← ⚠ 峰值高
  内存峰值：72.4%
  Load 峰值：8.2
  峰值连接数：156
  Total 5xx：3
  服务中断次数：0

瓶颈判断：
  1. API P95 1842ms 超限 (>1500ms) — Python 后端处理慢，检查数据库查询
  2. CPU 峰值 91.1% > 90% — 考虑扩充计算资源

下一步：
  1. 检查数据库查询索引（/api/reports 和 /api/articles 的慢查询）
  2. 考虑增加 uvicorn --workers 数量
  3. 对 /api/health 之外的 API 端点添加 Redis 缓存
```

### 8.2 结果解读逻辑

1. **状态** 是唯一的第一眼信号：PASS 表示所有硬性阈值通过，FAIL 表示至少一项越线
2. **静态 vs API** 分开判断：
   - 静态慢 → Nginx 配置 / 磁盘 I/O / 反向代理延迟
   - API 慢 → Python 应用 / 数据库查询 / 外部服务调用
3. **服务器状态** 交叉验证：
   - CPU 高 + API 慢 → 后端计算瓶颈
   - CPU 不高但 API 慢 → 数据库 / 网络 I/O 瓶颈
   - 内存持续上涨 → 疑似内存泄漏

---

## 9. 基线管理

### 9.1 首次基线

第一轮 smoke-load 通过后的结果作为**性能基线 v1**，记录在 `output/loadtest/baseline.json`。

### 9.2 定期回归

- 每次部署新功能后跑 smoke-load，与基线比较
- 每周建议跑一次 full suite（smoke + normal），建立长期趋势
- 每月审查 soak-test 结果，排查渐进式退化

### 9.3 退化判定

| 比较项 | 退化判定 |
|--------|----------|
| 同 profile 的 P95 涨幅 > 20% | 🟡 关注 |
| 同 profile 的 P95 涨幅 > 50% | 🔴 需优化后再发布 |
| 首次出现 502/504 | 🔴 关键回归，立即排查 |
| 失败率从 <0.1% 升至 >1% | 🔴 服务稳定性退化 |

### 9.4 基线文件格式

`output/loadtest/baseline.json` 存储最近一次 PASS 的 **smoke-load** 结果摘要：

```json
{
  "profile": "smoke-load",
  "date": "2026-07-09",
  "static_p95_ms": 120,
  "api_p95_ms": 340,
  "fail_rate_pct": 0.01,
  "req_p99_ms": 510,
  "cpu_avg": 12.3,
  "mem_peak": 45.0
}
```

---

## 10. 已知限制

1. **SQLite 并发限制** — 当前后端使用 SQLite，写入会锁表。高并发下 API 读性能可能受影响。若后续切换 PostgreSQL 需要重新建立基线。
2. **单机部署** — 所有服务在同一台服务器，无法区分 Nginx vs Python 延迟。
3. **本地机器做压测** — 网络距离会引入额外延迟（服务器杭州，压测端视执行位置而定）。建议后续在阿里云同区域建跳板机执行压测。
4. **k6 不驱动 JS** — k6 不执行浏览器中的 JavaScript，对 Dashboard 的 ★5 模块等客户端异步加载部分，只能测到静态 HTML 响应，无法测量用户感知的完整加载时间。如需完整前端性能数据，建议后续增加 Lighthouse / Playwright 性能测试。
5. **monitor 采样间隔 5s** — 无法捕捉 1s 内的瞬时毛刺。如需更细粒度，可改为 1s，但会增大 SSH 开销。
6. **测试数据量** — 当前数据库规模较小（~几百条文章），真实场景下数据量增长后查询响应时间会增加。

---

## 11. FAQ

### Q: 性能测试和冒烟测试什么关系？

冒烟测试（`qa_smoke_test.sh`）是做"活着"验证：页面 200、API 返回正确、JS 函数存在。
性能测试是做"快不快、稳不稳"验证：并发下的响应时间、失败率、资源消耗。
两者互补，冒烟测试在压测前后各跑一次。

### Q: 压测会不会影响线上用户？

正常运行时不会对线上一台 5 并发的轻压测基本无感。peak-load 及以上等级建议在低峰期执行。所有测试都有熔断保护。

### Q: limit-test 到底会压到什么程度？

阶梯从 20 VUs 开始，每 30 秒增加 20 VUs，直到触及任一硬性阈值（失败率 > 15%）自动熔断停止。不会无限加压。默认上限 200 VUs，可通过环境变量 `LIMIT_MAX_VUS` 调整。

### Q: 没有 jq 能跑吗？

可以。`performance_report.sh` 做了 fallback：有 jq 优先用 jq，没有则用 grep 提取关键字段。但建议安装 jq 以获得更准确的 JSON 解析。

### Q: 测试结果需要保存多久？

建议至少保留最近 30 天的结果用于趋势分析。旧的 `output/loadtest/` 文件可手动清理（保留 baseline.json）。
