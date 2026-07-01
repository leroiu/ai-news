# Error Log — AI Intelligence Platform

> 面试准备文档。整理项目中可能遇到的错误类型、原因、解决方式和后续规避建议。

---

## 一、错误类型总览

| 类别 | 数量 | 严重程度 |
|------|------|----------|
| API/网络错误 | 3 种 | 高 (中断流程) |
| 数据错误 | 4 种 | 中 (影响结果质量) |
| 配置错误 | 2 种 | 中 (启动失败) |
| 环境错误 | 2 种 | 高 (无法运行) |
| Pipeline 逻辑错误 | 2 种 | 中 (已修复) |
| 前端错误 | 1 种 | 低 (视觉问题) |
| 系统限制 | 2 种 | 低 (需知晓) |

---

## 二、API / 网络错误

### E1. API Key 未设置

**场景**: 运行 pipeline.py 时未设置 DEEPSEEK_API_KEY 或 MOONSHOT_API_KEY

**错误表现**:
```
[ERROR] 未设置 DEEPSEEK_API_KEY 环境变量
```

**原因**: ai_client.py 的 _call_openai_compatible() 函数检查 API Key。

**代码位置**: src/ai_client.py, line 108

```python
api_key = os.getenv(api_key_env)
if not api_key:
    log.error(f"未设置 {api_key_env} 环境变量")
    return None
```

**解决方式**: 创建 .env 文件或设置环境变量。

**后续规避**: pipeline.py 已在 entry point 预检 API Key（非 dry_run 模式下）。

---

### E2. API 调用超时 / 网络波动

**场景**: DeepSeek/Kimi API 请求超时或网络连接中断

**错误表现**: 日志中反复出现 "DeepSeek 调用失败 (尝试 n/3)"，最终 "DeepSeek 调用最终失败"

**原因**: 网络不稳定、API 服务端压力大或超时设置不合理。

**代码位置**: src/ai_client.py, _call_openai_compatible()

```python
RETRY_MAX = 3
RETRY_BASE_DELAY = 1.5  # 秒，指数退避: 1.5, 3, 6

for attempt in range(1, RETRY_MAX + 1):
    try:
        resp = client.chat.completions.create(...)
    except (APITimeoutError, APIConnectionError) as e:
        if _is_retryable(e) and attempt < RETRY_MAX:
            time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
            continue
```

**解决方式**: 重试机制自动处理。若持续失败，检查网络连接或切换到另一个后端 (AI_PROVIDER=kimi)。

**后续规避**:
- 双后端设计：DeepSeek 断服时切换到 Kimi
- 每篇文章独立处理，失败不影响同批次其他文章

---

### E3. AI 返回无法解析的 JSON

**场景**: API 调用成功但返回的内容不是有效 JSON

**错误表现**:
```
[WARNING] DeepSeek 返回无法解析 (尝试 1/3)
```

**原因**: LLM 模型偶尔输出格式异常（含 thinking block、解释文字等）。

**代码位置**: src/ai_client.py, _parse_json()

```python
def _parse_json(text):
    try:
        return json.loads(text)       # 直接解析
    except json.JSONDecodeError:
        pass
    match = re.search(r'''''(?:json)?s*([sS]*?)''''', text)
    if match:
        try:
            return json.loads(match.group(1))  # 提取 ```json 块
        except json.JSONDecodeError:
            pass
    return None  # 彻底失败
```

**解决方式**: `_parse_json()` 支持两种格式：
1. 纯 JSON 文本 (直接解析)
2. Markdown 包裹的 JSON 代码块 (正则提取)

**后续规避**: 重试机制会按指数退避重新发送请求。如果 3 次后仍失败，返回 None，由调用方做降级处理。

---

## 三、数据错误

### E4. INSERT OR IGNORE 导致数据无法覆写

**场景**: Pipeline 处理后 AI 数据无法覆盖裸数据

**原因** (已修复): 数据库写入策略最初使用 `INSERT OR IGNORE`，导致：
```
Pipeline 第一次写入: score=0 (裸数据)
Pipeline 第二次处理: 无法覆盖 -> score 永远为 0
```

**修复**: 改为 `INSERT OR REPLACE`。

**代码位置**: src/database.py insert_articles()

```python
conn.execute("""
    INSERT OR REPLACE INTO articles (...)
    VALUES (..., ?, ?, ...)
""")
```

**后续规避**: 已修复。HANDOVER.md 决策记录 ADR-008 记载此项。

---

### E5. Pipeline 只写文件不同步 DB

**场景**: 运行 Pipeline 后，生成的日报文件存在，但 Dashboard/API 查询不到

**原因** (已修复): Pipeline 早期版本只写入 Markdown 文件，未调用 `insert_report()` 同步到 SQLite。

**修复**: pipeline.py 在每个日报/周报/月报分支末尾增加数据库写入。

**代码位置**: pipeline.py 中 daily/weekly/monthly 各分支末尾：

```python
init_db()
insert_report(date=..., report_type=..., path=..., ...)
```

**后续规避**: 2026-06-29 已修复，当前版本全部正确同步。

---

### E6. 周报/月报未同步 DB

**场景**: 周报/月报生成后未被 API 和界面识别

**原因** (已修复): 周报/月报分支缺少 `insert_report()` 调用。

**代码位置**: pipeline.py 的 weekly/monthly 分支，早期版本:

```python
# 旧版本 (缺少):
# insert_report(date=report_date, report_type=period, path=str(report_path))

