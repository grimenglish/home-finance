import calendar
from copy import deepcopy
from datetime import date, datetime, timedelta
import csv
import html
import io
import json
import secrets
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from finance import (KINDS, CATEGORIES, uid, empty, digest, item, due, active, transactions,
                     signed, totals, card_total, paid, needed, source_name, validate,
                     operation, event, restore_event, replay, bill_payment, sample)
from finance import bill_amount, bill_summary, monthly_amount_operation
from finance import (expense_type, in_scope, scheduled, add_months, installment_amount,
                     installment_details, installment_estimate)
from sheets_store import SheetsStore, SetupRequired, UncertainWrite
from auth_access import auth_ready, allowed_user, verify_login
from google_signin import google_button

st.set_page_config(page_title='내 출금 캘린더', page_icon='📅', layout='wide')
st.markdown('''<style>
.stApp{background:#f6f7f3} .block-container{padding-top:2rem;max-width:1400px}
h1,h2,h3{color:#173f32} [data-testid="stMetric"]{background:white;border:1px solid #e3e8de;padding:22px;border-radius:15px}
[data-testid="stMetricValue"]{font-size:1.8rem} [data-testid="stTabs"] [role="tablist"]{gap:8px;border-bottom:1px solid #dce5d7}
[data-testid="stMetricLabel"]{font-weight:600}.schedule-line{display:flex;align-items:center;gap:14px}.schedule-line .date-tile{min-width:50px;padding:8px;font-size:23px}.schedule-name{font-size:17px;font-weight:650;margin:2px 0}.schedule-meta{color:#6e7973;font-size:12px;margin-top:3px}.summary-chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 18px}.summary-chip{background:#fff;border:1px solid #e1e7e1;padding:7px 12px;border-radius:9px;font-size:13px}.date-tile{background:#edf3ed;color:#173f32;border-radius:12px;padding:12px;text-align:center;font-size:26px;font-weight:750}.date-tile small{display:block;font-size:12px;font-weight:500}.badge{display:inline-block;padding:3px 9px;border-radius:6px;font-size:12px;margin:0 5px 6px 0;background:#e7eee7;color:#265a43}.badge.variable{background:#fff1da;color:#865509}.badge.card{background:#eee9ff;color:#604593}.badge.once{background:#e5efff;color:#3562a2}
[role="tab"]{padding:12px 20px!important;border-radius:10px 10px 0 0!important} [aria-selected="true"][role="tab"]{background:#e7efdf;color:#194b36}
.stButton>button{border-radius:9px;min-height:42px} [data-testid="stVerticalBlockBorderWrapper"]{background:white;border-radius:14px}
.hero{background:#173f32;padding:25px 30px;border-radius:16px;color:white;margin:0 0 24px}.hero h2{color:white;margin:0;font-size:26px}.hero p{margin:8px 0 0;color:#c6d8c6;font-size:14px}
.small-tag{background:#eaf3df;color:#315e36;padding:4px 10px;border-radius:5px;font-size:12px}
.calendar{width:100%;border-collapse:collapse;table-layout:fixed;background:white}.calendar th{padding:9px;color:#748168;font-size:12px}.calendar td{vertical-align:top;height:115px;border:1px solid #e4e9dd;padding:8px;font-size:12px}.calitem{background:#fff0db;border-radius:5px;padding:5px;margin:5px 0;font-size:11px}.calpaid{background:#e7efdf}
@media(max-width:700px){.block-container{padding:1rem} [role="tab"]{padding:9px 12px!important}.calendar td{height:90px;padding:3px;font-size:10px}.calitem{padding:3px;font-size:8px}.hero{padding:20px}.hero h2{font-size:22px}}
</style>''', unsafe_allow_html=True)
TODAY = datetime.now(ZoneInfo('Asia/Seoul')).date()
money = lambda n: f'{int(n):,}원'
def amount_label(amount): return money(amount) if amount is not None else '금액 미정'
def summary_label(bills):
    total, unknown = bill_summary(DATA, bills, MONTH)
    return money(total) + (f' + 미정 {unknown}건' if unknown else '')
def flash(message):
    st.session_state.pop('active_dialog', None)
    st.session_state.notice = message
    st.rerun()
def config():
    try: return dict(st.secrets)
    except Exception: return {}
CFG = config()
def logout_session():
    st.session_state.clear()
    st.rerun()

def authenticated():
    if not auth_ready(CFG):
        st.title('우리집 금융관리')
        st.info('구글 로그인 연결 전입니다. 아래에서 예시를 둘러볼 수 있습니다.')
        if st.button('예시 화면 둘러보기', type='primary'):
            st.session_state.demo = True
            st.session_state.data = sample(TODAY.strftime('%Y-%m'))
            st.session_state.demo_events = [restore_event(empty(), st.session_state.data)]
            st.rerun()
        with st.expander('Public 배포용 구글 로그인 설정'):
            st.write('Google Cloud에서 웹 OAuth 클라이언트를 만든 뒤 승인된 JavaScript 원본에 앱 주소를 넣고, Streamlit Secrets의 [google_login]에 클라이언트 ID를 설정하세요.')
            st.caption('이 버전에서는 [auth] 설정을 사용하지 않습니다. GOOGLE_LOGIN_SETUP.md를 따라 설정하세요.')
        st.stop()
    claims = st.session_state.get('google_claims')
    if claims:
        permitted, reason = allowed_user(CFG, claims, True)
        if permitted:
            st.session_state.login_email = claims['email'].strip().lower()
            return
        for key in ('data', 'store', 'pending', 'active_dialog', 'google_claims', 'login_email'):
            st.session_state.pop(key, None)
        st.session_state.pop('login_nonce', None)
        st.warning(reason)
    st.markdown('<div class="hero"><h2>우리집 금융관리</h2><p>본인 구글 계정으로 들어오세요.</p></div>', unsafe_allow_html=True)
    left, middle, right = st.columns([1, 1.3, 1])
    with middle:
        st.subheader('구글 계정으로 로그인')
        if 'login_nonce' not in st.session_state:
            st.session_state.login_nonce = secrets.token_urlsafe(32)
        credential = google_button(CFG['google_login']['client_id'], st.session_state.login_nonce)
        st.caption('허용한 본인 / 가족 계정만 금융자료를 볼 수 있습니다.')
        if credential:
            try:
                if not isinstance(credential, dict): raise ValueError('로그인 응답 형식이 올바르지 않습니다.')
                with st.spinner('구글 계정 확인 중…'):
                    identity = verify_login(CFG, credential.get('credential'), st.session_state.login_nonce)
                st.session_state.google_claims = identity
                st.session_state.pop('login_nonce', None)
                st.rerun()
            except ValueError as exc:
                for key in ('data', 'store', 'pending', 'active_dialog'):
                    st.session_state.pop(key, None)
                st.error(str(exc))
            except Exception:
                st.error('구글 로그인 검증에 연결하지 못했습니다. 잠시 후 다시 시도하세요.')
        if st.button('다른 계정으로 다시 시도'):
            st.session_state.pop('login_nonce', None)
            st.rerun()
    st.stop()

