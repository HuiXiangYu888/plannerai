import json
import re
from typing import Any
from app.mcp.tools import (
    calculate_time_blocks,
    check_plan_feasibility,
    extract_plan_duration,
    parse_time_availability,
    resolve_study_minutes,
)

# 匹配所有时间/数字相关的模式（用于从标题中精准剔除时间信息，而非整个子句）
_TIME_STRIP_RE = re.compile(
    r"(?:"
    r"每[天日周晚](?:早上|上午|中午|下午|晚上)?|"
    r"[早上午中下傍晚深夜]+\d{0,2}[点时]?\s*(?:到|至|-)\s*\d{0,2}[点时]?|"
    r"(?:\d+(?:\.\d+)?|半|[零〇一二两三四五六七八九十百千万半]+)\s*(?:个)?\s*(?:分钟|分|小时|时|天|日|周|星期|礼拜|月|个月)半?|\s"
    r")",
    re.IGNORECASE,
)

# 时间子句标记词：包含这些词则该子句大概率是时间/时长描述
_TIME_CLAUSE_MARKERS_RE = re.compile(
    r"每[天日周晚早晨]|坚持|持续|为期|"
    r"(?:\d+(?:\.\d+)?|[零一二两三四五六七八九十百千半]+)\s*(?:个)?\s*"
    r"(?:分钟|分|小时|时|天|日|周|星期|礼拜|月|个月)半?",
    re.IGNORECASE,
)

def _is_time_only_clause(clause: str) -> bool:
    """判断子句是否是纯时间/时长描述（无学习目标关键词）。"""
    if not _TIME_CLAUSE_MARKERS_RE.search(clause):
        return False
    # 去掉时间词和辅助动词后，剩余有效内容过少则认为是纯时间子句
    stripped = _TIME_STRIP_RE.sub("", clause).strip()
    stripped = re.sub(r"[坚持续学习规划]+", "", stripped).strip(" ，,。；;、")
    return len(stripped) < 2

_COMMON_GOAL_PREFIXES = (
    "帮我",
    "请帮我",
    "给我",
    "请给我",
    "生成",
    "做一个",
    "安排一个",
    "安排",
    "制定",
    "设计",
)

def _clean_goal_summary(text: str, duration_info: dict[str, Any], availability_info: dict[str, Any]) -> str:
    """从用户原始输入中提取目标主题，精准剔除时间/时长信息，保留学科/目标关键词。"""
    summary = text.strip()

    # 1. 精准移除 duration 匹配到的时间片段（只移除正则匹配的数字+单位，不扩大范围）
    if duration_info.get("found") and duration_info.get("candidate", {}).get("matched_text"):
        summary = summary.replace(duration_info["candidate"]["matched_text"], "")

    # 2. 对 availability blocks，只用全局时间正则剔除时间模式
    summary = _TIME_STRIP_RE.sub("", summary)

    # 3. 循环移除常见的无意义前缀
    prefixes = (
        "帮我", "请帮我", "给我", "请给我", "请", "生成", "做一个", "安排一个",
        "安排", "制定", "制定一个", "设计", "设计一个", "我想", "我要", "一个", "一份", "这个", "该",
        "这是", "是一个", "这是一份", "关于", "针对", "进行", "开展", "做个", "制作", "新建", "创建"
    )

    changed = True
    while changed:
        changed = False
        summary = summary.strip(" ，,。；;、？?！!\n\r的")
        for p in prefixes:
            if summary.startswith(p):
                summary = summary[len(p):]
                changed = True
                break

    # 4. 循环移除常见的无意义后缀（注意：'学习' 不再作为后缀，避免删掉 '自学' 之类的词）
    suffixes = (
        "学习计划", "复习计划", "备考计划", "训练计划", "计划", "安排", "课表", "日程", 
        "时间表", "安排表", "方案", "规划", "为期", "持续", "时长", "时间", "周期", "坚持"
    )
    changed = True
    while changed:
        changed = False
        summary = summary.strip(" ，,。；;、？?！!\n\r的")
        for s in suffixes:
            if summary.endswith(s):
                summary = summary[:-len(s)]
                changed = True
                break

    summary = summary.strip(" ，,。；;、？?！!\n\r的")
    return summary or "学习"

