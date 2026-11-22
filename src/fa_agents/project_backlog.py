"""Read-only project progress: verified commits + explicitly registered pending work.

No inference from ChatGPT conversation titles or file modification times.
Delivered/implemented means a Git commit, NOT a successful Windows deployment.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ALLOWED = {"todo", "doing", "blocked", "done"}


def read_project_backlog(repo_root: Path, *, project: str, max_commits: int = 18) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    manifest = next((p for p in (
        root / "docs" / "project_backlog.json",
        root / "Docs" / "project_backlog.json",
    ) if p.is_file()), None)
    result: dict[str, Any] = {
        "project": project,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": [], "commits": [], "warnings": [],
        "definitions": {
            "todo": "Requested / identified, not verified as completed",
            "doing": "In progress, not necessarily delivered",
            "blocked": "Blocked by a dependency or verification",
            "done": "Marked completed with explicit evidence",
            "commits": "Committed code; does not prove deployment, testing or approval",
        },
    }
    if manifest:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
                raise ValueError("Expected object with items array")
            result["items"] = [
                {k: item.get(k) for k in
                 ("id", "title", "description", "status", "priority", "source", "updated_at", "evidence")
                 if k in item}
                for item in payload.get("items", [])[:250]
                if isinstance(item, dict) and
                item.get("status") in _ALLOWED and
                isinstance(item.get("title"), str) and
                isinstance(item.get("id"), str)
            ]
            result["manifest_version"] = payload.get("version", 1)
        except (OSError, ValueError, UnicodeError) as exc:
            result["warnings"].append("Backlog manifest unreadable: " + type(exc).__name__)
    else:
        result["warnings"].append("No project_backlog.json is registered yet.")
    try:
        command = [
            "git", "-C", str(root), "log", "-n",
            str(max(1, min(int(max_commits), 40))),
            "--format=%H%x1f%cI%x1f%s",
        ]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   errors="replace", timeout=3, check=False)
        if completed.returncode:
            result["warnings"].append("Git history unavailable for this checkout.")
        else:
            for line in completed.stdout.splitlines():
                parts = line.split("\x1f", 2)
                if len(parts) != 3:
                    continue
                sha, timestamp, subject = parts
                if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha.lower()):
                    continue
                result["commits"].append({
                    "sha": sha, "timestamp": timestamp, "title": subject[:300],
                    "verification": "committed",
                })
    except (OSError, subprocess.TimeoutExpired):
        result["warnings"].append("Git history unavailable; displaying tracked backlog only.")
    return result