if not st.session_state.get('demo'): authenticated()
DEMO = st.session_state.get('demo', False)
def store():
    if DEMO: raise ValueError('예시 모드에서는 실제 구글 자료에 접근하지 않습니다.')
    authenticated()
    if 'store' not in st.session_state:
        app_cfg = dict(CFG.get('app', {}))
        if not app_cfg.get('spreadsheet_id') or not CFG.get('gcp_service_account'):
            raise ValueError('Streamlit Secrets에 구글 시트 ID와 서비스 계정을 설정해 주세요.')
        st.session_state.store = SheetsStore(app_cfg['spreadsheet_id'], CFG['gcp_service_account'])
    return st.session_state.store
if 'data' not in st.session_state:
    try:
        with st.spinner('구글 자료 불러오는 중…'):
            st.session_state.data, conflicts = store().load()
    except SetupRequired:
        st.title('구글 시트 연결 준비')
        st.write('처음 한 번만 전용 기록 탭을 준비하면 됩니다. 기존 다른 탭은 유지됩니다.')
        if st.button('구글 시트 연결 완료하기', type='primary'):
            try:
                store().initialize()
                st.rerun()
            except Exception as exc: st.error(str(exc))
        st.stop()
    except Exception as exc:
        st.error(str(exc))
        if st.button('다시 불러오기'): st.rerun()
        st.stop()
DATA = st.session_state.data

def commit(e):
    if not DEMO:
        authenticated()
        e['actor'] = st.session_state.login_email
    try:
        if DEMO:
            events = st.session_state.demo_events + [e]
            d, rejected = replay(events)
            if e['id'] in rejected: raise ValueError('다른 수정과 충돌했습니다. 새로 불러온 뒤 다시 수정하세요.')
            st.session_state.demo_events = events
            st.session_state.data = d
        else:
            st.session_state.pending = e
            with st.spinner('구글에 저장 중…'):
                result = store().append(e)
                if result is None: raise UncertainWrite('저장 여부를 다시 확인해 주세요.')
                st.session_state.data = result
            st.session_state.pop('pending', None)
        flash('예시 자료를 변경했습니다.' if DEMO else '구글 시트에 저장했습니다.')
    except UncertainWrite as exc: st.error(str(exc))
    except Exception as exc:
        st.session_state.pop('pending', None)
        st.error(str(exc))

if st.session_state.get('pending'):
    st.warning('앞선 저장 결과를 아직 확인하지 못했습니다. 먼저 확인한 뒤 계속 사용하세요.')
    st.download_button('현재 자료 JSON 백업', json.dumps(DATA, ensure_ascii=False, indent=2), '우리집_현재자료.json')
    pending = st.session_state.pending
    if st.button('저장 여부 확인', type='primary'):
        try:
            result = store().confirm(pending)
            if result is None: st.session_state.retry_allowed = True; st.info('기록이 확인되지 않았습니다. 아래 재시도로 같은 기록을 저장할 수 있습니다.')
            else:
                st.session_state.data = result
                st.session_state.pop('pending', None)
                st.session_state.pop('retry_allowed', None)
                flash('저장을 확인했습니다.')
        except ValueError as exc:
            st.session_state.pop('pending', None)
            st.session_state.data, _ = store().load()
            flash(str(exc))
        except Exception as exc: st.error(str(exc))
    if st.session_state.get('retry_allowed') and st.button('같은 기록 저장 재시도'):
        commit(pending)
    st.stop()

def index(options, value): return options.index(value) if value in options else 0
def choose_source(method, existing=''):
    if method == 'cash': return ''
    rows = DATA['cards' if method == 'card' else 'accounts']
    options = [''] + [x['id'] for x in rows]
    return st.selectbox('카드 선택' if method == 'card' else '통장 선택', options, index=index(options, existing), format_func=lambda id: source_name(DATA, method, id) if id else '선택해 주세요')

def dismiss_dialog():
    st.session_state.pop('active_dialog', None)

TYPE_LABELS = {'fixed': '고정', 'variable': '변동', 'card': '카드 청구', 'once': '일회성', 'installment': '할부'}
SCOPE_LABELS = {'personal': '개인', 'business': '사업장', 'all': '전체'}

