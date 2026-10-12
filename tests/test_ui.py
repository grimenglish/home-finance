import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')
def label(elements, name): return next(x for x in elements if x.label == name)
class UI(unittest.TestCase):
    def demo(self):
        at = AppTest.from_file(APP, default_timeout=30).run()
        label(at.button, '예시 화면 둘러보기').click().run()
        self.assertFalse(at.exception)
        return at
    def test_tabs_and_account_save(self):
        at = self.demo()
        self.assertEqual([x.label for x in at.tabs], ['홈', '결제달력', '자동이체', '카드실적', '계좌관리', '수입지출', '통계', '설정'])
        at.button(key='new-account').click().run()
        label(at.text_input, '통장 이름').set_value('새 통장')
        label(at.number_input, '현재 잔액 (원)').set_value(500000)
        label(at.button, '저장하기').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any(a['name'] == '새 통장' and a['balance'] == 500000 for a in at.session_state['data']['accounts']))
    def test_payment_complete_and_cancel(self):
        at = self.demo()
        at.button(key='home:pay:demo-bill').click().run()
        label(at.number_input, '실제 납부 금액 (원)').set_value(192000)
        label(at.button, '납부 완료 기록').click().run()
        self.assertFalse(at.exception)
        records = [t for t in at.session_state['data']['transactions'] if t.get('billId') == 'demo-bill']
        self.assertEqual(len(records), 1); self.assertEqual(records[0]['amount'], 192000)
        at.button(key='home:pay:demo-bill').click().run()
        label(at.button, '완료 취소').click().run()
        self.assertFalse(at.exception)
        self.assertFalse(any(t.get('billId') == 'demo-bill' for t in at.session_state['data']['transactions']))
    def test_card_transaction_and_performance(self):
        at = self.demo()
        at.button(key='record-card:demo-card').click().run()
        label(at.text_input, '어디에 썼나요? / 수입 내용').set_value('커피')
        label(at.number_input, '금액 (원)').set_value(5000)
        label(at.button, '저장하기').click().run()
        self.assertFalse(at.exception)
        record = next(t for t in at.session_state['data']['transactions'] if t['name'] == '커피')
        self.assertEqual(record['source'], 'demo-card'); self.assertTrue(record['eligible'])
        self.assertTrue(any(x.value == '87,000원' for x in at.metric))
    def test_google_login_gate_hides_finance(self):
        from unittest.mock import patch
        from test_auth import CONFIG
        at = AppTest.from_file(APP, default_timeout=30)
        at.secrets['app'] = CONFIG['app']; at.secrets['google_login'] = CONFIG['google_login']
        with patch('google_signin.google_button', return_value=None): at.run()
        self.assertFalse(at.exception); self.assertEqual(len(at.tabs), 0)
        self.assertTrue(any(h.value == '구글 계정으로 로그인' for h in at.subheader))
    def test_unallowed_google_account_cannot_read_or_retain_data(self):
        from unittest.mock import patch
        from test_auth import CONFIG
        at = AppTest.from_file(APP, default_timeout=30)
        at.secrets['app'] = CONFIG['app']; at.secrets['google_login'] = CONFIG['google_login']
        at.session_state['data'] = {'sensitive': 'must be cleared'}
        at.session_state['authorized'] = True
        at.session_state['google_claims'] = {'email': 'other@gmail.com', 'email_verified': True, 'exp': 9999999999}
        with patch('google_signin.google_button', return_value=None): at.run()
        self.assertFalse(at.exception); self.assertEqual(len(at.tabs), 0)
        self.assertTrue(any('허용되지 않은' in e.value for e in at.warning))
        with self.assertRaises(KeyError): _ = at.session_state['data']
    def test_verified_component_response_enters_app(self):
        from unittest.mock import patch
        from test_auth import CONFIG
        import time
        at = AppTest.from_file(APP, default_timeout=30)
        at.secrets['app'] = CONFIG['app']; at.secrets['google_login'] = CONFIG['google_login']
        identity = {'email': 'me@gmail.com', 'email_verified': True, 'sub': 'google-id', 'exp': time.time()+3600}
        with patch('google_signin.google_button', return_value={'credential':'a'*30}), patch('auth_access.verify_login', return_value=identity): at.run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['google_claims'], identity)
        self.assertTrue(any('구글 시트' in e.value for e in at.error))

if __name__ == '__main__': unittest.main()
