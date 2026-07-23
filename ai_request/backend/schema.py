"""제작요청서(주문) 스키마.

제안서 3.3 'AI 제작통역: 멀티모달 입력 → 구조화된 주문 JSON' 의 코어.
- 상인이 바로 승인할 수 있는 작업지시가 되려면 아래 '필수 슬롯'이 모두 채워져야 한다.
- 가격/납기 가능여부는 AI가 확정하지 않는다(상인 승인). 그래서 price 필드가 없다.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# 필수 슬롯: 이게 안 채워지면 상인이 견적을 낼 수 없다 → 반려/재질문 대상.
# 평가의 '완성률'과 '반려율'이 이 목록에 걸린다.
REQUIRED_SLOTS = ["item", "size", "quantity", "material_or_finish", "due", "pickup_method"]

# 채점 대상 전체 슬롯(필수 + 선택). 슬롯 F1 은 이 목록으로 계산.
SCORED_SLOTS = REQUIRED_SLOTS + ["colors", "notes"]


class Order(BaseModel):
    """상인이 승인 전 검수하는 구조화된 주문."""

    item: Optional[str] = Field(None, description="제작 품목. 예: 자수패치, 명함, 포스터, 간판, 유니폼 마킹")
    size: Optional[str] = Field(None, description="규격/사이즈. 예: 100x100mm, A5, 90x50mm")
    quantity: Optional[int] = Field(None, description="수량(정수). 모르면 null")
    pages: Optional[int] = Field(None, description="쪽수(정수). 책자·룩북·카탈로그 등 인쇄물일 때만. 아니면 null")
    print_mode: Optional[str] = Field(None, description="인쇄 방식. 예: 컬러, 흑백, 양면 컬러, 별색. 인쇄물이 아니면 null")
    material: Optional[str] = Field(None, description="재료/원단. 예: 면, 종이 250g, 아트지")
    finish: Optional[str] = Field(None, description="마감/가공. 예: 열접착, 코팅, 박, 재봉, 중철제본")
    colors: list[str] = Field(default_factory=list, description="색상 목록. 예: ['남색','주황']")
    due: Optional[str] = Field(None, description="희망 완료 시점. 원문 그대로 텍스트로. 예: '오늘 18:20', '금요일'")
    due_date: Optional[str] = Field(None, description="due 를 오늘 기준 실제 날짜로 환산. 'YYYY-MM-DD (요일)'. 확정 불가면 null")
    pickup_method: Optional[str] = Field(None, description="수령방법. 예: 현장수령, 픽업, 배송")
    budget: Optional[str] = Field(None, description="예산/희망가(있을 때만). 없으면 null")
    notes: Optional[str] = Field(None, description="기타 특이사항")

    source_lang: Optional[str] = Field(None, description="입력 언어 감지. 예: ko, en, zh")
    missing_slots: list[str] = Field(
        default_factory=list,
        description="필수 슬롯 중 입력에서 확정할 수 없어 상인 확인이 필요한 항목들",
    )


def required_value(order: dict, slot: str):
    """필수 슬롯 하나의 '채워졌는지' 판정용 대표값을 뽑는다.

    material_or_finish 는 재료 또는 마감 중 하나만 있어도 채워진 것으로 본다
    (업종에 따라 한쪽만 유효 — 인쇄는 재료, 마킹은 마감).
    """
    if slot == "material_or_finish":
        return order.get("material") or order.get("finish")
    return order.get(slot)


def compute_missing(order: dict) -> list[str]:
    """실제 채워진 값 기준으로 누락 필수 슬롯을 계산(모델 자기신고와 별개로 검증)."""
    missing = []
    for slot in REQUIRED_SLOTS:
        val = required_value(order, slot)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(slot)
    return missing


def order_json_schema() -> dict:
    """Claude structured output(output_config.format)에 넘길 JSON Schema.

    structured outputs 는 minLength/최소값 등 제약을 지원하지 않으므로 형태만 강제한다.
    """
    return {
        "type": "object",
        "properties": {
            "item": {"type": ["string", "null"]},
            "size": {"type": ["string", "null"]},
            "quantity": {"type": ["integer", "null"]},
            "pages": {"type": ["integer", "null"]},
            "print_mode": {"type": ["string", "null"]},
            "material": {"type": ["string", "null"]},
            "finish": {"type": ["string", "null"]},
            "colors": {"type": "array", "items": {"type": "string"}},
            "due": {"type": ["string", "null"]},
            "due_date": {"type": ["string", "null"]},
            "pickup_method": {"type": ["string", "null"]},
            "budget": {"type": ["string", "null"]},
            "notes": {"type": ["string", "null"]},
            "source_lang": {"type": ["string", "null"]},
            "missing_slots": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "item", "size", "quantity", "pages", "print_mode", "material", "finish", "colors",
            "due", "due_date", "pickup_method", "budget", "notes", "source_lang", "missing_slots",
        ],
        "additionalProperties": False,
    }
