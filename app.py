import json
import re
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from graph.workflow import graph
from models.schema import place_map_url
from tools import solar_api

load_dotenv()

st.set_page_config(page_title="Solar-Travel Planner", layout="wide")
st.title("Solar-Travel Planner")
st.caption("여행지와 기간을 말씀해 주세요. AI가 3가지 테마 일정을 제안드립니다.")

_CLASSIFY_SYSTEM = """\
이전 대화 맥락과 현재 메시지를 함께 보고 분류하세요.

- 이전 대화까지 합산해 국내 여행지와 기간이 모두 확인되면
  → {"type": "plan", "destination": "지역명", "duration": "N박 M일"}
- 여행 관련 일반 질문·추천·정보 요청 (지역 또는 기간 중 하나라도 불분명)
  → {"type": "chat"}
- 여행과 무관한 내용
  → {"type": "off_topic"}

핵심 규칙:
- 여행지와 기간이 서로 다른 턴에 걸쳐 나왔어도 합산해 plan으로 분류합니다.
  예) 이전: "여수 가볼까?" / 현재: "2박 3일이면 어때?" → {"type": "plan", "destination": "여수", "duration": "2박 3일"}
- 기간만 있고 여행지가 불분명하면 chat으로 분류합니다.
JSON만 반환하세요. 설명 없이."""

_TRAVEL_CHAT_SYSTEM = """\
당신은 친근한 국내 여행 전문가 챗봇입니다.
여행지 추천, 여행 팁, 음식, 날씨, 교통, 숙소 등 여행 관련 질문에 자연스럽고 유익하게 답하세요.
여행지와 기간이 모두 포함된 일정 요청이 오면,
"여행지와 기간을 함께 말씀해 주시면 맞춤 일정을 만들어 드릴게요!"라고 자연스럽게 안내하세요.
한국어로만 답변하세요."""


def _init():
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "app_phase": "idle",
        "plans": [],
        "destination": "",
        "duration": "",
        "doc_url": None,
        "last_error": None,
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "안녕하세요! 어디로 여행을 가고 싶으세요? "
                    "제가 알찬 여행 계획을 수립해 드리겠습니다! "
                    "(예: 부산 2박 3일)"
                ),
            }
        ],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _reset():
    for key in ["thread_id", "app_phase", "plans", "destination", "duration",
                "doc_url", "last_error", "messages"]:
        st.session_state.pop(key, None)


def _new_plan():
    """대화 히스토리는 유지하고, 일정 관련 상태만 초기화해 idle로 돌아갑니다."""
    for key in ["thread_id", "app_phase", "plans", "destination", "duration", "doc_url", "last_error"]:
        st.session_state.pop(key, None)


def _merge_updates_into(final_state: dict, chunk: dict) -> None:
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


def _classify(user_input: str, messages: list[dict]) -> tuple[str, str]:
    """(type, plan_input) 반환.

    type: 'plan' | 'chat' | 'off_topic'
    plan_input: plan일 때 "destination duration" 합성 문자열, 그 외 user_input 그대로
    """
    # messages[-1]이 현재 user_input이므로 그 이전 메시지를 컨텍스트로 사용
    context_msgs = messages[:-1][-6:]
    if context_msgs:
        context = "\n".join(f"[{m['role']}] {m['content']}" for m in context_msgs)
        prompt = f"[이전 대화]\n{context}\n\n[현재 메시지]\n{user_input}"
    else:
        prompt = user_input

    try:
        raw = solar_api.chat(system=_CLASSIFY_SYSTEM, user=prompt, temperature=0.0)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            msg_type = data.get("type", "chat")
            if msg_type == "plan":
                dest = data.get("destination", "")
                dur = data.get("duration", "")
                plan_input = f"{dest} {dur}".strip() if dest and dur else user_input
                return "plan", plan_input
            return msg_type, user_input
    except Exception:
        pass
    return "chat", user_input


_init()

# ──────────────────────────────────────────────────────────────
# 대화 히스토리 항상 표시
# ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ──────────────────────────────────────────────────────────────
# PHASE: IDLE — 채팅 입력 및 분기
# ──────────────────────────────────────────────────────────────
if st.session_state.app_phase == "idle":
    if user_input := st.chat_input("여행 질문이나 '부산 2박 3일'처럼 말씀해 주세요"):
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        msg_type, plan_input = _classify(user_input, st.session_state.messages)

        if msg_type == "off_topic":
            reply = "저는 국내 여행 관련 질문만 도와드릴 수 있어요. 여행지 추천이나 일정 계획을 물어봐 주세요!"
            with st.chat_message("assistant"):
                st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()

        elif msg_type == "chat":
            with st.chat_message("assistant"):
                response_text = st.write_stream(
                    solar_api.stream_messages(
                        messages=st.session_state.messages,
                        system=_TRAVEL_CHAT_SYSTEM,
                    )
                )
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            st.rerun()

        else:  # "plan"
            with st.chat_message("assistant"):
                status = st.empty()
                final_state: dict = {}

                for chunk in graph.stream(
                    {"raw_user_input": plan_input},
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
                    reply = f"죄송해요, 오류가 발생했어요: {final_state['error']}"
                    st.warning(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                elif final_state.get("plans"):
                    dest = final_state.get("destination", "")
                    dur = final_state.get("duration", "")
                    reply = f"**{dest} {dur}** 일정 3가지를 준비했어요! 아래에서 마음에 드는 일정을 선택해 주세요."
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    st.session_state.plans = final_state["plans"]
                    st.session_state.destination = dest
                    st.session_state.duration = dur
                    st.session_state.last_error = None
                    st.session_state.app_phase = "selecting"
                    st.rerun()
                else:
                    reply = "일정 생성에 실패했습니다. 다시 시도해 주세요."
                    st.error(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

# ──────────────────────────────────────────────────────────────
# PHASE: SELECTING — 3가지 테마 일정 선택
# ──────────────────────────────────────────────────────────────
elif st.session_state.app_phase == "selecting":
    plans = st.session_state.plans
    dest = st.session_state.destination
    dur = st.session_state.duration

    header_col, btn_col = st.columns([5, 1])
    with header_col:
        st.subheader(f"🗺️ {dest} {dur} — 추천 일정 3선")
        st.caption("마음에 드는 일정을 선택하면 Google Docs로 저장됩니다.")
    with btn_col:
        st.write("")  # 버튼 수직 정렬용 여백
        if st.button("새로운 여행 계획", use_container_width=True):
            _new_plan()
            st.rerun()

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
