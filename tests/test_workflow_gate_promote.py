"""Candidate review/approval/promotion/terminal closure without precompleted fixtures.

Reviewer and decision identities below are explicit synthetic role records.
These tests verify sequencing and bytes, not human identity or real host effects.
"""
from datetime import datetime, timezone
import base64
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
from plan_contract import PacketError, expected_content, packet_digest, sha256
from workflow_contract import REVIEW_AREAS, workflow_snapshot_digest
import plan_render
import promote
from support import save_packet
from workflow_support import make_workflow_packet, finalize_review_draft

spec = importlib.util.spec_from_file_location('sequence_gate',SCRIPTS/'gate-check.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReviewPromotionSequenceTests(unittest.TestCase):
    def test_unapproved_candidate_is_reviewed_then_exactly_approved_and_completed(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            base = Path(temporary)
            self.assertTrue(base.resolve().is_relative_to(ROOT.resolve()))
            project = base/'project'
            project.mkdir()
            plan = make_workflow_packet(project,complete=False)

            def save():
                save_packet(project,plan)
                plan_render.write_views(project,plan)

            def decision(path):
                stamp = datetime.now(timezone.utc).isoformat()
                value = {'plan_id':plan['plan_id'],'revision':plan['revision'],
                    'packet_sha256':packet_digest(plan),'approved_by':'Synthetic actual fixture decision',
                    'approved_at':stamp,'actions':[]}
                for draft in plan['drafts']:
                    value['actions'].append({'draft_id':draft['id'],'target':draft['target'],
                        'draft_sha256':draft['sha256'],'baseline_sha256':draft['baseline_sha256'],
                        'expected_sha256':draft['expected_sha256'],'transforms':draft['transforms'],
                        'effects':['write_file']})
                path.write_text(json.dumps(value),encoding='utf-8')
                return value

            save()
            self.assertEqual(plan['workflow']['review']['status'],'NOT_RUN')
            self.assertTrue(gate.inspect_packet(project)['ready'])
            self.assertFalse(gate.inspect_packet(project,stage='completion')['complete'])
            old_decision = base/'decision-v1.json'
            decision(old_decision)

            # Reserve a fresh, explicitly unapproved candidate before doing its
            # review. Do not mutate/reapprove the old decision in place.
            plan['revision'] = '2'
            draft = plan['drafts'][0]
            path = project/draft['path']
            raw = path.read_bytes()+b'\n## Candidate change\n\nBounded revision two acceptance detail.\n'
            path.write_bytes(raw)
            draft['sha256'] = sha256(raw)
            draft['expected_sha256'] = sha256(expected_content(draft,raw))
            w = plan['workflow']
            w['review'].update(status='NOT_RUN',reviewer_id='',revision='2',snapshot_sha256='',areas=[])
            policy = w['evidence_policy']
            policy.update(authorized=True,approval_ref='synthetic-fixture:explicit-terminal-evidence-authority',
                          paths=[],record_types=['review_receipt','command_exit','terminal_state'],prefixes=[])
            for role in ('project_status','memory'):
                doc = next(item for item in w['documents'] if item['role']==role)
                item = next(item for item in plan['drafts'] if item['id']==doc['draft_id'])
                output = expected_content(item,(project/item['path']).read_bytes())
                policy['paths'].append(item['target'])
                policy['prefixes'].append({'path':item['target'],'length':len(output),'sha256':sha256(output)})
            for phase in w['phases']:
                if phase['id'] in (6,7):
                    phase['status'] = 'NOT_APPLICABLE'
            save()
            self.assertFalse(any((project/item['target']).exists() for item in plan['drafts']))
            self.assertTrue(gate.inspect_packet(project)['ready'])
            before = {p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()}
            with self.assertRaises(PacketError):
                promote.promote(project,old_decision,apply=True)
            self.assertEqual(before,{p.relative_to(project).as_posix():p.read_bytes() for p in project.rglob('*') if p.is_file()})

            # The fixture reviewer reads the fresh candidate's actual bytes and
            # records its snapshot after the candidate exists, before approval.
            frozen = workflow_snapshot_digest(plan,project)
            read_hashes = {item['id']:sha256((project/item['path']).read_bytes()) for item in plan['drafts']}
            self.assertTrue(all(read_hashes[item['id']]==item['sha256'] for item in plan['drafts']))
            w['review'].update(status='ACCEPTED',reviewer_id='synthetic-independent-fixture-reviewer',
                snapshot_sha256=frozen,areas=[{'id':area,'status':'PASS',
                    'evidence':['synthetic-fixture:read-current-candidate-bytes'],
                    'reason':'Separate fixture reviewer result for this exact candidate.'} for area in REVIEW_AREAS])
            finalize_review_draft(plan,project)
            self.assertEqual(workflow_snapshot_digest(plan,project),frozen)
            review_doc = next(item for item in w['documents'] if item['role']=='independent_review')
            review_draft = next(item for item in plan['drafts'] if item['id']==review_doc['draft_id'])
            report = (project/review_draft['path']).read_text(encoding='utf-8')
            self.assertIn('Status: ACCEPTED',report)
            self.assertIn(frozen,report)
            self.assertFalse((project/review_draft['target']).exists())
            for phase in w['phases']:
                if phase['id']==8:
                    phase.update(status='COMPLETE',evidence=['synthetic-fixture:review-report-created'])
            save()
            self.assertTrue(gate.inspect_packet(project)['ready'])
            new_decision = base/'decision-v2.json'
            approved = decision(new_decision)
            approved_raw = (project/'md-drafts/plan-data.json').read_bytes()
            dry_run = promote.promote(project,new_decision)
            self.assertEqual(dry_run['status'],'DRY_RUN')
            applied = promote.promote(project,new_decision,apply=True)
            self.assertEqual(applied['status'],'COMMITTED',applied)
            self.assertFalse(applied['workflow_complete'])
            original_journal = (project/applied['journal']).read_bytes()
            journal = json.loads(original_journal)
            self.assertEqual(journal['version'],2)
            self.assertEqual(base64.b64decode(journal['approved_packet_raw_base64']),approved_raw)
            self.assertEqual(journal['approved_packet_raw_sha256'],sha256(approved_raw))
            self.assertEqual(packet_digest(journal['approved_packet']),approved['packet_sha256'])
            self.assertEqual(journal['material_snapshot_sha256'],frozen)
            self.assertFalse(gate.inspect_packet(project,stage='completion')['complete'])

            # Only preauthorized typed terminal receipts follow promotion. The
            # frozen body/prefix, review report and stable outputs stay intact.
            stamp = datetime.now(timezone.utc).isoformat()
            records = [{'type':'review_receipt','reviewer_id':w['review']['reviewer_id'],
                        'reference':review_draft['target'],'snapshot_sha256':frozen},
                       {'type':'command_exit','command':'synthetic-fixture:promote --apply',
                        'exit_code':0,'observed_at':stamp},
                       {'type':'terminal_state','value':'COMPLETE','reference':applied['journal']}]
            tail = ''.join(json.dumps(record)+'\n' for record in records).encode('utf-8')
            for relative in policy['paths']:
                with (project/relative).open('ab') as stream:
                    stream.write(tail)
            for phase in w['phases']:
                if phase['id'] in (5,9):
                    phase.update(status='COMPLETE',evidence=[applied['journal']])
            self.assertEqual(workflow_snapshot_digest(plan,project),frozen)
            save()
            result = gate.inspect_packet(project,stage='completion')
            self.assertTrue(result['complete'],result)
            self.assertEqual(result['completion_receipt']['snapshot_sha256'],frozen)
            self.assertEqual(result['completion_receipt']['approved_packet_sha256'],approved['packet_sha256'])
            self.assertNotEqual(result['completion_receipt']['observation_packet_sha256'],approved['packet_sha256'])
            self.assertIn(applied['journal'],result['completion_receipt']['promotion_refs'])
            self.assertEqual(json.loads(new_decision.read_text(encoding='utf-8')),approved)
            self.assertEqual((project/applied['journal']).read_bytes(),original_journal)
            with self.assertRaises(PacketError):
                promote.promote(project,new_decision,apply=True)
            self.assertEqual((project/review_draft['target']).read_bytes(),expected_content(review_draft,(project/review_draft['path']).read_bytes()))


if __name__=='__main__':
    unittest.main()
