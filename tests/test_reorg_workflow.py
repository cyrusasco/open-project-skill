"""Reorg-M with actual normalized discovery over a generated global SQLite DB."""
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/open-project/scripts'
sys.path.insert(0,str(SCRIPTS))
from plan_contract import expected_content,packet_digest,sha256
from workflow_contract import REVIEW_AREAS,workflow_snapshot_digest
import plan_render
import promote
from support import save_packet
from workflow_support import make_workflow_packet,finalize_review_draft

def module(name,filename):
    spec = importlib.util.spec_from_file_location(name,SCRIPTS/filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

discovery = module('reorg_discovery','discover-sessions.py')
gate = module('reorg_gate','gate-check.py')


class ReorgWorkflowTests(unittest.TestCase):
    def test_global_sqlite_history_to_new_docs_and_finite_completion_preserves_old_code(self):
        with tempfile.TemporaryDirectory(prefix='reorg-workflow-',dir=ROOT) as temporary:
            base = Path(temporary)
            self.assertTrue(base.resolve().is_relative_to(ROOT.resolve()))
            docs,code,history = (base/name for name in ('new-docs','existing-code','global-history'))
            for path in (docs,code,history):
                path.mkdir()
            source_code = code/'app.py'
            source_code.write_bytes(b'print("Existing bridge source remains unchanged")\r\n')
            old_code = source_code.read_bytes()
            db = history/'synthetic-global.sqlite'
            with closing(sqlite3.connect(db)) as connection,connection:
                connection.executescript('''
                  CREATE TABLE session(id TEXT PRIMARY KEY,parent_id TEXT,title TEXT,directory TEXT);
                  CREATE TABLE message(id TEXT PRIMARY KEY,session_id TEXT,data TEXT);
                  CREATE TABLE part(id TEXT PRIMARY KEY,session_id TEXT,message_id TEXT,data TEXT);
                ''')
                for sid,parent,directory,role,text in (
                    ('opaque-main',None,'D:/unrelated-workspace','user','Needle Bridge needs an operating manual and source routing.'),
                    ('opaque-child','opaque-main','D:/another-project','assistant','Needle Bridge preserves its existing source and separates new governance.')):
                    connection.execute('INSERT INTO session VALUES(?,?,?,?)',(sid,parent,'unrelated title',directory))
                    connection.execute('INSERT INTO message VALUES(?,?,?)',('m:'+sid,sid,json.dumps({'role':role})))
                    connection.execute('INSERT INTO part VALUES(?,?,?,?)',('p:'+sid,sid,'m:'+sid,json.dumps({'type':'text','text':text})))
            original_db = sha256(db.read_bytes())
            # Invoke the real adapter. No hand-authored census/pagination data.
            report = discovery.discover(db,['Needle Bridge'],source_id='generated-global-zcode',batch_size=1)
            receipt = report['discovery_receipt']
            self.assertEqual(receipt['status'],'COMPLETE')
            self.assertEqual({hit['session_id'] for hit in report['hits']},{'opaque-main','opaque-child'})
            self.assertFalse(receipt['all_system_history_complete'])
            self.assertEqual(receipt['census']['session_rows']['scanned'],2)
            self.assertTrue(all(receipt['pagination']['end_reached'].values()))
            self.assertEqual(sha256(db.read_bytes()),original_db)

            plan = make_workflow_packet(docs,host='zcode',complete=False)
            plan.update(route='reorg',scale='M')
            w = plan['workflow']
            w['roots']['source_roots'] = [{'id':'code','path':str(code)},{'id':'history','path':str(history)}]
            plan['sources'].append({'id':'old-code','kind':'file','root_id':'code','path':'app.py',
                'sha256':sha256(old_code),'required':True,'depth':'full'})
            evidence = docs/'evidence'
            evidence.mkdir()
            receipt_path = evidence/'discovery-receipt.json'
            receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True),encoding='utf-8')
            receipt_ref = {'root_id':'docs','path':'evidence/discovery-receipt.json','sha256':sha256(receipt_path.read_bytes())}
            inventory = [{'id':row['source_id'],'kind':'zcode-sqlite','required':True,
                          'status':row['status'],'reference':str(db)} for row in receipt['source_inventory']]
            w['discovery'].update(status='COMPLETE',reason='All generated local source inventory supplied to this fixture was scanned.',
                inventory=inventory,queries=['Needle Bridge'],receipts=[receipt_ref],reads=[],
                limitations=['Generated supplied sources only; discovery is separate from reading and does not claim all real history.'])
            # Read visible history through a separate read-only connection; the
            # discovery adapter deliberately reported candidates as unread.
            with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as connection:
                connection.execute('PRAGMA query_only=ON')
                for sid in ('opaque-main','opaque-child'):
                    rows = connection.execute('SELECT m.id,m.data,p.data FROM message m JOIN part p ON p.message_id=m.id WHERE m.session_id=? ORDER BY m.id,p.id',(sid,)).fetchall()
                    captured = [{'message_id':mid,'role':json.loads(meta)['role'],'text':json.loads(part)['text']}
                                for mid,meta,part in rows if json.loads(part).get('type')=='text']
                    capture_path = evidence/(sid+'.json')
                    capture_path.write_text(json.dumps(captured,ensure_ascii=False),encoding='utf-8')
                    digest = sha256(capture_path.read_bytes())
                    source_id = 'read-'+sid
                    plan['sources'].append({'id':source_id,'kind':'session','required':True,'depth':'full',
                        'reference':'sqlite:generated-global-zcode#'+sid,'verified':True,'content_sha256':digest})
                    plan['requirements'][0]['source_ids'].append(source_id)
                    w['features'][0]['source_ids'].append(source_id)
                    w['discovery']['reads'].append({'source_id':source_id,'depth':'full',
                        'reference':'sqlite:generated-global-zcode#'+sid,'unit':'messages','total':len(captured),
                        'content_sha256':digest,'capture':{'root_id':'docs','path':'evidence/'+capture_path.name,'sha256':digest},
                        'ranges':[{'start':1,'end':len(captured)}]})

            def save():
                save_packet(docs,plan)
                plan_render.write_views(docs,plan)

            def approve(filename):
                value = {'plan_id':plan['plan_id'],'revision':plan['revision'],'packet_sha256':packet_digest(plan),
                    'approved_by':'Synthetic fixture decision for this exact revision',
                    'approved_at':datetime.now(timezone.utc).isoformat(),'actions':[]}
                for draft in plan['drafts']:
                    value['actions'].append({'draft_id':draft['id'],'target':draft['target'],
                        'draft_sha256':draft['sha256'],'baseline_sha256':draft['baseline_sha256'],
                        'expected_sha256':draft['expected_sha256'],'transforms':draft['transforms'],'effects':['write_file']})
                path = base/filename
                path.write_text(json.dumps(value),encoding='utf-8')
                return path

            save()
            ready = gate.inspect_packet(docs)
            self.assertTrue(ready['ready'],ready)
            initial_decision = approve('initial-approved-packet.json')
            self.assertEqual(promote.promote(docs,initial_decision)['status'],'DRY_RUN')
            self.assertEqual(promote.promote(docs,initial_decision,apply=True)['status'],'COMMITTED')
            self.assertEqual(promote.promote(docs,initial_decision,apply=True)['status'],'NO_OP')
            self.assertFalse(gate.inspect_packet(docs,stage='completion')['complete'])
            self.assertEqual(source_code.read_bytes(),old_code)

            # A fresh, not-yet-approved candidate preserves old journals while
            # obtaining a real fixture report before a new exact decision.
            plan['revision'] = '2'
            for draft in plan['drafts']:
                draft['baseline_sha256'] = sha256((docs/draft['target']).read_bytes())
            w['review'].update(status='NOT_RUN',reviewer_id='',revision='2',snapshot_sha256='',areas=[])
            for phase in w['phases']:
                if phase['id'] in (6,7):
                    phase['status'] = 'NOT_APPLICABLE'
            policy = w['evidence_policy']
            policy.update(authorized=True,approval_ref='synthetic-fixture:explicit-terminal-recording',
                paths=[],record_types=['review_receipt','terminal_state'],prefixes=[])
            for role in ('project_status','memory'):
                doc = next(item for item in w['documents'] if item['role']==role)
                draft = next(item for item in plan['drafts'] if item['id']==doc['draft_id'])
                raw = expected_content(draft,(docs/draft['path']).read_bytes())
                policy['paths'].append(draft['target'])
                policy['prefixes'].append({'path':draft['target'],'length':len(raw),'sha256':sha256(raw)})
            save()
            frozen = workflow_snapshot_digest(plan,docs)
            w['review'].update(status='ACCEPTED',reviewer_id='synthetic-independent-reorg-reviewer',snapshot_sha256=frozen,
                areas=[{'id':area,'status':'PASS','evidence':['synthetic-fixture:actual-discovery-receipt-and-captures'],
                    'reason':'Separate fixture review of bounded supplied source scope and actual candidate bytes.'} for area in REVIEW_AREAS])
            finalize_review_draft(plan,docs)
            save()
            self.assertTrue(gate.inspect_packet(docs)['ready'])
            final_decision = approve('final-approved-packet.json')
            self.assertEqual(promote.promote(docs,final_decision)['status'],'DRY_RUN')
            applied = promote.promote(docs,final_decision,apply=True)
            self.assertEqual(applied['status'],'COMMITTED',applied)
            self.assertEqual(promote.promote(docs,final_decision,apply=True)['status'],'NO_OP')
            records = [{'type':'review_receipt','reviewer_id':w['review']['reviewer_id'],
                        'reference':'REVIEW_REPORT.md','snapshot_sha256':frozen},
                       {'type':'terminal_state','value':'COMPLETE','reference':applied['journal']}]
            tail = ''.join(json.dumps(row)+'\n' for row in records).encode('utf-8')
            for path in policy['paths']:
                with (docs/path).open('ab') as stream:
                    stream.write(tail)
            for phase in w['phases']:
                if phase['id'] in (5,8,9):
                    phase.update(status='COMPLETE',evidence=[applied['journal']])
            self.assertEqual(workflow_snapshot_digest(plan,docs),frozen)
            save()
            complete = gate.inspect_packet(docs,stage='completion')
            self.assertTrue(complete['complete'],complete)
            self.assertEqual(source_code.read_bytes(),old_code)
            self.assertEqual({path.name for path in code.iterdir()},{'app.py'})
            self.assertEqual(sha256(db.read_bytes()),original_db)
            self.assertEqual(w['roots']['destination_mode'],'new_folder')
            self.assertEqual(w['gitnexus']['applicability'],'N/A')


if __name__=='__main__':
    unittest.main()
