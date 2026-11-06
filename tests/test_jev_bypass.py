import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('jev_policy', ROOT/'scripts/configure-jev-bypass.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class ScopedJevPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'AGENTS.md'
        self.raw = b'\xef\xbb\xbf# Existing rules\r\nPreserve models and user scope.\r\n'
        self.path.write_bytes(self.raw)

    def test_preview_is_read_only(self):
        result = policy.configure(self.path)
        self.assertEqual(result['status'], 'PREVIEW')
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_apply_preserves_exact_existing_bytes_and_raw_backup(self):
        result = policy.configure(self.path, apply=True, expected=policy.digest(self.raw))
        self.assertEqual(self.path.read_bytes(), self.raw+policy.BLOCK)
        self.assertEqual(Path(result['backup']).read_bytes(), self.raw)
        self.assertTrue(result['active'])
        self.assertFalse(result['behavior_verified'])

    def test_repeat_is_noop_with_same_bytes(self):
        policy.configure(self.path, apply=True, expected=policy.digest(self.raw))
        raw = self.path.read_bytes()
        result = policy.configure(self.path, apply=True, expected=policy.digest(raw))
        self.assertEqual(result['status'], 'NO_OP')
        self.assertEqual(self.path.read_bytes(), raw)

    def test_revoke_preserves_preexisting_and_later_user_text(self):
        policy.configure(self.path, apply=True, expected=policy.digest(self.raw))
        addition = b'\n# Later user rule\nKeep deployment approval.\n'
        self.path.write_bytes(self.path.read_bytes()+addition)
        current = self.path.read_bytes()
        result = policy.configure(self.path, apply=True, remove=True, expected=policy.digest(current))
        self.assertFalse(result['active'])
        self.assertEqual(self.path.read_bytes(), self.raw+addition)

    def test_drift_refused_before_backup_or_mutation(self):
        with self.assertRaisesRegex(ValueError, 'baseline mismatch'):
            policy.configure(self.path, apply=True, expected='0'*64)
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_modified_duplicate_or_partial_block_is_not_overwritten(self):
        for suffix in [policy.BEGIN, policy.BLOCK+policy.BLOCK,
                       policy.BLOCK.replace(b'not a global disable', b'global disable')]:
            self.path.write_bytes(self.raw+suffix)
            with self.assertRaisesRegex(ValueError, 'changed/ambiguous'):
                policy.configure(self.path, apply=True, expected=policy.digest(self.path.read_bytes()))
            self.assertEqual(self.path.read_bytes(), self.raw+suffix)

    def test_conflicting_backup_is_not_overwritten(self):
        backup=self.path.with_name(self.path.name+'.open-project-jev-backup-'+policy.digest(self.raw)+'.bak')
        backup.write_bytes(b'other evidence')
        with self.assertRaisesRegex(ValueError, 'Backup conflicts'):
            policy.configure(self.path, apply=True, expected=policy.digest(self.raw))
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(backup.read_bytes(), b'other evidence')

    def test_missing_file_can_be_explicitly_created(self):
        self.path.unlink()
        result=policy.configure(self.path, apply=True, expected='NOT_EXISTS')
        self.assertEqual(result['status'], 'APPLIED')
        self.assertEqual(self.path.read_bytes(), policy.BLOCK)

    def test_non_instructions_target_rejected(self):
        with self.assertRaisesRegex(ValueError, 'AGENTS.md'):
            policy.configure(self.path.with_name('config.toml'))

    def test_windows_reparse_flag_blocks_even_without_is_junction_api(self):
        with patch.object(Path, 'is_symlink', return_value=False), patch.object(Path, 'lstat', return_value=SimpleNamespace(st_file_attributes=0x400)):
            with self.assertRaisesRegex(ValueError, 'Symlink/junction'):
                policy.configure(self.path)
        self.assertEqual(self.path.read_bytes(), self.raw)


if __name__ == '__main__':
    unittest.main()
