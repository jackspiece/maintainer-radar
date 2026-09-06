"""Keep shared browser heuristics aligned with the Python defaults."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from maintainer_radar.scoring import analyze_pr

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Browser parity checks need Node.js")
class DemoParityTests(unittest.TestCase):
    def test_shared_metadata_produces_the_same_decisions(self) -> None:
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        base = {
            "number": 1, "title": "Fix parser handling", "body": "Test plan: unit tests pass.",
            "updatedAt": now.isoformat(), "additions": 40, "deletions": 12, "changedFiles": 2,
            "files": [{"path": "src/parser.py"}, {"path": "tests/test_parser.py"}],
            "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
        }
        changes = [
            {},
            {"body": "This makes the ci and tests faster."},
            {"body": "## Test plan\npytest"},
            {"body": "**Validation:** pytest"},
            {"body": "Tested locally with pytest"},
            {"body": "Tests added: regression coverage"},
            {"body": "We should add tests later."},
            {"body": ""},
            {"body": "", "files": [{"path": "tests/test_parser.py"}], "changedFiles": 1},
            {"files": [{"path": "docs/guide.py"}], "changedFiles": 1},
            {"files": [{"path": "generated/test_parser.py"}], "changedFiles": 1},
            {"files": [{"path": "src/parser.py"}], "changedFiles": 1},
            {"files": [{"path": "src/parser.py"}], "changedFiles": 2},
            {"files": [{"path": "docs/guide.md"}], "changedFiles": 2},
            *({"files": [{"path": "README.md"}, {"path": path}]} for path in
              ("package-lock.json", "Dockerfile", "tests/test_parser.py")),
            {"draft": True},
            {"labels": [{"name": "waiting-on-author"}]},
            {"mergeable": "CONFLICTING"},
            {"mergeStateStatus": "BEHIND"},
            {"mergeStateStatus": "BLOCKED"},
            {"mergeStateStatus": "CLEAN"},
            {"statusCheckRollup": []},
            {"statusCheckRollup": [{"status": "COMPLETED", "conclusion": "FAILURE"}]},
            {"statusCheckRollup": [{"status": "IN_PROGRESS"}]},
            *({"statusCheckRollup": [{"state": state}]} for state in
              ("SUCCESS", "FAILURE", "ERROR", "PENDING", "EXPECTED")),
            {"statusCheckRollup": [{"status": "COMPLETED"}]},
            {"additions": 2200, "changedFiles": 40},
            {"updatedAt": "2026-05-10T00:00:00Z"},
        ]
        fixtures = [{**base, **change} for change in changes]
        shallow = {**base}
        del shallow["body"]
        fixtures.append(shallow)
        script = """
const fs = require('node:fs');
const demo = require('./docs/assets/demo.js');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = payload.fixtures.map(pr => demo.analyzePullRequest({
  ...pr, updated_at: pr.updatedAt, changed_files: pr.changedFiles
}, pr.files, { now: new Date(payload.now), checkRuns: pr.statusCheckRollup }));
process.stdout.write(JSON.stringify(results));
"""
        result = subprocess.run(
            ["node", "-e", script], cwd=ROOT, text=True, capture_output=True, timeout=15,
            input=json.dumps({"now": now.isoformat(), "fixtures": fixtures}),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        browser_results = json.loads(result.stdout)
        for fixture, browser in zip(fixtures, browser_results, strict=True):
            with self.subTest(fixture=fixture):
                python = analyze_pr(fixture, now=now)
                for key in ("risk", "reviewability", "action"):
                    self.assertEqual(browser[key], python[key], key)
                # Presentation order is independent; the evidence and decisions must agree.
                for key in ("flags", "signals"):
                    self.assertCountEqual(browser[key], python[key], key)
                self.assertEqual(browser["nextStep"], python["next_step"])
