import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.types import interrupt

from graph.state import TravelState
from models.schema import Place, TravelPlan
from tools import google_docs, solar_api, tour_api

_ANALYZE_SYSTEM = """\
당신은 여행 계획 도우미입니다. 사용자의 메시지에서 다음 두 가지를 추출하세요:
1. destination: 여행지 (도시명 또는 지역명, 예: "부산", "제주", "강원도")
2. duration: 기간 (예: "2박 3일", "1박 2일", "당일치기")

반드시 아래 JSON 형식만 반환하세요 (설명 없이):
{"destination": "...", "duration": "...", "search_query": "...여행 추천 명소 맛집"}

규칙:
- 여행지나 기간 중 하나라도 불분명하면 destination, duration을 null로 두고
  error 필드에 한국어 재질문 메시지를 담으세요.
  예: {"destination": null, "duration": null, "error": "여행지와 기간을 함께 알려주세요. 예: 부산 2박 3일"}
- search_query는 "부산 여행 추천 명소 맛집" 형태로 destination 기반 생성.
- 국내 여행지만 허용. 해외 지명이면 error 필드에 "국내 여행지만 입력 가능합니다." 반환.\
"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"JSON을 찾을 수 없습니다: {text!r}")
    return json.loads(match.group())


def node_analyze(state: TravelState) -> dict:
    raw = state.get("raw_user_input", "")
    try:
        response_text = solar_api.chat(
            system=_ANALYZE_SYSTEM,
            user=raw,
            temperature=0.0,
        )
        parsed = _extract_json(response_text)
    except Exception as exc:
        return {"error": f"입력 분석 중 오류가 발생했습니다: {exc}"}

    if parsed.get("error"):
        return {"error": parsed["error"]}

    destination = parsed.get("destination")
    duration = parsed.get("duration")

    if not destination or not duration:
        return {
            "error": parsed.get(
                "error",
                "여행지와 기간을 함께 알려주세요. 예: 제주도 3박 4일",
            )
        }

    search_query = parsed.get("search_query") or f"{destination} 여행 추천 명소 맛집"

    return {
        "destination": destination,
        "duration": duration,
        "search_query": search_query,
        "error": None,
    }


def node_search(state: TravelState) -> dict:
    t0 = time.perf_counter()
    destination = state.get("destination", "")
    search_query = state.get("search_query") or f"{destination} 여행 명소 맛집"

    try:
        # 키워드 검색 + 음식점 목록 병렬 호출
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_keyword = executor.submit(tour_api.search_keyword, search_query, destination)
            f_restaurants = executor.submit(tour_api.area_based_list, destination, "음식점")
            candidates = f_keyword.result()
            restaurants = f_restaurants.result()

        # 키워드 검색 0건이면 전국 범위 재시도 (순차 — 첫 결과 확인 후)
        if not candidates:
            candidates = tour_api.search_keyword(f"{destination} 명소", "")

        seen = {p.name for p in candidates}
        for place in restaurants:
            if place.name not in seen:
                candidates.append(place)
                seen.add(place.name)

        if not candidates:
            return {
                "error": (
                    f"'{destination}'에서 관광지를 찾지 못했습니다. "
                    "다른 지역명으로 다시 시도해 주세요."
                )
            }

        print(f"[timer] node_search: {time.perf_counter() - t0:.2f}s ({len(candidates[:20])}곳)")
        return {"candidates": candidates[:20], "error": None}

    except Exception as exc:
        return {"error": f"장소 검색 중 오류가 발생했습니다: {exc}"}


_PLAN_SYSTEM = """\
당신은 국내 여행 일정 설계 전문가입니다.
주어진 장소 후보 목록을 활용해 지정된 테마의 여행 일정을 JSON으로 작성하세요.

[테마 특성]
- 시그니처: 해당 지역 대표 명소와 유명 맛집 중심
- 감성/트렌드: SNS 인기 카페·포토존·핫플레이스 중심
- 힐링/여유: 자연·공원·한적한 장소·여백 있는 일정 중심

[출력 형식 — 아래 JSON만 반환, 설명 없이]
{
  "theme": "...",
  "summary": "테마 한 줄 소개",
  "days": [
    {
      "day": 1,
      "slots": [
        {"time": "오전", "place": {"name": "...", "map_search_query": null, "category": "...", "address": "...", "map_url": null, "description": "..."}},
        {"time": "오후", "place": {"name": "...", "map_search_query": null, "category": "...", "address": "...", "map_url": null, "description": "..."}},
        {"time": "저녁", "place": {"name": "보성 차밭 야경", "map_search_query": "보성 녹차밭", "category": "명소", "address": "...", "map_url": null, "description": "야경 감상 (수식어는 description에)"}}
      ]
    }
  ],
  "estimated_cost": "1인 기준 약 N만원"
}

