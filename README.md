# AI Intelligence Platform

> Automated AI news aggregation, analysis & knowledge management. RSS → AI Pipeline → Daily Digest → Web Dashboard.

📖 **Product Guide (Chinese)**: [PRODUCT_GUIDE.md](./PRODUCT_GUIDE.md)

---

## Overview

| Dimension | Detail |
|-----------|--------|
| **Positioning** | AI Intelligence Platform — News / Knowledge / Graph / Research |
| **Pipeline** | RSS → Classify → Summarize → Score → Daily Report + Web UI |
| **SSOT** | Knowledge Card (YAML) — all modules read from cards |
| **Web** | FastAPI on `:8765`, 8 pages, API-driven UI |
| **Database** | SQLite (WAL mode), 4 tables: entities / relationships / articles / reports |
| **Entities** | 92 knowledge cards, 8 types (model, company, tech, concept, product, person, methodology, event) |
| **Relations** | 592 edges in the knowledge graph |
| **RSS Sources** | 16 sources (14 active), RSS + HTML parsing |
| **Tests** | 249 passed, 0 failures |

---

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure API keys
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY=sk-xxx (DeepSeek is the default AI provider)

# 3. Start the web server
uv run uvicorn src.api.api:app --reload --port 8765

# 4. Run a one-off daily pipeline
uv run python pipeline.py --fetch-direct

# 5. Run tests
uv run pytest tests/ -q        # 249 passed
```

Open http://127.0.0.1:8765 for the Dashboard.

---

## Architecture

```
ai-news/
├── pipeline.py                    # CLI entry point — 9-stage pipeline
├── collector.py                   # RSS collector — runs hourly
├── config.yaml                    # RSS sources, categories, pipeline config
├── prompts/                       # AI prompt templates
├── templates/                     # Report templates (daily/weekly/monthly)
├── data/
│   ├── ai_news.db                 # SQLite database
│   ├── inbox.jsonl                # Raw fetched articles
│   └── knowledge/                 # Knowledge cards (YAML), organized by type
├── src/
│   ├── interfaces/                # Shared layer — i18n
│   ├── engine/                    # AI engine + data processing (18 modules)
│   │   ├── ai_client.py           # Multi-provider AI (DeepSeek/Kimi) + Embedding registry
│   │   ├── database.py            # SQLite CRUD + search + stats
│   │   ├── fetcher.py             # RSS + HTML fetching (16 sources)
│   │   ├── classifier.py          # AI article classification
│   │   ├── summarizer.py          # AI summarization with context
│   │   ├── scorer.py              # AI 1-5★ scoring
│   │   ├── reporter.py            # Markdown daily report generation
│   │   ├── knowledge.py           # Card loading / Jaccard + semantic matching
│   │   ├── embeddings.py          # Semantic embeddings (SiliconFlow BGE, 1024d)
│   │   ├── concept_miner.py       # Automated concept discovery
│   │   ├── trend_reporter.py      # Weekly/monthly trend analysis
│   │   ├── research_engine.py     # Deep research engine
│   │   └── ...
│   ├── frontend/                  # HTML page generators (14 modules)
│   │   ├── dashboard.py           # Dashboard — stats + top stories
│   │   ├── library.py             # Knowledge library with category navigation
│   │   ├── entity_page.py         # Entity detail view
│   │   ├── kg_d3.py               # D3.js interactive knowledge graph
│   │   ├── kg_3d.py               # Three.js 3D knowledge graph
│   │   ├── timeline_renderer.py   # AI history timeline
│   │   ├── research_page.py       # Research workbench
│   │   └── ...
│   └── api/                       # FastAPI application
│       └── api.py                 # 15+ REST endpoints + static file serving
└── tests/                         # 249 tests across 14 test modules
```

## Pipeline Flow

```
inbox.jsonl
  → Classify (AI categorization)
  → Concept Miner (discover new entities)
  → Knowledge Match (card matching, semantic + Jaccard)
  → Summarize (AI summary with historical context)
  → Score (AI 1-5★ rating)
  → Report (Markdown daily digest)
  → DB Sync (SQLite)
  → Dashboard + Library + Graph + Timeline refresh
```

## Web Routes

| Route | Content |
|-------|---------|
| `/` | Dashboard — stats, top stories, health |
| `/library` | Knowledge library — 92 cards, 8 types, semantic search |
| `/graph` | D3.js interactive knowledge graph (2D) |
| `/graph3d` | Three.js 3D knowledge graph |
| `/timeline` | AI industry timeline |
| `/events` | Milestone events timeline |
| `/reports` | Report browser (daily/weekly/monthly) |
| `/research` | Deep research assistant |
| `/entity/{id}` | Entity detail page |
| `/api/entities` | Entity list with type filter |
| `/api/articles` | Article list with score filter |
| `/api/search?q=&semantic=true` | Full-text + semantic hybrid search |
| `/api/stats` | Database statistics |
| `/api/health` | System health check |
| `/api/research` | POST — AI-powered deep research |
| `/api/embeddings/status` | Embedding readiness status |
| `/api/embeddings/rebuild` | POST — rebuild all embeddings |

## Scheduled Tasks

| Task | Frequency | Time |
|------|-----------|------|
| Collector | Hourly | from 8:00 |
| Daily Pipeline | Daily | 9:00 |
| Weekly Report | Sunday | 10:00 |
| Monthly Report | 1st of month | 10:00 |

Windows Task Scheduler `.bat` / `.vbs` files included.

## Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.13 | |
| AI Engine | DeepSeek + Kimi | OpenAI-compatible dual backends |
| Embeddings | SiliconFlow BGE (1024d) | Pluggable: openai/kimi/local |
| Web | FastAPI + Uvicorn | API-driven HTML shells |
| Database | SQLite (WAL mode) | Zero-config, foreign keys |
| Frontend | Vanilla JS + fetch API | No framework dependency |
| Package | uv | Fast Python package manager |
| Scheduling | Windows Task Scheduler | |

## Design Principles

- **SSOT**: Knowledge Cards (YAML) are the single source of truth
- **API-driven UI**: HTML shells + vanilla JS `fetch()` — no SSR, no React/Vue
- **File-driven**: No ORM — direct SQLite + YAML + JSONL
- **Context budget**: Files <300 lines, one feature per conversation
- **importance ≠ score**: Manual curation vs. AI real-time scoring
- **i18n**: Full Chinese/English toggle, 100+ translation keys

## Documentation

| Document | Audience |
|----------|----------|
| `PRODUCT_GUIDE.md` | Non-technical users (Chinese) |
| `README.md` | Developers, interviewers |
| `ARCHITECTURE_系统架构.md` | System architecture deep-dive |
| `ROADMAP_项目路线图.md` | Development roadmap |
| `DECISIONS_架构决策记录.md` | Architecture Decision Records (ADR) |
| `KNOWLEDGE-CARD-SCHEMA_知识卡片结构.md` | Knowledge card format spec |
| `CODEX_HANDOFF_Codex协作说明.md` | AI-to-AI handoff protocol |

## License

MIT — see [LICENSE](./LICENSE)
