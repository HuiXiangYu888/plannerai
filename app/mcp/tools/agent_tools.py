"""
LangChain Tool 封装层
将现有的纯函数工具包装为 LLM 可调用的 LangChain Tool。
Agent 通过这些 Tool 与工具逻辑交互，而不是直接调用函数。
"""

import json
from typing import Any

from langchain_core.tools import tool

from app.mcp.tools.duration_extractor import extract_plan_duration
from app.mcp.tools.planning_tools import (
    calculate_time_blocks,
    check_plan_feasibility,
    parse_time_availability,
    resolve_study_minutes,
)
from app.agents.study_planner import generate_study_plan


@tool
def tool_extract_duration(user_input: str) -> str:
    """从用户的自然语言输入中提取学习计划的时间周期（如"三个月"、"半年"）。

    当用户提到计划周期、学习时长时调用此工具。

    Args:
        user_input: 用户的原始输入文本。

    Returns:
        JSON 字符串，包含 candidate.total_minutes（总分钟数）、candidate.unit（单位）等。
        如果未识别到时间信息，found 为 false。
    """
    result = extract_plan_duration(user_input)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def tool_parse_availability(user_input: str) -> str:
    """从用户的自然语言输入中解析每周可用的学习时间（如"每天2小时"、"周末下午3小时"）。

    当需要了解用户的可用时间、学习时段时调用此工具。

    Args:
        user_input: 用户的原始输入文本。

    Returns:
        JSON 字符串，包含 blocks（时间段列表）、total_weekly_minutes（每周总分钟数）等。
        如果未识别到可用时间，found 为 false。
    """
    result = parse_time_availability(user_input)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def tool_check_feasibility(task_minutes: int, availability_json: str) -> str:
    """检查给定任务时长在用户可用时间内是否可行。

    Args:
        task_minutes: 任务所需的总学习时长（分钟）。
        availability_json: 可用时间信息的 JSON 字符串（来自 tool_parse_availability 的结果）。

    Returns:
        JSON 字符串，包含 status（ok/warning/fail）、reasons（原因列表）、recommendations（建议）。
    """
    try:
        availability = json.loads(availability_json)
    except (json.JSONDecodeError, TypeError):
        availability = {"blocks": [], "total_weekly_minutes": 0}
    result = check_plan_feasibility(task_minutes, availability)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def tool_calculate_time_blocks(
    task_minutes: int, availability_json: str
) -> str:
    """根据任务时长和可用时间，计算具体的学习时间切片（番茄钟安排）。

    Args:
        task_minutes: 任务所需的总学习时长（分钟）。
        availability_json: 可用时间信息的 JSON 字符串。

    Returns:
        JSON 字符串，包含 schedule（时间切片列表）、strategy（使用的策略如 pomodoro_50_10）。
    """
    try:
        availability = json.loads(availability_json)
    except (json.JSONDecodeError, TypeError):
        availability = {"blocks": [], "total_weekly_minutes": 0}
    result = calculate_time_blocks(task_minutes, availability)
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def tool_generate_plan(user_input: str, suggested_title: str | None = None) -> str:
    """根据用户的自然语言输入和提炼的主题生成完整的学习计划。

    这是最终生成计划的工具，应在收集到足够信息后调用。

    Args:
        user_input: 用户的完整学习需求描述（如"制定一个三个月的高考数学复习计划，每天学习2小时"）。
        suggested_title: 可选。大模型提炼的 4-8 字的高拟真、极简短计划主题名称（例如：“雅思备考”、“考研冲刺”、“Python编程”），请绝对不要包含“计划”或“复习计划”等后缀。

    Returns:
        JSON 字符串，包含 title（计划标题）、phases（阶段安排）、goal_summary（目标摘要）、
        status（ok/warning/need_more_info）等完整计划结构。
    """
    result = generate_study_plan(user_input, suggested_title=suggested_title)
    return json.dumps(result, ensure_ascii=False, default=str)


ALL_TOOLS = [
    tool_extract_duration,
    tool_parse_availability,
    tool_check_feasibility,
    tool_calculate_time_blocks,
    tool_generate_plan,
]
