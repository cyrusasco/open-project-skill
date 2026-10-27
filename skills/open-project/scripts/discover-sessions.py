#!/usr/bin/env python3
"""Read explicitly supplied Codex JSONL roots; emit references, never message text.

This inventories local files, not Codex app/cloud history. Search is a
Unicode casefolded literal substring within each supported visible text item.
All supported response and visible event record views are searched.
No Codex command, configuration change, or source-file write is performed.
"""
import argparse
import hashlib
import json
import os
import stat
import sys
from collections import defaultdict
from pathlib import Path

SCHEMA_VERSION = "codex-jsonl-discovery/v1"


def is_link(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def file_stat(path):
    info = path.stat()
    return {key: getattr(info, key) for key in
            ("st_size", "st_mtime_ns", "st_ctime_ns", "st_dev", "st_ino")}


def issue(code, line=None, severity="error", **details):
    result = {"code": code, "severity": severity}
    if line is not None:
        result["line"] = line
    result.update(details)
    return result


def reference(session):
    return {key: session[key] for key in ("source_id", "session_id", "revision")}


def ref_key(session):
    return (session["source_id"], session["session_id"], session["revision"])


def inventory(roots):
    files, problems, seen = [], [], set()
    for root in roots:
        try:
            for ancestor in (root, *root.parents):
                if is_link(ancestor):
                    raise ValueError("linked_source_root")
            if not root.is_dir():
                raise ValueError("source_root_not_directory")

            def walk_error(exc):
                problems.append(issue("inventory_read_error", path=exc.filename, errno=exc.errno))

            for directory, directories, filenames in os.walk(
                    root, followlinks=False, onerror=walk_error):
                for name in list(directories):
                    path = Path(directory) / name
                    try:
                        linked = is_link(path)
                    except OSError as exc:
                        directories.remove(name)
                        problems.append(issue("inventory_stat_error", path=str(path), errno=exc.errno))
                        continue
                    if linked:
                        directories.remove(name)
                        problems.append(issue("linked_directory_skipped", path=str(path)))
                for name in filenames:
                    if not name.lower().endswith(".jsonl"):
                        continue
                    path = Path(directory) / name
                    key = os.path.normcase(os.path.abspath(path))
                    if key not in seen:
                        seen.add(key)
                        files.append(path)
        except (OSError, ValueError) as exc:
            problems.append(issue(str(exc) if isinstance(exc, ValueError) else "source_root_read_error",
                                  path=str(root),
                                  **({"errno": exc.errno} if isinstance(exc, OSError) else {})))
    return sorted(files, key=lambda path: os.path.normcase(str(path))), problems


def visible_response(payload):
    if (not isinstance(payload, dict) or payload.get("type") != "message"
            or payload.get("role") not in ("user", "assistant")):
        return None
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    texts = [item["text"] for item in content if isinstance(item, dict)
             and item.get("type") in ("input_text", "output_text")
             and isinstance(item.get("text"), str)]
    return (payload["role"], texts) if texts else None


def visible_event(payload):
    if not isinstance(payload, dict):
        return None
    role = {"user_message": "user", "agent_message": "assistant"}.get(payload.get("type"))
    if not role:
        return None
    text = payload.get("message")
    if not isinstance(text, str):
        text = payload.get("text")
    return (role, [text]) if isinstance(text, str) else None


def read_session(path, keywords):
    canonical = os.path.normcase(os.path.abspath(path))
    session = {
        "source_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "path": str(path), "session_id": None, "parent_session_id": None,
        "revision": None, "status": "partial", "issues": [], "hits": [],
        "review": {"state": "unread", "depth": 0},
        "snapshot": {"before": None, "after": None, "bytes_read": 0,
                     "stable": False, "kind": "per-file-stat-check"},
        "counts": {"record_views_seen": 0, "record_views_eligible": 0, "record_views_scanned": 0,
                   "record_views_skipped": 0, "record_views_matching": 0, "keyword_hits": 0,
                   "secondary_event_record_views": 0, "possible_duplicate_event_record_views": 0},
    }
    try:
        if is_link(path):
            session["issues"].append(issue("linked_file_skipped"))
            session["status"] = "failed"
            return session
        session["snapshot"]["before"] = file_stat(path)
        with path.open("rb") as stream:
            data = stream.read()
        session["revision"] = hashlib.sha256(data).hexdigest()
        session["snapshot"]["bytes_read"] = len(data)
        session["snapshot"]["after"] = file_stat(path)
        session["snapshot"]["stable"] = (
            session["snapshot"]["before"] == session["snapshot"]["after"]
            and len(data) == session["snapshot"]["before"]["st_size"])
        if not session["snapshot"]["stable"]:
            session["issues"].append(issue("source_changed_during_read"))
    except OSError as exc:
        session["issues"].append(issue("source_read_error", errno=exc.errno))
        session["status"] = "failed"
        return session
    if data and not data.endswith(b"\n"):
        session["issues"].append(issue("missing_final_newline", severity="warning"))

    responses, events, metadata = [], [], None
    for line_number, raw in enumerate(data.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError:
            session["issues"].append(issue("invalid_utf8", line_number))
            continue
        except json.JSONDecodeError as exc:
            session["issues"].append(issue("invalid_json", line_number, column=exc.colno))
            continue
        if not isinstance(record, dict):
            session["issues"].append(issue("invalid_record_type", line_number))
            continue
        kind, payload = record.get("type"), record.get("payload")
        if kind == "session_meta" and isinstance(payload, dict):
            identity = payload.get("id", payload.get("session_id"))
            parent = payload.get("parent_thread_id")
            if not isinstance(identity, str) or not identity:
                session["issues"].append(issue("invalid_session_id", line_number))
                continue
            if parent is not None and not isinstance(parent, str):
                session["issues"].append(issue("invalid_parent_id", line_number))
                parent = None
            candidate = (identity, parent)
            if metadata is not None and metadata != candidate:
                session["issues"].append(issue("conflicting_session_metadata", line_number))
            if metadata is None:
                metadata = candidate
                session["session_id"], session["parent_session_id"] = candidate
        elif kind == "response_item":
            session["counts"]["record_views_seen"] += 1
            message = visible_response(payload)
            if message is not None:
                responses.append((line_number, "response_item", *message))
        elif (kind == "event_msg" and isinstance(payload, dict)
              and payload.get("type") in ("user_message", "agent_message")):
            session["counts"]["record_views_seen"] += 1
            message = visible_event(payload)
            if message is not None:
                events.append((line_number, "event_msg", *message))
    if metadata is None:
        session["issues"].append(issue("missing_session_metadata"))
    # Search both representations: an event can contain unique project text.
    # Keep view provenance instead of guessing which repeated texts are one message.
    selected = responses + events
    session["message_source"] = ("response_and_event_views" if responses and events else
                                 "response_item" if responses else "event_msg")
    session["counts"]["secondary_event_record_views"] = len(events)
    session["counts"]["possible_duplicate_event_record_views"] = len(events) if responses else 0
    session["view_notes"] = ([{
        "code": "secondary_event_view_may_duplicate_primary",
        "record_views": len(events)
    }] if responses and events else [])
    counts = session["counts"]
    counts["record_views_eligible"] = counts["record_views_scanned"] = len(selected)
    counts["record_views_skipped"] = counts["record_views_seen"] - len(selected)
    folded_keywords = [(keyword, keyword.casefold()) for keyword in keywords]
    for line_number, origin, role, texts in selected:
        matched = False
        folded_texts = [text.casefold() for text in texts]
        for keyword, folded_keyword in folded_keywords:
            occurrences = sum(text.count(folded_keyword) for text in folded_texts)
            if occurrences:
                matched = True
                session["hits"].append({
                    "keyword": keyword, "occurrences": occurrences,
                    "message_ref": {**reference(session), "line": line_number,
                                    "origin": origin, "role": role,
                                    "view": "primary" if origin == "response_item" else "secondary",
                                    "possible_duplicate": origin == "event_msg" and bool(responses)}})
        counts["record_views_matching"] += int(matched)
    counts["keyword_hits"] = len(session["hits"])
    session["status"] = "partial" if session["issues"] else "ok"
    return session


def add_parent_links(sessions):
    by_id = defaultdict(list)
    for session in sessions:
        if session["session_id"] is not None:
            by_id[session["session_id"]].append(session)
    for session in sessions:
        parent = session["parent_session_id"]
        candidates = by_id.get(parent, []) if parent is not None else []
        session["parent_link"] = {
            "status": "root" if parent is None else (
                "orphan" if not candidates else "resolved" if len(candidates) == 1 else "ambiguous"),
            "candidate_refs": [reference(candidate) for candidate in candidates]}
    closures = []
    for start in sessions:
        if not start["hits"]:
            continue
        ancestors, orphans, ambiguous, cycles = {}, set(), set(), {}
        visited, active = set(), set()
        pending = [(start, False)]
        while pending:
            node, leaving = pending.pop()
            key = ref_key(node)
            if leaving:
                active.remove(key)
                visited.add(key)
                continue
            if key in active:
                cycles[key] = reference(node)
                continue
            if key in visited:
                continue
            active.add(key)
            pending.append((node, True))
            parent = node["parent_session_id"]
            candidates = by_id.get(parent, []) if parent is not None else []
            if parent is not None and not candidates:
                orphans.add(parent)
            if len(candidates) > 1:
                ambiguous.add(parent)
            for candidate in reversed(candidates):
                if ref_key(candidate) != ref_key(start):
                    ancestors[ref_key(candidate)] = reference(candidate)
                pending.append((candidate, False))

        closures.append({"start_ref": reference(start), "ancestor_refs": list(ancestors.values()),
                         "orphan_parent_ids": sorted(orphans),
                         "ambiguous_parent_ids": sorted(ambiguous),
                         "cycle_refs": list(cycles.values())})
    return closures


def discover(roots, keywords, source_root_kind="explicit-local-jsonl-root"):
    roots = list(dict.fromkeys(Path(os.path.abspath(root)) for root in roots))
    keywords = list(dict.fromkeys(keywords))
    if not keywords or any(not isinstance(word, str) or not word for word in keywords):
        raise ValueError("at_least_one_nonempty_keyword_required")
    paths, problems = inventory(roots)
    sessions = [read_session(path, keywords) for path in paths]
    closures = add_parent_links(sessions)
    issues = problems + [item for session in sessions for item in session["issues"]]
    coverage = {
        "roots_requested": len(roots), "files_inventoried": len(paths),
        "files_attempted": len(sessions),
        "files_read": sum(item["revision"] is not None for item in sessions),
        "files_stable": sum(item["snapshot"]["stable"] for item in sessions),
        "files_partial": sum(item["status"] == "partial" for item in sessions),
        "files_failed": sum(item["status"] == "failed" for item in sessions),
        "files_matching": sum(bool(item["hits"]) for item in sessions),
        "errors": sum(item["severity"] == "error" for item in issues),
        "warnings": sum(item["severity"] == "warning" for item in issues)}
    for key in ("record_views_seen", "record_views_eligible", "record_views_scanned", "record_views_skipped",
                "record_views_matching", "keyword_hits",
                "secondary_event_record_views", "possible_duplicate_event_record_views"):
        coverage[key] = sum(item["counts"][key] for item in sessions)
    return {
        "schema_version": SCHEMA_VERSION, "status": "partial" if issues else "ok",
        "scope": {
            "roots": [{"path": str(root), "kind": source_root_kind} for root in roots],
            "inventory": "All recursive .jsonl files in explicitly supplied roots; no cwd/title filter",
            "unknown_sources": ["Other local Codex history roots not supplied",
                                "Codex app stores not represented by these JSONL files",
                                "Codex cloud/remote history not represented by these JSONL files"],
            "claims_complete_all_codex_history": False,
            "snapshot_limit": "Per-file byte hash and before/after stat; not an atomic database snapshot",
            "unsupported_content": "Reasoning, encrypted content, tools, and unverified formats are skipped",
            "review_state": "Discovery does not mark conversations as reviewed; initial depth is zero"},
        "search": {
            "keywords": keywords, "query_mode": "unicode-casefolded-literal",
            "mode": "Unicode casefolded literal substring per visible text item; original queries retained",
            "event_policy": "Search every supported response view as primary and every supported visible event view as secondary; retain line and origin references for both",
            "view_count_limit": "Record views are not unique human messages; secondary event views may duplicate primary views, and no text-based deduplication is attempted",
            "retained_content": "References and occurrence counts only; no snippets or message bodies"},
        "counter_definition": {
            "count_unit": "Record views, not unique human messages; both response and event representations are counted",
            "record_views_seen": "All response_item records plus event user_message/agent_message records",
            "record_views_eligible": "Every supported visible user/assistant response or event record view",
            "record_views_skipped": "Seen records minus eligible views; reasoning, encrypted content, tools and unverified formats are skipped",
            "keyword_hits": "Distinct original keyword/record-view matches; casefolded occurrences counted separately per hit",
            "secondary_event_record_views": "Supported visible event views, all searched with secondary provenance",
            "possible_duplicate_event_record_views": "Secondary event views in files that also contain primary response views; duplicates are possible, not verified"},
        "coverage": coverage, "inventory_issues": problems, "sessions": sessions,
        "matching_parent_closure": closures}


def write_new_output(path, result):
    path = Path(os.path.abspath(path))
    for component in (path, *path.parents):
        if os.path.lexists(component) and is_link(component):
            raise ValueError("linked_output_path_refused")
    path.parent.mkdir(parents=True, exist_ok=True)
    for component in (path.parent, *path.parent.parents):
        if is_link(component):
            raise ValueError("linked_output_path_refused")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-root", action="append", required=True,
                        help="Explicit local JSONL root; repeat for additional roots")
    parser.add_argument("--keyword", action="append", required=True,
                        help="Nonempty Unicode casefolded literal text; repeat for more terms; original query retained")
    parser.add_argument("--output", required=True, help="New JSON output path; existing files refused")
    parser.add_argument("--source-root-kind", default="explicit-local-jsonl-root")
    args = parser.parse_args(argv)
    try:
        result = discover(args.sessions_root, args.keyword, args.source_root_kind)
        write_new_output(args.output, result)
    except (OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print("Discovery failed: " + code, file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "coverage": result["coverage"]}))
    return 2 if result["status"] == "partial" else 0


if __name__ == "__main__":
    raise SystemExit(main())