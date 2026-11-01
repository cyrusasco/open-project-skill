# Codex edition 0.1.1

Skill revision 3.0.0-codex.2, packet1.0 with the Codex GitNexus plan profile. Main remains the separate ZCode edition; its harness is unchanged. The two-host update guide is shared as documentation only.

## Result

Every Codex plan must include the existing gitnexus-project-onboarding workflow. Each project Skill/Plugin deliverable has its own artifact identity, source root, graph/catalog status, admission steps, acceptance, blockers and evidence. PLAN section6 and offline HTML render the same structured tools row. Execution order and specification/review/status/handover templates retain the obligation.

G6 rejects missing, duplicate or malformed onboarding rows. Skill/Plugin catalog enrollment cannot be skipped as NOT_APPLICABLE. Missing integration prevents strict success and even otherwise-approved promotion before target/state mutation. A complete PLANNED/BLOCKED plan can be ready for review, with a warning that onboarding is not verified; final acceptance still requires the actual evidence.

The installed onboarding Skill was inspected directly. Its current copied-JavaScript synthetic-fixture MVP does not admit arbitrary real projects or Markdown Skills. Missing reviewed real-project/catalog adapters remain BLOCKED; they are explicit dependencies, not invented capabilities. Existing graph/catalog/casebook owners remain authoritative. Reused dependencies do not recursively enroll shared Skills.

## Validation

113 synthetic tests ran: 112 passed, 0 failures/errors, 1 real-Windows-symlink privilege skip. See TEST-RESULTS.json for the complete result. New checks cover omission/duplicates/typed fields, Skill/Plugin artifact coverage in rendered views, plan-ready versus verified state, catalog N/A rejection, strict CLI failure and promotion without side effects. Packaging requires the onboarding reference. The isolated0.1.1 package build succeeded with27 hash-listed resources; no real-profile installation succeeded. A fresh read-only task using the updated workflow retained separate Plugin/Skill rows and correctly reported missing real metadata adapters as BLOCKED.

Both independent review findings were corrected and rechecked: catalog N/A bypass, and constructing the onboarding row after rendering. The row is now created before rendering, gating and approval digest capture. No remaining findings were reported in the reviewed scope.

Native CLI0.154.0 successfully installed and loaded plugin0.1.1 in an isolated test home. All27 runtime hashes matched, with zero loader errors. NATIVE-LOAD-RESULT.json records this current evidence. It does not prove actual model invocation or installation into the real profile.

## Migration and boundaries

Earlier Codex packets must add the onboarding tools row, increment revision, regenerate both canonical views, rerun gate and obtain an approval matching the new packet digest. Root schema remains1.0. Do not reuse approvals after content changes.

The actual-profile native installation attempt failed AccessDenied while registering the marketplace in config.toml; no target plugin entry was installed. HOST-INSTALL-RESULT.json records that failure separately from the isolated success. No GitNexus backend/graph/catalog/casebook or live session history was modified. Calling the workflow remains explicit-only; there is no global automatic hook or enrollment.

File promotion approval covers write_file, not index build/catalog writes/backend verification. Use any existing valid authorization covering those effects; otherwise include the concrete required action for review. SOURCE, PACKAGED, INSTALLED, LOAD_VERIFIED and INVOCATION_VERIFIED remain distinct.

## Installation and two-host handoff

The source now includes scripts/install-plugin.ps1 (PowerShell7 and Python3.11+). It validates the source policy/version/resources, refuses conflicting marketplace roots, uses native registration/install/list commands and verifies exact installed identity/version/enabled/source. Failure remains INSTALL_NOT_VERIFIED, including a partial registration; it does not edit config/cache directly or remove existing state. Eight synthetic installer scenarios and a real native run in the isolated home passed.

UPDATE-GUIDE.md is shared on both branches. ZCode updates use main, preserving model/provider/frontmatter/commands/hooks/config. Codex uses codex-port. The current session cannot write the actual Codex profile; run the helper from an ordinary authorized PowerShell7 session with profile write access. No privilege or sandbox workaround is included.
