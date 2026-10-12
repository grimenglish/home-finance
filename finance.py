from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
from uuid import uuid4

KINDS = ('accounts', 'cards', 'bills', 'transactions')
CATEGORIES = ['생활비', '식비', '쇼핑', '관리비', '전기', '가스', '수도', '통신', '보험', '대출이자', '카드대금', '급여', '기타']
def uid(): return str(uuid4())
def empty(): return {'version': 1, **{k: [] for k in KINDS}}
def digest(x): return sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
def item(data, kind, id): return next((x for x in data[kind] if x['id'] == id), None)
def due(month, day):
    y, m = map(int, month.split('-'))
    return date(y, m, min(int(day), monthrange(y, m)[1])).isoformat()
def active(data, month): return [b for b in data['bills'] if (not b.get('start') or b['start'] <= month) and (not b.get('end') or b['end'] >= month)]
def transactions(data, month): return [t for t in data['transactions'] if t['date'][:7] == month]
def signed(t): return int(t['amount']) if t['type'] == 'expense' else -int(t['amount']) if t['type'] == 'refund' else 0
def totals(data, month):
    tx = transactions(data, month)
    return sum(t['amount'] for t in tx if t['type'] == 'income'), sum(signed(t) for t in tx)
def card_total(data, card, month): return sum(signed(t) for t in transactions(data, month) if t['method'] == 'card' and t['source'] == card and t.get('eligible'))
def paid(data, bill, month): return item(data, 'transactions', 'bill:' + bill + ':' + month) or next((t for t in data['transactions'] if t.get('billId') == bill and t.get('billMonth') == month), None)
def needed(data, account, month): return sum(b['amount'] for b in active(data, month) if b['method'] == 'account' and b['source'] == account and not paid(data, b['id'], month))
def source_name(data, method, id):
    if method == 'cash': return '현금'
    return (item(data, 'cards' if method == 'card' else 'accounts', id) or {}).get('name', '삭제된 항목')
def validate(data):
    if not isinstance(data, dict) or data.get('version') != 1: raise ValueError('지원하지 않는 백업 형식입니다.')
    for k in KINDS:
        if not isinstance(data.get(k), list) or len(data[k]) > 100000: raise ValueError('잘못된 기록 형식입니다.')
        seen = set()
        for x in data[k]:
            if not isinstance(x, dict) or not isinstance(x.get('id'), str) or not isinstance(x.get('name'), str) or not x['name'].strip() or x['id'] in seen: raise ValueError('중복 ID 또는 잘못된 이름입니다.')
            seen.add(x['id'])
            for field in {'accounts': ['balance'], 'cards': ['target'], 'bills': ['amount'], 'transactions': ['amount']}[k]:
                if not isinstance(x.get(field), int) or isinstance(x[field], bool) or not 0 <= x[field] <= 999999999999: raise ValueError('금액은 0 이상의 정수로 입력하세요.')
            if k in ('bills', 'cards') and (not isinstance(x.get('day'), int) or not 1 <= x['day'] <= 31): raise ValueError('납부일은 1~31일입니다.')
            if k == 'bills':
                for v in ('start', 'end'):
                    if x.get(v): datetime.strptime(x[v], '%Y-%m')
                if x.get('start') and x.get('end') and x['start'] > x['end']: raise ValueError('종료 월은 시작 월 이후여야 합니다.')
            if k == 'transactions':
                date.fromisoformat(x['date'])
                if x.get('type') not in ('expense', 'income', 'refund', 'transfer'): raise ValueError('잘못된 거래 유형입니다.')
            if k in ('bills', 'transactions'):
                if x.get('method') not in ('account', 'card', 'cash') or (k == 'bills' and x['method'] == 'cash'): raise ValueError('잘못된 결제 수단입니다.')
                if x['method'] != 'cash' and not isinstance(x.get('source'), str): raise ValueError('결제 수단을 선택하세요.')
    return data
