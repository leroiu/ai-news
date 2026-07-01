# AI News — 商业化架构设计

> **状态**: 架构决策已完成，等待项目有用户和社区后执行。
> **当前阶段**: 只开发开源核心，不实现任何商业化功能。
> **关联 ADR**: ADR-012 (Plugin Architecture), ADR-013 (Open Core / Closed Cloud)

---

## 1. 商业化策略

### 核心原则

**开源的是引擎，卖的是服务。** 任何人在自己电脑上能跑全部功能，但多租户、调度、计费、高可用是云端的价值。

### 为什么别人会付费？

| 自己部署 | 付费云服务 |
|---------|-----------|
| 需要自己的 DeepSeek/OpenAI API Key | 平台提供 API Key，开箱即用 |
| 需要自己部署服务器和定时任务 | 浏览器打开即用，平台自动更新 |
| 只有本地数据 | 云端历史数据积累 + 多设备同步 |
| 没有 Research Assistant | 积分解锁 AI 深度研究 |
| 只支持 DeepSeek | 可选 Claude/GPT 等高级模型 |

### 三层收费模型

```
免费层 → 新闻浏览、知识库、时间线、日报（零边际成本）
会员层 → 更高频更新、更长上下文、更好的模型
Research → 用户绑定自己的 API Key，或按次/积分收费
```

---

## 2. 架构总览

```
┌──────────────────────────────────────────────┐
│  Layer 3: Cloud Platform (私有仓库，不公开)    │
│  多租户 · 计费 · 调度 · Research SaaS · 管理   │
├──────────────────────────────────────────────┤
│  Layer 2: Plugin Interfaces (公开，MIT)       │
│  认证接口 · 计费接口 · 调度接口 · 存储接口       │
├──────────────────────────────────────────────┤
│  Layer 1: Core Engine (公开 GitHub，MIT)      │
│  抓取 · Pipeline · 卡片 · 日报 · 知识图谱 · API │
└──────────────────────────────────────────────┘
```

- **Layer 1** (开源): 单机完整可用，`pip install` 即跑
- **Layer 2** (开源): 抽象接口 + 本地实现（单用户、文件存储、CLI 调度）
- **Layer 3** (闭源): 云实现（多租户、S3、Cron、计费），只部署不公开

---

## 3. 代码仓库划分

### Repo 1: `ai-news` (GitHub 公开，MIT)

```
ai-news/
├── engine/                  # 核心引擎 — 与任何服务无关
│   ├── fetcher.py           # RSS/HTML 抓取
│   ├── dedup.py             # 去重
│   ├── classifier.py        # AI 分类
│   ├── summarizer.py        # AI 摘要
│   ├── scorer.py            # AI 评分
│   ├── concept_miner.py     # 概念挖掘
│   ├── knowledge.py         # 知识卡片匹配
│   ├── reporter.py          # Markdown 日报生成
│   ├── trend_reporter.py    # 周报/月报
│   ├── research_engine.py   # 研究引擎（核心逻辑，不含计费）
│   ├── database.py          # SQLite 数据层
│   ├── ai_client.py         # AI 后端抽象
│   ├── embeddings.py        # 嵌入向量
│   ├── cache.py             # 处理缓存
│   └── utils.py             # 配置、日志、工具
│
├── interfaces/              # 插件接口（ABC 抽象类）
│   ├── auth.py              # AuthProvider 接口
│   ├── billing.py           # BillingProvider 接口
│   ├── scheduler.py         # SchedulerProvider 接口
│   ├── storage.py           # StorageProvider 接口
│   └── research.py          # ResearchProvider 接口
│
├── plugins/                 # 默认本地实现（开源）
│   ├── auth_local.py        # 单用户（免登录，本地即是 Premium）
│   ├── billing_local.py     # 免计费（所有功能可用）
│   ├── scheduler_local.py   # CLI 触发（collector.py / pipeline.py）
│   └── storage_local.py     # 本地文件系统
│
├── frontend/                # 开源前端页面
│   ├── styles.py            # 设计系统 + 共享 CSS/JS
│   ├── i18n.py              # 国际化
│   ├── shell.py             # 页面壳（nav + html + 通用 JS）
│   ├── components.py        # UI 组件库
│   ├── dashboard.py
│   ├── library.py
│   ├── graph_2d.py
│   ├── graph_3d.py
│   ├── timeline.py
│   ├── entity.py
│   ├── events.py
│   ├── reports.py
│   └── research.py
│
├── api/                     # 开源 API
│   ├── app.py               # create_app() 工厂函数
│   ├── routes_public.py     # 公开只读端点
│   ├── routes_research.py   # Research 端点（通过接口调用）
│   └── deps.py              # FastAPI 依赖注入
│
├── cli/                     # 命令行入口
│   ├── collector.py
│   ├── pipeline.py
│   └── manage.py
│
├── prompts/                 # 提示词模板
├── data/knowledge/          # 知识卡片（YAML）
├── tests/
├── config.yaml
├── pyproject.toml
├── LICENSE                  # MIT
└── README.md
```

### Repo 2: `ai-news-cloud` (私有仓库，未来创建)

```
ai-news-cloud/
├── services/                # 云服务实现
│   ├── auth_cloud.py        # JWT + DB 多租户
│   ├── billing_cloud.py     # Lemon Squeezy 集成
│   ├── scheduler_cloud.py   # APScheduler / Celery
│   ├── storage_cloud.py     # S3 / R2
│   └── research_cloud.py    # 带计费的 Research
│
├── frontend/                # 商业版专属页面
│   ├── login.py
│   ├── settings.py
│   ├── billing.py
│   └── admin.py
│
├── api/                     # 商业版 API
│   ├── routes_auth.py
│   ├── routes_billing.py
│   └── routes_admin.py
│
├── docker/
├── deploy/
├── migrations/
└── pyproject.toml           # depends on ai-news (core)
```

