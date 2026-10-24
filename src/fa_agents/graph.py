"""Executable LangGraph plan -> parallel specialists -> review -> synthesis."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import START, END, StateGraph
from langgraph.types import Send

from .agents import Services, run_specialist, review
from .catalog import choose_agents
from .models import ResearchRequest, AgentResult, ResearchReport


class State(TypedDict, total=False):
    request: dict[str, Any]
    planned_agents: list[str]
    agent_id: str
    results: Annotated[list[dict[str, Any]], operator.add]
    warnings: list[str]
    report: dict[str, Any]


def plan(state: State) -> dict:
    return {"planned_agents": choose_agents(ResearchRequest.model_validate(state["request"]))}


def route(state: State) -> str | list[Send]:
    workers = [a for a in state["planned_agents"] if a != "risk"]
    if not workers:
        return "validate"
    return [Send("specialist", {"agent_id": a, "request": state["request"]}) for a in workers]


def validate(state: State) -> dict:
    results = [AgentResult.model_validate(x) for x in state.get("results", [])]
    warnings = []
    if not results:
        warnings.append("No evidence-gathering specialists were selected.")
    for x in results:
        if x.status == "failed":
            warnings.append(f"{x.agent_id} failed: {'; '.join(x.limitations)}")
        if x.status == "not_implemented":
            warnings.append(f"{x.agent_id} is not implemented.")
    return {"warnings": warnings}


def build_graph(services: Services | None = None):
    services = services or Services.build()

    def specialist(state: State) -> dict:
        result = run_specialist(state["agent_id"],
                                ResearchRequest.model_validate(state["request"]), services)
        return {"results": [result.model_dump(mode="json")]}

    def risk_review(state: State) -> dict:
        if "risk" not in state["planned_agents"]:
            return {}
        results = [AgentResult.model_validate(x) for x in state.get("results", [])]
        result = review(results, state["planned_agents"])
        return {"results": [result.model_dump(mode="json")]}

    def synthesize(state: State) -> dict:
        request = ResearchRequest.model_validate(state["request"])
        by_id = {r.agent_id: r for r in
                 (AgentResult.model_validate(x) for x in state.get("results", []))}
        results = [by_id[a] for a in state["planned_agents"] if a in by_id]
        unavailable = sum(r.status in {"failed", "no_data", "not_implemented"} for r in results)
        partial = sum(r.status == "partial" for r in results)
        completed = sum(r.status == "completed" for r in results)
        if not results or completed + partial == 0:
            status = "not_ready"
        elif unavailable or partial:
            status = "partial"
        else:
            status = "completed"
        sources = sum(len(r.evidence) for r in results)
        warnings = list(state.get("warnings", []))
        if services.demo:
            warnings.append("SYNTHETIC DEMO: company and news data are fabricated fixtures.")
        report = ResearchReport(
            request=request, status=status, data_mode="demo" if services.demo else "live",
            planned_agents=state["planned_agents"], results=results,
            warnings=warnings,
            summary=(f"{request.symbol}: {completed} completed, {partial} partial, "
                     f"{unavailable} unavailable specialist(s); {sources} source records. "
                     "No investment recommendation has been produced."),
        )
        return {"report": report.model_dump(mode="json")}

    graph = StateGraph(State)
    graph.add_node("plan", plan)
    graph.add_node("specialist", specialist)
    graph.add_node("validate", validate)
    graph.add_node("risk_review", risk_review)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route, ["specialist", "validate"])
    graph.add_edge("specialist", "validate")
    graph.add_edge("validate", "risk_review")
    graph.add_edge("risk_review", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()
