import json
from typing import Literal

import gradio as gr
from fastapi import FastAPI, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents import generate_study_plan
from app.gradio_app import build_demo
from app.llm import get_chat_model
from app.mcp.tools import (
    calculate_time_blocks,
    check_plan_feasibility,
    extract_plan_duration,
    parse_time_availability,
    resolve_study_minutes,
)


app = FastAPI(title="PlannerAI", version="0.1.0")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="用户当前输入")
    history: list[ChatMessage] = Field(default_factory=list, description="可选的上下文历史")
    system_prompt: str | None = Field(default=None, description="可选的系统提示词")


class DurationExtractRequest(BaseModel):
    text: str = Field(min_length=1, description="用户输入原文")


class TimeAvailabilityRequest(BaseModel):
    text: str = Field(min_length=1, description="用户输入的可用时间描述")


class CalculateTimeBlocksRequest(BaseModel):
    task_minutes: int = Field(gt=0, description="任务总时长，单位分钟")
    availability_text: str = Field(min_length=1, description="用户输入的可用时间描述")
    focus_minutes: int | None = Field(default=None, gt=0, description="每个专注切片分钟数")
    break_minutes: int | None = Field(default=None, ge=0, description="切片间休息分钟数")


class CheckFeasibilityRequest(BaseModel):
    task_minutes: int = Field(gt=0, description="任务总时长，单位分钟")
    availability_text: str = Field(min_length=1, description="用户输入的可用时间描述")
    daily_limit_minutes: int = Field(default=480, gt=0, description="单日建议上限，单位分钟")
    weekly_limit_minutes: int = Field(default=3600, gt=0, description="每周建议上限，单位分钟")
    max_contiguous_minutes: int = Field(default=180, gt=0, description="单次连续专注上限，单位分钟")


class StudyPlanRequest(BaseModel):
    text: str = Field(min_length=1, description="用户输入原文")


@app.get("/api")
async def root():
    return {"message": "PlannerAI API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/mcp/extract-duration")
async def mcp_extract_duration(request: DurationExtractRequest):
    return extract_plan_duration(request.text)


@app.post("/mcp/parse-time-availability")
async def mcp_parse_time_availability(request: TimeAvailabilityRequest):
    return parse_time_availability(request.text)


@app.post("/mcp/calculate-time-blocks")
async def mcp_calculate_time_blocks(request: CalculateTimeBlocksRequest):
    return calculate_time_blocks(
        task_minutes=request.task_minutes,
        availability=request.availability_text,
        focus_minutes=request.focus_minutes,
        break_minutes=request.break_minutes,
    )


@app.post("/mcp/check-plan-feasibility")
async def mcp_check_plan_feasibility(request: CheckFeasibilityRequest):
    return check_plan_feasibility(
        task_minutes=request.task_minutes,
        availability=request.availability_text,
        daily_limit_minutes=request.daily_limit_minutes,
        weekly_limit_minutes=request.weekly_limit_minutes,
        max_contiguous_minutes=request.max_contiguous_minutes,
    )


@app.post("/mcp/generate-study-plan")
async def mcp_generate_study_plan(request: StudyPlanRequest):
    return generate_study_plan(request.text)


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        study_plan = generate_study_plan(request.message)
        # 从 study_plan 响应中提取已计算的信息，避免重复调用
        duration_info = study_plan.get("duration_extraction",
            {"found": False, "candidate": None, "candidates": []})
        availability_info = study_plan.get("time_availability",
            {"found": False, "blocks": [], "candidate": None, "total_weekly_minutes": 0})
    except Exception:  # noqa: BLE001
        study_plan = {"found": False, "status": "need_more_info",
                      "duration_extraction": {"found": False, "candidate": None, "candidates": []},
                      "time_availability": {"found": False, "blocks": [], "candidate": None, "total_weekly_minutes": 0}}
        duration_info = study_plan.get("duration_extraction",
            {"found": False, "candidate": None, "candidates": []})
        availability_info = study_plan.get("time_availability",
            {"found": False, "blocks": [], "candidate": None, "total_weekly_minutes": 0})

    task_minutes = resolve_study_minutes(duration_info, availability_info)
    time_blocks_info = None
    feasibility_info = None

    if task_minutes is not None and availability_info["found"]:
        time_blocks_info = calculate_time_blocks(task_minutes, availability_info)
        feasibility_info = check_plan_feasibility(task_minutes, availability_info)
    try:
        model = get_chat_model()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    messages = []
    if request.system_prompt:
        messages.append(SystemMessage(content=request.system_prompt))
    if duration_info["found"]:
        candidate = duration_info["candidate"]
        messages.append(
            SystemMessage(
                content=(
                    "你可以参考以下已解析出的计划持续时间信息："
                    f"{candidate['value']}{candidate['unit']}"
                    f"（约 {candidate['total_minutes']} 分钟）。"
                )
            )
        )
    if availability_info["found"]:
        messages.append(
            SystemMessage(
                content=(
                    "你可以参考以下已解析出的可用时间信息："
                    f"{availability_info['candidate'].get('matched_text')}"
                )
            )
        )
    if feasibility_info and feasibility_info["status"] != "ok":
        messages.append(
            SystemMessage(
                content=(
                    "计划校验提示："
                    f"{'; '.join(item['message'] for item in feasibility_info['reasons'])}"
                )
            )
        )
    if study_plan["found"]:
        messages.append(SystemMessage(content=f"学习计划草案：{json.dumps(study_plan, ensure_ascii=False)}"))

    for item in request.history:
        if item.role == "system":
            messages.append(SystemMessage(content=item.content))
        elif item.role == "assistant":
            messages.append(AIMessage(content=item.content))
        else:
            messages.append(HumanMessage(content=item.content))

    messages.append(HumanMessage(content=request.message))

    try:
        response = model.invoke(messages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc

    return {
        "reply": response.content,
        "model": getattr(model, "model_name", None),
        "duration_extraction": duration_info,
        "time_availability": availability_info,
        "time_blocks": time_blocks_info,
        "plan_feasibility": feasibility_info,
        "study_plan": study_plan,
    }


app = gr.mount_gradio_app(app, build_demo(), path="/")
