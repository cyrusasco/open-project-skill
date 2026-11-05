import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/open-project/scripts'))
import gitnexus_onboard as g


class RealOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'plugin'
        self.state = Path(self.temp.name) / 'state'
        self.root.mkdir()
        self.write('plugin.json', json.dumps({'name': 'sample-plugin', 'version': '1.0.0'}))
        self.write('.agents/plugins/marketplace.json', json.dumps({'name': 'sample-market', 'plugins': [{'name': 'sample-plugin', 'source': {'source': 'local', 'path': './'}}]}))
        self.write('skills/sample/SKILL.md', '---\nname: sample\ndescription: Test\n---\nA skill.\n')
        self.write('skills/sample/scripts/math.py', 'def double(value):\n    return value * 2\n')
        self.write('skills/sample/scripts/main.py', 'from math import double\n\ndef run(value):\n    return double(value)\n')
        self.skill = Path(self.temp.name) / 'onboarding.md'
        self.skill.write_text('---\nname: gitnexus-project-onboarding\n---\n', encoding='utf-8')
        self.backend = {'root': str(Path(self.temp.name) / 'backend'), 'node': str(Path(self.temp.name) / 'node.exe')}

    def write(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding='utf-8')
        return p

    def plan(self):
        with patch.object(g, 'backend_identity', return_value=self.backend):
            return g.plan(self.root, self.state, 'sample-plugin', self.backend['root'], self.backend['node'], self.skill)

    def approval(self, p):
        return {'schema': 'open-project-real-approval/1', 'approved': True, 'admission_sha256': g.digest(p),
                'source_root': p['source']['root'], 'state_root': p['state_root'], 'project_id': p['project_id'],
                'effects': g.EFFECTS, 'request_ref': 'synthetic test authorization'}

    def run_result(self, p, generation, args):
        if args[0] == 'analyze':
            index = generation / 'snapshot/.gitnexus'
            index.mkdir()
            (index / 'lbug').write_bytes(b'synthetic database')
            (generation / 'registry').mkdir()
            (generation / 'registry/registry.json').write_text('[]')
            return {'exit_code': 0, 'reason': None, 'stdout': '', 'stderr': ''}
        q = next(q for q in p['oracle']['queries'] if q['query'] == args[1])
        return {'exit_code': 0, 'reason': None, 'stdout': json.dumps(q['rows']), 'stderr': ''}

    def test_oracle_from_actual_ast_lines_and_edges(self):
        p = self.plan()
        o = p['oracle']
        self.assertEqual(len(o['files']), 2)
        call = next(q for q in o['queries'] if q['kind'] == 'calls')['rows'][0]
        self.assertEqual((call['caller'], call['callerLine'], call['callee'], call['calleeLine']), ('run', 2, 'double', 0))
        self.assertFalse(self.state.exists())

    def test_source_and_state_cannot_overlap(self):
        self.state = self.root / 'state'
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.plan()

    def test_catalog_wrong_root_rejected(self):
        self.write('.agents/plugins/marketplace.json', json.dumps({'plugins': [{'name': 'sample-plugin', 'source': {'source': 'local', 'path': '../other'}}]}))
        with self.assertRaisesRegex(ValueError, 'exact source'):
            self.plan()

    def test_private_and_cache_files_excluded_before_read(self):
        self.write('skills/sample/secrets.json', 'not json; excluded')
        self.write('skills/sample/__pycache__/secret.pyc', 'excluded')
        p = self.plan()
        self.assertEqual(len(p['source']['excluded']), 2)
        self.assertFalse(any('secret' in f['path'] for f in p['source']['files']))

    def test_unsupported_language_not_silently_indexed(self):
        self.write('skills/sample/scripts/main.js', 'export const x=1;')
        with self.assertRaisesRegex(ValueError, 'unsupported resource'):
            self.plan()

    def test_duplicate_json_key_rejected(self):
        p = self.write('plugin.json', '{"name":"first","name":"second"}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            g.read_json(p)

    def test_changed_source_blocks_build_before_backend(self):
        p = self.plan()
        self.write('skills/sample/scripts/main.py', 'def changed():\n    return 1\n')
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend') as run:
            with self.assertRaises(ValueError):
                g.build(p, self.approval(p))
            run.assert_not_called()

    def test_wrong_approval_blocks_build(self):
        p = self.plan(); approval = self.approval(p); approval['state_root'] += '-other'
        with patch.object(g, 'run_backend') as run:
            with self.assertRaisesRegex(ValueError, 'approval'):
                g.build(p, approval)
            run.assert_not_called()

    def test_generation_build_verify_noop_stale_retire(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result) as run:
            ref = g.build(p, self.approval(p))
            self.assertFalse((self.state / 'current.json').exists())
            g.verify(self.state, ref)
            self.assertEqual(g.status(self.state)['status'], 'VERIFIED')
            n = run.call_count
            self.assertEqual(g.build(p, self.approval(p))['status'], 'NO_OP')
            self.assertEqual(run.call_count, n)
            self.write('skills/sample/scripts/math.py', 'def double(value):\n    return value * 3\n')
            self.assertEqual(g.status(self.state)['status'], 'STALE')
            self.assertEqual(g.rollback(self.state)['status'], 'RETIRED')
            self.assertTrue((self.root / 'skills/sample/scripts/math.py').is_file())
            self.assertTrue((self.state / 'generations' / ref['generation'] / 'receipt.json').is_file())

    def test_failed_build_does_not_activate(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', return_value={'exit_code': 1,'reason':None,'stdout':'','stderr':'failed'}):
            with self.assertRaisesRegex(ValueError, 'build failed'):
                g.build(p, self.approval(p))
        self.assertFalse((self.state / 'current.json').exists())
        self.assertFalse((self.state / 'staged.json').exists())

    def test_wrong_graph_cells_cannot_activate(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p))
            with patch.object(g, 'run_backend', return_value={'exit_code':0,'reason':None,'stdout':'[]','stderr':''}):
                with self.assertRaisesRegex(ValueError, 'verification failed'):
                    g.verify(self.state, ref)
        self.assertFalse((self.state / 'current.json').exists())

    def test_extra_snapshot_file_blocks_verify(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p))
            extra = self.state / 'generations' / ref['generation'] / 'snapshot/.gitnexusrc'
            extra.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'extra snapshot'):
                g.verify(self.state, ref)

    def test_tampered_receipt_is_not_fresh(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p)); g.verify(self.state, ref)
            path = self.state / 'generations' / ref['generation'] / 'receipt.json'
            data = json.loads(path.read_text()); data['owner'] = 'other'; path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'receipt hash'):
                g.status(self.state)

    def test_markdown_result_wrong_count_rejected(self):
        bad = {'row_count': 2, 'markdown': '| name |\n| --- |\n| double |'}
        with self.assertRaisesRegex(ValueError, 'header/count'):
            g.rows(json.dumps(bad), ['name'])

    def test_raw_rows_wrong_columns_rejected(self):
        with self.assertRaisesRegex(ValueError, 'row shape'):
            g.rows('[{"other":"double"}]', ['name'])

    def test_partial_graph_response_rejected(self):
        with self.assertRaisesRegex(ValueError, 'partial'):
            g.rows('{"partial":true,"row_count":0}', ['name'])

    def test_unresolved_cleanup_blocks_reuse(self):
        p = self.plan()
        g.state_owner(p, create=True)
        g.save(self.state / 'cleanup-unresolved.json', {'pid':123})
        with self.assertRaisesRegex(ValueError, 'cleanup'):
            g.state_owner(p)

    def test_changed_or_deleted_database_blocks_verified_status(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p)); g.verify(self.state, ref)
            db = self.state / 'generations' / ref['generation'] / 'snapshot/.gitnexus/lbug'
            db.write_bytes(b'changed database')
            with self.assertRaisesRegex(ValueError, 'index/registry changed'):
                g.status(self.state)
            db.unlink()
            with self.assertRaisesRegex(ValueError, 'database missing'):
                g.status(self.state)

    def test_changed_approval_blocks_verified_status(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p)); g.verify(self.state, ref)
            ap = self.state / 'generations' / ref['generation'] / 'approval.json'
            ap.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'approval evidence'):
                g.status(self.state)

    def test_nested_calls_not_attributed_to_outer_function(self):
        self.write('skills/sample/scripts/main.py', 'from math import double\n\ndef outer(value):\n    def inner():\n        return double(value)\n    return inner()\n')
        with self.assertRaisesRegex(ValueError, 'no supported cross-file'):
            self.plan()

    def test_native_catalog_wrong_source_cannot_complete(self):
        from types import SimpleNamespace
        codex = Path(self.temp.name) / 'codex.exe'; codex.touch()
        listings = [json.dumps({'marketplaces': [{'name':'sample-market','root':str(self.root)+'-wrong'}]}), json.dumps({'installed':[],'available':[]})]
        with patch.object(g.subprocess, 'run', side_effect=[SimpleNamespace(returncode=0,stdout=s.encode(),stderr=b'') for s in listings]):
            with self.assertRaisesRegex(ValueError, 'marketplace source mismatch'):
                g.catalog(self.root, codex)

    def test_catalog_separates_current_source_from_old_install(self):
        from types import SimpleNamespace
        codex = Path(self.temp.name) / 'codex.exe'; codex.touch()
        listings = [json.dumps({'marketplaces': [{'name':'sample-market','root':str(self.root)}]}),
                    json.dumps({'installed':[{'name':'sample-plugin','version':'0.9.0','installed':True,'source':{'source':'local','path':str(self.root)}}],'available':[]})]
        with patch.object(g.subprocess, 'run', side_effect=[SimpleNamespace(returncode=0,stdout=s.encode(),stderr=b'') for s in listings]):
            result = g.catalog(self.root, codex)
        self.assertEqual(result['status'], 'VERIFIED')
        self.assertFalse(result['installation_current'])
        self.assertEqual(result['skills'][0]['id'], 'sample')

    def test_build_cache_not_confused_with_closed_graph_identity(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p)); g.verify(self.state, ref)
            generation = self.state / 'generations' / ref['generation']
            cache = generation / 'snapshot/.gitnexus/parsedfile-cache'
            cache.mkdir(); (cache / 'worker-build-cache').write_text('not a query input')
            self.assertEqual(g.status(self.state)['status'], 'VERIFIED')

    def test_malformed_lookup_retains_failure_receipt(self):
        p = self.plan()
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p)); g.verify(self.state, ref)
            with patch.object(g, 'run_backend', return_value={'exit_code':0,'reason':None,'stdout':'not-json','stderr':''}):
                with self.assertRaisesRegex(ValueError, 'lookup failed'):
                    g.lookup(self.state, 'double')
            files = list((self.state / 'generations' / ref['generation']).glob('lookup-*.json'))
            self.assertEqual(len(files), 1)
            self.assertEqual(json.loads(files[0].read_text())['status'], 'FAILED')

    def test_mixed_skill_catalog_does_not_claim_markdown_graph(self):
        self.write('skills/docs/SKILL.md', '---\nname: docs\ndescription: Metadata only\n---\nText')
        p = self.plan()
        meta = {'status':'VERIFIED','source_sha256':p['source']['sha256'], 'plugin':{'id':'sample-plugin'},
                'skills':[{'id':s['id'],'path':s['path'],'source_root':str(self.root / Path(s['path']).parent)} for s in p['source']['skills']]}
        with patch.object(g, 'backend_identity', return_value=self.backend), patch.object(g, 'run_backend', side_effect=self.run_result):
            ref = g.build(p, self.approval(p)); g.verify(self.state, ref)
            with patch.object(g, 'catalog', return_value=meta):
                complete = g.complete(self.state, 'unused-test-cli')
            docs = next(a for a in complete['artifacts'] if a['id'] == 'docs')
            self.assertEqual(docs['graph_status'], 'NOT_APPLICABLE')
            self.assertEqual(docs['catalog_status'], 'VERIFIED')


if __name__ == '__main__':
    unittest.main()
