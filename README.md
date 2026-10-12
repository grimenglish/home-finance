# 우리집 금융관리

Streamlit 화면, GitHub 코드 관리, Google Sheets 자료 저장 방식의 웹 가계부입니다.
컴퓨터와 휴대폰에서 같은 주소로 접속할 수 있습니다.

## 처음 시작하는 순서

1. 통장 등록: 생활비 통장 이름과 현재 잔액을 입력합니다.
2. 카드 등록: 카드 이름, 매달 채울 실적, 결제일, 출금 통장을 입력합니다.
3. 자동이체 등록: 관리비, 공과금, 보험료, 이자, 카드대금 출금 등을 등록합니다.
4. 사용 기록: 카드 사용이나 수입이 있을 때 기록합니다.
5. 납부 확인: 은행 앱에서 실제 출금을 확인한 뒤 완료 체크합니다.

홈에서 지출, 미완료 납부, 남은 카드 실적, 필요한 통장 잔액을 확인합니다.
저장 버튼을 누르면 Google Sheets에 바로 기록합니다. 구글 로그인 팝업은 매번 필요하지 않습니다.

## 파일 구성

- `app.py`: 8개 탭과 입력 화면
- `google_signin.py`, `google_login_component/`: Public 앱의 구글 로그인 버튼
- `auth_access.py`: 허용 구글 계정 확인
- `finance.py`: 금액, 실적, 납부 계산
- `sheets_store.py`: Google Sheets 저장과 읽기
- `requirements.txt`: 필요한 Python 패키지
- `.streamlit/config.toml`: 화면 디자인
- `secrets.example.toml`: 연결 설정 예시 (실제 키 없음)
- `prepare_secrets.py`: 실제 Secrets 설정을 만드는 선택 도구
- `tests/`: 계산, 저장 방식, 화면 테스트

## 1. Google Sheets 준비

1. 본인 Google Drive에서 **새 빈 구글 스프레드시트**를 만듭니다.
2. 이름을 `우리집 금융관리`로 정합니다.
3. 주소에서 스프레드시트 ID를 복사합니다.
   `https://docs.google.com/spreadsheets/d/이_부분이_ID/edit`
4. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 만듭니다.
5. 프로젝트에서 **Google Sheets API**를 활성화합니다.
6. `IAM 및 관리자 → 서비스 계정`에서 서비스 계정을 만듭니다.
7. 서비스 계정의 `키 → 키 추가 → 새 키 만들기 → JSON`으로 키를 받습니다.
8. JSON의 `client_email` 주소를 복사합니다.
9. 구글 시트의 `공유` 버튼에서 그 주소를 **편집자**로 초대합니다.
   시트는 공개하지 않습니다. 시트 저장에는 Drive API나 로그인용 OAuth ID가 필요하지 않습니다. 로그인용 OAuth ID는 별도 단계에서 만듭니다.

서비스 계정은 본인이 공유한 시트에 앱이 접근하도록 연결하는 전용 계정입니다.

## 2. GitHub에 코드 올리기

1. 본인 GitHub에서 새 저장소를 만듭니다. 이번 버전은 Public으로 만듭니다. 실제 키와 금융자료는 저장소에 넣지 않습니다.
2. 압축을 풀고 `app.py`가 저장소 최상위에 오도록 내용을 업로드합니다.
3. `.streamlit/config.toml`도 폴더 구조를 유지해 올립니다.
4. `requirements.txt`, `auth_access.py`, `google_signin.py`, `google_login_component/`, `finance.py`, `sheets_store.py`는 반드시 함께 올립니다.

실제 서비스 계정 JSON, OAuth 비밀키, 금융 백업, `.streamlit/secrets.toml`은 올리지 않습니다.
압축파일에는 예시 값만 있으며 실제 금융내역이나 계정 키가 없습니다.

## 3. Streamlit에서 웹앱 배포

