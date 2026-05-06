import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from graph.workflow import graph
from models.schema import place_map_url

load_dotenv()

st.set_page_config(page_title="Solar-Travel Planner", layout="wide")              # page_icon="✈️" 제거
st.title("Solar-Travel Planner")
st.caption("여행지와 기간을 말씀해 주세요. AI가 3가지 테마 일정을 제안드립니다.")


def _init():
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "app_phase": "idle",   # idle | selecting | done
        "plans": [],
        "destination": "",
        "duration": "",
        "doc_url": None,
        "last_error": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _reset():
    for key in ["thread_id", "app_phase", "plans", "destination", "duration", "doc_url", "last_error"]:
        st.session_state.pop(key, None)


def _merge_updates_into(final_state: dict, chunk: dict) -> None:
    """stream_mode='updates' 청크를 final_state에 합친다. __interrupt__ 등 비-dict 페이로드는 건너튼다."""
    skip = frozenset({"__interrupt__", "__metadata__"})
    for node_name, node_state in chunk.items():
        if node_name in skip or node_state is None:
            continue
        if isinstance(node_state, dict):
            final_state.update(node_state)
        elif isinstance(node_state, list):
            for part in node_state:
                if isinstance(part, dict):
                    final_state.update(part)


_init()

# ──────────────────────────────────────────────────────────────
# PHASE: IDLE — 여행지·기간 입력
# ──────────────────────────────────────────────────────────────
if st.session_state.app_phase == "idle":
    if st.session_state.last_error:
        st.warning(st.session_state.last_error)

    with st.chat_message("assistant"):
        st.write("안녕하세요! 어디로, 몇 박 며칠 여행을 계획하고 계신가요?\n예) '부산 2박 3일'")

    if user_input := st.chat_input("예: 부산 2박 3일"):
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            status = st.empty()
            final_state: dict = {}

            # graph.stream으로 노드별 진행 상황 실시간 표시 (FR-CHAT-02)
            for chunk in graph.stream(
                {"raw_user_input": user_input},
                _config(),
                stream_mode="updates",
            ):
                _merge_updates_into(final_state, chunk)

                for node_name, node_state in chunk.items():
                    if node_name in ("__interrupt__", "__metadata__"):
                        continue
                    if not isinstance(node_state, dict):
                        continue

                    if node_name == "analyze":
                        if node_state.get("error"):
                            status.warning(node_state["error"])
                        else:
                            dest = node_state.get("destination", "")
                            dur = node_state.get("duration", "")
                            status.write(f"✅ **{dest} {dur}** 확인 — 장소 검색 중...")
                    elif node_name == "search":
                        n = len(node_state.get("candidates", []))
                        status.write(f"✅ 관광지·맛집 **{n}곳** 검색 완료 — 일정 생성 중...")
                    elif node_name == "plan":
                        status.write("✅ 3가지 테마 일정 생성 완료!")

            status.empty()

            if final_state.get("error"):
                st.warning(final_state["error"])
                st.session_state.last_error = final_state["error"]
            elif final_state.get("plans"):
                st.session_state.plans = final_state["plans"]
                st.session_state.destination = final_state.get("destination", "")
                st.session_state.duration = final_state.get("duration", "")
                st.session_state.last_error = None
                st.session_state.app_phase = "selecting"
                st.rerun()
            else:
                st.error("일정 생성에 실패했습니다. 다시 시도해 주세요.")

# ──────────────────────────────────────────────────────────────
# PHASE: SELECTING — 3가지 테마 일정 선택
# ──────────────────────────────────────────────────────────────
elif st.session_state.app_phase == "selecting":
    plans = st.session_state.plans
    dest = st.session_state.destination
    dur = st.session_state.duration

    st.subheader(f"🗺️ {dest} {dur} — 추천 일정 3선")
    st.caption("마음에 드는 일정을 선택하면 Google Docs로 저장됩니다.")

    cols = st.columns(3)
    for i, (col, plan) in enumerate(zip(cols, plans)):
        with col:
            with st.container(border=True):
                st.markdown(f"### {plan.theme}")
                st.caption(plan.summary)
                if plan.estimated_cost:
                    st.info(f"💰 {plan.estimated_cost}")

                for day_plan in plan.days:
                    st.markdown(f"**Day {day_plan.day}**")
                    for slot in day_plan.slots:
                        p = slot.place
                        map_url = place_map_url(p)
                        st.markdown(
                            f"- **{slot.time}**: [{p.name}]({map_url})  \n"
                            f"  *{p.description}*"
                        )
                    st.write("")

                if st.button("이 일정 선택", key=f"select_{i}", use_container_width=True, type="primary"):
                    with st.spinner("Google Docs를 생성하는 중..."):
                        result = graph.invoke(Command(resume=i), _config())
                    st.session_state.doc_url = result.get("doc_url")
                    st.session_state.last_error = result.get("error")
                    st.session_state.app_phase = "done"
                    st.rerun()

# ──────────────────────────────────────────────────────────────
# PHASE: DONE — 완료
# ──────────────────────────────────────────────────────────────
elif st.session_state.app_phase == "done":
    dest = st.session_state.destination
    dur = st.session_state.duration

    st.success(f"{dest} {dur} 여행 일정이 완성되었습니다!")

    if st.session_state.doc_url:
        st.link_button(
            "📄 Google Docs에서 일정 보기",
            st.session_state.doc_url,
            type="primary",
        )
    else:
        err = st.session_state.last_error or "알 수 없는 오류"
        st.warning(f"Google Docs 생성 실패: {err}")
        st.info("README의 **Google OAuth 설정**을 참고해 credentials.json 또는 .env(GOOGLE_*)를 준비한 뒤 다시 시도해 주세요.")

    st.divider()
    if st.button("새 여행 계획 시작하기"):
        _reset()
        st.rerun()
