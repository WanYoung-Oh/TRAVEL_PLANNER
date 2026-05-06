# Solar-Travel Planner — MVP 제품 요구사항 정의서 (PRD)

**문서 목적:** 최소 기능 제품(MVP)이 어떤 가치를 제공하고, 무엇을 만들지·하지 않을지, MacBook Pro M4 16GB 환경에서 어떻게 개발·실행할지 팀과 이해관계자가 같은 그림을 갖도록 정리합니다.  
**기반 문서:** `MVP-Concept.md`

---

## 1. 용어 정리

| 말 | 뜻 (비개발자용) |
| --- | --- |
| MVP | 꼭 필요한 기능만 넣은 첫 버전 제품 |
| LLM / Solar Pro | 인공지능이 글을 짓는 "두뇌". 우리는 업스테이지 서버(API)에 요청만 보냄 |
| LangGraph | 여러 단계(검색 → 일정 짜기 → 내보내기)를 순서대로·병렬로 돌리게 정리하는 도구 |
| TourAPI | 한국관광공사에서 제공하는 공식 관광 정보 API |
| OAuth | 구글 계정으로 "이 앱이 문서 만들 권한"을 안전하게 받는 방식 |
| RAG | DB에서 관련 정보를 찾아 AI에게 같이 넘겨주는 방식 |
| Streamlit | Python으로 빠르게 웹 UI를 만드는 프레임워크 (MVP 전용) |

---

## 2. 제품 개요

- **프로젝트명 (가칭):** Solar-Travel Planner  
- **한 줄 목적:** 사용자가 **여행 지역·기간**을 입력하면, AI가 **서로 다른 성격의 일정 3가지**를 제안하고, 고른 안을 **구글 문서**로 깔끔하게 만들어 준다.  
- **타겟:** 국내 여행 계획이 귀찮지만 **취향(테마)**은 반영하고 싶은 사람.  
- **국가/범위 (MVP):** **국내** 위주. 도·시 단위 입력. 해외·항공·숙소 예약 연동은 범위 밖.

---

## 3. 로컬 개발·실행 환경 (MacBook Pro M4, 16GB)

### 3.1 왜 이걸 PRD에 넣나

RAM 16GB에서 브라우저, 에디터, 우리 앱이 동시에 메모리를 씁니다. "무거운 AI를 내 컴퓨터에서 돌리지 않는다"는 원칙을 제품 요구사항에 박아 두면, MVP가 **항상 이 맥북에서 현실적으로** 돌아갑니다.

### 3.2 환경 원칙 (필수)

- **추론(일정 문장 짜기):** 전부 **Solar Pro API(클라우드)**. 로컬에서 대형 AI 모델을 돌리지 않는다.  
- **RAG:**  
  - **목표 아키텍처:** BM25 + 벡터 검색 하이브리드 + 국내 관광 DB 연동.  
  - **MVP 1차 기본값:** TourAPI 결과 + **키워드/간단 검색·캐시** 중심으로 시작. 벡터 검색은 **ChromaDB(인메모리/로컬)** 또는 **Upstage Embeddings API** 기반으로 제한한다.  
- **동시에 띄우는 프로그램:** Docker 사용 시 **한 세트(DB 하나)** 정도. 여러 무거운 컨테이너 + 로컬 AI 동시 실행은 권장하지 않는다.

### 3.3 로컬 실행 요약

```
Python 3.11+ 가상환경 → .env에 키 설정 → streamlit run app.py
```

---

## 4. 기능 요구사항 (추적용 ID)

### 4.1 대화형 정보 수집

- **FR-CHAT-01:** 챗봇 UI로 **여행지(도/시 단위)**와 **기간(N박 M일)**을 받는다.  
- **FR-CHAT-02:** AI 응답은 **스트리밍**(토큰 단위 실시간 표시)을 지원한다.  
- **FR-CHAT-03:** 입력 파싱 실패 시(예: "부산 가고 싶어"처럼 날짜 없음), 재질문 메시지를 출력한다.  
- **사용자 스토리:** "여행지와 날짜만 말하면, 나 맞춤 계획 초안을 받고 싶다."

### 4.2 테마별 3종 스케줄 제안

- **FR-PLAN-01:** Solar Pro로 다음 **3가지 테마** 일정을 만든다.  
  - 시그니처 (대표 명소 중심)  
  - 감성/트렌드 (SNS·카페 핫플 중심)  
  - 힐링/여유 (자연·여백 중심)  
