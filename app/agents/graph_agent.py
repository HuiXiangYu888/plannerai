"""
LangGraph ReAct Agent 定义
使用 create_react_agent 构建智能学习计划 Agent。
LLM 自主决定调用哪些工具、何时追问、何时生成计划。

特性：
- 异步流式输出（astream_events 逐 token）
- 日志记录（工具调用、错误、耗时）
- 计划自动同步（从 tool_generate_plan 结果提取）
- 错误恢复（超时/异常降级）
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.llm import get_chat_model
from app.mcp.tools.agent_tools import ALL_TOOLS

# ────────────────────────────────────────────────────────────
# 日志配置
# ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("plannerai.agent")

# ────────────────────────────────────────────────────────────
# Agent 系统提示词（优化版：含 Few-shot + 明确工具顺序）
# ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
你是 PlannerAI 学习计划智能助手。你的核心目标是帮助用户制定科学、可执行的学习计划。

## 工具调用策略
按以下顺序使用工具，逐步收集信息：
1. **tool_extract_duration** → 提取学习周期（如"三个月"→90天）
2. **tool_parse_availability** → 提取可用时间（如"每天2小时"→每周840分钟）
3. **tool_check_feasibility** → 验证计划是否可行（可选，信息充足时调用）
4. **tool_generate_plan** → 生成最终计划 JSON

## 关键规则
- **信息不足时追问**：如果用户只说"我要学雅思"但没有说周期或可用时间，你应该追问：
  "好的！想了解一下：1) 你打算准备多长时间？2) 每天/每周能投入多少时间学习？"
- **每次最多调 2-3 个工具**，不要重复调用
- **不要直接输出 JSON**：用 Markdown 表格、列表呈现计划
- **局部更新**：如果已有计划，在已有基础上调整，不要全部重写。并且在调用 `tool_generate_plan` 时，`suggested_title` 必须保持原计划的主题名称不变（严禁改成“修改为4个月”等指令性文字）。
- **工具调用参数规范**：在调用 `tool_generate_plan` 时，必须提供两个参数：
  1. `user_input`：传入当前学习需求的完整描述。
  2. `suggested_title`：根据对话上下文，提炼一个高质量的完整计划名称（例如：“雅思备考计划”、“新手在家健身计划”）。注意：主题名严禁包含任何标点符号（如逗号、冒号等，绝对不能输出类似“考研计划，408”这样带标点的名称）。



## 回复格式示例
```markdown
## 📚 三个月雅思备考计划

### 🎯 目标概览
| 项目 | 详情 |
|------|------|
| 学习目标 | 雅思 7.0 |
| 备考周期 | 90 天 |
| 每日学习时长 | 2 小时 |

### 📅 阶段安排
| 阶段 | 时间 | 重点 |
|------|------|------|
| 第1阶段 | 第1-18天 | 基础摸底与框架搭建 |
| 第2阶段 | 第19-63天 | 专项突破与模考练习 |
| 第3阶段 | 第64-90天 | 冲刺复盘与考前调整 |
```

## 语气
友好、专业、简洁。像一位经验丰富的学习顾问。
"""

# ────────────────────────────────────────────────────────────
# Agent 构建
# ────────────────────────────────────────────────────────────
_agent = None
_agent_model = None


def get_agent_model():
    """获取支持流式输出的模型实例（Agent 专用）"""
    global _agent_model
    if _agent_model is None:
        _agent_model = get_chat_model(streaming=True)
    return _agent_model


def get_agent():
    """获取全局 Agent 实例（懒加载、单例）"""
    global _agent
    if _agent is None:
        model = get_agent_model()
        _agent = create_react_agent(
            model,
            ALL_TOOLS,
            checkpointer=MemorySaver(),
            prompt=SystemMessage(content=SYSTEM_PROMPT),
        )
        logger.info("Agent initialized with %d tools", len(ALL_TOOLS))
    return _agent


# ────────────────────────────────────────────────────────────
# 消息格式转换
# ────────────────────────────────────────────────────────────
def dict_messages_to_langchain(
    messages: list[dict[str, str]],
) -> list[BaseMessage]:
    """将前端存储的 dict 消息列表转为 LangChain 消息列表"""
    result: list[BaseMessage] = []
    for msg in messages or []:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "user":
            result.append(HumanMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
    return result


# ────────────────────────────────────────────────────────────
# 降级流式函数（astream_events 失败时使用）
# ────────────────────────────────────────────────────────────
async def _stream_values_fallback(
    agent,
    history: list[BaseMessage],
    config: dict,
) -> AsyncGenerator[dict[str, Any], None]:
    """降级方案：用 stream_mode=values 获取完整消息而非逐 token。
    
    使用独立的 thread_id 避免与 astream_events 的 checkpoint 冲突。
    """
    # 使用唯一 thread_id 避免 MemorySaver checkpoint 导致重放无输出
    fallback_config = {
        "configurable": {"thread_id": config["configurable"]["thread_id"] + "_fb_" + str(uuid.uuid4())[:6]}
    }
    prev_count = 0
    async for event in agent.astream(
        {"messages": history},
        config=fallback_config,
        stream_mode="values",
    ):
        messages = event.get("messages", [])
        new_msgs = messages[prev_count:]
        prev_count = len(messages)

        for msg in new_msgs:
            if isinstance(msg, AIMessage):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool_name": tc.get("name", "unknown"),
                            "tool_args": json.dumps(tc.get("args", {}), ensure_ascii=False),
                        }
                if msg.content and isinstance(msg.content, str):
                    yield {"type": "token", "text": msg.content}

            elif isinstance(msg, ToolMessage):
                yield {
                    "type": "tool_result",
                    "tool_name": msg.name or "unknown",
                    "tool_result": str(msg.content)[:500],
                }
                if msg.name == "tool_generate_plan":
                    try:
                        plan_data = json.loads(str(msg.content))
                        if plan_data.get("found"):
                            yield {"type": "plan_sync", "plan": plan_data}
                    except (json.JSONDecodeError, TypeError):
                        pass


