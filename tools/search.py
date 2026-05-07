"""Tavily 기반 웹 검색 및 장소 링크 보강.

TAVILY_API_KEY 미설정·tavily-python 미설치 시 조용히 폴백합니다.
"""
import os

from models.schema import Place


def _client():
    """TavilyClient 반환. 키 없거나 패키지 없으면 None."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from tavily import TavilyClient  # noqa: PLC0415
        return TavilyClient(api_key=api_key)
    except ImportError:
        print("[search] tavily-python 미설치. `pip install tavily-python` 후 사용 가능합니다.")
        return None


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Tavily 웹 검색. [{url, title, content}, ...] 반환. 불가하면 []."""
    client = _client()
    if client is None:
        return []
    try:
        raw = client.search(query=query, max_results=max_results, search_depth="basic")
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "content": r.get("content", ""),
            }
            for r in raw.get("results", [])
        ]
    except Exception as exc:
        print(f"[search] Tavily 오류: {exc}")
        return []


_KAKAO_COORD = "map.kakao.com/link/map/"

# 지도 서비스 직접 URL 우선순위 도메인
_MAP_DOMAINS = (
    _KAKAO_COORD,           # 카카오맵 좌표 직링크 (최우선)
    "place.map.kakao.com",  # 카카오맵 장소 페이지
    "map.naver.com/p/entry", # 네이버맵 장소 페이지
    "naver.me/",            # 네이버 단축 URL
)


def _pick_map_url(results: list[dict]) -> str | None:
    """검색 결과에서 지도 서비스 직접 링크(좌표·place 기반) 우선 추출."""
    for r in results:
        url = r.get("url", "")
        if any(d in url for d in _MAP_DOMAINS):
            return url
    return None


def enrich_places(places: list[Place]) -> list[Place]:
    """map_url이 없거나 /?q= 검색 쿼리인 Place에 Tavily로 직접 링크를 보강합니다.

    동작 규칙:
    - 좌표 기반 카카오맵 URL(link/map/ 포함)이 이미 있으면 그대로 유지합니다.
    - TAVILY_API_KEY 미설정이면 원본 목록을 그대로 반환합니다.
    - Tavily 검색이 실패하거나 지도 URL을 찾지 못하면 해당 Place만 원본 유지합니다.

    호출 예시 (node_plan 이후):
        enriched_plans = [
            plan.model_copy(update={"days": [
                day.model_copy(update={"slots": [
                    slot.model_copy(update={"place": enrich_place(slot.place)})
                    for slot in day.slots
                ]})
                for day in plan.days
            ]})
            for plan in plans
        ]
    """
    client = _client()
    if client is None:
        return places

    enriched = []
    for place in places:
        if place.map_url and _KAKAO_COORD in place.map_url:
            # 이미 정확한 좌표 링크 — 건드리지 않음
            enriched.append(place)
            continue

        hits = search_web(f"{place.name} 카카오맵 OR 네이버지도", max_results=3)
        better_url = _pick_map_url(hits)
        enriched.append(
            place.model_copy(update={"map_url": better_url}) if better_url else place
        )
    return enriched
