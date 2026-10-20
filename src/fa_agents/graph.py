"""LangGraph orchestrator scaffold. It never fabricates agent research."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .catalog import SPECIALISTS, choose_agents
from .models import AgentResult, ResearchReport, ResearchRequest


class ResearchState(TypedDict, total=False):
    request: dict[str, Any]
    planned_agents: list[str]
    agent_id: str
    results: Annotated[list[dict[str, Any]], operator.add]
    warnings: list[str]
    report: dict[str, Any]


def plan(state: ResearchState) -> dict[str, Any]:
    request = ResearchRequest.model_validate(state["request"])
    return {"planned_agents": choose_agents(request)}


def dispatch(state: ResearchState) -> str | list[Send]:
    agents = state["planned_agents"]
    if not agents:
        return "validate"
    return [Send("specialist", {"agent_id": agent_id}) for agent_id in agents]


def specialist(state: ResearchState) -> dict[str, Any]:
    agent_id = state["agent_id"]
    if agent_id not in SPECIALISTS:
        raise ValueError(f"Unknown specialist: {agent_id}")
    result = AgentResult(
        agent_id=agent_id,
        status="not_implemented",
        summary=f"{SPECIALISTS[agent_id]}: implementation pending.",
        limitations=["No data was retrieved and no financial analysis was performed."],
    )
    return {"results": [result.model_dump(mode="json")]}


def validate(state: ResearchState) -> dict[str, Any]:
    results = [AgentResult.model_validate(item) for item in state.get("results", [])]
    warnings = []
    if not results:
        warnings.append("No specialists were selected.")
    if any(result.status != "completed" for result in results):
        warnings.append("The selected specialists have not completed verified research.")
    return {"warnings": warnings}


def synthesize(state: ResearchState) -> dict[str, Any]:
    """Emit a truthful execution report; actual evidence synthesis is not built."""
    results = [AgentResult.model_validate(item) for item in state.get("results", [])]
    status = "completed" if results and all(r.status == "completed" for r in results) else "not_ready"
    report = ResearchReport(
        request=ResearchRequest.model_validate(state["request"]),
        status=status,
        results=results,
        warnings=state.get("warnings", []),
    )
    return {"report": report.model_dump(mode="json")}


def build_graph():
    """A LangGraph plan/fan-out/aggregate scaffold with no paid services required."""
    workflow = StateGraph(ResearchState)
    workflow.add_node("plan", plan)
    workflow.add_node("specialist", specialist)
    workflow.add_node("validate", validate)
    workflow.add_node("synthesize", synthesize)
    workflow.add_edge(START, "plan")
    workflow.add_conditional_edges("plan", dispatch, ["specialist", "validate"])
    workflow.add_edge("specialist", "validate")
    workflow.add_edge("validate", "synthesize")
    workflow.add_edge("synthesize", END)
    return workflow.compile()
