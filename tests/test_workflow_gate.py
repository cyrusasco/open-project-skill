"""Stage-bound gates on synthetic packets; no live sessions or host state."""
from pathlib import Path
import copy
from datetime import datetime, timezone
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/open-project/scripts'
sys.path.insert(0, str(SCRIPTS))
from plan_contract import packet_digest, sha256
import plan_render
from support import save_packet
from workflow_support import make_workflow_packet

spec = importlib.util.spec_from_file_location('workflow_gate_under_test', SCRIPTS / 'gate-check.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class WorkflowGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / 'project'
        self.project.mkdir()

    def prepare(self, *, host='zcode', complete=False):
        self.plan = make_workflow_packet(self.project, host=host, complete=complete)
        self.save()
        return self.plan

    def save(self):
        save_packet(self.project, self.plan)
        plan_render.write_views(self.project, self.plan)

    def test_plan_readiness_does_not_claim_workflow_completion(self):
        self.prepare()
        result = gate.inspect_packet(self.project)
        self.assertTrue(result['ready'], result)
        self.assertFalse(result['complete'])
        self.assertEqual(result['status'], 'PLAN_READY')
        result = gate.inspect_packet(self.project, stage='completion')
        self.assertFalse(result['complete'], result)
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertFalse(result['completion_receipt']['complete'])

    def test_legacy_diagnostics_cannot_mint_current_readiness(self):
        self.prepare()
        self.plan['schema_version'] = '1.0'
        self.plan.pop('workflow')
        self.save()
        for diagnostic in (False, True):
            result = gate.inspect_packet(self.project, legacy_diagnostic=diagnostic)
            self.assertFalse(result['ready'])
            self.assertFalse(result['complete'])
            self.assertEqual(result['status'], 'MIGRATION_REQUIRED')
            self.assertTrue(result['diagnostic_only'])
            self.assertTrue(result['diagnostic_checks_passed'], result)

    def test_complete_receipt_binds_current_packet_and_output_snapshot(self):
        self.prepare(complete=True)
        result = gate.inspect_packet(self.project, stage='completion')
        self.assertTrue(result['complete'], result)
        receipt = result['completion_receipt']
        self.assertEqual(receipt['packet_sha256'], packet_digest(self.plan))
        self.assertEqual(receipt['revision'], self.plan['revision'])
        self.assertEqual(receipt['status'], 'COMPLETE')
        self.assertEqual(len(receipt['snapshot_sha256']), 64)
        before = receipt['observed_snapshot_sha256']
        self.assertEqual(receipt['snapshot_sha256'], before)
        spec_row = next(row for row in self.plan['drafts'] if row['kind'] == 'specification')
        (self.project / spec_row['target']).write_bytes(b'changed after independent review\n')
        result = gate.inspect_packet(self.project, stage='completion')
        self.assertFalse(result['complete'], result)
        self.assertNotEqual(result['completion_receipt']['observed_snapshot_sha256'], before)

    def test_completion_is_read_only(self):
        self.prepare(complete=True)
        before = {p.relative_to(self.project).as_posix(): p.read_bytes()
                  for p in self.project.rglob('*') if p.is_file()}
        result = gate.inspect_packet(self.project, stage='completion')
        self.assertTrue(result['complete'], result)
        after = {p.relative_to(self.project).as_posix(): p.read_bytes()
                 for p in self.project.rglob('*') if p.is_file()}
        self.assertEqual(after, before)

    def test_zcode_has_no_gitnexus_requirement(self):
        self.prepare(complete=True)
        self.assertFalse(any(row.get('id') == 'gitnexus-project-onboarding'
                             for row in self.plan['tools'] if isinstance(row,dict)))
        result = gate.inspect_packet(self.project, stage='completion')
        self.assertTrue(result['complete'], result)
        self.assertFalse(any('G6:' in value for value in result['errors']))

    def test_codex_pending_onboarding_cannot_become_complete(self):
        self.prepare(host='codex',complete=True)
        self.assertTrue(gate.inspect_packet(self.project,stage='completion')['complete'])
        row = next(row for row in self.plan['tools'] if row.get('id') == 'gitnexus-project-onboarding')
        row.update(status='BLOCKED', reason='Real adapter unavailable in this synthetic case.',
                   artifacts=[{'id':'fixture-project','source_root':str(self.project),'project_id':'fixture',
                       'kind':'project','graph_status':'BLOCKED','catalog_status':'NOT_APPLICABLE'}],
                   steps=['Review a real adapter.'],acceptance=['Obtain a real receipt.'],
                   blockers=['No reviewed real-project adapter.'])
        self.plan['revision'] = '2'
        self.plan['workflow']['review'].update(status='NOT_RUN',reviewer_id='',revision='2',snapshot_sha256='',areas=[])
        for phase in self.plan['workflow']['phases']:
            if phase['id'] >= 5:
                phase.update(status='PLANNED',evidence=[])
        self.save()
        self.assertTrue(gate.inspect_packet(self.project)['ready'])
        result = gate.inspect_packet(self.project,stage='completion')
        self.assertFalse(result['complete'])
        self.assertTrue(any('G6: Codex completion requires' in value for value in result['errors']),result)

    def test_invalid_stage_cannot_fall_back_to_a_ready_profile(self):
        self.prepare(complete=True)
        result = gate.inspect_packet(self.project, stage='typo')
        self.assertFalse(result['ready'])
        self.assertFalse(result['complete'])
        self.assertIn('stage must be', result['errors'][0])

    def test_codex_adopted_skill_cannot_hide_in_not_applicable(self):
        self.prepare(host='codex')
        definition = self.project/'fixture-skill/SKILL.md'
        definition.parent.mkdir()
        definition.write_text('---\nname: fixture-skill\ndescription: Explicit synthetic skill.\n---\n# Fixture\n',encoding='utf-8')
        next(row for row in self.plan['tools'] if row.get('kind') == 'SKILL').update(
            decision='adopt',artifacts=[{'root_id':'docs','path':'fixture-skill/SKILL.md','sha256':sha256(definition.read_bytes())}])
        next(phase for phase in self.plan['workflow']['phases'] if phase['id']==6)['required'] = True
        self.save()
        result = gate.inspect_packet(self.project)
        self.assertFalse(result['ready'])
        self.assertTrue(any('cannot use NOT_APPLICABLE' in value for value in result['errors']),result)

    def test_codex_verified_prose_without_captured_receipt_is_rejected(self):
        self.prepare(host='codex')
        row = next(row for row in self.plan['tools'] if row.get('id') == 'gitnexus-project-onboarding')
        row.update(status='VERIFIED',artifacts=[{'id':'fixture-skill','kind':'skill',
            'source_root':str(self.project),'project_id':'fixture',
            'graph_status':'NOT_APPLICABLE','catalog_status':'VERIFIED'}],
            steps=['Verify source'],acceptance=['Captured receipt'],evidence=['It passed.'])
        self.save()
        result = gate.inspect_packet(self.project)
        self.assertFalse(result['ready'])
        self.assertTrue(any('source:<id>' in value for value in result['errors']),result)
        self.assertTrue(any('real-project adapter scope' in value for value in result['errors']),result)

    def test_codex_capture_binding_and_fixture_scope_are_checked(self):
        # This checks metadata binding only, not actual backend enrollment or
        # authenticity of a real adapter. Independent review owns that judgment.
        self.prepare(host='codex')
        for identifier in ('onboarding-receipt','reviewed-adapter'):
            path = self.project/(identifier+'.txt')
            path.write_text('Synthetic captured metadata for '+identifier+'\n',encoding='utf-8')
            self.plan['sources'].append({'id':identifier,'kind':'file','required':True,'depth':'full',
                'path':path.name,'sha256':sha256(path.read_bytes())})
        row = next(row for row in self.plan['tools'] if row.get('id') == 'gitnexus-project-onboarding')
        row.update(status='VERIFIED',artifacts=[{'id':'fixture-skill','kind':'skill',
            'source_root':str(self.project),'project_id':'fixture',
            'graph_status':'NOT_APPLICABLE','catalog_status':'VERIFIED'}],
            steps=['Verify source'],acceptance=['Captured receipt'],evidence=['source:onboarding-receipt'],
            adapter_ref='source:reviewed-adapter',adapter_scope='fixture-only')
        self.save()
        self.assertFalse(gate.inspect_packet(self.project)['ready'])
        row['adapter_scope'] = 'real-project'
        self.save()
        self.assertTrue(gate.inspect_packet(self.project)['ready'])
        (self.project/'onboarding-receipt.txt').write_text('Changed after capture',encoding='utf-8')
        result = gate.inspect_packet(self.project)
        self.assertFalse(result['ready'])
        self.assertTrue(any('G6: cannot verify onboarding receipt capture' in value for value in result['errors']),result)

    def test_malformed_onboarding_values_fail_closed_without_crashing(self):
        self.prepare(host='codex')
        row = next(row for row in self.plan['tools'] if row.get('id') == 'gitnexus-project-onboarding')
        for changes in ({'status':'VERIFIED','evidence':None},
                        {'status':'PLANNED','artifacts':[{'id':'bad','kind':{},
                            'source_root':str(self.project),'project_id':'fixture',
                            'graph_status':'PLANNED','catalog_status':'PLANNED'}]}):
            with self.subTest(changes=changes):
                row.update(changes)
                self.save()
                result = gate.inspect_packet(self.project)
                self.assertFalse(result['ready'])
                self.assertTrue(any(value.startswith('G6:') for value in result['errors']),result)

    def test_completion_cli_emits_the_receipt_and_actual_exit(self):
        self.prepare(complete=True)
        run = subprocess.run([sys.executable, str(SCRIPTS / 'gate-check.py'),
                              str(self.project), '--stage', 'completion', '--strict', '--json'],
                             capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue(json.loads(run.stdout)['completion_receipt']['complete'])

    def test_declared_archive_preserves_source_identity_through_completion_and_noop(self):
        from workflow_contract import workflow_snapshot_digest
        from workflow_effects import effect_identity
        from workflow_support import finalize_review_draft
        import promote
        self.prepare(complete=True)
        old_review = copy.deepcopy(self.plan['workflow']['review'])
        self.plan['revision'] = '2'
        w = self.plan['workflow']
        code = self.project.parent/'code'
        code.mkdir()
        w['roots']['source_roots'] = [{'id':'code','path':str(code)}]
        original = b'# Preserved synthetic old specification\n'
        (code/'old-spec.md').write_bytes(original)
        original_ref = {'root_id':'code','path':'old-spec.md','sha256':sha256(original)}
        self.plan['sources'].append({'id':'original-spec','kind':'file','required':True,
                                     'depth':'full',**original_ref})
        spec_row = next(d for d in self.plan['drafts'] if d['kind']=='specification')
        action = {'id':'archive-old-spec','kind':'archive','source':copy.deepcopy(original_ref),
            'destination':{'root_id':'docs','path':'archive/old-spec.md','baseline_sha256':'NOT_EXISTS'},
            'expected_sha256':sha256(original),'source_after':'ABSENT',
            'superseded_by':{'root_id':'docs','path':spec_row['target'],'sha256':spec_row['expected_sha256']},
            'state':'PLANNED','reason':'Explicit fixture preservation action.',
            'receipt':{'root_id':'','path':'','sha256':''}}
        w['effects']['actions'] = [action]
        self.plan['folder_changes'] = [{'id':action['id'],'description':action['reason']}]
        stamp = datetime.now(timezone.utc).isoformat()
        w['decisions']['events'] = [{'id':'approval-event','action_id':action['id'],
            'state':'APPROVED','reference':'synthetic-fixture:actual-action-decision','observed_at':stamp}]
        w['decisions']['current'] = [{'action_id':action['id'],'state':'APPROVED','event_id':'approval-event'}]
        w['review'].update(status='NOT_RUN',reviewer_id='',revision='2',snapshot_sha256='',areas=[])
        for phase in w['phases']:
            if phase['id'] in (8,9):
                phase.update(status='PLANNED',evidence=[])
        self.save()
        self.assertTrue(gate.inspect_packet(self.project)['ready'])

        destination = self.project/action['destination']['path']
        destination.parent.mkdir()
        (code/'old-spec.md').replace(destination)
        receipt = {'schema_version':'open-project/effect-receipt/1.0','plan_id':self.plan['plan_id'],
            'executed_revision':'2','action_id':action['id'],'action_sha256':effect_identity(self.plan,action),
            'observed_at':stamp,'result':'COMPLETE','source_before_sha256':sha256(original),
            'destination_before_sha256':'NOT_EXISTS','destination_after_sha256':sha256(original),
            'source_after':'ABSENT','superseded_by':action['superseded_by']}
        evidence = self.project/'evidence/archive.json'
        evidence.parent.mkdir(exist_ok=True)
        evidence.write_text(json.dumps(receipt),encoding='utf-8')
        action.update(state='COMPLETE',receipt={'root_id':'docs','path':'evidence/archive.json',
                                               'sha256':sha256(evidence.read_bytes())})
        w['decisions']['events'].append({'id':'completed-event','action_id':action['id'],
            'state':'COMPLETED','reference':'synthetic-fixture:archive-receipt','observed_at':stamp})
        w['decisions']['current'] = [{'action_id':action['id'],'state':'COMPLETED','event_id':'completed-event'}]
        for phase in w['phases']:
            if phase['id'] in (8,9):
                phase.update(status='COMPLETE',evidence=['synthetic-fixture:final-phase'])
        w['review'] = old_review
        report_id = next(item['draft_id'] for item in w['documents'] if item['role']=='independent_review')
        report_draft = next(item for item in self.plan['drafts'] if item['id']==report_id)
        report_path = self.project/report_draft['path']
        report_draft['baseline_sha256'] = sha256((self.project/report_draft['target']).read_bytes())
        body = report_path.read_text(encoding='utf-8').split('\nStatus: ACCEPTED\n',1)[0]
        report_path.write_text(body+'\nStatus: NOT_RUN\nReviewer: not assigned\n',encoding='utf-8')
        report_draft['sha256'] = sha256(report_path.read_bytes())
        from plan_contract import expected_content
        report_draft['expected_sha256'] = sha256(expected_content(report_draft,report_path.read_bytes()))
        w['review'].update(revision='2',snapshot_sha256=workflow_snapshot_digest(self.plan,self.project))
        finalize_review_draft(self.plan,self.project)
        self.save()
        self.assertFalse(gate.inspect_packet(self.project,stage='completion')['complete'])
        self.assertEqual({key:self.plan['sources'][-1][key] for key in original_ref},original_ref)

        # Promotion retries also see the preserved historical evidence instead
        # of demanding a silent new source hash or recreation of the old file.
        approval = {'plan_id':self.plan['plan_id'],'revision':'2','packet_sha256':packet_digest(self.plan),
            'approved_by':'Synthetic current decision','approved_at':stamp,'actions':[]}
        for d in self.plan['drafts']:
            approval['actions'].append({'draft_id':d['id'],'target':d['target'],'draft_sha256':d['sha256'],
                'baseline_sha256':d['baseline_sha256'],'expected_sha256':d['expected_sha256'],
                'transforms':d['transforms'],'effects':['write_file']})
        approval_file = self.project.parent/'noop-approval.json'
        approval_file.write_text(json.dumps(approval),encoding='utf-8')
        self.assertEqual(promote.promote(self.project,approval_file,apply=True)['status'],'COMMITTED')
        result = gate.inspect_packet(self.project,stage='completion')
        self.assertTrue(result['complete'],result)
        self.assertEqual(promote.promote(self.project,approval_file,apply=True)['status'],'NO_OP')
        destination.write_bytes(b'drifted archive')
        self.assertFalse(gate.inspect_packet(self.project,stage='completion')['complete'])


if __name__ == '__main__':
    unittest.main()