@st.dialog('출금 항목 등록', width='large', on_dismiss=dismiss_dialog)
def expense_dialog(id=None, preset=None):
    if not DEMO: authenticated()
    old = deepcopy(item(DATA, 'bills', id)) if id else None
    x = old or {}
    choices = ['fixed', 'variable', 'card', 'once']
    kind = st.radio('지출 종류', choices, index=index(choices, expense_type(x) if old else preset or 'fixed'),
                    format_func=lambda k: {'fixed': '고정 지출', 'variable': '변동 지출', 'card': '카드 청구액', 'once': '일회성 지출'}[k], horizontal=True)
    with st.form('expense-form'):
        name = st.text_input('납부 항목', x.get('name', ''), placeholder='예: 사업장 전기료 / KB국민카드 / 보험료', max_chars=100)
        scope = st.radio('개인 / 사업장', ['personal', 'business'], index=index(['personal', 'business'], x.get('scope', 'personal')), format_func=lambda v: SCOPE_LABELS[v], horizontal=True)
        c1, c2 = st.columns(2)
        with c1:
            amount = x.get('amount', 0)
            if kind in ('variable', 'card'):
                st.info('매월 청구액을 입력하는 항목입니다. 처음에는 금액 미정으로 표시됩니다.')
            else:
                amount = st.number_input('매달 나가는 금액 (원)' if kind == 'fixed' else '나갈 금액 (원)', min_value=0, max_value=999999999999, value=amount, step=1000)
        with c2:
            if kind == 'once':
                single_date = st.date_input('출금 날짜', date.fromisoformat(due(x.get('start') or MONTH, x.get('day', TODAY.day))))
                day = single_date.day; start = end = single_date.strftime('%Y-%m')
            else:
                day = st.number_input('매달 몇 일에 나가나요?', min_value=1, max_value=31, value=x.get('day', 25))
                start = x.get('start', MONTH); end = x.get('end', '')
        method = x.get('method', 'account')
        if method == 'card' and kind != 'card':
            st.caption('이 항목은 카드 사용 내역입니다. 출금 합계에는 카드 청구액만 반영됩니다.')
        if kind == 'card': method = 'account'
        source = choose_source(method, x.get('source', ''))
        if kind != 'once':
            with st.expander('시작 / 종료 월 (선택)'):
                c1, c2 = st.columns(2)
                with c1: start = st.text_input('시작 월', start, placeholder='2026-10')
                with c2: end = st.text_input('종료 월', end, placeholder='비워두면 계속')
        note = st.text_input('메모 (선택)', x.get('note', ''), max_chars=300)
        submitted = st.form_submit_button('저장하기' if DEMO else '구글에 저장하기', type='primary', width='stretch')
    if submitted:
        try:
            if not name.strip(): raise ValueError('납부 항목을 입력해 주세요.')
            if not source: raise ValueError('출금 통장을 먼저 등록하고 선택해 주세요.')
            obj = {**x, 'id': id or uid(), 'name': name.strip(), 'scope': scope, 'expenseType': kind,
                   'amount': amount, 'day': day, 'start': start, 'end': end, 'method': method, 'source': source,
                   'variable': kind in ('variable', 'card'), 'category': '카드대금' if kind == 'card' else (x.get('category', '기타') if x.get('category') != '카드대금' else '기타'), 'note': note}
            new = deepcopy(DATA); new['bills'] = [b for b in new['bills'] if b['id'] != obj['id']] + [obj]; validate(new)
            commit(event(DATA, [operation(DATA, 'bills', obj['id'], obj)], name.strip() + ' 출금 항목 저장'))
        except Exception as exc: st.error(str(exc))

def open_expense(preset=None):
    st.session_state.active_dialog = {'type': 'expense', 'preset': preset}
    st.rerun()

@st.dialog('카드 할부 등록', width='large', on_dismiss=dismiss_dialog)
def installment_dialog(id=None):
    if not DEMO: authenticated()
    x = deepcopy(item(DATA, 'bills', id)) if id else {}
    parents = [b for b in DATA['bills'] if expense_type(b) == 'card' and b['method'] == 'account']
    if not parents:
        st.info('먼저 카드 청구 항목의 결제일과 출금 통장을 등록하세요.')
        if st.button('카드 청구 항목 등록', type='primary'): open_expense('card')
        return
    with st.form('installment-form'):
        name = st.text_input('할부 내용', x.get('name', ''), placeholder='예: 쿠팡 냉장고', max_chars=100)
        options = [b['id'] for b in parents]
        parent_id = st.selectbox('합산될 카드 청구 항목', options, index=index(options, x.get('parentBill')), format_func=lambda v: item(DATA, 'bills', v)['name'])
        total = st.number_input('할부 원금 총액 (원)', min_value=1, max_value=999999999999, value=x.get('total', 1200000), step=10000)
        months = st.number_input('할부 개월 수', min_value=1, max_value=120, value=x.get('months', 6))
        first = st.date_input('첫 청구 월', date.fromisoformat(x.get('firstMonth', MONTH) + '-01'), help='구매 월이 아닌 첫 할부금이 청구되는 월을 선택하세요. 날짜는 무시됩니다.').strftime('%Y-%m')
        note = st.text_input('메모 (선택)', x.get('note', ''), max_chars=300)
        st.caption('원금 균등 분할 예상입니다. 이자·수수료는 카드 청구액에 포함해서 입력하세요.')
        submitted = st.form_submit_button('할부 저장', type='primary', width='stretch')
    if submitted:
        try:
            if not name.strip(): raise ValueError('할부 내용을 입력해 주세요.')
            parent = item(DATA, 'bills', parent_id)
            obj = {**x, 'id': id or uid(), 'name': name.strip(), 'expenseType': 'installment',
                   'parentBill': parent_id, 'total': total, 'months': months, 'firstMonth': first,
                   'start': first, 'end': add_months(first, months - 1), 'day': parent['day'], 'amount': 0,
                   'category': '카드대금', 'method': 'account', 'source': parent['source'], 'scope': parent.get('scope', 'personal'), 'note': note}
            new = deepcopy(DATA); new['bills'] = [b for b in new['bills'] if b['id'] != obj['id']] + [obj]; validate(new)
            commit(event(DATA, [operation(DATA, 'bills', obj['id'], obj)], name.strip() + ' 할부 저장'))
        except Exception as exc: st.error(str(exc))

def open_installment(id=None):
    st.session_state.active_dialog = {'type': 'installment', 'id': id}
    st.rerun()

