"""Run the real Action build script locally with a credential-free stubbed scan."""
from __future__ import annotations

import json
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = (ROOT / "action.yml").read_text(encoding="utf-8")
BUILD_SCRIPT = textwrap.dedent(ACTION.split("      run: |\n", 1)[1])


def parse_outputs(raw: str) -> dict[str, str]:
    """Check Linux environment-file framing without calling GitHub's runner."""
    lines = iter(raw.split("\n"))
    outputs = {}
    for line in lines:
        if not line:
            continue
        if "=" in line and ("<<" not in line or line.index("=") < line.index("<<")):
            key, value = line.split("=", 1)
        elif "<<" in line:
            key, delimiter = line.split("<<", 1)
            value_lines = []
            for value_line in lines:
                if value_line == delimiter:
                    break
                value_lines.append(value_line)
            else:
                raise ValueError("Unterminated output delimiter")
            value = "\n".join(value_lines)
        else:
            raise ValueError(f"Invalid output line: {line!r}")
        if not key or key in outputs:
            raise ValueError(f"Invalid or duplicate output key: {key!r}")
        outputs[key] = value
    return outputs


@unittest.skipUnless(shutil.which("bash"), "Action execution requires Bash")
class ActionExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="radar-action-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        python = self.bin / "python"
        python.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n', encoding="utf-8")
        python.chmod(0o755)
        (self.directory / "runner-temp").mkdir()
        self.script = self.directory / "run.sh"
        self.script.write_text(BUILD_SCRIPT, encoding="utf-8")
        self.prs = json.loads((ROOT / "examples/sample-prs.json").read_text(encoding="utf-8"))[:1]
        wrapper = self.bin / "maintainer-radar"
        wrapper.write_text(f"#!{sys.executable}\n" + textwrap.dedent('''\
            import json
            import sys
            from pathlib import Path
            from unittest.mock import patch
            import maintainer_radar.cli as cli

            Path("argv.json").write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
            prs = json.loads(Path("prs.json").read_text(encoding="utf-8"))
            def list_prs(*args, **kwargs):
                with open("fetch.jsonl", "a", encoding="utf-8") as stream:
                    stream.write(json.dumps([args, kwargs]) + "\\n")
                return prs
            def view_pr(repository, number):
                return next(pr for pr in prs if pr["number"] == int(number))
            with patch.object(cli, "list_repo_prs", list_prs), patch.object(cli, "view_pr", view_pr):
                sys.exit(cli.main(sys.argv[1:]))
            '''), encoding="utf-8")
        wrapper.chmod(0o755)
        # An unexpected gh invocation must fail, never reach an authenticated CLI.
        gh = self.bin / "gh"
        gh.write_text("#!/bin/sh\necho 'Unexpected gh invocation blocked' >&2\nexit 99\n", encoding="utf-8")
        gh.chmod(0o755)

    def run_action(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        inputs_section = ACTION.split("inputs:\n", 1)[1].split("\noutputs:", 1)[0]
        defaults = dict(re.findall(
            r"^  ([a-z-]+):\n(?:(?:    .*|)\n)*?    default: (.*)$", inputs_section, re.MULTILINE,
        ))
        defaults = {key: json.loads(value) if value.startswith('"') else value for key, value in defaults.items()}
        self.assertEqual(len(defaults), 18)
        defaults.update(overrides)
        # Deliberately do not inherit tokens, authentication, or user configuration.
        environment = {
            "PATH": f"{self.bin}:{Path(sys.executable).parent}:/usr/bin:/bin",
            "HOME": str(self.directory),
            "LANG": "C.UTF-8",
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GITHUB_REPOSITORY": "fixture/queue",
            "GITHUB_OUTPUT": str(self.directory / "github-output"),
            "GITHUB_STEP_SUMMARY": str(self.directory / "step-summary"),
            "RUNNER_TEMP": str(self.directory / "runner-temp"),
        }
        environment.update({"INPUT_" + key.upper().replace("-", "_"): value for key, value in defaults.items()})
        for filename in ("github-output", "step-summary", "fetch.jsonl"):
            (self.directory / filename).write_text("", encoding="utf-8")
        (self.directory / "prs.json").write_text(json.dumps(self.prs), encoding="utf-8")
        return subprocess.run(
            ["bash", "--noprofile", "--norc", str(self.script)], cwd=self.directory,
            env=environment, text=True, capture_output=True, timeout=30,
        )

    def outputs(self) -> dict[str, str]:
        return parse_outputs((self.directory / "github-output").read_text(encoding="utf-8"))

    def assert_success(self, result: subprocess.CompletedProcess[str], report_path: str) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs()["report-path"], report_path)
        self.assertTrue((self.directory / report_path).is_file())
        self.assertEqual(len((self.directory / "fetch.jsonl").read_text().splitlines()), 1)

    def test_rejects_newline_output_paths_before_side_effects(self) -> None:
        for path in ("nested/report\nunknown=value.md", "nested/report\nname.md",
                     "nested/report\r\nunknown=value.md", "nested/report\rname.md",
                     "nested/report.md\n", "\rreport.md"):
            with self.subTest(path=path):
                result = self.run_action(output=path)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("output must be a single-line file path", result.stderr)
                self.assertEqual(self.outputs(), {})
                self.assertEqual((self.directory / "step-summary").read_text(), "")
                self.assertFalse((self.directory / "argv.json").exists())
                self.assertFalse((self.directory / "nested").exists())

    def test_leading_dash_output_paths_are_literal(self) -> None:
        for path in ("-report.md", "-reports/output.md", "--report.md"):
            with self.subTest(path=path):
                self.assert_success(self.run_action(output=path), path)

    def test_leading_dash_labels_reach_real_cli_as_values(self) -> None:
        for label in ("-bug", "--help", "-bug=needs review"):
            with self.subTest(label=label):
                self.prs[0]["labels"] = [{"name": label}]
                self.assert_success(self.run_action(label=label, format="json"), "maintainer-radar.json")
                self.assertEqual(self.outputs()["total"], "1")
                self.assertIn(f"--label={label}", json.loads((self.directory / "argv.json").read_text()))

    def test_leading_dash_config_path_reaches_real_cli_as_value(self) -> None:
        (self.directory / "-config.json").write_text("{}", encoding="utf-8")
        self.assert_success(self.run_action(config="-config.json"), "maintainer-radar.md")
        self.assertIn("--config=-config.json", json.loads((self.directory / "argv.json").read_text()))

    def test_portable_path_characters_and_label_data_stay_literal(self) -> None:
        label = 'bug: "quoted" \\ tab\t $(touch NEVER_EXECUTE) ${{ github.repository }}'
        self.prs[0]["labels"] = [{"name": label}]
        path = 'nested space/日本語: "report" \\ ${{ github.repository }}.json'
        self.assert_success(self.run_action(output=path, label=label, format="json"), path)
        self.assertEqual(self.outputs()["total"], "1")
        self.assertFalse((self.directory / "NEVER_EXECUTE").exists())

    def test_all_cli_option_values_remain_bound(self) -> None:
        (self.directory / "-config.json").write_text("{}", encoding="utf-8")
        options = {"limit": "17", "sort": "risk", "top": "3", "config": "-config.json",
                   "label": "-bug", "author": "fixture-author", "stale-days": "1",
                   "updated-since": "2020-01-01", "action": "review-now", "min-score": "0",
                   "max-risk": "100"}
        self.assert_success(self.run_action(**options), "maintainer-radar.md")
        argv = json.loads((self.directory / "argv.json").read_text())
        for option, value in options.items():
            self.assertIn(f"--{option}={value}", argv)
        self.assertEqual(len(argv), 16)  # repo, repository, 11 values, hydrate, --format, json

    def test_scan_failure_propagates_without_report_or_summary(self) -> None:
        (self.bin / "maintainer-radar").write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        result = self.run_action()
        self.assertEqual(result.returncode, 7)
        self.assertNotIn("summary-json", self.outputs())
        self.assertFalse((self.directory / "maintainer-radar.md").exists())
        self.assertEqual((self.directory / "step-summary").read_text(), "")

    def test_report_format_plan_summary_and_output_contracts(self) -> None:
        declared = set(re.findall(r"^  ([a-z-]+):$", ACTION.split("\noutputs:\n", 1)[1]
                                  .split("\nruns:\n", 1)[0], re.MULTILINE))
        plan_outputs = {"plan-budget-minutes", "planned-prs", "planned-minutes", "remaining-minutes",
                        "deferred-prs", "watch-only-prs"}
        for report_format, extension in (("markdown", "md"), ("html", "html"), ("json", "json"), ("csv", "csv")):
            for plan in ("", "15"):
                if report_format == "csv" and plan:
                    continue
                for summary in ("true", "false"):
                    with self.subTest(format=report_format, plan=plan, summary=summary):
                        result = self.run_action(**{"format": report_format, "review-plan-minutes": plan,
                                                    "step-summary": summary})
                        stem = "review-plan" if plan else "maintainer-radar"
                        self.assert_success(result, f"{stem}.{extension}")
                        outputs = self.outputs()
                        self.assertEqual(set(outputs), declared if plan else declared - plan_outputs)
                        self.assertEqual(json.loads(outputs["summary-json"])["total"], 1)
                        self.assertEqual(bool((self.directory / "step-summary").read_text()), summary == "true")
                        if plan:
                            self.assertEqual(outputs["plan-budget-minutes"], "15")


if __name__ == "__main__":
    unittest.main()
