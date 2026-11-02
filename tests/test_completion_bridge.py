"""Completion requires immutable promoted decisions, not only fresh self-claims."""
from pathlib import Path
import copy
import importlib.util
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/open-project/scripts'
sys.path.insert(0,str(SCRIPTS))
from workflow_contract import workflow_snapshot_digest
from workflow_support import make_workflow_packet,finalize_review_draft
from support import save_packet
import plan_render

spec = importlib.util.spec_from_file_location('completion_bridge_gate',SCRIPTS/'gate-check.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class CompletionBridgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)/'project'
        self.project.mkdir()
        # The complete fixture uses the real promoter with an explicit synthetic
        # decision and NO_OP targets; it does not fabricate a COMMITTED journal.
        self.plan = make_workflow_packet(self.project,complete=True)
        self.save()

    def save(self):
        save_packet(self.project,self.plan)
        plan_render.write_views(self.project,self.plan)

    def assert_bridge_failure(self):
        result = gate.inspect_packet(self.project,stage='completion')
        self.assertFalse(result['complete'],result)
        self.assertTrue(any(value.startswith('G8:') for value in result['errors']),result)

    def test_missing_committed_journal_prevents_completion_despite_outputs_and_review(self):
        self.assertTrue(gate.inspect_packet(self.project,stage='completion')['complete'])
        directory = self.project/'.open-project-promotion/journals'
        paths = list(directory.glob('*.json'))
        self.assertTrue(paths)
        for path in paths:
            path.unlink()
        self.assert_bridge_failure()

    def test_journal_packet_approval_raw_scope_and_action_tampering_are_rejected(self):
        path = next((self.project/'.open-project-promotion/journals').glob('*.json'))
        original = path.read_bytes()
        original_value = json.loads(original)
        mutations = [
            lambda j:j['approved_packet']['project'].update(name='tampered capture'),
            lambda j:j.update(approved_packet_raw_base64='not base64'),
            lambda j:j.update(approved_packet_raw_sha256='0'*64),
            lambda j:j.update(material_snapshot_sha256='0'*64),
            lambda j:j['approval'].update(approved_by='different decision identity'),
            lambda j:j['approval'].update(packet_sha256='0'*64),
            lambda j:j['actions'][0].update(expected_sha256='0'*64),
            lambda j:j['actions'][0].update(status='PENDING'),
            lambda j:j['approval']['actions'].pop(),
            lambda j:j.update(version=1),
        ]
        for number,mutate in enumerate(mutations):
            with self.subTest(mutation=number):
                value = copy.deepcopy(original_value)
                mutate(value)
                path.write_text(json.dumps(value),encoding='utf-8')
                self.assert_bridge_failure()
                path.write_bytes(original)
        self.assertTrue(gate.inspect_packet(self.project,stage='completion')['complete'])

    def test_material_change_and_self_refreshed_review_cannot_reuse_old_approval(self):
        self.plan['requirements'][0]['text'] += ' A new material requirement was added.'
        review = self.plan['workflow']['review']
        review['snapshot_sha256'] = workflow_snapshot_digest(self.plan,self.project)
        # This intentionally models an unapproved writer refreshing every visible
        # assertion, including report bytes. The immutable approval still wins.
        finalize_review_draft(self.plan,self.project,publish_fixture=True)
        self.save()
        self.assert_bridge_failure()


if __name__=='__main__':
    unittest.main()
