import calendar
from copy import deepcopy
from datetime import date, datetime, timedelta
import csv
import hmac
import html
import io
import json
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from finance import (KINDS, CATEGORIES, uid, empty, digest, item, due, active, transactions,
                     signed, totals, card_total, paid, needed, source_name, validate,
                     operation, event, restore_event, replay, bill_payment, sample)
from sheets_store import SheetsStore, SetupRequired, UncertainWrite

st.set_page_config(page_title='우리집 금융관리', page_icon='🏠', layout='wide')
st.markdown('''<style>
.stApp{background:#f6f7f3} .block-container{padding-top:2rem;max-width:1400px}
h1,h2,h3{color:#173f32} [data-testid="stMetric"]{background:white;border:1px solid #e3e8de;padding:22px;border-radius:15px}
[data-testid="stMetricValue"]{font-size:1.8rem} [data-testid="stTabs"] [role="tablist"]{gap:8px;border-bottom:1px solid #dce5d7}
[role="tab"]{padding:12px 20px!important;border-radius:10px 10px 0 0!important} [aria-selected="true"][role="tab"]{background:#e7efdf;color:#194b36}
.stButton>button{border-radius:9px;min-height:42px} [data-testid="stVerticalBlockBorderWrapper"]{background:white;border-radius:14px}
.hero{background:#173f32;padding:25px 30px;border-radius:16px;color:white;margin:0 0 24px}.hero h2{color:white;margin:0;font-size:26px}.hero p{margin:8px 0 0;color:#c6d8c6;font-size:14px}
.small-tag{background:#eaf3df;color:#315e36;padding:4px 10px;border-radius:5px;font-size:12px}
.calendar{width:100%;border-collapse:collapse;table-layout:fixed;background:white}.calendar th{padding:9px;color:#748168;font-size:12px}.calendar td{vertical-align:top;height:115px;border:1px solid #e4e9dd;padding:8px;font-size:12px}.calitem{background:#fff0db;border-radius:5px;padding:5px;margin:5px 0;font-size:11px}.calpaid{background:#e7efdf}
@media(max-width:700px){.block-container{padding:1rem} [role="tab"]{padding:9px 12px!important}.calendar td{height:90px;padding:3px;font-size:10px}.calitem{padding:3px;font-size:8px}.hero{padding:20px}.hero h2{font-size:22px}}
</style>''', unsafe_allow_html=True)
TODAY = datetime.now(ZoneInfo('Asia/Seoul')).date()
money = lambda n: f'{int(n):,}원'
def flash(message):
    st.session_state.pop('active_dialog', None)
    st.session_state.notice = message
    st.rerun()
def config():
    try: return dict(st.secrets)
    except Exception: return {}
CFG = config()
def authenticated():
    settings = dict(CFG.get('app', {}))
    password = str(settings.get('password', ''))
    if not password or password.startswith('CHANGE_'):
        st.title('우리집 금융관리')
        st.info('아직 연결 전입니다. 먼저 예시 화면을 둘러보세요.')
        if st.button('예시 화면 둘러보기', type='primary'):
            st.session_state.demo = True
            st.session_state.data = sample(TODAY.strftime('%Y-%m'))
            st.session_state.demo_events = [restore_event(empty(), st.session_state.data)]
            st.rerun()
        with st.expander('실제 사용 시작하기'):
            st.write('① GitHub에 코드 업로드 → ② Streamlit에 연결 → ③ 구글 시트와 Secrets 설정')
            st.caption('압축파일의 README.md에 순서대로 안내되어 있습니다. 비밀번호와 서비스 계정 키는 GitHub에 올리지 않습니다.')
        st.stop()
    if st.session_state.get('authorized'):
        return
    st.markdown('<div class="hero"><h2>우리집 금융관리</h2><p>우리집 지출과 카드 혜택을 한곳에서.</p></div>', unsafe_allow_html=True)
    left, middle, right = st.columns([1, 1.3, 1])
    with middle:
        with st.form('login'):
            entered = st.text_input('접속 비밀번호', type='password')
            submit = st.form_submit_button('입장하기', type='primary', width='stretch')
        if submit:
            import time
            if time.monotonic() < st.session_state.get('next_attempt', 0):
                st.error('잠시 후 다시 입력해 주세요.')
            elif hmac.compare_digest(entered.encode(), password.encode()):
                st.session_state.authorized = True
                st.session_state.pop('FormSubmitter:login-입장하기', None)
                st.rerun()
            else:
                st.session_state.next_attempt = time.monotonic() + 3
                st.error('비밀번호를 확인해 주세요.')
    st.stop()

