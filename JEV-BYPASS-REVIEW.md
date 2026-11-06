# Independent Jev bypass review

Reviewed 2026-11-06: the proposed Codex and ZCode diffs, both policy helpers, Codex installer wrapper, bypass references and relevant tests. No source tree or user profile was modified by this reviewer. Tests ran in disposable copies under `work/`.

**Final disposition: all three initial P2 findings below are resolved in the rechecked candidate; no unresolved code defect was identified in this review scope. Real installation and fresh-session model behavior remain separate acceptance items.**

Final reviewed SHA-256 identities:

- Both `configure-jev-bypass.py` copies: `1f79a3cdcc6599c6d8025a1da7c55a86d510fa1fdfb8346d0b254664e7859e65`.
- Codex `install-with-jev-bypass.ps1`: `23e2169ae4508face6cf5672d05d36b8d38656b828ae8ab11d528365e0586281`.
- Both `jev-bypass.md` references: `ee3caa2a73adf094e8c7520c761e4d54689bf65a94c1ff48782139e81cb600d3`.

## Findings from initial candidate

1. **P2 — Effective Codex instructions can be missed.** `open-project-codex/scripts/install-with-jev-bypass.ps1:7–8` always selects `AGENTS.md`; both copies of `scripts/configure-jev-bypass.py:52–53` reject `AGENTS.override.md`. A nonempty home override takes precedence in Codex. Reproduced with a disposable override requiring Jev: the wrapper returned `SOURCE_AND_POLICY_VERIFIED` and `policy.active=true`, although the effective override contained no exception. Select the effective file, or report this configuration as blocked; verify its identity/hash after installation. The real home inspected during review had no override. Host discovery reference: https://learn.chatgpt.com/docs/agent-configuration/agents-md (retrieved 2026-11-06).

2. **P2 — A late wrapper failure hides an already-applied policy.** `open-project-codex/scripts/install-with-jev-bypass.ps1:15–25` mutates instructions before invoking the installer, but its catch omits the successful policy result and backup. Reproduced using a disposable incomplete source missing `scripts/install-plugin.ps1`: host instructions changed and a backup existed, while output reported only `UPDATE_BLOCKED` and an error. Validate required installer/source inputs before mutation and preserve stage/policy/backup in any later partial-failure result. Automatic rollback is unnecessary if partial state is accurately reported.

3. **P2 — Junction rejection is incomplete on the supported Python 3.11 baseline.** Both copies of `scripts/configure-jev-bypass.py:54–56` reject junctions only when `Path.is_junction` exists, which starts in Python 3.12; the Codex installer accepts Python 3.11 (`scripts/install-plugin.ps1:49–50`). In 3.11 the branch silently skips junction checks. Use the existing builder's `lstat` reparse-point approach or explicitly require a compatible runtime. This is a static compatibility finding; tests used Python 3.14.

## Behavioral reasoning

| Scenario | Contract outcome and evidence |
|---|---|
| Explicit invocation, Jev missing | The new SKILL section and reference lines 5–10, 28–31 require immediate bounded `USER_AUTHORIZED_BYPASS`; no route or additional bypass request. This depends on effective host provisioning and actual model adoption. |
| Resume old `BLOCKED_ROUTING` | Reference lines 33–37 retain old evidence and Project Pair, check running children/pending effects, and allow new authorized work. No earlier result is rewritten. |
| Quoted Skill / review only | Reference lines 12–15 and helper block lines 27–29 exclude activation; ordinary governance remains. |
| Explicit user opt-back to Jev | Reference line 10 and helper block line 29 restore the user's requested Jev path. A missing required Jev dependency may then block its dependent work. |
| Unapproved promote | Reference lines 48–53 preserve effect approval and failed gates. Promotion implementation is unchanged; the tested stale-approval sequence rejects before any project-byte change. |

Native model/provider and agent files are unchanged in the diff. ZCode retains AP-17 and GitNexus N/A; Codex retains its onboarding obligations. The existing real adapter already represents an absent Jev controller casebook honestly rather than fabricating receipts.

## Validation and limits

- 28 tests passed: both editions' nine bypass-helper tests and ten Codex installer tests.
- Eight Codex promotion/sequence tests passed, including exact revision approval and byte-preserving rejection.
- Both repositories passed `git diff --check` at review time. Shared helper and bypass-reference bytes matched across editions.
- Exact existing bytes, raw backup, idempotence, removal preserving later user text, baseline mismatch, modified/duplicate marker refusal and conflicting-backup refusal are exercised.
- Drift checks are cooperative, with no OS-level exclusion of other writers. Removal restores the original content plus later user content; creating and then removing an originally missing instructions file leaves an empty file.
- Source/unit fixtures do not prove real fresh-session activation, resumption behavior or model obedience. The candidate correctly marks invocation behavior unverified. ZCode has no automated native install verification in this update. Ordinary plugin installation alone does not provision the host exception.

## Correction recheck

All initial findings are closed. The wrapper now selects the nonempty effective override, validates source/installer inputs before applying the policy, retains stage/policy/backup on later failure, and rechecks effective selection plus exact instruction hash after installation. The helper now recognizes Windows reparse flags without depending on the Python 3.12 junction API.

Updated tests: 10 helper tests per edition and 14 Codex installer tests pass. One new test initially used direct console output, which bypassed the PowerShell capture pipeline; its corrected pipeline-output fixture passed on the focused rerun. Two additional independent fixture probes changed the effective override or appended host text during native installation; both correctly returned `PARTIAL_UPDATE` at `policy-verification` and retained backup evidence. The earlier eight promotion tests remain applicable because promotion code is unchanged.

## GitNexus UPDATE admission comparison

Read-only comparison of `work/jev-bypass/admission.json` with `work/real-onboarding/admission-final.json` found identical source root, plugin/marketplace identity, owner, state root, backend pins, owner skill, adapter, oracle, effect scope and declared limitations. Resource count changes from 35 to 36 only by adding the bypass reference; six existing metadata/document resources change. All ten admitted Python files are byte-identical. Every current admitted source hash, backend pin, Node hash and owner-skill hash matched the new admission.

This is maintenance within the same admitted effect scope, so the continuing maintenance authorization identified by the parent need not be renewed merely because source metadata/docs changed. This review did not independently retrieve the earlier conversational authorization and did not run the backend. The existing profile covers runtime resources and ten runtime Python files; authoring-root installer/helper scripts are outside that graph profile. Build/verify, retained receipts and fresh installation/invocation claims remain the parent's responsibility.
