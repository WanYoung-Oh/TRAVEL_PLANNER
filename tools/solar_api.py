import os
import time
from openai import OpenAI

SOLAR_BASE_URL = "https://api.upstage.ai/v1"
SOLAR_MODEL = "solar-pro"
_MAX_RETRIES = 2  # PRD §11: 최대 2회 재시도


def get_client() -> OpenAI:
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise ValueError("UPSTAGE_API_KEY가 .env에 설정되지 않았습니다.")
    return OpenAI(api_key=api_key, base_url=SOLAR_BASE_URL)


def chat(system: str, user: str, temperature: float = 0.7) -> str:
    """Solar Pro에 단일 요청. 5xx/타임아웃 시 최대 2회 재시도 후 예외 전파."""
    client = get_client()
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=SOLAR_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(2 ** attempt)  # 1s → 2s 지수 백오프
    raise last_exc  # type: ignore[misc]


def stream(system: str, user: str, temperature: float = 0.7):
    """Solar Pro 스트리밍 응답 제너레이터."""
    client = get_client()
    response = client.chat.completions.create(
        model=SOLAR_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        stream=True,
    )
    for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