- **FR-PLAN-02:** 일정마다 **명소**와 **맛집**이 **날짜·시간대(오전/오후/저녁) 단위**로 포함된다.  
- **FR-PLAN-03:** 각 일정은 **테마 이름, 한 줄 소개, 장소 목록** 구조로 반환된다.  
- **FR-LINK-01:** 장소별로 **지도/정보로 갈 수 있는 링크**(TourAPI URL, 카카오·네이버 지도 딥링크 등)를 제공한다. 링크를 못 구하면 **텍스트 주소만**이라도 표시하는 **폴백**을 둔다.  
- **FR-DATA-01:** 관광 후보는 **한국관광공사 TourAPI 4.0**을 우선 활용한다. API 키·호출 한도는 `.env` 및 문서에 명시한다.

### 4.3 구글 문서 내보내기

- **FR-EXPORT-01:** 사용자가 **하나를 선택**한 최종 일정을 **Google Docs**에 **표 형태**로 생성한다.  
- **FR-EXPORT-02:** 표 안 링크는 **클릭 가능**해야 한다.  
- **FR-EXPORT-03:** Google 계정 연동은 **OAuth 2.0** 방식을 따른다.  
- **FR-EXPORT-04:** 생성된 Google Docs 링크를 앱 화면에서 **바로 열 수 있도록** 표시한다.

---

## 5. LangGraph 워크플로 (제품 설계)

### 5.1 상태(State) 구조

```python
class TravelState(TypedDict):
    # 입력
    destination: str          # 여행지 (예: "부산")
    duration: str             # 기간 (예: "2박 3일")
    raw_user_input: str       # 원본 사용자 메시지

    # 중간 처리
    search_query: str         # Node_Analyze가 만든 검색 쿼리
    candidates: list[Place]   # Node_Search가 찾은 장소 후보
    plans: list[TravelPlan]   # Node_Plan이 만든 3가지 일정

    # 출력
    selected_plan: TravelPlan # Node_Wait에서 사용자가 선택한 안
    doc_url: str              # Node_Export 후 Google Docs URL
    error: str | None         # 에러 메시지
```

### 5.2 노드 정의

| 노드 | 역할 | 입력 → 출력 |
| --- | --- | --- |
| **Node_Analyze** | 사용자 의도 파악, 검색 쿼리 생성 | `raw_user_input` → `destination`, `duration`, `search_query` |
| **Node_Search** | TourAPI + (선택) Tavily로 장소 후보 확보 | `search_query`, `destination` → `candidates` |
| **Node_Plan (Parallel)** | Solar Pro로 3테마 일정 병렬 생성 | `candidates`, `duration` → `plans` |
| **Node_Wait** | 사용자 선택 대기 (LangGraph Interrupt) | `plans` → `selected_plan` |
| **Node_Export** | 선택 일정을 Google Docs 표로 생성 | `selected_plan` → `doc_url` |

### 5.3 플로우 다이어그램

```
[사용자 입력]
     │
     ▼
Node_Analyze
     │
     ▼
Node_Search (TourAPI 4.0)
     │
     ▼
Node_Plan ──┬── 시그니처 일정 생성 (Solar Pro)
 (병렬)     ├── 감성/트렌드 일정 생성 (Solar Pro)
            └── 힐링/여유 일정 생성 (Solar Pro)
     │
     ▼
Node_Wait ◄── [사용자: 카드에서 1가지 선택]
     │
     ▼
Node_Export (Google Docs API)
     │
     ▼
[Google Docs URL 반환]
```

### 5.4 구현 순서 (Phase 대응)

- **Phase 1:** Analyze → Search → Plan을 **1개 테마 또는 순차 3테마**로 먼저 완성해 동작 검증.  
- **Phase 2:** Plan을 **병렬 3테마**로 맞추고, UI에서 **3카드 슬라이드**로 비교.  
- **Phase 3:** 링크 보강(Tavily 또는 검색 API), Google Docs **표+하이퍼링크** 완성.  
- **Phase 4:** 예외(결과 없음·폐업 추정 등), 캐싱, 속도 개선, 배포.

---

## 6. UI/UX 요구사항

### 6.1 화면 플로우

