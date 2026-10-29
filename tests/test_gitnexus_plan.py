"""Codex plan inclusion checks; never executes the installed onboarding backend."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/open-project/scripts'
sys.path.insert(0, str(SCRIPTS))
from plan_contract import PacketError, packet_digest
import plan_render
import promote
from support import make_packet, save_packet

spec = importlib.util.spec_from_file_location('gitnexus_plan_gate', SCRIPTS / 'gate-check.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GitNexusPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        self.plan = make_packet(self.project, host='codex')

    def inspect(self):
        save_packet(self.project, self.plan)
        plan_render.write_views(self.project, self.plan)
        return gate.inspect_packet(self.project)

    def applicable(self, status='PLANNED'):
        row = self.plan['tools'][0]
        row.update(status=status, reason='Selected fixture Skill and Plugin require admission planning.',
                   skill_ref='fixture:reviewed-onboarding-skill-snapshot',
                   artifacts=[{'id': 'skill-a', 'kind': 'skill', 'source_root': 'fixture/skill-a',
                               'project_id': 'fixture-project', 'graph_status': 'NOT_APPLICABLE',
                               'catalog_status': 'PLANNED'},
                              {'id': 'plugin-a', 'kind': 'plugin', 'source_root': 'fixture/plugin-a',
                               'project_id': 'fixture-project', 'graph_status': 'BLOCKED',
                               'catalog_status': 'PLANNED'}],
                   steps=['Review supported source scope and metadata catalog owner.',
                          'Independently review admission before any separately authorized build.'],
                   acceptance=['Each selected artifact has graph/catalog disposition and receipt references.'],
                   blockers=[], evidence=[])
        if status == 'BLOCKED':
            row['blockers'] = ['Installed onboarding supports only the fixed JavaScript fixture workspace.']
        return row

    def assert_g6_failure(self, result):
        self.assertFalse(result['ready'], result)
        self.assertTrue(any(error.startswith('G6:') for error in result['errors']), result)

    def test_codex_missing_or_duplicate_inclusion_is_not_ready(self):
        row = self.plan['tools'][0]
        for rows in ([], [copy.deepcopy(row), copy.deepcopy(row)], ['gitnexus-project-onboarding']):
            self.plan['tools'] = rows
            with self.subTest(rows=rows):
                self.assert_g6_failure(self.inspect())

    def test_nonapplicable_requires_explicit_reason_and_no_artifacts(self):
        self.assertTrue(self.inspect()['ready'])
        self.plan['tools'][0]['reason'] = '  '
        self.assert_g6_failure(self.inspect())
        row = self.applicable('NOT_APPLICABLE')
        self.assert_g6_failure(self.inspect())
        row['artifacts'] = []
        self.assertTrue(self.inspect()['ready'])

    def test_planned_and_blocked_are_complete_plans_without_completion_claim(self):
        for status in ('PLANNED', 'BLOCKED'):
            self.applicable(status)
            with self.subTest(status=status):
                result = self.inspect()
                self.assertTrue(result['ready'], result)
                self.assertTrue(any(status in item and 'not verified' in item
                                    for item in result['warnings']), result)

    def test_blocked_requires_actionable_blocker_list(self):
        row = self.applicable('BLOCKED')
        row['blockers'] = []
        self.assert_g6_failure(self.inspect())

    def test_malformed_inclusion_values_fail_closed(self):
        original = copy.deepcopy(self.applicable())
        changes = [{'status': 'DONE'}, {'status': []}, {'skill_ref': ''}, {'reason': None},
                   {'steps': 'inspect; build'}, {'steps': []}, {'acceptance': []},
                   {'blockers': [False]}, {'evidence': ['']}, {'artifacts': {}},
                   {'artifacts': []}, {'artifacts': ['skill-a']}]
        for change in changes:
            row = copy.deepcopy(original)
            row.update(change)
            self.plan['tools'] = [row]
            with self.subTest(change=change):
                self.assert_g6_failure(self.inspect())

    def test_artifact_identity_and_disposition_are_required(self):
        row = self.applicable()
        original = copy.deepcopy(row['artifacts'][0])
        for field in ('id', 'kind', 'source_root', 'project_id', 'graph_status', 'catalog_status'):
            artifact = copy.deepcopy(original)
            del artifact[field]
            row['artifacts'] = [artifact]
            with self.subTest(missing=field):
                self.assert_g6_failure(self.inspect())
        row['artifacts'] = [copy.deepcopy(original), copy.deepcopy(original)]
        self.assert_g6_failure(self.inspect())

    def test_verified_requires_receipt_and_all_artifact_dispositions_complete(self):
        row = self.applicable('VERIFIED')
        self.assert_g6_failure(self.inspect())
        row['evidence'] = ['fixture:immutable-admission-and-catalog-receipts']
        self.assert_g6_failure(self.inspect())
        for artifact in row['artifacts']:
            artifact['catalog_status'] = 'VERIFIED'
            artifact['graph_status'] = 'NOT_APPLICABLE'
        self.assertTrue(self.inspect()['ready'])
        row['blockers'] = ['Fixture catalog owner still unavailable.']
        self.assert_g6_failure(self.inspect())

    def test_zcode_packet_does_not_gain_codex_dependency(self):
        self.plan['host'] = 'zcode'
        self.plan['tools'] = []
        self.assertTrue(self.inspect()['ready'])

    def test_skill_and_plugin_catalog_obligation_cannot_be_marked_nonapplicable(self):
        row = self.applicable('VERIFIED')
        row['evidence'] = ['fixture:graph-disposition-receipt']
        artifact = row['artifacts'][0]
        row['artifacts'] = [artifact]
        artifact['graph_status'] = 'NOT_APPLICABLE'
        artifact['catalog_status'] = 'NOT_APPLICABLE'
        for kind in ('skill', 'plugin'):
            artifact['kind'] = kind
            with self.subTest(kind=kind):
                result = self.inspect()
                self.assert_g6_failure(result)
                self.assertTrue(any('require catalog onboarding' in error for error in result['errors']), result)

    def test_full_artifact_scope_steps_and_blockers_render_in_both_views(self):
        row = self.applicable('BLOCKED')
        result = self.inspect()
        self.assertTrue(result['ready'], result)
        views = [(self.project / name).read_text(encoding='utf-8') for name in plan_render.OUTPUTS]
        for view in views:
            for expected in ('gitnexus-project-onboarding', 'skill-a', 'plugin-a',
                             'fixture/skill-a', 'fixture/plugin-a', row['steps'][0], row['blockers'][0]):
                self.assertIn(expected, view)

    def test_strict_missing_inclusion_returns_failure_and_advisory_preserves_not_ready(self):
        self.plan['tools'] = []
        self.inspect()
        command = [sys.executable, str(SCRIPTS / 'gate-check.py'), str(self.project), '--json']
        for strict, expected_exit in ((False, 0), (True, 1)):
            result = subprocess.run(command + (['--strict'] if strict else []), capture_output=True,
                                    text=True, encoding='utf-8')
            self.assertEqual(result.returncode, expected_exit, result.stderr + result.stdout)
            self.assert_g6_failure(json.loads(result.stdout))

    def test_missing_onboarding_refuses_approved_target_write_without_mutation(self):
        self.plan['tools'] = []
        self.inspect()
        draft = self.plan['drafts'][0]
        approval = {'plan_id': self.plan['plan_id'], 'revision': self.plan['revision'],
                    'packet_sha256': packet_digest(self.plan), 'approved_by': 'Synthetic reviewer',
                    'approved_at': '2026-10-29T12:00:00+08:00',
                    'actions': [{'draft_id': draft['id'], 'target': draft['target'],
                                 'draft_sha256': draft['sha256'], 'baseline_sha256': draft['baseline_sha256'],
                                 'expected_sha256': draft['expected_sha256'], 'transforms': draft['transforms'],
                                 'effects': ['write_file']}]}
        approval_path = Path(self.temp.name) / 'approval.json'
        approval_path.write_text(json.dumps(approval), encoding='utf-8')
        snapshot = lambda: {path.relative_to(self.project).as_posix(): path.read_bytes()
                            for path in self.project.rglob('*') if path.is_file()}
        before = snapshot()
        with self.assertRaisesRegex(PacketError, 'G6:'):
            promote.promote(self.project, approval_path, apply=True)
        self.assertEqual(snapshot(), before)
        self.assertFalse((self.project / promote.STATE).exists())


if __name__ == '__main__':
    unittest.main()
