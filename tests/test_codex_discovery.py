"""Synthetic-only regression tests. Does not discover or open live Codex history."""
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "skills/open-project/scripts/discover-sessions.py"
SPEC = importlib.util.spec_from_file_location("codex_discovery", SCRIPT)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


def meta(identity, parent=None, cwd="C:/unrelated-project"):
    payload = {"id": identity, "cwd": cwd}
    if parent is not None:
        payload["parent_thread_id"] = parent
    return {"type": "session_meta", "payload": payload}


def message(text, role="user"):
    return {"type": "response_item", "payload": {
        "type": "message", "role": role,
        "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}]}}


def event(text, role="user"):
    return {"type": "event_msg", "payload": {
        "type": "user_message" if role == "user" else "agent_message", "message": text}}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-test-", dir=SCRIPT.parent)
        self.base = Path(self.temp.name)
        self.root = self.base / "sessions"
        self.root.mkdir()

    def tearDown(self):
        assert self.base.resolve().is_relative_to(SCRIPT.parent.resolve())
        self.temp.cleanup()

    def write(self, relative, records):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
                        encoding="utf-8")
        return path

    def scan(self, keywords=None, roots=None):
        return ADAPTER.discover(roots or [self.root], keywords or ["needle"])

    def test_recursive_cross_cwd_unicode_and_literal_percent_underscore(self):
        self.write("2024/a.jsonl", [meta("opaque:not-a-uuid", cwd="C:/project-A"),
                                   message("private surrounding words 主題 %_ needle")])
        self.write("archive/2023/b.JSONL", [meta("other-id", cwd="D:/project-B"),
                                          message("主題 abc %X _Y", "assistant")])
        self.write("outside-title.jsonl", [meta("third"), message("unmatched")])
        result = self.scan(["主題", "%_"], [self.root, self.root / "archive"])
        self.assertEqual(result["coverage"]["files_inventoried"], 3)
        self.assertEqual(result["coverage"]["record_views_matching"], 2)
        self.assertEqual(result["coverage"]["keyword_hits"], 3)
        self.assertFalse(result["scope"]["claims_complete_all_codex_history"])
        self.assertEqual(len(result["scope"]["unknown_sources"]), 3)
        self.assertIn("opaque:not-a-uuid", [s["session_id"] for s in result["sessions"]])
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("private surrounding words", encoded)
        self.assertNotIn("abc %X _Y", encoded)
        self.assertTrue(all(s["review"] == {"state": "unread", "depth": 0}
                            for s in result["sessions"]))

    def test_mixedcase_alias_matches_by_default_and_original_query_is_retained(self):
        self.write("mixedcase.jsonl", [meta("mixedcase"), message("Connect LINE Bridge for this project")])
        result = self.scan(["line bridge"])
        self.assertEqual(result["coverage"]["keyword_hits"], 1)
        self.assertEqual(result["search"]["query_mode"], "unicode-casefolded-literal")
        self.assertEqual(result["search"]["keywords"], ["line bridge"])
        self.assertEqual(result["sessions"][0]["hits"][0]["keyword"], "line bridge")
        self.assertNotIn("Connect LINE Bridge", json.dumps(result))

    def test_mixed_stream_unique_event_keyword_is_discovered_with_secondary_provenance(self):
        self.write("mixed-stream.jsonl", [meta("mixed-stream"), event("needle unique project keyword"),
                                        message("visible response without that search term")])
        result = self.scan()
        self.assertEqual(result["coverage"]["keyword_hits"], 1)
        self.assertEqual(result["coverage"]["record_views_eligible"], 2)
        self.assertEqual(result["coverage"]["record_views_scanned"], 2)
        self.assertEqual(result["coverage"]["record_views_skipped"], 0)
        self.assertEqual(result["coverage"]["secondary_event_record_views"], 1)
        self.assertEqual(result["coverage"]["possible_duplicate_event_record_views"], 1)
        self.assertEqual(result["status"], "ok")
        reference = result["sessions"][0]["hits"][0]["message_ref"]
        self.assertEqual(reference["origin"], "event_msg")
        self.assertEqual(reference["line"], 2)
        self.assertEqual(reference["view"], "secondary")
        self.assertTrue(reference["possible_duplicate"])
        self.assertIn("not unique human messages", result["counter_definition"]["count_unit"])
        self.assertNotIn("unique project keyword", json.dumps(result))

    def test_response_and_event_duplicates_are_retained_as_separate_record_views(self):
        self.write("duplicate.jsonl", [meta("a"), event("needle"), message("needle"),
                                       event("needle", "assistant"), message("needle", "assistant")])
        result = self.scan()
        self.assertEqual(result["coverage"]["record_views_seen"], 4)
        self.assertEqual(result["coverage"]["record_views_eligible"], 4)
        self.assertEqual(result["coverage"]["record_views_scanned"], 4)
        self.assertEqual(result["coverage"]["record_views_skipped"], 0)
        self.assertEqual(result["coverage"]["keyword_hits"], 4)
        session = result["sessions"][0]
        self.assertEqual(session["message_source"], "response_and_event_views")
        self.assertEqual(result["coverage"]["possible_duplicate_event_record_views"], 2)
        self.assertEqual(result["coverage"]["secondary_event_record_views"], 2)
        self.assertEqual({hit["message_ref"]["origin"] for hit in session["hits"]},
                         {"response_item", "event_msg"})
        primary = [hit for hit in session["hits"] if hit["message_ref"]["view"] == "primary"]
        secondary = [hit for hit in session["hits"] if hit["message_ref"]["view"] == "secondary"]
        self.assertEqual(len(primary), 2)
        self.assertEqual(len(secondary), 2)
        self.assertTrue(all(hit["message_ref"]["possible_duplicate"] for hit in secondary))
        self.assertTrue(all(not hit["message_ref"]["possible_duplicate"] for hit in primary))

    def test_secondary_event_view_and_unverified_agent_response_skipped(self):
        self.write("legacy.jsonl", [meta("legacy"), event("needle"),
                                    event("needle", "assistant"),
                                    {"type": "response_item", "payload": {
                                        "type": "agent_message", "author": "unverified-author",
                                        "encrypted_content": "needle-SECRET", "text": "needle-SECRET"}}])
        result = self.scan(["needle", "SECRET"])
        self.assertEqual(result["coverage"]["record_views_seen"], 3)
        self.assertEqual(result["coverage"]["record_views_eligible"], 2)
        self.assertEqual(result["coverage"]["record_views_skipped"], 1)
        self.assertEqual(result["coverage"]["keyword_hits"], 2)
        self.assertEqual(result["sessions"][0]["message_source"], "event_msg")
        self.assertTrue(all(hit["message_ref"]["view"] == "secondary"
                            and not hit["message_ref"]["possible_duplicate"]
                            for hit in result["sessions"][0]["hits"]))
        self.assertNotIn("needle-SECRET", json.dumps(result))

    def test_reasoning_encrypted_tool_and_non_message_roles_never_searched_or_retained(self):
        forbidden = "REASONING_ONLY_SECRET"
        self.write("reasoning.jsonl", [
            meta("secret-test"), message("visible"),
            {"type": "response_item", "payload": {
                "type": "reasoning", "summary": [{"text": forbidden}], "encrypted_content": forbidden}},
            {"type": "response_item", "payload": {
                "type": "message", "role": "assistant",
                "content": [{"type": "encrypted_content", "text": forbidden}]}},
            {"type": "response_item", "payload": {
                "type": "message", "role": "system",
                "content": [{"type": "output_text", "text": forbidden}]}},
            {"type": "response_item", "payload": {"type": "function_call_output", "output": forbidden}},
        ])
        result = self.scan(["ONLY_SECRET"])
        self.assertEqual(result["coverage"]["record_views_eligible"], 1)
        self.assertEqual(result["coverage"]["record_views_skipped"], 4)
        self.assertEqual(result["coverage"]["keyword_hits"], 0)
        self.assertNotIn(forbidden, json.dumps(result))

    def test_bad_json_truncation_and_invalid_utf8_preserve_valid_hits_and_mark_partial(self):
        path = self.write("broken.jsonl", [meta("broken"), message("needle")])
        with path.open("ab") as output:
            output.write(b'{"type":broken}\n\xff\n{"type":"response_item"')
        result = self.scan()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["coverage"]["files_partial"], 1)
        self.assertEqual(result["coverage"]["keyword_hits"], 1)
        codes = [item["code"] for item in result["sessions"][0]["issues"]]
        self.assertEqual(codes.count("invalid_json"), 2)
        self.assertIn("invalid_utf8", codes)
        self.assertIn("missing_final_newline", codes)
        self.assertEqual(result["sessions"][0]["revision"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_identical_session_ids_with_conflicting_revisions_are_not_merged(self):
        first = self.write("a.jsonl", [meta("opaque-parent"), message("first")])
        second = self.write("b.jsonl", [meta("opaque-parent"), message("second")])
        self.write("child.jsonl", [meta("child", "opaque-parent"), message("needle")])
        result = self.scan()
        parents = [s for s in result["sessions"] if s["session_id"] == "opaque-parent"]
        self.assertEqual(len(parents), 2)
        self.assertEqual(len({s["source_id"] for s in parents}), 2)
        self.assertEqual(len({s["revision"] for s in parents}), 2)
        self.assertEqual({s["revision"] for s in parents},
                         {hashlib.sha256(first.read_bytes()).hexdigest(),
                          hashlib.sha256(second.read_bytes()).hexdigest()})
        child = next(s for s in result["sessions"] if s["session_id"] == "child")
        self.assertEqual(child["parent_link"]["status"], "ambiguous")
        closure = result["matching_parent_closure"][0]
        self.assertEqual(len(closure["ancestor_refs"]), 2)
        self.assertEqual(closure["ambiguous_parent_ids"], ["opaque-parent"])

    def test_parent_closure_includes_ancestors_and_reports_orphans_and_cycles(self):
        self.write("a.jsonl", [meta("a", "b"), message("needle")])
        self.write("b.jsonl", [meta("b", "a"), message("ancestor")])
        self.write("orphan.jsonl", [meta("orphan", "missing"), message("needle")])
        self.write("grandchild.jsonl", [meta("grandchild", "orphan"), message("needle")])
        result = self.scan()
        closures = {c["start_ref"]["session_id"]: c for c in result["matching_parent_closure"]}
        self.assertEqual([r["session_id"] for r in closures["a"]["ancestor_refs"]], ["b"])
        self.assertTrue(closures["a"]["cycle_refs"])
        self.assertEqual(closures["orphan"]["orphan_parent_ids"], ["missing"])
        self.assertEqual(closures["grandchild"]["orphan_parent_ids"], ["missing"])
        self.assertEqual([r["session_id"] for r in closures["grandchild"]["ancestor_refs"]], ["orphan"])

    def test_deep_parent_chain_does_not_depend_on_python_recursion_limit(self):
        sessions = []
        for i in range(1500):
            sessions.append({"source_id": str(i), "session_id": str(i), "revision": "hash",
                             "parent_session_id": str(i + 1) if i < 1499 else None,
                             "hits": [1] if i == 0 else []})
        closure = ADAPTER.add_parent_links(sessions)[0]
        self.assertEqual(len(closure["ancestor_refs"]), 1499)
        self.assertEqual(closure["cycle_refs"], [])

    def test_read_only_source_bytes_hash_and_mtime_unchanged(self):
        path = self.write("readonly.jsonl", [meta("read-only"), message("needle")])
        original_mode = path.stat().st_mode
        path.chmod(stat.S_IREAD)
        before = (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
        try:
            result = self.scan()
            output = self.base / "report.json"
            ADAPTER.write_new_output(output, result)
            after = (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
            self.assertEqual(before, after)
            self.assertEqual(result["sessions"][0]["revision"], hashlib.sha256(before[0]).hexdigest())
            self.assertTrue(result["sessions"][0]["snapshot"]["stable"])
        finally:
            path.chmod(original_mode)

    def test_changed_source_is_partial_even_when_readable(self):
        path = self.write("changing.jsonl", [meta("changing"), message("needle")])
        actual = ADAPTER.file_stat(path)
        changed = {**actual, "st_mtime_ns": actual["st_mtime_ns"] + 1}
        with mock.patch.object(ADAPTER, "file_stat", side_effect=[actual, changed]):
            session = ADAPTER.read_session(path, ["needle"])
        self.assertEqual(session["status"], "partial")
        self.assertFalse(session["snapshot"]["stable"])
        self.assertIn("source_changed_during_read", [i["code"] for i in session["issues"]])

    def test_read_failure_is_counted_without_message_text(self):
        path = self.write("locked.jsonl", [meta("locked"), message("needle")])
        with mock.patch.object(Path, "open", side_effect=PermissionError(13, "denied")):
            session = ADAPTER.read_session(path, ["needle"])
        self.assertEqual(session["status"], "failed")
        self.assertIsNone(session["revision"])
        self.assertEqual(session["counts"]["record_views_scanned"], 0)
        self.assertEqual(session["issues"][0]["code"], "source_read_error")

    def test_output_refuses_existing_file_and_linked_path(self):
        existing = self.base / "existing.json"
        existing.write_text("do not overwrite", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            ADAPTER.write_new_output(existing, {})
        self.assertEqual(existing.read_text(encoding="utf-8"), "do not overwrite")
        target = self.base / "would-be-linked.json"
        actual = ADAPTER.is_link
        with mock.patch.object(ADAPTER, "is_link",
                               side_effect=lambda path: path == self.base or actual(path)):
            with self.assertRaisesRegex(ValueError, "linked_output_path_refused"):
                ADAPTER.write_new_output(target, {})
        self.assertFalse(target.exists())

    def test_missing_root_is_partial_not_an_empty_success(self):
        result = self.scan(roots=[self.base / "missing"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["coverage"]["files_inventoried"], 0)
        self.assertEqual(result["coverage"]["errors"], 1)

    def test_empty_keyword_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonempty_keyword"):
            self.scan([""])

    def test_cli_explicit_roots_repeated_keywords_new_output_and_partial_exit(self):
        self.write("cli.jsonl", [meta("cli"), message("主題 needle %_")])
        second = self.base / "second-root"
        second.mkdir()
        (second / "bad.jsonl").write_bytes(b'{"broken":')
        output = self.base / "nested" / "result.json"
        command = [sys.executable, str(SCRIPT), "--sessions-root", str(self.root),
                   "--sessions-root", str(second), "--keyword", "主題",
                   "--keyword", "%_", "--output", str(output),
                   "--source-root-kind", "synthetic-fixture"]
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 2, process.stderr)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["coverage"]["roots_requested"], 2)
        self.assertEqual(result["coverage"]["keyword_hits"], 2)
        self.assertTrue(all(root["kind"] == "synthetic-fixture" for root in result["scope"]["roots"]))
        old_bytes = output.read_bytes()
        repeated = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(repeated.returncode, 1)
        self.assertEqual(output.read_bytes(), old_bytes)


if __name__ == "__main__":
    unittest.main()