```
[1. 채팅 입력 화면]
  ├── 사이드바: 앱 소개, 사용 방법
  ├── 채팅창: 사용자 메시지 입력
  └── 스트리밍 응답: "부산 2박 3일 일정을 찾고 있습니다..."

[2. 일정 제안 화면]
  ├── 3종 카드 (가로 슬라이드 or 탭)
  │   ├── 카드 1: 시그니처 — 제목, 한 줄 소개, 장소 목록
  │   ├── 카드 2: 감성/트렌드 — 동일 구조
  │   └── 카드 3: 힐링/여유 — 동일 구조
  └── [이 일정으로 문서 만들기] 버튼 (카드별)

[3. 내보내기 완료 화면]
  ├── "구글 문서가 생성되었습니다!"
  └── [Google Docs 열기] 링크 버튼
```

### 6.2 컴포넌트 상세

| 컴포넌트 | 설명 | MVP 구현 방법 |
| --- | --- | --- |
| **채팅창** | 메시지 스트리밍 지원 | `st.chat_message` + `st.write_stream` |
| **일정 카드** | 3가지 제안을 탭 또는 컬럼으로 비교 | `st.tabs` 또는 `st.columns(3)` |
| **링크 칩** | 장소명 클릭 시 지도로 이동 | `st.link_button` 또는 Markdown 링크 |
| **선택 버튼** | 카드별 "이 일정 선택" | `st.button` → LangGraph `interrupt` 해제 |
| **Google Docs 버튼** | 생성 완료 후 URL 열기 | `st.link_button(url=doc_url)` |

### 6.3 UX 원칙

- **입력 최소화:** 첫 메시지에 여행지 + 기간만 말하면 된다.
- **대기 시간 시각화:** 일정 생성 중 `st.spinner("일정을 짜는 중입니다...")` 표시.
- **폴백 UI:** 링크 없는 장소는 텍스트 주소 + 카카오맵 검색 URL로 대체.

---

## 7. 기술 스택 (상세)

### 7.1 핵심 스택

| 구분 | 선택 | 비고 |
| --- | --- | --- |
| **언어** | Python 3.11+ | M4 네이티브 지원 |
| **LLM** | Upstage **Solar Pro API** | OpenAI 호환 엔드포인트 |
| **오케스트레이션** | **LangGraph** 0.2.x | 상태 머신 + 병렬 노드 |
| **관광 데이터** | **TourAPI 4.0** | 한국관광공사 공식 API |
| **문서 내보내기** | **Google Docs API** v1 + OAuth 2.0 | |
| **프론트엔드 (MVP)** | **Streamlit** 1.35+ | 빠른 채팅 UI 구현 |
| **링크 보강 (선택)** | **Tavily API** 또는 Google Custom Search | Phase 3 이후 적용 |

### 7.2 RAG / 검색 스택

| 구분 | MVP 기본값 | 목표 아키텍처 |
| --- | --- | --- |
| **벡터 DB** | ChromaDB (인메모리 또는 로컬 파일) | 동일 (소형 인덱스 유지) |
| **임베딩** | Upstage Embeddings API (클라우드) | 동일 |
| **키워드 검색** | rank-bm25 (Python 라이브러리) | BM25 + 벡터 하이브리드 |
| **관광 데이터 소스** | TourAPI 4.0 실시간 조회 | TourAPI + 캐시 레이어 |

### 7.3 주요 Python 의존성

```
# LangChain / LangGraph
langgraph>=0.2
langchain-core>=0.2
langchain-upstage        # Solar Pro 연동

# UI
streamlit>=1.35

# 관광 데이터
requests                 # TourAPI HTTP 호출

# RAG
chromadb                 # 벡터 DB
rank-bm25                # BM25 검색

# Google Docs
google-auth-oauthlib
google-api-python-client

# 링크 보강 (선택)
tavily-python

# 유틸리티
python-dotenv
pydantic>=2
```

---

## 8. 프로젝트 구조

```
Travel_Planner/
├── app.py                  # Streamlit 진입점
├── .env                    # API 키 (git 제외)
├── .env.example            # 키 이름만 공개 (git 포함)
├── requirements.txt
│
├── graph/
│   ├── state.py            # TravelState TypedDict 정의
│   ├── nodes.py            # 5개 노드 함수
│   └── workflow.py         # LangGraph 워크플로 조립
│
├── tools/
│   ├── tour_api.py         # TourAPI 4.0 클라이언트
│   ├── solar_api.py        # Solar Pro API 래퍼
│   ├── google_docs.py      # Google Docs API + OAuth
│   └── search.py           # Tavily / 링크 보강 (선택)
│
├── rag/
│   ├── bm25_retriever.py   # BM25 검색
│   ├── vector_store.py     # ChromaDB 관리
│   └── hybrid.py           # BM25 + 벡터 혼합 검색
│
├── ui/
│   ├── chat.py             # 채팅 컴포넌트
│   ├── plan_cards.py       # 3종 일정 카드 컴포넌트
│   └── styles.py           # CSS 커스텀
│
├── models/
│   └── schema.py           # Place, TravelPlan, DayPlan 데이터 모델
│
└── docs/
    ├── MVP-Concept.md
    └── PRD.md
```

