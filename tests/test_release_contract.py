from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_builder', ROOT / 'scripts/build-plugin.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class ReleaseContractTests(unittest.TestCase):
    def test_native_host_bytes_are_preserved(self):
        baseline = json.loads((ROOT/'HOST-PROTECTION.json').read_text(encoding='utf-8'))
        self.assertEqual(baseline['edition'], json.loads((ROOT/'SOURCE.json').read_text())['edition'])
        for item in baseline['files']:
            with self.subTest(path=item['path']):
                raw = (ROOT/item['path']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
                self.assertEqual(len(raw), item['bytes'])

    def test_release_contract_and_resources_match(self):
        info, files = builder.source_files(ROOT)
        self.assertEqual(info['contract_version'], '2.0')
        self.assertEqual(info['plugin_version'], '0.2.0')
        self.assertIn('skills/open-project/scripts/workflow_contract.py', files)
        self.assertIn('skills/open-project/scripts/workflow_effects.py', files)
        self.assertIn('skills/open-project/scripts/workflow_package.py', files)
        self.assertIn('skills/open-project/templates/project-manual.template.md', files)
        if info['edition'] == 'zcode':
            self.assertEqual(info['gitnexus_applicability'], 'NOT_APPLICABLE')
            self.assertNotIn('skills/open-project/agents/openai.yaml', files)
        else:
            self.assertEqual(info['gitnexus_applicability'], 'CODEX_ONLY')
            self.assertIn('skills/open-project/references/gitnexus-onboarding.md', files)

    def test_missing_new_runtime_resources_cannot_package(self):
        for missing in ['scripts/workflow_contract.py', 'scripts/workflow_effects.py', 'scripts/workflow_package.py', 'templates/project-manual.template.md']:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                copy = Path(tmp)/'source'
                copy.mkdir()
                for name in ['LICENSE','VERSION','SOURCE.json','plugin.json','.zcode-plugin','.codex-plugin','commands','skills']:
                    source = ROOT/name
                    if source.is_dir():
                        shutil.copytree(source,copy/name,ignore=shutil.ignore_patterns('__pycache__'))
                    elif source.is_file():
                        shutil.copy2(source,copy/name)
                (copy/'skills/open-project'/missing).unlink()
                with self.assertRaisesRegex(ValueError,'Missing runtime resource'):
                    builder.build(copy,Path(tmp)/'package')

if __name__ == '__main__':
    unittest.main()