if not st.session_state.get('demo'): authenticated()
DEMO = st.session_state.get('demo', False)
def store():
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
    return st.selectbox('어느 카드 / 통장인가요?', options, index=index(options, existing), format_func=lambda id: source_name(DATA, method, id) if id else '선택해 주세요')

def dismiss_dialog():
    st.session_state.pop('active_dialog', None)

@st.dialog('기록 입력', width='large', on_dismiss=dismiss_dialog)
def edit_dialog(kind, id=None, pre_card=None):
    old = deepcopy(item(DATA, kind, id)) if id else None
    x = old or {}
    st.subheader(('수정: ' if old else '추가: ') + {'accounts': '계좌', 'cards': '카드', 'bills': '자동이체', 'transactions': '수입 / 지출'}[kind])
    # Method changes rerun only this dialog; dependent source choices stay accurate.
    method = x.get('method', 'card' if pre_card else 'account')
    if kind in ('bills', 'transactions'):
        methods = ['account', 'card'] + (['cash'] if kind == 'transactions' else [])
        method = st.radio('어떻게 결제하나요?', methods, index=index(methods, method), format_func=lambda a: {'account': '통장', 'card': '카드', 'cash': '현금'}[a], horizontal=True)
    with st.form('record-form'):
        name = st.text_input({'accounts': '통장 이름', 'cards': '카드 이름', 'bills': '납부 항목', 'transactions': '어디에 썼나요? / 수입 내용'}[kind], value=x.get('name', ''), placeholder={'accounts': '예: 카카오 생활비 통장', 'cards': '예: 신한 생활비 카드', 'bills': '예: 아파트 관리비', 'transactions': '예: 마트 장보기'}[kind], max_chars=100)
        obj = dict(x)
        c1, c2 = st.columns(2)
        if kind == 'accounts':
            with c1:
                obj['bank'] = st.text_input('은행', x.get('bank', ''), placeholder='예: 카카오뱅크')
                obj['owner'] = st.text_input('소유자', x.get('owner', ''))
            with c2:
                obj['balance'] = st.number_input('현재 잔액 (원)', min_value=0, max_value=999999999999, value=x.get('balance', 0), step=10000)
                obj['last4'] = st.text_input('끝 4자리 (선택)', x.get('last4', ''), max_chars=4)
            obj['balanceDate'] = TODAY.isoformat()
        elif kind == 'cards':
            with c1:
                obj['issuer'] = st.text_input('카드사', x.get('issuer', ''))
                obj['target'] = st.number_input('매달 채울 실적 (원)', min_value=0, max_value=999999999999, value=x.get('target', 300000), step=10000)
            with c2:
                obj['owner'] = st.text_input('소유자', x.get('owner', ''))
                obj['day'] = st.number_input('카드대금 결제일', min_value=1, max_value=31, value=x.get('day', 25))
            opts = [''] + [a['id'] for a in DATA['accounts']]
            obj['account'] = st.selectbox('카드대금이 빠지는 통장', opts, index=index(opts, x.get('account')), format_func=lambda a: source_name(DATA, 'account', a) if a else '미지정')
            st.caption('카드대금 출금 일정은 자동이체 탭에 따로 등록하세요.')
        else:
            with c1:
                obj['amount'] = st.number_input('금액 (원)', min_value=0, max_value=999999999999, value=x.get('amount', 0), step=1000)
                cats = CATEGORIES + ([x['category']] if x.get('category') and x['category'] not in CATEGORIES else [])
                obj['category'] = st.selectbox('분류', cats, index=index(cats, x.get('category', '생활비')))
            with c2:
                if kind == 'bills':
                    obj['day'] = st.number_input('매달 몇 일에 나가나요?', min_value=1, max_value=31, value=x.get('day', 20))
                    obj['payee'] = st.text_input('받는 곳 (선택)', x.get('payee', ''), placeholder='예: 관리사무소 / 통신사')
                else:
                    default_date = date.fromisoformat(x['date']) if x.get('date') else (TODAY if MONTH == TODAY.strftime('%Y-%m') else date.fromisoformat(MONTH + '-01'))
                    obj['date'] = st.date_input('사용 / 입금 날짜', value=default_date).isoformat()
                    types = ['expense', 'income', 'refund', 'transfer']
                    obj['type'] = st.selectbox('거래 유형', types, index=index(types, x.get('type')), format_func=lambda a: {'expense': '지출', 'income': '수입', 'refund': '환불', 'transfer': '이체 (지출 제외)'}[a])
            obj['method'] = method
            obj['source'] = choose_source(method, x.get('source', pre_card or ''))
            if method == 'card': obj['eligible'] = st.checkbox('이 금액을 카드 실적에 포함', value=x.get('eligible', True))
            else: obj['eligible'] = False
            if kind == 'bills':
                with st.expander('기간 설정 (선택)'):
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
    x = item(DATA, kind, id)
    st.write(f"‘{x['name']}’을 삭제할까요?")
    if kind == 'bills': st.caption('기존 납부 기록은 수입지출에 유지됩니다.')
    if kind in ('accounts', 'cards'):
        method = 'account' if kind == 'accounts' else 'card'
        used = any(t.get('method') == method and t.get('source') == id for t in DATA['bills'] + DATA['transactions']) or (kind == 'accounts' and any(c.get('account') == id for c in DATA['cards']))
        if used: st.info('연결된 자동이체, 거래 내역 또는 카드를 먼저 수정해 주세요.'); return
    if st.button('삭제하기', type='primary'):
        commit(event(DATA, [operation(DATA, kind, id, None)], x['name'] + ' 삭제'))

