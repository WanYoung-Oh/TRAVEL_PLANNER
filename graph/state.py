from typing import TypedDict
from models.schema import Place, TravelPlan


class TravelState(TypedDict, total=False):
    # 입력
    raw_user_input: str
    destination: str      # 예: "부산"
    duration: str         # 예: "2박 3일"

    # 중간 처리
    search_query: str
    candidates: list[Place]
    plans: list[TravelPlan]

    # 출력
    selected_plan: TravelPlan
    doc_url: str | None

    # 에러
    error: str | None
