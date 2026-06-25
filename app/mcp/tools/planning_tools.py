import re
from typing import Any
from app.mcp.tools._utils import DURATION_RE, parse_number, parse_duration_match
from app.mcp.tools._utils import parse_chinese_int  # noqa: F401

_TIME_RANGE_RE = re.compile(
    r"(?P<start>\d{1,2})(?::(?P<start_min>\d{1,2}))?\s*(?:点|时)?\s*(?:到|至|-|—|~)\s*(?P<end>\d{1,2})(?::(?P<end_min>\d{1,2}))?\s*(?:点|时)?"
)

_DAY_RANGE_RE = re.compile(r"(?:周|星期)(?P<start>[一二三四五六日天])(?:到|至|-|—|~)(?:周|星期)(?P<end>[一二三四五六日天])")

DAY_TOKEN_MAP = {
    "周一": "mon",
    "星期一": "mon",
    "周二": "tue",
    "星期二": "tue",
    "周三": "wed",
    "星期三": "wed",
    "周四": "thu",
    "星期四": "thu",
    "周五": "fri",
    "星期五": "fri",
    "周六": "sat",
    "星期六": "sat",
    "周日": "sun",
    "周天": "sun",
    "星期日": "sun",
    "星期天": "sun",
}

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DAY_WORDS = {
    "mon": ("周一", "星期一"),
    "tue": ("周二", "星期二"),
    "wed": ("周三", "星期三"),
    "thu": ("周四", "星期四"),
    "fri": ("周五", "星期五"),
    "sat": ("周六", "星期六"),
    "sun": ("周日", "周天", "星期日", "星期天"),
}

TIME_OF_DAY_MAP = {
    "morning": ("早上", "上午", "清晨", "晨间"),
    "noon": ("中午",),
    "afternoon": ("下午", "午后"),
    "evening": ("晚上", "傍晚", "夜晚", "夜里", "深夜"),
    "all_day": ("全天",),
}


def _split_clauses(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"[，,。；;、\n]+", text) if part.strip()]
    return parts or [text.strip()]


def _time_of_day(text: str) -> str | None:
    for label, hints in TIME_OF_DAY_MAP.items():
        if any(hint in text for hint in hints):
            return label
    return None


def _expand_day_range(start: str, end: str) -> list[str]:
    alias_to_day = {"一": "mon", "二": "tue", "三": "wed", "四": "thu", "五": "fri", "六": "sat", "日": "sun", "天": "sun"}
    start_day = alias_to_day.get(start)
    end_day = alias_to_day.get(end)
    if start_day is None or end_day is None:
        return []

    start_index = DAY_ORDER.index(start_day)
    end_index = DAY_ORDER.index(end_day)
    if start_index <= end_index:
        return DAY_ORDER[start_index : end_index + 1]
    return DAY_ORDER[start_index:] + DAY_ORDER[: end_index + 1]


def _extract_days(text: str) -> list[str]:
    day_set: set[str] = set()

    if any(keyword in text for keyword in ("周末", "周六日", "周六和周日", "周六、周日")):
        day_set.update({"sat", "sun"})

    if any(keyword in text for keyword in ("工作日", "平日")):
        day_set.update({"mon", "tue", "wed", "thu", "fri"})

    for match in _DAY_RANGE_RE.finditer(text):
        day_set.update(_expand_day_range(match.group("start"), match.group("end")))

    for token, day in DAY_TOKEN_MAP.items():
        if token in text:
            day_set.add(day)

    ordered_days = [day for day in DAY_ORDER if day in day_set]
    return ordered_days