@st.dialog('납부 완료', on_dismiss=dismiss_dialog)
def payment_dialog(bill):
    existing = paid(DATA, bill['id'], MONTH)
    if existing:
        st.write(f"{bill['name']}의 {MONTH} 완료를 취소할까요?")
        st.caption('연결된 수입지출 기록도 삭제됩니다.')
        if st.button('완료 취소', type='primary'):
            commit(event(DATA, [operation(DATA, 'transactions', existing['id'], None)], bill['name'] + ' 완료 취소'))
        return
    st.write(f"{bill['name']} / {MONTH}")
    st.caption('은행 앱에서 실제 납부 여부를 확인한 후 기록하세요.')
    with st.form('payment'):
        amount = st.number_input('실제 납부 금액 (원)', min_value=0, max_value=999999999999, value=bill['amount'], step=1000)
        day = st.date_input('납부 날짜', value=date.fromisoformat(due(MONTH, bill['day'])), min_value=date.fromisoformat(MONTH + '-01'), max_value=date.fromisoformat(due(MONTH, 31)))
        if st.form_submit_button('납부 완료 기록', type='primary', width='stretch'):
            commit(event(DATA, [bill_payment(DATA, bill, MONTH, amount, day.isoformat())], bill['name'] + ' 납부 완료'))

def open_editor(kind, id=None, pre_card=None):
    st.session_state.active_dialog = {'type': 'edit', 'kind': kind, 'id': id, 'pre_card': pre_card}
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
    p = paid(DATA, b['id'], MONTH)
    with st.container(border=True):
        a, bcol, c = st.columns([4, 2, 2], vertical_alignment='center')
        with a:
            st.markdown(f"**{b['name']}**")
            st.caption(f"{int(due(MONTH, b['day'])[-2:])}일 / {source_name(DATA, b['method'], b['source'])} → {b.get('payee') or b['category']}")
        with bcol: st.markdown('**' + money(p['amount'] if p else b['amount']) + '**')
        with c:
            if st.button('✓ 완료' if p else '완료 체크', key=prefix + ':pay:' + b['id'], type='secondary' if p else 'primary', width='stretch'): open_payment(b)

def table_rows(tx):
    types = {'income': '수입', 'expense': '지출', 'refund': '환불', 'transfer': '이체'}
    return [{'날짜': t['date'], '내용': t['name'], '유형': types[t['type']], '금액(원)': t['amount'], '분류': t['category'], '결제 수단': source_name(DATA, t['method'], t['source']), '카드 실적': '포함' if t.get('eligible') and t['method'] == 'card' else '제외', '메모': t.get('note', '')} for t in sorted(tx, key=lambda x: x['date'], reverse=True)]
def df_table(rows):
    if rows: st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    else: st.caption('아직 기록이 없습니다.')

