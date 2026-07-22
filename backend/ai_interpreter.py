"""Natural-language route input interpreter.

The route engine remains the source of truth for operating hours, walking time,
and the exact 10/30/60/90 minute budget.  OpenAI only turns a visitor's words
into a small, validated set of route conditions.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


ALLOWED_MINUTES = (10, 30, 60, 90)
ALLOWED_PURPOSES = ("look", "history", "family", "make", "service", "rest")
ALLOWED_DESTINATIONS = ("ddp", "hipjiro", "euljiro-entrance", "bangsan", "cheonggyecheon")
# The visitor-facing buttons are more detailed than the first MVP route graph.
# Map them to the graph's validated purpose vocabulary before route calculation.
ROUTE_PURPOSE_MAP = {
    "look": "look",
    "history": "memory",
    "family": "memory",
    "make": "make",
    "service": "make",
    "rest": "rest",
}


def _nearest_minutes(value: int) -> int:
    return min(ALLOWED_MINUTES, key=lambda item: abs(item - value))


def normalize_intent(value: dict[str, Any], *, gate_token: str | None = None) -> dict[str, Any]:
    """Accept only the small contract used by the deterministic route engine."""
    try:
        minutes = int(value.get("minutes", 30))
    except (TypeError, ValueError):
        minutes = 30
    minutes = _nearest_minutes(minutes)
    experience_type = value.get("purpose", "look")
    if experience_type not in ALLOWED_PURPOSES:
        experience_type = "look"
    destination = value.get("destination")
    if destination not in ALLOWED_DESTINATIONS:
        destination = None
    return {
        "gate_token": gate_token or value.get("gate_token") or "E3-01",
        "minutes": minutes,
        "purpose": ROUTE_PURPOSE_MAP[experience_type],
        "experience_type": experience_type,
        "destination": destination,
        "accessible": bool(value.get("accessible", False)),
        "companions": value.get("companions", "alone"),
        "weather": value.get("weather", "normal"),
    }


def rule_based_intent(text: str, *, gate_token: str | None = None) -> dict[str, Any]:
    """Offline fallback: enough for demos when an API key is unavailable."""
    source = text.lower()
    minutes_match = re.search(r"(10|30|60|90)\s*분", source)
    minutes = int(minutes_match.group(1)) if minutes_match else 30

    purpose = "look"
    if any(word in source for word in ("아이", "가족", "어린이")):
        purpose = "family"
    elif any(word in source for word in ("사진", "역사", "기억", "전시")):
        purpose = "history"
    elif any(word in source for word in ("만들", "인쇄", "제작", "마킹", "수선", "명함")):
        purpose = "make"
    elif any(word in source for word in ("카페", "쉬", "휴식", "앉")):
        purpose = "rest"

    destination = None
    if "ddp" in source or "동대문" in source:
        destination = "ddp"
    elif "힙지로" in source:
        destination = "hipjiro"
    elif "방산" in source:
        destination = "bangsan"
    elif "청계천" in source:
        destination = "cheonggyecheon"

    return normalize_intent(
        {
            "minutes": minutes,
            "purpose": purpose,
            "destination": destination,
            "accessible": any(word in source for word in ("휠체어", "유모차", "엘리베이터")),
            "companions": "family" if purpose == "family" else "alone",
            "weather": "rain" if any(word in source for word in ("비", "폭염", "한파")) else "normal",
        },
        gate_token=gate_token,
    )


def _openai_intent(text: str, gate_token: str | None) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "minutes": {"type": "integer", "enum": list(ALLOWED_MINUTES)},
            "purpose": {"type": "string", "enum": list(ALLOWED_PURPOSES)},
            "destination": {"type": ["string", "null"], "enum": list(ALLOWED_DESTINATIONS) + [None]},
            "accessible": {"type": "boolean"},
            "companions": {"type": "string", "enum": ["alone", "family", "friends", "business"]},
            "weather": {"type": "string", "enum": ["normal", "rain", "heat", "cold"]},
        },
        "required": ["minutes", "purpose", "destination", "accessible", "companions", "weather"],
    }
    instruction = """You convert a Korean visitor request into route conditions for Euljiro underground mall.\n
Return JSON only, following the supplied schema. Choose only 10, 30, 60, or 90 minutes.\n
purpose meanings: look=quick discovery, history=history/photo, family=child/family, make=printing/making/repair, service=store service, rest=rest/cafe.\n
Never invent shop opening hours, prices, route times, or a location. If not stated, choose 30 minutes, look, null destination, false accessibility, alone, normal weather."""
    body = {
        "model": os.getenv("OPENAI_ROUTE_MODEL", "gpt-5-mini"),
        "instructions": instruction,
        "input": text,
        "text": {"format": {"type": "json_schema", "name": "route_conditions", "strict": True, "schema": schema}},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed: {error.code} {message[:240]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"OpenAI network error: {error.reason}") from error

    output_text = payload.get("output_text")
    if not output_text:
        raise RuntimeError("OpenAI returned no structured output")
    return normalize_intent(json.loads(output_text), gate_token=gate_token)


def interpret_route_request(text: str, *, gate_token: str | None = None) -> dict[str, Any]:
    """Use OpenAI when configured; retain a transparent offline demo fallback."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text is required")
    try:
        return {"intent": _openai_intent(text.strip(), gate_token), "engine": "openai"}
    except RuntimeError as error:
        return {
            "intent": rule_based_intent(text.strip(), gate_token=gate_token),
            "engine": "rule_fallback",
            "notice": "OpenAI API key or network is unavailable; used the local demo parser.",
            "openai_error": str(error),
        }
