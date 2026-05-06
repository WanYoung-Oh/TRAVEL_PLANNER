import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models.schema import TravelPlan, place_map_url

_SCOPES = ["https://www.googleapis.com/auth/documents"]
_CREDENTIALS_FILE = Path("credentials.json")
_TOKEN_FILE = Path("token.json")


def _oauth_client_config() -> dict:
    """Desktop(install) OAuth 클라이언트 설정. credentials.json 우선, 없으면 .env."""
    load_dotenv()

    if _CREDENTIALS_FILE.exists():
        raw = json.loads(_CREDENTIALS_FILE.read_text(encoding="utf-8"))
        if "installed" in raw:
            return raw
        if "web" in raw:
            raise ValueError(
                "credentials.json이 '웹 애플리케이션'용입니다. "
                "Google Cloud Console에서 '데스크톱 앱' OAuth 클라이언트를 만들고 "
                "해당 JSON을 다시 받아 프로젝트 루트에 두세요."
            )
        raise ValueError(
            "credentials.json 형식을 알 수 없습니다. 'installed' 블록이 있는 "
            "데스크톱 클라이언트 JSON인지 확인하세요."
        )

    cid = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    if cid and secret:
        return {
            "installed": {
                "client_id": cid,
                "client_secret": secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

    raise FileNotFoundError(
        "Google OAuth 설정이 없습니다. 아래 중 하나를 준비하세요.\n\n"
        f"• 방법 A: Cloud Console에서 '데스크톱 앱' 클라이언트 JSON을 다운로드해 "
        f"프로젝트 루트에 {_CREDENTIALS_FILE.name} 으로 저장\n"
        "• 방법 B: .env 에 GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET "
        "(데스크톱 클라이언트와 동일한 값)\n\n"
        "Google Docs API 사용 설정, OAuth 동의 화면, "
        "(테스트 모드면) 테스트 사용자에 본인 Gmail 추가가 필요합니다. "
        "README의 'Google OAuth 설정'을 참고하세요."
    )

# 표 컬럼 인덱스
_COL_DATE = 0
_COL_TIME = 1
_COL_PLACE = 2
_COL_CATEGORY = 3
_COL_ADDRESS = 4
_N_COLS = 5


def _friendly_docs_api_error(exc: HttpError) -> str | None:
    """403 SERVICE_DISABLED 등 — 사용자에게 켤 API 안내. 해당 없으면 None."""
    if exc.resp.status != 403:
        return None
    try:
        blob = json.loads(exc.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError):
        return None
    details = blob.get("error", {}).get("details") or []
    activation_url: str | None = None
    for d in details:
        if d.get("reason") == "SERVICE_DISABLED":
            meta = d.get("metadata") or {}
            activation_url = meta.get("activationUrl")
            break
    if not activation_url and "docs.googleapis.com" in (
        blob.get("error", {}).get("message") or ""
    ):
        activation_url = "https://console.cloud.google.com/apis/library/docs.googleapis.com"
    if activation_url:
        return (
            "Google Docs API가 이 Google Cloud 프로젝트에서 아직 켜지지 않았습니다.\n\n"
            "1) 아래 링크를 열고 「사용」(Enable)을 누르세요.\n"
            f"{activation_url}\n\n"
            "2) 방금 켰다면 반영까지 1~2분 걸릴 수 있습니다. 잠시 후 다시 시도하세요.\n\n"
            "README의 Cloud Console 절차 2번(Google Docs API 사용 설정)과 같습니다."
        )
    return None


def _get_service():
    """OAuth 2.0 인증으로 Google Docs 서비스 객체를 반환."""
    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_cfg = _oauth_client_config()
            flow = InstalledAppFlow.from_client_config(client_cfg, _SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_FILE.write_text(creds.to_json())

    return build("docs", "v1", credentials=creds)


def _build_table_data(plan: TravelPlan) -> tuple[list[list[str]], dict[tuple[int, int], str]]:
    """TravelPlan → (rows, place_urls). rows[0]은 헤더. place_urls: (row, col) → map_url."""
    header = ["날짜", "시간대", "장소", "카테고리", "주소"]
    data_rows: list[list[str]] = []
    place_urls: dict[tuple[int, int], str] = {}

    for day_plan in plan.days:
        for slot in day_plan.slots:
            p = slot.place
            r = len(data_rows) + 1  # +1 for header row
            url = place_map_url(p)
            place_urls[(r, _COL_PLACE)] = url
            data_rows.append([
                f"Day {day_plan.day}",
                slot.time,
                p.name,
                p.category,
                p.address,
            ])

    return [header] + data_rows, place_urls


def _get_cell_starts(doc: dict) -> list[list[int]]:
    """[row][col] → 해당 셀 첫 번째 단락의 startIndex."""
    result: list[list[int]] = []
    for el in doc.get("body", {}).get("content", []):
        if "table" not in el:
            continue
        for row in el["table"].get("tableRows", []):
            starts = []
            for cell in row.get("tableCells", []):
                content = cell.get("content", [])
                starts.append(content[0]["startIndex"] if content else 0)
            result.append(starts)
    return result


def _get_cell_ranges(doc: dict) -> list[list[tuple[int, int]]]:
    """[row][col] → (text_startIndex, text_endIndex) — 단락 끝 \\n 제외."""
    result: list[list[tuple[int, int]]] = []
    for el in doc.get("body", {}).get("content", []):
        if "table" not in el:
            continue
        for row in el["table"].get("tableRows", []):
            ranges = []
            for cell in row.get("tableCells", []):
                content = cell.get("content", [])
                if content:
                    para = content[0]
                    s, e = para["startIndex"], para["endIndex"] - 1
                    ranges.append((s, e))
                else:
                    ranges.append((0, 0))
            result.append(ranges)
    return result


def create_travel_doc(
    plan: TravelPlan,
    destination: str = "",
    duration: str = "",
) -> str:
    """선택된 여행 일정을 Google Docs 표(table) 형태로 생성하고 편집 URL을 반환.

    표 구조: 날짜 | 시간대 | 장소(클릭 가능 링크) | 카테고리 | 주소
    헤더 행 굵게(bold), 장소 열 하이퍼링크 적용 (FR-EXPORT-01/02).
    """
    service = _get_service()

    try:
        # ── 1. 문서 생성 ──────────────────────────────────────
        title = f"[Solar Planner] {destination} {duration} — {plan.theme}"
        doc = service.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        # ── 2. 표 데이터 준비 ─────────────────────────────────
        all_rows, place_urls = _build_table_data(plan)
        n_rows = len(all_rows)

        # ── 3. 빈 표 삽입 ────────────────────────────────────
        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [
                {"insertTable": {
                    "rows": n_rows,
                    "columns": _N_COLS,
                    "location": {"index": 1},
                }}
            ]},
        ).execute()

        # ── 4. 셀 인덱스 읽기 → 역순 채우기 ──────────────────
        doc1 = service.documents().get(documentId=doc_id).execute()
        cell_starts = _get_cell_starts(doc1)

        fill_requests = []
        for r in reversed(range(min(n_rows, len(cell_starts)))):
            for c in reversed(range(min(_N_COLS, len(cell_starts[r])))):
                text = all_rows[r][c] if r < len(all_rows) and c < len(all_rows[r]) else ""
                if text:
                    fill_requests.append({
                        "insertText": {
                            "location": {"index": cell_starts[r][c]},
                            "text": text,
                        }
                    })

        if fill_requests:
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": fill_requests},
            ).execute()

        # ── 5. 스타일 적용: 헤더 bold + 장소 열 hyperlink ─────
        doc2 = service.documents().get(documentId=doc_id).execute()
        cell_ranges = _get_cell_ranges(doc2)

        style_requests = []
        for r, row_ranges in enumerate(cell_ranges):
            for c, (s, e) in enumerate(row_ranges):
                if s >= e:
                    continue

                if r == 0:
                    # 헤더 행: bold
                    style_requests.append({
                        "updateTextStyle": {
                            "range": {"startIndex": s, "endIndex": e},
                            "textStyle": {"bold": True},
                            "fields": "bold",
                        }
                    })
                elif c == _COL_PLACE and (r, c) in place_urls:
                    # 장소 열: 클릭 가능 hyperlink (FR-EXPORT-02)
                    style_requests.append({
                        "updateTextStyle": {
                            "range": {"startIndex": s, "endIndex": e},
                            "textStyle": {
                                "link": {"url": place_urls[(r, c)]},
                                "foregroundColor": {
                                    "color": {"rgbColor": {"red": 0.1, "green": 0.3, "blue": 0.8}}
                                },
                                "underline": True,
                            },
                            "fields": "link,foregroundColor,underline",
                        }
                    })

        if style_requests:
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": style_requests},
            ).execute()

        return f"https://docs.google.com/document/d/{doc_id}/edit"
    except HttpError as exc:
        hint = _friendly_docs_api_error(exc)
        if hint:
            raise RuntimeError(hint) from exc
        raise
