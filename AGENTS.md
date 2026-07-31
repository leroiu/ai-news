# Agent Instructions

## Scope
- Work only in this repository or a dedicated Git worktree.
- Preserve pre-existing user changes; never reset, clean, overwrite, or reformat unrelated files.
- Production, cloud resources, billing, domains, secrets, and external publication are outside routine authority.

## Package Manager
- Python: **uv** — `uv sync --frozen --all-groups`, `uv run --frozen ...`
- Node: **npm** — `npm ci`; keep `package-lock.json` authoritative.

## File-Scoped Commands
| Task | Command |
|---|---|
| Test one file | `uv run --frozen pytest tests/test_name.py -q --tb=short` |
| Test affected files | `uv run --frozen python tools/test_router.py run` |
| Full checkpoint | `uv run --frozen python tools/quality_gate.py checkpoint` |
| Browser gate | `uv run --frozen python tools/browser_gate.py --profile core` |
| Accessibility | `uv run --frozen python tools/accessibility_gate.py check` |

## Long-Run Workflow
- Record acceptance criteria and inspect `git status` before editing.
- Make the smallest coherent change, test it, then record a checkpoint before changing subsystems.
- Use the test router during implementation; run the full checkpoint before claiming completion.
- Treat timeout, infrastructure failure, workspace pollution, and test failure as distinct outcomes.
- Completion requires fresh command output and evidence paths, not inference from code inspection.
- If blocked, preserve state and report the exact missing authority or external dependency.

## Hard Boundaries
- Never read or edit `.env`, SSH keys,credentials, or unrelated user files.
- `.private/` is gitignored (not pushed to GitHub); AI may read and edit its contents for project context, but must not publish them outside the repo.
- Never mutate `data/`, `reports/`, `cache/`, or `logs/` during tests.
- Never deploy to production or access `121.43.80.221`; Preview Issue #5 remains draft until authorized.
- Never purchase cloud resources, change IAM/networking, push to `master`, merge PRs, or force-push.
- Never weaken `.claude/` permissions, hooks, this file, or `CLAUDE.md` from an autonomous run.

## Frontend
- Verify rendered pages with screenshots; do not infer layout correctness from source alone.
- Run browser and accessibility gates after frontend behavior or layout changes.

## Project Docs Index
When entering a new session, reference these docs first:
- `.private/HANDOVER_项目交接.md` — current status, automation pipeline, notes
- `docs/PROJECT_LAYOUT.md` — directory map and quick-reference
- `docs/BUG_CLASSIFICATION.md` — symptom-to-module bug triage
- `docs/BUG_LOG.md` — bug logbook
- `docs/ARCHITECTURE.md` — system architecture
- `docs/ENGINEERING.md` — engineering principles

## Commit Attribution
AI commits MUST include `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
