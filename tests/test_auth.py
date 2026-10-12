import unittest
from auth_access import allowed_user, auth_ready, verify_login, GOOGLE_METADATA
from unittest.mock import patch
import time

CONFIG = {'app': {'allowed_emails': ['Me@gmail.com']}, 'google_login': {'client_id': 'configured.apps.googleusercontent.com'}}
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
    def test_token_signature_verifier_and_nonce_binding(self):
        claims = {'email': 'me@gmail.com', 'email_verified': True, 'sub': 'google-id', 'exp': time.time()+3600, 'nonce': 'own-session'}
        with patch('auth_access.id_token.verify_oauth2_token', return_value=claims) as verifier:
            verified = verify_login(CONFIG, 'a'*30, 'own-session')
            self.assertEqual(verified['email'], 'me@gmail.com')
            self.assertNotIn('nonce', verified)
            self.assertEqual(verifier.call_args.kwargs['audience'], CONFIG['google_login']['client_id'])
            with self.assertRaises(ValueError): verify_login(CONFIG, 'a'*30, 'other-session')
        with patch('auth_access.id_token.verify_oauth2_token', side_effect=ValueError('Invalid signature')):
            with self.assertRaises(ValueError): verify_login(CONFIG, 'a'*30, 'own-session')

if __name__ == '__main__': unittest.main()