1. [Streamlit Community Cloud](https://share.streamlit.io/)에 GitHub 계정으로 로그인합니다.
2. Create app을 누르고 위 저장소를 선택합니다.
3. Main file path는 `app.py`로 설정합니다.
4. Python은 **3.11 이상**을 사용합니다. 이 코드는 Python 3.12에서 검증했습니다.
5. Advanced settings의 Secrets에 아래 설정을 붙여넣습니다.
6. Deploy를 누릅니다. 이미 배포했다면 앱 설정의 Secrets에서 입력할 수 있습니다.
7. 생성된 `…streamlit.app` 주소로 접속합니다.
8. 허용한 본인 구글 계정으로 로그인합니다.
9. 처음 나타나는 `구글 시트 연결 완료하기` 버튼을 한 번 누릅니다.

구글 시트에 `금융기록` 탭이 준비되면 실제 사용을 시작할 수 있습니다.
허용 이메일 목록에 등록한 가족은 같은 가계부를 봅니다.

## 4. 구글 로그인과 Secrets 설정

구글 로그인 순서는 `GOOGLE_LOGIN_SETUP.md`를 따라하세요.
`secrets.example.toml`의 `[app]`, `[google_login]`, `[gcp_service_account]` 설정을 Streamlit Secrets에 입력합니다.

- `[app].allowed_emails`: 접근을 허용할 본인과 가족의 구글 이메일
- `[app].spreadsheet_id`: 금융자료를 저장할 시트 ID
- `[google_login].client_id`: 구글 로그인 버튼용 웹 OAuth 클라이언트 ID
- `[gcp_service_account]`: 해당 시트에 편집자로 공유한 서비스 계정

로그인은 구글 계정으로 하고, 가계부는 지정한 가족 공용 시트에 저장합니다.
허용되지 않은 계정은 금융자료를 불러오지 않습니다. 각 구글 계정별로 별도 가계부가 생기는 방식은 아닙니다.
개인정보 설정은 Streamlit Secrets에만 입력하며 GitHub에 올리지 않습니다.

수동 변환이 번거로우면 PC에서 `python prepare_secrets.py`를 실행하세요.
받은 서비스 계정 JSON, 시트 ID, 허용 이메일, OAuth 클라이언트 ID를 입력하면
`.streamlit/secrets.toml`을 만듭니다. 해당 파일을 Streamlit Secrets에 복사하세요.

## 사용하는 탭

| 탭 | 사용 방법 |
|---|---|
| 홈 | 이번 달 지출과 미완료 납부, 카드 목표, 통장 필요액 확인 |
| 결제달력 | 날짜별 일정 확인 후 아래에서 완료 체크 |
| 자동이체 | 정기 납부 항목 등록, 수정, 삭제 |
| 카드실적 | 카드별 목표, 현재 실적, 남은 금액 확인 |
| 계좌관리 | 통장과 현재 잔액 관리 |
| 수입지출 | 거래 기록, 검색, 수정, 삭제, CSV 다운로드 |
| 통계 | 분류별 지출과 최근 6개월 비교 |
| 설정 | 전체 JSON 백업과 복원 |

## 계산 규칙

- 카드 사용은 사용일에 지출로 계산합니다.
- 카드대금 출금은 이체로 계산하여 지출에 중복되지 않습니다.
- 납부 완료는 선택한 달에만 적용되고 수입지출 기록이 생깁니다.
- 완료 취소 또는 연결된 거래 삭제 시 납부가 미완료 상태로 돌아갑니다.
- 월말 29~31일 일정은 해당 월의 마지막 날까지만 표시합니다.
- 카드 실적은 달력 월 기준, 실적 포함 지출에서 실적 포함 환불을 뺍니다.
- 환불은 입력한 환불일에 반영합니다. 실제 카드사 실적 처리 기준은 다를 수 있습니다.
- 예상 납부 금액과 실제 금액이 다르면 완료 체크할 때 실제 금액을 입력합니다.
- 통장 잔액은 수동 입력값입니다. 납부 기록으로 자동 차감하지 않습니다.
- 카드대금이 통장에서 나가는 일정은 자동이체에 직접 등록해야 필요 잔액에 포함됩니다.

## 자료 저장

구글 시트 `금융기록` 탭에는 변경 이력이 행별로 남습니다.
앱은 이 기록을 읽어서 현재 계좌, 카드, 자동이체, 사용내역을 구성합니다.
삭제도 삭제 이력으로 남으며 원본 행을 직접 지우지 않습니다.
`금융기록` 탭의 행을 정렬하거나 수정, 삭제하지 마세요. 앱에서 관리하세요.

다른 기기의 변경은 `자료 새로고침`을 누르면 보입니다.
같은 기록을 동시에 수정하면 먼저 저장된 기록을 유지하고 후속 수정은 충돌로 안내합니다.
저장 응답이 끊기면 동일 기록의 저장 여부를 확인합니다. 같은 ID의 중복 요청은 한 번만 반영합니다.
정기적으로 설정에서 JSON 백업을 내려받으세요.

기존 PC 버전의 JSON 백업도 복원할 수 있습니다. 실제 사용내역과 카드실적 포함 여부를 확인하세요.
예시 화면의 자료는 세션에서만 변경되고 구글에는 저장되지 않습니다.

## PC에서 미리 실행 (선택)

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Secrets 없이 시작하면 예시 둘러보기 화면이 열립니다.
실제 자료 연결은 `.streamlit/secrets.toml` 설정이 필요합니다.

## 오류 확인

- **구글 권한 오류**: Sheets API 활성화와 서비스 계정 이메일의 편집자 공유 확인
- **구글 시트 ID 오류**: 전체 URL이 아니라 `/d/` 뒤 ID만 입력
- **private_key 오류**: 원본 JSON의 줄바꿈과 키 항목을 확인
- **동시 수정 충돌**: 현재 자료 JSON 백업 → 자료 새로고침 → 다시 수정
- **저장 결과 불명**: 저장 여부 확인 버튼 사용. 확인되지 않으면 동일 기록 저장 재시도
- **기록 형식 오류**: 원본 시트를 백업하고 손상된 행을 확인. 빈 자료로 자동 덮어쓰지 않음

## 검증과 공식 참고

계산, 월말 처리, 납부 중복 방지, 환불, 동시 수정 충돌, 로그 재시도,
구글 계정 접근 차단과 예시 화면 입력을 테스트합니다. 실제 구글 연결과 운영 배포는 본인 계정 설정 후 확인해야 합니다.

- [Streamlit 배포](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [Streamlit Secrets](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [개인 Google Sheet 연결](https://docs.streamlit.io/develop/tutorials/databases/private-gsheet)
- [Google Sheets append](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append)

- [구글 로그인 검증 공식 안내](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)

## Public 배포와 로그인

이 버전은 Streamlit 내장 로그인과 `[auth]`를 사용하지 않습니다.
기존 Secrets의 `[auth]` 및 하위 섹션을 삭제하고 `[google_login]`을 설정하세요.
구글 로그인 버튼에서 받은 ID 토큰을 서버가 서명, 발급자, 대상 앱, 만료 시각, 세션 nonce와 허용 이메일 기준으로 검증합니다.
로그인 정보는 서버 세션에만 유지합니다. 페이지를 새로고침하거나 새 기기로 접속하면 다시 로그인할 수 있습니다.
실제 Google 팝업과 Public 배포 경로는 본인 앱 주소 설정 후 확인해야 합니다.