# ────────────────────────────────────────────────────────────
# 异步流式运行 Agent（逐 token + 工具事件）
# ────────────────────────────────────────────────────────────
async def run_agent_stream(
    user_text: str,
    session_id: str,
    messages_state: list[dict[str, str]],
    plan_state: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    """
    异步运行 Agent 并 yield 中间事件，供 Gradio 前端流式渲染。

    优先使用 astream_events 逐 token 流式输出；
    如果 astream_events 失败则降级到 stream_mode=values。
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": session_id}}

    # 构建历史消息 + 当前用户消息
    history = dict_messages_to_langchain(messages_state)
    history.append(HumanMessage(content=user_text))

    # 如果存在已有计划，注入精简上下文（仅关键字段）
    if plan_state and plan_state.get("found"):
        plan_summary = {
            "title": plan_state.get("title"),
            "goal_summary": plan_state.get("goal_summary"),
            "horizon_days": plan_state.get("horizon_days"),
            "status": plan_state.get("status"),
            "phases": [
                {"phase": p.get("phase"), "range": p.get("range"), "focus": p.get("focus")}
                for p in (plan_state.get("phases") or [])[:3]
            ],
        }
        plan_context = (
            f"[系统提示] 当前已有学习计划摘要，请在已有基础上局部调整（不要从头生成）：\n"
            f"{json.dumps(plan_summary, ensure_ascii=False)}"
        )
        # 检查历史中是否已有 plan_context，避免重复注入
        existing_contexts = [
            m for m in history
            if isinstance(m, SystemMessage) and m.content and "已有学习计划摘要" in str(m.content)
        ]
        if not existing_contexts:
            history.insert(0, SystemMessage(content=plan_context))

    start_time = time.time()
    logger.info("Agent stream started for session=%s", session_id)

    # 尝试 astream_events 逐 token 流式（不指定 version，使用默认兼容模式）
    try:
        got_tokens = False
        got_tool_results = False
        async for event in agent.astream_events(
            {"messages": history},
            config=config,
        ):
            kind = event.get("event", "")
            logger.debug("Event: %s", kind)

            # ── 逐 token 流式输出 ──
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token_text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    if token_text:
                        got_tokens = True
                        yield {"type": "token", "text": token_text}

            # ── 工具调用开始 ──
            elif kind == "on_tool_start":
                name = event.get("name", "unknown")
                input_data = event.get("data", {}).get("input", {})
                args_str = json.dumps(input_data, ensure_ascii=False, default=str)
                logger.info("Tool call: %s(%s)", name, args_str[:100])
                yield {
                    "type": "tool_call",
                    "tool_name": name,
                    "tool_args": args_str,
                }

            # ── 工具调用完成 ──
            elif kind == "on_tool_end":
                name = event.get("name", "unknown")
                output = event.get("data", {}).get("output", "")
                output_str = str(output)[:500]
                logger.info("Tool result: %s → %s...", name, output_str[:80])
                got_tool_results = True
                yield {
                    "type": "tool_result",
                    "tool_name": name,
                    "tool_result": output_str,
                }

                # 从 tool_generate_plan 提取计划 JSON（自动同步）
                if name == "tool_generate_plan":
                    try:
                        plan_data = json.loads(str(output))
                        if plan_data.get("found"):
                            yield {
                                "type": "plan_sync",
                                "plan": plan_data,
                            }
                            logger.info("Plan synced: %s", plan_data.get("title", "?"))
                    except (json.JSONDecodeError, TypeError):
                        pass

        # 如果 astream_events 没有产出任何 token，降级到 stream_mode=values
        if not got_tokens:
            logger.warning(
                "astream_events produced no tokens (got_tool_results=%s), falling back to stream_mode=values",
                got_tool_results,
            )
            async for event in _stream_values_fallback(agent, history, config):
                yield event

    except Exception as exc:
        elapsed = time.time() - start_time
        logger.error("Agent stream error after %.1fs: %s", elapsed, exc)
        yield {"type": "error", "error": str(exc)}

    elapsed = time.time() - start_time
    logger.info("Agent stream completed in %.1fs for session=%s", elapsed, session_id)
    yield {"type": "done"}

