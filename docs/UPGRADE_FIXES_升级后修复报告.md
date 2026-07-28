# 升级后修复报告

> 本文档记录工具链升级落地后,对两个既存测试失败的根因分析、修复与验证结果。
>
> 日期: 2026-07-26
> 关联: [docs/TOOLCHAIN.md](./TOOLCHAIN.md) · [docs/BUG_LOG.md](./BUG_LOG.md)

## 概述

工具链升级主体已落地(Python 3.13.14 / uv 0.11.32 / FastAPI 0.139.2 / PyJWT 2.13.0 / npm 11.16.0 等,详见 `docs/TOOLCHAIN.md`),完整 checkpoint 结果为 **513 passed / 2 failed / 1 skipped**。

经核实,两个失败**均与工具链升级逻辑无关**,是升级前已存在的既存问题:

| 失败 | 测试 | 性质 | 状态 |
|------|------|------|------|
| 1 | `test_claude_longrun_config.py::test_shared_rules_block_external_and_self_modifying_actions` | 配置缺项 | ✅ 已修复并提交 |
| 2 | `test_inbox_dedup.py::test_rss_deduplicate_across_runs` | 真实代码 bug | ✅ 已修复并提交 |

---

## 失败 1: `.claude/settings.json` deny 列表缺 2 项

### 现象

```
AssertionError: assert {'Bash(git pu...push *)', ...} <= {'Bash(aliyun...lean *)', ...}
Extra items in the left set:
  'Edit(AGENTS.md)'
  'Read(.private/**)'
```

测试 `test_shared_rules_block_external_and_self_modifying_actions` 要求 `.claude/settings.json` 的 `permissions.deny` 包含 9 条规则,实际缺失 2 条:

- `Read(.private/**)`
- `Edit(AGENTS.md)`

其余 7 条(`Read(.env)`、`Edit(.claude/**)`、`Bash(git push *)`、`Bash(ssh *)`、`PowerShell(git push *)` 等)均已存在。

### 根因

`.claude/settings.json` 当前只 deny 了 `Read(.private/**/.env)`(仅 `.private/` 下的 `.env`),而测试与 AGENTS.md 硬边界("Never read or edit `.env`, `.private/`, SSH keys")要求更宽的 `Read(.private/**)`(整个 `.private/` 目录)。`Edit(AGENTS.md)` 同理未列入 deny。

与工具链升级无关 —— 这是 `.claude/` 配置与测试契约的既存不一致。

### 修复(已应用)

> `.claude/settings.json` 受 `Edit(.claude/**)` deny 规则保护,Edit 工具无法直接修改。经用户明确授权后,通过 Python 脚本以 JSON 程序化方式安全写入(仅新增 2 个数组元素,保留全部既有内容)。

在 `.claude/settings.json` 的 `permissions.deny` 数组中新增 2 行:

```diff
     "deny": [
       "Read(.env)",
+      "Read(.private/**)",
       "Read(.private/**/.env)",
       "Read(//**/.ssh/**)",
       "Edit(.env)",
       "Edit(.private/**/.env)",
       "Edit(data/**)",
       "Edit(reports/**)",
       "Edit(cache/**)",
       "Edit(logs/**)",
       "Edit(.claude/**)",
       "Edit(CLAUDE.md)",
+      "Edit(AGENTS.md)",
       "Edit(docs/LONG_RUNNING_AGENT_MODE.md)",
       ...
     ]
```

此改动**加强**权限(增加 deny 项),方向上符合 AGENTS.md "Never weaken `.claude/` permissions" 的约束。应用后该测试即可通过。

---

## 失败 2: inbox 标题去重对短标题误判(已修复)

### 现象

```
FAILED tests/test_inbox_dedup.py::test_rss_deduplicate_across_runs - assert 2 == 3
```

`test_rss_deduplicate_across_runs` 模拟两次 Action 运行:run1 写入 RSS Item 1、2;run2 写入 RSS Item 1、2、3。期望 inbox 最终有 3 条(1、2 去重,3 新增),实际只剩 2 条 —— RSS Item 3 被错误丢弃。

### 根因

`src/engine/utils.py` 的 `append_inbox` 在 `4dc1f3a`(已提交)引入了标题相似度去重,阈值 0.85:

```python
if SequenceMatcher(None, cmp_title, et).ratio() >= 0.85:
    is_title_dup = True
```

短标题公共前缀占比高,SequenceMatcher 比率虚高。实测:

- `"rss item 3"` vs `"rss item 1"` → ratio = **0.90 ≥ 0.85** → 误判为重复
- `"rss item 3"` vs `"rss item 2"` → ratio = **0.90 ≥ 0.85** → 误判为重复

