# Solar-Travel Planner — Claude 작업 지침

## 프로젝트 개요

Upstage Solar Pro API + LangGraph 기반 국내 여행 일정 생성 서비스.  
핵심 문서: `docs/PRD.md`, `docs/MVP-Concept.md`

## 커스텀 커맨드 처리 규칙 (중요)

아래 커맨드는 **Skill 도구를 사용하지 말고**, `.claude/commands/<name>.md` 파일을 직접 읽어 실행한다.

| 커맨드 | 파일 | 역할 |
|--------|------|------|
| `/tp-setup [--phase N]` | `.claude/commands/tp-setup.md` | 프로젝트 초기 구조 생성 |
| `/tp-node <name> [--test]` | `.claude/commands/tp-node.md` | LangGraph 노드 구현 |
| `/tp-phase [N]` | `.claude/commands/tp-phase.md` | Phase 진행 상황 확인 |

**처리 방법:**
1. 해당 `.md` 파일을 Read로 읽는다.
2. 파일 내 지침(## 실행 지침)을 따라 직접 실행한다.
3. `Skill("tp-*")` 호출은 절대 하지 않는다.

## 기술 스택 요약

- **LLM:** Upstage Solar Pro API (`https://api.upstage.ai/v1`, OpenAI 호환)
- **오케스트레이션:** LangGraph
- **프론트엔드:** Streamlit
- **관광 데이터:** TourAPI 4.0
- **문서 내보내기:** Google Docs API + OAuth 2.0
- **환경:** Python 3.11+, MacBook M4 16GB (로컬 대형 AI 모델 금지)

## 개발 환경

```bash
pip install -r requirements.txt
cp .env.example .env  # API 키 입력 후
streamlit run app.py
```

## Phase 현황

현재: **Phase 1 — Core Logic** (구조 생성 완료, 노드 구현 필요)

다음 작업: `graph/nodes.py`의 `node_analyze` → `node_search` → `node_plan` 순서로 구현.
