"""Contract and readiness regressions using fully synthetic project packets."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/open-project/scripts'
sys.path.insert(0,str(SCRIPTS))
from plan_contract import (PacketError,DRAFT_MARKER,validate_plan,load_plan,packet_digest,
    sha256,read_draft,expected_content,resolve_inside,schema_document)
import plan_render
from support import make_packet,save_packet,gitnexus_plan_row
spec = importlib.util.spec_from_file_location('packet_gate',SCRIPTS/'gate-check.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class ContractGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)/'project'
        self.project.mkdir()
        self.plan = make_packet(self.project)

    def ready(self):
        save_packet(self.project,self.plan)
        plan_render.write_views(self.project,self.plan)
        return gate.inspect_packet(self.project)

    def replace_draft(self,raw,index=0):
        draft = self.plan['drafts'][index]
        path = self.project/draft['path']
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
        draft['sha256'] = sha256(raw)
        draft['expected_sha256'] = sha256(expected_content(draft,raw))
        return draft

    def add_agent(self,raw,host='zcode'):
        self.plan['host'] = host
        if host == 'codex':
            self.plan['tools'].append(gitnexus_plan_row())
        draft = {'id':'agent','path':'md-drafts/agents/worker.DRAFT.md',
            'target':'.zcode/agents/worker.md' if host=='zcode' else '.codex/agents/worker.toml',
            'template':'agent.template.md','kind':host+'-agent','required':True,
            'sha256':'0'*64,'baseline_sha256':'NOT_EXISTS','expected_sha256':'0'*64,
            'transforms':['normalize_utf8_lf']}
        self.plan['drafts'].append(draft)
        self.replace_draft(raw,1)
        return draft

    def test_valid_minimal_packet_and_schema_are_consistent(self):
        result = self.ready()
        self.assertTrue(result['ready'],result)
        self.assertEqual(result['errors'],[])
        self.assertEqual(result['packet_sha256'],packet_digest(self.plan))
        self.assertEqual(load_plan(self.project),self.plan)
        schema = json.loads((ROOT/'skills/open-project/schemas/plan.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(schema,schema_document())

    def test_missing_every_mandatory_field_is_rejected(self):
        for field in list(self.plan):
            if field in ('code_map','timeline','approval_requests'):
                continue
            with self.subTest(field=field):
                value = copy.deepcopy(self.plan)
                del value[field]
                with self.assertRaises(PacketError):
                    validate_plan(value)

    def test_invalid_types_unknown_fields_and_nonfinite_values(self):
        mutations = [lambda p:p.update(revision=1),lambda p:p.update(revision='0'),
            lambda p:p.update(host='other'),lambda p:p.update(project=[]),
            lambda p:p.update(facts={}),lambda p:p.update(facts=[0]),
            lambda p:p.update(unsupported=True),lambda p:p['drafts'][0].update(required=1),
            lambda p:p['drafts'][0].update(sha256='f'*63),
            lambda p:p['drafts'][0].update(transforms=['repair_model']),
            lambda p:p['drafts'][0].update(surprise='x'),
            lambda p:p.update(facts=[{'value':float('nan')}]),
            lambda p:p.update(facts=[{'value':float('inf')}]),
            lambda p:p.update(facts=[{'value':'\ud800'}])]
        for mutate in mutations:
            value = copy.deepcopy(self.plan)
            mutate(value)
            with self.subTest(packet=value):
                with self.assertRaises(PacketError):
                    validate_plan(value)

    def test_required_specification_cannot_be_removed_optional_or_renamed(self):
        for change in ({'required':False},{'kind':'document'},{'target':'other.md'}):
            value = copy.deepcopy(self.plan)
            value['drafts'][0].update(change)
            with self.assertRaises(PacketError):
                validate_plan(value)

    def test_draft_dependencies_are_known_unique_and_acyclic(self):
        for deps in (['missing'],['spec'],['spec','spec']):
            value = copy.deepcopy(self.plan)
            value['drafts'][0]['depends_on'] = deps
            with self.assertRaises(PacketError):
                validate_plan(value)
        duplicate = copy.deepcopy(self.plan['drafts'][0])
        self.plan['drafts'].append(duplicate)
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_no_arbitrary_array_or_graph_quotas(self):
        self.plan['requirements'] = [{'id':str(n),'description':'requirement'} for n in range(1500)]
        self.plan['graph'] = {'nodes':[{'id':str(n)} for n in range(35)],'links':[]}
        validate_plan(self.plan)
        self.assertTrue(self.ready()['ready'])

    def test_traversal_absolute_ads_reserved_and_control_paths(self):
        for value in ('../x.md','/x.md','C:/x.md','C:x.md','a\\x.md','a/../x.md','a//x.md',
                      'a/./x.md','a/NUL.txt','a/COM¹.txt','a/CONIN$','a/x:secret','a/x.','a/x '):
            with self.subTest(path=value):
                with self.assertRaises(PacketError):
                    resolve_inside(self.project,value)
        for value in ('md-drafts/plan-data.json','.git/config','.open-project-promotion/journal.json'):
            self.plan['drafts'][0]['target'] = value
            with self.assertRaises(PacketError):
                validate_plan(self.plan)

    def test_generated_views_cannot_be_manifest_drafts(self):
        for value in ('md-drafts/PLAN.DRAFT.md','md-drafts/PLAN-REPORT.DRAFT.html','md-drafts/plan-data.json'):
            self.plan['drafts'][0]['path'] = value
            with self.assertRaises(PacketError):
                validate_plan(self.plan)

    def test_parent_target_collision_rejected(self):
        draft = copy.deepcopy(self.plan['drafts'][0])
        draft.update(id='nested',path='md-drafts/nested.DRAFT.md',target='product_specification.md/other.md',kind='document')
        self.plan['drafts'].append(draft)
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_reparse_components_rejected_before_resolve(self):
        path = self.project/'md-drafts'
        original = Path.lstat
        def inspected(location,*args,**kwargs):
            if location == path:
                return type('Attrs',(),{'st_mode':stat.S_IFDIR,'st_file_attributes':0x400})()
            return original(location,*args,**kwargs)
        with mock.patch.object(Path,'lstat',inspected):
            with self.assertRaises(PacketError):
                resolve_inside(self.project,'md-drafts/plan-data.json')

    def test_transforms_are_exact_and_self_checking(self):
        draft = self.plan['drafts'][0]
        raw = (DRAFT_MARKER+'\r\nA\r\nB\r').encode('utf-8')
        self.assertEqual(expected_content(draft,raw),b'A\nB\n')
        with self.assertRaises(PacketError):
            expected_content(draft,b'A\n')
        with self.assertRaises(PacketError):
            expected_content(draft,('prefix\n'+DRAFT_MARKER+'\nA').encode('utf-8'))
        draft['transforms'] = ['normalize_utf8_lf']
        self.assertEqual(expected_content(draft,b'A\r\n'),b'A\n')
        self.assertEqual(expected_content(draft,b'\xef\xbb\xbfA\r\n'),b'A\n')

    def test_required_specification_cannot_be_blank(self):
        self.replace_draft((DRAFT_MARKER+'\n \n').encode('utf-8'))
        result = self.ready()
        self.assertFalse(result['ready'])
        self.assertTrue(any('no content' in e for e in result['errors']))

    def test_missing_json_never_falls_back_to_legacy_plan(self):
        (self.project/'md-drafts/PLAN.DRAFT.md').write_text('# Legacy\n',encoding='utf-8')
        result = gate.inspect_packet(self.project)
        self.assertFalse(result['ready'])
        self.assertTrue(result['errors'])

    def test_duplicate_json_keys_and_nan_are_rejected(self):
        path = self.project/'md-drafts/plan-data.json'
        for raw in ('{"a":1,"a":2}','{"value":NaN}','{"value":Infinity}'):
            path.write_text(raw,encoding='utf-8')
            with self.assertRaises(PacketError):
                load_plan(self.project)

    def test_draft_bytes_and_expected_hash_must_match(self):
        self.ready()
        draft = self.plan['drafts'][0]
        (self.project/draft['path']).write_bytes(b'changed')
        self.assertFalse(gate.inspect_packet(self.project)['ready'])
        with self.assertRaises(PacketError):
            read_draft(self.project,draft)
        self.plan['drafts'][0]['expected_sha256'] = 'f'*64
        self.replace_draft((DRAFT_MARKER+'\nRestored\n').encode('utf-8'))
        self.plan['drafts'][0]['expected_sha256'] = 'f'*64
        save_packet(self.project,self.plan)
        result = gate.inspect_packet(self.project)
        self.assertFalse(result['ready'])
        self.assertTrue(any('expected content hash mismatch' in e for e in result['errors']))

    def test_both_views_are_required_and_mtime_cannot_make_stale_views_valid(self):
        self.ready()
        for relative in ('md-drafts/PLAN.DRAFT.md','md-drafts/PLAN-REPORT.DRAFT.html'):
            path = self.project/relative
            original = path.read_bytes()
            path.write_bytes(original+b'changed')
            os.utime(path,None)
            result = gate.inspect_packet(self.project)
            self.assertFalse(result['ready'])
            self.assertTrue(any('differs' in e for e in result['errors']))
            path.write_bytes(original)
            path.unlink()
            self.assertFalse(gate.inspect_packet(self.project)['ready'])
            path.write_bytes(original)
        self.assertTrue(gate.inspect_packet(self.project)['ready'])

    def test_required_file_source_hash_and_missing_source_fail(self):
        path = self.project/'evidence.txt'
        path.write_bytes(b'captured evidence')
        self.plan['sources'] = [{'id':'file','kind':'file','path':'evidence.txt','sha256':sha256(path.read_bytes()),'required':True}]
        self.assertTrue(self.ready()['ready'])
        path.write_bytes(b'changed')
        result = gate.inspect_packet(self.project)
        self.assertFalse(result['ready'])
        self.assertTrue(any('source hash mismatch' in e for e in result['errors']))
        path.unlink()
        self.assertFalse(gate.inspect_packet(self.project)['ready'])

    def test_external_sources_are_explicit_and_not_pretend_files(self):
        for kind in ('session','url','tool'):
            self.plan['sources'] = [{'id':'external','kind':kind,'reference':'captured record','verified':True,'required':True}]
            self.assertTrue(self.ready()['ready'])
        self.plan['sources'][0]['verified'] = False
        self.assertFalse(self.ready()['ready'])
        self.plan['sources'][0]['required'] = False
        result = self.ready()
        self.assertTrue(result['ready'])
        self.assertTrue(result['warnings'])
        self.plan['sources'] = [{'id':'unknown','kind':'unknown','verified':True,'reference':'unresolved'}]
        self.assertFalse(self.ready()['ready'])

    def test_source_equal_promoted_target_allows_only_exact_expected_evidence(self):
        draft = self.plan['drafts'][0]
        path = self.project/draft['target']
        path.write_bytes(b'baseline\n')
        baseline = sha256(path.read_bytes())
        draft['baseline_sha256'] = baseline
        self.plan['sources'] = [{'id':'baseline','kind':'file','path':draft['target'],'sha256':baseline}]
        self.assertTrue(self.ready()['ready'])
        path.write_bytes(expected_content(draft,(self.project/draft['path']).read_bytes()))
        result = gate.inspect_packet(self.project)
        self.assertTrue(result['ready'])
        self.assertTrue(any('pre-promotion' in w for w in result['warnings']))
        self.plan['sources'][0]['sha256'] = 'e'*64
        self.assertFalse(gate.inspect_packet(self.project,self.plan)['ready'])

    @unittest.skipUnless(os.name == 'nt','Windows case-insensitive path composition')
    def test_windows_case_variant_source_equal_promoted_target_remains_ready(self):
        draft = self.plan['drafts'][0]
        target = self.project/draft['target']
        target.write_bytes(b'baseline\n')
        baseline = sha256(target.read_bytes())
        draft['baseline_sha256'] = baseline
        self.plan['sources'] = [{'id':'baseline','kind':'file','path':draft['target'].upper(),'sha256':baseline}]
        self.assertTrue(self.ready()['ready'])
        target.write_bytes(expected_content(draft,(self.project/draft['path']).read_bytes()))
        result = gate.inspect_packet(self.project)
        self.assertTrue(result['ready'],result)
        self.assertTrue(any('pre-promotion' in warning for warning in result['warnings']))
        self.plan['sources'][0]['sha256'] = 'e'*64
        self.assertFalse(gate.inspect_packet(self.project,self.plan)['ready'])

    def test_zcode_agent_positive_control_without_tools_heuristic(self):
        self.add_agent(b'---\nname: worker\ndescription: "work # safely"\nmodel: "provider/model" # literal\n---\nInstructions\n')
        self.assertTrue(self.ready()['ready'])

    def test_zcode_missing_empty_inherit_and_placeholder_models_fail(self):
        samples = ('','model:\n','model: # next line must not be consumed\n',
            'model: inherit\n','model: "inherit" # comment\n',"model: 'inherit' # comment\n",
            'model: <provider/model>\n','model: ""\n',"model: ''\n",'model: null\n',
            'model: true\n','model: 0\n','model: 0x10\n','model: a: b\n')
        for field in samples:
            with self.subTest(model=field):
                self.plan['drafts'] = self.plan['drafts'][:1]
                raw = ('---\nname: worker\n'+field+'description: instructions\n---\nBody\n').encode('utf-8')
                self.add_agent(raw)
                result = self.ready()
                self.assertFalse(result['ready'])
                self.assertTrue(any('G3' in e for e in result['errors']))

    def test_zcode_native_frontmatter_must_start_line_one(self):
        self.add_agent(b'<!-- open-project:draft -->\n---\nmodel: provider/model\n---\nBody\n')
        self.assertFalse(self.ready()['ready'])
        self.plan['drafts'][1]['transforms'].append('remove_draft_marker')
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_document_with_tools_is_not_misclassified_as_agent(self):
        raw = b'---\ntools: [Read]\n---\nOrdinary specification\n'
        self.plan['drafts'][0]['transforms'] = ['normalize_utf8_lf']
        self.replace_draft(raw)
        self.assertTrue(self.ready()['ready'])

    def test_zcode_import_and_gate_work_without_tomllib(self):
        self.add_agent(b'---\nmodel: provider/model\n---\nInstructions\n')
        self.ready()
        with mock.patch.dict(sys.modules,{'tomllib':None}):
            isolated_spec = importlib.util.spec_from_file_location('gate_without_tomllib',SCRIPTS/'gate-check.py')
            isolated_gate = importlib.util.module_from_spec(isolated_spec)
            isolated_spec.loader.exec_module(isolated_gate)
            result = isolated_gate.inspect_packet(self.project)
            self.assertTrue(result['ready'],result)
        self.plan['drafts'] = self.plan['drafts'][:1]
        self.add_agent(b'name = "worker"\ndescription = "work"\ndeveloper_instructions = "Instructions"\n',host='codex')
        self.ready()
        with mock.patch.dict(sys.modules,{'tomllib':None}):
            result = isolated_gate.inspect_packet(self.project)
            self.assertFalse(result['ready'])
            self.assertTrue(any('requires Python 3.11' in error for error in result['errors']))

    def test_codex_native_toml_requires_fields_but_model_is_optional(self):
        self.add_agent(b'name = "worker"\ndescription = "work"\ndeveloper_instructions = "Instructions"\n',host='codex')
        self.assertTrue(self.ready()['ready'])
        for raw in (b'name = "worker"\ndescription = "work"\n',b'---\nmodel: provider/model\n---\nBody\n',b'name = 1\ndescription = "work"\ndeveloper_instructions = "body"\n'):
            self.replace_draft(raw,1)
            self.assertFalse(self.ready()['ready'])

    def test_host_kind_mismatch_is_schema_error(self):
        self.add_agent(b'---\nmodel: provider/model\n---\nBody\n')
        self.plan['host'] = 'codex'
        with self.assertRaises(PacketError):
            validate_plan(self.plan)

    def test_g5_unicode_nested_links_and_frozen_archive_basename(self):
        self.plan['drafts'][0]['target'] = 'docs/product_specification.md'
        nested = self.project/'docs/資料'
        nested.mkdir(parents=True)
        (nested/'需求.md').write_text('evidence',encoding='utf-8')
        (self.project/'archive').mkdir()
        (self.project/'archive/FROZEN.md').write_text('archive',encoding='utf-8')
        raw = (DRAFT_MARKER+'\n[需求](資料/需求.md)\n[planned](product_specification.md)\n[Frozen](FROZEN.md)\n[web](https://example.invalid/missing.md)\n').encode('utf-8')
        self.replace_draft(raw)
        result = self.ready()
        self.assertTrue(result['ready'])
        self.assertEqual(len(result['warnings']),1,result)
        self.assertIn('FROZEN.md',result['warnings'][0])
        self.assertNotIn('需求.md',result['warnings'][0])

    def test_malformed_markdown_url_warns_without_crash_or_url_disclosure(self):
        self.replace_draft((DRAFT_MARKER+'\n[broken](http://[)\n').encode('utf-8'))
        result = self.ready()
        self.assertTrue(result['ready'],result)
        self.assertTrue(any('malformed Markdown reference' in warning for warning in result['warnings']))
        self.assertTrue(all('http://' not in warning for warning in result['warnings']))
        process = subprocess.run([sys.executable,str(SCRIPTS/'gate-check.py'),str(self.project),'--strict','--json'],
                                 capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertTrue(json.loads(process.stdout)['ready'])
        self.assertNotIn('Traceback',process.stderr)

    def test_advisory_cli_is_zero_but_not_ready_and_strict_fails(self):
        script = SCRIPTS/'gate-check.py'
        before = sorted(p.relative_to(self.project).as_posix() for p in self.project.rglob('*'))
        for strict in (False,True):
            args = [sys.executable,str(script),str(self.project),'--json'] + (['--strict'] if strict else [])
            process = subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(process.returncode,1 if strict else 0,process.stderr)
            result = json.loads(process.stdout)
            self.assertFalse(result['ready'])
            self.assertTrue(result['errors'])
        after = sorted(p.relative_to(self.project).as_posix() for p in self.project.rglob('*'))
        self.assertEqual(before,after)

if __name__ == '__main__':
    unittest.main()