因此 run2 的 RSS Item 3 被当作标题重复跳过。这是 `4dc1f3a` 引入的**真实代码 bug**,非测试问题,也与工具链升级无关(`src/engine/utils.py` 的未提交改动仅为 `TYPE_CHECKING` 导入重构,未触碰去重逻辑)。

### 修复(已应用)

采用**短标题保护**:仅对长度 ≥ 15 的标题做模糊匹配,短标题只走 ID 精确去重。长标题(真实文章标题通常 30+ 字符)的相似度去重不受影响。

`src/engine/utils.py` — `append_inbox`:

```diff
     # ── 过滤：ID 去重 + 标题相似度去重 ──
     new_articles = []
     skipped_id = 0
     skipped_title = 0
+    # 短标题公共前缀占比高，SequenceMatcher 比率易虚高
+    # （如 "rss item 1" vs "rss item 3" = 0.90 ≥ 0.85 会误杀），
+    # 仅对长度 >= 15 的标题做模糊匹配，短标题只走 ID 精确去重。
+    MIN_TITLE_LEN_FOR_FUZZY = 15
     for a in articles:
         # 1. URL/ID 精确匹配
         if a.id in existing_ids:
             skipped_id += 1
             continue
         # 2. 标题相似度检测 (阈值 0.85，仅与最近 500 篇比较以保性能)
         is_title_dup = False
         cmp_title = a.title.lower().strip()
-        for et in existing_titles[-500:]:
-            if SequenceMatcher(None, cmp_title, et).ratio() >= 0.85:
-                skipped_title += 1
-                is_title_dup = True
-                break
+        if len(cmp_title) >= MIN_TITLE_LEN_FOR_FUZZY:
+            for et in existing_titles[-500:]:
+                if SequenceMatcher(None, cmp_title, et).ratio() >= 0.85:
+                    skipped_title += 1
+                    is_title_dup = True
+                    break
         if is_title_dup:
             continue
         new_articles.append(a)
```

**为何选短标题保护而非提高阈值**:`test_dedup.py::test_removes_title_duplicate` 依赖 0.85 阈值识别 "AI Breakthrough Today"(20 字符)与 "AI Breakthrough Today!" 这类真实近似标题去重;提高阈值到 0.95 会削弱长标题去重能力。短标题保护是根因修复 —— 问题本质是短标题信息量不足导致比率失真,而非阈值本身不合理。

---

## 验证结果

> uv 已从 0.11.24 升级至 0.11.32(杀死占用 `uvx.exe` 的残留进程后 `uv self update` 成功),`uv run --frozen` 工作流恢复。

| 范围 | 命令 | 结果 |
|------|------|------|
| 去重相关 | `uv run --frozen pytest tests/test_inbox_dedup.py tests/test_dedup.py tests/test_pipeline_inbox_dedup.py` | **17 passed** |
| append_inbox 消费方 | `pytest tests/test_frontend.py tests/test_source_validation.py` | **69 passed** |
| 两处修复联合验证 | `uv run --frozen pytest tests/test_claude_longrun_config.py tests/test_inbox_dedup.py` | **10 passed** |
| 提交后自洽检查 | `uv run --frozen pytest tests/test_claude_longrun_config.py tests/test_inbox_dedup.py tests/test_toolchain_config.py tests/test_auth.py` | **16 passed** |
| 完整 checkpoint | `uv run --frozen python tools/quality_gate.py checkpoint` | **515 passed / 0 failed / 1 skipped** ✅ PASS |

失败 2 的目标测试 `test_rss_deduplicate_across_runs` 已转绿,失败 1 的 `test_shared_rules_block_external_and_self_modifying_actions` 已转绿,且未影响 `test_dedup.py` 的长标题去重契约。

---

## 剩余事项

1. **~~失败 1~~**:已修复 -- `.claude/settings.json` 补齐 `Read(.private/**)` 和 `Edit(AGENTS.md)` 两条 deny。
2. **~~uv 版本对齐~~**:已完成 -- `uv self update 0.11.32` 成功,`uv run --frozen` 工作流恢复。
3. **提交**:已完成两次本地提交(未 push,遵守 AGENTS.md "Never push to master"):
   - `048082c` - toolchain: pin Python 3.13.14/uv 0.11.32/npm 11.16.0, freeze deps, add Ruff/pip-audit/Dependabot
   - `bc25ebf` - fix: short-title dedup false-positive + .claude deny gaps + long-run agent config
4. **完整 checkpoint 复跑**:已完成 -- 515 passed / 0 failed / 1 skipped,Quality Gate PASS。
5. **push 到远端**:待用户授权(AGENTS.md 禁止自主 push to master)。
