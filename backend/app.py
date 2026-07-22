from __future__ import annotations

import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from route_engine import gate_information, recommend_route
from ai_interpreter import interpret_route_request

try:
    from route_database import database_status, list_stores, stores_open_now
    _DB_AVAILABLE = True
except Exception:  # pragma: no cover - optional data layer
    _DB_AVAILABLE = False


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.get("/")
    def demo_page():
        return send_from_directory("web", "index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "서울 아랫길 지하상가 QR 코스추천 API"})

    @app.get("/api/gates/<gate_token>")
    def gate(gate_token: str):
        return jsonify({"gate": gate_information(gate_token)})

    @app.get("/api/data/status")
    def data_status():
        if not _DB_AVAILABLE:
            return jsonify({"available": False, "message": "점포 데이터베이스가 아직 연결되지 않았습니다."})
        return jsonify(database_status())

    @app.get("/api/planned-spaces")
    def planned_spaces():
        if not _DB_AVAILABLE:
            return jsonify({"spaces": []})
        from route_database import list_planned_spaces
        return jsonify({"spaces": list_planned_spaces()})

    @app.get("/api/stores")
    def stores():
        if not _DB_AVAILABLE:
            return jsonify({"stores": []})
        query = request.args.get("q", "")
        open_now = request.args.get("open_now", "false").lower() == "true"
        if open_now:
            return jsonify({
                "stores": stores_open_now(query),
                "status_definition": "게시 영업시간과 현재시간이 일치함. 휴무·임시휴점은 상인 상태값으로 별도 확인 필요.",
            })
        return jsonify({"stores": list_stores(query)})

    @app.post("/api/routes/recommend")
    def recommend():
        payload = request.get_json(silent=True) or {}
        result = recommend_route(
            gate_token=payload.get("gate_token", ""),
            minutes=payload.get("minutes", 30),
            purpose=payload.get("purpose", "look"),
            destination=payload.get("destination"),
            accessible=bool(payload.get("accessible", False)),
            now_value=payload.get("now"),
            scenario=payload.get("scenario", "after_redevelopment"),
        )
        status = 200 if result.get("route") else 422
        return jsonify(result), status

    @app.post("/api/ai/routes/recommend")
    def ai_recommend():
        """Natural language -> validated conditions -> deterministic exact-time route."""
        payload = request.get_json(silent=True) or {}
        interpretation = interpret_route_request(
            payload.get("text", ""),
            gate_token=payload.get("gate_token"),
        )
        intent = interpretation["intent"]
        # Button-based requests are authoritative.  Natural language remains
        # an optional fallback for the free-text input only.
        if payload.get("minutes") in (10, 30, 60, 90):
            intent["minutes"] = payload["minutes"]
        if payload.get("purpose") in {"look", "memory", "make", "move", "history", "family", "service", "rest"}:
            intent["purpose"] = {"history": "memory", "family": "memory", "service": "make"}.get(payload["purpose"], payload["purpose"])
        if payload.get("destination") in {"ddp", "hipjiro", "bangsan", None, ""}:
            intent["destination"] = payload.get("destination") or None
        result = recommend_route(
            gate_token=intent["gate_token"],
            minutes=intent["minutes"],
            purpose=intent["purpose"],
            destination=intent["destination"],
            accessible=intent["accessible"],
            now_value=payload.get("now"),
            scenario="after_redevelopment",
        )
        # A visitor may choose a far-away exit with a 10-minute budget.
        # Do not make the UI fail: give the best local course and clearly tell
        # the visitor that the selected destination is the next leg.
        if not result.get("route") and intent["destination"]:
            requested_destination = intent["destination"]
            fallback = recommend_route(
                gate_token=intent["gate_token"],
                minutes=intent["minutes"],
                purpose=intent["purpose"],
                destination=None,
                accessible=intent["accessible"],
                now_value=payload.get("now"),
                scenario="after_redevelopment",
            )
            if fallback.get("route"):
                fallback["route"]["destination_notice"] = (
                    f"선택한 {requested_destination} 방향은 현재 {intent['minutes']}분 안에 도달하기 어려워, "
                    "지금 위치에서 이용 가능한 코스로 먼저 안내합니다."
                )
                fallback["route"]["requested_destination"] = requested_destination
                result = fallback
        result["ai"] = {
            "engine": interpretation["engine"],
            "interpreted_conditions": intent,
            **({"notice": interpretation["notice"]} if "notice" in interpretation else {}),
        }
        status = 200 if result.get("route") else 422
        return jsonify(result), status

    @app.errorhandler(ValueError)
    def value_error(error: ValueError):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(Exception)
    def unexpected_error(error: Exception):
        app.logger.exception("Unhandled route recommendation error")
        return jsonify({"error": "서버에서 코스를 계산하지 못했습니다."}), 500

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5011")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
