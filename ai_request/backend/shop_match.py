"""추천점포 매칭 — 확정된 주문 슬롯을 을지로 점포 태그와 규칙 매칭.

제작요청서(3번 화면)의 '추천 점포 N곳'을 만든다. LLM 이 아니라 순수 규칙이라
비용 0·수십 ms 이고 결과가 결정적(재현 가능)이다 — 가격/납기 확정이 아니라
'어느 점포로 요청을 보낼지'만 고른다(상인 승인은 여전히 사람이 한다).

매칭 점수 = 품목 태그 일치(주) + 마감/가공 태그 일치(보조).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_SHOPS = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "shops.json").read_text("utf-8")
)["shops"]

# 품목 동의어 → 표준 태그. handles 매칭 전에 입력 item 을 정규화한다.
_ITEM_SYNONYMS = {
    "패치": "자수패치", "와펜": "자수패치", "네임택": "네임택",
    "티셔츠": "유니폼", "단체복": "유니폼",
    "책": "책자", "소책자": "책자", "책자": "책자", "룩북": "룩북", "카탈로그": "카탈로그",
    "전단": "전단지", "리플렛": "전단지", "리플릿": "전단지",
    "라벨": "라벨", "라벨지": "라벨",
    "배너": "배너", "현수막": "현수막", "플래카드": "현수막",
    "명패": "명패", "스탬프": "스탬프", "도장": "도장",
}


def _norm(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def _canonical_item(item: str | None) -> str:
    n = _norm(item)
    for key, tag in _ITEM_SYNONYMS.items():
        if key in n:
            return tag
    return n


def _score(shop: dict, item_tag: str, finish: str) -> tuple[int, list[str]]:
    """점포 하나의 매칭 점수와 매칭 근거(사람이 읽는 이유)를 계산."""
    score, reasons = 0, []
    if item_tag:
        for h in shop["handles"]:
            hn = _norm(h)
            if hn and (hn in item_tag or item_tag in hn):
                score += 3
                reasons.append(f"{h} 취급")
                break
    if finish:
        fn = _norm(finish)
        for f in shop["finishes"]:
            ff = _norm(f)
            if ff and (ff in fn or fn in ff):
                score += 2
                reasons.append(f"{f} 가능")
                break
    return score, reasons


def match(order: dict, top_n: int = 2) -> list[dict]:
    """주문 → 추천 점포 상위 top_n. 매칭이 전혀 없으면 빈 리스트(상인 확인 필요).

    반환 각 항목: {id, name, category, location, hours, note, reason}
    """
    item_tag = _canonical_item(order.get("item"))
    finish = order.get("finish") or ""

    scored = []
    for shop in _SHOPS:
        s, reasons = _score(shop, item_tag, finish)
        if s > 0:
            scored.append((s, shop, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, shop, reasons in scored[:top_n]:
        out.append({
            "id": shop["id"],
            "name": shop["name"],
            "category": shop["category"],
            "location": shop["location"],
            "hours": shop["hours"],
            "note": shop["note"],
            "reason": " · ".join(reasons) if reasons else shop["category"],
        })
    return out
