"""FastAPI 웹 데모 백엔드.

- GET  /                프론트엔드(제작통역 4단계 데모) 제공
- GET  /api/health      백엔드/LLM 연결 상태 (프론트가 실호출/데모모드 판단)
- POST /api/translate   제작통역 실행 → 주문 JSON + 비용/시간 계측
- GET  /api/eval        평가 하네스 A/B/C 요약 (후보 C 실측 포함)

실행:  uvicorn backend.app:app --reload   (프로젝트 루트에서)
키가 없으면 제작통역은 스텁으로 동작하고 health.llm = "stub".
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config
from .order_translation import OrderTranslator

app = FastAPI(title="서울 아랫길 600년 · 제작통역")

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
_translator: OrderTranslator | None = None


def translator() -> OrderTranslator:
    global _translator
    if _translator is None:
        _translator = OrderTranslator()
    return _translator


class TranslateReq(BaseModel):
    text: str


@app.get("/")
def index():
    return FileResponse(FRONTEND)


@app.get("/api/health")
def health():
    from . import restore
    return {
        "ok": True,
        "llm": config.active_backend(),   # local | claude | stub
        "model": config.active_model(),
        "restore": restore.available(),
    }


@app.get("/api/route")
def route(start: str = "E1", budget: int = 30):
    from . import route as route_mod
    try:
        return route_mod.plan_course(start, budget)
    except ValueError as e:
        return {"error": str(e)}


class RestoreReq(BaseModel):
    image_b64: str  # data URI 또는 순수 base64


@app.post("/api/restore")
def restore_ep(req: RestoreReq):
    import base64 as _b64
    from . import restore
    if not restore.available():
        return {"error": "Pillow 미설치 — pip install pillow"}
    raw = req.image_b64.split(",", 1)[-1]
    return restore.restore_preview(_b64.b64decode(raw))


def _meta_dict(res) -> dict:
    return {
        "latency_ms": round(res.meta.latency_ms, 1),
        "input_tokens": res.meta.input_tokens,
        "output_tokens": res.meta.output_tokens,
        "cost_usd": round(res.meta.cost_usd, 6),
        "cost_krw": round(res.meta.cost_krw, 2),
        "backend": res.meta.backend,
        "model": res.meta.model,
    }


@app.post("/api/translate")
def translate(req: TranslateReq):
    """제작통역 코어(슬롯필링만). 평가 하네스와 동일 의미 — 추천점포 미포함."""
    res = translator().translate(req.text)
    return {
        "order": res.order,
        "missing_slots": res.missing_slots,
        "needs_merchant_confirm": res.needs_merchant_confirm,
        "meta": _meta_dict(res),
    }


@app.post("/api/generate")
def generate(req: TranslateReq):
    """3번 화면 'AI 제작요청서' 생성: 제작통역 + 추천점포 매칭까지."""
    from . import shop_match
    res = translator().translate(req.text)
    shops = shop_match.match(res.order, top_n=2)
    return {
        "order": res.order,
        "missing_slots": res.missing_slots,
        "recommended_shops": shops,
        "needs_merchant_confirm": res.needs_merchant_confirm,
        "meta": _meta_dict(res),
    }


class OrderSubmitReq(BaseModel):
    order: dict
    recommended_shops: list = []
    text: str | None = None


@app.post("/api/orders")
def create_order(req: OrderSubmitReq):
    """'상인에게 전달' → 요청서 접수·주문번호 발급(4번 화면으로)."""
    from . import order_store
    rec = order_store.create(req.order, req.recommended_shops, req.text)
    return {
        "order_id": rec["order_id"],
        "status": rec["status"],
        "created_at": rec["created_at"],
        "recommended_shops": rec["recommended_shops"],
    }


@app.get("/api/orders/{order_id}")
def read_order(order_id: str):
    """4번 화면 상태 조회(상인 승인 대기/완료)."""
    from . import order_store
    rec = order_store.get(order_id)
    if rec is None:
        return {"error": "not_found", "order_id": order_id}
    return rec


@app.get("/api/eval")
def eval_summary():
    # 무거우므로 필요 시에만. 지연 임포트.
    from eval.run_eval import load_testset, run_system, TranslateOnlyClient
    from backend.llm_client import StubClient, get_client

    rows = load_testset()
    backend = config.active_backend()
    live = backend != "stub"
    systems = {
        "A_번역만": TranslateOnlyClient(),
        "B_규칙기반": StubClient(),
        "C_파이프라인": get_client() if live else StubClient(),
    }
    out = {}
    for name, client in systems.items():
        t = run_system(name, client, rows)
        out[name] = {
            "slot_f1": round(t.f1, 3),
            "completion_rate": round(t.completion_rate, 3),
            "false_rejection_rate": round(t.false_rejection_rate, 3),
            "mean_cost_krw": round(t.mean_cost_krw, 2),
            "mean_latency_ms": round(t.mean_latency_ms, 1),
        }
    return {"model": config.active_model(), "backend": backend,
            "llm_connected": live, "n": len(rows), "systems": out}
