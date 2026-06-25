"""Agent helpers for PlannerAI."""

from app.agents.study_planner import generate_study_plan


def get_agent():
    """延迟导入，避免循环依赖"""
    from app.agents.graph_agent import get_agent as _get_agent
    return _get_agent()


def get_agent_model():
    from app.agents.graph_agent import get_agent_model as _get_agent_model
    return _get_agent_model()


async def run_agent_stream(*args, **kwargs):
    from app.agents.graph_agent import run_agent_stream as _run_agent_stream
    async for event in _run_agent_stream(*args, **kwargs):
        yield event


__all__ = ["generate_study_plan", "get_agent", "get_agent_model", "run_agent_stream"]