def operation(data, kind, id, value):
    if kind not in KINDS: raise ValueError('잘못된 항목입니다.')
    return {'kind': kind, 'id': id, 'expected': digest(item(data, kind, id)), 'value': deepcopy(value)}
def event(data, ops, label, actor='우리집'):
    return {'id': uid(), 'time': datetime.now().astimezone().isoformat(), 'actor': actor, 'label': label, 'ops': deepcopy(ops)}
def restore_event(data, new):
    validate(new)
    return {'id': uid(), 'time': datetime.now().astimezone().isoformat(), 'actor': '우리집', 'label': '백업 복원', 'replace': deepcopy(new), 'expected': digest(data)}
def replay(events):
    data, seen, rejected = empty(), set(), set()
    for e in events:
        if e['id'] in seen: continue
        seen.add(e['id'])
        try:
            if 'replace' in e:
                if e['expected'] != digest(data): raise ValueError('충돌')
                new = deepcopy(e['replace'])
            else:
                new = deepcopy(data)
                for op in e['ops']:
                    k, id = op['kind'], op['id']
                    if k not in KINDS or digest(item(new, k, id)) != op['expected']: raise ValueError('충돌')
                    new[k] = [x for x in new[k] if x['id'] != id]
                    if op['value'] is not None:
                        if op['value']['id'] != id: raise ValueError('ID 불일치')
                        new[k].append(deepcopy(op['value']))
            data = validate(new)
        except (ValueError, TypeError, KeyError): rejected.add(e['id'])
    return data, rejected
def bill_payment(data, bill, month, amount, payment_date):
    id = 'bill:' + bill['id'] + ':' + month
    if payment_date[:7] != month: raise ValueError('선택 월 안의 날짜를 입력해 주세요.')
    t = {'id': id, 'name': bill['name'], 'amount': int(amount), 'date': payment_date, 'category': bill['category'], 'method': bill['method'], 'source': bill['source'], 'eligible': bill.get('eligible', False), 'type': 'transfer' if bill['category'] == '카드대금' else 'expense', 'billId': bill['id'], 'billMonth': month, 'note': '납부 완료'}
    return operation(data, 'transactions', id, t)
def sample(month):
    d = empty(); a, c = 'demo-account', 'demo-card'
    d['accounts'] = [{'id': a, 'name': '생활비 통장', 'bank': '카카오뱅크', 'owner': '우리집', 'balance': 1200000, 'balanceDate': date.today().isoformat(), 'last4': '1234'}]
    d['cards'] = [{'id': c, 'name': '생활비 카드', 'issuer': '예시 카드', 'owner': '우리집', 'target': 300000, 'day': 25, 'account': a, 'note': '관리비 실적 제외 (예시)'}]
    d['bills'] = [{'id': 'demo-bill', 'name': '아파트 관리비', 'day': 20, 'amount': 180000, 'category': '관리비', 'method': 'account', 'source': a, 'payee': '관리사무소', 'start': month, 'end': '', 'eligible': False}, {'id': 'demo-internet', 'name': '인터넷 요금', 'day': 15, 'amount': 33000, 'category': '통신', 'method': 'card', 'source': c, 'payee': '통신사', 'start': month, 'end': '', 'eligible': True}, {'id': 'demo-statement', 'name': '카드대금 출금', 'day': 25, 'amount': 420000, 'category': '카드대금', 'method': 'account', 'source': a, 'payee': '카드사', 'start': month, 'end': '', 'eligible': False}]
    d['transactions'] = [{'id': 'demo-tx', 'name': '마트 장보기', 'date': month + '-03', 'amount': 82000, 'category': '생활비', 'type': 'expense', 'method': 'card', 'source': c, 'eligible': True}, {'id': 'demo-income', 'name': '생활비 입금', 'date': month + '-01', 'amount': 2100000, 'category': '급여', 'type': 'income', 'method': 'account', 'source': a, 'eligible': False}]
    return d