---

## 9. 데이터 모델

```python
# models/schema.py

class Place(BaseModel):
    name: str                    # 장소명
    category: str                # "명소" | "맛집" | "카페" 등
    address: str                 # 텍스트 주소 (폴백용)
    map_url: str | None          # 지도 링크 (없으면 None)
    description: str             # Solar Pro가 생성한 한 줄 소개

class TimeSlot(BaseModel):
    time: str                    # "오전" | "오후" | "저녁"
    place: Place

class DayPlan(BaseModel):
    day: int                     # 1, 2, 3...
    slots: list[TimeSlot]

class TravelPlan(BaseModel):
    theme: str                   # "시그니처" | "감성/트렌드" | "힐링/여유"
    summary: str                 # 테마 한 줄 소개
    days: list[DayPlan]
    estimated_cost: str | None   # 선택적
```

---

## 10. 외부 API 연동 상세

### 10.1 TourAPI 4.0 주요 엔드포인트

| 엔드포인트 | 용도 | 주요 파라미터 |
| --- | --- | --- |
| `areaBasedList` | 지역 기반 관광지 목록 | `areaCode`, `contentTypeId`, `numOfRows` |
| `searchKeyword` | 키워드 검색 | `keyword`, `areaCode` |
| `detailCommon` | 장소 상세 정보 | `contentId` |

- **일일 호출 한도:** 무료 계정 기준 확인 후 `.env`에 `TOUR_API_DAILY_LIMIT` 명시.
- **응답 포맷:** JSON. `items.item[]` 배열에서 `title`, `addr1`, `mapx`, `mapy`, `firstimage` 추출.

### 10.2 Solar Pro API

- **엔드포인트:** Upstage OpenAI 호환 (`https://api.upstage.ai/v1`)
- **모델명:** `solar-pro`
- **병렬 호출:** Phase 2부터 3개 테마를 `asyncio.gather` 또는 LangGraph 병렬 노드로 동시 요청.
- **토큰 예산:** 장소 후보 데이터(TourAPI 결과) + 시스템 프롬프트 포함 1회 요청당 약 2,000–4,000 토큰 예상.

### 10.3 Google Docs API

- **인증:** OAuth 2.0, `credentials.json` 로컬 보관 (git 제외).
- **주요 작업:** `documents.create` (신규 문서) → `documents.batchUpdate` (표 삽입 + 하이퍼링크 적용).
- **출력 형식:** 날짜별 행, 시간대별 열, 장소명 + 링크 포함 표.

---

## 11. 에러 처리 전략

| 시나리오 | 처리 방법 |
| --- | --- |
| 사용자 입력 파싱 실패 (날짜/지역 불명확) | Node_Analyze가 재질문 메시지 반환 → 채팅에 표시 |
| TourAPI 검색 결과 0건 | 검색 범위 확대 (도→전국) 후 재시도. 그래도 없으면 오류 메시지 |
| Solar Pro API 오류 (5xx, 타임아웃) | 최대 2회 재시도, 실패 시 사용자에게 안내 후 중단 |
| 링크 수집 실패 | 텍스트 주소 + 카카오맵 검색 URL(`https://map.kakao.com/?q=장소명`) 폴백 |
| Google OAuth 미완료 | OAuth URL을 채팅창에 안내 → 인증 후 재시도 유도 |
| Google Docs 생성 실패 | 일정 텍스트를 화면에 직접 표시 (내보내기 실패해도 일정 확인 가능) |

---

## 12. 비기능 요구사항

- **NFR-MEM:** 로컬에서는 Solar Pro를 거치지 않는 무거운 AI 추론을 기본값으로 두지 않는다. RAG는 경량 경로가 MVP 기본.  
- **NFR-LAT:** 최초 입력부터 3안 표시까지 목표 소요 시간은 **60초 이내**. 측정은 Phase 4에서 실측 후 기입.  
- **NFR-ACC:** "실존 장소" 비율 목표는 TourAPI 기반이므로 **98% 이상** 기대. 샘플 10건 수동 검증으로 확인.  
- **NFR-SEC:** API 키·OAuth 비밀은 `.env`로만 관리, `.gitignore`에 반드시 추가.  
- **NFR-PORT:** `streamlit run app.py` 단일 명령으로 로컬 실행 가능.

