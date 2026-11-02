"""Minimized synthetic incident replays; no private transcript or project bytes."""
from pathlib import Path
import copy
import importlib.util
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/open-project/scripts'
sys.path.insert(0,str(SCRIPTS))
from plan_contract import expected_content, sha256
import plan_render
from support import save_packet
from workflow_support import make_workflow_packet

spec=importlib.util.spec_from_file_location('incident_gate',SCRIPTS/'gate-check.py')
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class IncidentReplayTests(unittest.TestCase):
    def test_six_file_manifest_cannot_erase_four_core_obligations(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            project=Path(tmp)/'project'
            plan=make_workflow_packet(project)
            spec_row=copy.deepcopy(plan['drafts'][0])
            plan['drafts']=[spec_row]
            for n,name in enumerate(['README.md','HISTORY.md','ROADMAP.md','OPS-RUNBOOK.md','DECISIONS.md']):
                row=copy.deepcopy(spec_row)
                row.update(id=f'extra-{n}',kind='document',target=name,path=f'md-drafts/extra-{n}.DRAFT.md',
                           template='project_status.template.md')
                raw=('<!-- open-project:draft -->\n# '+name+'\n\nSynthetic incident content.\n').encode()
                (project/row['path']).write_bytes(raw)
                row['sha256']=sha256(raw)
                row['expected_sha256']=sha256(expected_content(row,raw))
                plan['drafts'].append(row)
            # Six real staged files and fresh hashes do not define completeness.
            self.assertEqual(len(plan['drafts']),6)
            result=gate.inspect_packet(project,plan)
            self.assertFalse(result['ready'],result)
            self.assertTrue(any('mandatory' in error or 'required draft' in error for error in result['errors']),result)

    def test_folder_exists_after_move_but_stale_packet_is_not_ready(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base=Path(tmp)
            old=base/'old-docs'
            new=base/'new-governance'
            plan=make_workflow_packet(old)
            save_packet(old,plan)
            plan_render.write_views(old,plan)
            self.assertTrue(gate.inspect_packet(old)['ready'])
            shutil.copytree(old,new)
            self.assertTrue(new.is_dir())
            result=gate.inspect_packet(new)
            self.assertFalse(result['ready'],result)
            self.assertTrue(any('root' in error or 'destination' in error for error in result['errors']),result)
            self.assertFalse(result['complete'])

if __name__=='__main__':
    unittest.main()