[규칙]
- 후보 목록에 없는 실존 장소도 추가 가능
- 하루 슬롯은 오전/오후/저녁 3개 권장 (최소 2개)
- 각 날 일정에 맛집 또는 카페를 반드시 1곳 이상 포함할 것 (FR-PLAN-02)
- place.name: 카드에 보여줄 표기(테마·시간대 표현 가능, 예: "보성 차밭 야경")
- place.map_search_query: 카카오맵 검색용 공식·짧은 지명만(예: "보성 녹차밭", "대한다원"). 야경·산책·코스·전망·추천 등 수식어는 넣지 말 것. name이 이미 검색에 충분하면 null
- place.description: 분위기·야경·팁 등 자유 서술
- map_url은 비워 두어도 됨(앱이 map_search_query·name으로 링크 생성). TourAPI 좌표 URL 수준으로 확실할 때만 사용
- estimated_cost는 식비+교통비 기준 간략 추정치\
"""

_THEMES = ["시그니처", "감성/트렌드", "힐링/여유"]


def _format_candidates(candidates: list[Place]) -> str:
    return "\n".join(
        f"- {p.name} ({p.category}) / {p.address}" for p in candidates
    )


def _build_plan(theme: str, candidates: list[Place], destination: str, duration: str) -> TravelPlan:
    user_msg = (
        f"여행지: {destination}\n"
        f"기간: {duration}\n"
        f"테마: {theme}\n\n"
        f"[장소 후보]\n{_format_candidates(candidates)}"
    )
    response_text = solar_api.chat(
        system=_PLAN_SYSTEM,
        user=user_msg,
        temperature=0.7,
    )
    data = _extract_json(response_text)
    return TravelPlan.model_validate(data)


def node_plan(state: TravelState) -> dict:
    t0 = time.perf_counter()
    candidates: list[Place] = list(state.get("candidates", []))
    duration = state.get("duration", "")
    destination = state.get("destination", "")

    try:
        # 3테마 ThreadPoolExecutor로 병렬 호출 (PRD §5.2 Node_Plan Parallel)
        with ThreadPoolExecutor(max_workers=len(_THEMES)) as executor:
            future_to_idx = {
                executor.submit(_build_plan, theme, candidates, destination, duration): i
                for i, theme in enumerate(_THEMES)
            }
            results: dict[int, TravelPlan] = {}
            for future in as_completed(future_to_idx):
                results[future_to_idx[future]] = future.result()

        plans = [results[i] for i in sorted(results)]
        print(f"[timer] node_plan: {time.perf_counter() - t0:.2f}s (3테마 병렬)")
        return {"plans": plans, "error": None}
    except Exception as exc:
        return {"error": f"일정 생성 중 오류가 발생했습니다: {exc}"}


def node_wait(state: TravelState) -> dict:
    plans: list[TravelPlan] = state.get("plans", [])

    # 그래프를 일시 정지하고 UI에 선택 요청 신호를 보냄.
    # Streamlit에서 Command(resume=index)로 재개하면 interrupt()가 index를 반환.
    # 주의: 이 노드가 동작하려면 graph를 checkpointer와 함께 compile해야 함.
    selected_index = interrupt({"action": "select_plan", "count": len(plans)})

    try:
        idx = int(selected_index)
    except (ValueError, TypeError):
        return {
            "error": (
                f"선택값이 숫자가 아닙니다. "
                f"0~{len(plans) - 1} 중 하나를 입력해 주세요. (받은 값: {selected_index!r})"
            )
        }

    if not (0 <= idx < len(plans)):
        return {
            "error": (
                f"선택 범위를 벗어났습니다. "
                f"0~{len(plans) - 1} 중 하나를 선택해 주세요. (받은 값: {idx})"
            )
        }

    return {"selected_plan": plans[idx], "error": None}


def node_export(state: TravelState) -> dict:
    selected_plan: TravelPlan | None = state.get("selected_plan")
    destination = state.get("destination", "")
    duration = state.get("duration", "")

    if not selected_plan:
        return {"doc_url": None, "error": "선택된 일정이 없습니다."}

    try:
        doc_url = google_docs.create_travel_doc(selected_plan, destination, duration)
        return {"doc_url": doc_url, "error": None}
    except (FileNotFoundError, ValueError) as exc:
        return {"doc_url": None, "error": str(exc)}
    except RuntimeError as exc:
        # google_docs에서 API 미사용 등 사용자 안내 문장
        return {"doc_url": None, "error": str(exc)}
    except Exception as exc:
        return {
            "doc_url": None,
            "error": f"Google Docs 생성 중 오류가 발생했습니다: {exc}",
        }
