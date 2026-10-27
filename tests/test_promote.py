"""Synthetic promotion/recovery tests; never touches installed sources or databases."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types
import stat
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/open-project/scripts"
sys.path.insert(0, str(SCRIPTS))
from plan_contract import PacketError, sha256, packet_digest, expected_content
import plan_render
import promote
from support import make_packet, save_packet


class SimulatedCrash(BaseException):
    pass


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        self.plan = make_packet(self.project)
        self.approval = Path(self.temporary.name) / "approval.json"

    def prepare(self, selected=None):
        save_packet(self.project, self.plan)
        plan_render.write_views(self.project, self.plan)
        selected = self.plan["drafts"] if selected is None else selected
        value = {"plan_id": self.plan["plan_id"], "revision": self.plan["revision"],
                 "packet_sha256": packet_digest(self.plan), "approved_by": "Synthetic reviewer",
                 "approved_at": "2026-10-27T22:00:00+00:00", "actions": []}
        for draft in selected:
            value["actions"].append({"draft_id": draft["id"], "target": draft["target"],
                "draft_sha256": draft["sha256"], "baseline_sha256": draft["baseline_sha256"],
                "expected_sha256": draft["expected_sha256"], "transforms": draft["transforms"], "effects": ["write_file"]})
        self.approval.write_text(json.dumps(value), encoding="utf-8")
        return value

    def baseline(self, raw=b"existing bytes\r\n"):
        draft = self.plan["drafts"][0]
        target = self.project / draft["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        draft["baseline_sha256"] = sha256(raw)
        return draft, target

    def snapshot(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes()
                for p in self.project.rglob("*") if p.is_file()}

    def result(self, **kwargs):
        return promote.promote(self.project, self.approval, **kwargs)

    def journal(self, result):
        return json.loads((self.project / result["journal"]).read_text(encoding="utf-8"))

    def test_dry_run_reads_only_and_cli_defaults_to_dry_run(self):
        self.prepare()
        before = self.snapshot()
        self.assertEqual(self.result()["status"], "DRY_RUN")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.project / promote.STATE).exists())
        command = [sys.executable, str(SCRIPTS / "promote.py"), str(self.project), "--approval", str(self.approval)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "DRY_RUN")
        self.assertEqual(self.snapshot(), before)

    def test_apply_writes_expected_bytes_and_preserves_nested_byte_backup(self):
        self.plan["drafts"][0]["target"] = "docs/product_specification.md"
        draft, target = self.baseline(b"original\r\n\x00bytes")
        self.prepare()
        original = target.read_bytes()
        result = self.result(apply=True)
        self.assertEqual(result["status"], "COMMITTED", result)
        for entry in self.plan["drafts"]:
            expected = expected_content(entry, (self.project / entry["path"]).read_bytes())
            self.assertEqual((self.project / entry["target"]).read_bytes(), expected)
        action = next(a for a in self.journal(result)["actions"] if a["draft_id"] == draft["id"])
        self.assertTrue(action["backup"].endswith("/" + draft["target"]))
        self.assertEqual((self.project / action["backup"]).read_bytes(), original)
        self.assertFalse((self.project / promote.STATE / "lock.json").exists())

    def test_repeated_apply_is_noop_and_has_no_new_backups(self):
        self.baseline()
        self.prepare()
        first = self.result(apply=True)
        before = self.snapshot()
        second = self.result(apply=True)
        self.assertEqual(first["status"], "COMMITTED")
        self.assertEqual(second["status"], "NO_OP")
        self.assertEqual(self.snapshot(), before)

    def test_reorg_source_equal_target_can_be_applied_and_repeated_as_noop(self):
        draft, target = self.baseline(b"historical specification\n")
        self.plan["sources"] = [{"id": "original-spec", "kind": "file", "path": draft["target"],
                                 "sha256": draft["baseline_sha256"], "required": True}]
        self.prepare()
        first = self.result(apply=True)
        self.assertEqual(first["status"], "COMMITTED", first)
        self.assertEqual(sha256(target.read_bytes()), draft["expected_sha256"])
        before = self.snapshot()
        self.assertEqual(self.result(apply=True)["status"], "NO_OP")
        self.assertEqual(self.snapshot(), before)

    def test_already_expected_is_noop_without_backup(self):
        for draft in self.plan["drafts"]:
            target = self.project / draft["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected_content(draft, (self.project / draft["path"]).read_bytes()))
        self.prepare()
        result = self.result(apply=True)
        self.assertEqual(result["status"], "COMMITTED")
        self.assertTrue(all(a["status"] == "NO_OP" and a["backup"] is None for a in result["actions"]))
        self.assertFalse((self.project / promote.STATE / "backups").exists())

    def test_target_drift_stops_entire_batch_before_state_writes(self):
        draft, target = self.baseline()
        self.prepare()
        target.write_bytes(b"unapproved user edit")
        before = self.snapshot()
        with self.assertRaisesRegex(PacketError, "drift"):
            self.result(apply=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.project / promote.STATE).exists())

    def test_draft_drift_stops_before_state_writes(self):
        self.prepare()
        draft = self.plan["drafts"][0]
        (self.project / draft["path"]).write_bytes(b"changed draft")
        before = self.snapshot()
        with self.assertRaises(PacketError):
            self.result(apply=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.project / promote.STATE).exists())

    def test_stale_or_broader_approval_is_rejected(self):
        value = self.prepare()
        mutations = [lambda v: v.update(revision="other"),
                     lambda v: v.update(packet_sha256="0" * 64),
                     lambda v: v.update(approved_by=" "),
                     lambda v: v.update(approved_at="2026-10-27T22:00:00"),
                     lambda v: v["actions"][0].update(target="other.md"),
                     lambda v: v["actions"][0].update(effects=["write_file", "execute"]),
                     lambda v: v["actions"].append(copy.deepcopy(v["actions"][0]))]
        before = self.snapshot()
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(value)
                mutation(changed)
                self.approval.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(PacketError):
                    self.result(apply=True)
                self.assertEqual(self.snapshot(), before)

    def test_exact_selected_subset_is_supported_and_dependencies_are_required(self):
        first = self.plan["drafts"][0]
        second = copy.deepcopy(first)
        second.update(id="dependent", path="md-drafts/dependent.DRAFT.md", target="dependent.md", depends_on=[first["id"]])
        raw = (self.project / first["path"]).read_bytes()
        (self.project / second["path"]).write_bytes(raw)
        self.plan["drafts"].append(second)
        self.prepare([second])
        with self.assertRaisesRegex(PacketError, "omits dependency"):
            self.result(apply=True)
        self.prepare([first])
        self.assertEqual(self.result(apply=True)["status"], "COMMITTED")
        self.assertFalse((self.project / second["target"]).exists())

    def test_validation_runs_before_any_target_write(self):
        self.prepare()
        report = self.project / "md-drafts/PLAN-REPORT.DRAFT.html"
        report.write_text("stale report", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaisesRegex(PacketError, "gate"):
            self.result(apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_unsafe_target_path_is_rejected(self):
        draft = self.plan["drafts"][0]
        self.prepare()
        self.plan["drafts"][0]["target"] = "../outside.md"
        # Persist the malicious plan directly; normal rendering rejects it too.
        (self.project / "md-drafts/plan-data.json").write_text(json.dumps(self.plan), encoding="utf-8")
        with self.assertRaises(PacketError):
            self.result(apply=True)
        self.assertFalse((self.project.parent / "outside.md").exists())

    def test_backup_parent_symlink_or_junction_is_rejected(self):
        self.baseline()
        self.prepare()
        state = self.project / promote.STATE
        state.mkdir()
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        link = state / "backups"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                self.skipTest("symlink creation unavailable")
            import _winapi
            try:
                _winapi.CreateJunction(str(outside), str(link))
            except OSError:
                # This sandbox disallows link creation. Exercise the exact Windows
                # reparse attribute branch with a synthetic lstat result instead.
                link.mkdir(exist_ok=True)
                original_lstat = Path.lstat
                def reparse_lstat(path, *args, **kwargs):
                    if path == link:
                        return types.SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                    return original_lstat(path, *args, **kwargs)
                patcher = mock.patch.object(Path, "lstat", reparse_lstat)
                patcher.start()
                self.addCleanup(patcher.stop)
        self.addCleanup(lambda: (link.unlink() if link.is_symlink() else link.rmdir()) if link.exists() else None)
        with self.assertRaisesRegex(PacketError, "unsafe|symlink|reparse"):
            self.result(apply=True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_backup_collision_never_overwrites_existing_bytes(self):
        self.baseline()
        self.prepare()
        class Fixed:
            hex = "f" * 32
        root = self.project / promote.STATE / "backups" / Fixed.hex
        root.mkdir(parents=True)
        sentinel = root / "sentinel"
        sentinel.write_bytes(b"retain")
        before = self.snapshot()
        with mock.patch.object(promote.uuid, "uuid4", return_value=Fixed()):
            with self.assertRaisesRegex(PacketError, "collision"):
                self.result(apply=True)
        self.assertEqual(sentinel.read_bytes(), b"retain")
        after = self.snapshot()
        after.pop(promote.STATE + "/.gitignore", None)
        self.assertEqual(after, before)

    def test_write_failure_rolls_back_verified_bytes(self):
        draft, target = self.baseline()
        self.prepare()
        original = target.read_bytes()
        replace = promote._replace
        fired = False
        def fail_after_write(source, destination):
            nonlocal fired
            replace(source, destination)
            if destination == target and not fired:
                fired = True
                raise OSError("synthetic failure after replacement")
        with mock.patch.object(promote, "_replace", side_effect=fail_after_write):
            result = self.result(apply=True)
        self.assertEqual(result["status"], "FAILED_RECOVERED", result)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.journal(result)["status"], "FAILED_RECOVERED")
        with self.assertRaisesRegex(PacketError, "resume"):
            self.result(apply=True)
        self.assertEqual(self.result(apply=True, resume=True)["status"], "COMMITTED")

    def test_new_nested_target_failure_recovers_file_bytes_and_states_directory_scope(self):
        draft = self.plan["drafts"][0]
        draft["target"] = "new/nested/product_specification.md"
        target = self.project / draft["target"]
        self.prepare()
        replace = promote._replace
        fired = False
        def fail_after_write(source, destination):
            nonlocal fired
            replace(source, destination)
            if destination == target and not fired:
                fired = True
                raise OSError("synthetic nested write failure")
        with mock.patch.object(promote, "_replace", side_effect=fail_after_write):
            result = self.result(apply=True)
        self.assertEqual(result["status"], "FAILED_RECOVERED", result)
        self.assertEqual(result["recovery_scope"], "target_file_bytes")
        self.assertTrue(result["empty_parent_directories_may_remain"])
        self.assertFalse(target.exists())
        self.assertTrue(target.parent.is_dir())

    def test_failed_rollback_is_reported_unrecovered_and_not_overwritten(self):
        draft, target = self.baseline()
        self.prepare()
        replace = promote._replace
        fired = False
        def fail_write_and_recovery(source, destination):
            nonlocal fired
            if destination == target:
                if not fired:
                    replace(source, destination)
                    fired = True
                raise OSError("synthetic persistent target failure")
            replace(source, destination)
        with mock.patch.object(promote, "_replace", side_effect=fail_write_and_recovery):
            result = self.result(apply=True)
        self.assertEqual(result["status"], "FAILED_UNRECOVERED", result)
        self.assertEqual(self.journal(result)["status"], "FAILED_UNRECOVERED")
        changed = json.loads(self.approval.read_text(encoding="utf-8"))
        changed["approved_at"] = "2026-10-27T23:00:00+00:00"
        self.approval.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(PacketError, "unresolved"):
            self.result(apply=True)

    def test_crash_after_replace_resumes_same_approval_without_new_backup(self):
        draft, target = self.baseline()
        self.prepare()
        replace = promote._replace
        def crash_after_replace(source, destination):
            replace(source, destination)
            if destination == target:
                raise SimulatedCrash()
        with mock.patch.object(promote, "_replace", side_effect=crash_after_replace):
            with self.assertRaises(SimulatedCrash):
                self.result(apply=True)
        backups = list((self.project / promote.STATE / "backups").rglob("*"))
        result = self.result(apply=True, resume=True)
        self.assertEqual(result["status"], "COMMITTED", result)
        self.assertEqual(list((self.project / promote.STATE / "backups").rglob("*")), backups)
        self.assertEqual(sha256(target.read_bytes()), draft["expected_sha256"])

    def test_crash_after_backup_resumes_and_checks_backup_hash(self):
        draft, target = self.baseline()
        self.prepare()
        write = promote._backup_write
        def crash_after_backup(root, relative, data):
            write(root, relative, data)
            raise SimulatedCrash()
        with mock.patch.object(promote, "_backup_write", side_effect=crash_after_backup):
            with self.assertRaises(SimulatedCrash):
                self.result(apply=True)
        result = self.result(apply=True, resume=True)
        self.assertEqual(result["status"], "COMMITTED", result)
        self.assertEqual(sha256(target.read_bytes()), draft["expected_sha256"])

    def test_resume_rejects_target_drift_and_new_approval(self):
        draft, target = self.baseline()
        self.prepare()
        replace = promote._replace
        def crash_after_replace(source, destination):
            replace(source, destination)
            if destination == target:
                raise SimulatedCrash()
        with mock.patch.object(promote, "_replace", side_effect=crash_after_replace):
            with self.assertRaises(SimulatedCrash):
                self.result(apply=True)
        changed = json.loads(self.approval.read_text(encoding="utf-8"))
        changed["approved_at"] = "2026-10-27T23:00:00+00:00"
        self.approval.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(PacketError):
            self.result(apply=True, resume=True)
        changed["approved_at"] = "2026-10-27T22:00:00+00:00"
        self.approval.write_text(json.dumps(changed), encoding="utf-8")
        target.write_bytes(b"unapproved drift")
        with self.assertRaisesRegex(PacketError, "drift"):
            self.result(apply=True, resume=True)
        self.assertEqual(target.read_bytes(), b"unapproved drift")

    def test_apply_creates_private_metadata_and_rejects_unexpected_existing_file(self):
        self.prepare()
        state = self.project / promote.STATE
        state.mkdir()
        ignore = state / ".gitignore"
        ignore.write_bytes(b"user owned content\n")
        before = self.snapshot()
        with self.assertRaisesRegex(PacketError, "unexpected existing"):
            self.result(apply=True)
        self.assertEqual(self.snapshot(), before)
        ignore.unlink()
        self.assertEqual(self.result(apply=True)["status"], "COMMITTED")
        self.assertEqual(ignore.read_bytes(), b"*\n")

    def test_tampered_backup_blocks_resume_and_does_not_touch_target(self):
        draft, target = self.baseline()
        self.prepare()
        replace = promote._replace
        def crash_after_replace(source, destination):
            replace(source, destination)
            if destination == target:
                raise SimulatedCrash()
        with mock.patch.object(promote, "_replace", side_effect=crash_after_replace):
            with self.assertRaises(SimulatedCrash):
                self.result(apply=True)
        backups = [p for p in (self.project / promote.STATE / "backups").rglob("*") if p.is_file()]
        self.assertEqual(len(backups), 1)
        backups[0].write_bytes(b"corrupt backup")
        before = target.read_bytes()
        with self.assertRaisesRegex(PacketError, "backup has changed"):
            self.result(apply=True, resume=True)
        self.assertEqual(target.read_bytes(), before)

    def test_malformed_crash_journal_is_rejected_before_any_resume_mutation(self):
        draft, target = self.baseline()
        self.prepare()
        replace = promote._replace
        def crash_after_replace(source, destination):
            replace(source, destination)
            if destination == target:
                raise SimulatedCrash()
        with mock.patch.object(promote, "_replace", side_effect=crash_after_replace):
            with self.assertRaises(SimulatedCrash):
                self.result(apply=True)
        self.assertEqual(sha256(target.read_bytes()), draft["expected_sha256"])
        journal_path = next((self.project / promote.STATE / "journals").glob("*.json"))
        original = json.loads(journal_path.read_text(encoding="utf-8"))
        mutations = [
            ("NaN", lambda value: value.update(errors=float("nan"))),
            ("Infinity", lambda value: value.update(errors=float("inf"))),
            ("invalid Unicode", lambda value: value.update(errors=["\ud800"])),
            ("errors object", lambda value: value.update(errors={})),
            ("status array", lambda value: value.update(status=[])),
            ("boolean version", lambda value: value.update(version=True)),
        ]
        for name, mutation in mutations:
            with self.subTest(name=name):
                altered = copy.deepcopy(original)
                mutation(altered)
                journal_path.write_text(json.dumps(altered), encoding="utf-8")
                before_files = self.snapshot()
                before_paths = {path.relative_to(self.project).as_posix() for path in self.project.rglob("*")}
                with self.assertRaises(PacketError):
                    self.result(apply=True, resume=True)
                self.assertEqual(self.snapshot(), before_files)
                self.assertEqual({path.relative_to(self.project).as_posix() for path in self.project.rglob("*")}, before_paths)
                self.assertEqual(sha256(target.read_bytes()), draft["expected_sha256"])

    def test_missing_pending_backup_key_cannot_roll_back_an_earlier_written_target(self):
        first, first_target = self.baseline()
        second = copy.deepcopy(first)
        second.update(id="second", path="md-drafts/second.DRAFT.md", target="second.md",
                      kind="document", depends_on=[first["id"]])
        (self.project / second["path"]).write_bytes((self.project / first["path"]).read_bytes())
        second_target = self.project / second["target"]
        second_bytes = b"second baseline\n"
        second_target.write_bytes(second_bytes)
        second["baseline_sha256"] = sha256(second_bytes)
        self.plan["drafts"].append(second)
        self.prepare()
        write = promote._journal_write
        def crash_after_first_written(root, relative, journal):
            write(root, relative, journal)
            if (journal["status"] == "APPLYING" and journal["actions"][0]["status"] == "WRITTEN"
                    and journal["actions"][1]["status"] == "PENDING"):
                raise SimulatedCrash()
        with mock.patch.object(promote, "_journal_write", side_effect=crash_after_first_written):
            with self.assertRaises(SimulatedCrash):
                self.result(apply=True)
        self.assertEqual(sha256(first_target.read_bytes()), first["expected_sha256"])
        journal_path = next((self.project / promote.STATE / "journals").glob("*.json"))
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        del journal["actions"][1]["backup"]
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        before_files = self.snapshot()
        before_paths = {path.relative_to(self.project).as_posix() for path in self.project.rglob("*")}
        with self.assertRaisesRegex(PacketError, "action fields"):
            self.result(apply=True, resume=True)
        self.assertEqual(self.snapshot(), before_files)
        self.assertEqual({path.relative_to(self.project).as_posix() for path in self.project.rglob("*")}, before_paths)
        self.assertEqual(sha256(first_target.read_bytes()), first["expected_sha256"])
        self.assertEqual(second_target.read_bytes(), second_bytes)

    def test_target_drift_has_explicit_cli_status(self):
        draft, target = self.baseline()
        self.prepare()
        target.write_bytes(b"unapproved drift")
        result = subprocess.run([sys.executable, str(SCRIPTS / "promote.py"), str(self.project),
                                 "--approval", str(self.approval), "--apply"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "STOPPED_DRIFTED")
        self.assertFalse((self.project / promote.STATE).exists())

    def test_active_lock_is_never_automatically_removed(self):
        self.prepare()
        state = self.project / promote.STATE
        state.mkdir()
        lock = state / "lock.json"
        lock.write_text(json.dumps({"pid": os.getpid(), "approval_sha256": "other"}), encoding="utf-8")
        before = lock.read_bytes()
        with self.assertRaisesRegex(PacketError, "lock"):
            self.result(apply=True)
        self.assertEqual(lock.read_bytes(), before)

    def test_resume_requires_an_existing_original_journal(self):
        self.prepare()
        with self.assertRaisesRegex(PacketError, "requires the journal"):
            self.result(apply=True, resume=True)
        self.assertFalse((self.project / promote.STATE).exists())


if __name__ == "__main__":
    unittest.main()
