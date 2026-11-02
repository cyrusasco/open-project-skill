"""Coverage receipts on generated sources only; never open personal history."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/open-project/scripts/discover-sessions.py'
SPEC = importlib.util.spec_from_file_location('discovery_coverage_adapter', SCRIPT)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class CoverageReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='discovery-coverage-', dir=ROOT)
        self.base = Path(self.temp.name)
        self.db = self.base / 'synthetic.sqlite'
        with contextlib.closing(sqlite3.connect(self.db)) as connection, connection:
            connection.executescript('''
                CREATE TABLE session(id TEXT PRIMARY KEY,parent_id TEXT,title TEXT,directory TEXT);
                CREATE TABLE message(id TEXT PRIMARY KEY,session_id TEXT,data TEXT);
                CREATE TABLE part(id TEXT PRIMARY KEY,session_id TEXT,message_id TEXT,data TEXT);
            ''')

    def tearDown(self):
        assert self.base.resolve().is_relative_to(ROOT.resolve())
        self.temp.cleanup()

    def add(self, identity, text='needle', *, parent=None, directory='D:/unrelated', kind='text'):
        with contextlib.closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute('INSERT INTO session VALUES(?,?,?,?)',
                               (identity, parent, 'unrelated title', directory))
            connection.execute('INSERT INTO message VALUES(?,?,?)',
                               ('m:' + identity, identity, '{"role":"user"}'))
            connection.execute('INSERT INTO part VALUES(?,?,?,?)',
                               ('p:' + identity, identity, 'm:' + identity,
                                json.dumps({'type': kind, 'text': text})))

    def jsonl(self, identity='file-session'):
        root = self.base / 'jsonl'
        root.mkdir(exist_ok=True)
        path = root / (identity + '.jsonl')
        rows = [
            {'type': 'session_meta', 'payload': {'id': identity, 'cwd': 'D:/unrelated'}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                'content': [{'type': 'input_text', 'text': 'needle %_'}]}},
            {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'needle %_'}},
            {'type': 'response_item', 'payload': {'type': 'reasoning', 'text': 'PRIVATE_REASONING'}},
        ]
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        return root

    def assertCensus(self, receipt):
        for row in receipt['census'].values():
            if row['total'] is not None:
                self.assertEqual(row['total'], row['eligible'])
                self.assertEqual(row['total'], row['scanned'] + row['unscanned'])
            self.assertLessEqual(row['matched'] + row['skipped'], row['scanned'])
            self.assertGreaterEqual(row['error_rows'], 0)

    def test_global_229_sessions_in_229_directories_all_retained(self):
        for index in range(229):
            self.add('opaque:' + str(index), 'LINE Bridge project',
                     directory='D:/line-bridge' if index == 0 else f'D:/other/{index}')
        result = ADAPTER.discover(self.db, ['line bridge'], batch_size=17)
        receipt = result['discovery_receipt']
        self.assertEqual(len(result['candidates']), 229)
        self.assertEqual(receipt['census']['session_rows']['matched'], 229)
        self.assertEqual(receipt['census']['part_rows']['total'], 229)
        self.assertTrue(all(receipt['pagination']['end_reached'].values()))
        self.assertEqual(receipt['reading'], {'full': 0, 'partial': 0,
                                             'summary-only': 0, 'unread': 229})
        self.assertFalse(receipt['all_system_history_complete'])
        self.assertCensus(receipt)

    def test_skip_and_error_counts_have_explicit_units_and_conservation(self):
        self.add('normal')
        self.add('reasoning', kind='reasoning', text='needle PRIVATE_REASONING')
        self.add('malformed')
        with contextlib.closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute('UPDATE part SET data=? WHERE session_id=?', ('{bad', 'malformed'))
        result = ADAPTER.discover(self.db, ['needle'])
        receipt = result['discovery_receipt']
        self.assertEqual(receipt['status'], 'PARTIAL')
        self.assertEqual(receipt['census']['part_rows'], {
            'unit': 'part rows in supplied SQLite snapshot', 'total': 3, 'eligible': 3,
            'scanned': 3, 'skipped': 2, 'error_rows': 1, 'matched': 1, 'unscanned': 0})
        self.assertIn('subsets of scanned', receipt['counter_definition'])
        self.assertNotIn('PRIVATE_REASONING', json.dumps(result))
        self.assertCensus(receipt)

    def test_working_copy_cannot_certify_original_snapshot_atomicity(self):
        self.add('copy-fixture')
        result = ADAPTER.discover(self.db, ['needle'], source_kind='working-copy')
        receipt = result['discovery_receipt']
        self.assertTrue(receipt['snapshot']['atomic_for_supplied_source'])
        self.assertFalse(receipt['snapshot']['atomic_for_original_source'])
        self.assertTrue(any('DB+WAL' in text for text in receipt['limitations']))
        self.assertEqual(receipt['complete_scope'], 'supplied_sources_only')

    def test_parent_closure_has_ancestors_and_descendants_without_reading_claim(self):
        self.add('ancestor', text='unmatched')
        self.add('matched', parent='ancestor')
        self.add('child', parent='matched', text='unmatched')
        self.add('grandchild', parent='child', text='unmatched')
        result = ADAPTER.discover(self.db, ['needle'])
        closure = result['matching_parent_closure'][0]
        self.assertEqual(closure['ancestor_session_ids'], ['ancestor'])
        self.assertEqual(closure['descendant_session_ids'], ['child', 'grandchild'])
        self.assertTrue(closure['inventory_complete'])
        self.assertTrue(all(item['depth'] == 'unread' for item in result['inventory']))

    def test_query_groups_keep_aliases_and_literal_wildcards(self):
        self.add('group', text='LINE Bridge contains %_ literally')
        result = ADAPTER.discover(self.db, query_groups=[
            {'id': 'project-aliases', 'keywords': ['line bridge', 'line-bridge']},
            {'id': 'distinctive-token', 'keywords': ['%_']}])
        groups = result['discovery_receipt']['query_groups']
        self.assertEqual(groups[0]['query_ids'], ['q1', 'q2'])
        self.assertEqual(groups[1]['query_ids'], ['q3'])
        self.assertEqual({hit['query_id'] for hit in result['hits']}, {'q1', 'q3'})
        for group in ({'id': 'x', 'keywords': []},
                      {'id': 'x', 'keywords': ['needle'], 'operator': 'SQL'},
                      {'id': 'x', 'keywords': ['']}):
            with self.assertRaises(ValueError):
                ADAPTER.discover(self.db, query_groups=[group])

    def test_jsonl_and_sqlite_share_receipt_but_preserve_native_reports(self):
        self.add('sqlite')
        sql = ADAPTER.discover(self.db, ['needle'])
        root = self.jsonl()
        report = ADAPTER.discover([root], ['needle'])
        receipt = report['discovery_receipt']
        self.assertEqual(sql['adapter'], 'zcode-sqlite')
        self.assertEqual(report['schema_version'], 'codex-jsonl-discovery/v1')
        self.assertEqual(receipt['schema_version'], sql['discovery_receipt']['schema_version'])
        self.assertEqual(report['coverage']['record_views_matching'], 2)
        self.assertEqual(receipt['census']['record_views']['scanned'], 3)
        self.assertEqual(receipt['census']['record_views']['skipped'], 1)
        self.assertFalse(receipt['snapshot']['atomic_for_supplied_source'])
        self.assertEqual(receipt['reading']['unread'], 1)
        self.assertNotIn('PRIVATE_REASONING', json.dumps(report))
        self.assertCensus(receipt)

    def test_unavailable_and_deadline_receipts_are_not_complete(self):
        missing = ADAPTER.discover(self.base / 'missing.sqlite', ['needle'])['discovery_receipt']
        self.assertEqual(missing['status'], 'UNAVAILABLE')
        self.assertEqual(missing['source_inventory'][0]['status'], 'UNAVAILABLE')
        self.assertIsNone(missing['census']['part_rows']['total'])
        deadline = ADAPTER.discover(self.db, ['needle'], max_seconds=0)['discovery_receipt']
        self.assertEqual(deadline['status'], 'PARTIAL')
        self.assertEqual(deadline['source_inventory'][0]['status'], 'UNAVAILABLE')
        self.assertFalse(any(deadline['pagination']['end_reached'].values()))
        jsonl = ADAPTER.discover([self.base / 'missing-jsonl'], ['needle'])['discovery_receipt']
        self.assertEqual(jsonl['status'], 'PARTIAL')
        self.assertEqual(jsonl['source_inventory'][0]['status'], 'UNAVAILABLE')
        self.assertFalse(jsonl['pagination']['end_reached']['files'])

    def test_cli_emits_separate_receipt_and_refuses_overwriting_source_or_report(self):
        self.add('cli')
        output = self.base / 'report.json'
        receipt_path = self.base / 'receipt.json'
        argv = ['--db', str(self.db), '--query-group',
                '{"id":"aliases","keywords":["needle"]}', '--output', str(output),
                '--receipt-output', str(receipt_path), '--project', str(self.base)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ADAPTER.main(argv), 0)
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        self.assertEqual(receipt, json.loads(output.read_text(encoding='utf-8'))['discovery_receipt'])
        before = output.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ADAPTER.main(argv), 1)
        self.assertEqual(output.read_bytes(), before)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ADAPTER.main(['--db', str(self.db), '--keyword', 'needle', '--output', str(self.db)])


if __name__ == '__main__':
    unittest.main()