# 新版本 (已修复):
insert_report(date=report_date, report_type=period, path=str(report_path))
```

**后续规避**: 已修复。HANDOVER.md 中的"已修复 Bug"清单记载。

---

### E7. --limit 参数不生效

**场景**: 运行 `pipeline.py --limit 10` 发现依然处理了所有文章

**原因** (已修复): 早期参数解析只支持 `--limit=10` 格式，不支持 `--limit 10` 空格格式。

**修复**: 增加两种格式支持。

**代码位置**: pipeline.py 参数解析逻辑:

```python
# 同时支持 --limit=10 和 --limit 10
if arg.startswith("--limit="):
    try: limit = int(arg.split("=")[1])
elif arg == "--limit" and i + 1 < len(sys.argv):
    try: limit = int(sys.argv[i + 1])
```

**后续规避**: 当前版本两种格式均可使用。

---

## 四、配置错误

### E8. config.yaml 格式错误

**场景**: 修改 RSS 源或配置后 Pipeline 启动失败

**错误表现**:
```
yaml.YAMLError: mapping values are not allowed here
FileNotFoundError: 配置文件不存在: config.yaml
```

**代码位置**: src/utils.py, load_config()

```python
def load_config(path=None):
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

**解决方式**: 检查 YAML 缩进和格式，确保对齐一致 (YAML 对缩进敏感)。

**后续规避**: 修改 config.yaml 后用 `python -m yamllint config.yaml` 检查格式。

---

### E9. RSS 源配置不当导致抓取空

**场景**: 运行 Collector 后 inbox 一直为空

**常见原因**:
- RSS 源 URL 过期或不可用
- RSS 源实际返回了数据但解析失败
- max_age_hours 设置过小 (默认 72h)，周末无新内容

**代码位置**: src/fetcher.py

```python
# 每个源独立抓取，失败只跳过该源
for source in enabled_sources:
    try:
        response = await client.get(source.url, timeout=30)
        parsed = feedparser.parse(response.text)
    except Exception:
        log.warning(f"抓取失败: {source.name}")
        continue
```

**Config 示例**:
```yaml
sources:
  - name: "MIT Technology Review AI"
    url: "https://www.technologyreview.com/feed/"
    enabled: false  # 注意：可以禁用不可靠的源
```

**解决方式**:
- 在 `sources` 中标记 `enabled: false` 临时跳过不可用的源
- 检查 RSS URL 是否有效
- 工作日 vs 周末 RSS 更新频率不同 (如 ArXiv 工作日更新，周末无内容)

---

## 五、环境错误

### E10. 中文乱码

**场景**: AI 返回的中文内容在 Windows 终端上显示乱码

**错误表现**: Dashboard 页面或日报中出现 `` 方块字符或乱码

**原因**: Windows CMD/PowerShell 默认使用 GBK 编码，Python 输出了 UTF-8 编码的中文。

**代码位置**: 项目本身正确处理了 UTF-8 编码 (所有文件读写指定 encoding="utf-8")，问题在终端层面。

**潜在解决方案** (来自代码注释): 通过适当编码配置或卸载导致编码冲突的应用 (如 EleBank) 解决。

**后续规避**: 推荐使用 VS Code 终端或 Windows Terminal，避免 CMD 原生终端。

---

### E11. 依赖安装问题

**场景**: uv sync 或 pip install 失败

**原因**: uv.lock 版本锁定或网络问题。

**解决方式**:
```bash
uv sync              # 标准安装
uv sync --frozen     # 如果只想用锁定的版本
pip install -r requirements.txt  # 回退到 pip
```

---

## 六、系统限制

### E12. 文件大小限制

**场景**: 单文件超过 300 行被标记为"待拆分"