@st.dialog('받은 돈 기록', on_dismiss=dismiss_dialog)
def receipt_dialog(id=None):
    if not DEMO: authenticated()
    old = deepcopy(item(DATA, 'transactions', id)) if id else None
    x = old or {}
    method = st.radio('어떻게 받았나요?', ['cash', 'account'],
                      index=index(['cash', 'account'], x.get('method', 'cash')),
                      format_func=lambda v: {'cash': '현금', 'account': '계좌 입금'}[v], horizontal=True)
    with st.form('receipt-form'):
        scope = st.radio('기록 구분', ['personal', 'business'], index=index(['personal', 'business'], x.get('scope', 'personal')), format_func=lambda v: SCOPE_LABELS[v], horizontal=True)
        sender = st.text_input('누구에게 받았나요?', x.get('sender', x.get('name', '')), placeholder='예: 엄마', max_chars=100)
        amount = st.number_input('받은 금액 (원)', min_value=0, max_value=999999999999, value=x.get('amount', 0), step=10000)
        default_date = date.fromisoformat(x['date']) if x.get('date') else (TODAY if MONTH == TODAY.strftime('%Y-%m') else date.fromisoformat(MONTH + '-01'))
        received_date = st.date_input('받은 날짜', default_date).isoformat()
        source = choose_source(method, x.get('source', ''))
        note = st.text_input('메모 (선택)', x.get('note', ''), placeholder='예: 이번 달 생활비', max_chars=300)
        submitted = st.form_submit_button('저장하기' if DEMO else '구글에 저장하기', type='primary', width='stretch')
    if submitted:
        try:
            if not sender.strip(): raise ValueError('돈을 준 사람을 입력해 주세요.')
            if amount <= 0: raise ValueError('받은 금액을 입력해 주세요.')
            if method == 'account' and not source: raise ValueError('입금받은 통장을 선택해 주세요. 통장은 통장·카드 메뉴에서 등록할 수 있습니다.')
            obj = {**x, 'id': id or uid(), 'name': sender.strip(), 'sender': sender.strip(), 'type': 'income',
                   'amount': amount, 'date': received_date, 'method': method, 'source': source,
                   'category': x.get('category', '기타'), 'eligible': False, 'note': note, 'scope': scope}
            new = deepcopy(DATA); new['transactions'] = [t for t in new['transactions'] if t['id'] != obj['id']] + [obj]; validate(new)
            commit(event(DATA, [operation(DATA, 'transactions', obj['id'], obj)], sender.strip() + ' 받은 돈 ' + ('수정' if old else '추가')))
        except Exception as exc: st.error(str(exc))

@st.dialog('기록 입력', width='large', on_dismiss=dismiss_dialog)
def edit_dialog(kind, id=None, pre_card=None):
    if not DEMO: authenticated()
    old = deepcopy(item(DATA, kind, id)) if id else None
    x = old or {}
    st.subheader(('수정: ' if old else '추가: ') + {'accounts': '계좌', 'cards': '카드', 'bills': '자동이체', 'transactions': '수입 / 지출'}[kind])
    # Method changes rerun only this dialog; dependent source choices stay accurate.
    method = x.get('method', 'card' if pre_card else 'account')
    if kind in ('bills', 'transactions'):
        methods = ['account', 'card'] + (['cash'] if kind == 'transactions' else [])
        method = st.radio('어떻게 결제하나요?', methods, index=index(methods, method), format_func=lambda a: {'account': '통장', 'card': '카드', 'cash': '현금'}[a], horizontal=True)
    variable = False
    if kind == 'bills':
        variable = st.radio('금액은 어떻게 정해지나요?', [False, True], index=int(x.get('variable', False)),
                            format_func=lambda v: '매달 달라요 (전기료·가스비 등)' if v else '매달 같아요', horizontal=True)
    with st.form('record-form'):
        name = st.text_input({'accounts': '통장 이름', 'cards': '카드 이름', 'bills': '납부 항목', 'transactions': '어디에 썼나요? / 수입 내용'}[kind], value=x.get('name', ''), placeholder={'accounts': '예: 카카오 생활비 통장', 'cards': '예: 신한 생활비 카드', 'bills': '예: 아파트 관리비', 'transactions': '예: 마트 장보기'}[kind], max_chars=100)
        obj = dict(x)
        c1, c2 = st.columns(2)
        if kind == 'accounts':
            with c1:
                obj['bank'] = st.text_input('은행', x.get('bank', ''), placeholder='예: 카카오뱅크')
            obj.setdefault('balance', 0)
            obj.setdefault('owner', '')
            obj.setdefault('last4', '')
        elif kind == 'cards':
            with c1:
                obj['issuer'] = st.text_input('카드사', x.get('issuer', ''))
            with c2:
                obj['day'] = st.number_input('카드대금 결제일', min_value=1, max_value=31, value=x.get('day', 25))
            obj.setdefault('target', 0)
            obj.setdefault('owner', '')
            opts = [''] + [a['id'] for a in DATA['accounts']]
            obj['account'] = st.selectbox('카드대금이 빠지는 통장', opts, index=index(opts, x.get('account')), format_func=lambda a: source_name(DATA, 'account', a) if a else '미지정')
            st.caption('카드대금 출금은 자동이체에 따로 등록하세요.')
        else:
            with c1:
                if kind == 'bills' and variable:
                    obj['amount'] = x.get('amount', 0)
                    st.info('고지서가 나오면 ‘이번 달 금액 입력’에서 청구액을 넣으세요.')
                else:
                    obj['amount'] = st.number_input('매달 나가는 금액 (원)' if kind == 'bills' else '금액 (원)', min_value=0, max_value=999999999999, value=x.get('amount', 0), step=1000)
                if kind == 'transactions':
                    cats = CATEGORIES + ([x['category']] if x.get('category') and x['category'] not in CATEGORIES else [])
                    obj['category'] = st.selectbox('분류', cats, index=index(cats, x.get('category', '생활비')))
            with c2:
                if kind == 'bills':
                    obj['day'] = st.number_input('매달 몇 일에 나가나요?', min_value=1, max_value=31, value=x.get('day', 20))
                    obj.setdefault('payee', '')
                else:
                    default_date = date.fromisoformat(x['date']) if x.get('date') else (TODAY if MONTH == TODAY.strftime('%Y-%m') else date.fromisoformat(MONTH + '-01'))
                    obj['date'] = st.date_input('사용 / 입금 날짜', value=default_date).isoformat()
                    types = ['expense', 'income', 'refund', 'transfer']
                    obj['type'] = st.selectbox('거래 유형', types, index=index(types, x.get('type')), format_func=lambda a: {'expense': '지출', 'income': '수입', 'refund': '환불', 'transfer': '이체 (지출 제외)'}[a])
            obj['method'] = method
            obj['source'] = choose_source(method, x.get('source', pre_card or ''))
            obj['eligible'] = x.get('eligible', False) if method == 'card' else False
            if kind == 'bills':
                obj['variable'] = variable
                card_payment = st.checkbox('카드대금 출금 항목', value=x.get('category') == '카드대금', help='카드 사용액과 중복 지출로 계산되지 않도록 표시합니다.')
                obj['category'] = '카드대금' if card_payment else (x.get('category', '기타') if x.get('category') != '카드대금' else '기타')
                with st.expander('시작 / 종료 월 (선택)'):
                    l, r = st.columns(2)
                    with l: obj['start'] = st.text_input('시작 월', x.get('start', MONTH), placeholder='2026-10')
                    with r: obj['end'] = st.text_input('종료 월', x.get('end', ''), placeholder='비워두면 계속')
        obj['note'] = st.text_input('메모 (선택)', x.get('note', ''), max_chars=300)
        submitted = st.form_submit_button('저장하기' if DEMO else '구글에 저장하기', type='primary', width='stretch')
    if submitted:
        try:
            if not name.strip(): raise ValueError('이름을 입력해 주세요.')
            if kind in ('bills', 'transactions') and method != 'cash' and not obj['source']: raise ValueError('통장이나 카드를 먼저 등록한 뒤 선택해 주세요.')
            if kind == 'accounts' and obj['last4'] and (len(obj['last4']) != 4 or not obj['last4'].isdigit()): raise ValueError('끝번호는 숫자 4자리로 입력하세요.')
            if kind == 'transactions' and obj.get('billMonth') and obj['date'][:7] != obj['billMonth']: raise ValueError('납부 완료 기록은 같은 월 안에서 수정해 주세요.')
            if kind == 'transactions' and obj['category'] == '카드대금' and obj['type'] == 'expense': raise ValueError('카드대금 출금은 이체 유형으로 기록해 주세요.')
            obj.update(id=id or uid(), name=name.strip())
            new = deepcopy(DATA); new[kind] = [v for v in new[kind] if v['id'] != obj['id']] + [obj]; validate(new)
            commit(event(DATA, [operation(DATA, kind, obj['id'], obj)], f'{name} ' + ('수정' if old else '추가')))
        except Exception as exc: st.error(str(exc))

