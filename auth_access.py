"""Google OIDC signs the identity; this module limits access to verified, allowed emails."""
import time

GOOGLE_METADATA = 'https://accounts.google.com/.well-known/openid-configuration'
def auth_ready(config):
    auth = dict(config.get('auth', {}))
    fields = ('redirect_uri', 'cookie_secret', 'client_id', 'client_secret')
    return all(isinstance(auth.get(k), str) and auth[k] and not auth[k].startswith(('YOUR_', 'CHANGE_')) for k in fields) and auth.get('server_metadata_url') == GOOGLE_METADATA
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