with st.sidebar:
    st.header('우리집 가계부')
    selected = st.date_input('조회할 달', value=TODAY.replace(day=1), help='일자와 관계없이 선택한 달 전체를 조회합니다.')
    MONTH = selected.strftime('%Y-%m')
    st.caption('조회 월: ' + MONTH)
    if st.button('＋ 사용 / 수입 기록', type='primary', width='stretch'): open_editor('transactions')
    if st.button('자료 새로고침', width='stretch'):
        if not DEMO:
            try:
                st.session_state.data, _ = store().load()
                flash('최신 구글 자료를 불러왔습니다.')
            except Exception as exc: st.error(str(exc))
        else: st.toast('예시 자료입니다.')
    st.divider()
    st.caption('예시 모드 / 구글 저장 안 됨' if DEMO else '저장 위치: Google Sheets')
    st.caption('잔액과 납부 여부는 직접 확인해 주세요.')
    if st.button('예시 종료' if DEMO else '로그아웃', width='stretch'):
        st.session_state.clear()
        st.rerun()
if DEMO: st.warning('예시 화면입니다. 입력과 수정은 가능하지만 구글에는 저장되지 않습니다.')
if st.session_state.get('notice'): st.success(st.session_state.pop('notice'))
st.markdown('<div class="hero"><h2>우리집 금융관리</h2><p>언제, 어느 통장에서, 얼마나 나가는지 한눈에.</p></div>', unsafe_allow_html=True)
tabs = st.tabs(['홈', '결제달력', '자동이체', '카드실적', '계좌관리', '수입지출', '통계', '설정'])
with tabs[0]:
    income, spend = totals(DATA, MONTH)
    bills = sorted(active(DATA, MONTH), key=lambda b: b['day'])
    pending = [b for b in bills if not paid(DATA, b['id'], MONTH)]
    if not any(DATA[k] for k in KINDS):
        st.info('첫 사용 순서: ① 통장 등록 → ② 카드 등록 → ③ 자동이체 등록')
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button('① 통장 등록', key='start-account', width='stretch'): open_editor('accounts')
        with c2:
            if st.button('② 카드 등록', key='start-card', width='stretch'): open_editor('cards')
        with c3:
            if st.button('③ 자동이체 등록', key='start-bill', width='stretch'): open_editor('bills')
    c = st.columns(4)
    c[0].metric('이번 달 지출', money(spend)); c[1].metric('아직 안 낸 금액', money(sum(b['amount'] for b in pending)), f'{len(pending)}건 남음', delta_color='off')
    c[2].metric('이번 달 수입', money(income)); c[3].metric('정기 납부 예정', money(sum(b['amount'] for b in bills)))
    st.caption('지출은 완료한 납부와 직접 기록한 거래 기준. 카드대금 이체는 지출에서 제외.')
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader('이번 달 납부 일정')
        for b in bills[:8]: payment_row(b, 'home')
        if not bills: st.info('자동이체 탭에서 납부 항목을 등록하세요.')
        st.subheader('최근 사용 내역')
        df_table(table_rows(transactions(DATA, MONTH))[:5])
    with right:
        st.subheader('카드, 얼마나 더 써야 할까?')
        for card in DATA['cards']:
            used = card_total(DATA, card['id'], MONTH); goal = card['target']; remain = max(0, goal - used)
            with st.container(border=True):
                st.markdown(f"**{card['name']}**")
                st.metric('남은 실적', money(remain))
                st.progress(min(1., max(0., used / goal)) if goal else 0.)
                st.caption(f'현재 {money(used)} / 목표 {money(goal)}')
        if not DATA['cards']: st.info('카드실적 탭에서 월 목표를 등록하세요.')
        st.subheader('통장 잔액 체크')
        for account in DATA['accounts']:
            need = needed(DATA, account['id'], MONTH)
            with st.container(border=True):
                st.markdown(f"**{account['name']}**")
                st.caption(f"입력 잔액 {money(account['balance'])} / 남은 출금 {money(need)}")
                if need > account['balance']: st.warning(f"{money(need - account['balance'])} 추가 필요")
                else: st.success('입력 잔액 기준, 납부 금액 충분')