@st.dialog('삭제 확인', on_dismiss=dismiss_dialog)
def delete_dialog(kind, id):
    if not DEMO: authenticated()
    x = item(DATA, kind, id)
    st.write(f"‘{x['name']}’을 삭제할까요?")
    if kind == 'bills': st.caption('기존 납부 기록은 납부내역에 유지됩니다.')
    if kind == 'bills' and installment_details(DATA, id):
        st.info('연결된 할부 내역을 먼저 다른 카드 청구 항목으로 옮기거나 삭제하세요.')
        return
    if kind in ('accounts', 'cards'):
        method = 'account' if kind == 'accounts' else 'card'
        used = any(t.get('method') == method and t.get('source') == id for t in DATA['bills'] + DATA['transactions']) or (kind == 'accounts' and any(c.get('account') == id for c in DATA['cards']))
        if used: st.info('연결된 자동이체, 거래 내역 또는 카드를 먼저 수정해 주세요.'); return
    if st.button('삭제하기', type='primary'):
        commit(event(DATA, [operation(DATA, kind, id, None)], x['name'] + ' 삭제'))

@st.dialog('납부 완료', on_dismiss=dismiss_dialog)
def payment_dialog(bill):
    if not DEMO: authenticated()
    existing = paid(DATA, bill['id'], MONTH)
    if existing:
        st.write(f"{bill['name']}의 {MONTH} 완료를 취소할까요?")
        st.caption('이 항목의 해당 월 납부 기록도 삭제됩니다.')
        if st.button('완료 취소', type='primary'):
            commit(event(DATA, [operation(DATA, 'transactions', existing['id'], None)], bill['name'] + ' 완료 취소'))
        return
    st.write(f"{bill['name']} / {MONTH}")
    st.caption('은행 앱에서 실제 납부 여부를 확인한 후 기록하세요.')
    with st.form('payment'):
        amount = st.number_input('실제 납부 금액 (원)', min_value=0, max_value=999999999999, value=bill_amount(DATA, bill, MONTH), step=1000, placeholder='실제 출금된 금액을 입력하세요')
        day = st.date_input('납부 날짜', value=date.fromisoformat(due(MONTH, bill['day'])), min_value=date.fromisoformat(MONTH + '-01'), max_value=date.fromisoformat(due(MONTH, 31)))
        if st.form_submit_button('납부 완료 기록', type='primary', width='stretch'):
            if amount is None: st.error('실제 납부 금액을 입력해 주세요.')
            else: commit(event(DATA, [bill_payment(DATA, bill, MONTH, amount, day.isoformat())], bill['name'] + ' 납부 완료'))

@st.dialog('이번 달 금액 입력', on_dismiss=dismiss_dialog)
def monthly_amount_dialog(bill):
    if not DEMO: authenticated()
    st.write(f"{MONTH} / {bill['name']}")
    st.caption('이 달의 청구액만 저장합니다. 다른 달의 금액은 바뀌지 않습니다.')
    if expense_type(bill) == 'card':
        st.info('이번 달 할부 원금 예상: ' + money(installment_estimate(DATA, bill['id'], MONTH)))
        st.caption('아래에는 할부와 일시불, 이자 등을 포함한 카드 명세서 총 청구액을 입력하세요. 할부 원금을 따로 더하지 않습니다.')
    with st.form('monthly-amount'):
        amount = st.number_input('이번 달 청구액 (원)', min_value=0, max_value=999999999999,
                                 value=bill.get('monthlyAmounts', {}).get(MONTH), step=1000, placeholder='고지서 금액')
        clear = st.checkbox('금액 미정으로 되돌리기')
        submitted = st.form_submit_button('청구액 저장', type='primary', width='stretch')
    if submitted:
        try:
            if amount is None and not clear: raise ValueError('청구액을 입력해 주세요.')
            op = monthly_amount_operation(DATA, bill, MONTH, None if clear else amount)
            commit(event(DATA, [op], bill['name'] + ' ' + MONTH + ' 청구액 저장'))
        except Exception as exc: st.error(str(exc))

