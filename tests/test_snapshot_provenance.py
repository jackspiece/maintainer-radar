from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from maintainer_radar import __version__
from maintainer_radar.cli import main
from maintainer_radar.compare import compare_snapshots, load_snapshot, render_comparison, validate_snapshot
from maintainer_radar.config import DEFAULT_CONFIG
from maintainer_radar.snapshot import SNAPSHOT_KIND, snapshot_parts

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-06-01T00:00:00Z"


def envelope() -> dict:
    return {
        "kind": SNAPSHOT_KIND, "schema_version": 1,
        "provenance": {
            "radar_version": __version__, "analysis_time": NOW,
            "config": deepcopy(DEFAULT_CONFIG),
            "capture": {
                "command": "repo", "source": "github", "repository": "owner/repo", "author": None,
                "state": "open", "limit": 30, "hydrate": True,
                "filters": {"label": None, "author": None, "stale_days": None, "updated_since": None,
                            "action": None, "min_score": None, "max_risk": None},
                "sort": "input", "top": None,
            },
            "counts": {"observed": 0, "emitted": 0},
        },
        "items": [],
    }


def run_cli(args: list[str]) -> tuple[int, str, str]:
    with patch("sys.stdout", new_callable=StringIO) as stdout, patch("sys.stderr", new_callable=StringIO) as stderr:
        code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()


