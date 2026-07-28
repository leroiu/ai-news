@AGENTS.md

# Claude Code Project Rules

- Detailed long-run policy: `docs/LONG_RUNNING_AGENT_MODE.md`.
- Start autonomous work through `scripts/start-claude-longrun.ps1`; do not switch to `bypassPermissions` on native Windows.
- `dontAsk` plus `.claude/settings.longrun.json` is the approved host mode. Unlisted actions are denied instead of prompting.
- Auto-mode classifier failure and primary-model unavailability are different failures; permission escalation fixes neither.
- Before compaction or stopping, leave a checkpoint under `output/claude-checkpoints/`.
- A task that reaches deployment, Preview, production, billing, domain, or secret configuration must stop and request authority.
