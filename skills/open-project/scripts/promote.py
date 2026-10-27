#!/usr/bin/env python3
"""Reviewable, approval-bound promotion of a validated open-project packet.

An approval is evidence of a recorded decision. It does not grant operating-system
permission. Dry runs only read files; target writes require --apply.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import uuid

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from plan_contract import (PacketError, load_plan, validate_plan, resolve_inside,
                           packet_digest, read_draft, expected_content)

STATE = ".open-project-promotion"
NOT_EXISTS = "NOT_EXISTS"
RESOLVED = {"COMMITTED", "FAILED_RECOVERED"}
JOURNAL_STATES = {"PREPARED", "APPLYING", "COMMITTED", "FAILED_RECOVERED", "FAILED_UNRECOVERED"}
APPROVAL_FIELDS = {"plan_id", "revision", "packet_sha256", "approved_by", "approved_at", "actions"}
ACTION_FIELDS = {"draft_id", "target", "draft_sha256", "baseline_sha256", "expected_sha256", "transforms", "effects"}
JOURNAL_FIELDS = {"version", "plan_id", "revision", "packet_sha256", "approval_sha256", "approval",
                  "status", "backup_id", "actions", "errors"}
JOURNAL_ACTION_FIELDS = {"draft_id", "target", "baseline_sha256", "expected_sha256", "status", "backup"}
ACTION_STATES = {"NO_OP", "PENDING", "BACKUP_INTENT", "WRITE_INTENT", "WRITTEN", "ROLLED_BACK", "ROLLBACK_FAILED"}


class TargetDrift(PacketError):
    status = "STOPPED_DRIFTED"



def _error_message(exc):
    if isinstance(exc, PacketError):
        return str(exc)
    if isinstance(exc, OSError):
        detail = "filesystem operation failed (" + type(exc).__name__
        if exc.errno is not None:
            detail += ", errno " + str(exc.errno)
        detail += ")"
        if exc.filename is not None:
            detail += ": " + str(exc.filename)
        return detail
    return "promotion operation failed (" + type(exc).__name__ + ")"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (UnicodeError, ValueError) as exc:
        raise PacketError("invalid canonical JSON content") from exc


def _plain_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PacketError("duplicate JSON key in approval or journal")
            result[key] = value
        return result
    def reject_constant(value):
        raise PacketError("non-finite JSON constant")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                           parse_constant=reject_constant)
        # Validate every key and nested value before the caller can mutate state.
        # UTF-8 encoding also rejects escaped unpaired Unicode surrogates.
        _canonical(value)
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        raise PacketError("cannot read JSON " + str(path) + ": " + str(exc)) from exc


def _check_plain(path):
    """Check every existing ancestor without resolving away links or junctions."""
    absolute = Path(os.path.abspath(path))
    for component in reversed([absolute, *absolute.parents]):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PacketError("symlink or reparse point is unsafe: " + str(component))
    return absolute


def _project(project):
    root = _check_plain(Path(project))
    if not root.is_dir():
        raise PacketError("project must be an existing directory")
    return root


def _inside(root, relative):
    path = Path(resolve_inside(root, relative))
    _check_plain(path)
    return path


def _hash_file(path):
    _check_plain(path)
    try:
        if not path.exists():
            return NOT_EXISTS
        if not path.is_file():
            raise PacketError("expected a regular file: " + str(path))
        return digest(path.read_bytes())
    except OSError as exc:
        raise PacketError("cannot inspect file " + str(path) + ": " + str(exc)) from exc


def _mkdirs(root, relative):
    if relative == ".":
        return root
    destination = _inside(root, relative)
    components = destination.relative_to(root).parts
    current = root
    for component in components:
        current = current / component
        _check_plain(current)
        try:
            current.mkdir()
        except FileExistsError:
            if not current.is_dir():
                raise PacketError("directory required: " + str(current))
        _check_plain(current)
    return destination


def _fsync_dir(path):
    # Windows does not generally permit opening directories with os.open.
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def _write_exclusive(path, data):
    _check_plain(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_dir(path.parent)



def _backup_write(root, relative, data):
    """Publish complete backup bytes atomically without replacing any destination."""
    destination = _inside(root, relative)
    _mkdirs(root, destination.parent.relative_to(root).as_posix())
    temporary = destination.parent / (".backup-" + uuid.uuid4().hex + ".tmp")
    _write_exclusive(temporary, data)
    try:
        _inside(root, relative)
        _check_plain(temporary)
        if os.name == "nt":
            # Windows rename() refuses an existing destination; unlike replace().
            os.rename(temporary, destination)
        else:
            # POSIX rename() can overwrite, so publish through an exclusive link.
            os.link(temporary, destination)
        _fsync_dir(destination.parent)
    finally:
        if temporary.exists():
            _check_plain(temporary)
            temporary.unlink()


def _private_metadata(root, create=False):
    path = _inside(root, STATE + "/.gitignore")
    if path.exists():
        if not path.is_file() or path.read_bytes() != b"*\n":
            raise PacketError("unexpected existing promotion .gitignore; no overwrite allowed")
    elif create:
        try:
            _write_exclusive(path, b"*\n")
        except FileExistsError:
            _private_metadata(root)


def _replace(source, destination):
    """Atomic replacement boundary; no fault-injection CLI switches."""
    _check_plain(source)
    _check_plain(destination)
    os.replace(source, destination)
    _fsync_dir(destination.parent)


def _atomic_write(root, relative, data):
    destination = _inside(root, relative)
    parent_rel = destination.parent.relative_to(root).as_posix()
    _mkdirs(root, parent_rel)
    temporary = destination.parent / (".promote-" + uuid.uuid4().hex + ".tmp")
    _write_exclusive(temporary, data)
    try:
        _inside(root, relative)
        _replace(temporary, destination)
    finally:
        if temporary.exists():
            _check_plain(temporary)
            temporary.unlink()


def _journal_write(root, relative, journal):
    _atomic_write(root, relative, _canonical(journal) + b"\n")


def _pid_alive(pid):
    if type(pid) is not int or pid <= 0:
        return True
    if os.name == "nt":
        # os.kill(pid, 0) can terminate a process on Windows. Query a handle instead.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # unknown/access denied => busy
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


@contextmanager
def _lock(root, approval_hash, resume):
    _mkdirs(root, STATE)
    lock = _inside(root, STATE + "/lock.json")
    identity = {"pid": os.getpid(), "approval_sha256": approval_hash, "token": uuid.uuid4().hex}
    if lock.exists():
        previous = _plain_json(lock)
        if (not resume or not isinstance(previous, dict)
                or previous.get("approval_sha256") != approval_hash
                or _pid_alive(previous.get("pid"))):
            raise PacketError("promotion lock exists; another operation may be active")
        _check_plain(lock)
        lock.unlink()
    try:
        _write_exclusive(lock, _canonical(identity))
    except FileExistsError as exc:
        raise PacketError("promotion lock was acquired by another operation") from exc
    try:
        yield
    finally:
        if lock.exists():
            current = _plain_json(lock)
            if current == identity:
                lock.unlink()
                _fsync_dir(lock.parent)


def _gate(root, plan):
    spec = importlib.util.spec_from_file_location("open_project_promotion_gate", SCRIPTS / "gate-check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gate = module.inspect_packet(root, plan)
    if not gate["ready"]:
        raise PacketError("packet gate is not ready: " + "; ".join(gate["errors"]))
    if gate["packet_sha256"] != packet_digest(plan):
        raise PacketError("gate packet digest does not match the plan")
    return gate


def _approval(root, plan, approval_path):
    path = _check_plain(Path(approval_path))
    if not path.is_file():
        raise PacketError("approval must be a regular JSON file")
    value = _plain_json(path)
    if not isinstance(value, dict) or set(value) != APPROVAL_FIELDS:
        raise PacketError("approval fields do not match the approval contract")
    for key in ("plan_id", "revision", "packet_sha256"):
        expected = packet_digest(plan) if key == "packet_sha256" else plan[key]
        if type(value[key]) is not type(expected) or value[key] != expected:
            raise PacketError("approval " + key + " does not match the packet")
    if not isinstance(value["approved_by"], str) or not value["approved_by"].strip():
        raise PacketError("approved_by must record a nonblank decision maker")
    try:
        when = datetime.fromisoformat(value["approved_at"].replace("Z", "+00:00"))
        if when.utcoffset() is None:
            raise ValueError("timezone offset required")
    except (ValueError, TypeError, AttributeError) as exc:
        raise PacketError("approved_at must be ISO 8601 with a timezone offset") from exc
    if not isinstance(value["actions"], list) or not value["actions"]:
        raise PacketError("approval must select at least one action")
    drafts = {draft["id"]: draft for draft in plan["drafts"]}
    selected = {}
    for action in value["actions"]:
        if not isinstance(action, dict) or set(action) != ACTION_FIELDS:
            raise PacketError("approval action fields do not match the contract")
        draft_id = action["draft_id"]
        if not isinstance(draft_id, str) or draft_id not in drafts or draft_id in selected:
            raise PacketError("approval contains an unknown or duplicate draft")
        draft = drafts[draft_id]
        expected = {"draft_id": draft_id, "target": draft["target"], "draft_sha256": draft["sha256"],
                    "baseline_sha256": draft["baseline_sha256"], "expected_sha256": draft["expected_sha256"],
                    "transforms": draft["transforms"], "effects": ["write_file"]}
        if action != expected:
            raise PacketError("approval action does not exactly match draft " + draft_id)
        if action["target"].split("/")[0].casefold() == STATE.casefold():
            raise PacketError("promotion bookkeeping cannot be a target")
        selected[draft_id] = draft
    ordered, visited = [], set()
    def visit(draft_id):
        if draft_id in visited:
            return
        for dependency in selected[draft_id].get("depends_on", []):
            if dependency not in selected:
                raise PacketError("approval omits dependency " + dependency + " for " + draft_id)
            visit(dependency)
        visited.add(draft_id)
        ordered.append(selected[draft_id])
    for draft_id in selected:
        visit(draft_id)
    return value, digest(_canonical(value)), ordered


def _content(root, drafts):
    content = {}
    for draft in drafts:
        raw = read_draft(root, draft)
        if digest(raw) != draft["sha256"]:
            raise PacketError("draft has changed: " + draft["id"])
        transformed = expected_content(draft, raw)
        if digest(transformed) != draft["expected_sha256"]:
            raise PacketError("expected content hash mismatch: " + draft["id"])
        content[draft["id"]] = transformed
    return content


def _preflight(root, drafts):
    actions = []
    for draft in drafts:
        current = _hash_file(_inside(root, draft["target"]))
        if current not in (draft["baseline_sha256"], draft["expected_sha256"]):
            raise TargetDrift("target drift: " + draft["target"])
        actions.append({"draft_id": draft["id"], "target": draft["target"],
                        "baseline_sha256": draft["baseline_sha256"], "expected_sha256": draft["expected_sha256"],
                        "status": "NO_OP" if current == draft["expected_sha256"] else "PENDING", "backup": None})
    return actions


def _journal_path(plan, approval_hash):
    token = digest(str(plan["plan_id"]).encode("utf-8"))[:20]
    return STATE + "/journals/" + token + "-" + approval_hash + ".json"



def _validate_journal_shape(journal):
    _canonical(journal)
    if not isinstance(journal, dict) or set(journal) != JOURNAL_FIELDS:
        raise PacketError("promotion journal fields do not match the contract")
    if type(journal["version"]) is not int or journal["version"] != 1:
        raise PacketError("unsupported promotion journal version")
    if not isinstance(journal["status"], str) or journal["status"] not in JOURNAL_STATES:
        raise PacketError("invalid promotion journal state")
    for field in ("plan_id", "revision", "packet_sha256", "approval_sha256", "backup_id"):
        if not isinstance(journal[field], str) or not journal[field].strip():
            raise PacketError("invalid promotion journal " + field)
    if not isinstance(journal["approval"], dict):
        raise PacketError("promotion journal approval must be an object")
    if not isinstance(journal["errors"], list) or any(not isinstance(error, str) for error in journal["errors"]):
        raise PacketError("promotion journal errors must be an array of strings")
    if not isinstance(journal["actions"], list) or not journal["actions"]:
        raise PacketError("promotion journal actions must be a nonempty array")
    for action in journal["actions"]:
        if not isinstance(action, dict) or set(action) != JOURNAL_ACTION_FIELDS:
            raise PacketError("promotion journal action fields do not match the contract")
        for field in ("draft_id", "target", "baseline_sha256", "expected_sha256"):
            if not isinstance(action[field], str) or not action[field].strip():
                raise PacketError("invalid promotion journal action " + field)
        if not isinstance(action["status"], str) or action["status"] not in ACTION_STATES:
            raise PacketError("invalid promotion journal action state")
        if action["backup"] is not None and not isinstance(action["backup"], str):
            raise PacketError("promotion journal backup must be a path or null")
    return journal


def _existing(root, journal_rel):
    directory = _inside(root, STATE + "/journals")
    if not directory.exists():
        return None
    if not directory.is_dir():
        raise PacketError("journal directory is not a directory")
    existing = None
    for path in directory.iterdir():
        _check_plain(path)
        if path.suffix != ".json":
            continue
        journal = _validate_journal_shape(_plain_json(path))
        if path == _inside(root, journal_rel):
            existing = journal
        elif journal["status"] not in RESOLVED:
            raise PacketError("unresolved promotion journal requires its original approval and --resume: " + path.name)
    return existing


def _validate_resume(root, journal, plan, approval_hash, actions):
    _validate_journal_shape(journal)
    if (journal.get("version") != 1 or journal.get("plan_id") != plan["plan_id"]
            or journal.get("revision") != plan["revision"]
            or journal.get("packet_sha256") != packet_digest(plan)
            or journal.get("approval_sha256") != approval_hash):
        raise PacketError("resume journal does not match this packet and approval")
    if journal.get("status") not in JOURNAL_STATES:
        raise PacketError("invalid resume journal state")
    if digest(_canonical(journal.get("approval"))) != approval_hash:
        raise PacketError("resume journal decision evidence has changed")
    backup_id = journal.get("backup_id")
    if (not isinstance(backup_id, str) or len(backup_id) != 32
            or any(c not in "0123456789abcdef" for c in backup_id)):
        raise PacketError("invalid journal backup identity")
    previous = journal.get("actions")
    if not isinstance(previous, list) or len(previous) != len(actions):
        raise PacketError("resume journal action set has changed")
    for old, fresh in zip(previous, actions):
        if not isinstance(old, dict):
            raise PacketError("invalid resume journal action")
        for field in ("draft_id", "target", "baseline_sha256", "expected_sha256"):
            if old.get(field) != fresh[field]:
                raise PacketError("resume journal action does not match approval")
        phase = old.get("status")
        if journal["status"] == "COMMITTED" and phase not in {"NO_OP", "WRITTEN"}:
            raise PacketError("committed journal has an incomplete action")
        current = _hash_file(_inside(root, old["target"]))
        baseline, expected = old["baseline_sha256"], old["expected_sha256"]
        allowed = {"NO_OP": {expected}, "WRITTEN": {expected}, "PENDING": {baseline},
                   "BACKUP_INTENT": {baseline}, "WRITE_INTENT": {baseline, expected}, "ROLLED_BACK": {baseline},
                   "ROLLBACK_FAILED": {baseline, expected}}
        if phase not in allowed or current not in allowed[phase]:
            raise TargetDrift("target drift since journal: " + old["target"])
        backup = old.get("backup")
        if backup is not None:
            expected_prefix = STATE + "/backups/" + journal.get("backup_id", "") + "/"
            if not isinstance(backup, str) or not backup.startswith(expected_prefix) or backup != expected_prefix + old["target"]:
                raise PacketError("journal backup path is invalid")
            actual_backup = _hash_file(_inside(root, backup))
            if (baseline == NOT_EXISTS or (actual_backup != baseline
                    and not (phase == "BACKUP_INTENT" and actual_backup == NOT_EXISTS))):
                raise PacketError("backup has changed: " + old["target"])
        elif phase in {"WRITE_INTENT", "WRITTEN", "ROLLED_BACK", "ROLLBACK_FAILED"} and baseline != NOT_EXISTS:
            raise PacketError("resume journal is missing a required backup")
    return journal


def _rollback(root, journal):
    errors = []
    for action in reversed(journal["actions"]):
        if action["status"] == "NO_OP":
            try:
                if _hash_file(_inside(root, action["target"])) != action["expected_sha256"]:
                    raise PacketError("no-op target changed")
            except Exception as exc:
                errors.append(action["target"] + ": " + _error_message(exc))
            continue
        try:
            target = _inside(root, action["target"])
            current = _hash_file(target)
            baseline, expected = action["baseline_sha256"], action["expected_sha256"]
            if current == baseline:
                if action["status"] not in {"PENDING", "BACKUP_INTENT"}:
                    action["status"] = "ROLLED_BACK"
                continue
            if current != expected or action["status"] not in {"WRITE_INTENT", "WRITTEN", "ROLLBACK_FAILED"}:
                raise PacketError("target changed outside this promotion; rollback refused")
            if baseline == NOT_EXISTS:
                target.unlink()
                _fsync_dir(target.parent)
            else:
                backup = _inside(root, action["backup"])
                data = backup.read_bytes()
                if digest(data) != baseline:
                    raise PacketError("backup hash mismatch")
                _atomic_write(root, action["target"], data)
            if _hash_file(target) != baseline:
                raise PacketError("rollback verification failed")
            action["status"] = "ROLLED_BACK"
        except Exception as exc:
            action["status"] = "ROLLBACK_FAILED"
            errors.append(action["target"] + ": " + _error_message(exc))
    return errors


def promote(project, approval_path, *, apply=False, resume=False):
    """Return a structured result; validation failures raise PacketError."""
    root = _project(project)
    for internal in (STATE, STATE + "/journals", STATE + "/backups", STATE + "/lock.json"):
        _inside(root, internal)
    _private_metadata(root)
    plan = load_plan(root)
    validate_plan(plan)
    gate = _gate(root, plan)
    approval, approval_hash, drafts = _approval(root, plan, approval_path)
    content = _content(root, drafts)
    actions = _preflight(root, drafts)
    journal_rel = _journal_path(plan, approval_hash)
    existing = _existing(root, journal_rel)
    if existing is not None:
        if existing.get("status") != "COMMITTED" and not resume:
            raise PacketError("existing promotion journal requires --resume")
        _validate_resume(root, existing, plan, approval_hash, actions)
    elif resume:
        raise PacketError("--resume requires the journal and its original approval")
    result = {"status": "DRY_RUN", "ready": True, "packet_sha256": packet_digest(plan),
              "approval_sha256": approval_hash, "warnings": gate.get("warnings", []),
              "actions": actions, "decision_evidence_only": True}
    if not apply:
        return result
    with _lock(root, approval_hash, resume):
        _private_metadata(root, create=True)
        # Repeat all reads under the cooperative lock before creating a journal.
        latest_plan = load_plan(root)
        if packet_digest(latest_plan) != packet_digest(plan):
            raise PacketError("packet changed before application")
        _gate(root, latest_plan)
        latest_approval, latest_hash, _ = _approval(root, latest_plan, approval_path)
        if latest_hash != approval_hash:
            raise PacketError("approval changed before application")
        content = _content(root, drafts)
        actions = _preflight(root, drafts)
        existing = _existing(root, journal_rel)
        if existing is not None:
            if existing.get("status") != "COMMITTED" and not resume:
                raise PacketError("existing promotion journal requires --resume")
            journal = _validate_resume(root, existing, plan, approval_hash, actions)
            if journal["status"] == "COMMITTED":
                return {**result, "status": "NO_OP", "actions": journal["actions"], "journal": journal_rel}
        else:
            if resume:
                raise PacketError("resume journal disappeared")
            backup_id = uuid.uuid4().hex
            backup_root = _inside(root, STATE + "/backups/" + backup_id)
            if backup_root.exists():
                raise PacketError("backup directory collision; no files were overwritten")
            journal = {"version": 1, "plan_id": plan["plan_id"], "revision": plan["revision"],
                       "packet_sha256": packet_digest(plan), "approval_sha256": approval_hash,
                       "approval": approval, "status": "PREPARED", "backup_id": backup_id,
                       "actions": actions, "errors": []}
            _journal_write(root, journal_rel, journal)
        try:
            journal["status"] = "APPLYING"
            _journal_write(root, journal_rel, journal)
            for action in journal["actions"]:
                target = _inside(root, action["target"])
                current = _hash_file(target)
                if action["status"] == "NO_OP":
                    if current != action["expected_sha256"]:
                        raise TargetDrift("target drift before no-op: " + action["target"])
                    continue
                if action["status"] in {"WRITE_INTENT", "WRITTEN", "ROLLBACK_FAILED"} and current == action["expected_sha256"]:
                    action["status"] = "WRITTEN"
                    _journal_write(root, journal_rel, journal)
                    continue
                if current != action["baseline_sha256"]:
                    raise TargetDrift("target drift before write: " + action["target"])
                if current != NOT_EXISTS:
                    new_backup = action["backup"] is None
                    if new_backup:
                        action["backup"] = STATE + "/backups/" + journal["backup_id"] + "/" + action["target"]
                        action["status"] = "BACKUP_INTENT"
                        _journal_write(root, journal_rel, journal)
                    backup = _inside(root, action["backup"])
                    _mkdirs(root, backup.parent.relative_to(root).as_posix())
                    if new_backup or not backup.exists():
                        raw = target.read_bytes()
                        if digest(raw) != current:
                            raise TargetDrift("target changed while backing up: " + action["target"])
                        _backup_write(root, action["backup"], raw)
                    if _hash_file(backup) != current:
                        raise PacketError("backup verification failed")
                action["status"] = "WRITE_INTENT"
                _journal_write(root, journal_rel, journal)
                if _hash_file(_inside(root, action["target"])) != action["baseline_sha256"]:
                    raise TargetDrift("target drift after backup: " + action["target"])
                _atomic_write(root, action["target"], content[action["draft_id"]])
                if _hash_file(target) != action["expected_sha256"]:
                    raise PacketError("write verification failed: " + action["target"])
                action["status"] = "WRITTEN"
                _journal_write(root, journal_rel, journal)
            for action in journal["actions"]:
                if _hash_file(_inside(root, action["target"])) != action["expected_sha256"]:
                    raise TargetDrift("final target verification failed: " + action["target"])
            journal["status"] = "COMMITTED"
            _journal_write(root, journal_rel, journal)
            return {**result, "status": "COMMITTED", "actions": journal["actions"], "journal": journal_rel}
        except Exception as exc:
            rollback_errors = _rollback(root, journal)
            journal["status"] = "FAILED_UNRECOVERED" if rollback_errors else "FAILED_RECOVERED"
            journal["errors"] = [_error_message(exc), *rollback_errors]
            persisted = True
            try:
                _journal_write(root, journal_rel, journal)
            except Exception as journal_error:
                persisted = False
                journal["errors"].append("could not persist recovery journal: " + _error_message(journal_error))
            return {**result, "status": journal["status"], "ready": False, "actions": journal["actions"],
                    "journal": journal_rel, "journal_persisted": persisted, "recovery_scope": "target_file_bytes",
                    "empty_parent_directories_may_remain": True, "errors": journal["errors"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="write approved files (default: read-only dry run)")
    parser.add_argument("--resume", action="store_true", help="resume the same packet and recorded approval")
    args = parser.parse_args(argv)
    try:
        result = promote(args.project, args.approval, apply=args.apply, resume=args.resume)
    except (PacketError, OSError, ValueError) as exc:
        print(json.dumps({"status": getattr(exc, "status", "REJECTED"), "ready": False, "errors": [_error_message(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"].startswith("FAILED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
