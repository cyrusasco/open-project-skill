"""Behavioral regressions for mandatory workflow obligations and evidence bounds."""
import copy
import json
import re
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'skills/open-project/scripts'), str(ROOT / 'tests')]
from plan_contract import PacketError, expected_content, sha256, validate_plan
from workflow_contract import workflow_findings, workflow_snapshot_digest
from workflow_support import make_workflow_packet, finalize_review_draft


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tests', prefix='workflow-contract-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.plan = make_workflow_packet(self.project)

    def codes(self, stage='plan'):
        return {row['code'] for row in workflow_findings(self.plan, self.project, stage)}

    def complete(self):
        self.plan = make_workflow_packet(self.project, complete=True)

    def refresh_review(self):
        self.plan['workflow']['review']['snapshot_sha256'] = workflow_snapshot_digest(self.plan, self.project)
        finalize_review_draft(self.plan, self.project, publish_fixture=True)

    def history(self):
        capture = self.project / 'session-capture.txt'
        capture.write_bytes(b'Visible message one.\nVisible message two.\nVisible message three.\n')
        digest = sha256(capture.read_bytes())
        self.plan['sources'].append({'id': 'session-1', 'kind': 'session', 'required': True,
            'depth': 'full', 'reference': 'synthetic:visible-capture', 'verified': True,
            'content_sha256': digest})
        self.plan['workflow']['discovery'].update(status='COMPLETE',
            reason='Global inventory of the one synthetic authorized source.',
            inventory=[{'id': 'synthetic-db', 'kind': 'sqlite', 'required': True,
                        'status': 'AVAILABLE', 'reference': 'synthetic:db-inventory'}],
            queries=['synthetic-project'],
            reads=[{'source_id': 'session-1', 'depth': 'full', 'reference': 'synthetic:read-range',
                    'unit': 'lines', 'total': 3, 'content_sha256': digest,
                    'capture': {'root_id': 'docs', 'path': capture.name, 'sha256': digest},
                    'ranges': [{'start': 1, 'end': 3}]}])
        receipt = {'schema_version': 'open-project/discovery-receipt/2.0', 'adapter': 'synthetic',
            'status': 'COMPLETE', 'source_inventory': [{'source_id': 'synthetic-db', 'status': 'AVAILABLE'}],
            'query_groups': [{'id': 'project-keywords', 'keywords': ['synthetic-project']}],
            'census': {'message_rows': {'unit': 'message rows', 'total': 3, 'eligible': 3,
                'scanned': 3, 'skipped': 0, 'error_rows': 0, 'matched': 1, 'unscanned': 0}},
            'pagination': {'end_reached': {'message_rows': True}},
            'snapshot': {'kind': 'synthetic', 't0': '2026-11-02T00:00:00Z', 't1': '2026-11-02T00:00:01Z'},
            'complete_scope': 'supplied_sources_only', 'all_system_history_complete': False,
            'reading': {'full': 0, 'partial': 0, 'summary-only': 0, 'unread': 3}, 'limitations': []}
        self.save_receipt(receipt)
        return receipt

    def save_receipt(self, data):
        path = self.project / 'discovery-receipt.json'
        raw = json.dumps(data, sort_keys=True).encode('utf-8')
        path.write_bytes(raw)
        self.plan['workflow']['discovery']['receipts'] = [{'root_id': 'docs', 'path': path.name, 'sha256': sha256(raw)}]

    def test_complete_core_documents_and_future_work_are_plan_ready(self):
        validate_plan(self.plan)
        self.assertEqual([], workflow_findings(self.plan, self.project))
        self.assertIn('W_PHASE', self.codes('completion'))
        self.assertIn('W_REVIEW', self.codes('completion'))

    def test_every_omitted_core_role_is_rejected_even_when_manifest_claims_complete(self):
        for role in ('project_manual', 'specification', 'project_status', 'memory', 'independent_review'):
            with self.subTest(role=role):
                packet = copy.deepcopy(self.plan)
                packet['workflow']['documents'] = [d for d in packet['workflow']['documents'] if d['role'] != role]
                with self.assertRaises(PacketError):
                    validate_plan(packet)

    def test_required_false_cannot_cancel_manual(self):
        self.plan['drafts'][1]['required'] = False
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_full_phase_set_is_mandatory(self):
        self.plan['workflow']['phases'].pop()
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_wrong_root_cannot_fall_back_to_cwd(self):
        self.plan['workflow']['roots']['docs_root'] = str(self.project.parent)
        self.assertIn('W_ROOT', self.codes())

    def test_new_folder_cannot_relabel_existing_unrelated_directory(self):
        receipt = self.plan['workflow']['roots']['creation_receipt']
        receipt.update(before='EXISTING', status='EXISTING')
        self.assertIn('W_DESTINATION', self.codes())

    def test_resume_requires_same_plan_identity(self):
        receipt = self.plan['workflow']['roots']['creation_receipt']
        receipt.update(before='SAME_PLAN', status='RESUMED')
        self.assertEqual(set(), self.codes())
        receipt['plan_id'] = 'unrelated-plan'
        self.assertIn('W_DESTINATION', self.codes())

    def test_x_spec_with_fresh_hashes_still_fails_content_obligations(self):
        draft = self.plan['drafts'][0]
        raw = b'x\n'
        (self.project / draft['path']).write_bytes(raw)
        draft.update(sha256=sha256(raw), expected_sha256=sha256(raw), transforms=[])
        self.assertIn('W_CONTENT', self.codes())
        self.assertIn('W_TRACEABILITY', self.codes())

    def test_empty_requirement_is_not_accepted_as_generic_object(self):
        self.plan['requirements'] = [{}]
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_feature_cannot_omit_a_declared_requirement(self):
        self.plan['requirements'].append({'id': 'REQ-2', 'text': 'Another feature is required.',
            'source_ids': ['user-goal'], 'acceptance': ['A second bounded result.']})
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_decision_current_cannot_contradict_latest_real_event(self):
        self.plan['workflow']['decisions'] = {
            'events': [{'id': 'event-1', 'action_id': 'A7', 'state': 'APPROVED',
                        'reference': 'synthetic:user-approval', 'observed_at': '2026-11-02T21:00:00+08:00'}],
            'current': [{'action_id': 'A7', 'state': 'PENDING_APPROVAL', 'event_id': 'event-1'}]}
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_fake_timestamp_is_rejected(self):
        self.plan['workflow']['roots']['creation_receipt']['observed_at'] = '21:2x'
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_workflow_strings_retain_original_unicode_scalar_guard(self):
        self.plan['workflow']['features'][0]['description'] = '\ud800'
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_zcode_has_no_gitnexus_dependency(self):
        self.assertEqual(set(), self.codes())
        self.assertFalse(any(t.get('id') == 'gitnexus-project-onboarding' for t in self.plan['tools']))
        self.plan['workflow']['gitnexus']['applicability'] = 'REQUIRED'
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_codex_requires_its_own_authoritative_g6_row(self):
        self.plan = make_workflow_packet(self.project, host='codex')
        validate_plan(self.plan)
        self.plan['tools'] = [t for t in self.plan['tools'] if t.get('id') != 'gitnexus-project-onboarding']
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_invalid_host_cannot_gain_zcode_na(self):
        self.plan['host'] = 'unknown'
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_completion_positive_has_current_independent_review_and_all_outputs(self):
        self.complete()
        self.assertEqual(set(), self.codes('completion'))

    def test_old_review_revision_is_not_final_review(self):
        self.complete()
        self.plan['workflow']['review']['revision'] = '0'
        self.assertIn('W_REVIEW', self.codes('completion'))

    def test_stable_byte_changes_and_material_scope_changes_invalidate_review(self):
        self.complete()
        old = self.plan['workflow']['review']['snapshot_sha256']
        for field, mutate in [
            ('feature', lambda p: p['workflow']['features'][0].update(description='New material behavior.')),
            ('tool', lambda p: p['tools'][0].update(decision='adopt')),
            ('package', lambda p: p['workflow']['package'].update(reason='A different packaging scope.')),
            ('source', lambda p: p['sources'][0].update(reference='synthetic:changed-source')),
            ('unknown', lambda p: p['unknowns'].append({'id': 'hidden', 'required': True, 'status': 'OPEN'})),
            ('fact', lambda p: p['facts'].append('A new material observation.')),
            ('conflict', lambda p: p['conflicts'].append('An unresolved scope conflict.')),
            ('risk', lambda p: p['risks'].append('A newly identified risk.')),
            ('approval', lambda p: p['approval_requests'].append('A new requested side effect.')),
            ('execution', lambda p: p.update(execution={'next': 'Deploy now.'})),
        ]:
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.plan)
                mutate(mutated)
                self.assertNotEqual(old, workflow_snapshot_digest(mutated, self.project))

    def test_review_cannot_omit_required_area(self):
        self.complete()
        self.plan['workflow']['review']['areas'].pop()
        self.assertIn('W_REVIEW', self.codes('completion'))

    def test_metadata_accepted_cannot_hide_an_unexecuted_report(self):
        self.complete()
        draft = next(d for d in self.plan['drafts'] if d['id'] == 'review')
        path = self.project / draft['path']
        raw = path.read_bytes().replace(b'Status: ACCEPTED', b'Status: NOT_RUN')
        path.write_bytes(raw)
        draft['sha256'] = sha256(raw)
        output = expected_content(draft, raw)
        draft['expected_sha256'] = sha256(output)
        (self.project / draft['target']).write_bytes(output)
        self.assertIn('W_REVIEW', self.codes('completion'))

    def test_shipped_angle_placeholders_fail_in_prose_but_code_examples_remain_valid(self):
        draft = next(d for d in self.plan['drafts'] if d['id'] == 'manual')
        path = self.project / draft['path']
        original = path.read_bytes()
        for token in (b'<PROJECT>', b'<DOCS_ROOT>', b'<ID>', b'<ISO8601_WITH_OFFSET>', b'<SOURCE_REFS_AND_REVISION>'):
            with self.subTest(token=token):
                raw = original + b'\nCurrent root: ' + token + b'\n'
                path.write_bytes(raw)
                draft.update(sha256=sha256(raw), expected_sha256=sha256(expected_content(draft, raw)))
                self.assertIn('W_CONTENT', self.codes())
        raw = original + b'\nCommand example uses `<ID>`.\n\n```text\ncommand <PROJECT>\n```\n<p>HTML paragraph.</p>\n'
        path.write_bytes(raw)
        draft.update(sha256=sha256(raw), expected_sha256=sha256(expected_content(draft, raw)))
        self.assertNotIn('W_CONTENT', self.codes())

    def test_actual_core_template_fill_tokens_fail_after_section_mapping(self):
        draft = next(d for d in self.plan['drafts'] if d['id'] == 'manual')
        path = self.project / draft['path']
        original = path.read_bytes()
        found = set()
        for filename in ('project-manual.template.md', 'product_specification.template.md',
                         'project_status.template.md', 'memory.template.md', 'REVIEW_REPORT.template.md'):
            text = (ROOT / 'skills/open-project/templates' / filename).read_text(encoding='utf-8')
            found.update(re.findall(r'\{\{[^}]+\}\}', text))
        self.assertTrue(found, 'Core templates should expose their fill-token inventory')
        for token in found:
            with self.subTest(token=token):
                raw = original + ('\nUnfilled actual template field: ' + token + '\n').encode('utf-8')
                path.write_bytes(raw)
                draft.update(sha256=sha256(raw), expected_sha256=sha256(expected_content(draft, raw)))
                self.assertIn('W_CONTENT', self.codes())

    def test_governance_roles_cannot_map_native_agent_drafts(self):
        for role in ('project_manual', 'project_status', 'memory', 'independent_review'):
            with self.subTest(role=role):
                plan = copy.deepcopy(self.plan)
                identifier = next(d['draft_id'] for d in plan['workflow']['documents'] if d['role'] == role)
                draft = next(d for d in plan['drafts'] if d['id'] == identifier)
                draft.update(kind='zcode-agent', transforms=['normalize_utf8_lf'])
                with self.assertRaises(PacketError):
                    validate_plan(plan)

    def test_one_overview_heading_cannot_satisfy_all_manual_sections(self):
        doc = next(d for d in self.plan['workflow']['documents'] if d['role'] == 'project_manual')
        for section in doc['sections']:
            section['heading'] = 'Overview'
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_empty_declared_sections_are_not_complete_content(self):
        draft = next(d for d in self.plan['drafts'] if d['id'] == 'manual')
        path = self.project / draft['path']
        raw = path.read_bytes().replace(b'## Purpose\n\nFixture requirement REQ-1 and feature F1 have bounded acceptance.\n\n', b'## Purpose\n\n')
        path.write_bytes(raw)
        draft.update(sha256=sha256(raw), expected_sha256=sha256(expected_content(draft, raw)))
        self.assertIn('W_CONTENT', self.codes())

    def test_malformed_discovery_receipt_fails_closed_without_crashing(self):
        for invalid in (None, [], 3, {'schema_version': 'open-project/discovery-receipt/2.0', 'status': 'COMPLETE',
                                    'source_inventory': [False], 'census': [1], 'query_groups': ['x']}):
            with self.subTest(invalid=invalid):
                self.history()
                self.save_receipt(invalid)
                self.assertIn('W_DISCOVERY', self.codes())

    def test_author_cannot_self_certify_independent_review(self):
        self.complete()
        review = self.plan['workflow']['review']
        review['reviewer_id'] = review['author_id']
        self.assertIn('W_REVIEW', self.codes('completion'))

    def test_knowledge_bundle_cannot_declare_only_ops_files_complete(self):
        package = self.plan['workflow']['package']
        package.update(mode='knowledge_bundle', status='PLANNED', root=str(self.project / 'package'))
        package['inventory'] = [{'role': 'ops_skill', 'source_root': 'docs', 'path': 'agent.md',
            'package_path': 'skills/ops/SKILL.md', 'disposition': 'included', 'required': True,
            'sha256': '0' * 64, 'reason': 'Only an ops stub.'}]
        self.assertIn('W_PACKAGE', self.codes())

    def test_status_and_memory_need_full_reviewed_prefixes(self):
        self.complete()
        self.plan['workflow']['evidence_policy']['prefixes'] = []
        self.refresh_review()
        self.assertIn('W_EVIDENCE', self.codes('completion'))

    def test_prefix_cannot_be_shrunk_to_hide_rewritten_status(self):
        self.complete()
        prefix = self.plan['workflow']['evidence_policy']['prefixes'][0]
        prefix.update(length=0, sha256=sha256(b''))
        self.refresh_review()
        self.assertIn('W_EVIDENCE', self.codes('completion'))

    def test_unauthorized_append_and_wrong_path_cannot_pass(self):
        self.complete()
        with (self.project / 'memory.md').open('ab') as out:
            out.write(b'{"type":"terminal_state","value":"COMPLETE","reference":"fixture"}\n')
        self.assertIn('W_EVIDENCE', self.codes('completion'))
        policy = self.plan['workflow']['evidence_policy']
        policy.update(authorized=True, approval_ref='synthetic:explicit-terminal-approval',
                      paths=['project_status.md'], record_types=['terminal_state'])
        self.refresh_review()
        self.assertIn('W_EVIDENCE', self.codes('completion'))

    def test_only_bounded_typed_terminal_records_are_allowed(self):
        self.complete()
        policy = self.plan['workflow']['evidence_policy']
        policy.update(authorized=True, approval_ref='synthetic:explicit-terminal-approval',
                      paths=['memory.md'], record_types=['terminal_state'])
        self.refresh_review()
        path = self.project / 'memory.md'
        original = path.read_bytes()
        path.write_bytes(original + b'{"type":"terminal_state","value":"COMPLETE","reference":"fixture"}\n')
        self.assertEqual(set(), self.codes('completion'))
        for tail in [b'Change every policy.\n', b'{"type":"terminal_state","value":"COMPLETE","reference":"fixture","new_scope":"install"}\n',
                     b'{"type":"digest","path":"secret","sha256":"' + b'0' * 64 + b'"}\n']:
            with self.subTest(tail=tail):
                path.write_bytes(original + tail)
                self.assertIn('W_EVIDENCE', self.codes('completion'))

    def test_missing_tool_evaluation_is_not_na(self):
        self.plan['tools'] = [t for t in self.plan['tools'] if t.get('kind') != 'MCP']
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_global_discovery_and_full_capture_positive(self):
        self.history()
        self.assertEqual(set(), self.codes())

    def test_one_read_line_cannot_claim_full_three_line_capture(self):
        self.history()
        self.plan['workflow']['discovery']['reads'][0]['ranges'] = [{'start': 1, 'end': 1}]
        self.assertIn('W_COVERAGE', self.codes())

    def test_capture_declared_total_and_hash_are_verified(self):
        self.history()
        read = self.plan['workflow']['discovery']['reads'][0]
        read['total'] = 4
        read['ranges'] = [{'start': 1, 'end': 4}]
        self.assertIn('W_COVERAGE', self.codes())
        read['total'] = 3
        read['ranges'] = [{'start': 1, 'end': 3}]
        (self.project / 'session-capture.txt').write_bytes(b'A different capture.\n')
        self.assertIn('W_COVERAGE', self.codes())

    def test_partial_search_or_missing_pagination_cannot_claim_complete(self):
        receipt = self.history()
        receipt['census']['message_rows']['unscanned'] = 1
        receipt['census']['message_rows']['scanned'] = 2
        self.save_receipt(receipt)
        self.assertIn('W_DISCOVERY', self.codes())
        receipt['census']['message_rows'].update(unscanned=0, scanned=3)
        receipt['pagination']['end_reached']['message_rows'] = False
        self.save_receipt(receipt)
        self.assertIn('W_DISCOVERY', self.codes())

    def test_tool_retrieval_counts_never_prove_model_deep_reading(self):
        self.history()
        self.plan['workflow']['discovery']['reads'][0]['depth'] = 'summary-only'
        self.assertIn('W_COVERAGE', self.codes())

    def test_reorg_cannot_hide_existing_history_by_na(self):
        self.plan['route'] = 'reorg'
        self.assertIn('W_DISCOVERY', self.codes())

    def test_required_inventory_source_needs_its_own_receipt(self):
        self.history()
        self.plan['workflow']['discovery']['inventory'].append({'id': 'missing-db', 'kind': 'sqlite',
            'required': True, 'status': 'AVAILABLE', 'reference': 'synthetic:known-other-db'})
        self.assertIn('W_DISCOVERY', self.codes())

    def test_cross_root_sources_are_not_resolved_against_docs(self):
        source = self.project / 'code-root'
        source.mkdir()
        (source / 'INDEX.md').write_bytes(b'Code evidence.\n')
        self.plan['workflow']['roots']['source_roots'].append({'id': 'code', 'path': str(source)})
        self.plan['sources'].append({'id': 'code-evidence', 'kind': 'file', 'root_id': 'code',
            'path': 'INDEX.md', 'sha256': sha256((source / 'INDEX.md').read_bytes()), 'depth': 'full', 'required': True})
        self.assertEqual(set(), self.codes())

    def test_codex_independent_review_has_its_extra_gitnexus_area(self):
        self.plan = make_workflow_packet(self.project, host='codex', complete=True)
        self.assertEqual(set(), self.codes('completion'))
        self.plan['workflow']['review']['areas'] = [a for a in self.plan['workflow']['review']['areas'] if a['id'] != 'gitnexus']
        self.assertIn('W_REVIEW', self.codes('completion'))

    def test_record_evidence_cannot_grant_project_config_writes(self):
        policy = self.plan['workflow']['evidence_policy']
        policy.update(authorized=True, approval_ref='synthetic:claimed', paths=['.git/config'], record_types=['digest'])
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_omitted_required_defaults_true_for_session_capture_checks(self):
        self.history()
        source = self.plan['sources'][-1]
        source.pop('required')
        source['depth'] = 'summary-only'
        self.plan['workflow']['discovery']['reads'] = []
        self.assertIn('W_COVERAGE', self.codes())

    def test_explicit_and_default_required_have_same_review_identity(self):
        first = workflow_snapshot_digest(self.plan, self.project)
        self.plan['sources'][0].pop('required')
        self.assertEqual(first, workflow_snapshot_digest(self.plan, self.project))

    def test_open_required_issues_block_the_due_stage(self):
        self.plan['workflow']['issues'] = [{'id': 'P1-verify', 'severity': 'P1', 'required': True,
            'phase': 6, 'status': 'OPEN', 'reference': 'synthetic:unrun-check', 'reason': 'Execution still needed.'}]
        self.assertNotIn('W_ISSUE', self.codes())
        self.assertIn('W_ISSUE', self.codes('completion'))
        self.plan['workflow']['issues'][0]['phase'] = 2
        self.assertIn('W_ISSUE', self.codes())

    def test_open_optional_p2_is_a_legal_roadmap_item(self):
        self.complete()
        self.plan['workflow']['issues'] = [{'id': 'P2-future', 'severity': 'P2', 'required': False,
            'phase': 9, 'status': 'OPEN', 'reference': 'synthetic:roadmap', 'reason': 'Optional later work.'}]
        self.refresh_review()
        self.assertEqual(set(), self.codes('completion'))

    def test_adopted_tool_cannot_hide_optional_implementation_or_missing_definition(self):
        tool = next(t for t in self.plan['tools'] if t['kind'] == 'SKILL')
        tool['decision'] = 'adopt'
        self.assertIn('W_PHASE', self.codes())
        self.assertIn('W_TOOL', self.codes())

    def test_native_agent_cannot_use_project_manual_as_its_definition(self):
        tool = next(t for t in self.plan['tools'] if t['kind'] == 'native_agent')
        tool.update(decision='adopt', artifacts=[{'draft_id': 'manual'}])
        next(p for p in self.plan['workflow']['phases'] if p['id'] == 6)['required'] = True
        self.assertIn('W_TOOL', self.codes())

    def test_skill_artifact_must_refer_to_its_actual_skill_definition(self):
        tool = next(t for t in self.plan['tools'] if t['kind'] == 'SKILL')
        tool.update(decision='adopt', artifacts=[{'draft_id': 'manual'}])
        next(p for p in self.plan['workflow']['phases'] if p['id'] == 6)['required'] = True
        self.assertIn('W_TOOL', self.codes())

    def test_captured_cli_artifact_is_accepted_then_hash_drift_is_rejected(self):
        path = self.project / 'synthetic-cli.py'
        path.write_bytes(b'print("synthetic fixture")\n')
        tool = next(t for t in self.plan['tools'] if t['kind'] == 'CLI')
        tool.update(decision='adopt', artifacts=[{'root_id': 'docs', 'path': path.name, 'sha256': sha256(path.read_bytes())}])
        next(p for p in self.plan['workflow']['phases'] if p['id'] == 6)['required'] = True
        self.assertEqual(set(), self.codes())
        path.write_bytes(b'print("unreviewed changed fixture")\n')
        self.assertIn('W_TOOL', self.codes())

    def test_plugin_adoption_cannot_claim_no_package_and_optional_phase(self):
        tool = next(t for t in self.plan['tools'] if t['kind'] == 'Plugin')
        tool['decision'] = 'adopt'
        self.assertIn('W_PACKAGE', self.codes())
        self.assertIn('W_PHASE', self.codes())

    def test_adopted_package_cannot_keep_plugin_na(self):
        self.plan['workflow']['package'].update(mode='local_adapter', status='PLANNED', root=str(self.project / 'bundle'))
        self.assertIn('W_PACKAGE', self.codes())


if __name__ == '__main__':
    unittest.main()
