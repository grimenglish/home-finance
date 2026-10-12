"""Google OIDC signs the identity; this module limits access to verified, allowed emails."""
import time
import hmac
from google.oauth2 import id_token
from google.auth.transport.requests import Request

GOOGLE_METADATA = 'https://accounts.google.com/.well-known/openid-configuration'
def auth_ready(config):
    client = dict(config.get('google_login', {})).get('client_id', '')
    return isinstance(client, str) and client.endswith('.apps.googleusercontent.com') and not client.startswith(('YOUR_', 'CHANGE_'))

def verify_login(config, credential, nonce):
    if not auth_ready(config) or not isinstance(credential, str) or not 20 <= len(credential) <= 20000 or not isinstance(nonce, str) or not nonce:
        raise ValueError('올바른 구글 로그인 정보가 아닙니다.')
    client_id = config['google_login']['client_id']
    # Signature, issuer, audience and expiry are checked by Google's library.
    claims = id_token.verify_oauth2_token(credential, Request(), audience=client_id)
    actual_nonce = claims.get('nonce')
    if not isinstance(actual_nonce, str) or not hmac.compare_digest(actual_nonce, nonce):
        raise ValueError('다른 로그인 세션의 정보입니다. 다시 로그인해 주세요.')
    permitted, reason = allowed_user(config, claims, True)
    if not permitted: raise ValueError(reason)
    # Retain verified identity only, never store the raw token in the finance log.
    return {k: claims[k] for k in ('email', 'email_verified', 'exp', 'sub') if k in claims}
def allowed_user(config, claims, logged_in, now=None):
    if not logged_in: return False, '로그인이 필요합니다.'
    raw = dict(config.get('app', {})).get('allowed_emails', [])
    if not isinstance(raw, list) or not raw: return False, '허용 계정이 아직 설정되지 않았습니다.'
    allowed = {e.strip().lower() for e in raw if isinstance(e, str)}
    email = claims.get('email', '')
    if not isinstance(email, str) or claims.get('email_verified') is not True or email.strip().lower() not in allowed:
        return False, '허용되지 않은 구글 계정입니다.'
    exp = claims.get('exp')
    if not isinstance(exp, (int, float)) or exp <= (time.time() if now is None else now): return False, '로그인이 만료되었습니다. 다시 로그인해 주세요.'
    return True, ''
