import unittest
from auth_access import allowed_user, auth_ready, GOOGLE_METADATA

CONFIG = {'app': {'allowed_emails': ['Me@gmail.com']}, 'auth': {'redirect_uri': 'https://finance.streamlit.app/oauth2callback', 'cookie_secret': 'a' * 64, 'client_id': 'configured.apps.googleusercontent.com', 'client_secret': 'configured', 'server_metadata_url': GOOGLE_METADATA}}
class Access(unittest.TestCase):
    def test_verified_allowed_account(self):
        self.assertTrue(allowed_user(CONFIG, {'email': 'me@gmail.com', 'email_verified': True, 'exp': 2000}, True, now=1000)[0])
        self.assertTrue(auth_ready(CONFIG))
    def test_unlisted_unverified_expired_or_logged_out_are_denied(self):
        for claims, logged in [({'email': 'other@gmail.com', 'email_verified': True, 'exp': 2000}, True), ({'email': 'me@gmail.com', 'email_verified': False, 'exp': 2000}, True), ({'email': 'me@gmail.com', 'email_verified': True, 'exp': 999}, True), ({'email': 'me@gmail.com', 'email_verified': True}, True), ({'email': 'me@gmail.com', 'email_verified': True, 'exp': 2000}, False)]:
            self.assertFalse(allowed_user(CONFIG, claims, logged, now=1000)[0])
    def test_missing_or_malformed_allowlist_denied(self):
        claims = {'email': 'me@gmail.com', 'email_verified': True, 'exp': 2000}
        for conf in [{}, {'app': {'allowed_emails': 'me@gmail.com'}}]:
            self.assertFalse(allowed_user(conf, claims, True, now=1000)[0])

if __name__ == '__main__': unittest.main()
