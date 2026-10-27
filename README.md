# Open Project · Codex

A manually invoked Codex plugin for project start/reorganization, full drafts, approval and handover.

只喺你明確選取 open-project 時用；平時修 bug、開新 project 或讀 repo，不應自動導入完整流程。

## Edition boundary

This is the **codex-port branch** of cyrusasco/open-project-skill. Main remains the ZCode edition. Do not merge this entire branch into main or copy its host settings into ZCode.

Shared contract, checker, renderer, promote and generic templates come from the reviewed common source. Codex has separate invocation policy, JSONL discovery, native agent templates and portable manifests. PORTING.md and SOURCE.json record provenance.

- Plugin: open-project-codex 0.1.0
- Skill: open-project (3.0.0-codex.1)
- Packet contract: 1.0
- Python 3.11+ for standard-library tools and native-agent TOML checks
- No MCP server, automatic hook or global instruction installation

## Use

After selecting this plugin in a supported Codex surface, explicitly select the open-project skill or request:

    用 open-project 幫我重整 <project folder>，先出完整草稿同離線報告。

agents/openai.yaml uses the YAML boolean allow_implicit_invocation:false. Metadata may remain visible; it does not authorize workflow execution. Inventory independently installed duplicates separately.

Phase4 delivers PLAN, every full MD draft/specification, JSON, offline HTML and gate evidence before formal writes. Continue within concrete existing authorization, without asking the same approval repeatedly. Completing or stopping a task does not permanently activate the workflow.

## Local marketplace

Check installed CLI help first. Supported clients can use:

    codex plugin marketplace add cyrusasco/open-project-skill --ref codex-port --json
    codex plugin add open-project-codex@open-project-codex --json
    codex plugin list --marketplace open-project-codex --available --json

The catalog source is relative to the repository root on this branch. Do not register main as the Codex edition. This is repo/local marketplace distribution, not public directory submission.

To disable a local-marketplace plugin in a trusted project:

    [plugins."open-project-codex@open-project-codex"]
    enabled = false

This Codex-specific choice is not applied automatically. The package does not rewrite global AGENTS or touch ZCode settings.

## Build without installing

    python scripts/build-plugin.py

Output: build/codex/open-project-codex/. Resource allowlist excludes DB/history/secrets/tests. Different existing output is never overwritten; use --output for another candidate. PACKAGE-MANIFEST.json records source hashes and starts at PACKAGED, not INSTALLED or INVOCATION_VERIFIED.

## Runtime tools

Under skills/open-project/scripts/:

    python discover-sessions.py --sessions-root <whole CLI sessions root> --keyword <alias> --output <task-local-report.json>
    python render-plan.py <PROJECT>
    python gate-check.py <PROJECT> --json
    python gate-check.py <PROJECT> --strict
    python promote.py <PROJECT> --approval <approval.json>
    python promote.py <PROJECT> --approval <approval.json> --apply

Prefer available native app list/read/archived tools. CLI JSONL does not cover all app/cloud histories. The adapter retains source/hash/snapshot/coverage, no cwd/title prefilter, unread depth until deep-read, and no hidden reasoning evidence.

Rendering reads schema1.0 md-drafts/plan-data.json and every full draft, including specification. It produces matching Markdown and static offline HTML with full draft text. Advisory exit0 is not ready=true.

Promote defaults to dry-run. Apply requires an authentic user approval record matching plan/draft/target/baseline/expected hashes and fixed transforms. Approval records are evidence, not OS security boundaries. Never regenerate a baseline after drafting.

## Tests and host verification

    python -m unittest discover -s tests -v

All fixtures are synthetic files/SQLite/JSONL. Common ZCode-policy fixtures validate the shared parser, not operation of a ZCode harness. Port-specific tests cover Codex JSONL and native agents. Parsing/loading tests do not prove actual model invocation; fresh-session behavior is reported separately.

Model/reasoning remains user/host-controlled. Native agent TOML is optional; fields cannot expand parent permissions.

MIT; preserve LICENSE and upstream attribution.

## Verified native name

Codex CLI0.154.0 exposes this Git/local plugin skill as open-project-codex:open-project. In a Codex message, explicit CLI-style invocation is:

    $open-project-codex:open-project reorg <project folder>

Use the actual skill picker/registry name on other surfaces. This is prompt text, not a PowerShell command.