def open_monthly_amount(bill):
    st.session_state.active_dialog = {'type': 'monthly_amount', 'id': bill['id']}
    st.rerun()

def open_editor(kind, id=None, pre_card=None):
    receipt = kind == 'transactions' and not pre_card and (not id or item(DATA, kind, id).get('type') == 'income')
    type_ = 'receipt' if receipt else ('installment' if kind == 'bills' and id and expense_type(item(DATA, kind, id)) == 'installment' else 'expense' if kind == 'bills' else 'edit')
    st.session_state.active_dialog = {'type': type_, 'kind': kind, 'id': id, 'pre_card': pre_card}
    st.rerun()
def open_delete(kind, id):
    st.session_state.active_dialog = {'type': 'delete', 'kind': kind, 'id': id}
    st.rerun()
def open_payment(bill):
    st.session_state.active_dialog = {'type': 'pay', 'id': bill['id']}
    st.rerun()

def row_controls(kind, x, prefix):
    a, b = st.columns(2)
    with a:
        if st.button('수정', key=prefix + ':edit:' + x['id'], width='stretch'): open_editor(kind, x['id'])
    with b:
        if st.button('삭제', key=prefix + ':del:' + x['id'], width='stretch'): open_delete(kind, x['id'])
def payment_row(b, prefix):
    p = paid(DATA, b['id'], MONTH); amount = bill_amount(DATA, b, MONTH); kind = expense_type(b)
    day = int(due(MONTH, b['day'])[-2:]); scope = b.get('scope', 'personal')
    with st.container(border=True):
        title, actions = st.columns([3, 1.8], vertical_alignment='center')
        with title:
            meta = html.escape(source_name(DATA, b['method'], b['source']))
            if p: meta += ' / 납부일 ' + p['date']
            elif MONTH == TODAY.strftime('%Y-%m') and day < TODAY.day: meta += ' / 출금 확인 필요'
            st.markdown(f'<div class="schedule-line"><div class="date-tile">{day:02d}<small>{int(MONTH[-2:])}월</small></div><div><span class="badge {kind}">{TYPE_LABELS[kind]}</span><span class="badge">{SCOPE_LABELS[scope]}</span><div class="schedule-name">{html.escape(b["name"])}</div><div class="schedule-meta">{meta}</div></div></div>', unsafe_allow_html=True)
            if kind == 'card':
                estimate = installment_estimate(DATA, b['id'], MONTH)
                if estimate: st.caption('할부 원금 예상 ' + money(estimate) + ' 포함')
        with actions:
            st.markdown('**' + amount_label(amount) + '**')
            if b.get('variable') and not p:
                c1,c2=st.columns(2)
                with c1:
                    if st.button('금액 수정' if amount is not None else '금액 입력', key=prefix + ':amount:' + b['id'], width='stretch'): open_monthly_amount(b)
                with c2:
                    if st.button('완료 체크', key=prefix + ':pay:' + b['id'], width='stretch'): open_payment(b)
            elif st.button('✓ 납부 완료' if p else '완료 체크', key=prefix + ':pay:' + b['id'], type='secondary', width='stretch'): open_payment(b)
        if kind == 'card' and installment_details(DATA, b['id'], MONTH):
            with st.expander('이번 달 할부 상세'):
                df_table([{'할부 내용': x['name'], '이번 달 예상(원)': installment_amount(x, MONTH), '마지막 청구 월': add_months(x['firstMonth'], x['months']-1)} for x in installment_details(DATA, b['id'], MONTH)])

def table_rows(tx):
    types = {'income': '수입', 'expense': '지출', 'refund': '환불', 'transfer': '이체'}
    return [{'날짜': t['date'], '내용': t['name'], '유형': types[t['type']], '금액(원)': t['amount'], '분류': t['category'], '결제 수단': source_name(DATA, t['method'], t['source']), '카드 실적': '포함' if t.get('eligible') and t['method'] == 'card' else '제외', '메모': t.get('note', '')} for t in sorted(tx, key=lambda x: x['date'], reverse=True)]
def df_table(rows):
    if rows: st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    else: st.caption('아직 기록이 없습니다.')

header, period, scope_control = st.columns([2.5, 1.4, 2])
with header:
    st.markdown('## 내 출금 캘린더')
    st.caption('언제 · 어느 통장에서 · 얼마가 나가는지')
with period:
    selected = st.date_input('조회할 달', value=TODAY.replace(day=1), help='선택한 달 전체를 조회합니다.')
    MONTH = selected.strftime('%Y-%m')
with scope_control:
    SCOPE = st.radio('조회 구분', ['all', 'personal', 'business'], format_func=lambda v: SCOPE_LABELS[v], horizontal=True)
with st.sidebar:
    st.header('출금 일정 관리')
    if st.button('＋ 출금 항목 등록', type='primary', width='stretch'): open_expense()
    if st.button('＋ 받은 돈 기록', width='stretch'): open_editor('transactions')
    if st.button('자료 새로고침', width='stretch'):
        if not DEMO:
            try:
                st.session_state.data, _ = store().load(); flash('최신 구글 자료를 불러왔습니다.')
            except Exception as exc: st.error(str(exc))
        else: st.toast('예시 자료입니다.')
    st.divider()
    st.caption('예시 모드 / 구글 저장 안 됨' if DEMO else 'Google Sheets에 저장')
    if not DEMO: st.caption('로그인: ' + st.session_state.login_email)
    if st.button('예시 종료' if DEMO else '로그아웃', width='stretch'): logout_session()
