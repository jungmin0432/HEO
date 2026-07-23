"""전역 설정 — 모델, 가격, 환율. 비용 리포트가 여기서 나온다."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# --- 모델 선택 -------------------------------------------------------------
MODEL = os.getenv("EULJIRO_MODEL", "claude-opus-4-8")

# --- 로컬 GPU LLM (Ollama / vLLM, OpenAI 호환) ----------------------------
# EULJIRO_LOCAL_BASE_URL 이 설정되면 자체 GPU 서버의 오픈모델을 쓴다(무료).
#   예) Ollama:  http://localhost:11434/v1   (원격이면 서버 IP:11434/v1)
#       vLLM:    http://localhost:8001/v1
LOCAL_BASE_URL = os.getenv("EULJIRO_LOCAL_BASE_URL")  # 없으면 로컬 미사용
LOCAL_MODEL = os.getenv("EULJIRO_LOCAL_MODEL", "qwen2.5:32b-instruct")
LOCAL_API_KEY = os.getenv("EULJIRO_LOCAL_API_KEY", "local")  # Ollama 는 아무 값이나 됨

# --- Google Gemini (무료 티어) ------------------------------------------
# aistudio.google.com 에서 무료 키 발급. OpenAI 호환 엔드포인트로 호출.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("EULJIRO_GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# --- Groq (무료 티어, 한도 넉넉) ----------------------------------------
# console.groq.com 에서 무료 키 발급(gsk_...). OpenAI 호환. 오픈모델(Llama 등), 매우 빠름.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# gpt-oss-120b: 다국어 번역 품질 좋고 reasoning_effort=low 로 빠름(~1초). Groq 무료.
GROQ_MODEL = os.getenv("EULJIRO_GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# --- 가격표 (USD per 1M tokens) -------------------------------------------
# 출처: Anthropic 공식 가격 (2026-06 기준). 모델 교체 시 여기만 갱신.
# 비용 리포트의 "AI는 비용 병목이 아니다" 논증은 이 표에서 계산된다.
PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    # model: (input, output)
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
# 자체 GPU 로컬 모델은 API 과금이 없다 → 0원. (전기료는 별개)
if LOCAL_BASE_URL:
    PRICING_USD_PER_MTOK.setdefault(LOCAL_MODEL, (0.0, 0.0))
# Gemini / Groq 무료 티어 → 0원으로 기록(무료 한도 내 사용 가정).
PRICING_USD_PER_MTOK.setdefault(GEMINI_MODEL, (0.0, 0.0))
PRICING_USD_PER_MTOK.setdefault(GROQ_MODEL, (0.0, 0.0))

USD_KRW = float(os.getenv("EULJIRO_USD_KRW", "1350"))


@dataclass(frozen=True)
class CostBreakdown:
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_krw: float


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> CostBreakdown:
    """토큰 사용량 → 건당 비용(USD, KRW). 평가 하네스가 케이스마다 호출."""
    in_price, out_price = PRICING_USD_PER_MTOK.get(model, (5.00, 25.00))
    cost_usd = (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price
    return CostBreakdown(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        cost_krw=cost_usd * USD_KRW,
    )


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def has_local() -> bool:
    return bool(LOCAL_BASE_URL)


def has_gemini() -> bool:
    return bool(GEMINI_API_KEY)


def has_groq() -> bool:
    return bool(GROQ_API_KEY)


def active_backend() -> str:
    """현재 어떤 LLM 백엔드가 뜰지. 우선순위: 로컬 GPU > Groq > Gemini > Claude > 스텁.

    명시적으로 켠 것(BASE_URL·키)을 순서대로 우선한다.
    """
    if has_local():
        return "local"
    if has_groq():
        return "groq"
    if has_gemini():
        return "gemini"
    if has_api_key():
        return "claude"
    return "stub"


def active_model() -> str:
    return {
        "local": LOCAL_MODEL,
        "groq": GROQ_MODEL,
        "gemini": GEMINI_MODEL,
        "claude": MODEL,
    }.get(active_backend(), MODEL)