**当前超标文件**:
| 文件 | 行数 | 建议拆分方式 |
|------|------|-------------|
| src/knowledge_graph.py | 501 | kg_mermaid.py + kg_d3.py + kg_data.py |
| src/timeline.py | 351 | timeline_data.py + timeline_renderer.py |

**原因**: ENGINEERING_PRINCIPLES.md 规定单文件不超过 300 行。

**影响**: 大文件在 Claude Code/Codex 中单次读取会消耗较多上下文。

**当前状态**: 已发现但尚未拆分 (标注在 ROADMAP.md 和 HANDOVER.md 中)。

---

### E13. 缓存文件膨胀

**场景**: data/processed_cache.json 持续增长

**当前限制**: 上限 10000 条，超过时淘汰最旧的 50%。

**代码位置**: src/cache.py

```python
MAX_CACHE_SIZE = 10000

def _save(cache):
    if len(cache) > MAX_CACHE_SIZE:
        keys = sorted(cache.keys(), key=lambda k: cache[k].get("cached_at", ""))
        for k in keys[:len(keys)//2]:
            del cache[k]
```

**影响**: 大部分场景下缓存文件 2-5 MB，不影响运行。

---

### E14. Concept Miner 生成低质量草稿

**场景**: 自动概念挖掘生成了 33 张草稿卡片，质量参差不齐

**原因**: Concept Miner 的 AI 抽取逻辑可能存在误判，将一些非核心概念也纳入了候选。

**影响**: 需要定期人工审核 data/knowledge/methodology/ 目录下的草稿卡片。

**后续规避**: 已在 HANDOVER.md 中标注为待办事项，建议每次 Pipeline 运行后进行人工审核。

---

## 七、前端错误 (低风险)

### E15. HTML/JS 转义问题

**场景**: 实体详情页加载时出现 JavaScript 错误

**原因**: Python f-string 中 `'` 不转义，导致 JS 收到裸引号。

**修复方式** (已在 PROJECT_MEMORY.md 的 Known Pitfalls 中记录):
```python
# 问题: Python f-string 中 \' 不转义
html = f"<script>const name = '{entity_name}';</script>"
# 如果 entity_name 包含 ' , JS 会报 Unexpected identifier

# 解决: 用 \\' 在 Python 中产生 JS 的 \'
html = f"<script>const name = '{(entity_name).replace(chr(39), chr(92)+chr(39))}';</script>"
```

**后续规避**: 使用 json.dumps() 序列化再注入 HTML，避免手动拼接字符串。

---

## 八、错误处理架构总结

```
AI 调用
  |
  +-- call_ai()
  |     |-- API Key 缺失 -> None (调用方降级)
  |     |-- 网络超时 -> 指数退避重试 3 次 -> None
  |     |-- JSON 解析失败 -> 重试 -> None
  |     +-- 成功 -> [parsed JSON]
  |
  +-- 各模块 (classify/summarize/score/mine/tend)
        |-- call_ai() 返回 None -> 使用默认值
        |-- 部分文章失败 -> 跳过失败文章
        +-- 全部成功 -> 正常流程
```

Pipeline 整体容错设计:
- 每个阶段独立执行 (Stage 1-9)
- 缓存机制确保已处理文章不重复调用 API
- 单篇文章失败不影响同批次其他文章
- 整批失败后使用默认值，不中断 Pipeline
- 已在测试覆盖 (147 tests) 中验证错误路径

---

## 面试官可能追问的问题

1. **API 重试策略为什么用指数退避？** 避免 API 雪崩。服务端 429/5xx 时所有客户端同时重试只会加重负载。指数退避给服务端恢复时间。

2. **为什么 INSERT OR IGNORE 改为 REPLACE 是关键修复？** IGNORE 导致 AI 处理数据无法覆写裸数据 (score=0)，日报一直显示未处理文章。这是 Pipeline 中段最严重的逻辑 Bug。

3. **大文件拆分真的必要吗？** 对 Claude Code/Codex 等 AI 编码助手是必要的。>300 行的文件单次读取占用大量上下文，拆分为小型单职责文件后 AI 按需加载。当前知识图谱 (501行) 和 Timeline (351行) 已标记待拆分。

4. **如何验证一个 Bug 是否修复？** 当前 147 个测试覆盖了大部分模块的关键路径。测试不足的模块 (如 dashboard/entity_page 等 HTML 生成器) 通过手动检查生成结果验证。

5. **双后端容错在实际运行中有效吗？** 有效。DeepSeek 偶尔 5xx 时切换到 Kimi 可以绕过。两个后端都是 OpenAI 兼容协议，切换成本极低。但需要注意两个后端的模型能力和价格不同，摘要质量可能不一致。