def _duration_minutes_from_clause(text: str) -> tuple[int | None, str | None]:
    time_range = _TIME_RANGE_RE.search(text)
    if time_range:
        start_hour = int(time_range.group("start"))
        start_minute = int(time_range.group("start_min") or 0)
        end_hour = int(time_range.group("end"))
        end_minute = int(time_range.group("end_min") or 0)
        start_total = start_hour * 60 + start_minute
        end_total = end_hour * 60 + end_minute
        if end_total <= start_total:
            end_total += 24 * 60
        return end_total - start_total, "explicit_range"

    if "全天" in text:
        return 24 * 60, "all_day"

    if "半天" in text:
        return 12 * 60, "half_day"

    match = DURATION_RE.search(text)
    if not match:
        return None, None

    parsed = parse_duration_match(match)
    value = parsed["value"]

    unit = match.group("unit").lower()
    factor_map = {"分": 1, "分钟": 1, "min": 1, "mins": 1, "小时": 60, "时": 60, "h": 60, "hr": 60, "hrs": 60, "天": 1440, "日": 1440, "周": 10080, "星期": 10080, "礼拜": 10080, "月": 43200, "个月": 43200}
    factor = factor_map.get(unit, 60)
    return int(round(value * factor)), unit


def _recurrence_from_clause(text: str, days: list[str]) -> tuple[str, int]:
    if any(keyword in text for keyword in ("每天", "每日", "每晚", "每晨", "每个工作日", "每天晚上", "每天早上")):
        return "daily", 7
    if days:
        return "weekly", len(days)
    if any(keyword in text for keyword in ("每周", "每星期", "每礼拜")):
        return "weekly", 1
    return "once", 1


def _build_block(clause: str) -> dict[str, Any] | None:
    duration_minutes, duration_source = _duration_minutes_from_clause(clause)
    time_period = _time_of_day(clause)
    days = _extract_days(clause)
    recurrence, repeat_count = _recurrence_from_clause(clause, days)

    if duration_minutes is None and time_period is None and not days and recurrence == "once":
        return None

    block: dict[str, Any] = {
        "matched_text": clause,
        "recurrence": recurrence,
        "repeat_count": repeat_count,
        "days": days,
        "time_of_day": time_period,
        "duration_minutes": duration_minutes,
        "duration_source": duration_source,
        "weekly_minutes": duration_minutes * repeat_count if duration_minutes is not None else None,
        "needs_clarification": duration_minutes is None,
    }

    return block