if DEMO: st.warning('예시 화면입니다. 입력과 수정은 가능하지만 구글에는 저장되지 않습니다.')
if st.session_state.get('notice'): st.success(st.session_state.pop('notice'))
tabs = st.tabs(['이번 달', '지출 항목', '할부 관리', '받은 돈', '설정'])
bills = sorted(scheduled(DATA, MONTH, SCOPE), key=lambda b: (b['day'], b['name']))
pending_bills = [b for b in bills if not paid(DATA, b['id'], MONTH)]
completed_bills = [b for b in bills if paid(DATA, b['id'], MONTH)]
receipts = [t for t in transactions(DATA, MONTH) if t['type'] == 'income' and in_scope(t, SCOPE)]
with tabs[0]:
    if not DATA['accounts']:
        st.info('출금 통장의 이름만 등록하면 시작할 수 있어요. 잔액은 필요 없습니다.')
        if st.button('통장 등록', key='start-account', type='primary'): open_editor('accounts')
    cards = [b for b in bills if expense_type(b) == 'card']
    fixed = [b for b in bills if expense_type(b) == 'fixed']
    variable = [b for b in bills if expense_type(b) == 'variable']
    once = [b for b in bills if expense_type(b) == 'once']
    total, unknown = bill_summary(DATA, bills, MONTH)
    remaining, remaining_unknown = bill_summary(DATA, pending_bills, MONTH)
    c = st.columns(3)
    c[0].metric('이번 달 확인된 총액', money(total))
    c[1].metric('앞으로 나갈 금액', money(remaining), f'{len(pending_bills)}건 남음', delta_color='off')
    c[2].metric('금액 미입력', f'{unknown}건')
    if unknown: st.warning(f'청구액 미입력 {unknown}건 — 위 금액은 입력된 항목만 합산한 금액입니다.')
    groups = [('고정', fixed), ('변동', variable), ('카드 청구', cards), ('일회성', once)]
    chips = ''.join(f'<span class="summary-chip">{title} <strong>{summary_label(rows)}</strong></span>' for title,rows in groups if rows)
    st.markdown('<div class="summary-chips">' + chips + '</div>', unsafe_allow_html=True)
    bar = st.columns([3, 1])
    with bar[0]: status = st.radio('출금 목록', ['남은 출금', '금액 미입력', '전체 일정'], horizontal=True, label_visibility='collapsed')
    with bar[1]:
        if st.button('＋ 지출 등록', key='home-new-bill', width='stretch'): open_expense()
    displayed = [b for b in pending_bills if bill_amount(DATA,b,MONTH) is None] if status == '금액 미입력' else bills if status == '전체 일정' else pending_bills
    view = st.radio('일정 보기', ['날짜순', '고정 / 변동 구분'], horizontal=True)
    if view == '날짜순':
        for b in displayed: payment_row(b, 'home')
    else:
        for kind in ('fixed', 'variable', 'card', 'once'):
            subset = [b for b in displayed if expense_type(b) == kind]
            if subset:
                st.markdown('**' + TYPE_LABELS[kind] + '**')
                for b in subset: payment_row(b, 'home')
    if not displayed: st.info('금액 미입력 항목이 없습니다.' if status == '금액 미입력' else '표시할 출금 일정이 없습니다.')
    if completed_bills and status != '전체 일정':
        with st.expander(f'납부 완료 {len(completed_bills)}건'):
            for b in completed_bills: payment_row(b, 'home')
    with st.expander('출금 달력 보기'):
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(int(MONTH[:4]), int(MONTH[-2:]))
        markup = '<table class="calendar"><tr>' + ''.join(f'<th>{d}</th>' for d in ['일', '월', '화', '수', '목', '금', '토']) + '</tr>'
        for week in weeks:
            markup += '<tr>'
            for day in week:
                markup += '<td>' + (str(day) if day else '')
                if day:
                    for b in bills:
                        if int(due(MONTH, b['day'])[-2:]) == day:
                            p = paid(DATA, b['id'], MONTH)
                            markup += f'<div class="calitem {"calpaid" if p else ""}">{"✓ " if p else ""}{html.escape(b["name"])}<br>{amount_label(bill_amount(DATA, b, MONTH))}</div>'
                markup += '</td>'
            markup += '</tr>'
        st.markdown(markup + '</table>', unsafe_allow_html=True)
    with st.expander('월별 요약 / 지난달 비교'):
        st.write(f"납부 완료 {len(completed_bills)}건 / " + money(bill_summary(DATA,completed_bills,MONTH)[0]))
        st.write('받은 돈 ' + money(sum(t['amount'] for t in receipts)))
        previous = add_months(MONTH, -1); previous_bills = scheduled(DATA,previous,SCOPE)
        if previous_bills:
            prev_total, prev_unknown = bill_summary(DATA,previous_bills,previous)
            st.write(f'전월 확인액 {money(prev_total)} / 이번 달 확인액 {money(total)}')
            if unknown or prev_unknown: st.caption('미입력 청구액이 있어 최종 증감은 아직 미정입니다.')
            else: st.write((f'{money(total-prev_total)} 증가' if total>=prev_total else f'{money(prev_total-total)} 감소'))
        else: st.caption('지난달 등록된 출금 일정이 없습니다.')
        st.caption('할부 상세는 카드 청구액에 포함되며 따로 합산하지 않습니다.')
with tabs[1]:
    st.subheader('등록한 지출 항목')
    c = st.columns(3)
    with c[0]:
        if st.button('＋ 고정 / 변동 등록', key='new-bill', type='primary'): open_expense()
    with c[1]:
        if st.button('＋ 카드 청구 등록'): open_expense('card')
    with c[2]:
        if st.button('＋ 일회성 등록'): open_expense('once')
    kind_filter = st.radio('항목 구분', ['all', 'fixed', 'variable', 'card', 'once'], format_func=lambda v: '전체' if v == 'all' else TYPE_LABELS[v], horizontal=True)
    for b in sorted(DATA['bills'], key=lambda b: (b['day'], b['name'])):
        if expense_type(b) == 'installment' or not in_scope(b, SCOPE) or (kind_filter != 'all' and expense_type(b) != kind_filter): continue
        with st.container(border=True):
            title, controls = st.columns([3, 1])
            with title:
                st.markdown(f"**{b['name']}** / {TYPE_LABELS[expense_type(b)]} / {SCOPE_LABELS[b.get('scope','personal')]}")
                st.caption(f"{b['day']}일 / {source_name(DATA, b['method'], b['source'])} / 기간 {b.get('start') or '계속'} ~ {b.get('end') or '계속'}")
                if b['method'] == 'card': st.caption('카드 사용 항목 — 통장 출금 합계에는 카드 명세서 청구액으로 반영됩니다.')
            with controls: row_controls('bills', b, 'bill')
    with st.expander('이번 달 납부 기록 / 이전 사용내역'):
        tx = sorted([t for t in transactions(DATA, MONTH) if t['type'] != 'income' and in_scope(t, SCOPE)], key=lambda t: t['date'], reverse=True)
        df_table([{'날짜': t['date'], '항목': t['name'], '금액(원)': t['amount'], '출금 수단': source_name(DATA, t['method'], t['source'])} for t in tx])
        for t in tx:
            with st.expander(f"{t['date']} / {t['name']} / {money(t['amount'])}"): row_controls('transactions', t, 'history')