with tabs[1]:
    st.subheader(MONTH + ' 결제달력')
    st.caption('달력 아래에서 납부를 완료 처리하세요. 29~31일 일정은 월말을 넘지 않습니다.')
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(int(MONTH[:4]), int(MONTH[-2:]))
    markup = '<table class="calendar"><tr>' + ''.join(f'<th>{d}</th>' for d in ['일', '월', '화', '수', '목', '금', '토']) + '</tr>'
    for week in weeks:
        markup += '<tr>'
        for day in week:
            markup += '<td>' + (str(day) if day else '')
            if day:
                for b in active(DATA, MONTH):
                    if int(due(MONTH, b['day'])[-2:]) == day:
                        p = paid(DATA, b['id'], MONTH)
                        markup += f'<div class="calitem {"calpaid" if p else ""}">{"✓ " if p else ""}{html.escape(b["name"])}<br>{money(p["amount"] if p else b["amount"])}</div>'
            markup += '</td>'
        markup += '</tr>'
    st.markdown(markup + '</table>', unsafe_allow_html=True)
    st.write('')
    for b in sorted(active(DATA, MONTH), key=lambda x: x['day']): payment_row(b, 'calendar')
with tabs[2]:
    st.subheader('매달 나가는 돈')
    if st.button('＋ 자동이체 등록', key='new-bill', type='primary'): open_editor('bills')
    st.caption('납부 완료 시 수입지출에도 자동 반영됩니다. 은행에서 이체를 실행하는 기능은 없습니다.')
    for b in sorted(DATA['bills'], key=lambda x: x['day']):
        with st.expander(f"매월 {b['day']}일 / {b['name']} / {money(b['amount'])}"):
            st.write(f"출금: {source_name(DATA, b['method'], b['source'])} → {b.get('payee') or b['category']}")
            st.caption(f"기간: {b.get('start') or '제한 없음'} ~ {b.get('end') or '계속'}")
            row_controls('bills', b, 'bill')
            if b in active(DATA, MONTH): payment_row(b, 'bill')
    if not DATA['bills']: st.info('예: 관리비, 전기요금, 통신비, 보험료, 대출이자, 카드대금 출금')
with tabs[3]:
    st.subheader('카드별 월 실적')
    if st.button('＋ 카드 등록', key='new-card', type='primary'): open_editor('cards')
    st.caption('달력 월 기준으로 계산합니다. 카드사별 실적 제외 항목은 사용내역에서 체크해 주세요.')
    for card in DATA['cards']:
        used = card_total(DATA, card['id'], MONTH); goal = card['target']
        with st.container(border=True):
            st.subheader(card['name'])
            c1, c2, c3 = st.columns(3)
            c1.metric('현재 실적', money(used)); c2.metric('월 목표', money(goal)); c3.metric('더 사용하면 될 금액', money(max(0, goal - used)))
            st.progress(min(1., max(0., used / goal)) if goal else 0.)
            st.caption(f"결제일 {card['day']}일 / 출금 통장 {source_name(DATA, 'account', card.get('account', '')) if card.get('account') else '미지정'} / {card.get('note', '')}")
            if st.button('＋ 이 카드 사용 기록', key='record-card:' + card['id'], type='primary'): open_editor('transactions', pre_card=card['id'])
            row_controls('cards', card, 'card')
            with st.expander('이 카드의 이번 달 사용내역'):
                df_table(table_rows([t for t in transactions(DATA, MONTH) if t['method'] == 'card' and t['source'] == card['id']]))
with tabs[4]:
    st.subheader('돈이 빠지는 통장')
    if st.button('＋ 통장 등록', key='new-account', type='primary'): open_editor('accounts')
    st.caption('잔액은 은행 앱에서 확인하여 직접 입력합니다. 기록만으로 잔액이 자동 변경되지는 않습니다.')
    for a in DATA['accounts']:
        with st.container(border=True):
            st.subheader(a['name'])
            st.caption(f"{a.get('bank', '')} / {a.get('owner', '')} / 끝번호 {a.get('last4') or '미입력'}")
            need = needed(DATA, a['id'], MONTH)
            c1, c2, c3 = st.columns(3)
            c1.metric('현재 입력 잔액', money(a['balance'])); c2.metric('미완료 출금', money(need)); c3.metric('추가 필요액', money(max(0, need - a['balance'])))
            st.caption(f"잔액 입력일 {a.get('balanceDate', '미입력')} / 연결 카드: {', '.join(c['name'] for c in DATA['cards'] if c.get('account') == a['id']) or '없음'}")
            row_controls('accounts', a, 'account')
