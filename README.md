# open-project — ZCode edition

Explicitly requested project start / reorganization, with full drafts before approval.

通用開案／重整流程，**只喺用戶明確叫用 open-project 時啟動**。保留 Phase 0–9、全文 MD 草稿、product specification、離線 HTML、advisory 預設及 N/A。此 repo 保持 ZCode harness；Codex 版使用獨立來源，不覆寫 ZCode 設定。

## Source and compatibility

- Skill revision: **3.0.0**; packet contract: **1.0**; first plugin package: **0.1.0**.
- ZCode conventions retained: Agent / subagent_type, ReadSessionContext, .zcode-plugin, command $ARGUMENTS, current agent model/provider rules.
- Model selection is resolved. This release fixes parsing and integrity, and does not change working backend/model configuration.
- SOURCE.json records the reviewed upstream commit. Generated package manifests record exact content hashes.
- No command changes the installed skill, host config, plugin cache or another project automatically.

## Explicit invocation

Use the command exposed by ZCode, for example:

    /open-project new <goal or folder>
    /open-project reorg <project folder>

Plugin namespaces can change the displayed command name. Select the actual command shown by the host, and verify which package it resolves to.

**ZCode native manual-only enforcement is not yet verified.** The description and workflow require explicit invocation, but packaging a discoverable skill is not a host-level guarantee. Do not copy Codex or Claude flags into ZCode. Until native behavior is verified, disable the plugin when not using it, and use a dedicated explicitly invoked task when enabled. This fallback has an extra step; it is not advertised as an enabled-but-never-automatic guarantee.

Before migrating, inventory old standalone skills and global commands so another copy cannot keep auto-triggering or shadow the plugin. Back up and disable only the chosen old entry; do not delete unrelated user setup. Installation/load/invocation verification are separate from building.

## Build a plugin without installing

    python scripts/build-plugin.py

This writes an isolated package to build/zcode/open-project/ and verifies the resource allowlist. It includes no database, session history, secrets, permanent service or automatic hook. Existing different output is not overwritten; choose another --output for a new build. Rebuilding identical bytes is a no-op.

The repo contains a native ZCode manifest and marketplace entry using the ZCode plugins[].source string convention. JSON validity and a complete package do not prove that a particular ZCode version loads it. Use the host's plugin installation flow, then test in a new session. No installation or restart is performed by the build script.

## Runtime tools

All tools are under skills/open-project/scripts/:

    python discover-sessions.py --db <ZCode db.sqlite> --keyword <project-alias> --output <task-local-report.json>
    python render-plan.py <PROJECT>
    python gate-check.py <PROJECT> --json
    python gate-check.py <PROJECT> --strict
    python promote.py <PROJECT> --approval <approval.json>
    python promote.py <PROJECT> --approval <approval.json> --apply

- Discovery searches system-wide visible conversation text before directory/title signals. Search hits are candidates, not full review. Coverage, source identity, read depth and snapshot limits are explicit.
- Rendering consumes md-drafts/plan-data.json and writes only the two staging views. Full draft text is embedded in the offline HTML.
- Gate checking validates schema, required drafts/specification, content hashes, host-specific agent syntax and exact generated views. Advisory can exit zero with ready=false; strict fails required errors.
- Promote defaults to dry-run. Applying needs an exact approval record and unchanged hashes; backups, journal, no-op and recovery states are recorded. An approval record is evidence of a decision, not an OS permission boundary.
- Supported deterministic transforms: exact draft marker removal and UTF-8/LF normalization. Other edits must be made in the staged draft before approval.
- Capture target hashes when reading the source. Do not regenerate a baseline after writing a draft.

See references/workflow-contract.md, references/host-zcode.md and the schema inside the skill for packet fields and limitations.

## Workflow

| Phase | Output |
|---|---|
| 0 | Intent, route, scale, targeted interview |
| 1 | Facts, unknowns, read-time baseline |
| 2 | Whole-system discovery, relationships, deep-read tags, coverage |
| 3 | Files/code/git/secret review |
| 4 | PLAN + every full MD draft + specification + JSON + offline HTML + gate report; approval |
| 5 | Approved writes only, drift checks, byte backups, deterministic promote |
| 6 | Build justified tools/agents; N/A is valid |
| 7 | Package the target project's plugin only if needed |
| 8 | Independent review; required unresolved findings prevent acceptance |
| 9 | Handover; LOCAL COMPLETE / NOT_PUSHED are valid |

## Tests

    python -m unittest discover -s tests -v

Tests use synthetic files/SQLite databases, never the live ZCode database. They include malformed packet/agent negatives, numeric/unknown-value rendering, cross-directory discovery, WAL and promote drift/recovery cases. A test pass is not a fresh-session host-loading claim. SELFTEST.md and historical percentage scores are not prerequisites or current evidence.

Python **3.10+** for ZCode tools; Python 3.11+ only for TOML checking in the separate Codex edition. No runtime package dependency is required for ZCode.

MIT — retain LICENSE in derived packages.

## Migrating a v2 packet

Version 3 uses the breaking schema1.0 packet contract. Legacy Markdown-only or loose JSON packets intentionally report INCOMPLETE. Preserve old packets and approvals as history. Rebuild the structured packet and complete drafts from verified evidence, preserving known first-read baselines; if a baseline is unknown or drifted, read/review the new source and make a new revision. Regenerate both views and obtain an exact new approval. Never silently infer a legacy approval or recapture a baseline after drafting.
