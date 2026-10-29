# Codex host adapter

## Contents

1. Invocation and package
2. Sessions and coverage
3. Agents and execution roots
4. GitNexus onboarding
5. Verification and limitations

## Invocation and package

Use a portable plugin.json at the package root, with skills/open-project/SKILL.md. agents/openai.yaml sets policy.allow_implicit_invocation to the YAML boolean false. Explicit skill selection remains available; do not assume a slash command name. Use the actual picker/registry entry shown by the target host.

This package does not install hooks, MCP servers, global instructions or another copy of the skill. A plugin can still expose metadata while explicit-only policy prevents implicit invocation. Inventory any independently installed duplicate before interpreting a negative trigger test.

The source catalog .agents/plugins/marketplace.json uses a local source object resolved from the repository root. It is not packaged in the standalone plugin. A local CLI may support:

    codex plugin marketplace add <repo-or-local-root> --json
    codex plugin add open-project-codex@open-project-codex --json
    codex plugin list --marketplace open-project-codex --available --json

Check installed CLI help first. Marketplace registration/installation writes host state; perform it only within the selected scope. Do not restart or rewrite the user's application as a side effect of a source update.

## Sessions and coverage

Use native app list/read/archived tools when they exist, paginate every source and retain actual source identifiers. Not all CLI, cloud and app histories share one storage source. A hidden/unavailable app backend is UNKNOWN.

The local fallback accepts explicit JSONL source roots. A conventional CLI location is CODEX_HOME/sessions (or ~/.codex/sessions); archived JSONL roots and exports must be separately inventoried. Do not scan only the active cwd or assume this root includes app/cloud history.

The adapter reads visible response_item message content with role user/assistant. It does not read reasoning or encrypted content as conversation evidence. event_msg user/assistant records are a fallback when a file has no supported response message records, avoiding double-counting two views. Inter-agent records without a known user/assistant role remain skipped/unknown.

Snapshot identity is per-file raw hash, size and before/after stat observations. Files are not a single database transaction; concurrent changes mean the affected file is PARTIAL. JSONL truncation, duplicate IDs with different revisions, unreadable sources, orphan parent metadata and unknown schemas are reported. Search results start at depth unread; a hit is not a full deep-read.

The adapter never writes history, creates a permanent index, copies hidden reasoning into reports or includes private text snippets by default. Output is an explicitly selected task-local report.

## Agents and execution roots

Use currently available native roles/tools. If custom agents are justified and supported, native TOML requires name, description and developer_instructions. Model and effort can be omitted to inherit the parent. Host-selected model/reasoning remains authoritative; this plugin does not pick a backend.

Custom agent fields do not grant permissions or override parent sandbox/approval. Capture requested role, child identity and observed behavior; a requested label alone does not prove which definition was loaded.

Plugin resources are read relative to the selected installed skill. Project commands run from the approved project root, not the plugin cache. Use templates/agent.template.md for a project operation manual; use agent.template.toml only for actual native agent registration, with a separately scoped write target.

## GitNexus onboarding

Read [the Codex onboarding contract](gitnexus-onboarding.md) for every open-project plan. Reuse the installed gitnexus-project-onboarding Skill, resolved under CODEX_HOME or the configured skill root, and capture its current source identity. Do not bundle a copy, invent an MCP dependency or install it automatically. Missing Skill/adapter/catalog access is a BLOCKED dependency.

Every adopted/created Skill and Plugin has a separate admission row in the plan. Project code/structure goes to the approved graph; capability metadata goes to its existing catalog owner; minimized receipts stay with the immutable casebook owner. The installed Skill inspected for this revision is fixture-only. Its fixed copied-JavaScript workspace and pin are not permission to index a real project, personal skill home or plugin cache. Real project/catalog admission needs its own reviewed adapter.

Keep the active project/task/native session/Project Pair. Planning does not approve backend execution. Build, verify, catalog registration and UPDATE require their actual effect scope and valid existing authorization; stale detection never triggers a rebuild. No global hooks, history indexing or writes to frozen original_skills are added.

## Verification and limitations

Test configuration parsing/package loading separately from actual invocation behavior. An isolated CLI home can test loading without changing the real user's plugins. Do not copy credentials into a test home or claim an unauthenticated test proved model behavior.

A new session must verify explicit selection works, unrelated prompts do not activate this workflow, and disabling the selected package removes its capability. Existing sessions can cache metadata.

Sources checked 2026-10-27:
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://developers.openai.com/plugins/build/plugins

These are host contracts, not evidence that this particular package was installed or used.