with tabs[5]:
    st.subheader('수입과 사용내역')
    if st.button('＋ 내역 기록', key='new-tx', type='primary'): open_editor('transactions')
    a, b = st.columns([3, 1])
    with a: query = st.text_input('검색', placeholder='내용, 분류, 카드 또는 통장 이름')
    with b: tfilter = st.selectbox('거래 유형', ['전체', '지출', '수입', '환불', '이체'])
    mapping = {'지출': 'expense', '수입': 'income', '환불': 'refund', '이체': 'transfer'}
    tx = [t for t in transactions(DATA, MONTH) if (tfilter == '전체' or t['type'] == mapping[tfilter]) and (not query or query.lower() in (t['name'] + t['category'] + source_name(DATA, t['method'], t['source'])).lower())]
    rows = table_rows(tx); df_table(rows)
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=['날짜', '내용', '유형', '금액(원)', '분류', '결제 수단', '카드 실적', '메모']); writer.writeheader()
    for row in rows: writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for k, v in row.items()})
    st.download_button('엑셀용 CSV 다운로드', output.getvalue().encode('utf-8-sig'), f'우리집_거래_{MONTH}.csv', mime='text/csv')
    with st.expander('내역 수정 / 삭제'):
        ids = [''] + [t['id'] for t in sorted(tx, key=lambda t: t['date'], reverse=True)]
        chosen = st.selectbox('수정할 기록', ids, format_func=lambda id: f"{item(DATA, 'transactions', id)['date']} / {item(DATA, 'transactions', id)['name']} / {money(item(DATA, 'transactions', id)['amount'])}" if id else '기록을 선택하세요')
        if chosen: row_controls('transactions', item(DATA, 'transactions', chosen), 'tx')
    st.caption('카드 사용액은 지출, 카드대금 출금은 이체로 기록합니다. 환불은 환불일에 지출과 실적에서 차감됩니다.')
with tabs[6]:
    st.subheader('우리집 지출 통계')
    inc, out = totals(DATA, MONTH)
    c1, c2, c3 = st.columns(3); c1.metric('지출', money(out)); c2.metric('수입', money(inc)); c3.metric('수입 - 지출', money(inc - out))
    st.caption('수입 - 지출은 통장 잔액과 다른 수치입니다.')
    groups = {}
    for t in transactions(DATA, MONTH): groups[t['category']] = groups.get(t['category'], 0) + signed(t)
    left, right = st.columns(2)
    with left:
        st.subheader('어디에 많이 썼을까?')
        values = {k: v for k, v in groups.items() if v}
        if values: st.bar_chart(pd.DataFrame({'지출(원)': values}))
        else: st.info('사용내역을 입력하면 분류별로 집계됩니다.')
    with right:
        st.subheader('최근 6개월 지출')
        current = date.fromisoformat(MONTH + '-01'); ms = []
        for _ in range(6): ms.append(current.strftime('%Y-%m')); current = (current - timedelta(days=1)).replace(day=1)
        values = {m: totals(DATA, m)[1] for m in reversed(ms)}
        st.bar_chart(pd.DataFrame({'지출(원)': values}))
with tabs[7]:
    st.subheader('저장과 백업')
    st.success('예시 화면: 임시 자료만 사용 중' if DEMO else 'Google Sheets 연결됨 / 저장 버튼을 누를 때 즉시 저장')
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
    st.caption('구글 시트의 금융기록 탭은 저장 이력입니다. 행을 정렬, 수정, 삭제하지 말고 앱에서 관리해 주세요.')
    st.caption('가족이 같은 앱을 사용할 수 있습니다. 다른 기기의 변경은 자료 새로고침으로 확인하세요. 같은 기록의 동시 수정은 충돌로 안내합니다.')
    with st.expander('자주 묻는 사용 방법'):
        st.write('통장 등록 → 카드 등록 → 자동이체 등록 순서로 시작하세요.')
        st.write('관리비처럼 매달 금액이 달라지면 완료 체크에서 실제 금액을 입력하세요.')
        st.write('카드대금 출금은 자동이체에 카드대금 분류로 등록하세요. 지출 통계에서 이중으로 잡히지 않습니다.')
        st.write('카드사 혜택 기준과 기록된 실적이 다를 수 있으므로 실적 제외 항목을 직접 체크해 주세요.')
st.caption('모든 금액은 원 단위입니다. 계좌와 카드는 직접 기록하며 자동조회하지 않습니다.')

if st.session_state.get('active_dialog'):
    dialog = st.session_state.active_dialog
    if dialog['type'] == 'edit': edit_dialog(dialog['kind'], dialog.get('id'), dialog.get('pre_card'))
    elif dialog['type'] == 'delete': delete_dialog(dialog['kind'], dialog['id'])
    elif dialog['type'] == 'pay': payment_dialog(item(DATA, 'bills', dialog['id']))
