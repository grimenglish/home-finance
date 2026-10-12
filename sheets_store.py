"""Append-only Google Sheets records. Every write is one atomic row; retries are deduplicated by event ID."""
import json
from urllib.parse import quote
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from finance import replay

TITLE = '금융기록'
HEADER = ['저장일시', '입력자', '작업', '기록 ID', '데이터 조각 수'] + [f'데이터 {i}' for i in range(1, 51)]
class SetupRequired(Exception): pass
class UncertainWrite(Exception): pass

class SheetsStore:
    def __init__(self, spreadsheet_id, service_account):
        if not spreadsheet_id or '/' in spreadsheet_id: raise ValueError('구글 시트 ID를 확인해 주세요.')
        self.base = 'https://sheets.googleapis.com/v4/spreadsheets/' + spreadsheet_id
        credentials = Credentials.from_service_account_info(dict(service_account), scopes=['https://www.googleapis.com/auth/spreadsheets'])
        self.session = AuthorizedSession(credentials)
    def request(self, method, path='', **kwargs):
        r = self.session.request(method, self.base + path, timeout=30, **kwargs)
        if not r.ok:
            if r.status_code == 403: raise RuntimeError('구글 시트 공유 권한 또는 Sheets API 활성화를 확인해 주세요.')
            if r.status_code == 404: raise RuntimeError('구글 시트 ID와 서비스 계정 공유를 확인해 주세요.')
            if r.status_code == 429: raise RuntimeError('요청이 많습니다. 잠시 후 다시 시도하세요.')
            raise RuntimeError(f'구글 저장 요청에 실패했습니다. ({r.status_code})')
        return r.json()
    def exists(self):
        meta = self.request('GET', params={'fields': 'sheets.properties'})
        return next((s['properties'] for s in meta.get('sheets', []) if s['properties']['title'] == TITLE), None)
    def initialize(self):
        properties = self.exists()
        if not properties:
            result = self.request('POST', ':batchUpdate', json={'requests': [{'addSheet': {'properties': {'title': TITLE, 'gridProperties': {'rowCount': 1000, 'columnCount': 55, 'frozenRowCount': 1}}}}]})
            properties = result['replies'][0]['addSheet']['properties']
        # Never overwrite an existing nonempty sheet.
        current = self.request('GET', '/values/' + quote(f"'{TITLE}'!A1:E1", safe='')).get('values', [])
        if current and current[0] != HEADER[:5]: raise RuntimeError('금융기록 탭의 첫 행 형식이 다릅니다. 새 빈 시트를 사용해 주세요.')
        if not current:
            self.request('PUT', '/values/' + quote(f"'{TITLE}'!A1:BC1", safe=''), params={'valueInputOption': 'RAW'}, json={'values': [HEADER]})
        self.request('POST', ':batchUpdate', json={'requests': [{'repeatCell': {'range': {'sheetId': properties['sheetId'], 'startRowIndex': 0, 'endRowIndex': 1}, 'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.07, 'green': 0.25, 'blue': 0.2}, 'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}}}, 'fields': 'userEnteredFormat'}}]})
    def events(self):
        if not self.exists(): raise SetupRequired('최초 연결 준비가 필요합니다.')
        rows = self.request('GET', '/values/' + quote(f"'{TITLE}'!A:BC", safe='')).get('values', [])
        if not rows or rows[0][:5] != HEADER[:5]: raise SetupRequired('최초 연결 준비가 필요합니다.')
        out = []
        for row in rows[1:]:
            if not row: continue
            try:
                size = int(row[4]); e = json.loads(''.join(row[5:5 + size]))
                if not 1 <= size <= 50 or len(row[5:5 + size]) != size or e['id'] != row[3]: raise ValueError()
                out.append(e)
            except (ValueError, KeyError, IndexError, TypeError):
                raise RuntimeError('금융기록 탭에 손상된 행이 있습니다. 원본을 백업한 뒤 복구해 주세요. 자료를 빈 가계부로 덮어쓰지 않습니다.')
        return out
    def load(self): return replay(self.events())
    def append(self, e):
        serialized = json.dumps(e, ensure_ascii=False, separators=(',', ':'))
        chunks = [serialized[i:i + 40000] for i in range(0, len(serialized), 40000)]
        if len(chunks) > 50: raise ValueError('한 번에 저장할 자료가 너무 큽니다. 200만 자 이하로 나누어 주세요.')
        row = [e['time'], e.get('actor', '우리집'), e['label'], e['id'], len(chunks), *chunks]
        try:
            self.request('POST', '/values/' + quote(f"'{TITLE}'!A:BC", safe='') + ':append', params={'valueInputOption': 'RAW', 'insertDataOption': 'INSERT_ROWS'}, json={'majorDimension': 'ROWS', 'values': [row]})
        except Exception as exc:
            raise UncertainWrite('저장 결과를 확인하지 못했습니다. 아래 확인 버튼으로 동일 기록을 확인해 주세요.') from exc
        return self.confirm(e)
    def confirm(self, e):
        events = self.events()
        if not any(x['id'] == e['id'] for x in events): return None
        data, rejected = replay(events)
        if e['id'] in rejected: raise ValueError('같은 항목이 다른 창에서 바뀌었습니다. 새 자료를 불러온 뒤 다시 수정하세요.')
        return data