with tabs[2]:
    st.subheader('카드 할부')
    if st.button('＋ 할부 등록', key='new-installment', type='primary'): open_installment()
    st.info('할부는 카드 청구액의 상세내역입니다. 카드 청구 총액을 입력하면 출금 합계에 한 번만 반영됩니다.')
    details = [b for b in DATA['bills'] if expense_type(b) == 'installment' and in_scope(b, SCOPE)]
    current = [b for b in details if b['firstMonth'] <= MONTH <= add_months(b['firstMonth'], b['months'] - 1)]
    st.metric('이번 달 할부 원금 예상', money(sum(installment_amount(b, MONTH) for b in current)))
    mode = st.radio('할부 표시', ['진행 / 예정', '종료', '전체'], horizontal=True)
    for b in sorted(details, key=lambda b: (b['firstMonth'], b['name'])):
        end = add_months(b['firstMonth'], b['months']-1); finished = MONTH > end
        if (mode == '진행 / 예정' and finished) or (mode == '종료' and not finished): continue
        parent = item(DATA, 'bills', b['parentBill']); y,m=map(int,MONTH.split('-')); fy,fm=map(int,b['firstMonth'].split('-'))
        elapsed = (y-fy)*12 + m-fm; before = max(0, min(b['months'], elapsed))
        with st.container(border=True):
            st.markdown(f"**{b['name']}** / {parent['name']}")
            c1,c2,c3=st.columns(3)
            c1.metric('원금 총액', money(b['total'])); c2.metric('이번 달 예상', money(installment_amount(b, MONTH))); c3.metric('남은 예정 회차', str(b['months']-before)+'회')
            st.progress(before / b['months'])
            st.caption(f"첫 청구 {b['firstMonth']} → 마지막 {end} / 총 {b['months']}개월 / " + ('종료' if finished else '청구 시작 전' if elapsed < 0 else f'{elapsed+1}회차 예정'))
            st.caption('회차는 청구 월 기준이며 실제 납부 여부는 카드 청구 항목에서 확인합니다.')
            row_controls('bills', b, 'installment')
    if not details: st.caption('구매 내용, 총액, 할부 개월 수, 첫 청구 월을 등록하세요.')
with tabs[3]:
    st.subheader('받은 돈')
    if st.button('＋ 받은 돈 기록', key='new-tx', type='primary'): open_editor('transactions')
    st.metric('이번 달 받은 돈 합계', money(sum(t['amount'] for t in receipts)))
    tx = sorted(receipts, key=lambda t: t['date'], reverse=True)
    df_table([{'받은 날짜': t['date'], '준 사람': t.get('sender', t['name']), '금액(원)': t['amount'],
               '받은 방법': source_name(DATA, t['method'], t['source']), '메모': t.get('note', '')} for t in tx])
    for t in tx:
        with st.expander(f"{t['date']} / {t.get('sender', t['name'])} / {money(t['amount'])}"):
            row_controls('transactions', t, 'receipt')

with tabs[4]:
    st.subheader('출금 통장')
    if st.button('＋ 통장 등록', key='new-account', type='primary'): open_editor('accounts')
    st.caption('통장 이름과 은행만 입력하세요. 잔액 입력은 필요 없습니다.')
    for a in DATA['accounts']:
        with st.container(border=True):
            st.markdown(f"**{a['name']}**"); st.caption(a.get('bank','')); row_controls('accounts',a,'account')
    with st.expander('이전 카드 등록 정보'):
        if st.button('＋ 카드 등록', key='new-card'): open_editor('cards')
        for card in DATA['cards']:
            st.markdown(f"**{card['name']}**"); row_controls('cards',card,'card')
    with st.expander('백업과 복원'):
        st.download_button('전체 JSON 백업 다운로드', json.dumps(DATA, ensure_ascii=False, indent=2), f'우리집_전체백업_{TODAY}.json', mime='application/json')
        with st.expander('백업 파일 복원'):
            uploaded = st.file_uploader('JSON 백업 파일', type=['json'])
            agree = st.checkbox('현재 자료를 백업 파일의 자료로 교체합니다.')
            if st.button('백업 복원', disabled=not uploaded or not agree):
                try:
                    if uploaded.size > 2 * 1024 * 1024: raise ValueError('2MB 이하의 JSON 파일을 선택하세요.')
                    new = validate(json.loads(uploaded.getvalue()))
                    commit(restore_event(DATA, {k: new[k] for k in ('version', *KINDS)}))
                except Exception as exc: st.error(str(exc))

    st.caption('가족의 변경 사항은 자료 새로고침으로 확인하세요.')
    st.caption('출금은 은행에서 직접 확인합니다. 이 앱은 일정과 기록을 관리합니다.')

if st.session_state.get('active_dialog'):
    dialog = st.session_state.active_dialog
    if dialog['type'] == 'receipt': receipt_dialog(dialog.get('id'))
    elif dialog['type'] == 'expense': expense_dialog(dialog.get('id'), dialog.get('preset'))
    elif dialog['type'] == 'installment': installment_dialog(dialog.get('id'))
    elif dialog['type'] == 'edit': edit_dialog(dialog['kind'], dialog.get('id'), dialog.get('pre_card'))
    elif dialog['type'] == 'delete': delete_dialog(dialog['kind'], dialog['id'])
    elif dialog['type'] == 'pay': payment_dialog(item(DATA, 'bills', dialog['id']))
    elif dialog['type'] == 'monthly_amount': monthly_amount_dialog(item(DATA, 'bills', dialog['id']))
