# Public 배포 + 구글 로그인 설정

이 버전은 Streamlit 내장 `st.login()` 대신 Google Identity Services 버튼을 사용합니다.
앱 주소는 공개되지만 금융자료를 읽고 쓰기 전에 구글 로그인 서명과 허용 이메일을 서버에서 검증합니다.
가계부 저장 위치는 기존의 비공개 Google Sheets입니다.

## 1. GitHub 파일 교체

압축을 풀고 기존 저장소 파일을 덮어씁니다.
`app.py`, `auth_access.py`, `google_signin.py`, `google_login_component/`, `requirements.txt`가 함께 있어야 합니다.
구글 계정 키와 실제 금융자료는 GitHub에 올리지 않습니다.

## 2. GitHub를 Public으로 설정

저장소에서 Settings → General → Danger Zone → Change repository visibility → Public.
실제 서비스 계정 JSON, 실제 Secrets, 금융내역이 저장소에 없는 상태에서 진행하세요.

## 3. Streamlit에 배포

GitHub 저장소를 연결하고 Branch는 main, Main file path는 app.py, Python은 3.12로 설정합니다.
Secrets를 아직 넣지 않았다면 예시 화면만 열립니다.
배포 후 주소창의 `https://...streamlit.app` 주소를 복사합니다.
이미 배포된 앱은 Streamlit 앱 설정에서 공개 범위를 Public으로 맞춥니다.

## 4. 기존 내장 로그인 설정 삭제

Streamlit Secrets에 `[auth]`, `[auth.google]` 같은 섹션이 있다면 해당 섹션 전체를 삭제합니다.
`[app].allowed_emails`, 시트 ID, `[gcp_service_account]`는 유지합니다.
이 버전은 native 로그인 cookie_secret, client_secret, redirect_uri를 사용하지 않습니다.

## 5. Google Cloud 로그인 클라이언트

1. Google Cloud Console에서 프로젝트를 선택합니다.
2. Google Auth Platform → Branding에서 앱 이름과 필수 이메일을 설정합니다.
3. Audience는 개인 Gmail이면 External. Testing이면 본인 / 가족을 Test users에 추가합니다.
4. Clients → Create client → Web application 선택.
5. **Authorized JavaScript origins**에 앱 주소를 입력합니다.

```text
https://본인앱주소.streamlit.app
```

주소 뒤 `/oauth2callback`이나 `/` 같은 경로를 넣지 않습니다.
로컬 테스트를 하려면 `http://localhost:8501`도 원본 목록에 추가합니다.
팝업 callback 방식이므로 Authorized redirect URIs는 이 버전에서 필요하지 않습니다.
이전에 만든 웹 OAuth 클라이언트가 있다면 그 클라이언트의 JavaScript origins만 추가해도 됩니다.

6. Create 후 **Client ID**를 복사합니다. Client secret은 로그인에 사용하지 않습니다.

## 6. Streamlit Secrets 설정

아래 예시의 자리표시를 실제 값으로 바꿉니다. 같은 TOML 섹션을 두 번 만들지 않습니다.

```toml
[app]
spreadsheet_id = "기존_구글시트_ID"
allowed_emails = ["본인이메일@gmail.com", "가족이메일@gmail.com"]

[google_login]
client_id = "발급받은_Client_ID.apps.googleusercontent.com"

[gcp_service_account]
# 기존 서비스 계정의 모든 항목과 private_key 유지
```

시트 저장용 서비스 계정은 편집자로 시트에 공유해야 합니다.
실제 키는 Streamlit Secrets에만 넣으며 GitHub와 채팅에 보내지 않습니다.
`python prepare_secrets.py`로 전체 TOML을 생성할 수도 있습니다.

## 7. 확인

1. Secrets 저장 후 앱 재시작.
2. 구글 로그인 버튼 누르기 → 허용 계정 선택.
3. 가계부가 열리는지 확인.
4. 내역 저장 → 자료 새로고침 → 시트 반영 확인.
5. 로그아웃 후 허용되지 않은 계정으로 로그인하여 차단 확인.

Google 팝업이 안 열리면 이 사이트의 팝업을 허용합니다.
구글 버튼이 뜨지 않으면 google_login_component 폴더 업로드와 앱 주소의 JavaScript origins 등록을 확인합니다.
`origin_mismatch` 오류가 보이면 현재 앱 주소를 Google Cloud 원본 목록에 정확히 등록합니다.
테스트 상태에서는 Google Test users와 앱 allowed_emails에 모두 등록합니다.

로그인 정보는 서버 세션에만 유지됩니다. 페이지 새로고침, 세션 만료, 새 기기 접속 시 다시 로그인할 수 있습니다.
허용 가족은 같은 구글 시트의 가계부를 사용합니다. 구글 계정마다 별도 가계부를 만들지는 않습니다.

실제 Google 팝업과 Public 배포는 사용자 계정 설정 후 검증해야 합니다.
코드 테스트에서는 토큰 서명 검증 호출, 세션 nonce 연결, 허용 이메일, 만료 계정 차단을 확인했습니다.

[Google 버튼 API](https://developers.google.com/identity/gsi/web/reference/js-reference)
[서버 로그인 검증](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
