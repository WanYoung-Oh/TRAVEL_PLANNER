import os
import time

import requests
from models.schema import Place

# 동일 쿼리 반복 호출을 막는 인메모리 캐시 (TTL 1시간)
_cache: dict[str, tuple[list, float]] = {}
_CACHE_TTL = 3600

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"

# 주요 지역 코드 (TourAPI 4.0 기준)
AREA_CODES = {
    "서울": "1", "인천": "2", "대전": "3", "대구": "4", "광주": "5",
    "부산": "6", "울산": "7", "세종": "8", "경기": "31", "강원": "32",
    "충북": "33", "충남": "34", "경북": "35", "경남": "36",
    "전북": "37", "전남": "38", "제주": "39",
}

# 컨텐츠 타입 (TourAPI 4.0 기준)
CONTENT_TYPES = {
    "관광지": "12", "문화시설": "14", "축제행사": "15",
    "음식점": "39", "숙박": "32", "쇼핑": "38",
}


def _get_api_key() -> str:
    key = os.getenv("TOUR_API_KEY")
    if not key:
        raise ValueError("TOUR_API_KEY가 .env에 설정되지 않았습니다.")
    return key


def _get(endpoint: str, extra_params: dict) -> list[dict]:
    """serviceKey를 URL에 직접 삽입해 requests 이중인코딩 방지 (data.go.kr 500 오류 대응)."""
    cache_key = f"{endpoint}|{sorted(extra_params.items())}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[1] < _CACHE_TTL:
        print(f"[TourAPI] 캐시 히트: {endpoint} {extra_params}")
        return cached[0]

    api_key = _get_api_key()
    base = f"{BASE_URL}/{endpoint}?serviceKey={api_key}"
    common = {
        "MobileOS": "ETC",
        "MobileApp": "SolarTravelPlanner",
        "_type": "json",
        "numOfRows": "30",
        **extra_params,
    }
    resp = requests.get(base, params=common, timeout=10)
    if not resp.ok:
        # 실제 에러 원인 출력 (AUTH_XXX 코드 등)
        print(f"[TourAPI] {endpoint} HTTP {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()
    data = resp.json().get("response", {})
    # API 레벨 에러 코드 확인 (resultCode != 0000)
    header = data.get("header", {})
    if header.get("resultCode", "0000") != "0000":
        raise RuntimeError(f"TourAPI 오류: {header.get('resultMsg')} (code={header.get('resultCode')})")
    items = data.get("body", {}).get("items") or {}
    result = items.get("item", [])
    _cache[cache_key] = (result, time.time())
    return result


def get_area_code(destination: str) -> str:
    """도시명을 TourAPI 지역 코드로 변환. 없으면 전국("")."""
    for key, code in AREA_CODES.items():
        if key in destination:
            return code
    return ""


def search_keyword(keyword: str, destination: str = "") -> list[Place]:
    """키워드 기반 관광지 검색. 0건이면 areaCode를 제거해 전국 범위로 재시도."""
    area_code = get_area_code(destination)
    extra: dict = {"keyword": keyword}
    if area_code:
        extra["areaCode"] = area_code

    try:
        items = _get("searchKeyword2", extra)
        places = [_to_place(i) for i in items]

        # 0건이고 지역 코드를 썼다면 전국 범위 재시도
        if not places and area_code:
            items2 = _get("searchKeyword2", {"keyword": keyword})
            places = [_to_place(i) for i in items2]

        return places
    except Exception as e:
        print(f"[TourAPI] searchKeyword2 오류: {e}")
        return []


def area_based_list(destination: str, content_type: str = "관광지") -> list[Place]:
    """지역 기반 관광지 목록 조회."""
    area_code = get_area_code(destination)
    extra: dict = {"contentTypeId": CONTENT_TYPES.get(content_type, "12")}
    if area_code:
        extra["areaCode"] = area_code

    try:
        items = _get("areaBasedList2", extra)
        return [_to_place(i) for i in items]
    except Exception as e:
        print(f"[TourAPI] areaBasedList2 오류: {e}")
        return []


def _to_place(item: dict) -> Place:
    name = item.get("title", "")
    address = (item.get("addr1", "") + " " + item.get("addr2", "")).strip()
    # TourAPI 좌표(mapx=경도, mapy=위도) 기반 카카오맵 링크, 없으면 검색 URL 폴백
    mapx = item.get("mapx", "")
    mapy = item.get("mapy", "")
    if mapx and mapy:
        encoded = requests.utils.quote(name)
        map_url = f"https://map.kakao.com/link/map/{encoded},{mapy},{mapx}"
    else:
        map_url = f"https://map.kakao.com/?q={requests.utils.quote(name)}"
    return Place(
        name=name,
        category=_resolve_category(item.get("contenttypeid", "")),
        address=address,
        map_url=map_url,
        description="",
    )


def _resolve_category(type_id: str) -> str:
    reverse = {v: k for k, v in CONTENT_TYPES.items()}
    return reverse.get(type_id, "기타")