def parse_time_availability(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        return {"found": False, "raw_text": text, "blocks": [], "candidate": None, "total_weekly_minutes": 0}

    blocks: list[dict[str, Any]] = []
    for clause in _split_clauses(text):
        block = _build_block(clause)
        if block is not None:
            blocks.append(block)

    if not blocks:
        return {"found": False, "raw_text": text, "blocks": [], "candidate": None, "total_weekly_minutes": 0}

    scored_blocks = []
    for block in blocks:
        score = 0
        if block["duration_minutes"] is not None:
            score += 3
        if block["recurrence"] == "daily":
            score += 2
        if block["recurrence"] == "weekly":
            score += 1
        if block["time_of_day"]:
            score += 1
        if block["days"]:
            score += len(block["days"])
        block["score"] = score
        scored_blocks.append(block)

    candidate = sorted(scored_blocks, key=lambda item: (item["score"], item["weekly_minutes"] or 0), reverse=True)[0]
    total_weekly_minutes = sum(block["weekly_minutes"] or 0 for block in blocks)

    return {
        "found": True,
        "raw_text": text,
        "blocks": blocks,
        "candidate": candidate,
        "total_weekly_minutes": total_weekly_minutes,
    }


def _availability_to_blocks(availability: Any) -> tuple[list[dict[str, Any]], int]:
    if isinstance(availability, str):
        parsed = parse_time_availability(availability)
        blocks = parsed["blocks"]
    elif isinstance(availability, dict):
        blocks = list(availability.get("blocks", []))
    elif isinstance(availability, list):
        blocks = list(availability)
    else:
        blocks = []

    slot_instances: list[dict[str, Any]] = []
    total_available = 0
    for block in blocks:
        duration_minutes = block.get("duration_minutes")
        if duration_minutes is None:
            continue

        repeat_count = int(block.get("repeat_count") or 1)
        repeat_count = max(repeat_count, 1)
        for occurrence_index in range(repeat_count):
            slot_instances.append(
                {
                    "source": block.get("matched_text") or block.get("source") or "unknown",
                    "occurrence_index": occurrence_index + 1,
                    "slot_minutes": int(duration_minutes),
                    "recurrence": block.get("recurrence", "once"),
                    "time_of_day": block.get("time_of_day"),
                    "days": block.get("days", []),
                }
            )
            total_available += int(duration_minutes)

    return slot_instances, total_available


def calculate_time_blocks(
    task_minutes: int,
    availability: Any,
    focus_minutes: int | None = None,
    break_minutes: int | None = None,
    min_slice_minutes: int = 25,
) -> dict[str, Any]:
    if task_minutes <= 0:
        return {
            "feasible": False,
            "status": "invalid",
            "task_minutes": task_minutes,
            "available_minutes": 0,
            "remaining_task_minutes": task_minutes,
            "schedule": [],
            "message": "task_minutes 必须大于 0",
        }

    slots, available_minutes = _availability_to_blocks(availability)

    if focus_minutes is None:
        focus_minutes = 50 if task_minutes >= 180 or available_minutes >= 240 else 25
    if break_minutes is None:
        break_minutes = 10 if focus_minutes >= 50 else 5

    focus_minutes = max(int(focus_minutes), 1)
    break_minutes = max(int(break_minutes), 0)
    min_slice_minutes = max(int(min_slice_minutes), 1)

    schedule: list[dict[str, Any]] = []
    remaining_task = task_minutes
    used_available = 0

    for slot in slots:
        if remaining_task <= 0:
            break

        slot_remaining = slot["slot_minutes"]
        slot_plan: list[dict[str, Any]] = []

        while remaining_task > 0 and slot_remaining > 0:
            work_minutes = min(focus_minutes, remaining_task, slot_remaining)
            if work_minutes < min_slice_minutes:
                work_minutes = min(remaining_task, slot_remaining)
            if work_minutes <= 0:
                break

            slot_plan.append({"type": "focus", "minutes": work_minutes})
            remaining_task -= work_minutes
            slot_remaining -= work_minutes
            used_available += work_minutes

            if remaining_task <= 0 or slot_remaining <= 0:
                break

            pause_minutes = min(break_minutes, slot_remaining)
            if pause_minutes <= 0:
                break

            slot_plan.append({"type": "break", "minutes": pause_minutes})
            slot_remaining -= pause_minutes
            used_available += pause_minutes

        schedule.append(
            {
                "source": slot["source"],
                "occurrence_index": slot["occurrence_index"],
                "slot_minutes": slot["slot_minutes"],
                "planned_minutes": sum(item["minutes"] for item in slot_plan),
                "items": slot_plan,
            }
        )

    return {
        "feasible": remaining_task == 0,
        "status": "ok" if remaining_task == 0 else "insufficient_time",
        "strategy": "pomodoro_50_10" if focus_minutes >= 50 else "pomodoro_25_5",
        "task_minutes": task_minutes,
        "available_minutes": available_minutes,
        "allocated_minutes": used_available,
        "remaining_task_minutes": remaining_task,
        "remaining_available_minutes": max(available_minutes - used_available, 0),
        "schedule": schedule,
    }


def check_plan_feasibility(
    task_minutes: int,
    availability: Any,
    daily_limit_minutes: int = 480,
    weekly_limit_minutes: int = 3600,
    max_contiguous_minutes: int = 180,
    horizon_days: int | None = None,
) -> dict[str, Any]:
    parsed_availability = availability if isinstance(availability, dict) and "blocks" in availability else parse_time_availability(availability) if isinstance(availability, str) else {"blocks": list(availability or [])}
    available_blocks, available_minutes = _availability_to_blocks(parsed_availability)

    reasons: list[dict[str, Any]] = []
    recommendations: list[str] = []

    if task_minutes <= 0:
        reasons.append({"code": "invalid_task_minutes", "message": "任务时长必须大于 0"})

    # available_minutes 是每周（或自然循环周期）的可用时间
    # 如果给定了计划天数（horizon_days），则计算整个周期的总可用时间
    if horizon_days is not None and horizon_days > 0:
        total_available_time = available_minutes / 7.0 * horizon_days
    else:
        total_available_time = available_minutes

    if total_available_time < task_minutes:
        reasons.append({"code": "insufficient_time", "message": "用户可用时长不足以覆盖任务总量"})
        recommendations.append("缩小目标范围，或者延长计划周期")

    # 1. 检查每周负荷：如果每周规划的总可用时长（即负荷上限）超过限制
    weekly_available = parsed_availability.get("total_weekly_minutes", 0) if isinstance(parsed_availability, dict) else available_minutes
    if weekly_available > weekly_limit_minutes:
        reasons.append({"code": "exceeds_weekly_human_limit", "message": f"每周规划的可用时间 ({weekly_available} 分钟) 超过每周建议上限 {weekly_limit_minutes} 分钟"})
        recommendations.append("减少每周规划的可用时间，避免学习负荷过大")

    # 2. 检查每日负荷：估算每日最高负荷
    daily_totals: dict[str, int] = {}
    for block in available_blocks:
        slot_mins = block.get("slot_minutes", 0)
        recurrence = block.get("recurrence")
        days = block.get("days") or []
        
        if recurrence == "daily":
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
                daily_totals[d] = daily_totals.get(d, 0) + slot_mins
        elif recurrence == "weekly" and days:
            for d in days:
                daily_totals[d] = daily_totals.get(d, 0) + slot_mins
        else:
            daily_totals["once"] = daily_totals.get("once", 0) + slot_mins

    max_daily_load = max(daily_totals.values(), default=0)
    
    # 如果没有指定周期性规律（比如单次任务），直接以单次任务总时长作为单日最高负荷
    if not daily_totals and task_minutes > daily_limit_minutes:
        max_daily_load = task_minutes

    if max_daily_load > daily_limit_minutes:
        reasons.append({"code": "exceeds_daily_human_limit", "message": f"单日规划的可用时间 ({max_daily_load} 分钟) 超过单日建议上限 {daily_limit_minutes} 分钟"})
        recommendations.append("拆成多个学习日，或者缩短单次可用时间")

    max_slot_minutes = max((block["slot_minutes"] for block in available_blocks), default=0)
    if max_slot_minutes > max_contiguous_minutes:
        reasons.append({"code": "long_contiguous_session", "message": f"单次可用时段达到 {max_slot_minutes} 分钟，建议插入休息"})
        recommendations.append("使用番茄钟切片，避免长时间连续专注")

    if not available_blocks:
        reasons.append({"code": "missing_availability", "message": "未识别到明确可用时间"})
        recommendations.append("补充每天/每周的可用时长")

    status = "ok"
    if reasons:
        status = "fail" if any(reason["code"] in {"invalid_task_minutes", "insufficient_time", "exceeds_weekly_human_limit", "exceeds_daily_human_limit"} for reason in reasons) else "warning"

    return {
        "feasible": status != "fail",
        "status": status,
        "task_minutes": task_minutes,
        "available_minutes": available_minutes,
        "limits": {
            "daily_limit_minutes": daily_limit_minutes,
            "weekly_limit_minutes": weekly_limit_minutes,
            "max_contiguous_minutes": max_contiguous_minutes,
        },
        "reasons": reasons,
        "recommendations": list(dict.fromkeys(recommendations)),
    }


def resolve_study_minutes(duration_info: dict[str, Any], availability_info: dict[str, Any]) -> int | None:
    """根据计划周期（如天/周/月）或物理学习时间，结合可用时间，解析出实际学习时间（单位：分钟）"""
    if not duration_info or not duration_info.get("found") or not duration_info.get("candidate"):
        return None

    cand = duration_info["candidate"]
    unit = cand.get("unit")
    total_mins = cand.get("total_minutes") or 0

    if unit in ("day", "week", "month"):
        # 这是周期单位，计算周期天数
        horizon_days = max(1, int(round(total_mins / 1440)))
        weekly_minutes = availability_info.get("total_weekly_minutes", 0) if availability_info else 0
        if weekly_minutes:
            return weekly_minutes * horizon_days // 7
        else:
            # 默认每日可用 120 分钟
            return horizon_days * 120
    else:
        # 物理学习时间（分/小时）直接返回
        return int(total_mins)
