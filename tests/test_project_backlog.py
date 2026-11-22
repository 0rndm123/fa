"""Project backlog is explicitly recorded; Git commits are code evidence only."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT / "src/fa_agents/project_backlog.py"


def load_reader():
    spec=importlib.util.spec_from_file_location("backlog_under_test",MODULE)
    module=importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.read_project_backlog


class ProjectBacklogTests(unittest.TestCase):
    def test_registered_pending_work_and_invalid_status(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"docs").mkdir()
            (root/"docs"/"project_backlog.json").write_text(json.dumps({
                "version":1,"items":[
                    {"id":"REQ-1","title":"Outstanding request","status":"todo",
                     "priority":"P1","source":"User request"},
                    {"id":"BAD","title":"Should be ignored","status":"invented"},
                ]}),encoding="utf-8")
            data=load_reader()(root,project="Example")
            self.assertEqual(len(data["items"]),1)
            self.assertEqual(data["items"][0]["id"],"REQ-1")
            self.assertNotIn("completed",data["items"][0])
            self.assertEqual(data["commits"],[])

    def test_completion_requires_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/"docs").mkdir()
            payload={"version":1,"items":[
                {"id":"NOT-PROVEN","title":"Unverified delivery","status":"done"},
                {"id":"PROVEN","title":"Verified delivery","status":"done",
                 "evidence":"Commit abcdef1 + accepted Windows QA"},
            ]}
            (root/"docs"/"project_backlog.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            data=load_reader()(root,project="Example")
            statuses={item["id"]:item["status"] for item in data["items"]}
            self.assertEqual(statuses["NOT-PROVEN"],"todo")
            self.assertEqual(statuses["PROVEN"],"done")
            self.assertTrue(any("lacks completion evidence" in w for w in data["warnings"]))

    def test_invalid_manifest_is_reported_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/"docs").mkdir()
            (root/"docs"/"project_backlog.json").write_text("not-json",encoding="utf-8")
            response=load_reader()(root,project="Example")
            self.assertFalse(response["items"])
            self.assertTrue(any("manifest" in w.lower() for w in response["warnings"]))

    @unittest.skipUnless(shutil.which("git"),"Git not installed")
    def test_recent_commits_are_real_and_not_marked_approved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            subprocess.run(["git","-C",str(root),"init","-q"],check=True)
            subprocess.run(["git","-C",str(root),"-c","user.name=QA",
                            "-c","user.email=qa@example.invalid","commit",
                            "--allow-empty","-qm","Validated commit marker"],
                           check=True)
            data=load_reader()(root,project="Example")
            self.assertTrue(data["commits"])
            self.assertEqual(data["commits"][0]["title"],"Validated commit marker")
            self.assertEqual(data["commits"][0]["verification"],"committed")
            self.assertNotIn("approved",data["commits"][0])


if __name__=="__main__":
    unittest.main()
