"""PC에서만 실행합니다. 실제 키와 로그인 비밀값는 표준 출력에 표시하지 않습니다."""
import json
from pathlib import Path

def quoted(value): return json.dumps(value, ensure_ascii=False)
if __name__ == '__main__':
    keypath = input('서비스 계정 JSON 파일 경로: ').strip().strip('"')
    sheetid = input('구글 시트 ID (/d/ 뒤 부분): ').strip()
    emails = [e.strip().lower() for e in input('허용할 구글 이메일 (여러 명은 쉼표로 구분): ').split(',') if e.strip()]
    client_id = input('Google OAuth 클라이언트 ID: ').strip()
    if not emails or not client_id.endswith('.apps.googleusercontent.com'):
        raise SystemExit('허용 이메일과 OAuth 클라이언트 ID를 확인하세요.')
    if not sheetid or '/' in sheetid: raise SystemExit('주소 전체가 아닌 시트 ID만 입력하세요.')
    values = json.loads(Path(keypath).read_text('utf-8'))
    if values.get('type') != 'service_account': raise SystemExit('서비스 계정 JSON이 아닙니다.')
    text = '[app]\nallowed_emails = ' + quoted(emails) + '\nspreadsheet_id = ' + quoted(sheetid) + '\n\n[google_login]\nclient_id = ' + quoted(client_id) + '\n\n[gcp_service_account]\n'
    for k, v in values.items():
        if isinstance(v, str) and k.replace('_', '').isalnum(): text += k + ' = ' + quoted(v) + '\n'
    out = Path(__file__).resolve().parent / '.streamlit' / 'secrets.toml'
    if out.exists() and input('기존 Secrets 파일을 교체할까요? yes 입력: ').strip() != 'yes': raise SystemExit('취소했습니다.')
    out.parent.mkdir(exist_ok=True)
    out.write_text(text, encoding='utf-8')
    try: out.chmod(0o600)
    except OSError: pass
    print('설정 파일을 만들었습니다: .streamlit/secrets.toml')
    print('내용을 Streamlit Secrets에 복사하세요. 이 파일과 실제 JSON 키는 GitHub에 올리지 마세요.')