def _build_phases(horizon_days: int, goal_summary: str) -> list[dict[str, Any]]:
    if horizon_days <= 1:
        return [
            {
                "phase": "当日执行",
                "range": "第1天",
                "focus": f"围绕{goal_summary}完成输入整理、核心学习和当日复盘",
            }
        ]

    phase_specs = [
        ("第1阶段", 0.2, "摸底和框架搭建"),
        ("第2阶段", 0.5, "主线学习和专项突破"),
        ("第3阶段", 0.3, "巩固练习和复盘冲刺"),
    ]

    phases: list[dict[str, Any]] = []
    current_start = 1
    remaining_days = horizon_days

    for index, (name, ratio, focus) in enumerate(phase_specs):
        if index == len(phase_specs) - 1:
            phase_days = remaining_days
        else:
            phase_days = max(1, int(round(horizon_days * ratio)))
            max_allowed = remaining_days - (len(phase_specs) - index - 1)
            phase_days = min(phase_days, max_allowed)

        phase_end = current_start + phase_days - 1
        phases.append(
            {
                "phase": name,
                "range": f"第{current_start}-{phase_end}天",
                "focus": f"{goal_summary}：{focus}",
                "days": phase_days,
            }
        )

        current_start = phase_end + 1
        remaining_days -= phase_days

    return phases

def _build_slot_templates(availability_info: dict[str, Any]) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for block in availability_info.get("blocks", []):
        duration_minutes = block.get("duration_minutes")
        if not duration_minutes:
            continue

        focus_minutes = 50 if duration_minutes >= 90 else 25
        break_minutes = 10 if focus_minutes >= 50 else 5
        schedule = calculate_time_blocks(
            task_minutes=int(duration_minutes),
            availability=[block],
            focus_minutes=focus_minutes,
            break_minutes=break_minutes,
        )

        templates.append(
            {
                "source": block.get("matched_text"),
                "recurrence": block.get("recurrence"),
                "days": block.get("days", []),
                "time_of_day": block.get("time_of_day"),
                "minutes_per_occurrence": duration_minutes,
                "template": schedule.get("schedule", []),
            }
        )

    return templates

def generate_study_plan(text: str) -> dict[str, Any]:
    raw_text = (text or "").strip()
    if not raw_text:
        return {
            "found": False,
            "status": "need_more_info",
            "plan_type": None,
            "title": None,
            "goal_summary": None,
            "horizon_days": None,
            "capacity": {"weekly_minutes": 0, "estimated_total_minutes": 0},
            "feasibility": None,
            "time_availability": {"found": False, "blocks": []},
            "duration_extraction": {"found": False, "candidate": None, "candidates": []},
            "slot_templates": [],
            "phases": [],
            "clarification_needed": ["学习目标", "可用时间"],
        }

    duration_info = extract_plan_duration(raw_text)
    availability_info = parse_time_availability(raw_text)

    goal_summary = _clean_goal_summary(raw_text, duration_info, availability_info)
    horizon_days = None
    if duration_info.get("found"):
        horizon_days = max(1, int(round(duration_info["candidate"]["total_minutes"] / 1440)))

    plan_type = "single_day" if horizon_days == 1 else "short_term" if horizon_days else "incomplete"
    weekly_minutes = availability_info.get("total_weekly_minutes", 0)
    estimated_total_minutes = weekly_minutes * max(horizon_days or 1, 1) // 7 if weekly_minutes else 0

    feasibility = None
    if duration_info.get("found") and availability_info.get("found"):
        study_minutes = resolve_study_minutes(duration_info, availability_info)
        feasibility = check_plan_feasibility(study_minutes, availability_info)

    slot_templates = _build_slot_templates(availability_info) if availability_info.get("found") else []
    phases = _build_phases(horizon_days, goal_summary) if horizon_days else []

    clarification_needed: list[str] = []
    if not duration_info.get("found"):
        clarification_needed.append("学习周期")
    if not availability_info.get("found"):
        clarification_needed.append("可用时间")

    status = "ok"
    if clarification_needed:
        status = "need_more_info"
    elif feasibility and feasibility.get("status") in {"warning", "fail"}:
        status = "warning"

    return {
        "found": True,
        "status": status,
        "plan_type": plan_type,
        "title": f"{goal_summary}学习计划",
        "goal_summary": goal_summary,
        "horizon_days": horizon_days,
        "capacity": {
            "weekly_minutes": weekly_minutes,
            "estimated_total_minutes": estimated_total_minutes,
        },
        "feasibility": feasibility,
        "duration_extraction": duration_info,
        "time_availability": availability_info,
        "slot_templates": slot_templates,
        "phases": phases,
        "clarification_needed": clarification_needed,
        "suggested_followup": (
            "请补充学习目标和可用时间。"
            if clarification_needed
            else "如果要调整计划，可以修改周期、可用时长或优先级。"
        ),
    }

def plan_summary_text(plan: dict[str, Any]) -> str:
    if not plan.get("found"):
        return ""

    summary = {
        "title": plan.get("title"),
        "plan_type": plan.get("plan_type"),
        "horizon_days": plan.get("horizon_days"),
        "goal_summary": plan.get("goal_summary"),
        "clarification_needed": plan.get("clarification_needed", []),
        "phases": plan.get("phases", []),
    }
    return json.dumps(summary, ensure_ascii=False)
