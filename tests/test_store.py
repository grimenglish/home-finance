import unittest
from urllib.parse import unquote
from finance import empty, sample, restore_event, replay
from sheets_store import SheetsStore, HEADER, UncertainWrite

class FakeStore(SheetsStore):
    def __init__(self):
        self.rows = [HEADER]
        self.uncertain = False
        self.calls = []
    def request(self, method, path='', **kwargs):
        self.calls.append((method, path, kwargs))
        if method == 'GET' and not path:
            return {'sheets': [{'properties': {'title': '금융기록', 'sheetId': 1}}]}
        if method == 'GET' and path.startswith('/values/'):
            return {'values': self.rows}
        if method == 'POST' and path.endswith(':append'):
            self.rows.extend(kwargs['json']['values'])
            if self.uncertain: self.uncertain = False; raise TimeoutError('response lost')
            return {'updates': {'updatedRows': 1}}
        raise AssertionError((method, path))

class StoreTests(unittest.TestCase):
    def test_atomic_append_chunk_roundtrip(self):
        s = FakeStore(); d = sample('2026-10')
        d['accounts'][0]['note'] = '가' * 60000
        e = restore_event(empty(), d)
        self.assertEqual(s.append(e), d)
        self.assertEqual(s.rows[1][4], 2)
        append = next(x for x in s.calls if x[1].endswith(':append'))
        self.assertEqual(append[2]['params']['valueInputOption'], 'RAW')
        self.assertEqual(append[2]['params']['insertDataOption'], 'INSERT_ROWS')
        self.assertEqual(len(append[2]['json']['values']), 1)
    def test_uncertain_response_confirm_and_duplicate_retry(self):
        s = FakeStore(); e = restore_event(empty(), sample('2026-10')); s.uncertain = True
        with self.assertRaises(UncertainWrite): s.append(e)
        self.assertEqual(s.confirm(e), sample('2026-10'))
        self.assertEqual(s.append(e), sample('2026-10'))
        self.assertEqual(len(s.load()[0]['accounts']), 1)
    def test_corrupt_log_does_not_load_empty(self):
        s = FakeStore(); s.rows.append(['today', 'user', 'save', 'id', 1, 'broken-json'])
        with self.assertRaises(RuntimeError): s.load()

if __name__ == '__main__': unittest.main()
