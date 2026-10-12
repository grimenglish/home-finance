import unittest
from copy import deepcopy
from finance import *

class FinanceTests(unittest.TestCase):
    def test_month_end_and_periods(self):
        self.assertEqual(due('2026-02', 31), '2026-02-28')
        self.assertEqual(due('2028-02', 31), '2028-02-29')
        self.assertEqual(due('2026-04', 31), '2026-04-30')
        d = sample('2026-10'); self.assertFalse(active(d, '2026-09'))
    def test_card_payment_not_double_expense_and_refund(self):
        d = sample('2026-10')
        op = bill_payment(d, d['bills'][2], '2026-10', 420000, '2026-10-25')
        base = restore_event(empty(), d)
        e = event(d, [op], '카드대금 출금')
        result, rejected = replay([base, e])
        self.assertFalse(rejected); self.assertEqual(totals(result, '2026-10')[1], 82000)
        t = deepcopy(d['transactions'][0]); t.update(id='refund', type='refund', amount=12000)
        result['transactions'].append(t)
        self.assertEqual(card_total(result, 'demo-card', '2026-10'), 70000)
        t['eligible'] = False
        self.assertEqual(card_total(result, 'demo-card', '2026-10'), 82000)
    def test_duplicate_bill_completion_and_retry(self):
        d = sample('2026-10'); base = restore_event(empty(), d)
        op = bill_payment(d, d['bills'][0], '2026-10', 180000, '2026-10-20')
        one = event(d, [op], '완료'); two = event(d, [op], '완료')
        result, rejected = replay([base, one, one, two])
        self.assertEqual(len(result['transactions']), 3); self.assertEqual(rejected, {two['id']})
        cancel = event(result, [operation(result, 'transactions', op['id'], None)], '취소')
        result, _ = replay([base, one, one, two, cancel])
        self.assertFalse(paid(result, 'demo-bill', '2026-10'))
    def test_simultaneous_different_records_keep_both_but_same_record_conflicts(self):
        d = sample('2026-10'); base = restore_event(empty(), d)
        a = deepcopy(d['accounts'][0]); a['balance'] = 999
        c = deepcopy(d['cards'][0]); c['target'] = 600000
        ea = event(d, [operation(d, 'accounts', a['id'], a)], '잔액')
        ec = event(d, [operation(d, 'cards', c['id'], c)], '카드')
        a['balance'] = 888; eb = event(d, [operation(d, 'accounts', a['id'], deepcopy(a))], '동시 잔액')
        data, conflicts = replay([base, ea, ec, eb])
        self.assertEqual(data['accounts'][0]['balance'], 999); self.assertEqual(data['cards'][0]['target'], 600000)
        self.assertIn(eb['id'], conflicts)
    def test_atomic_restore_conflict_and_validation(self):
        d = sample('2026-10'); base = restore_event(empty(), d)
        restore = restore_event(d, empty())
        t = deepcopy(d['transactions'][0]); t['name'] = '변경'
        change = event(d, [operation(d, 'transactions', t['id'], t)], '수정')
        data, rejected = replay([base, change, restore])
        self.assertIn(restore['id'], rejected); self.assertTrue(data['accounts'])
        bad = deepcopy(d); bad['transactions'][0]['amount'] = -1
        with self.assertRaises(ValueError): validate(bad)
        bad = deepcopy(d); bad['transactions'][0]['date'] = '2026-02-30'
        with self.assertRaises(ValueError): validate(bad)

if __name__ == '__main__': unittest.main()
