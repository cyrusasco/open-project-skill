# open-project (ZCode skill)

A generic ZCode skill for **starting a new project or reorganizing an existing one** — evidence-first, drafts-before-approval, N/A-friendly.

通用 ZCode skill：開新 project／重整舊 project 嘅端到端流程——先攞證據，草稿全文俾你過目，批准先落正式檔。

## What it does

Phase 0–9, one pipeline for both routes:

| Phase | What |
|---|---|
| 0 | Intent / interview (new route asks targeted questions) + size S/M/L |
| 1 | Facts vs unknowns (every fact has a source; unknowns marked UNVERIFIED) |
| 2 | Session review (whole-system discovery, depth tags, pain points, role stats) |
| 3 | File / code / git / secret review (code map, conflicts, authority order) |
| 4 | PLAN + **full MD drafts (md-drafts/ staging)** + offline HTML report + gate-check — **stops for your approval** |
| 5 | Drift check → byte-level backups → promote (whitelisted transforms only) |
| 6 | Build only what the evaluation says (SKILL / MCP / CLI / Plugin / agent — **N/A is a valid answer**) |
| 7 | Plugin packaging (PACKAGED vs INSTALLED states) |
| 8 | Independent read-only review (12 checks, PASS/FAIL/UNVERIFIED) |
| 9 | Handover (LOCAL COMPLETE / NOT_PUSHED are legal endings) |

`scripts/gate-check.py` — advisory mechanical checks (missing drafts, stale HTML vs plan-data, agent model placeholder, fake timestamps, stale references). Suggestions at the end of the report; `--strict` makes any FAIL exit non-zero.

## Install

1. Copy this repo's `skills/open-project/` folder → `~/.zcode/skills/open-project/`
2. Copy `commands/open-project.md` → `~/.zcode/commands/open-project.md`
3. Restart ZCode (skills load in **new** sessions only), then:

```
/open-project new <goal or folder>
/open-project reorg <existing project folder>
```

## Requirements

- ZCode
- Python 3.10+ (for `scripts/gate-check.py`)
- git + GitHub CLI (`gh`) — optional, used for open-source candidate search in Phase 4

## Repo layout

```
skills/open-project/          <- the skill (SKILL.md, templates/ x10, scripts/)
commands/open-project.md      <- /open-project slash command
```

## License

MIT — see [LICENSE](LICENSE).
