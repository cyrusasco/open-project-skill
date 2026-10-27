#!/usr/bin/env python3
"""Global read-only ZCode discovery. References are candidates, never full reviews."""
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

def discover(db, keywords, *, batch_size=1000, max_seconds=120, source_id=None):
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

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--keyword', action='append', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--project', type=Path, help='Constrain output location only; never filter source sessions')
    parser.add_argument('--batch-size', type=int, default=1000)
    parser.add_argument('--max-seconds', type=float, default=120)
    args = parser.parse_args(argv)
    output, database = args.output.expanduser().resolve(), args.db.expanduser().resolve()
    if args.project:
        try:
            output.relative_to(args.project.expanduser().resolve())
        except ValueError:
            parser.error('--output must resolve within --project')
    if output in (database, Path(str(database) + '-wal'), Path(str(database) + '-shm')):
        parser.error('--output must not replace the database or WAL/shared-memory files')
    try:
        report = discover(database, args.keyword, batch_size=args.batch_size, max_seconds=args.max_seconds)
    except ValueError as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=output.parent,
                                         prefix='.discovery-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(json.dumps({'status': report['status'], 'output': str(output),
                      'candidate_sessions': len(report['candidates'])}))
    return 0 if report['status'] == 'complete' else 2

if __name__ == '__main__':
    raise SystemExit(main())
