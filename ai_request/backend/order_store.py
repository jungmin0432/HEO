"""제작요청서 제출 저장소.

'상인에게 전달'(3번 화면) → 주문번호 발급 → 상인 승인 대기(4번 화면)의 최소 상태기계.
데모용 인메모리 저장(프로세스 재시작 시 초기화). 운영 시 SQLite/DB 로 교체.

상태: pending_merchant(승인대기) → approved(승인) / rejected(반려).
가격·납기 확정은 여기서 하지 않는다 — 상인이 approve 할 때 채운다(human-in-the-loop).
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_ORDERS: dict[str, dict] = {}
_SEQ = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create(order: dict, recommended_shops: list | None = None, source_text: str | None = None) -> dict:
    """요청서를 접수하고 주문번호(EJ-0001…)를 발급. 접수 레코드를 반환."""
    global _SEQ
    with _LOCK:
        _SEQ += 1
        oid = f"EJ-{_SEQ:04d}"
        rec = {
            "order_id": oid,
            "status": "pending_merchant",
            "order": order,
            "recommended_shops": recommended_shops or [],
            "source_text": source_text,
            "created_at": _now(),
            "updated_at": _now(),
            "merchant_note": None,
        }
        _ORDERS[oid] = rec
    return rec


def get(order_id: str) -> dict | None:
    return _ORDERS.get(order_id)


def set_status(order_id: str, status: str, merchant_note: str | None = None) -> dict | None:
    """상인 승인/반려 반영(4번 화면 데모용)."""
    with _LOCK:
        rec = _ORDERS.get(order_id)
        if rec is None:
            return None
        rec["status"] = status
        rec["merchant_note"] = merchant_note
        rec["updated_at"] = _now()
    return rec
