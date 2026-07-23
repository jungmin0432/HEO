"""Runs the pre-registered scenarios in VALIDATION_DESIGN_ai_course.md against
each candidate model and dumps raw results to JSON for scoring.

Success criteria and scenarios were committed BEFORE this script ran.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

for line in open(Path(__file__).parent / ".env", encoding="utf-8"):
    if "=" in line:
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

import ai_course_designer as acd

MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3.6-27b"]
NOW = "2026-07-22T14:00:00+09:00"

SCENARIOS = [
    dict(gate_token="E4-02", minutes=60, purpose="rest", destination=None, accessible=False,
         text="쉬면서 커피도 마시고 싶고, 유모차라 계단은 피하고 싶어요"),
    dict(gate_token="E1-01", minutes=10, purpose="look", destination=None, accessible=False,
         text="아이랑 같이 왔는데 잠깐 볼만한 거 있을까요"),
    dict(gate_token="E4-01", minutes=30, purpose="make", destination=None, accessible=False,
         text="명함이랑 포스터 급하게 뽑아야 하는데 시간이 별로 없어요"),
    dict(gate_token="E3-01", minutes=90, purpose="memory", destination="ddp", accessible=False,
         text="옛날 사진 보고 싶고 DDP 쪽으로 넘어갈 거예요"),
    dict(gate_token="E3-02", minutes=30, purpose="look", destination=None, accessible=False,
         text="I have 30 minutes, want to see some art and grab a coffee"),
    dict(gate_token="E1-01", minutes=60, purpose="look", destination=None, accessible=False,
         text="그냥 아무거나 구경하고 싶어요"),
    dict(gate_token="E4-02", minutes=10, purpose="look", destination=None, accessible=False,
         text="빨리 둘러보고 싶은데 뭔가 기억에 남는 것도 보고 싶어요"),
    dict(gate_token="DDP-01", minutes=60, purpose="rest", destination=None, accessible=True,
         text="휠체어라서 엘리베이터로만 이동 가능해요, 쉬었다 갈 곳 필요해요"),
    dict(gate_token="E3-01", minutes=30, purpose="memory", destination=None, accessible=False,
         text="사진 인화하고 카메라 상담도 받고 싶어요"),
    dict(gate_token="E4-01", minutes=90, purpose="make", destination=None, accessible=False,
         text="제작 상담도 받고 쉬기도 하고 구경도 하고 싶어요, 다 하고 싶어요"),
    dict(gate_token="E1-01", minutes=30, purpose="look", destination="hipjiro", accessible=False,
         text="힙지로 쪽으로 갈 건데 가는 길에 뭐 좀 보고 싶어요"),
    dict(gate_token="E4-02", minutes=10, purpose="rest", destination=None, accessible=False,
         text="그냥 커피만 한 잔 하고 싶어요"),
]


def run():
    results = []
    for model in MODELS:
        for i, scenario in enumerate(SCENARIOS):
            t0 = time.perf_counter()
            try:
                out = acd.design_course(now_value=NOW, model=model, **scenario)
                elapsed = time.perf_counter() - t0
                route = out.get("route") or {}
                validator = route.get("validator") or out.get("validator") or {}
                results.append({
                    "model": model,
                    "scenario_index": i,
                    "text": scenario["text"],
                    "engine": out.get("engine"),
                    "reason": out.get("engine_reason"),
                    "stops": [
                        {"title": s["title"], "verified": s.get("location_verified")}
                        for s in route.get("stops", [])
                    ],
                    "walking_distance_m": route.get("walking_distance_m"),
                    "dropped_hallucinated": validator.get("dropped_hallucinated", []),
                    "dropped_over_budget": validator.get("dropped_over_budget", []),
                    "elapsed_sec": round(elapsed, 3),
                    "llm_usage": out.get("llm_usage", {}),
                    "error": None,
                })
            except Exception as e:
                elapsed = time.perf_counter() - t0
                results.append({
                    "model": model, "scenario_index": i, "text": scenario["text"],
                    "engine": "error", "reason": None, "stops": [],
                    "dropped_hallucinated": [], "dropped_over_budget": [],
                    "elapsed_sec": round(elapsed, 3), "llm_usage": {}, "error": str(e),
                })
            print(f"[{model}] scenario {i+1}/{len(SCENARIOS)}: engine={results[-1]['engine']} stops={len(results[-1]['stops'])}")
            time.sleep(3.5)  # stay well under free-tier rate limits

    out_path = Path(__file__).parent / "ai_course_eval_results_v2.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved to", out_path)


if __name__ == "__main__":
    run()
