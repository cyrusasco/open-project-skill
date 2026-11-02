"""Read-only exact inventory and knowledge-link closure regressions."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/open-project/scripts'))
from plan_contract import sha256
import workflow_package


class PackageFindingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        self.package_root = self.project / 'package'

    def packet(self, files, mode='knowledge_bundle'):
        items = []
        for relative, body in files.items():
            raw = body.encode('utf-8') if isinstance(body, str) else body
            for location in (self.project / 'sources' / relative, self.package_root / relative):
                location.parent.mkdir(parents=True, exist_ok=True)
                location.write_bytes(raw)
            items.append({'role': 'knowledge', 'source_root': 'docs', 'path': 'sources/' + relative,
                          'package_path': relative, 'disposition': 'included', 'required': True,
                          'sha256': sha256(raw), 'reason': 'Synthetic package inventory.'})
        return {'schema_version': '2.0', 'workflow': {
            'roots': {'docs_root': str(self.project), 'source_roots': []},
            'package': {'mode': mode, 'status': 'PACKAGED', 'root': str(self.package_root),
                        'reason': 'Explicit synthetic package mode.', 'inventory': items,
                        'fresh_session_evidence': []}}}

    def findings(self, packet, stage='completion'):
        return workflow_package.package_findings(packet, self.project, stage)

    def test_exact_knowledge_inventory_and_encoded_links_close_locally(self):
        packet = self.packet({
            'README.md': '# Knowledge\n[Ops][op]\n![Picture](assets/a%20b.png?version=1#preview)\n'
                         '[Citation](https://example.invalid/a?q=1#part)\n'
                         '[op]: <refs/ops manual.md?version=1#rules> "Ops title"\n',
            'refs/ops manual.md': '# Rules\n[Home](../README.md#knowledge)\n',
            'assets/a b.png': b'fixture-image-bytes',
        })
        before = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        self.assertEqual(self.findings(packet), [])
        after = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_missing_and_extra_files_are_both_reported(self):
        packet = self.packet({'README.md': '# Existing knowledge\n', 'missing.md': 'Included content\n'})
        (self.package_root / 'missing.md').unlink()
        (self.package_root / '.unlisted').write_text('Unexpected package content', encoding='utf-8')
        findings = self.findings(packet)
        self.assertTrue(all(row['severity'] == 'error' for row in findings))
        self.assertTrue(any('missing package files: missing.md' in row['message'] for row in findings))
        self.assertTrue(any('extra package files: .unlisted' in row['message'] for row in findings))

    def test_planned_package_needs_no_existing_output_at_plan_stage(self):
        packet = self.packet({'README.md': 'Knowledge\n'})
        packet['workflow']['package'].update(status='PLANNED', root=str(self.project / 'not-built-yet'))
        self.assertEqual(self.findings(packet, 'plan'), [])
        self.assertTrue(any(row['code'] == 'W_PACKAGE_PATH' for row in self.findings(packet)))

    def test_relative_escape_absolute_paths_and_unsafe_schemes_fail(self):
        packet = self.packet({'README.md': 'Initial content\n'})
        targets = ['../outside.md', '%2e%2e/outside.md', '/absolute.md', 'C:/outside.md',
                   'C%3A/outside.md', 'file:///C:/outside.md', '//server/share.md',
                   '%2f%2fserver/share.md', 'sub\\file.md', 'javascript:alert(1)',
                   'data:text/html,hello', '%FF.md']
        for target in targets:
            with self.subTest(target=target):
                (self.package_root / 'README.md').write_text('[Link](' + target + ')\n', encoding='utf-8')
                self.assertTrue(any(row['code'] == 'W_PACKAGE_LINK' for row in self.findings(packet)))

    def test_missing_markdown_image_reference_and_html_targets_fail(self):
        packet = self.packet({'README.md': 'Initial content\n'})
        for body in ['[Missing](missing.md)', '![Missing](missing.png)', '[Missing [inner]](missing.md)',
                     '![Missing [inner]](missing.png)', '[Missing][not-defined]',
                     '<a href="missing.md">Missing</a>', '<img src="missing.png">']:
            with self.subTest(body=body):
                (self.package_root / 'README.md').write_text(body + '\n', encoding='utf-8')
                self.assertTrue(any(row['code'] == 'W_PACKAGE_LINK' for row in self.findings(packet)))

    def test_backslash_traversal_cannot_be_masked_by_a_coincidental_filename(self):
        packet = self.packet({'README.md': '[Outside](..\\outside.md)\n',
                              '..outside.md': 'A coincidental local filename must not mask traversal.\n'})
        self.assertIn('\\', workflow_package._destination('..\\outside.md)'))
        self.assertTrue(any(row['code'] == 'W_PACKAGE_LINK' and 'backslash' in row['message']
                            for row in self.findings(packet)))

    def test_code_examples_are_not_link_dependencies(self):
        packet = self.packet({'README.md': '# Knowledge\n```md\n[Example](missing.md)\n```\n'
                                                   '`![Example](missing.png)`\n'})
        self.assertEqual(self.findings(packet), [])

    def test_parenthesized_and_escaped_destinations_are_supported(self):
        packet = self.packet({'README.md': '[One](ref(a).md "Title")\n[Two](ref\\(a\\).md)\n',
                              'ref(a).md': 'Content\n'})
        self.assertEqual(self.findings(packet), [])

    def test_fragment_and_query_only_links_refer_to_current_document(self):
        packet = self.packet({'README.md': '# Knowledge\n[Here](#knowledge)\n[View](?view=1#knowledge)\n'})
        self.assertEqual(self.findings(packet), [])

    def test_required_external_adapter_dependency_is_explicit_and_hash_checked(self):
        packet = self.packet({'SKILL.md': '# Ops\n[External](../../external/manual.md)\n'}, mode='local_adapter')
        external_root = self.project / 'external'
        external_root.mkdir()
        raw = b'Explicit external operation manual\n'
        (external_root / 'manual.md').write_bytes(raw)
        packet['workflow']['roots']['source_roots'] = [{'id': 'code', 'path': str(external_root)}]
        packet['workflow']['package']['inventory'].append({
            'role': 'project_manual', 'source_root': 'code', 'path': 'manual.md', 'package_path': '',
            'disposition': 'external', 'required': True, 'sha256': sha256(raw),
            'reason': 'Local adapter explicitly depends on this external manual.'})
        self.assertEqual(self.findings(packet), [])
        (external_root / 'manual.md').write_bytes(b'Changed outside the reviewed package scope\n')
        self.assertTrue(any(row['code'] == 'W_PACKAGE_EXTERNAL' for row in self.findings(packet)))

    def test_adapter_external_dependency_cannot_use_an_unknown_root(self):
        packet = self.packet({'SKILL.md': '# Ops\n'}, mode='local_adapter')
        packet['workflow']['package']['inventory'].append({
            'role': 'project_manual', 'source_root': 'missing-root', 'path': 'manual.md', 'package_path': '',
            'disposition': 'external', 'required': True, 'sha256': 'a' * 64,
            'reason': 'Unknown roots are not implicit permissions.'})
        self.assertTrue(any(row['code'] == 'W_PACKAGE_EXTERNAL' for row in self.findings(packet)))

    def test_junction_attribute_is_rejected_before_any_traversal(self):
        packet = self.packet({'README.md': '# Knowledge\n'})
        entry = SimpleNamespace(name='outside', path=str(self.package_root / 'outside'),
                                stat=lambda **kw: SimpleNamespace(st_mode=stat.S_IFDIR | 0o755,
                                                                 st_file_attributes=0x400))
        listing = mock.MagicMock()
        listing.__enter__.return_value = iter([entry])
        with mock.patch.object(workflow_package.os, 'scandir', return_value=listing) as scan:
            findings = self.findings(packet)
        self.assertEqual(scan.call_count, 1)
        self.assertTrue(any(row['code'] == 'W_PACKAGE_PATH' and 'reparse' in row['message'] for row in findings))

    def test_root_reparse_attribute_is_rejected_without_scanning(self):
        packet = self.packet({'README.md': '# Knowledge\n'})
        original = Path.lstat
        def status(path):
            if path == self.package_root:
                return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x400)
            return original(path)
        with mock.patch.object(Path, 'lstat', status), mock.patch.object(workflow_package.os, 'scandir') as scan:
            findings = self.findings(packet)
        scan.assert_not_called()
        self.assertTrue(any(row['code'] == 'W_PACKAGE_PATH' for row in findings))

    def test_no_package_remains_not_applicable(self):
        packet = {'workflow': {'package': {'mode': 'none'}}}
        self.assertEqual(self.findings(packet), [])


if __name__ == '__main__':
    unittest.main()
