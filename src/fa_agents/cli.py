"""Minimal local interface; not an online research client yet."""
from __future__ import annotations

import argparse
import json

from .catalog import choose_agents
from .models import AssetClass, ResearchRequest


def main() -> None:
    parser = argparse.ArgumentParser(prog="fa-agent")
    parser.add_argument("command", choices=["plan", "run"])
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--asset-class", choices=[c.value for c in AssetClass], required=True)
    parser.add_argument("--exchange")
    parser.add_argument("--question", default="Analyze this instrument.")
    parser.add_argument("--horizon", choices=["short", "medium", "long"], default="medium")
    parser.add_argument("--include-agent", action="append", dest="include_agents")
    parser.add_argument("--exclude-agent", action="append", default=[], dest="exclude_agents")
    args = parser.parse_args()
    request = ResearchRequest(
        symbol=args.symbol,
        asset_class=args.asset_class,
        exchange=args.exchange,
        question=args.question,
        horizon=args.horizon,
        include_agents=args.include_agents,
        exclude_agents=args.exclude_agents,
    )
    if args.command == "plan":
        output = {"request": request.model_dump(mode="json"), "planned_agents": choose_agents(request)}
    else:
        from .graph import build_graph

        state = build_graph().invoke({"request": request.model_dump(mode="json")})
        output = state["report"]
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
