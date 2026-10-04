"""Regenerate deterministic offline examples, or check them without writing."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-06-01T00:00:00Z"
REPORTS = {
    "sample-report.md": ["--format", "markdown"],
    "sample-report.json": ["--format", "json"],
    "sample-report.csv": ["--format", "csv"],
    "sample-report.html": ["--format", "html"],
    "sample-review-plan-15.md": ["--review-plan-minutes", "15"],
    "sample-review-plan-30.md": ["--review-plan-minutes", "30"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if an example is missing or stale")
    args = parser.parse_args()
    commands = {
        filename: ["from-json", str(ROOT / "examples/sample-prs.json"), "--now", NOW, *options]
        for filename, options in REPORTS.items()
    }
    for fmt, extension in (("markdown", "md"), ("json", "json")):
        commands[f"sample-comparison.{extension}"] = [
            "compare", str(ROOT / "examples/snapshots/before.json"),
            str(ROOT / "examples/snapshots/after.json"), "--format", fmt,
        ]
    stale = []
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    # A local .maintainer-radar.json must not change checked-in sample output.
    with TemporaryDirectory() as workdir:
        for filename, command in commands.items():
            result = subprocess.run(
                [sys.executable, "-m", "maintainer_radar", *command],
                cwd=workdir, env=env, check=True, capture_output=True, text=True, encoding="utf-8",
            )
            target = ROOT / "examples/output" / filename
            if args.check:
                if not target.exists() or target.read_text(encoding="utf-8") != result.stdout:
                    stale.append(str(target.relative_to(ROOT)))
            else:
                target.write_text(result.stdout, encoding="utf-8")
                print(f"Wrote {target.relative_to(ROOT)}")
    if stale:
        print("Stale examples: " + ", ".join(stale), file=sys.stderr)
        print("Run python scripts/generate_examples.py and commit the updated output.", file=sys.stderr)
        return 1
    if args.check:
        print(f"All {len(commands)} offline examples are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
