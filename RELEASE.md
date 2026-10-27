# Codex edition 0.1.0

Skill revision 3.0.0-codex.1, packet1.0. Upstream f4e32bed5a11b9d83567c8e580db82cd908d9ba3.

92 synthetic tests ran: 91 passed, 0 failures/errors, 1 Windows real-symlink privilege skip. See TEST-RESULTS.json. All common code matches PORTING.md.

This edition adds a portable skills-only plugin, boolean explicit-only invocation policy, native Codex agent templates and all-visible-record-view JSONL discovery. No ZCode model or agent settings are copied.

PACKAGE/INSTALL/LOAD/INVOCATION are distinct states. Native metadata loading and any actual model behavior must be reported separately; unit tests do not certify implicit invocation behavior. No live history/database or real host configuration changed.

Use codex-port for Codex and main for ZCode. Local/repo marketplace registration can pin this branch. Do not merge whole host editions.

Packet migration is breaking: preserve old evidence and approvals, rebuild from verified first-read baselines, regenerate exact views and obtain a new exact approval.

Recovery covers target file bytes; audit state/backups and empty created directories may remain. Cooperative locks do not prevent arbitrary external writers.

## Native loading check

Codex CLI0.154.0 successfully registered and installed the local marketplace in an isolated CODEX_HOME. A fresh app-server process recognized open-project-codex:open-project with zero loader errors; all26 runtime resource hashes matched. See NATIVE-LOAD-RESULT.json. The installed manual-only metadata file matches source. No model turn was run, so this does not claim LLM invocation behavior has been tested. The real user profile and ZCode configuration were not modified.
