# 구글 계정으로 로그인하기

이 버전은 접속 비밀번호 대신 구글 계정을 사용합니다.
본인과 가족 이메일을 허용 목록에 넣어야 가계부에 접근할 수 있습니다.
로그인 기능은 금융자료를 저장하는 서비스 계정과 별도로 설정합니다.

## 1. GitHub 코드 교체

압축을 풀고 기존 저장소에 내용을 덮어씁니다.
특히 `app.py`, `auth_access.py`, `requirements.txt`를 함께 반영하세요.
실제 Secrets와 계정 키는 GitHub에 올리지 않습니다.

## 2. Streamlit 앱 주소 확인

앱을 배포했다면 주소창의 `https://...streamlit.app` 주소를 복사합니다.
아직 배포 전이라면 먼저 Streamlit에서 GitHub 저장소를 연결해 `app.py`로 배포하세요.
로그인 설정 전에는 실제 금융자료를 불러오지 않고 예시 화면만 제공합니다.

## 3. Google Cloud에서 로그인 앱 만들기

1. [Google Cloud Console](https://console.cloud.google.com/)에서 기존 프로젝트를 선택합니다.
2. **Google Auth Platform**을 엽니다.
3. **Branding**에서 앱 이름을 `우리집 금융관리`로 입력하고 필수 이메일을 설정합니다.
4. **Audience**에서 개인 Gmail 계정을 쓴다면 External을 선택합니다.
5. Testing 상태에서는 **Test users**에 본인과 가족 이메일을 추가합니다.
6. **Clients → Create client**를 누릅니다.
7. Application type은 **Web application**을 선택합니다.
8. **Authorized redirect URIs**에 아래 주소를 넣습니다.

```text
https://본인앱주소.streamlit.app/oauth2callback
```

실제 앱 주소 뒤에 `/oauth2callback`을 붙이는 것입니다. 철자, 대소문자, https가 정확히 일치해야 합니다.
이 방식에서는 JavaScript origins 입력은 필요하지 않습니다.
생성한 **Client ID**와 **Client secret**을 본인 PC에 보관합니다.

## 4. Streamlit Secrets 변경

Streamlit 앱의 설정에서 Secrets를 엽니다.
기존 서비스 계정 설정은 유지하고 `[app]`과 `[auth]`를 다음처럼 설정합니다.
같은 이름의 TOML 섹션을 두 번 만들지 마세요.
예시의 자리표시는 실제 값으로 바꿉니다.

```toml
[app]
spreadsheet_id = "기존_구글시트_ID"
allowed_emails = ["본인이메일@gmail.com", "가족이메일@gmail.com"]

[auth]
redirect_uri = "https://본인앱주소.streamlit.app/oauth2callback"
cookie_secret = "본인PC에서_새로_생성한_무작위_문자열"
client_id = "발급받은_Client_ID"
client_secret = "발급받은_Client_secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[gcp_service_account]
# 기존 서비스 계정 항목과 비밀키를 그대로 유지
```

기존 `[app].password`는 삭제할 수 있습니다. 이 버전에서는 사용하지 않습니다.
`cookie_secret`은 본인 PC에서 다음 명령으로 새로 생성하고, 결과를 Secrets에만 넣으세요.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

또는 `python prepare_secrets.py`로 전체 설정 파일을 생성할 수 있습니다.
로그인 허용 이메일은 주소 전체를 입력합니다. 이름이나 `@gmail.com`만 입력하지 않습니다.

## 5. 로그인 확인

1. Secrets를 저장하고 앱을 재시작합니다.
2. **구글 계정으로 로그인**을 누릅니다.
3. 허용 목록에 넣은 본인 계정을 선택합니다.
4. 가계부 화면이 열리는지 확인합니다.
5. 다른 계정을 선택하면 접근이 차단되는지 확인합니다.
6. 기존 구글 시트에 저장과 새로고침이 정상적으로 되는지 확인합니다.

가족은 Google Cloud Test users와 Streamlit allowed_emails에 모두 등록해야 테스트 상태에서 이용할 수 있습니다.
가계부는 지정한 시트 한 개를 함께 사용합니다. 계정별로 다른 시트를 만드는 방식은 아닙니다.

## 오류가 보이면

- `redirect_uri_mismatch`: Google Cloud와 Secrets의 callback 주소를 정확하게 맞추기
- `access_denied`: Google Cloud의 Test users 확인
- 허용되지 않은 계정: `[app].allowed_emails`에 실제 로그인한 이메일 등록
- 로그인 만료: 로그아웃 후 다시 로그인
- Authlib 오류: 최신 `requirements.txt`를 GitHub에 반영하고 Streamlit 재시작
- 구글 저장 권한 오류: 로그인 OAuth 설정과 별개로 시트를 서비스 계정에 편집자로 공유하기

실제 구글 로그인 왕복 과정은 계정 설정 후 본인 웹앱에서 확인해야 합니다.
코드 테스트에서는 허용 목록, 이메일 확인, 만료 토큰 차단을 확인합니다.

[Streamlit 공식 구글 로그인 안내](https://docs.streamlit.io/develop/tutorials/authentication/google)
