"""Standalone command-line application with offline demo and live read-only mode."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .agents import Services
from .catalog import choose_agents
from .models import AssetClass, ResearchReport, ResearchRequest


def main() -> None:
    parser = argparse.ArgumentParser(prog="fa-agent")
    parser.add_argument("command", choices=["plan", "run", "demo"])
    parser.add_argument("--symbol", help="Symbol, or DEMO in demo mode")
    parser.add_argument("--asset-class", choices=[x.value for x in AssetClass], default="equity")
    parser.add_argument("--as-of", help="ISO timestamp or date (point-in-time cutoff)")
    parser.add_argument("--exchange")
    parser.add_argument("--horizon", choices=["short", "medium", "long"], default="medium")
    parser.add_argument("--question", default="Analyze this financial instrument.")
    parser.add_argument("--coordination", choices=["standard", "adaptive", "assisted"], default="adaptive")
    parser.add_argument("--include-agent", action="append", dest="include_agents")
    parser.add_argument("--exclude-agent", action="append", default=[], dest="exclude_agents")
    parser.add_argument("--prices", help="Daily CSV with date and close columns")
    parser.add_argument("--llm", action="store_true", help="Use optional LangChain OpenAI commentary")
    parser.add_argument("--model", help="LLM model name")
    parser.add_argument("--output", help="Save structured report to JSON")
    a = parser.parse_args()
    if a.command == "demo" and a.symbol not in (None, "DEMO"):
        parser.error("Demo accepts only synthetic DEMO symbol.")
    if a.command == "demo" and a.llm:
        parser.error("LLM commentary is disabled for demo data.")
    symbol = "DEMO" if a.command == "demo" else a.symbol
    if not symbol:
        parser.error("--symbol is required for plan/run")
    try:
        request = ResearchRequest(
            symbol=symbol, asset_class=a.asset_class, exchange=a.exchange,
            question=a.question, horizon=a.horizon, coordination=a.coordination,
            as_of=datetime.fromisoformat(a.as_of) if a.as_of else None,
            include_agents=a.include_agents, exclude_agents=a.exclude_agents,
        )
        if a.command == "plan":
            output = {"request": request.model_dump(mode="json"),
                      "planned_agents": choose_agents(request)}
        else:
            from .graph import build_graph
            svc = Services.build("demo" if a.command == "demo" else "live", a.prices)
            result = build_graph(svc).invoke({"request": request.model_dump(mode="json")})
            report = ResearchReport.model_validate(result["report"])
            if a.llm:
                from .llm import explain
                report.llm_commentary = explain(report, a.model)
            output = report.model_dump(mode="json")
        contents = json.dumps(output, ensure_ascii=False, indent=2)
        if a.output:
            path = Path(a.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents + "\n", encoding="utf-8")
        print(contents)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"FA-Agent error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
