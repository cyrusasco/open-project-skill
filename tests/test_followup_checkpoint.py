"""Bounded relevance screening and continuation; no real session reads."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/open-project/scripts'))
from plan_contract import PacketError, packet_digest, sha256
from followup_checkpoint import evaluate_checkpoint, inspect_checkpoint, checkpoint_schema


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        raw = b'Synthetic inventory, scoped keyword hits, explicit deferral and read receipt.\n'
        (self.root / 'evidence.txt').write_bytes(raw)
        self.plan = {'schema_version': '2.0', 'plan_id': 'example', 'revision': '2',
                     'sources': [{'id': 'E', 'kind': 'file', 'path': 'evidence.txt', 'sha256': sha256(raw)}],
                     'workflow': {'roots': {'docs_root': str(self.root), 'source_roots': []}}}
        self.data = {'schema_version': 'open-project/followup/1.0', 'plan_id': 'example',
                     'revision': '2', 'packet_sha256': packet_digest(self.plan),
                     'scope': 'Synthetic project relevance only', 'inventory_evidence': ['source:E'],
                     'inventory': [{'id': 'a', 'source': 'native', 'session_id': 'opaque-a'},
                                   {'id': 'b', 'source': 'native', 'session_id': 'opaque-b'}],
                     'screening': [self.row('a', 'RELATED', 'FULL'), self.row('b', 'UNRELATED', 'NOT_REQUIRED')],
                     'tasks': []}

    def row(self, name, relevance, read):
        return {'id': name, 'relevance': relevance, 'read': read, 'basis': 'bounded_context',
                'reason': 'Scoped content classification', 'evidence': ['source:E'],
                'read_scope': 'Only project requirements and necessary neighboring messages'}

    def task(self, kind='reading', state='READY'):
        return {'id': 't', 'kind': kind, 'session_ids': ['a'], 'action': 'Read relevant followup',
                'state': state, 'reason': 'Specific remaining task', 'owner': 'parent',
                'evidence': ['source:E'], 'authority_ref': '', 'blocker': 'none'}

    def run_check(self):
        return evaluate_checkpoint(self.plan, self.root, self.data)

    def test_unrelated_session_need_not_be_deep_read(self):
        result = self.run_check()
        self.assertTrue(result['can_stop'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['screening_counts']['UNRELATED'], 1)

    def test_inventory_count_difference_does_not_imply_missing_deep_reads(self):
        for i in range(57):
            name = 'unrelated-' + str(i)
            self.data['inventory'].append({'id': name, 'source': 'native', 'session_id': name})
            self.data['screening'].append(self.row(name, 'UNRELATED', 'UNREAD'))
        self.assertTrue(self.run_check()['can_stop'])

    def test_missing_screening_is_distinct_from_required_deep_read(self):
        self.data['screening'].pop()
        with self.assertRaisesRegex(PacketError, 'missing screening'):
            self.run_check()

    def test_title_path_parent_alone_cannot_exclude(self):
        for basis in ('metadata_only', 'verified_link'):
            self.data['screening'][1]['basis'] = basis
            with self.assertRaisesRegex(PacketError, 'alone'):
                self.run_check()

    def test_uncertain_relation_requires_bounded_classification_not_full_read(self):
        self.data['screening'][0] = self.row('a', 'UNDETERMINED', 'UNREAD')
        self.data['screening'][0]['basis'] = 'metadata_only'
        with self.assertRaisesRegex(PacketError, 'continuation task'):
            self.run_check()
        self.data['tasks'] = [self.task('relevance')]
        self.assertEqual(self.run_check()['status'], 'CONTINUE_REQUIRED')

    def test_related_unread_requires_action_even_if_other_work_blocked(self):
        self.data['screening'][0]['read'] = 'PARTIAL'
        blocked = {**self.task('other', 'BLOCKED'), 'id': 'blocked', 'blocker': 'tool_limit'}
        self.data['tasks'] = [blocked]
        with self.assertRaisesRegex(PacketError, 'continuation task'):
            self.run_check()
        self.data['tasks'].append(self.task())
        result = self.run_check()
        self.assertFalse(result['can_stop'])
        self.assertEqual(result['ready_tasks'], ['t'])

    def test_real_blocker_allows_checkpoint_but_never_completion(self):
        self.data['screening'][0]['read'] = 'PARTIAL'
        self.data['tasks'] = [{**self.task(state='BLOCKED'), 'blocker': 'missing_source'}]
        self.assertTrue(self.run_check()['can_stop'])
        self.assertFalse(self.run_check()['complete'])
        self.data['tasks'][0]['blocker'] = 'none'
        with self.assertRaisesRegex(PacketError, 'concrete dependency'):
            self.run_check()

    def test_user_deferral_requires_captured_authority(self):
        self.data['tasks'] = [self.task('other', 'DEFERRED')]
        with self.assertRaisesRegex(PacketError, 'user scope'):
            self.run_check()
        self.data['tasks'][0]['authority_ref'] = 'source:E'
        self.assertTrue(self.run_check()['can_stop'])

    def test_unchecked_related_attachment_is_a_ready_task(self):
        self.data['tasks'] = [self.task('attachment')]
        self.assertFalse(self.run_check()['can_stop'])

    def test_stale_packet_hash_and_captured_evidence_fail(self):
        self.data['packet_sha256'] = '0' * 64
        with self.assertRaisesRegex(PacketError, 'another packet'):
            self.run_check()
        self.data['packet_sha256'] = packet_digest(self.plan)
        (self.root / 'evidence.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(PacketError, 'captured file bytes'):
            self.run_check()

    def test_duplicates_and_unknown_evidence_fail(self):
        old = deepcopy(self.data)
        self.data['inventory'].append(self.data['inventory'][0])
        with self.assertRaisesRegex(PacketError, 'duplicate'):
            self.run_check()
        self.data = old
        self.data['screening'][0]['evidence'] = ['source:invented']
        with self.assertRaisesRegex(PacketError, 'unknown checkpoint evidence'):
            self.run_check()

    def test_missing_or_invalid_checkpoint_fails_closed(self):
        with mock.patch('followup_checkpoint.load_plan', return_value=self.plan):
            self.assertEqual(inspect_checkpoint(self.root)['status'], 'CHECKPOINT_INCOMPLETE')
            (self.root/'md-drafts').mkdir()
            (self.root/'md-drafts/followup-checkpoint.json').write_text('{bad')
            self.assertFalse(inspect_checkpoint(self.root)['can_stop'])

    def test_published_schema_matches_executable_contract(self):
        schema = json.loads((ROOT/'skills/open-project/schemas/followup.schema.json').read_text())
        self.assertEqual(schema, checkpoint_schema())

    def test_copied_packet_cannot_certify_another_project_root(self):
        other = self.root/'other'
        other.mkdir()
        with self.assertRaisesRegex(PacketError, 'canonical docs_root'):
            evaluate_checkpoint(self.plan, other, self.data)


if __name__ == '__main__':
    unittest.main()
