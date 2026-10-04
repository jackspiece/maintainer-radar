from __future__ import annotations

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from maintainer_radar.cli import main
from maintainer_radar.compare import (
    compare_snapshots, load_snapshot, render_comparison, validate_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def observation(number: int = 1, repository: str = "team/project") -> dict:
    return {
        "number": number, "title": "Fix parser", "url": f"https://github.com/{repository}/pull/{number}",
        "action": "ask for CI fix", "risk": 30, "reviewability": 70,
        "next_step": "Ask for passing checks.", "flags": ["CI failing"], "signals": ["tests changed"],
        "checks": {"passed": 0, "failed": 1, "pending": 0, "skipped": 0, "total": 1},
    }


class SnapshotComparisonTests(unittest.TestCase):
    def test_unchanged_and_reordered_sets_do_not_produce_changes(self) -> None:
        before = [observation(2), observation()]
        before[0]["flags"] = ["CI failing", "stale 7 days"]
        before[0]["signals"] = ["tests changed", "test plan present"]
        after = deepcopy(list(reversed(before)))
        after[1]["flags"].reverse()
        after[1]["signals"].reverse()
        result = compare_snapshots(before, after)
        self.assertEqual(result["summary"], {"before": 2, "after": 2, "newly_observed": 0,
                                          "no_longer_observed": 0, "changed": 0, "unchanged": 2})
        self.assertEqual(result, compare_snapshots(list(reversed(before)), list(reversed(after))))
        self.assertEqual(before[0]["flags"], ["CI failing", "stale 7 days"])
        self.assertEqual(after[1]["flags"], ["stale 7 days", "CI failing"])

    def test_ci_recovery_retains_explanatory_before_and_after(self) -> None:
        before = observation()
        after = deepcopy(before)
        after.update(action="review now", risk=0, reviewability=100,
                     next_step="Start a review.", flags=[], signals=["tests changed", "CI passed"])
        after["checks"].update(passed=1, failed=0)
        result = compare_snapshots([before], [after])
        item = result["changed"][0]
        differences = {change["field"]: change for change in item["changes"]}
        self.assertEqual(differences["action"], {"field": "action", "before": "ask for CI fix", "after": "review now"})
        self.assertEqual(differences["checks"]["before"]["failed"], 1)
        self.assertEqual(differences["checks"]["after"]["failed"], 0)
        self.assertEqual(item["before"]["flags"], ["CI failing"])
        self.assertEqual(item["after"]["signals"], ["CI passed", "tests changed"])
        markdown = render_comparison(result)
        self.assertIn("ask for CI fix | review now", markdown)
        self.assertIn("| risk | 30 | 0 |", markdown)
        self.assertIn("| reviewability | 70 | 100 |", markdown)
        self.assertIn("not proof of code progress", markdown)

    def test_added_and_missing_remain_observations(self) -> None:
        result = compare_snapshots([observation(1)], [observation(2)])
        self.assertEqual(result["summary"]["newly_observed"], 1)
        self.assertEqual(result["summary"]["no_longer_observed"], 1)
        self.assertNotIn("closed", result)
        self.assertNotIn("merged", result)
        self.assertIn("Absence does not establish", render_comparison(result))
        self.assertIn("filters, scan limits", render_comparison(result))

    def test_empty_snapshots_are_supported_in_both_directions(self) -> None:
        self.assertEqual(compare_snapshots([], [observation()])["summary"]["newly_observed"], 1)
        self.assertEqual(compare_snapshots([observation()], [])["summary"]["no_longer_observed"], 1)
        empty = compare_snapshots([], [])
        self.assertEqual(empty["summary"]["changed"], 0)
        self.assertIn("None.", render_comparison(empty))

    def test_identity_keeps_repositories_hosts_and_exact_urls_distinct(self) -> None:
        items = [observation(1, "team/first"), observation(1, "team/second")]
        third = observation(1, "team/first")
        third["url"] = "https://forge.example/team/first/pulls/1"
        fourth = observation()
        fourth["url"] = "https://gitlab.example/group/subgroup/project/-/merge_requests/1"
        items.extend([third, fourth])
        self.assertEqual(compare_snapshots([], items)["summary"]["newly_observed"], 4)
        changed_url = deepcopy(items[0])
        changed_url["url"] += "?view=all#discussion"
        compared = compare_snapshots([items[0]], [changed_url])
        self.assertEqual(compared["summary"]["changed"], 0)
        self.assertEqual(compared["summary"]["newly_observed"], 1)

    def test_duplicate_identity_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate pull request URL"):
            compare_snapshots([observation(), observation()], [])

    def test_full_queue_schema_required(self) -> None:
        for payload in ({}, {"items": [observation()]}, {"total": 1}, [None], [12], [{}],
                        [{"number": 1, "title": "Raw PR", "url": observation()["url"]}]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_snapshot(payload)

    def test_required_fields_cannot_be_missing(self) -> None:
        for field in observation():
            item = observation()
            del item[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_snapshot([item])

    def test_malformed_field_values_fail(self) -> None:
        values = {
            "number": [True, False, 0, -1, 1.0, "1"],
            "title": [None, 12, "bad\ud800"], "action": [None, "", "  ", 3],
            "next_step": [None, 8],
            "risk": [True, -1, 101, 1.5, float("inf"), float("nan"), "30"],
            "reviewability": [False, -1, 101, 4.0, None],
            "flags": [None, "CI failing", [1], [None], ["bad\ud800"]],
            "signals": [None, {}, [False]], "checks": [None, {}, [], "passed"],
        }
        for field, invalid in values.items():
            for value in invalid:
                item = observation()
                item[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_snapshot([item])

    def test_malformed_check_counts_fail(self) -> None:
        for key in ("passed", "failed", "pending", "skipped", "total"):
            for value in (True, -1, 0.5, "1", float("inf")):
                item = observation()
                item["checks"][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_snapshot([item])
        item = observation()
        item["checks"]["total"] = 5
        with self.assertRaisesRegex(ValueError, "checks.total"):
            validate_snapshot([item])

    def test_invalid_or_unqualified_urls_fail(self) -> None:
        for url in ("", "#1", "/team/project/pull/1", "javascript:alert(1)", "file:///a/b/pull/1",
                    "https://github.com/pull/1", "https://github.com/team/project", "https://github.com/a/b/pull/2",
                    "https://github.com/a/b/pull/1/", "https://github.com/a/b/pull/01",
                    "https://user:secret@github.com/a/b/pull/1", "https://github.com/a/b/pull/1\n",
                    "https://github.com/a/../pull/1", "https://github.com/a//pull/1",
                    "https://github.com:bad/a/b/pull/1", "https://github.com:0/a/b/pull/1",
                    "https://github.com/a\\b/pull/1", "https://[bad/a/b/pull/1"):
            item = observation()
            item["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_snapshot([item])

    def test_markdown_escapes_hostile_titles_and_changed_values(self) -> None:
        before = observation()
        after = observation()
        hostile = 'left|right\nrelease](https://evil.invalid/)<!-- <img src=x> `code` &copy;'
        after.update(title=hostile, action=hostile, next_step=hostile, flags=[hostile], signals=[hostile])
        result = render_comparison(compare_snapshots([before], [after]))
        self.assertNotIn("<img", result)
        self.assertNotIn("<!--", result)
        self.assertNotIn("](https://evil.invalid/)", result)
        self.assertNotIn("&copy;", result)
        self.assertNotIn("`code`", result)
        for line in result.splitlines():
            if line.startswith("|"):
                self.assertEqual(line.count("|"), 4, line)
        self.assertEqual(result.count("](<https://github.com/team/project/pull/1>)"), 1)
        self.assertIn("left&#124;right release&#93;", result)

    def test_link_destination_cannot_break_out(self) -> None:
        item = observation()
        item["url"] += '?x=)[bad](https://evil.invalid/)<>"'
        result = render_comparison(compare_snapshots([], [item]))
        self.assertNotIn(")[bad]", result)
        self.assertIn("%29%5Bbad%5D%28", result)
        self.assertNotIn('<>"', result)

    def test_link_destination_preserves_literal_entity_text(self) -> None:
        item = observation()
        item["url"] += "?literal=&#41;&copy;&next=1"
        result = render_comparison(compare_snapshots([], [item]))
        self.assertIn("?literal=&amp;#41;&amp;copy;&amp;next=1", result)

    def test_json_is_deterministic_and_keeps_original_text(self) -> None:
        before = observation()
        after = observation()
        after["title"] = "left|right\n中文"
        report = compare_snapshots([before], [after])
        self.assertEqual(json.loads(render_comparison(report, "json")), report)
        self.assertEqual(report["changed"][0]["after"]["title"], "left|right\n中文")
        self.assertEqual(render_comparison(report, "json"), render_comparison(report, "json"))
        with self.assertRaisesRegex(ValueError, "markdown or json"):
            render_comparison(report, "csv")

    def test_load_rejects_invalid_encoding_json_duplicates_and_nonfinite(self) -> None:
        payloads = [b"\xff", b"{", b"[NaN]", b"[Infinity]", b"[1e400]", b'{"a": 1, "a": 2}',
                    b"[" * 2000 + b"]" * 2000]
        with TemporaryDirectory() as workdir:
            path = Path(workdir) / "snapshot.json"
            for payload in payloads:
                path.write_bytes(payload)
                with self.subTest(payload=payload[:30]), self.assertRaises(ValueError):
                    load_snapshot(path)
                self.assertEqual(path.read_bytes(), payload)
            with self.assertRaisesRegex(ValueError, "regular JSON file"):
                load_snapshot(workdir)

    def test_file_and_record_limits(self) -> None:
        with TemporaryDirectory() as workdir:
            path = Path(workdir) / "snapshot.json"
            path.write_text("[] ")
            with patch("maintainer_radar.compare.MAX_SNAPSHOT_BYTES", 2), self.assertRaisesRegex(ValueError, "exceeds"):
                load_snapshot(path)
        with patch("maintainer_radar.compare.MAX_SNAPSHOT_RECORDS", 1), self.assertRaisesRegex(ValueError, "exceeds"):
            validate_snapshot([observation(), observation(2)])

    def test_unknown_metadata_is_not_compared_or_mutated(self) -> None:
        old = observation()
        new = deepcopy(old)
        old["author"] = "first"
        new["author"] = "second"
        old["score_breakdown"] = [{"label": "custom", "risk_delta": 30, "kind": "flag"}]
        new["files"] = {"total_files": 100}
        self.assertEqual(compare_snapshots([old], [new])["summary"]["unchanged"], 1)
        self.assertEqual(new["files"], {"total_files": 100})


class ComparisonCliTests(unittest.TestCase):
    def test_cli_does_not_score_read_config_call_network_or_modify_inputs(self) -> None:
        with TemporaryDirectory() as workdir:
            paths = [Path(workdir) / name for name in ("before.json", "after.json")]
            for path in paths:
                path.write_text(json.dumps([observation()]))
            original = [path.read_bytes() for path in paths]
            for args in (["compare", *map(str, paths), "--format", "json"],
                         ["--format", "json", "compare", *map(str, paths)],
                         ["compare", *map(str, paths)]):
                with patch("maintainer_radar.cli.load_config") as config, \
                        patch("maintainer_radar.cli.analyze_pr") as score, \
                        patch("maintainer_radar.cli.list_repo_prs") as fetch, \
                        patch("sys.stdout", new_callable=StringIO) as stdout:
                    self.assertEqual(main(args), 0)
                    self.assertTrue(stdout.getvalue())
                    config.assert_not_called()
                    score.assert_not_called()
                    fetch.assert_not_called()
                self.assertEqual([path.read_bytes() for path in paths], original)

    def test_invalid_second_snapshot_has_no_partial_stdout_and_no_writes(self) -> None:
        with TemporaryDirectory() as workdir:
            before = Path(workdir) / "before.json"
            after = Path(workdir) / "after.json"
            before.write_text(json.dumps([observation()]))
            after.write_bytes(b"[false]")
            original = [path.read_bytes() for path in (before, after)]
            with patch("sys.stdout", new_callable=StringIO) as stdout, \
                    patch("sys.stderr", new_callable=StringIO) as stderr:
                self.assertEqual(main(["compare", str(before), str(after)]), 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("invalid snapshot", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual([path.read_bytes() for path in (before, after)], original)

    def test_missing_file_and_unsupported_global_format_fail_cleanly(self) -> None:
        for args in (["compare", "/no/such/before.json", "/no/such/after.json"],
                     ["--format", "html", "compare", "before.json", "after.json"]):
            with patch("sys.stdout", new_callable=StringIO) as stdout, \
                    patch("sys.stderr", new_callable=StringIO) as stderr:
                self.assertEqual(main(args), 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_fictional_examples_match_committed_reports(self) -> None:
        before = load_snapshot(ROOT / "examples/snapshots/before.json")
        after = load_snapshot(ROOT / "examples/snapshots/after.json")
        result = compare_snapshots(before, after)
        self.assertEqual(result["summary"], {"before": 3, "after": 3, "newly_observed": 1,
                                          "no_longer_observed": 1, "changed": 1, "unchanged": 1})
        for fmt, extension in (("markdown", "md"), ("json", "json")):
            self.assertEqual(render_comparison(result, fmt),
                             (ROOT / f"examples/output/sample-comparison.{extension}").read_text())


if __name__ == "__main__":
    unittest.main()