class ProvenanceTests(unittest.TestCase):
    def test_settings_match_is_qualified_and_time_counts_are_only_context(self) -> None:
        before = envelope()
        after = deepcopy(before)
        after["provenance"]["analysis_time"] = "2026-06-02T08:00:00+08:00"
        after["provenance"]["counts"]["observed"] = 5
        report = compare_snapshots(before, after)
        self.assertEqual(report["provenance"]["status"], "recorded-settings-match")
        self.assertEqual(report["provenance"]["differences"], [])
        markdown = render_comparison(report)
        self.assertIn("does not prove comparable coverage", markdown)
        self.assertIn("observed 5, emitted 0", markdown)
        self.assertIn("self-reported", markdown)
        self.assertIn("Offline export coverage and hydration are unknown", markdown)

    def test_each_recorded_setting_difference_is_visible_without_rescoring(self) -> None:
        before = envelope()
        after = deepcopy(before)
        data = after["provenance"]
        data["radar_version"] = "0.22.0"
        data["config"]["large_diff_lines"] = 300
        data["config"]["test_hints"] = ["specs/"]
        data["capture"].update(repository="owner/other", state="all", limit=50, hydrate=False, sort="score", top=10)
        data["capture"]["filters"].update(label="review", author="alice", stale_days=7,
                                             updated_since="2026-05-01", action="review-now", min_score=80, max_risk=20)
        report = compare_snapshots(before, after)
        self.assertEqual(report["provenance"]["status"], "recorded-settings-differ")
        differences = {item["field"]: item for item in report["provenance"]["differences"]}
        self.assertEqual(len(differences), 16)
        self.assertEqual(differences["config.large_diff_lines"],
                         {"field": "config.large_diff_lines", "before": 500, "after": 300})
        self.assertEqual(report["summary"]["changed"], 0)
        self.assertEqual(json.loads(render_comparison(report, "json")), report)
        self.assertIn("Interpret score and queue changes with caution", render_comparison(report))
        self.assertIn("| config.large_diff_lines | 500 | 300 |", render_comparison(report))
        self.assertEqual(before, envelope())

    def test_mixed_legacy_inputs_preserve_known_provenance_and_report_unknown(self) -> None:
        for before, after in (([], envelope()), (envelope(), [])):
            with self.subTest(before=type(before)):
                report = compare_snapshots(before, after)
                self.assertEqual(report["provenance"]["status"], "unknown")
                self.assertEqual(report["provenance"]["differences"], [])
                self.assertIn("legacy array without provenance", render_comparison(report))
        legacy = compare_snapshots([], [])
        self.assertNotIn("provenance", legacy)
        self.assertIn("queue JSON does not record", render_comparison(legacy))

    def test_provenance_markdown_does_not_interpret_untrusted_text(self) -> None:
        before = envelope()
        after = deepcopy(before)
        hostile = '[bad](https://evil.invalid/)|<img src=x>&copy;`code`'
        after["provenance"]["radar_version"] = hostile
        after["provenance"]["config"]["test_hints"] = [hostile]
        after["provenance"]["capture"]["filters"]["label"] = hostile
        report = compare_snapshots(before, after)
        markdown = render_comparison(report)
        for fragment in ("<img", "&copy;", "`code`", "](https://evil.invalid/)"):
            self.assertNotIn(fragment, markdown)
        for line in markdown.splitlines():
            if line.startswith("|"):
                self.assertEqual(line.count("|"), 4)
        self.assertEqual(json.loads(render_comparison(report, "json"))["provenance"]["after"]
                         ["capture"]["filters"]["label"], hostile)

    def test_wrong_or_ambiguous_envelopes_fail(self) -> None:
        for field, values in {
            "kind": [None, "other", True, {}],
            "schema_version": [True, 0, 2, "1", 1.0, []],
            "provenance": [None, {}, [], "yes"], "items": [None, {}, "[]", 1],
        }.items():
            for value in values:
                data = envelope()
                data[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_snapshot(data)
        for key in envelope():
            data = envelope()
            del data[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_snapshot(data)
        data = envelope()
        data["extra"] = "ambiguous metadata"
        with self.assertRaises(ValueError):
            validate_snapshot(data)

    def test_metadata_rejects_missing_extra_and_wrong_nested_fields(self) -> None:
        paths = (("provenance",), ("provenance", "config"), ("provenance", "capture"),
                 ("provenance", "capture", "filters"), ("provenance", "counts"))
        for path in paths:
            for mutation in ("missing", "extra", "type"):
                data = envelope()
                target = data
                for key in path[:-1]:
                    target = target[key]
                item = target[path[-1]]
                if mutation == "missing":
                    item.pop(next(iter(item)))
                elif mutation == "extra":
                    item["unexpected"] = 1
                else:
                    target[path[-1]] = []
                with self.subTest(path=path, mutation=mutation), self.assertRaises(ValueError):
                    validate_snapshot(data)

    def test_metadata_values_fail_cleanly(self) -> None:
        cases = {
            ("radar_version",): [None, [], "", "bad\ud800", "line\nbreak"],
            ("analysis_time",): [None, "2026-06-01", "not-a-time", "2026-06-01T00:00:00"],
            ("config", "large_diff_lines"): [True, -1, 0.5, "3", {}],
            ("config", "test_hints"): ["tests/", [None], [""], ["bad\udfff"]],
            ("capture", "command"): [None, [], "pr"],
            ("capture", "source"): [False, "bitbucket"],
            ("capture", "repository"): [None, "", 12],
            ("capture", "author"): ["unexpected"],
            ("capture", "limit"): [None, True, -1, 0, "30"],
            ("capture", "hydrate"): [None, 1, "true"],
            ("capture", "state"): [[], {}, "draft"],
            ("capture", "sort"): [[], {}, "custom"],
            ("capture", "top"): [True, -1, 0, "2"],
            ("capture", "filters", "min_score"): [True, -1, 101, 1.5],
            ("capture", "filters", "max_risk"): [False, -1, 101],
            ("capture", "filters", "stale_days"): [True, -1, 2.5],
            ("capture", "filters", "label"): [[], "", "bad\nlabel"],
            ("counts", "observed"): [True, -1, 0.5, "0"],
            ("counts", "emitted"): [False, -1, 1, "0"],
        }
        for path, values in cases.items():
            for value in values:
                data = envelope()
                target = data["provenance"]
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                    validate_snapshot(data)

    def test_offline_scope_cannot_claim_live_hydration_or_coverage(self) -> None:
        data = envelope()
        capture = data["provenance"]["capture"]
        capture.update(command="from-json", source="gitlab", repository=None, author=None,
                       state=None, limit=None, hydrate=None)
        self.assertEqual(validate_snapshot(data), [])
        for key, value in (("hydrate", True), ("limit", 50), ("repository", "team/repo")):
            malformed = deepcopy(data)
            malformed["provenance"]["capture"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_snapshot(malformed)
        data["provenance"]["capture"]["filters"]["label"] = "docs"
        with self.assertRaises(ValueError):
            validate_snapshot(data)

    def test_loader_preserves_provenance_and_keeps_strict_read_limits(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(envelope()))
            original = path.read_bytes()
            self.assertEqual(load_snapshot(path), envelope())
            self.assertEqual(path.read_bytes(), original)
            with patch("maintainer_radar.compare.MAX_SNAPSHOT_BYTES", 10), self.assertRaises(ValueError):
                load_snapshot(path)
            path.write_text(json.dumps(envelope()).replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_snapshot(path)
            data = envelope()
            data["items"] = json.loads((ROOT / "examples/output/sample-report.json").read_text())
            data["provenance"]["counts"] = {"observed": 2, "emitted": 2}
            with patch("maintainer_radar.compare.MAX_SNAPSHOT_RECORDS", 1), self.assertRaisesRegex(ValueError, "exceeds"):
                validate_snapshot(data)


class SnapshotCliTests(unittest.TestCase):
    def test_default_arrays_stay_byte_identical_and_fixed_time_snapshots_repeat(self) -> None:
        args = ["from-json", str(ROOT / "examples/sample-prs.json"), "--format", "json", "--now", NOW]
        code, plain, error = run_cli(args)
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(plain, (ROOT / "examples/output/sample-report.json").read_text())
        code, captured, error = run_cli([*args, "--snapshot"])
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(run_cli([*args, "--snapshot"])[1], captured)
        data = json.loads(captured)
        self.assertEqual(data["items"], json.loads(plain))
        provenance = data["provenance"]
        self.assertEqual(provenance["radar_version"], __version__)
        self.assertEqual(provenance["analysis_time"], NOW)
        self.assertEqual(provenance["counts"], {"observed": 2, "emitted": 2})
        self.assertEqual(provenance["capture"]["hydrate"], None)
        self.assertEqual(provenance["config"], DEFAULT_CONFIG)
        self.assertNotIn(str(ROOT), captured)
        self.assertNotIn("sample-prs.json", captured)
        self.assertNotIn(".maintainer-radar.json", captured)
        validate_snapshot(data)

    def test_implicit_clock_is_the_same_time_used_for_all_scoring(self) -> None:
        fixed = datetime(2026, 6, 1, tzinfo=timezone.utc)
        from maintainer_radar.scoring import analyze_pr
        with patch("maintainer_radar.cli.datetime") as clock, \
                patch("maintainer_radar.cli.analyze_pr", wraps=analyze_pr) as scoring:
            clock.now.return_value = fixed
            code, output, error = run_cli(["from-json", str(ROOT / "examples/sample-prs.json"),
                                           "--format", "json", "--snapshot"])
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["provenance"]["analysis_time"], NOW)
            clock.now.assert_called_once_with(timezone.utc)
            self.assertEqual(len(scoring.call_args_list), 2)
            self.assertTrue(all(call.kwargs["now"] is fixed for call in scoring.call_args_list))

    def test_snapshot_clock_utc_overflow_fails_before_fetch_or_input_read(self) -> None:
        values = ("0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00",
                  "0001-01-01T00:59:59.999999+01:00", "9999-12-31T23:00:00-01:00")
        commands = (["from-json", "missing.json"], ["repo", "owner/repo"], ["author", "alice"])
        for value in values:
            for command in commands:
                with self.subTest(value=value, command=command), \
                        patch("maintainer_radar.cli._load_json") as load, \
                        patch("maintainer_radar.cli.list_repo_prs") as repo, \
                        patch("maintainer_radar.cli.search_author_prs") as author:
                    code, output, error = run_cli([*command, "--format", "json", "--snapshot", "--now", value])
                    self.assertEqual((code, output), (2, ""))
                    self.assertEqual(error, "maintainer-radar: --now is outside the supported UTC date range\n")
                    for source in (load, repo, author):
                        source.assert_not_called()

    def test_snapshot_clock_accepts_utc_extremes_and_preserves_normal_scoring(self) -> None:
        values = (
            ("0001-01-01T00:00:00Z", "0001-01-01T00:00:00Z"),
            ("9999-12-31T23:59:59.999999Z", "9999-12-31T23:59:59.999999Z"),
            ("0001-01-01T01:00:00+01:00", "0001-01-01T00:00:00Z"),
            ("9999-12-31T22:59:59.999999-01:00", "9999-12-31T23:59:59.999999Z"),
            ("0001-01-01T00:00:00-01:00", "0001-01-01T01:00:00Z"),
            ("9999-12-31T23:59:59.999999+01:00", "9999-12-31T22:59:59.999999Z"),
            ("0001-01-01", "0001-01-01T00:00:00Z"),
            ("9999-12-31T23:59:59.999999", "9999-12-31T23:59:59.999999Z"),
            ("2026-06-01T08:00:00+08:00", NOW),
            ("2026-05-31T19:00:00-05:00", NOW),
            (NOW, NOW),
        )
        for value, expected in values:
            with self.subTest(value=value):
                args = ["from-json", str(ROOT / "examples/sample-prs.json"), "--format", "json", "--now", value]
                code, plain, error = run_cli(args)
                self.assertEqual((code, error), (0, ""))
                code, output, error = run_cli([*args, "--snapshot"])
                self.assertEqual((code, error), (0, ""))
                data = json.loads(output)
                self.assertEqual(data["provenance"]["analysis_time"], expected)
                self.assertEqual(data["items"], json.loads(plain))
                validate_snapshot(data)

    def test_non_snapshot_clock_keeps_boundary_offsets_accepted(self) -> None:
        for value in ("0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"):
            with self.subTest(value=value):
                code, output, error = run_cli(["from-json", str(ROOT / "examples/sample-prs.json"),
                                               "--format", "json", "--now", value])
                self.assertEqual((code, error), (0, ""))
                self.assertEqual(len(json.loads(output)), 2)

    def test_malformed_clock_keeps_existing_diagnostic(self) -> None:
        for value in ("not-a-time", "0000-01-01T00:00:00Z", "10000-01-01T00:00:00Z"):
            for options in ([], ["--snapshot"]):
                with self.subTest(value=value, options=options), patch("maintainer_radar.cli._load_json") as load:
                    code, output, error = run_cli(["from-json", "missing.json", "--format", "json",
                                                   "--now", value, *options])
                    self.assertEqual((code, output), (2, ""))
                    self.assertEqual(error, "maintainer-radar: --now must be an ISO date, for example 2026-06-01\n")
                    load.assert_not_called()

    def test_effective_config_records_defaults_and_overrides_not_path(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "private-configuration.json"
            path.write_text('{"large_diff_lines": 300, "test_hints": [" SPECS/ "]}')
            code, output, error = run_cli(["from-json", str(ROOT / "examples/sample-prs.json"),
                                          "--config", str(path), "--format", "json", "--snapshot", "--now", NOW])
            self.assertEqual((code, error), (0, ""))
            config = json.loads(output)["provenance"]["config"]
            self.assertEqual(config, {**DEFAULT_CONFIG, "large_diff_lines": 300, "test_hints": ["specs/"]})
            self.assertNotIn(directory, output)
            self.assertNotIn(path.name, output)

    def test_live_repo_records_scope_and_prefilter_count(self) -> None:
        prs = json.loads((ROOT / "examples/sample-prs.json").read_text())
        with patch("maintainer_radar.cli.list_repo_prs", return_value=prs) as fetch, \
                patch("maintainer_radar.cli.hydrate_prs", side_effect=lambda records, **kw: records) as hydrate:
            code, output, error = run_cli(["repo", "https://github.com/owner/repo/pulls", "--limit", "50",
                                          "--hydrate", "--top", "1", "--sort", "score", "--format", "json",
                                          "--snapshot", "--now", NOW])
            self.assertEqual((code, error), (0, ""))
            fetch.assert_called_once_with("owner/repo", state="open", limit=50)
            hydrate.assert_called_once()
            data = json.loads(output)
            self.assertEqual(data["provenance"]["counts"], {"observed": 2, "emitted": 1})
            capture = data["provenance"]["capture"]
            self.assertEqual(capture["repository"], "owner/repo")
            self.assertEqual(capture["limit"], 50)
            self.assertEqual(capture["hydrate"], True)
            self.assertEqual(capture["sort"], "score")
            self.assertEqual(capture["top"], 1)
            validate_snapshot(data)
        with patch("maintainer_radar.cli.list_repo_prs", return_value=prs):
            code, output, error = run_cli(["repo", "owner/repo", "--label", "no-matching-label",
                                          "--format", "json", "--snapshot", "--now", NOW])
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["provenance"]["counts"], {"observed": 2, "emitted": 0})
            self.assertEqual(json.loads(output)["provenance"]["capture"]["filters"]["label"], "no-matching-label")

    def test_author_capture_is_distinct_from_repo_author_filter(self) -> None:
        with patch("maintainer_radar.cli.search_author_prs", return_value=[]) as fetch:
            code, output, error = run_cli(["--format", "json", "author", "alice", "--snapshot", "--state", "closed",
                                          "--max-risk", "20", "--now", NOW])
            self.assertEqual((code, error), (0, ""))
            fetch.assert_called_once_with("alice", state="closed", limit=50)
            data = json.loads(output)
            capture = data["provenance"]["capture"]
            self.assertEqual(capture["author"], "alice")
            self.assertIsNone(capture["repository"])
            self.assertIsNone(capture["filters"]["author"])
            self.assertEqual(capture["filters"]["max_risk"], 20)
            validate_snapshot(data)

    def test_all_offline_source_shapes_and_stdin_have_unknown_scope(self) -> None:
        for source, name in (("gitlab", "gitlab-merge-requests.json"), ("forgejo", "forgejo-pull-requests.json"),
                             ("gitea", "forgejo-pull-requests.json")):
            with self.subTest(source=source):
                code, output, error = run_cli(["from-json", str(ROOT / "tests/fixtures" / name), "--source", source,
                                              "--snapshot", "--format", "json", "--now", NOW])
                self.assertEqual((code, error), (0, ""))
                data = json.loads(output)
                self.assertEqual(data["provenance"]["capture"]["source"], source)
                validate_snapshot(data)
        with patch("sys.stdin", StringIO("[]")):
            code, output, error = run_cli(["from-json", "-", "--snapshot", "--format", "json", "--now", NOW])
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["items"], [])

    def test_invalid_modes_and_settings_fail_before_fetch_or_input_read(self) -> None:
        options = (["--format", "markdown"], ["--format", "csv"], ["--summary-only"],
                   ["--review-plan-minutes", "10"], ["--group-by", "action"], ["--top", "0"],
                   ["--limit", "0"], ["--min-score", "101"], ["--max-risk", "-1"],
                   ["--updated-since", "not-a-date"])
        for extra in options:
            with self.subTest(extra=extra), patch("maintainer_radar.cli.list_repo_prs") as fetch:
                code, output, error = run_cli(["repo", "owner/repo", "--format", "json", "--snapshot", *extra])
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertNotIn("Traceback", error)
                fetch.assert_not_called()
        with patch("maintainer_radar.cli._load_json") as load:
            code, output, error = run_cli(["from-json", "missing.json", "--snapshot", "--format", "json", "--detail"])
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            load.assert_not_called()

    def test_emitted_snapshot_is_bounded_and_records_require_qualified_urls(self) -> None:
        args = ["from-json", str(ROOT / "examples/sample-prs.json"), "--snapshot", "--format", "json", "--now", NOW]
        with patch("maintainer_radar.cli.MAX_SNAPSHOT_BYTES", 1):
            code, output, error = run_cli(args)
            self.assertEqual((code, output), (2, ""))
            self.assertIn("exceeds", error)
        with patch("sys.stdin", StringIO('[{"number": 1, "title": "No URL"}]')):
            code, output, error = run_cli(["from-json", "-", "--snapshot", "--format", "json"])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("url", error)

    def test_compare_never_reads_config_rescores_or_calls_network(self) -> None:
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("before.json", "after.json")]
            for path in paths:
                path.write_text(json.dumps(envelope()))
            originals = [path.read_bytes() for path in paths]
            with patch("maintainer_radar.cli.load_config") as config, patch("maintainer_radar.cli.analyze_pr") as score, \
                    patch("maintainer_radar.cli.list_repo_prs") as fetch, patch("maintainer_radar.cli.view_pr") as detail:
                code, output, error = run_cli(["compare", *map(str, paths), "--format", "json"])
                self.assertEqual((code, error), (0, ""))
                self.assertEqual(json.loads(output)["provenance"]["status"], "recorded-settings-match")
                for mock in (config, score, fetch, detail):
                    mock.assert_not_called()
            self.assertEqual([path.read_bytes() for path in paths], originals)
            data = envelope()
            del data["provenance"]["capture"]["limit"]
            paths[1].write_text(json.dumps(data))
            code, output, error = run_cli(["compare", *map(str, paths)])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("invalid snapshot", error)
            self.assertNotIn("Traceback", error)

    def test_config_only_demo_explains_an_observation_difference(self) -> None:
        before = load_snapshot(ROOT / "examples/output/sample-snapshot.json")
        after = load_snapshot(ROOT / "examples/output/sample-snapshot-lower-threshold.json")
        report = compare_snapshots(before, after)
        self.assertEqual(report["provenance"]["differences"], [
            {"field": "config.large_diff_lines", "before": 500, "after": 50},
        ])
        self.assertEqual(report["summary"]["changed"], 1)
        self.assertEqual(report["changed"][0]["number"], 42)
        self.assertEqual(report["changed"][0]["before"]["risk"], 0)
        self.assertEqual(report["changed"][0]["after"]["risk"], 7)
        for fmt, extension in (("markdown", "md"), ("json", "json")):
            self.assertEqual(render_comparison(report, fmt),
                             (ROOT / f"examples/output/sample-provenance-comparison.{extension}").read_text())

    def test_counts_cannot_disagree_with_observations_or_top(self) -> None:
        data = json.loads((ROOT / "examples/output/sample-snapshot.json").read_text())
        data["provenance"]["counts"]["observed"] = 1
        with self.assertRaisesRegex(ValueError, "observed must be"):
            validate_snapshot(data)
        data["provenance"]["counts"]["observed"] = 2
        data["provenance"]["capture"]["top"] = 1
        with self.assertRaisesRegex(ValueError, "capture.top"):
            validate_snapshot(data)

    def test_snapshot_parts_does_not_mutate_input(self) -> None:
        data = envelope()
        original = deepcopy(data)
        records, provenance = snapshot_parts(data)
        self.assertEqual(records, [])
        self.assertEqual(provenance, data["provenance"])
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