---

## 4. 插件接口设计

### 五个核心接口

```python
# interfaces/auth.py
class AuthProvider(ABC):
    async def get_user(self, request) -> Optional[User]: ...
    async def register(self, email, username, password) -> User: ...
    async def login(self, email, password) -> Optional[tuple[User, str]]: ...
    async def save_api_key(self, user, provider, label, key) -> None: ...
    async def list_api_keys(self, user) -> list[ApiKeyInfo]: ...
    async def delete_api_key(self, user, key_id) -> None: ...

# interfaces/billing.py
class BillingProvider(ABC):
    async def check_feature(self, user, feature, **kwargs) -> bool: ...
    async def consume_credit(self, user, amount=1, feature="research") -> int: ...
    async def get_credits(self, user) -> int: ...
    async def get_tier(self, user) -> str: ...

# interfaces/scheduler.py
class SchedulerProvider(ABC):
    async def run_collector(self) -> str: ...
    async def run_pipeline(self, mode="daily", **kwargs) -> str: ...
    async def get_run_status(self, run_id) -> PipelineRunStatus: ...

# interfaces/storage.py
class StorageProvider(ABC):
    async def save_report(self, date, content) -> str: ...
    async def read_report(self, date) -> Optional[str]: ...
    async def list_reports(self, report_type) -> list[ReportInfo]: ...

# interfaces/research.py
class ResearchProvider(ABC):
    async def execute(self, topic, depth, lang, user, api_key=None) -> ResearchReport: ...
```

### 本地实现（默认）

```python
# plugins/auth_local.py
class LocalAuthProvider(AuthProvider):
    """单用户模式：免登录，始终返回 local-user (tier=premium)"""

# plugins/billing_local.py
class LocalBillingProvider(BillingProvider):
    """免计费：check_feature() 永远返回 True, consume_credit() 是空操作"""

# plugins/scheduler_local.py
class LocalSchedulerProvider(SchedulerProvider):
    """CLI 模式：run_collector() 直接调用 engine 函数"""

# plugins/storage_local.py
class LocalStorageProvider(StorageProvider):
    """本地模式：文件系统读写 reports/ 目录"""
```

---

## 5. FastAPI 工厂模式

```python
# api/app.py
def create_app(
    auth: AuthProvider = None,
    billing: BillingProvider = None,
    scheduler: SchedulerProvider = None,
    storage: StorageProvider = None,
    research: ResearchProvider = None,
) -> FastAPI:
    """工厂函数。不传参数 = 本地单用户模式。"""
    auth = auth or LocalAuthProvider()
    billing = billing or LocalBillingProvider()
    # ... 注入到 app.state
    return app

# 本地启动
# uv run uvicorn api.app:create_app --factory --port 8765

# 云端启动（未来）
# app = create_app(
#     auth=CloudAuthProvider(db),
#     billing=CloudBillingProvider(ls_client),
#     ...
# )
```

---

## 6. 数据边界

| 表 | 归属 | 定义位置 |
|----|------|---------|
| entities, articles, reports | 开源 | `engine/database.py` |
| relationships, embeddings | 开源 | `engine/database.py` |
| pipeline_runs, collector_runs | 开源 | `engine/database.py` |
| users, user_api_keys | 闭源 | `services/auth_cloud.py` (未来) |
| payments, subscriptions | 闭源 | `services/billing_cloud.py` (未来) |

**关键**: 开源版 `database.py` 不包含任何用户相关表定义。

---

## 7. Research Assistant 可插拔设计

```
frontend/research.py (开源)   ← 表单 + 报告渲染 UI
api/routes_research.py (开源)  ← POST /api/research，调 ResearchProvider
interfaces/research.py (开源)  ← ResearchProvider ABC
engine/research_engine.py (开源) ← 核心：搜索→组装上下文→调 AI（纯函数）
services/research_cloud.py(未来) ← 包装：计费检查→扣积分→调核心→记录
```

核心逻辑 `research_engine.py` 不涉及认证、计费、用户系统。云版通过 `ResearchProvider` 包装一层计费逻辑。

---

## 8. 前端插件注入

开源版 `frontend/shell.py` 提供钩子，云版通过注册插件注入 login/settings/billing 页面和导航链接：

```python
# frontend/shell.py
FRONTEND_PLUGINS: list = []

def register_frontend_plugin(plugin):
    """云版在 create_app() 之前调用，注册商业版页面"""
    FRONTEND_PLUGINS.append(plugin)

# 云版入口:
# from frontend.shell import register_frontend_plugin
# register_frontend_plugin(CloudAuthPlugin())
```

---

## 9. 实施阶段

### 当前阶段（现在）: 开源核心完善
- [ ] Step 0: 重构项目结构 `src/` → `engine/` + `frontend/` + `api/` + `cli/` + `interfaces/` + `plugins/`
- [ ] Step 1: GitHub 开源准备（LICENSE, README, .gitignore, git init）
- [ ] 完善 Research Engine 核心逻辑
- [ ] 完善 Knowledge Graph
- [ ] Pipeline 稳定性
- [ ] 前端体验（Codex 负责）

### 未来阶段（有用户和社区后）: 商业化
- [ ] 创建私有仓库 `ai-news-cloud`
- [ ] 实现 CloudAuth, CloudBilling, CloudScheduler, CloudStorage, CloudResearch
- [ ] 实现 Login/Settings/Billing/Admin 页面
- [ ] Lemon Squeezy 集成
- [ ] Railway 部署上线

---

> **最后更新**: 2026-07-01
> **关联文档**: DECISIONS_架构决策记录.md (ADR-012, ADR-013)
