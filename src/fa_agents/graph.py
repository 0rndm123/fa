"""Executable LangGraph research planner -> bounded delegation -> critical review.

Research remains read-only. Specialists retain responsibility for all source
retrieval and calculations. The coordinator may call at most two *additional*
already implemented specialists in one extra round; there are no unbounded loops.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import START, END, StateGraph
from langgraph.types import Send

from .agents import Services, run_specialist, review
from .catalog import choose_agents
from .coordinator import assess_followups, critical_review, initial_plan
from .models import ResearchRequest, ResearchPlan, AgentResult, ResearchReport


class State(TypedDict, total=False):
    request: dict[str, Any]
    automatic_selection: bool
    initial_agents: list[str]
    planned_agents: list[str]
    followup_agents: list[str]
    coordination_plan: dict[str, Any]
    critical_review: dict[str, Any]
    agent_id: str
    results: Annotated[list[dict[str, Any]], operator.add]
    warnings: list[str]
    report: dict[str, Any]


def _automatic(state: State, request: ResearchRequest) -> bool:
    # When UI auto routing pre-selects the agents, it passes the original
    # intent explicitly. CLI callers can rely on include_agents=None.
    return state.get("automatic_selection", request.include_agents is None)


def plan(state: State) -> dict:
    request = ResearchRequest.model_validate(state["request"])
    selected = choose_agents(request)
    coordination = initial_plan(selected, request.coordination, manual=not _automatic(state, request))
    return {
        "planned_agents": selected,
        "initial_agents": selected,
        "followup_agents": [],
        "coordination_plan": coordination.model_dump(mode="json"),
    }


def route(state: State) -> str | list[Send]:
    workers = [a for a in state["planned_agents"] if a != "risk"]
    if not workers:
        return "assess"
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

    def assess(state: State) -> dict:
        request = ResearchRequest.model_validate(state["request"])
        original = ResearchPlan.model_validate(state["coordination_plan"])
        results = [AgentResult.model_validate(x) for x in state.get("results", [])]
        updated = assess_followups(
            request, original, results, manual=not _automatic(state, request),
            demo=services.demo,
        )
        additional = [a for a in updated.followup_agents if a not in state["initial_agents"]]
        return {
            "followup_agents": additional,
            "planned_agents": state["initial_agents"] + additional,
            "coordination_plan": updated.model_dump(mode="json"),
        }

    def route_followups(state: State) -> str | list[Send]:
        pending = state.get("followup_agents", [])
        if not pending:
            return "validate"
        return [Send("followup_specialist", {"agent_id": agent_id, "request": state["request"]})
                for agent_id in pending]

    def risk_review(state: State) -> dict:
        if "risk" not in state["planned_agents"]:
            return {}
        results = [AgentResult.model_validate(x) for x in state.get("results", [])]
        result = review(results, state["planned_agents"])
        return {"results": [result.model_dump(mode="json")]}

    def challenge(state: State) -> dict:
        request = ResearchRequest.model_validate(state["request"])
        results = [AgentResult.model_validate(x) for x in state.get("results", [])]
        audit = critical_review(request, results)
        return {"critical_review": audit.model_dump(mode="json")}

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
        audit = state.get("critical_review", {})
        if any(f.get("severity") == "high" for f in audit.get("findings", [])):
            warnings.append("Critical review identified high-severity source or consistency gaps.")
            if status == "completed":
                status = "partial"
        if services.demo:
            warnings.append("SYNTHETIC DEMO: company and news data are fabricated fixtures.")
        report = ResearchReport(
            request=request, status=status, data_mode="demo" if services.demo else "live",
            planned_agents=state["planned_agents"], results=results,
            research_plan=ResearchPlan.model_validate(state["coordination_plan"]),
            critical_review=audit,
            warnings=warnings,
            summary=(f"{request.symbol}: {completed} completed, {partial} partial, "
                     f"{unavailable} unavailable specialist(s); {sources} source records. "
                     "No investment recommendation has been produced."),
        )
        return {"report": report.model_dump(mode="json")}

    graph = StateGraph(State)
    graph.add_node("plan", plan)
    graph.add_node("specialist", specialist)
    graph.add_node("assess", assess)
    graph.add_node("followup_specialist", specialist)
    graph.add_node("validate", validate)
    graph.add_node("risk_review", risk_review)
    graph.add_node("challenge", challenge)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route, ["specialist", "assess"])
    graph.add_edge("specialist", "assess")
    graph.add_conditional_edges("assess", route_followups,
                                ["followup_specialist", "validate"])
    graph.add_edge("followup_specialist", "validate")
    graph.add_edge("validate", "risk_review")
    graph.add_edge("risk_review", "challenge")
    graph.add_edge("challenge", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()
