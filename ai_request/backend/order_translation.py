"""제작통역 파이프라인: 입력 텍스트 → (LLM 슬롯필링) → (룰 제약검증) → 구조화 주문 + 계측.

파이프라인 = LLM 슬롯필링 + 룰 검증. 베이스라인(구글번역/LLM 단독)과의 차이가 여기서 난다.
반환 meta 에 latency_ms / tokens / cost 를 담아 평가 하네스가 비용·시간을 '측정'하게 한다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config
from .llm_client import LLMClient, get_client
from .schema import compute_missing


@dataclass
class TranslationMeta:
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_krw: float
    backend: str
    model: str


@dataclass
class TranslationResult:
    order: dict
    meta: TranslationMeta
    needs_merchant_confirm: bool
    missing_slots: list[str] = field(default_factory=list)


class OrderTranslator:
    def __init__(self, client: LLMClient | None = None):
        self.client = client or get_client()
        self.model = getattr(self.client, "model", config.MODEL)

    def translate(self, text: str) -> TranslationResult:
        t0 = time.perf_counter()
        res = self.client.translate(text)
        latency_ms = (time.perf_counter() - t0) * 1000

        order = res.order
        # 룰 검증: 모델 자기신고(missing_slots)와 별개로 실제 채워진 값으로 재계산.
        missing = compute_missing(order)
        order["missing_slots"] = missing

        cost = config.estimate_cost(self.model, res.input_tokens, res.output_tokens)
        meta = TranslationMeta(
            latency_ms=latency_ms,
            input_tokens=res.input_tokens,
            output_tokens=res.output_tokens,
            cost_usd=cost.cost_usd,
            cost_krw=cost.cost_krw,
            backend=res.backend,
            model=self.model,
        )
        return TranslationResult(
            order=order,
            meta=meta,
            needs_merchant_confirm=True,   # 항상 상인 승인 필요(human-in-the-loop)
            missing_slots=missing,
        )
