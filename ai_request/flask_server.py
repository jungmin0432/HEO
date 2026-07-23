"""AI 제작통역소 — Flask prototype server.

Per the competition spec (AI 제작통역소 row):
  LLM (Claude / GPT-4o) + Structured Output JSON Mode + Whisper (voice)
  + Human-in-the-loop merchant approval.

This is a thin Flask layer over the proven AI code in `backend/`:
  text/voice request  ->  Claude structured-output slot filling
                      ->  rule validation (missing required slots)
                      ->  shop matching (rule-based, no LLM)
                      ->  order card + merchant-confirm flag
No API key? It runs on a rule-based StubClient so the demo works offline.

Run:
    pip install -r requirements.txt
    python flask_server.py                 # -> http://localhost:5000
    (set ANTHROPIC_API_KEY in .env for real Claude; otherwise stub mode)

Routes (the frontend calls these):
    GET  /                     serve the demo frontend
    GET  /api/health           backend / LLM status
    POST /api/interpret        text -> structured order (+ shops)   [main button]
    POST /api/generate         alias of /api/interpret (frontend compat)
    POST /api/orders           'send to merchant' -> order_id
    GET  /api/orders/<id>      order status (merchant approval)
    POST /api/transcribe       optional: voice(base64 audio) -> text (Whisper)
"""
from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from backend import config, order_store, shop_match
from backend.order_translation import OrderTranslator

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"

# One translator instance (picks Claude if ANTHROPIC_API_KEY is set, else StubClient).
_translator: OrderTranslator | None = None


def translator() -> OrderTranslator:
    global _translator
    if _translator is None:
        _translator = OrderTranslator()
    return _translator


# Allow a separately-hosted frontend (web app) to call this API during the demo.
@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


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


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    if (FRONTEND_DIR / "index.html").exists():
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({"ok": True, "hint": "POST /api/interpret with {'text': ...}"})


@app.get("/request")
def request_page():
    """제작요청서 전용 페이지(AI 시간제작소 UI 가이드 디자인)."""
    return send_from_directory(FRONTEND_DIR, "request.html")


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "llm": config.active_backend(),   # local | claude | stub
        "model": config.active_model(),
        "service": "AI 제작통역소",
    })


def _interpret(text: str) -> dict:
    """Core: text -> structured order card + recommended shops.

    AI 호출이 실패해도(한도초과 429·네트워크 등) 500 으로 죽지 않고,
    규칙기반 스텁으로 대체해 항상 유효한 주문서를 돌려준다(데모 중단 방지).
    """
    llm_note = None
    try:
        res = translator().translate(text)
    except Exception as e:  # noqa: BLE001 - 데모 견고성: 어떤 LLM 오류든 스텁으로 폴백
        from backend.llm_client import StubClient
        res = OrderTranslator(client=StubClient()).translate(text)
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            llm_note = "AI 사용량(무료 한도) 초과 — 규칙기반으로 임시 처리됨. 잠시 후 다시 시도하세요."
        else:
            llm_note = "AI 호출 오류 — 규칙기반으로 임시 처리됨."

    shops = shop_match.match(res.order, top_n=2)
    return {
        "order": res.order,
        "missing_slots": res.missing_slots,
        "recommended_shops": shops,
        "needs_merchant_confirm": res.needs_merchant_confirm,
        "llm_note": llm_note,        # 정상이면 null
        "meta": _meta_dict(res),
    }


@app.post("/api/interpret")
@app.post("/api/generate")  # alias so the existing frontend works unchanged
def interpret():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty_text"}), 400
    return jsonify(_interpret(text))


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    order = data.get("order")
    if not isinstance(order, dict):
        return jsonify({"error": "order_required"}), 400
    rec = order_store.create(order, data.get("recommended_shops") or [], data.get("text"))
    return jsonify({
        "order_id": rec["order_id"],
        "status": rec["status"],
        "created_at": rec["created_at"],
        "recommended_shops": rec["recommended_shops"],
    })


@app.get("/api/orders/<order_id>")
def read_order(order_id: str):
    rec = order_store.get(order_id)
    if rec is None:
        return jsonify({"error": "not_found", "order_id": order_id}), 404
    return jsonify(rec)


@app.post("/api/transcribe")
def transcribe():
    """Optional voice input (PDF: Whisper ASR). base64 audio -> text.

    Gracefully degrades: if OPENAI_API_KEY / SDK is missing, returns a clear
    'not configured' message instead of crashing — keeps the demo runnable.
    Then feed the returned text into /api/interpret.
    """
    import os
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({"error": "whisper_not_configured",
                        "hint": "set OPENAI_API_KEY to enable voice, or POST text to /api/interpret"}), 501
    data = request.get_json(silent=True) or {}
    audio_b64 = data.get("audio_b64")
    if not audio_b64:
        return jsonify({"error": "audio_required"}), 400
    try:
        import openai  # lazy import
        raw = base64.b64decode(audio_b64.split(",", 1)[-1])
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(raw)
            tmp = f.name
        with open(tmp, "rb") as fh:
            tr = openai.OpenAI().audio.transcriptions.create(model="whisper-1", file=fh)
        return jsonify({"text": tr.text})
    except Exception as e:  # noqa: BLE001 - demo robustness
        return jsonify({"error": "transcription_failed", "detail": str(e)}), 500


if __name__ == "__main__":
    _be = config.active_backend()  # local | gemini | claude | stub
    _label = {"local": "로컬 GPU", "groq": "Groq(무료)", "gemini": "Gemini(무료)",
              "claude": "Claude", "stub": "stub(규칙기반, 키 없음)"}.get(_be, _be)
    print(f"[AI 제작통역소] LLM = {_be} · {_label} · model = {config.active_model()}")
    print("  http://localhost:5000   (Ctrl+C to stop)")
    app.run(host="0.0.0.0", port=5000, debug=True)
