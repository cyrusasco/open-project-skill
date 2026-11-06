"""Native install flow tested with a disposable CLI double; no real home writes."""
import json
import os
from pathlib import Path
import shutil
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which('pwsh')


@unittest.skipUnless(PWSH, 'PowerShell 7 is required for the native installer tests')
class InstallPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / 'source with spaces'
        self.source.mkdir()
        for rel in ['LICENSE', 'VERSION', 'SOURCE.json', 'plugin.json', 'skills', '.agents', 'scripts']:
            original = ROOT / rel
            target = self.source / rel
            if original.is_dir():
                shutil.copytree(original, target, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                shutil.copy2(original, target)
        self.log = self.work / 'calls.jsonl'
        self.config = self.work / 'scenario.json'
        self.stub = self.work / 'codex-double.ps1'
        self.stub.write_text(r'''$ErrorActionPreference = 'Stop'
$scenario = Get-Content -LiteralPath $env:INSTALL_TEST_SCENARIO -Raw | ConvertFrom-Json
ConvertTo-Json -InputObject @($args) -Compress | Add-Content -LiteralPath $env:INSTALL_TEST_LOG -Encoding utf8
if (($args[0..2] -join ' ') -eq 'plugin marketplace list') {
    @{marketplaces=$scenario.marketplaces} | ConvertTo-Json -Depth 10 -Compress
    exit 0
}
if (($args[0..2] -join ' ') -eq 'plugin marketplace add') {
    if ($scenario.deny_registration) { [Console]::Error.WriteLine('Access is denied'); exit 5 }
    @{status='REGISTERED'} | ConvertTo-Json -Compress
    exit 0
}
if (($args[0..1] -join ' ') -eq 'plugin add') {
    if ($scenario.deny_installation) { [Console]::Error.WriteLine('Installation denied'); exit 5 }
    @{status='INSTALLED'} | ConvertTo-Json -Compress
    exit 0
}
if (($args[0..1] -join ' ') -eq 'plugin list') {
    @{installed=$scenario.installed;available=@()} | ConvertTo-Json -Depth 10 -Compress
    exit 0
}
throw 'Unexpected native call'
''', encoding='utf-8')
        version = json.loads((self.source / 'plugin.json').read_text(encoding='utf-8'))['version']
        self.scenario = {'marketplaces': [], 'deny_registration': False, 'deny_installation': False,
                         'installed': [{'pluginId': 'open-project-codex@open-project-codex',
                                        'name': 'open-project-codex', 'marketplaceName': 'open-project-codex',
                                        'version': version, 'installed': True, 'enabled': True,
                                        'source': {'source': 'local', 'path': str(self.source)}}]}

    def run_installer(self, *, with_bypass=False, seed_cache=True):
        self.config.write_text(json.dumps(self.scenario), encoding='utf-8')
        env = os.environ.copy()
        env.update(INSTALL_TEST_SCENARIO=str(self.config), INSTALL_TEST_LOG=str(self.log))
        if with_bypass:
            host = self.work / 'host'
            host.mkdir(exist_ok=True)
            env['CODEX_HOME'] = str(host)
            if seed_cache:
                info, resources = runpy.run_path(str(self.source/'scripts/build-plugin.py'))['source_files'](self.source)
                cache = host/'plugins/cache/open-project-codex/open-project-codex'/info['plugin_version']
                for rel, raw in resources.items():
                    target = cache/rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
        entry = 'install-with-jev-bypass.ps1' if with_bypass else 'install-plugin.ps1'
        result = subprocess.run([PWSH, '-NoLogo', '-NoProfile', '-File', str(ROOT / 'scripts' / entry),
                                 '-SourceRoot', str(self.source), '-CodexCommand', str(self.stub),
                                 '-PythonCommand', sys.executable], capture_output=True, text=True,
                                encoding='utf-8', env=env, timeout=30)
        calls = [json.loads(line) for line in self.log.read_text(encoding='utf-8-sig').splitlines()] if self.log.exists() else []
        return result, calls

    def test_scoped_wrapper_installs_policy_and_plugin(self):
        host = self.work / 'host'
        host.mkdir()
        original = b'# Existing rules\r\nKeep models.\r\n'
        (host/'AGENTS.md').write_bytes(original)
        result, calls = self.run_installer(with_bypass=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'SOURCE_AND_POLICY_VERIFIED')
        self.assertTrue(report['policy']['active'])
        self.assertEqual(report['installation']['status'], 'INSTALL_VERIFIED')
        self.assertFalse(report['invocation_behavior_verified'])
        self.assertTrue((host/'AGENTS.md').read_bytes().startswith(original))
        self.assertEqual(Path(report['policy']['backup']).read_bytes(), original)
        self.assertTrue(any(call[:2] == ['plugin', 'add'] for call in calls))

    def test_scoped_wrapper_rejects_modified_policy_before_native_install(self):
        host = self.work / 'host'
        host.mkdir()
        raw = b'<!-- open-project-jev-bypass:v1:begin -->\nuser edited\n'
        (host/'AGENTS.md').write_bytes(raw)
        result, calls = self.run_installer(with_bypass=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'UPDATE_BLOCKED')
        self.assertEqual(calls, [])
        self.assertEqual((host/'AGENTS.md').read_bytes(), raw)

    def test_native_install_success_without_actual_cache_cannot_verify_wrapper(self):
        result, _ = self.run_installer(with_bypass=True, seed_cache=False)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'PARTIAL_INSTALL')
        self.assertFalse(report['verification']['installed_bytes_verified'])

    def test_read_only_verifier_rejects_plugin_only_install_and_cache_drift(self):
        self.run_installer(with_bypass=True)
        host = self.work/'host'
        verify = runpy.run_path(str(self.source/'scripts/verify-installation.py'))['verify']
        before = {p.relative_to(host): p.read_bytes() for p in host.rglob('*') if p.is_file()}
        report = verify(self.source, host, {'installed':self.scenario['installed']})
        self.assertEqual(report['status'], 'SOURCE_AND_POLICY_VERIFIED')
        self.assertEqual(before, {p.relative_to(host): p.read_bytes() for p in host.rglob('*') if p.is_file()})
        (host/'AGENTS.md').write_text('Generic Jev instructions without exception\n')
        report = verify(self.source, host, {'installed':self.scenario['installed']})
        self.assertFalse(report['jev_policy_verified'])
        self.assertEqual(report['status'], 'INSTALLATION_INCOMPLETE')
        version = self.scenario['installed'][0]['version']
        (host/'plugins/cache/open-project-codex/open-project-codex'/version/'skills/open-project/SKILL.md').write_text('drift')
        report = verify(self.source, host, {'installed':self.scenario['installed']})
        self.assertFalse(report['installed_bytes_verified'])

    def test_verifier_uses_active_override_instead_of_default_exception(self):
        self.run_installer(with_bypass=True)
        host = self.work/'host'
        (host/'AGENTS.override.md').write_text('Other active user instructions\n')
        verify = runpy.run_path(str(self.source/'scripts/verify-installation.py'))['verify']
        self.assertFalse(verify(self.source, host, {'installed':self.scenario['installed']})['jev_policy_verified'])

    def test_verifier_rejects_extra_installed_skill(self):
        self.run_installer(with_bypass=True)
        host = self.work/'host'
        version = self.scenario['installed'][0]['version']
        extra = host/'plugins/cache/open-project-codex/open-project-codex'/version/'skills/unexpected/SKILL.md'
        extra.parent.mkdir(parents=True)
        extra.write_text('Unreviewed runtime skill')
        verify = runpy.run_path(str(self.source/'scripts/verify-installation.py'))['verify']
        report = verify(self.source, host, {'installed':self.scenario['installed']})
        self.assertFalse(report['installed_bytes_verified'])
        self.assertIn('skills/unexpected/SKILL.md', report['unexpected_resources'])

    def test_verifier_requires_explicit_absolute_native_source_path(self):
        self.run_installer(with_bypass=True)
        verify = runpy.run_path(str(self.source/'scripts/verify-installation.py'))['verify']
        old = os.getcwd()
        try:
            os.chdir(self.source)
            for value in (None, '', '.', 'relative-source'):
                row = {**self.scenario['installed'][0], 'source': {'source': 'local'}}
                if value is not None:
                    row['source']['path'] = value
                self.assertFalse(verify(self.source, self.work/'host', {'installed':[row]})['native_verified'])
        finally:
            os.chdir(old)

    def test_scoped_wrapper_uses_nonempty_override_without_changing_default(self):
        host = self.work / 'host'
        host.mkdir()
        original = b'Generic Jev rule\n'
        (host/'AGENTS.md').write_bytes(original)
        override = host/'AGENTS.override.md'
        override.write_bytes(b'Active custom rule\n')
        result, _ = self.run_installer(with_bypass=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)['policy']['target'], str(override))
        self.assertEqual((host/'AGENTS.md').read_bytes(), original)
        self.assertIn(b'open-project-jev-bypass:v1:begin', override.read_bytes())

    def test_scoped_wrapper_ignores_empty_override(self):
        host = self.work / 'host'
        host.mkdir()
        override = host/'AGENTS.override.md'
        override.write_bytes(b' \r\n')
        result, _ = self.run_installer(with_bypass=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)['policy']['target'], str(host/'AGENTS.md'))
        self.assertEqual(override.read_bytes(), b' \r\n')

    def test_scoped_wrapper_missing_installer_does_not_mutate_policy(self):
        (self.source/'scripts/install-plugin.ps1').unlink()
        result, calls = self.run_installer(with_bypass=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['stage'], 'source-validation')
        self.assertFalse((self.work/'host/AGENTS.md').exists())
        self.assertEqual(calls, [])

    def test_scoped_wrapper_native_failure_retains_policy_and_backup_evidence(self):
        host = self.work/'host'
        host.mkdir()
        original = b'Existing rules\n'
        (host/'AGENTS.md').write_bytes(original)
        self.stub.write_text("Write-Output 'not-json'\nexit 0\n", encoding='utf-8')
        result, _ = self.run_installer(with_bypass=True)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertIn(report['status'], ['PARTIAL_UPDATE', 'PARTIAL_INSTALL'])
        self.assertTrue(report['policy']['active'])
        self.assertEqual(Path(report['policy']['backup']).read_bytes(), original)

    def test_success_uses_native_registration_install_and_exact_state_verification(self):
        result, calls = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'INSTALL_VERIFIED')
        self.assertFalse(report['allow_implicit_invocation'])
        self.assertFalse(report['invocation_behavior_verified'])
        self.assertEqual(calls, [
            ['plugin', 'marketplace', 'list', '--json'],
            ['plugin', 'marketplace', 'add', str(self.source.resolve()), '--json'],
            ['plugin', 'add', 'open-project-codex@open-project-codex', '--json'],
            ['plugin', 'list', '--marketplace', 'open-project-codex', '--available', '--json']])

    def test_existing_matching_registration_is_not_added_again(self):
        self.scenario['marketplaces'] = [{'name': 'open-project-codex', 'root': str(self.source)}]
        result, calls = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)['marketplace_registration'], 'EXISTING')
        self.assertFalse(any(call[:3] == ['plugin', 'marketplace', 'add'] for call in calls))

    def test_unrelated_same_name_marketplace_is_not_replaced(self):
        other = self.work / 'other-source'
        other.mkdir()
        self.scenario['marketplaces'] = [{'name': 'open-project-codex', 'root': str(other)}]
        result, calls = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)
        self.assertIn('another source', result.stderr)

    def test_denied_registration_stops_before_plugin_installation(self):
        self.scenario['deny_registration'] = True
        result, calls = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report['stage'], 'marketplace-registration')
        self.assertFalse(report['installation_verified'])
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(call[:2] == ['plugin', 'add'] for call in calls))

    def test_denied_installation_reports_partial_registration_without_cleanup(self):
        self.scenario['deny_installation'] = True
        result, calls = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report['marketplace_registration'], 'REGISTERED')
        self.assertEqual(report['stage'], 'plugin-installation')
        self.assertFalse(report['installation_verified'])
        self.assertEqual(len(calls), 3)

    def test_wrong_version_disabled_or_string_boolean_never_reports_verified(self):
        original = self.scenario['installed'][0].copy()
        for change in [{'version': '0.0.0'}, {'enabled': False}, {'installed': 'true'}]:
            self.scenario['installed'] = [{**original, **change}]
            with self.subTest(change=change):
                result, _ = self.run_installer()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)['status'], 'INSTALL_NOT_VERIFIED')

    def test_invalid_manual_policy_stops_before_any_native_call(self):
        policy = self.source / 'skills/open-project/agents/openai.yaml'
        original = policy.read_text(encoding='utf-8')
        for replacement in ['allow_implicit_invocation: true', 'allow_implicit_invocation: "false"',
                            'missing_policy: false']:
            policy.write_text(original.replace('allow_implicit_invocation: false', replacement), encoding='utf-8')
            with self.subTest(replacement=replacement):
                result, calls = self.run_installer()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
                self.assertEqual(json.loads(result.stdout)['stage'], 'source-validation')

    def test_catalog_cannot_redirect_install_to_another_source(self):
        path = self.source / '.agents/plugins/marketplace.json'
        catalog = json.loads(path.read_text(encoding='utf-8'))
        catalog['plugins'][0]['source']['path'] = '..'
        path.write_text(json.dumps(catalog), encoding='utf-8')
        result, calls = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