---

## 13. MVP 포함 / 제외

**포함 (In):**  
대화 입력, 3테마 제안(Phase 1에서는 순차라도 최종 3안), TourAPI 연동, 지도/정보 링크(폴백 포함), Google Docs 내보내기, 기본 오류 메시지, 스트리밍 응답.

**제외 (Out, MVP 이후):**  
멀티 유저 계정·결제, 모바일 네이티브 앱, 실시간 영업·혼잡 API 보장, 로컬 대형 LLM, 대규모 벡터 클러스터, 숙소/항공 예약 연동, 다국어(한국어만).

---

## 14. 성공 지표 (KPI)

| 지표 | 목표 | 측정 방법 |
| --- | --- | --- |
| 실존 장소 정확도 | 98% 이상 | TourAPI 기반 + 샘플 10건 수동 확인 |
| 3안 생성 소요 시간 | 60초 이내 | Phase 4 실측 |
| 입력 → 문서 완성 클릭 수 | 5회 이하 | UX 단계 수 계산 |
| 테마 차별성 | 3안이 명확히 다름 | 정성 평가 (소수 사용자 테스트) |

---

## 15. 리스크·가정

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| Google Cloud OAuth 심사 지연 | Google Docs 기능 블로킹 | OAuth 완료 전에는 텍스트 내보내기로 대체 |
| TourAPI 일일 호출 한도 초과 | 일정 생성 실패 | 응답 캐싱 + 호출 수 모니터링 |
| Solar Pro 요금·쿼터 제한 | 병렬 호출 불가 | 병렬 → 순차로 fallback, 쿼터 확인 |
| M4 16GB 메모리 압박 | 개발 환경 불안정 | ChromaDB 인메모리 대신 파일 모드 전환 가능 |

---

## 16. 로드맵 (상세)

### Phase 1 — Core Logic (우선순위: 필수)
- [x] Python 프로젝트 구조 세팅 (`graph/`, `tools/`, `models/`)
- [x] TourAPI 4.0 클라이언트 구현 (`tools/tour_api.py`) — KorService2, HTTPS
- [x] Solar Pro API 래퍼 구현 (`tools/solar_api.py`) — 최대 2회 재시도
- [x] LangGraph 기본 워크플로 (Analyze → Search → Plan → Wait → Export)
- [x] Streamlit 기본 채팅 UI + 노드별 진행 상황 스트리밍 (FR-CHAT-02)

### Phase 2 — Multi-Theme (우선순위: 핵심 기능)
- [x] Node_Plan 병렬 3테마 구현 — ThreadPoolExecutor (PRD §5.2)
- [x] Node_Wait (LangGraph Interrupt) 구현
- [x] 3종 카드 UI — `app.py` st.columns(3) + st.container(border=True)
- [x] 데이터 모델 완성 (`models/schema.py`) — Place, TimeSlot, DayPlan, TravelPlan

### Phase 3 — Link & Doc (우선순위: 완성도)
- [x] 장소별 지도 링크 수집 — TourAPI mapx/mapy 좌표 링크 + 카카오맵 폴백 (FR-LINK-01)
- [x] Google OAuth 2.0 연동 (`tools/google_docs.py`)
- [x] Google Docs 표 생성 — 날짜|시간대|장소|카테고리|주소, 헤더 bold, 장소 hyperlink (FR-EXPORT-01/02)
- [x] 링크 칩 UI — `app.py` 카드 내 Markdown 하이퍼링크

### Phase 4 — QA & MVP (우선순위: 안정화)
- [x] 예외 처리 전략 구현 — 조건부 엣지(error→END), 노드별 try/except (Section 11)
- [ ] TourAPI 응답 캐싱
- [ ] 응답 속도 측정 및 최적화
- [ ] `.env.example` 작성 및 README 정리

---

## 17. 문서 이력

| 버전 | 날짜 | 설명 |
| --- | --- | --- |
| 0.1 | 2026-05-06 | `MVP-Concept.md` 반영, M4 16GB 로컬 전제 및 MVP 단계·RAG 경량화 명시 |
| 0.2 | 2026-05-06 | 기술 스택 상세화 (Streamlit, ChromaDB, 의존성), 프로젝트 구조, 데이터 모델, 에러 처리 전략, API 연동 상세, UI/UX 화면 플로우, Phase별 체크리스트 추가 |
