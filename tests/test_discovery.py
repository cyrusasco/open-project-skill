"""Synthetic-only discovery tests. No user database or history is accessed."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/open-project/scripts/discover-sessions.py'
SPEC = importlib.util.spec_from_file_location('zcode_discovery', SCRIPT)
discovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discovery)

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.root = Path(self.temp.name)
        self.db = self.root / 'synthetic.sqlite'
        self.writer = sqlite3.connect(self.db)
        self.writer.executescript('''
          CREATE TABLE session(id TEXT PRIMARY KEY, parent_id TEXT, title TEXT, directory TEXT,
            time_created INTEGER, time_updated INTEGER, time_archived INTEGER,
            time_deleted INTEGER, time_compacting INTEGER);
          CREATE TABLE message(id TEXT PRIMARY KEY, session_id TEXT, data TEXT);
          CREATE TABLE part(id TEXT PRIMARY KEY, session_id TEXT, message_id TEXT, data TEXT);
        ''')
    def tearDown(self):
        self.writer.close()
        self.temp.cleanup()
    def session(self, sid, parent=None, title='unrelated', directory='/different/project'):
        self.writer.execute('INSERT INTO session VALUES(?,?,?,?,1,2,NULL,NULL,NULL)',
                            (sid, parent, title, directory))
    def message(self, mid, sid, role='user', **extra):
        self.writer.execute('INSERT INTO message VALUES(?,?,?)',
                            (mid, sid, json.dumps({'role': role, **extra})))
    def part(self, pid, sid, mid, kind='text', text='needle', **extra):
        self.writer.execute('INSERT INTO part VALUES(?,?,?,?)',
                            (pid, sid, mid, json.dumps({'type': kind, 'text': text, **extra}, ensure_ascii=True)))
    def run_discovery(self, keywords=('needle',), **kw):
        self.writer.commit()
        return discovery.discover(self.db, keywords, **kw)

    def test_global_cross_directory_opaque_ids_and_keyset_pagination(self):
        ids = ['229', 'completely:opaque', 'sess_old', 'session_new', 'z-last']
        for i, sid in enumerate(ids):
            self.session(sid)
            self.message('m' + str(i), sid, role='assistant' if i % 2 else 'user')
            self.part('p' + str(i), sid, 'm' + str(i), text='x' * 20000 + ' needle')
        r = self.run_discovery(batch_size=2, source_id='fixture')
        self.assertEqual(r['status'], 'complete')
        self.assertEqual({x['session_id'] for x in r['inventory']}, set(ids))
        self.assertEqual({x['session_id'] for x in r['hits']}, set(ids))
        self.assertEqual(r['coverage']['eligible']['parts'], 5)
        self.assertEqual(r['coverage']['scanned']['parts'], 5)
        self.assertEqual(r['coverage']['matched_messages'], 5)
        self.assertEqual(r['coverage']['distinct_sessions'], 5)
        for c in r['candidates']:
            self.assertEqual((c['classification'], c['depth']), ('unconfirmed', 'unread'))
            self.assertEqual(c['source_id'], 'fixture')
            self.assertEqual(len(c['revision_digest']), 64)
        self.assertNotIn('x' * 200, json.dumps(r))

    def test_literal_wildcards_sql_injection_and_json_unicode(self):
        self.session('opaque')
        self.message('m', 'opaque')
        self.part('a', 'opaque', 'm', text='100%_literal 中文 STRASSE "escaped"')
        self.part('b', 'opaque', 'm', text='100xxliteral')
        self.part('c', 'opaque', 'm', text="literal ' OR 1=1 --")
        r = self.run_discovery(['%_', '中文', 'straße', '"escaped"', "' OR 1=1 --"], batch_size=1)
        self.assertEqual([h['part_id'] for h in r['hits']], ['a', 'a', 'a', 'a', 'c'])
        self.assertEqual(r['coverage']['matched_parts'], 2)
        self.assertEqual(r['coverage']['matched_messages'], 1)
        self.assertEqual(r['coverage']['distinct_sessions'], 1)

    def test_wal_only_commits_visible_and_source_bytes_unchanged(self):
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.writer.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self.session('wal-only')
        self.message('m', 'wal-only')
        self.part('p', 'wal-only', 'm')
        self.writer.commit()
        wal = Path(str(self.db) + '-wal')
        self.assertTrue(wal.exists())
        copied = self.root / 'base-only.sqlite'
        shutil.copyfile(self.db, copied)
        with contextlib.closing(sqlite3.connect(copied)) as base:
            self.assertEqual(base.execute('SELECT COUNT(*) FROM session').fetchone()[0], 0)
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.db, wal)}
        r = discovery.discover(self.db, ['needle'])
        self.assertEqual([h['session_id'] for h in r['hits']], ['wal-only'])
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})
        self.assertEqual(r['snapshot']['delta']['data_version_changed'], False)
        self.assertIsNone(r['snapshot']['delta']['row_count_delta'])

    def test_reasoning_excluded_tools_and_summary_are_separate(self):
        self.session('s', title='needle metadata')
        self.message('normal', 's', summary={'title': 'needle summary'})
        self.message('summary', 's', role='assistant', summary=True)
        self.part('a', 's', 'normal', kind='reasoning', text='needle PRIVATE_REASONING')
        self.part('b', 's', 'normal', kind='tool', text='unused', state={'input': {'q': 'needle'}, 'output': 'needle output'})
        self.part('c', 's', 'summary', text='needle summary body')
        r = self.run_discovery()
        self.assertEqual(r['hits'], [])
        self.assertEqual(len(r['signals']['tool']), 2)
        self.assertEqual(len(r['signals']['summary']), 2)
        self.assertEqual(len(r['signals']['metadata']), 1)
        self.assertEqual(r['coverage']['skipped']['reasoning'], 1)
        self.assertEqual(r['coverage']['matched_parts'], 0)
        self.assertNotIn('PRIVATE_REASONING', json.dumps(r))

    def test_malformed_json_missing_message_and_mismatched_refs_are_honest(self):
        self.session('s')
        self.message('m', 's')
        self.writer.execute('INSERT INTO message VALUES(?,?,?)', ('badm', 's', 'PRIVATE_MALFORMED'))
        self.writer.execute('INSERT INTO part VALUES(?,?,?,?)', ('badp', 's', 'm', '{PRIVATE_JSON'))
        self.part('missing', 's', 'absent')
        self.part('wrong', 'other', 'm')
        self.part('unknown-role', 's', 'badm')
        self.part('valid', 's', 'm')
        r = self.run_discovery()
        self.assertEqual(r['status'], 'partial')
        self.assertTrue(r['coverage']['parts_complete'])
        self.assertEqual(r['coverage']['error_rows'], {'messages': 1, 'parts': 3})
        self.assertEqual([h['part_id'] for h in r['hits']], ['valid'])
        self.assertNotIn('PRIVATE_', json.dumps(r))

    def test_parent_chains_orphans_and_cycles(self):
        for sid, parent in [('root', None), ('child', 'root'), ('orphan', 'gone'), ('a', 'b'), ('b', 'a')]:
            self.session(sid, parent)
        r = self.run_discovery()
        inventory = {x['session_id']: x for x in r['inventory']}
        self.assertEqual(inventory['child']['parent_chain'], {'session_ids': ['root'], 'status': 'root'})
        self.assertEqual(inventory['orphan']['parent_chain']['status'], 'orphan')
        self.assertEqual(inventory['a']['parent_chain']['status'], 'cycle')
        self.assertEqual(inventory['a']['parent_chain']['session_ids'], ['b', 'a'])
    def test_unreadable_missing_and_invalid_schema_do_not_create_sources(self):
        missing = self.root / 'missing.sqlite'
        r = discovery.discover(missing, ['needle'])
        self.assertEqual(r['status'], 'unavailable')
        self.assertFalse(missing.exists())
        self.assertIsNone(r['coverage']['eligible']['parts'])
        corrupt = self.root / 'corrupt.sqlite'
        corrupt.write_text('not sqlite', encoding='utf-8')
        self.assertEqual(discovery.discover(corrupt, ['needle'])['status'], 'unavailable')
        wrong = self.root / 'schema.sqlite'
        with contextlib.closing(sqlite3.connect(wrong)) as c:
            c.execute('CREATE TABLE session (id TEXT PRIMARY KEY)')
        r = discovery.discover(wrong, ['needle'])
        self.assertEqual(r['status'], 'unavailable')
        self.assertTrue(any(e['kind'] == 'schema' for e in r['errors']))

    def test_deadline_partial_denominators_unknown_and_input_validation(self):
        r = discovery.discover(self.db, ['needle'], max_seconds=0)
        self.assertEqual(r['status'], 'partial')
        self.assertEqual(r['coverage']['stop_reason'], 'max_seconds')
        self.assertIsNone(r['coverage']['eligible']['sessions'])
        self.assertIsNone(r['coverage']['eligible']['visible_parts'])
        self.assertEqual(r['inventory'], [])
        for kw in ({'batch_size': 0}, {'max_seconds': -1}, {'max_seconds': float('inf')}):
            with self.assertRaises(ValueError):
                discovery.discover(self.db, ['needle'], **kw)

    def test_revision_digest_deterministic_and_changes_with_content(self):
        self.session('s')
        self.message('m', 's')
        self.part('p', 's', 'm')
        a = self.run_discovery(batch_size=1, source_id='same')['inventory'][0]['revision_digest']
        b = self.run_discovery(batch_size=10, source_id='same')['inventory'][0]['revision_digest']
        self.assertEqual(a, b)
        self.writer.execute('UPDATE part SET data=? WHERE id=?', (json.dumps({'type': 'text', 'text': 'new needle'}), 'p'))
        c = self.run_discovery(source_id='same')['inventory'][0]['revision_digest']
        self.assertNotEqual(a, c)

    def test_cli_project_constrains_output_only_and_protects_db(self):
        self.session('outside-project', directory='/nothing/in/common')
        self.message('m', 'outside-project')
        self.part('p', 'outside-project', 'm')
        self.writer.commit()
        project = self.root / 'project'
        output = project / 'evidence' / 'report.json'
        argv = ['--db', str(self.db), '--keyword', 'needle', '--output', str(output), '--project', str(project)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(discovery.main(argv), 0)
        r = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual([x['session_id'] for x in r['candidates']], ['outside-project'])
        self.assertFalse(output.read_bytes().startswith(b'\xef\xbb\xbf'))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            discovery.main(['--db', str(self.db), '--keyword', 'needle', '--output', str(self.root / 'escape.json'), '--project', str(project)])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            discovery.main(['--db', str(self.db), '--keyword', 'needle', '--output', str(self.db)])

    def test_snapshot_stays_consistent_during_concurrent_wal_commit(self):
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.session('before')
        self.message('m-before', 'before')
        self.part('p-before', 'before', 'm-before')
        self.writer.commit()
        writer = self.writer
        original_connect = sqlite3.connect
        injected = []
        class ConcurrentConnection(sqlite3.Connection):
            def execute(connection, sql, parameters=()):
                result = super().execute(sql, parameters)
                if sql == 'SELECT COUNT(*) FROM "session"' and not injected:
                    injected.append(True)
                    writer.execute('INSERT INTO session(id,title) VALUES(?,?)', ('after', 'new'))
                    writer.execute('INSERT INTO message VALUES(?,?,?)', ('m-after', 'after', '{"role":"user"}'))
                    writer.execute('INSERT INTO part VALUES(?,?,?,?)', ('p-after', 'after', 'm-after', '{"type":"text","text":"needle"}'))
                    writer.commit()
                return result
        def connect(*args, **kwargs):
            return original_connect(*args, factory=ConcurrentConnection, **kwargs)
        with mock.patch.object(discovery.sqlite3, 'connect', side_effect=connect):
            r = discovery.discover(self.db, ['needle'])
        self.assertEqual([x['session_id'] for x in r['inventory']], ['before'])
        self.assertEqual([x['session_id'] for x in r['hits']], ['before'])
        self.assertEqual(r['coverage']['eligible']['sessions'], 1)
        self.assertTrue(r['snapshot']['delta']['data_version_changed'])
        self.assertIsNone(r['snapshot']['delta']['row_count_delta'])

    def test_blob_json_is_hashed_without_text_leakage(self):
        self.session('s')
        self.message('m', 's')
        self.writer.execute('INSERT INTO part VALUES(?,?,?,?)', ('p', 's', 'm', b'{"type":"text","text":"needle PRIVATE_BLOB"}'))
        r = self.run_discovery()
        self.assertEqual(r['status'], 'complete')
        self.assertEqual([h['part_id'] for h in r['hits']], ['p'])
        self.assertNotIn('PRIVATE_BLOB', json.dumps(r))

    def test_missing_optional_parent_is_unknown_not_assumed_root(self):
        small = self.root / 'minimal.sqlite'
        with contextlib.closing(sqlite3.connect(small)) as c:
            c.executescript('CREATE TABLE session(id TEXT PRIMARY KEY); CREATE TABLE message(id TEXT PRIMARY KEY, session_id TEXT, data TEXT); CREATE TABLE part(id TEXT PRIMARY KEY, session_id TEXT, message_id TEXT, data TEXT); INSERT INTO session VALUES("opaque");')
        r = discovery.discover(small, ['needle'])
        self.assertEqual(r['status'], 'complete')
        self.assertIn('parent_id', r['missing_optional_session_fields'])
        self.assertEqual(r['inventory'][0]['parent_chain']['status'], 'unknown')

    def test_duplicate_null_and_empty_identity_ids_are_explicit_schema_errors(self):
        for table in ('session', 'message', 'part'):
            for invalid_kind in ('duplicate', 'null', 'empty'):
                with self.subTest(table=table, invalid_kind=invalid_kind):
                    db = self.root / ('ambiguous-' + table + '-' + invalid_kind + '.sqlite')
                    with contextlib.closing(sqlite3.connect(db)) as c:
                        c.executescript('''
                            CREATE TABLE session(id TEXT, parent_id TEXT, title TEXT);
                            CREATE TABLE message(id TEXT, session_id TEXT, data TEXT);
                            CREATE TABLE part(id TEXT, session_id TEXT, message_id TEXT, data TEXT);
                            INSERT INTO session VALUES('s',NULL,'unrelated');
                            INSERT INTO message VALUES('m','s','{"role":"user"}');
                            INSERT INTO part VALUES('p','s','m','{"type":"text","text":"needle"}');
                        ''')
                        if invalid_kind == 'duplicate':
                            if table == 'message':
                                # Regression: the second role used to overwrite the user.
                                c.execute('INSERT INTO message VALUES(?,?,?)', ('m', 's', '{"role":"system"}'))
                            else:
                                c.execute('INSERT INTO "' + table + '" SELECT * FROM "' + table + '"')
                        else:
                            c.execute('UPDATE "' + table + '" SET id=?',
                                      (None if invalid_kind == 'null' else '',))
                        c.commit()
                    r = discovery.discover(db, ['needle'], batch_size=1)
                    self.assertEqual(r['status'], 'unavailable')
                    errors = [e for e in r['errors'] if e['code'] == 'ambiguous_identity_ids']
                    self.assertEqual([e['table'] for e in errors], [table])
                    self.assertEqual(r['coverage']['scanned'],
                                     {'sessions': 0, 'messages': 0, 'parts': 0, 'visible_parts': 0})
                    self.assertFalse(r['coverage']['messages_complete'])
                    self.assertFalse(r['coverage']['parts_complete'])

if __name__ == '__main__':
    unittest.main()
