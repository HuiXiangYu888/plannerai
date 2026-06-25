from typing import Any
from app.mcp.tools._utils import DURATION_RE, parse_duration_match, parse_number

_PLAN_HINTS = ("计划", "持续", "坚持", "周期", "为期", "总共", "内完成", "安排")
_REPEAT_HINTS = ("每天", "每日", "每周", "每晚", "每个")


def _score_candidate(text: str, start: int, end: int, normalized_unit: str) -> int:
    window = text[max(0, start - 8): min(len(text), end + 8)]
    score = 3 if normalized_unit in ("day", "week", "month") else 1

    if any(hint in window for hint in _PLAN_HINTS):
        score += 2
    if any(hint in window for hint in _REPEAT_HINTS):
        score -= 2
    return score


def extract_plan_duration(text: str) -> dict[str, Any]:
    """Extract likely plan duration from natural language text.

    Returns a dict with a best candidate and all candidates for debugging.
    """
    if not text or not text.strip():
        return {"found": False, "candidate": None, "candidates": []}

    candidates: list[dict[str, Any]] = []
    for m in DURATION_RE.finditer(text):
        try:
            parsed = parse_duration_match(m)
        except (ValueError, KeyError, Exception):
            continue
        if parsed["value"] <= 0:
            continue
        parsed["score"] = _score_candidate(text, m.start(), m.end(), parsed["unit"])
        candidates.append(parsed)

    if not candidates:
        return {"found": False, "candidate": None, "candidates": []}

    best = sorted(candidates, key=lambda x: (x["score"], x["total_minutes"], -x["start"]), reverse=True)[0]
    return {"found": True, "candidate": best, "candidates": candidates}
