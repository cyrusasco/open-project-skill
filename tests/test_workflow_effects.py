"""Synthetic T21/T22 effects: no live projects and no Git command execution."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/open-project/scripts'))
from plan_contract import PacketError, sha256
from workflow_effects import (GIT_COMMAND, MAX_GIT_STDOUT_BYTES, effect_identity,
                              effects_findings, porcelain_counts,
                              preserved_source_location, validate_effects_structure)


class WorkflowEffectsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workflow-effects-', dir=ROOT)
        self.base = Path(self.temp.name)
        self.project = self.base / 'docs'
        self.code = self.base / 'code'
        self.project.mkdir()
        self.code.mkdir()
        self.plan = {'schema_version': '2.0', 'plan_id': 'synthetic-effects', 'revision': '1',
                     'folder_changes': [], 'workflow': {
                         'roots': {'docs_root': str(self.project),
                                   'source_roots': [{'id': 'code', 'path': str(self.code)}]},
                         'decisions': {'current': []},
                         'effects': {'actions': [], 'git': {'status': 'NOT_APPLICABLE',
                                                          'reason': 'No Git repository in fixture.'}}}}

    def tearDown(self):
        assert self.base.resolve().is_relative_to(ROOT.resolve())
        self.temp.cleanup()

    def write(self, root, relative, raw):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return target

    def reference(self, root_id, relative, raw):
        root = self.project if root_id == 'docs' else self.code
        self.write(root, relative, raw)
        return {'root_id': root_id, 'path': relative, 'sha256': sha256(raw)}

    def receipt(self, action, **changes):
        data = {'schema_version': 'open-project/effect-receipt/1.0',
                'plan_id': self.plan['plan_id'], 'executed_revision': self.plan['revision'],
                'action_id': action['id'], 'action_sha256': effect_identity(self.plan, action),
                'observed_at': datetime.now(timezone.utc).isoformat(), 'result': 'COMPLETE',
                'source_before_sha256': action['source']['sha256'],
                'destination_before_sha256': action['destination']['baseline_sha256'],
                'destination_after_sha256': action['expected_sha256'],
                'source_after': action['source_after'], 'superseded_by': action['superseded_by']}
        data.update(changes)
        action['receipt'] = self.reference('docs', 'evidence/' + action['id'] + '.json',
                                         (json.dumps(data, sort_keys=True) + '\n').encode())
        return data

    def action(self, kind='archive', complete=True, source_after=None):
        old = b'# Original synthetic specification\n'
        source = self.reference('code', 'old-spec.md', old)
        replacement = self.reference('docs', 'product_specification.md', b'# Replacement synthetic spec\n')
        action = {'id': 'preserve-old-spec', 'kind': kind, 'source': source,
                  'destination': {'root_id': 'docs', 'path': 'archive/old-spec.md',
                                  'baseline_sha256': 'NOT_EXISTS'},
                  'expected_sha256': sha256(old),
                  'source_after': source_after or ('PRESENT' if kind == 'copy' else 'ABSENT'),
                  'superseded_by': replacement if kind == 'archive' else
                                   {'root_id': '', 'path': '', 'sha256': ''},
                  'state': 'COMPLETE' if complete else 'PLANNED',
                  'reason': 'Preserve explicitly declared synthetic bytes.',
                  'receipt': {'root_id': '', 'path': '', 'sha256': ''}}
        self.plan['workflow']['effects']['actions'] = [action]
        self.plan['folder_changes'] = [{'id': action['id'], 'description': 'Explicit synthetic preservation.'}]
        self.plan['workflow']['decisions']['current'] = [
            {'action_id': action['id'], 'state': 'COMPLETED' if complete else 'APPROVED'}]
        if complete:
            self.write(self.project, action['destination']['path'], old)
            if action['source_after'] == 'ABSENT':
                (self.code / 'old-spec.md').unlink()
            self.receipt(action)
        return action

    def git(self, raw=b'', clean=None, counts=None):
        (self.code / '.git').mkdir(exist_ok=True)
        self.plan['workflow']['effects']['git'] = {
            'status': 'OBSERVED', 'reason': 'Synthetic captured status, no Git process used.',
            'root_id': 'code', 'root_path': str(self.code),
            'observed_at': datetime.now(timezone.utc).isoformat(), 'exit_code': 0,
            'command': list(GIT_COMMAND),
            'stdout': self.reference('docs', 'evidence/git-porcelain.txt', raw),
            'claimed_clean': raw == b'' if clean is None else clean,
            'counts': porcelain_counts(raw) if counts is None else counts}
        return self.plan['workflow']['effects']['git']

    def test_required_effects_cannot_be_omitted_or_silently_untyped(self):
        validate_effects_structure(self.plan)
        self.assertEqual(effects_findings(self.plan, self.project, 'completion'), [])
        del self.plan['workflow']['effects']
        with self.assertRaises(PacketError):
            validate_effects_structure(self.plan)

    def test_physical_archive_without_supersedes_mapping_or_receipt_is_incomplete(self):
        action = self.action()
        self.assertTrue((self.project / 'archive/old-spec.md').exists())
        action['superseded_by'] = {'root_id': '', 'path': '', 'sha256': ''}
        with self.assertRaisesRegex(PacketError, 'superseded_by'):
            validate_effects_structure(self.plan)
        action['superseded_by'] = {'root_id': 'docs', 'path': 'product_specification.md',
                                   'sha256': sha256((self.project / 'product_specification.md').read_bytes())}
        action['receipt'] = {'root_id': '', 'path': '', 'sha256': ''}
        self.assertTrue(any(row['code'] == 'W_EFFECT_STRUCTURE'
                            for row in effects_findings(self.plan, self.project, 'completion')))

    def test_valid_archive_checks_receipt_mapping_bytes_and_replacement(self):
        action = self.action()
        self.assertEqual(effects_findings(self.plan, self.project, 'completion'), [])
        self.receipt(action, superseded_by={'root_id': '', 'path': '', 'sha256': ''})
        self.assertTrue(any('supersedes scope' in row['message']
                            for row in effects_findings(self.plan, self.project, 'completion')))
        self.receipt(action)
        (self.project / 'archive/old-spec.md').write_bytes(b'drifted archive')
        self.assertTrue(any('destination bytes' in row['message']
                            for row in effects_findings(self.plan, self.project, 'completion')))

    def test_planned_copy_checks_before_state_but_cannot_be_complete(self):
        self.action('copy', complete=False)
        self.assertEqual(effects_findings(self.plan, self.project, 'plan'), [])
        self.assertTrue(effects_findings(self.plan, self.project, 'completion'))
        self.write(self.project, 'archive/old-spec.md', b'unrelated preexisting file')
        self.assertTrue(any('NOT_EXISTS' in row['message']
                            for row in effects_findings(self.plan, self.project)))

    def test_move_source_presence_and_folder_action_mapping_are_checked(self):
        self.action('move')
        self.assertEqual(effects_findings(self.plan, self.project, 'completion'), [])
        self.write(self.code, 'old-spec.md', b'# Original synthetic specification\n')
        self.assertTrue(any('source still exists' in row['message']
                            for row in effects_findings(self.plan, self.project, 'completion')))
        self.plan['folder_changes'][0]['id'] = 'unmapped-folder-action'
        with self.assertRaisesRegex(PacketError, 'map exactly'):
            validate_effects_structure(self.plan)

    def test_preserved_source_fallback_is_exact_and_keeps_original_identity(self):
        from workflow_contract import source_location
        action = self.action()
        source = deepcopy(action['source'])
        before = deepcopy(source)
        destination = preserved_source_location(self.plan, self.project, source)
        self.assertEqual(destination, self.project / 'archive/old-spec.md')
        self.assertEqual(source_location(self.plan, self.project, source), destination)
        self.assertEqual(sha256(destination.read_bytes()), source['sha256'])
        self.assertEqual(source, before)
        self.assertIsNone(preserved_source_location(self.plan, self.project,
                                                   {**source, 'path': 'another-old-spec.md'}))
        self.assertIsNone(preserved_source_location(self.plan, self.project,
                                                   {**source, 'sha256': '0' * 64}))
        self.receipt(action, action_sha256='0' * 64)
        with self.assertRaises(PacketError):
            preserved_source_location(self.plan, self.project, source)

    def test_rebinding_root_invalidates_old_action_receipt(self):
        self.action()
        moved_code = self.base / 'different-code-root'
        moved_code.mkdir()
        self.plan['workflow']['roots']['source_roots'][0]['path'] = str(moved_code)
        self.assertTrue(any('supersedes scope' in row['message']
                            for row in effects_findings(self.plan, self.project, 'completion')))

    def test_untracked_documentation_cannot_be_called_clean(self):
        observation = self.git(b'?? DOCUMENTATION.md\n', clean=True)
        self.assertTrue(any('clean claim' in row['message']
                            for row in effects_findings(self.plan, self.project, 'completion')))
        observation['claimed_clean'] = False
        self.assertEqual(effects_findings(self.plan, self.project, 'completion'), [])
        self.assertEqual(observation['counts'], {'tracked': 0, 'untracked': 1, 'ignored': 0})

    def test_tracked_untracked_ignored_counts_and_empty_clean_are_exact(self):
        observation = self.git(b'M  first.md\n M second.md\n?? DOCUMENTATION.md\n!! cache/\n')
        self.assertEqual(effects_findings(self.plan, self.project), [])
        self.assertEqual(observation['counts'], {'tracked': 2, 'untracked': 1, 'ignored': 1})
        observation['counts']['untracked'] = 0
        self.assertTrue(any('counts contradict' in row['message']
                            for row in effects_findings(self.plan, self.project)))
        self.git(b'', clean=True)
        self.assertEqual(effects_findings(self.plan, self.project, 'completion'), [])

    def test_git_metadata_timestamp_and_root_cannot_be_stale_or_fake_na(self):
        observation = self.git()
        observation['root_path'] = str(self.project)
        with self.assertRaisesRegex(PacketError, 'root_path'):
            validate_effects_structure(self.plan)
        observation['root_path'] = str(self.code)
        observation['observed_at'] = '2026-11-02T21:2x:00+08:00'
        with self.assertRaisesRegex(PacketError, 'timestamp'):
            validate_effects_structure(self.plan)
        self.plan['workflow']['effects']['git'] = {'status': 'NOT_APPLICABLE', 'reason': 'No Git claimed.'}
        self.assertTrue(any('cannot be N/A' in row['message']
                            for row in effects_findings(self.plan, self.project)))

    def test_git_capture_hash_bound_and_no_commands_or_cwd_changes(self):
        observation = self.git(b'?? DOCUMENTATION.md\n')
        before = os.getcwd()
        with mock.patch('subprocess.run', side_effect=AssertionError('No process permitted')):
            self.assertEqual(effects_findings(self.plan, self.project), [])
        self.assertEqual(os.getcwd(), before)
        self.write(self.project, observation['stdout']['path'], b'')
        self.assertTrue(any('hash mismatch' in row['message']
                            for row in effects_findings(self.plan, self.project)))
        self.git(b'x' * (MAX_GIT_STDOUT_BYTES + 1), clean=False,
                 counts={'tracked': 0, 'untracked': 0, 'ignored': 0})
        self.assertTrue(any('bounded capture' in row['message']
                            for row in effects_findings(self.plan, self.project)))

    def test_invalid_paths_and_porcelain_cannot_pass(self):
        action = self.action('copy', complete=False)
        action['destination']['path'] = '../outside.md'
        with self.assertRaises(PacketError):
            validate_effects_structure(self.plan)
        for raw in (b'\n', b'hello\n', b'?? \n', b'XX path\n', b'\xff'):
            with self.assertRaises(PacketError):
                porcelain_counts(raw)

    def test_large_valid_capture_is_streamed_and_every_byte_hash_checked(self):
        raw = b'!! synthetic-dependencies/ignored-file\n' * 310000
        observation = self.git(raw)
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('No full-file read')):
            self.assertEqual(effects_findings(self.plan, self.project), [])
        self.assertEqual(observation['counts']['ignored'], 310000)
        observation['stdout']['sha256'] = '0' * 64
        self.assertTrue(any('hash mismatch' in x['message'] for x in effects_findings(self.plan, self.project)))

    def test_chunk_boundary_utf8_crlf_and_final_unterminated_record(self):
        from workflow_effects import GIT_READ_CHUNK_BYTES
        raw = b'!! ' + b'a' * (GIT_READ_CHUNK_BYTES - 4) + '圖'.encode() + b'\r\n?? last.md'
        self.git(raw)
        self.assertEqual(effects_findings(self.plan, self.project), [])

    def test_total_stream_limit_stops_without_accepting_prefix(self):
        self.git(b'!! cache/\n' * 10)
        with mock.patch('workflow_effects.MAX_GIT_CAPTURE_BYTES', 20):
            self.assertTrue(any('total limit' in x['message'] for x in effects_findings(self.plan, self.project)))

    def test_mutated_capture_identity_is_rejected(self):
        self.git(b'!! cache/\n')
        from types import SimpleNamespace
        actual = os.stat(self.project/'evidence/git-porcelain.txt')
        changed = SimpleNamespace(**{k:getattr(actual,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')})
        changed.st_mtime_ns += 1
        with mock.patch('workflow_effects.os.fstat', side_effect=[actual, changed]):
            self.assertTrue(any('changed during' in x['message'] for x in effects_findings(self.plan, self.project)))


if __name__ == '__main__':
    unittest.main()
