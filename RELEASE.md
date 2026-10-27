# Release 3.0.0 — ZCode edition

Shared integrity upgrade; ZCode host configuration preserved.

## Changes

- Explicitly requested workflow; Phase 0–9 and complete review packet retained.
- Structured packet1.0, required full specification/drafts, content-bound exact Markdown/HTML views, precise approvals and read-time baselines.
- Safe typed frontmatter parsing with existing ZCode model/provider policy preserved.
- Whole-system visible-session discovery with read-only WAL snapshot, lineage, coverage and opaque IDs.
- Dry-run promotion, exact hashes, private byte backups, Windows-safe locking, idempotent/no-op behavior and verified crash recovery.
- Offline full-text renderer with exact decimal/unknown values, phase guide, charts, scalable graph and safe links.
- Native ZCode package manifests and reproducible allowlisted build.

## Validation

89 synthetic tests ran: 88 passed, 0 failures, 0 errors, 1 real-symlink test skipped because the Windows environment denies symlink creation. See TEST-RESULTS.json.

An independent review verified malformed URL handling, ambiguous database identity rejection, package completeness, Windows case-insensitive repeated promotion, optional TOML import, and malformed-journal rejection before mutation.

No live session database, installed ZCode skill, backend model/provider setting or global host configuration was modified.

## Update and migration

Use main for ZCode. Update source/package as one revision, then use ZCode's supported reload/new-session flow; do not assume a session already holding v2 instructions hot-loads v3.

Packet1.0 is a breaking review-packet contract. Preserve historical packets/approvals, rebuild from verified first-read evidence, regenerate both views and obtain a new exact approval. Do not infer legacy approval or silently recapture a baseline after drafting.

## Limits

PACKAGED does not mean INSTALLED or LOAD_VERIFIED. ZCode native manual-only enforcement and fresh-session loading are not verified here. Python3.10 compatibility was tested by simulating absent tomllib, not by running an actual3.10 interpreter.

Promotion recovery verifies target file bytes. Audit state/backups and empty created parent directories may remain. Cooperative locks do not stop arbitrary external writers.

The separate codex-port branch has its own portable manifest, invocation policy, native agents and history adapter. Never copy that branch's settings into ZCode or merge the whole port branch into main.
