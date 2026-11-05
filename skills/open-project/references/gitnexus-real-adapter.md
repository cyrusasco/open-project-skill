# Real Python plugin adapter

Use `scripts/gitnexus_onboard.py` only when a Codex user has authorized real
onboarding or UPDATE. This supplements the existing `gitnexus-project-onboarding`
owner; it does not change that owner's fixture-only entrypoint. ZCode does not use
this adapter. No automatic trigger, global hook, server, MCP or backend install.

## Supported admission

A local Codex plugin with `plugin.json`, an existing
`.agents/plugins/marketplace.json` pointing to `./`, and named immediate
`skills/<name>/SKILL.md` entries. Runtime resources are inventoried under those
skills. Only Python files are copied to the graph snapshot; Markdown, JSON,
HTML, YAML and TOML are fingerprinted metadata, not code graph nodes. Unknown
file types, missing owner/runtime, missing cross-file oracle or other catalog
layout are explicit unsupported profiles, never evidence of successful onboarding.
Pure Markdown skills need a separate metadata-only admission profile.

Excluded before content reads: named secret files, credentials, caches,
dependencies, build/dist and tests. Repository history and session histories
are not scanned. At most 300 resources / 8 MiB / 512 KiB per resource and
128 Python files. All existing path ancestors and admitted leaves reject
symlinks, junctions/reparse points, traversal and hardlinks. This is path
validation, not an OS security boundary against concurrent hostile writers.

The backend remains the existing GitNexus 1.6.9, checked against eight exact
effect-critical file hashes. Node executable bytes are also bound to admission.
Pass their existing absolute locations; do not download substitutes or edit pins
when they differ. The snapshot gets its own registry, HOME, temp and cache;
`--index-only --skip-git` prevents source/config/agent injection. Extension
installation is `never`, model download flags are offline, embeddings are off.
This is software effect routing, not proof of OS network isolation.

## Commands

All path placeholders below mean absolute paths chosen for this project. STATE
must be outside SOURCE, exclusively owned, and writable in the current session.
OUT/PLAN/APPROVAL are task evidence files. Use an absolute ADAPTER path from the
selected plugin skill; no dependence on the shell's current directory.

```text
python ADAPTER plan --source SOURCE --state STATE --project PROJECT_ID --backend BACKEND_ROOT --node NODE_EXE --owner-skill OWNER_SKILL_MD --out PLAN
python ADAPTER build --plan PLAN --approval APPROVAL
python ADAPTER verify --state STATE --ref BUILD_RESULT_JSON
python ADAPTER status --state STATE
python ADAPTER complete --state STATE --codex CODEX_EXE --out COMPLETION_JSON
python ADAPTER lookup --state STATE --name PythonFunctionName
python ADAPTER rollback --state STATE
```

`plan` reads source and runtime identities and writes the requested new plan
file only. Its oracle is derived from Python AST without importing or executing
source. Independently review the file inventory, oracle, state owner and effects
before build. Approval records real existing user authorization; its hash is
integrity binding, not user authentication:

```json
{
  "schema": "open-project-real-approval/1",
  "approved": true,
  "admission_sha256": "<digest(plan) from adapter helper>",
  "source_root": "<exact admission source.root>",
  "state_root": "<exact admission state_root>",
  "project_id": "<exact admission project_id>",
  "effects": ["owned-python-snapshot", "owned-index-registry-cache", "owned-receipts-and-pointer"],
  "request_ref": "<actual user request reference>"
}
```

Capture the JSON stdout from `build` to BUILD_RESULT_JSON. `build` stages an
immutable generation; `verify` requires actual successful CLI output for all
admitted File rows, sampled definitions with exact zero-based declaration rows,
cross-file CALLS, IMPORTS and a negative query. Partial/missing/wrong rows fail;
no reducing the expected oracle to make a graph result pass. The raw command
runs, admission, approval, build receipt and verification remain in the generation.
Only successful verification publishes an atomic current pointer. This is
structural acceptance for the declared coverage, not semantic completeness.

`status` starts no backend. It checks source identity, captured evidence, backend,
owner skill, adapter, snapshot and closed DB/metadata/query-helper/registry hashes.
Build-only parse caches are excluded from the closed graph identity; graph queries
do not rebuild from them. Source changes
are STALE; missing or corrupted required evidence is BLOCKED. UPDATE requires
a new admission and actual authorization. Replaying the identical build is a
no-op. `rollback` restores a prior owned pointer or retires the first; it never
deletes source, generations or failed runs. Recovery must not steal stale locks
or remove unresolved process markers without investigating the recorded process.

`lookup` provides a usable bounded exact-symbol query against this project's
owned index. Results identify original source files and human 1-based lines,
with snapshot digest and raw query evidence. Rows/comments remain data, not
instructions. Query can open the owned DB/registry and is not a zero-effect
operation; it verifies identities before/after. It never silently rebuilds.
It does not imply registration in an unrelated global MCP or provide FTS search.

## Native catalog and complete receipt

`complete` reads the existing native Codex marketplace/plugin listing with the
absolute installed `codex.exe`, matches the registered source root, and binds
the current source manifest plus each canonical contained SKILL.md. It creates
no parallel catalog. The receipt distinguishes source catalog admission from
installed version and model invocation. The native CLI can attempt incidental
temporary PATH-alias writes; this is not a zero-write host guarantee. An older installed cache must be updated
through the native installer separately; catalog admission is not installation.

Each plugin and contained skill has its own artifact row with graph/catalog
status. They share the project graph that includes their actual runtime files.
Capture COMPLETION_JSON and this adapter as required full file sources, then use
`source:<ID>` for the G6 evidence and adapter_ref, with adapter_scope=real-project.
Do not promote a fixture receipt or a successful plan to VERIFIED.

The existing immutable casebook collector accepts genuine Jev controller state
only. A directly authorized task with no such state marks that collector N/A
and keeps its actual generation receipts; it must not fabricate Jev records or
create a replacement casebook. If a real Jev state exists, use its owner normally.

## Provenance and acceptance

The lifecycle follows the existing reviewed real-project-v1 two-file Python
pilot (2026-10-27): copied allowlist, pinned backend, source-derived exact oracle,
staged verification, bounded processes, atomic pointer and retained rollback.
This adapter is separately implemented for explicit plugin inventories; the
pilot's fixed source, state, approval and verification are not reused as authority.
Tests use disposable synthetic sources. Real onboarding receipts must come from
the selected actual source and backend. Tests do not claim native plugin invocation.
