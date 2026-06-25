"""Utility functions shared across MCP tools."""
from __future__ import annotations

import re
from typing import Any


_CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def parse_chinese_int(text: str) -> int:
    if text in _CHINESE_DIGITS:
        return _CHINESE_DIGITS[text]
    total = 0
    section = 0
    number = 0
    for ch in text:
        if ch in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[ch]
        elif ch in _CHINESE_UNITS:
            unit = _CHINESE_UNITS[ch]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
                number = 0
            else:
                if number == 0:
                    number = 1
                section += number * unit
                number = 0
    return total + section + number


def parse_number(raw: str) -> float:
    token = raw.strip()
    if token == "半":
        return 0.5
    try:
        return float(token)
    except ValueError:
        pass
    if token.endswith("半") and len(token) > 1:
        return parse_number(token[:-1]) + 0.5
    return float(parse_chinese_int(token))


DURATION_RE = re.compile(
    r"(?P<number>\d+(?:\.\d+)?|半|[零〇一二两三四五六七八九十百千万半]+)\s*(?:个)?\s*"
    r"(?P<unit>分钟|分|min|mins?|小时|时|h|hr|hrs?|天|日|周|星期|礼拜|月|个月)"
    r"(?P<suffix_half>半)?",
    re.IGNORECASE,
)

_UNIT_META = {
    "分": ("minute", 1),
    "分钟": ("minute", 1),
    "min": ("minute", 1),
    "mins": ("minute", 1),
    "小时": ("hour", 60),
    "时": ("hour", 60),
    "h": ("hour", 60),
    "hr": ("hour", 60),
    "hrs": ("hour", 60),
    "天": ("day", 1440),
    "日": ("day", 1440),
    "周": ("week", 10080),
    "星期": ("week", 10080),
    "礼拜": ("week", 10080),
    "月": ("month", 43200),
    "个月": ("month", 43200),
}

_FACTOR_MAP = {k: v for k in _UNIT_META for v in [_UNIT_META[k][1]]}


def unit_minute_factor(unit: str) -> int:
    return _FACTOR_MAP[unit.lower()]


def parse_duration_match(match: re.Match) -> dict[str, Any]:
    raw_number = match.group("number")
    raw_unit = match.group("unit").lower()
    suffix_half = match.group("suffix_half")
    value = parse_number(raw_number)
    if suffix_half:
        value += 0.5
    normalized_unit, minute_factor = _UNIT_META[raw_unit]
    total_minutes = int(round(value * minute_factor))
    return {
        "matched_text": match.group(0),
        "value": value,
        "unit": normalized_unit,
        "total_minutes": total_minutes,
        "start": match.start(),
        "end": match.end(),
    }
