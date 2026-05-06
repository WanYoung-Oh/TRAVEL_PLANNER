from urllib.parse import quote

from pydantic import BaseModel


class Place(BaseModel):
    name: str
    category: str  # "명소" | "맛집" | "카페" 등
    address: str
    map_url: str | None = None  # TourAPI 좌표 링크 등; 일반적으로 비움
    # 카카오맵 ?q= 에만 사용. name에 "야경·코스" 등이 붙은 경우 공식 지명(예: 보성 녹차밭)을 넣음
    map_search_query: str | None = None
    description: str = ""


class TimeSlot(BaseModel):
    time: str  # "오전" | "오후" | "저녁"
    place: Place


class DayPlan(BaseModel):
    day: int  # 1, 2, 3...
    slots: list[TimeSlot]


class TravelPlan(BaseModel):
    theme: str  # "시그니처" | "감성/트렌드" | "힐링/여유"
    summary: str  # 테마 한 줄 소개
    days: list[DayPlan]
    estimated_cost: str | None = None


def place_map_url(place: Place) -> str:
    """카카오맵 검색 URL. 좌표 링크는 유지, 그 외는 검색어 우선순위로 q= 생성.

    우선순위: map_search_query → name → address
    (표시용 name에 '야경' 등 수식어가 있어도 검색은 map_search_query로 맞출 수 있음)
    """
    raw = (place.map_url or "").strip()
    if raw.startswith("https://map.kakao.com/link/map/"):
        return raw

    query = (
        (place.map_search_query or "").strip()
        or (place.name or "").strip()
        or (place.address or "").strip()
    )
    if not query:
        return "https://map.kakao.com/"
    return f"https://map.kakao.com/?q={quote(query, safe='')}"
