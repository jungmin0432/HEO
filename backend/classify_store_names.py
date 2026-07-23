"""One-time batch classification: guess a short category for each of the 161
real store names from their name alone (no location data used). Cached to
store_categories.json so the live endpoint never needs to call an LLM for
this. Every guess is clearly labeled "(추정)" wherever it's shown -- this is
a name-based guess, not a verified business category.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

for line in open(Path(__file__).parent / ".env", encoding="utf-8"):
    if "=" in line:
        k, v = line.strip().split("=", 1)
        os.environ[k] = v

import ai_course_designer as acd

names = acd.REAL_STORE_NAMES
system = (
    "For each Korean shop name in the list, guess its most likely business "
    "category from the name alone, in 2-4 Korean characters (e.g. 빵집, "
    "카페, 신발, 스포츠용품, 인쇄소, 의류, 미용실, 부동산, 식당, 액세서리). "
    "If genuinely unclear, use 잡화. Return ONLY a JSON object mapping each "
    "exact input name to its category string, nothing else."
)
user = json.dumps(names, ensure_ascii=False)

raw = acd._call_groq(system, user, model="llama-3.3-70b-versatile")
raw.pop("_usage", None)

out_path = Path(__file__).parent / "store_categories.json"
out_path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved", len(raw), "entries to", out_path)
