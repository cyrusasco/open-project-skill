#!/usr/bin/env python3
"""Read-only explicit-source discovery for ZCode SQLite and Codex JSONL.

No directory/title prefilter; emitted references remain unread candidates.
Use --db or explicit --sessions-root entries. No live source is changed.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import stat
import sys
from collections import defaultdict

SESSION_FIELDS = ('id', 'parent_id', 'title', 'directory', 'time_created', 'time_updated',
                  'time_archived', 'time_deleted', 'time_compacting')
REQUIRED = {'session': {'id'}, 'message': {'id', 'session_id', 'data'},
            'part': {'id', 'session_id', 'message_id', 'data'}}

class Expired(Exception):
    pass

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'),
                      default=lambda v: {'sqlite_blob_hex': v.hex()} if isinstance(v, bytes) else str(type(v).__name__))

def hash_record(hasher, kind, record):
    blob = canonical([kind, record]).encode('utf-8')
    hasher.update(str(len(blob)).encode('ascii') + b':' + blob)

def strings(value, path):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from strings(value[key], path + '.' + str(key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from strings(item, path + '[' + str(i) + ']')

def object_data(raw):
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError('record must be an object')
    return obj

def lineage(sid, inventory, complete):
    chain, seen, current = [], {sid}, sid
    while current in inventory:
        if 'parent_id' not in inventory[current]:
            return {'session_ids': chain, 'status': 'unknown'}
        parent = inventory[current].get('parent_id')
        if parent is None or parent == '':
            return {'session_ids': chain, 'status': 'root'}
        chain.append(parent)
        if parent in seen:
            return {'session_ids': chain, 'status': 'cycle', 'cycle_at': parent}
        if parent not in inventory:
            return {'session_ids': chain, 'status': 'orphan' if complete else 'unknown',
                    'missing_parent_id': parent}
        seen.add(parent)
        current = parent
    return {'session_ids': chain, 'status': 'unknown'}

def discover_sqlite(db, keywords, *, batch_size=1000, max_seconds=120, source_id=None):
    """Search decoded visible dialogue globally, with no directory/title prefilter.

    SQLite mode=ro, query_only and BEGIN retain WAL visibility and one snapshot.
    Keywords are Python literal Unicode casefold substrings, never SQL patterns.
    Metadata/tool/summary hits remain separate; reasoning and snippets are excluded.
    Connections close before return. Only the supplied database is covered.
    """
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise ValueError('batch_size must be a positive integer')
    if not isinstance(max_seconds, (int, float)) or not math.isfinite(max_seconds) or max_seconds < 0:
        raise ValueError('max_seconds must be finite and nonnegative')
    keywords = [keywords] if isinstance(keywords, str) else list(keywords)
    if not keywords or any(not isinstance(k, str) or not k for k in keywords):
        raise ValueError('at least one nonempty literal keyword is required')
    path = Path(db).expanduser().resolve()
    source_id = source_id or 'sqlite:' + hashlib.sha256(str(path).encode('utf-8')).hexdigest()
    started = time.monotonic()
    deadline = started + max_seconds
    queries = [{'query_id': 'q' + str(i + 1), 'literal': k} for i, k in enumerate(keywords)]
    folded = [(q['query_id'], q['literal'].casefold()) for q in queries]
    report = {'format_version': 1, 'adapter': 'zcode-sqlite', 'source_id': source_id,
        'status': 'unavailable', 'queries': queries,
        'matching': 'Unicode casefold literal substring on decoded fields; no SQL LIKE',
        'inventory': [], 'hits': [], 'signals': {'metadata': [], 'tool': [], 'summary': []},
        'candidates': [], 'errors': [],
        'snapshot': {'transaction': 'BEGIN; mode=ro; query_only=ON', 't0': None, 't1': None,
                     'data_version_t0': None, 'data_version_t1': None,
                     'delta': {'data_version_changed': None, 'row_count_delta': None,
                               'row_count_delta_status': 'not_measured'}},
        'coverage': {'eligible': {'sessions': None, 'messages': None, 'parts': None, 'visible_parts': None},
            'scanned': {'sessions': 0, 'messages': 0, 'parts': 0, 'visible_parts': 0},
            'skipped': {}, 'error_rows': {'messages': 0, 'parts': 0},
            'matched_parts': 0, 'matched_messages': 0, 'distinct_sessions': 0,
            'metadata_complete': False, 'messages_complete': False, 'parts_complete': False,
            'stop_reason': None, 'sources_supplied': 1, 'sources_opened': 0, 'unknown_sources': None,
            'unknown_sources_note': 'Other databases, exports and hosts were not enumerated.',
            'recall': 'unmeasured; no gold corpus was supplied'},
        'limitations': ['Search candidates are unconfirmed and unread; discovery is not full review.',
                        'Reasoning parts are skipped; raw snippets are never included.',
                        'Only this supplied source and the recorded snapshot are covered.']}
    coverage = report['coverage']
    inventory, messages, digests = {}, {}, {}
    matched_parts, matched_messages, matched_sessions = set(), set(), set()
    con = None
    def check():
        if time.monotonic() >= deadline:
            raise Expired()
    def skip(reason):
        coverage['skipped'][reason] = coverage['skipped'].get(reason, 0) + 1
    def error(kind, code, **refs):
        # Exception messages can expose source text; output only safe codes and refs.
        report['errors'].append({'kind': kind, 'code': code, **refs})
    def digest(sid):
        if sid not in digests:
            digests[sid] = hashlib.sha256()
            hash_record(digests[sid], 'source_session', [source_id, sid])
        return digests[sid]
    def match(text, field, refs, signal=None):
        text = text.casefold()
        for query_id, literal in folded:
            if literal in text:
                hit = {'query_id': query_id, 'source_id': source_id, 'source_field': field, **refs}
                if signal:
                    report['signals'][signal].append(hit)
                else:
                    report['hits'].append(hit)
                    matched_parts.add(refs['part_id'])
                    matched_messages.add(refs['message_id'])
                    matched_sessions.add(refs['session_id'])
    def batches(table, columns):
        # SQL names come only from constants; keys and limits are parameterized.
        names = ', '.join('"' + c + '"' for c in columns)
        last, first = None, True
        while True:
            check()
            condition = '' if first else ' WHERE "id" > ?'
            params = (batch_size,) if first else (last, batch_size)
            rows = con.execute('SELECT ' + names + ' FROM "' + table + '"' + condition +
                               ' ORDER BY "id" LIMIT ?', params).fetchall()
            if not rows:
                return
            for row in rows:
                check()
                if row['id'] is None:
                    raise sqlite3.DatabaseError('null id')
                yield dict(row)
            last, first = rows[-1]['id'], False
    try:
        check()
        if not path.is_file():
            error('source', 'not_a_readable_file')
        else:
            con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True,
                                  timeout=min(1.0, max_seconds))
            con.row_factory = sqlite3.Row
            con.execute('PRAGMA query_only=ON')
            con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            con.execute('BEGIN')
            report['snapshot']['t0'] = now()
            # First read fixes the transaction snapshot, including committed WAL.
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            coverage['sources_opened'] = 1
            report['snapshot']['data_version_t0'] = con.execute('PRAGMA data_version').fetchone()[0]
            schema = {}
            for table, required in REQUIRED.items():
                check()
                schema[table] = {r['name'] for r in con.execute('PRAGMA table_info("' + table + '")')}
                if table not in tables or not required.issubset(schema[table]):
                    error('schema', 'missing_required_table_or_columns', table=table,
                          missing_columns=sorted(required - schema[table]))
            report['schema'] = {t: sorted(c) for t, c in schema.items()}
            if not report['errors']:
                # Validate the identity contract before dictionary lookup or keyset scans.
                # Unknown schemas may omit PK/NOT NULL constraints; duplicate IDs must
                # never overwrite another message role or make a paginated census lie.
                for table in REQUIRED:
                    check()
                    invalid = con.execute('SELECT "id" FROM "' + table + '" '
                        'GROUP BY "id" HAVING COUNT(*) > 1 OR "id" IS NULL '
                        'OR length(CAST("id" AS TEXT)) = 0 LIMIT 1').fetchone()
                    if invalid is not None:
                        error('schema', 'ambiguous_identity_ids', table=table,
                              requirement='unique_nonnull_nonempty_ids')
            if not report['errors']:
                for table, plural in (('session', 'sessions'), ('message', 'messages'), ('part', 'parts')):
                    check()
                    coverage['eligible'][plural] = con.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0]
                present = [f for f in SESSION_FIELDS if f in schema['session']]
                report['missing_optional_session_fields'] = [f for f in SESSION_FIELDS if f not in present]
                for row in batches('session', present):
                    sid = row.pop('id')
                    inventory[sid] = {'source_id': source_id, 'session_id': sid, **row, 'depth': 'unread'}
                    hash_record(digest(sid), 'session', row)
                    coverage['scanned']['sessions'] += 1
                coverage['metadata_complete'] = True
                for row in batches('message', ('id', 'session_id', 'data')):
                    coverage['scanned']['messages'] += 1
                    hash_record(digest(row['session_id']), 'message', row)
                    refs = {'session_id': row['session_id'], 'message_id': row['id']}
                    try:
                        obj = object_data(row['data'])
                        messages[row['id']] = {'session_id': row['session_id'], 'role': obj.get('role'),
                                               'summary': obj.get('summary') is True}
                        if isinstance(obj.get('summary'), (dict, str)):
                            for field, value in strings(obj['summary'], 'message.data.summary'):
                                match(value, field, refs, 'summary')
                    except (ValueError, TypeError, UnicodeError, RecursionError):
                        messages[row['id']] = {'session_id': row['session_id'], 'role': None, 'summary': False}
                        skip('malformed_message_json')
                        coverage['error_rows']['messages'] += 1
                        error('message', 'malformed_json', **refs)
                coverage['messages_complete'] = True
                for row in batches('part', ('id', 'session_id', 'message_id', 'data')):
                    coverage['scanned']['parts'] += 1
                    hash_record(digest(row['session_id']), 'part', row)
                    refs = {'session_id': row['session_id'], 'message_id': row['message_id'], 'part_id': row['id']}
                    try:
                        obj = object_data(row['data'])
                    except (ValueError, TypeError, UnicodeError, RecursionError):
                        coverage['error_rows']['parts'] += 1
                        skip('malformed_part_json')
                        error('part', 'malformed_json', **refs)
                        continue
                    kind = obj.get('type')
                    if kind == 'reasoning':
                        skip('reasoning')
                        continue
                    message = messages.get(row['message_id'])
                    if not message:
                        skip('missing_message')
                        coverage['error_rows']['parts'] += 1
                        error('part', 'missing_message', **refs)
                        continue
                    if message['session_id'] != row['session_id']:
                        skip('session_reference_mismatch')
                        coverage['error_rows']['parts'] += 1
                        error('part', 'session_reference_mismatch', **refs)
                        continue
                    if kind == 'text':
                        text = obj.get('text')
                        if not isinstance(text, str):
                            skip('non_string_text')
                        elif message['role'] not in ('user', 'assistant'):
                            skip('non_dialogue_or_unknown_role')
                        elif message['summary']:
                            skip('summary_text_separate')
                            match(text, 'part.data.text', refs, 'summary')
                        else:
                            coverage['scanned']['visible_parts'] += 1
                            match(text, 'part.data.text', {**refs, 'role': message['role']})
                    elif kind == 'tool':
                        skip('tool_separate')
                        state = obj.get('state')
                        if isinstance(state, dict):
                            for key in ('input', 'output'):
                                for field, value in strings(state.get(key), 'part.data.state.' + key):
                                    match(value, field, refs, 'tool')
                    elif kind == 'summary':
                        skip('summary_separate')
                        for key in ('text', 'title', 'body'):
                            for field, value in strings(obj.get(key), 'part.data.' + key):
                                match(value, field, refs, 'summary')
                    else:
                        skip('other_part_type')
                coverage['parts_complete'] = True
                coverage['eligible']['visible_parts'] = coverage['scanned']['visible_parts']
                # Metadata signals never narrow the dialogue scan.
                for sid, item in inventory.items():
                    check()
                    for field in ('title', 'directory'):
                        if isinstance(item.get(field), str):
                            match(item[field], 'session.' + field, {'session_id': sid}, 'metadata')
                for plural in ('sessions', 'messages', 'parts'):
                    if coverage['scanned'][plural] != coverage['eligible'][plural]:
                        error('schema', 'nonunique_or_unsupported_ids', table=plural)
                report['status'] = 'complete' if not report['errors'] else 'partial'
                if report['errors']:
                    coverage['stop_reason'] = 'record_errors'
    except Expired:
        report['status'] = 'partial'
        coverage['stop_reason'] = 'max_seconds'
    except (sqlite3.Error, OSError) as exc:
        if time.monotonic() >= deadline:
            report['status'] = 'partial'
            coverage['stop_reason'] = 'max_seconds'
        else:
            report['status'] = 'partial' if any(coverage['scanned'].values()) else 'unavailable'
            error('source', 'sqlite_or_io_error', exception_type=type(exc).__name__)
            coverage['stop_reason'] = 'source_error'
    finally:
        if con is not None:
            con.set_progress_handler(None, 0)
            try:
                con.rollback()
                version = con.execute('PRAGMA data_version').fetchone()[0]
                report['snapshot']['data_version_t1'] = version
                initial = report['snapshot']['data_version_t0']
                if initial is not None:
                    report['snapshot']['delta']['data_version_changed'] = version != initial
            except sqlite3.Error:
                error('source', 'snapshot_end_probe_failed')
            finally:
                con.close()
        report['snapshot']['t1'] = now()
    # DB connection is closed before report assembly or any subsequent review.
    complete_revision = coverage['metadata_complete'] and coverage['messages_complete'] and coverage['parts_complete']
    for sid, item in inventory.items():
        item['parent_chain'] = lineage(sid, inventory, coverage['metadata_complete'])
        item['revision_digest'] = digests[sid].hexdigest()
        item['revision_scope'] = 'snapshot_records' if complete_revision else 'partial_snapshot_records'
    report['inventory'] = list(inventory.values())
    by_session = {}
    for kind, hits in [('visible_dialogue', report['hits']), *report['signals'].items()]:
        for hit in hits:
            sid = hit['session_id']
            candidate = by_session.setdefault(sid, {'source_id': source_id, 'session_id': sid,
                'classification': 'unconfirmed', 'depth': 'unread', 'signals': [], 'query_ids': [],
                'metadata_present': sid in inventory, 'revision_digest': digest(sid).hexdigest(),
                'revision_scope': 'snapshot_records' if complete_revision and sid in inventory else 'partial_snapshot_records',
                'parent_chain': inventory[sid]['parent_chain'] if sid in inventory else {'session_ids': [], 'status': 'unknown'}})
            if kind not in candidate['signals']:
                candidate['signals'].append(kind)
            if hit['query_id'] not in candidate['query_ids']:
                candidate['query_ids'].append(hit['query_id'])
    report['candidates'] = list(by_session.values())
    coverage.update(matched_parts=len(matched_parts), matched_messages=len(matched_messages),
                    distinct_sessions=len(matched_sessions), candidate_sessions=len(by_session),
                    signal_hits={kind: len(hits) for kind, hits in report['signals'].items()},
                    unscanned={key: None if total is None else total - coverage['scanned'][key]
                               for key, total in coverage['eligible'].items()},
                    duration_seconds=round(time.monotonic() - started, 6))
    return report


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


def discover_jsonl(roots, keywords, source_root_kind="explicit-local-jsonl-root"):
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



def normalize_queries(keywords, query_groups=None):
    """Keep query provenance; grouping is literal ANY, never a SQL expression."""
    words = [keywords] if isinstance(keywords, str) else list(keywords or [])
    groups = []
    for group in query_groups or []:
        if not isinstance(group, dict) or set(group) - {'id', 'keywords', 'operator'}:
            raise ValueError('invalid_query_group')
        identity = group.get('id')
        terms = group.get('keywords')
        if (not isinstance(identity, str) or not identity.strip()
                or not isinstance(terms, list) or not terms
                or group.get('operator', 'ANY') != 'ANY'
                or any(not isinstance(term, str) or not term for term in terms)):
            raise ValueError('invalid_query_group')
        groups.append({'id': identity, 'keywords': list(dict.fromkeys(terms)), 'operator': 'ANY'})
    if words:
        groups.insert(0, {'id': 'project-keywords', 'keywords': list(dict.fromkeys(words)),
                          'operator': 'ANY'})
    if (not groups or any(not isinstance(word, str) or not word for word in words)
            or len({group['id'] for group in groups}) != len(groups)):
        raise ValueError('at_least_one_nonempty_keyword_required_or_duplicate_group')
    flattened = list(dict.fromkeys(word for group in groups for word in group['keywords']))
    identities = {word: 'q' + str(index + 1) for index, word in enumerate(flattened)}
    for group in groups:
        group['query_ids'] = [identities[word] for word in group['keywords']]
    return flattened, groups


def census(unit, total, scanned, *, skipped=0, errors=0, matched=0):
    # eligible is the entire supplied-source census, not only matching dialogue.
    # skipped/error_rows overlap scanned and are NOT additive denominator buckets.
    return {'unit': unit, 'total': total, 'eligible': total, 'scanned': scanned,
            'skipped': skipped, 'error_rows': errors, 'matched': matched,
            'unscanned': None if total is None else total - scanned}


def sqlite_parent_closure(report):
    """Describe matched-session ancestors and descendants without content export."""
    items = {item['session_id']: item for item in report['inventory']}
    children = defaultdict(list)
    for identity, item in items.items():
        parent = item.get('parent_id')
        if parent not in (None, ''):
            children[parent].append(identity)
    result = []
    for candidate in report['candidates']:
        identity = candidate['session_id']
        chain = candidate['parent_chain']
        descendants, seen, pending = [], {identity}, list(children.get(identity, []))
        cycle = False
        while pending:
            child = pending.pop()
            if child in seen:
                cycle = True
                continue
            seen.add(child)
            descendants.append(child)
            pending.extend(children.get(child, []))
        result.append({'source_id': report['source_id'], 'session_id': identity,
                       'ancestor_session_ids': chain['session_ids'],
                       'descendant_session_ids': sorted(descendants),
                       'ancestor_status': chain['status'], 'descendant_cycle': cycle,
                       'inventory_complete': report['coverage']['metadata_complete']})
    return result


def sqlite_receipt(report, path, groups, source_kind):
    coverage = report['coverage']
    census_rows = {}
    for plural, singular in (('sessions', 'session'), ('messages', 'message'), ('parts', 'part')):
        skipped = (sum(coverage['skipped'].values()) if plural == 'parts' else
                   coverage['error_rows']['messages'] if plural == 'messages' else 0)
        # malformed_message_json is a message skip, not a second skipped part.
        if plural == 'parts':
            skipped -= coverage['skipped'].get('malformed_message_json', 0)
        errors = coverage['error_rows'].get(plural, 0)
        matched = {'sessions': coverage['distinct_sessions'],
                   'messages': coverage['matched_messages'],
                   'parts': coverage['matched_parts']}[plural]
        census_rows[singular + '_rows'] = census(
            singular + ' rows in supplied SQLite snapshot', coverage['eligible'][plural],
            coverage['scanned'][plural], skipped=skipped, errors=errors, matched=matched)
    working_copy = source_kind == 'working-copy'
    limitations = list(report['limitations'])
    limitations.append('Other authorized databases, exports and hosts require separate inventory entries.')
    if working_copy:
        limitations.append('A transaction makes this supplied copy consistent; it does not establish '
                           'that an earlier DB+WAL file copy was an atomic snapshot of the original.')
    receipt = {
        'schema_version': 'open-project/discovery-receipt/2.0',
        'adapter': 'zcode-sqlite',
        'status': {'complete': 'COMPLETE', 'partial': 'PARTIAL', 'unavailable': 'UNAVAILABLE'}[report['status']],
        'source_inventory': [{'source_id': report['source_id'], 'kind': 'zcode-sqlite',
                              'path': str(path), 'status': 'AVAILABLE' if
                              coverage['sources_opened'] == 1 and report['status'] != 'unavailable'
                              else 'UNAVAILABLE', 'source_kind': source_kind,
                              'availability_basis': 'Successfully opened supported schema' if
                              coverage['sources_opened'] == 1 and report['status'] != 'unavailable'
                              else 'Not opened or supported schema unavailable',
                              'schema': report.get('schema', {})}],
        'query_groups': groups,
        'census': census_rows,
        'pagination': {'method': 'keyset-id', 'end_reached': {
            'session_rows': coverage['metadata_complete'],
            'message_rows': coverage['messages_complete'], 'part_rows': coverage['parts_complete']}},
        'snapshot': {**report['snapshot'], 'kind': 'sqlite-read-transaction',
                     'source_kind': source_kind,
                     'atomic_for_supplied_source': coverage['sources_opened'] == 1,
                     'atomic_for_original_source': False if working_copy else coverage['sources_opened'] == 1},
        'reading': {'full': 0, 'partial': 0, 'summary-only': 0,
                    'unread': len(report['inventory'])},
        'complete_scope': 'supplied_sources_only', 'all_system_history_complete': False,
        'limitations': limitations,
        'counter_definition': 'total=eligible=scanned+unscanned when known. skipped/error_rows '
                              'are subsets of scanned and may overlap; do not add them to scanned. '
                              'matched counts visible dialogue only; discovery is not deep reading.'}
    return receipt


def jsonl_receipt(report, groups, started, finished):
    coverage = report['coverage']
    inventory_rows = []
    for root in report['scope']['roots']:
        path = Path(root['path'])
        root_issues = [item for item in report['inventory_issues']
                       if item.get('path') == str(path)]
        inventory_rows.append({
            'source_id': 'jsonl-root:' + hashlib.sha256(str(path).encode('utf-8')).hexdigest(),
            'kind': 'codex-jsonl-root', 'path': str(path), 'source_kind': root['kind'],
            'status': 'AVAILABLE' if path.is_dir() and not is_link(path) and not root_issues
            else 'UNAVAILABLE'})
    seen = coverage['record_views_seen']
    issues = report['inventory_issues']
    return {
        'schema_version': 'open-project/discovery-receipt/2.0', 'adapter': 'codex-jsonl',
        'status': 'COMPLETE' if report['status'] == 'ok' else 'PARTIAL',
        'source_inventory': inventory_rows, 'query_groups': groups,
        'census': {
            'files': census('unique file paths, not unique conversation identities',
                            coverage['files_inventoried'], coverage['files_attempted'],
                            errors=coverage['files_failed'], matched=coverage['files_matching']),
            'record_views': census('supported stream record views, not unique human messages',
                                   seen, seen, skipped=coverage['record_views_skipped'],
                                   matched=coverage['record_views_matching'])},
        'pagination': {'method': 'recursive-files-and-line-eof', 'end_reached': {
            'files': not issues,
            'record_views': not coverage['files_failed'] and not any(
                not session['snapshot']['stable'] for session in report['sessions'])}},
        'snapshot': {'kind': 'non-atomic-file-collection', 't0': started, 't1': finished,
                     'atomic_for_supplied_source': False, 'atomic_for_original_source': False,
                     'stable_files': coverage['files_stable'],
                     'limitation': 'Each file has its own byte hash and before/after stat; roots '
                                   'can change between enumeration and reads. No global atomic snapshot.'},
        'reading': {'full': 0, 'partial': 0, 'summary-only': 0,
                    'unread': len(report['sessions'])},
        'complete_scope': 'supplied_sources_only', 'all_system_history_complete': False,
        'limitations': list(report['scope']['unknown_sources']) + [
            'Record views may duplicate messages. File hashing/retrieval does not establish deep reading.',
            'Malformed lines and unsupported records are reported separately, not guessed into visible-message totals.'],
        'counter_definition': 'total=eligible=scanned+unscanned. skipped/error_rows are '
                              'subsets of scanned, not additive denominator buckets. Record-view '
                              'counts exclude metadata/invalid lines; never call these unique messages.'}


def discover(source, keywords=None, source_root_kind='explicit-local-jsonl-root', *,
             batch_size=1000, max_seconds=120, source_id=None,
             source_kind='live-database', query_groups=None):
    """Dispatch an explicit DB path or a list of explicit JSONL roots.

    Both native report APIs are retained. The additive discovery_receipt is a
    count/snapshot record only. It never upgrades unread sources to reviewed.
    """
    words, groups = normalize_queries(keywords, query_groups)
    if isinstance(source, (str, os.PathLike)):
        if source_kind not in ('live-database', 'working-copy'):
            raise ValueError('source_kind must be live-database or working-copy')
        result = discover_sqlite(source, words, batch_size=batch_size,
                                 max_seconds=max_seconds, source_id=source_id)
        result['matching_parent_closure'] = sqlite_parent_closure(result)
        result['discovery_receipt'] = sqlite_receipt(
            result, Path(source).expanduser().resolve(), groups, source_kind)
    else:
        started = now()
        result = discover_jsonl(source, words, source_root_kind)
        result['discovery_receipt'] = jsonl_receipt(result, groups, started, now())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument('--db', type=Path, help='Explicit ZCode SQLite source; no directory/title filter')
    sources.add_argument('--sessions-root', action='append', help='Explicit Codex JSONL root; repeat for more roots')
    parser.add_argument('--keyword', action='append', default=[])
    parser.add_argument('--query-group', action='append', default=[],
                        help='JSON {"id":"project","keywords":["name","alias"]}; literal ANY')
    parser.add_argument('--output', required=True, type=Path, help='New native report JSON path')
    parser.add_argument('--receipt-output', type=Path, help='Optional new standalone normalized receipt JSON')
    parser.add_argument('--project', type=Path, help='Constrain outputs only, never source sessions')
    parser.add_argument('--batch-size', type=int, default=1000)
    parser.add_argument('--max-seconds', type=float, default=120)
    parser.add_argument('--source-root-kind', default='explicit-local-jsonl-root')
    parser.add_argument('--source-kind', choices=('live-database', 'working-copy'), default='live-database',
                        help='Use working-copy for copied DB/WAL; it cannot prove original atomicity')
    args = parser.parse_args(argv)
    outputs = [args.output.expanduser().resolve()]
    if args.receipt_output:
        outputs.append(args.receipt_output.expanduser().resolve())
    if len(set(outputs)) != len(outputs):
        parser.error('report and receipt outputs must differ')
    if args.project:
        for output in outputs:
            if not output.is_relative_to(args.project.expanduser().resolve()):
                parser.error('all outputs must resolve within --project')
    if args.db:
        database = args.db.expanduser().resolve()
        protected = (database, Path(str(database) + '-wal'), Path(str(database) + '-shm'))
        if any(output in protected for output in outputs):
            parser.error('output must not replace database or WAL/shared-memory files')
    try:
        groups = [json.loads(raw) for raw in args.query_group]
        result = discover(args.db if args.db else args.sessions_root, args.keyword,
                          args.source_root_kind, batch_size=args.batch_size,
                          max_seconds=args.max_seconds, source_kind=args.source_kind,
                          query_groups=groups)
        write_new_output(outputs[0], result)
        if len(outputs) > 1:
            write_new_output(outputs[1], result['discovery_receipt'])
    except (OSError, ValueError) as exc:
        print('Discovery failed: ' + (str(exc) if isinstance(exc, ValueError)
                                      else type(exc).__name__), file=sys.stderr)
        return 1
    print(json.dumps({'status': result['status'], 'output': str(outputs[0]),
                      'coverage': result['coverage']}))
    return 0 if result['status'] in ('complete', 'ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
