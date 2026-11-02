"""Exact approval and legacy recovery boundaries on synthetic fixtures."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/open-project/scripts'
sys.path.insert(0, str(SCRIPTS))
from plan_contract import PacketError, packet_digest
import plan_render
import promote
from support import save_packet
from workflow_support import make_workflow_packet


class WorkflowPromotionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / 'project'
        self.project.mkdir()
        self.plan = make_workflow_packet(self.project)
        self.approval = Path(temporary.name) / 'approval.json'

    def prepare(self):
        save_packet(self.project, self.plan)
        plan_render.write_views(self.project, self.plan)
        value = {'plan_id':self.plan['plan_id'], 'revision':self.plan['revision'],
                 'packet_sha256':packet_digest(self.plan), 'approved_by':'Synthetic actual decision reference',
                 'approved_at':'2026-11-02T21:00:00+08:00', 'actions':[]}
        for draft in self.plan['drafts']:
            value['actions'].append({'draft_id':draft['id'], 'target':draft['target'],
                'draft_sha256':draft['sha256'], 'baseline_sha256':draft['baseline_sha256'],
                'expected_sha256':draft['expected_sha256'], 'transforms':draft['transforms'],
                'effects':['write_file']})
        self.approval.write_text(json.dumps(value), encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.project).as_posix():p.read_bytes()
                for p in self.project.rglob('*') if p.is_file()}

    def legacy(self):
        self.plan['schema_version'] = '1.0'
        self.plan.pop('workflow')
        self.prepare()

    def seed_original_journal(self):
        # This represents bytes left by the old release, not a fresh action
        # admitted by the new release. Recovery still verifies every identity.
        approval, approval_hash, drafts = promote._approval(self.project,self.plan,self.approval)
        actions = promote._preflight(self.project,drafts)
        rel = promote._journal_path(self.plan,approval_hash)
        journal = {'version':1,'plan_id':self.plan['plan_id'],'revision':self.plan['revision'],
                   'packet_sha256':packet_digest(self.plan),'approval_sha256':approval_hash,
                   'approval':approval,'status':'PREPARED','backup_id':'a'*32,
                   'actions':actions,'errors':[]}
        path = self.project / rel
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(journal),encoding='utf-8')
        return path

    def test_v2_promotion_is_not_workflow_completion(self):
        self.prepare()
        result = promote.promote(self.project,self.approval,apply=True)
        self.assertEqual(result['status'],'COMMITTED',result)
        self.assertEqual(result['workflow_status'],'PROMOTED')
        self.assertFalse(result['workflow_complete'])

    def test_default_dry_run_does_not_mutate(self):
        self.prepare()
        before = self.snapshot()
        result = promote.promote(self.project,self.approval)
        self.assertEqual(result['status'],'DRY_RUN')
        self.assertFalse(result['workflow_complete'])
        self.assertEqual(self.snapshot(),before)

    def test_legacy_new_promotion_is_refused_before_state_creation(self):
        self.legacy()
        before = self.snapshot()
        with self.assertRaises(promote.LegacyMigration):
            promote.promote(self.project,self.approval,apply=True)
        self.assertEqual(self.snapshot(),before)

    def test_legacy_recovery_cannot_create_a_new_journal(self):
        self.legacy()
        before = self.snapshot()
        with self.assertRaises(promote.LegacyMigration):
            promote.promote(self.project,self.approval,apply=True,resume=True,legacy_recovery=True)
        self.assertEqual(self.snapshot(),before)

    def test_only_exact_original_legacy_journal_can_recover(self):
        self.legacy()
        self.seed_original_journal()
        result = promote.promote(self.project,self.approval,apply=True,resume=True,legacy_recovery=True)
        self.assertEqual(result['status'],'COMMITTED',result)
        self.assertEqual(result['workflow_status'],'RECOVERY_ONLY')
        self.assertFalse(result['workflow_complete'])

    def test_changed_legacy_approval_cannot_rebind_recovery(self):
        self.legacy()
        self.seed_original_journal()
        value = json.loads(self.approval.read_text(encoding='utf-8'))
        value['approved_by'] = 'Different decision'
        self.approval.write_text(json.dumps(value),encoding='utf-8')
        before = self.snapshot()
        with self.assertRaises(PacketError):
            promote.promote(self.project,self.approval,apply=True,resume=True,legacy_recovery=True)
        self.assertEqual(self.snapshot(),before)

    def test_recovery_flag_cannot_change_v2_validation(self):
        self.prepare()
        with self.assertRaises(PacketError):
            promote.promote(self.project,self.approval,resume=True,legacy_recovery=True)


if __name__ == '__main__':
    unittest.main()
