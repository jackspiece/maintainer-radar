from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from maintainer_radar.cli import (
    _as_pr_list,
    _load_json,
    _normalize_repository_arg,
    _parse_pr_reference,
    _parse_now,
    build_parser,
    filter_analyses,
    filter_prs,
    hydrate_prs,
    limit_analyses,
    main,
    sort_analyses,
)


class CliTests(unittest.TestCase):
    def test_invalid_json_items_fail_without_traceback(self) -> None:
        for payload in ('[null]', '{"items": [42]}'):
            with self.subTest(payload=payload), patch("sys.stdin", StringIO(payload)), \
                    patch("sys.stderr", new_callable=StringIO) as stderr:
                self.assertEqual(main(["from-json", "-"]), 2)
                self.assertIn("must be an object", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_explicit_missing_config_fails_before_github_request(self) -> None:
        with patch("maintainer_radar.cli.list_repo_prs") as fetch, \
                patch("sys.stderr", new_callable=StringIO) as stderr:
            self.assertEqual(main(["repo", "owner/repo", "--config", "/no/such/config.json"]), 2)
            fetch.assert_not_called()
            self.assertIn("config.json", stderr.getvalue())

    def test_format_works_before_subcommand(self) -> None:
        args = build_parser().parse_args(
            ["--format", "json", "from-json", "examples/sample-prs.json"]
        )

        self.assertEqual(args.format, "json")
        self.assertEqual(args.command, "from-json")

    def test_format_works_after_subcommand(self) -> None:
        args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--format", "json"]
        )

        self.assertEqual(args.format, "json")
        self.assertEqual(args.command, "from-json")

    def test_csv_format_is_available(self) -> None:
        args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--format", "csv"]
        )

        self.assertEqual(args.format, "csv")

    def test_html_format_is_available(self) -> None:
        args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--format", "html"]
        )

        self.assertEqual(args.format, "html")

    def test_summary_only_flag_is_available_for_queue_commands(self) -> None:
        repo_args = build_parser().parse_args(["repo", "owner/repo", "--summary-only"])
        author_args = build_parser().parse_args(["author", "alice", "--summary-only"])
        json_args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--summary-only"]
        )

        self.assertTrue(repo_args.summary_only)
        self.assertTrue(author_args.summary_only)
        self.assertTrue(json_args.summary_only)

    def test_action_score_and_risk_flags_parse(self) -> None:
        args = build_parser().parse_args(
            [
                "repo",
                "owner/repo",
                "--action",
                "review-now",
                "--min-score",
                "80",
                "--max-risk",
                "20",
            ]
        )

        self.assertEqual(args.action, "review-now")
        self.assertEqual(args.min_score, 80)
        self.assertEqual(args.max_risk, 20)

    def test_sort_flag_is_available_for_queue_commands(self) -> None:
        repo_args = build_parser().parse_args(["repo", "owner/repo", "--sort", "action"])
        author_args = build_parser().parse_args(["author", "alice", "--sort", "risk"])
        json_args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--sort", "stale"]
        )

        self.assertEqual(repo_args.sort, "action")
        self.assertEqual(author_args.sort, "risk")
        self.assertEqual(json_args.sort, "stale")

    def test_hydrate_flag_is_available_for_live_queue_commands(self) -> None:
        repo_args = build_parser().parse_args(["repo", "owner/repo", "--hydrate"])
        author_args = build_parser().parse_args(["author", "alice", "--hydrate"])

        self.assertTrue(repo_args.hydrate)
        self.assertTrue(author_args.hydrate)

    def test_top_flag_is_available_for_queue_commands(self) -> None:
        repo_args = build_parser().parse_args(["repo", "owner/repo", "--top", "5"])
        author_args = build_parser().parse_args(["author", "alice", "--top", "3"])
        json_args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--top", "1"]
        )

        self.assertEqual(repo_args.top, 5)
        self.assertEqual(author_args.top, 3)
        self.assertEqual(json_args.top, 1)

    def test_group_by_flag_is_available_for_queue_commands(self) -> None:
        repo_args = build_parser().parse_args(["repo", "owner/repo", "--group-by", "action"])
        author_args = build_parser().parse_args(["author", "alice", "--group-by", "action"])
        json_args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--group-by", "action"]
        )

        self.assertEqual(repo_args.group_by, "action")
        self.assertEqual(author_args.group_by, "action")
        self.assertEqual(json_args.group_by, "action")

    def test_review_plan_minutes_flag_is_available_for_queue_commands(self) -> None:
        repo_args = build_parser().parse_args(
            ["repo", "owner/repo", "--review-plan-minutes", "30"]
        )
        author_args = build_parser().parse_args(
            ["author", "alice", "--review-plan-minutes", "20"]
        )
        json_args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--review-plan-minutes", "45"]
        )

        self.assertEqual(repo_args.review_plan_minutes, 30)
        self.assertEqual(author_args.review_plan_minutes, 20)
        self.assertEqual(json_args.review_plan_minutes, 45)

    def test_comment_template_flag_is_available_for_pr_command(self) -> None:
        args = build_parser().parse_args(["pr", "owner/repo", "123", "--comment-template"])

        self.assertTrue(args.comment_template)

    def test_pr_command_accepts_pr_url_without_number(self) -> None:
        args = build_parser().parse_args(["pr", "https://github.com/owner/repo/pull/123"])

        self.assertEqual(args.repository, "https://github.com/owner/repo/pull/123")
        self.assertIsNone(args.number)

    def test_recommend_command_accepts_repo_url_and_defaults_to_hydration(self) -> None:
        args = build_parser().parse_args(
            ["recommend", "https://github.com/owner/repo/pulls", "--limit", "5"]
        )

        self.assertEqual(args.command, "recommend")
        self.assertEqual(args.repository, "https://github.com/owner/repo/pulls")
        self.assertEqual(args.limit, 5)
        self.assertFalse(args.no_hydrate)

    def test_recommend_command_emits_markdown_next_commands(self) -> None:
        with patch(
            "maintainer_radar.cli.list_repo_prs",
            return_value=[{"number": 1, "title": "Fix parser"}],
        ) as list_repo_prs, patch(
            "maintainer_radar.cli.view_pr",
            return_value={"number": 1, "body": "Test plan: unit tests."},
        ) as view_pr, patch(
            "maintainer_radar.cli.analyze_pr",
            return_value={
                "number": 1,
                "title": "Fix parser",
                "action": "review now",
                "reviewability": 90,
                "risk": 10,
                "stale_days": 0,
                "signals": ["CI passed"],
                "flags": [],
            },
        ), patch("sys.stdout", new=StringIO()) as stdout:
            result = main(["recommend", "https://github.com/owner/repo/pulls"])

        output = stdout.getvalue()

        self.assertEqual(result, 0)
        list_repo_prs.assert_called_once_with("owner/repo", state="open", limit=30)
        view_pr.assert_called_once_with("owner/repo", 1)
        self.assertIn("Maintainer Radar Recommendation", output)
        self.assertIn("Workflow: `review-sprint`", output)
        self.assertIn("maintainer-radar repo owner/repo --hydrate --action review-now", output)

    def test_recommend_command_can_skip_hydration_and_emit_json(self) -> None:
        with patch(
            "maintainer_radar.cli.list_repo_prs",
            return_value=[{"number": 2, "title": "Fix CI"}],
        ) as list_repo_prs, patch("maintainer_radar.cli.view_pr") as view_pr, patch(
            "maintainer_radar.cli.analyze_pr",
            return_value={
                "number": 2,
                "title": "Fix CI",
                "action": "ask for CI fix",
                "reviewability": 20,
                "risk": 80,
                "stale_days": 0,
                "flags": ["CI failing"],
            },
        ), patch("sys.stdout", new=StringIO()) as stdout:
            result = main(["recommend", "owner/repo", "--no-hydrate", "--format", "json"])

        output = json.loads(stdout.getvalue())

        self.assertEqual(result, 0)
        list_repo_prs.assert_called_once_with("owner/repo", state="open", limit=30)
        view_pr.assert_not_called()
        self.assertEqual(output["workflow_mode"], "blocker-sweep")
        self.assertIn("--sort action --group-by action", output["commands"]["focused_report"])

    def test_repository_arg_accepts_common_github_url_shapes(self) -> None:
        cases = {
            "owner/repo": "owner/repo",
            "owner/repo/pulls": "owner/repo",
            "https://github.com/owner/repo": "owner/repo",
            "https://github.com/owner/repo/": "owner/repo",
            "https://github.com/owner/repo.git": "owner/repo",
            "https://github.com/owner/repo/pulls": "owner/repo",
            "github.com/owner/repo/pull/123": "owner/repo",
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(_normalize_repository_arg(value), expected)

    def test_parse_pr_reference_accepts_url_or_explicit_number(self) -> None:
        self.assertEqual(
            _parse_pr_reference("https://github.com/owner/repo/pull/123", None),
            ("owner/repo", "123"),
        )
        self.assertEqual(
            _parse_pr_reference("https://github.com/owner/repo/pulls", "77"),
            ("owner/repo", "77"),
        )
        with self.assertRaises(ValueError):
            _parse_pr_reference("owner/repo", None)

    def test_repo_command_normalizes_github_urls_before_fetching(self) -> None:
        with patch("maintainer_radar.cli.list_repo_prs", return_value=[]) as list_repo_prs, patch(
            "sys.stdout", new=StringIO()
        ):
            result = main(
                [
                    "repo",
                    "https://github.com/owner/repo/pulls",
                    "--summary-only",
                ]
            )

        self.assertEqual(result, 0)
        list_repo_prs.assert_called_once_with("owner/repo", state="open", limit=30)

    def test_pr_command_normalizes_github_pr_url_before_fetching(self) -> None:
        with patch(
            "maintainer_radar.cli.view_pr",
            return_value={"number": 123, "title": "Fix bug"},
        ) as view_pr, patch(
            "maintainer_radar.cli.analyze_pr",
            return_value={
                "number": 123,
                "title": "Fix bug",
                "action": "needs triage",
                "next_step": "Triage manually before assigning reviewer time.",
                "reviewability": 50,
                "risk": 50,
            },
        ), patch("sys.stdout", new=StringIO()):
            result = main(["pr", "https://github.com/owner/repo/pull/123"])

        self.assertEqual(result, 0)
        view_pr.assert_called_once_with("owner/repo", "123")

    def test_init_action_command_accepts_report_options(self) -> None:
        args = build_parser().parse_args(
            [
                "init-action",
                "--report-format",
                "html",
                "--schedule",
                "0 9 * * 1",
                "--limit",
                "25",
                "--sort",
                "risk",
                "--top",
                "10",
                "--group-by",
                "action",
                "--review-plan-minutes",
                "30",
                "--label",
                "bug",
                "--author",
                "alice",
                "--stale-days",
                "14",
                "--updated-since",
                "2026-06-01",
                "--action",
                "review-now",
                "--min-score",
                "80",
                "--max-risk",
                "20",
                "--config",
                ".maintainer-radar.json",
                "--no-hydrate",
                "--no-step-summary",
                "--path",
                ".github/workflows/maintainer-radar.yml",
                "--force",
            ]
        )

        self.assertEqual(args.command, "init-action")
        self.assertEqual(args.report_format, "html")
        self.assertEqual(args.schedule, "0 9 * * 1")
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.sort, "risk")
        self.assertEqual(args.top, 10)
        self.assertEqual(args.group_by, "action")
        self.assertEqual(args.review_plan_minutes, 30)
        self.assertEqual(args.label, "bug")
        self.assertEqual(args.author, "alice")
        self.assertEqual(args.stale_days, 14)
        self.assertEqual(args.updated_since, "2026-06-01")
        self.assertEqual(args.action, "review-now")
        self.assertEqual(args.min_score, 80)
        self.assertEqual(args.max_risk, 20)
        self.assertEqual(args.config, ".maintainer-radar.json")
        self.assertTrue(args.no_hydrate)
        self.assertTrue(args.no_step_summary)
        self.assertTrue(args.force)

    def test_init_action_writes_workflow_and_protects_existing_file(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / ".github" / "workflows" / "maintainer-radar.yml"

            with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
                first_result = main(
                    [
                        "init-action",
                        "--report-format",
                        "html",
                        "--config",
                        ".maintainer-radar.json",
                        "--action",
                        "review-now",
                        "--min-score",
                        "80",
                        "--group-by",
                        "action",
                        "--path",
                        str(path),
                    ]
                )
                second_result = main(
                    ["init-action", "--report-format", "html", "--path", str(path)]
                )
                forced_result = main(
                    [
                        "init-action",
                        "--report-format",
                        "html",
                        "--config",
                        ".maintainer-radar.json",
                        "--action",
                        "review-now",
                        "--min-score",
                        "80",
                        "--group-by",
                        "action",
                        "--path",
                        str(path),
                        "--force",
                    ]
                )

            output = path.read_text(encoding="utf-8")

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 2)
        self.assertEqual(forced_result, 0)
        self.assertIn("pull-requests: read", output)
        self.assertIn("uses: JackSpiece/maintainer-radar@", output)
        self.assertIn("format: html", output)
        self.assertIn('action: "review-now"', output)
        self.assertIn('min-score: "80"', output)
        self.assertIn('group-by: "action"', output)
        self.assertIn('config: ".maintainer-radar.json"', output)
        self.assertIn("maintainer-radar.html", output)

    def test_init_action_does_not_load_scoring_config(self) -> None:
        with patch("maintainer_radar.cli.load_config") as load_config, patch(
            "sys.stdout", new=StringIO()
        ):
            result = main(["init-action"])

        self.assertEqual(result, 0)
        load_config.assert_not_called()

    def test_init_action_supports_pinned_action_ref(self) -> None:
        pinned = "JackSpiece/maintainer-radar@0123456789abcdef0123456789abcdef01234567"

        with patch("sys.stdout", new=StringIO()) as stdout:
            result = main(["init-action", "--action-ref", pinned])

        self.assertEqual(result, 0)
        self.assertIn(f"uses: {pinned}", stdout.getvalue())

    def test_init_config_command_accepts_profile(self) -> None:
        args = build_parser().parse_args(
            [
                "init-config",
                "--profile",
                "strict",
                "--path",
                ".maintainer-radar.json",
                "--force",
            ]
        )

        self.assertEqual(args.command, "init-config")
        self.assertEqual(args.profile, "strict")
        self.assertEqual(args.path, ".maintainer-radar.json")
        self.assertTrue(args.force)

    def test_init_config_prints_profile_json(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            result = main(["init-config", "--profile", "large-repo"])

        output = json.loads(stdout.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(output["large_diff_lines"], 1000)
        self.assertEqual(output["stale_days"], 30)

    def test_init_config_writes_file_and_protects_existing_file(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / ".maintainer-radar.json"

            with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
                first_result = main(["init-config", "--profile", "strict", "--path", str(path)])
                second_result = main(["init-config", "--profile", "balanced", "--path", str(path)])
                forced_result = main(
                    [
                        "init-config",
                        "--profile",
                        "large-repo",
                        "--path",
                        str(path),
                        "--force",
                    ]
                )

            output = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 2)
        self.assertEqual(forced_result, 0)
        self.assertEqual(output["large_file_count"], 20)
        self.assertEqual(output["stale_days"], 30)

    def test_init_config_does_not_load_scoring_config(self) -> None:
        with patch("maintainer_radar.cli.load_config") as load_config, patch(
            "sys.stdout", new=StringIO()
        ):
            result = main(["init-config"])

        self.assertEqual(result, 0)
        load_config.assert_not_called()

    def test_init_repo_command_accepts_setup_options(self) -> None:
        args = build_parser().parse_args(
            [
                "init-repo",
                "--profile",
                "strict",
                "--config-path",
                ".maintainer-radar.json",
                "--workflow-path",
                ".github/workflows/radar.yml",
                "--report-format",
                "html",
                "--schedule",
                "0 9 * * 1",
                "--limit",
                "25",
                "--sort",
                "risk",
                "--group-by",
                "action",
                "--no-hydrate",
                "--no-step-summary",
                "--force",
            ]
        )

        self.assertEqual(args.command, "init-repo")
        self.assertEqual(args.profile, "strict")
        self.assertEqual(args.report_format, "html")
        self.assertEqual(args.schedule, "0 9 * * 1")
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.sort, "risk")
        self.assertEqual(args.group_by, "action")
        self.assertTrue(args.no_hydrate)
        self.assertTrue(args.no_step_summary)
        self.assertTrue(args.force)

    def test_init_repo_writes_config_and_workflow(self) -> None:
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".maintainer-radar.json"
            workflow_path = Path(tmp) / ".github" / "workflows" / "maintainer-radar.yml"

            with patch("sys.stdout", new=StringIO()) as stdout:
                result = main(
                    [
                        "init-repo",
                        "--profile",
                        "strict",
                        "--config-path",
                        str(config_path),
                        "--workflow-path",
                        str(workflow_path),
                    ]
                )

            config = json.loads(config_path.read_text(encoding="utf-8"))
            workflow = workflow_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertIn(f"Wrote {config_path}", stdout.getvalue())
        self.assertIn(f"Wrote {workflow_path}", stdout.getvalue())
        self.assertEqual(config["large_diff_lines"], 300)
        self.assertIn("contents: read", workflow)
        self.assertIn("pull-requests: read", workflow)
        self.assertIn('config: "', workflow)
        self.assertIn(str(config_path), workflow)
        self.assertIn('group-by: "action"', workflow)
        self.assertIn('hydrate: "true"', workflow)

    def test_init_repo_protects_existing_files_without_partial_write(self) -> None:
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".maintainer-radar.json"
            workflow_path = Path(tmp) / ".github" / "workflows" / "maintainer-radar.yml"
            workflow_path.parent.mkdir(parents=True)
            workflow_path.write_text("existing workflow", encoding="utf-8")

            with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()):
                result = main(
                    [
                        "init-repo",
                        "--profile",
                        "strict",
                        "--config-path",
                        str(config_path),
                        "--workflow-path",
                        str(workflow_path),
                    ]
                )

            self.assertEqual(result, 2)
            self.assertFalse(config_path.exists())
            self.assertEqual(workflow_path.read_text(encoding="utf-8"), "existing workflow")

    def test_init_repo_does_not_load_scoring_config(self) -> None:
        with TemporaryDirectory() as tmp, patch(
            "maintainer_radar.cli.load_config"
        ) as load_config, patch("sys.stdout", new=StringIO()):
            result = main(
                [
                    "init-repo",
                    "--config-path",
                    str(Path(tmp) / ".maintainer-radar.json"),
                    "--workflow-path",
                    str(Path(tmp) / ".github" / "workflows" / "maintainer-radar.yml"),
                ]
            )

        self.assertEqual(result, 0)
        load_config.assert_not_called()

    def test_as_pr_list_accepts_common_shapes(self) -> None:
        self.assertEqual(_as_pr_list({"number": 1}), [{"number": 1}])
        self.assertEqual(_as_pr_list([{"number": 1}]), [{"number": 1}])
        self.assertEqual(_as_pr_list({"items": [{"number": 1}]}), [{"number": 1}])

    def test_load_json_accepts_stdin_path(self) -> None:
        with patch("sys.stdin", StringIO('{"items": [{"number": 7}]}')):
            data = _load_json("-")

        self.assertEqual(data, {"items": [{"number": 7}]})

    def test_from_json_accepts_gitlab_source(self) -> None:
        args = build_parser().parse_args(
            ["from-json", "tests/fixtures/gitlab-merge-requests.json", "--source", "gitlab"]
        )

        self.assertEqual(args.source, "gitlab")

    def test_from_json_accepts_forgejo_and_gitea_sources(self) -> None:
        forgejo_args = build_parser().parse_args(
            ["from-json", "tests/fixtures/forgejo-pull-requests.json", "--source", "forgejo"]
        )
        gitea_args = build_parser().parse_args(
            ["from-json", "tests/fixtures/forgejo-pull-requests.json", "--source", "gitea"]
        )

        self.assertEqual(forgejo_args.source, "forgejo")
        self.assertEqual(gitea_args.source, "gitea")

    def test_config_flag_is_available_for_commands(self) -> None:
        args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--config", "config.json"]
        )

        self.assertEqual(args.config, "config.json")

    def test_now_flag_is_available_for_commands(self) -> None:
        args = build_parser().parse_args(
            ["from-json", "examples/sample-prs.json", "--now", "2026-06-01"]
        )

        self.assertEqual(args.now, "2026-06-01")

    def test_parse_now_accepts_iso_dates_and_rejects_invalid_values(self) -> None:
        self.assertIsNone(_parse_now(None))
        self.assertEqual(
            _parse_now("2026-06-01").isoformat(),
            "2026-06-01T00:00:00+00:00",
        )

        with self.assertRaises(ValueError):
            _parse_now("not-a-date")

    def test_filter_prs_supports_label_author_and_dates(self) -> None:
        prs = [
            {
                "number": 1,
                "author": {"login": "alice"},
                "labels": [{"name": "bug"}],
                "updatedAt": "2026-06-01T00:00:00Z",
            },
            {
                "number": 2,
                "author": {"login": "bob"},
                "labels": [{"name": "docs"}],
                "updatedAt": "2026-05-01T00:00:00Z",
            },
        ]

        self.assertEqual([pr["number"] for pr in filter_prs(prs, label="bug")], [1])
        self.assertEqual([pr["number"] for pr in filter_prs(prs, author="bob")], [2])
        self.assertEqual(
            [pr["number"] for pr in filter_prs(prs, updated_since="2026-05-15")],
            [1],
        )

    def test_filter_prs_stale_days_respects_now_override(self) -> None:
        prs = [
            {"number": 1, "updatedAt": "2026-05-20T00:00:00Z"},
            {"number": 2, "updatedAt": "2026-05-31T00:00:00Z"},
        ]
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)

        self.assertEqual(
            [pr["number"] for pr in filter_prs(prs, stale_days=5, now=now)],
            [1],
        )

    def test_filter_analyses_supports_action_score_and_risk(self) -> None:
        analyses = [
            {"number": 1, "action": "review now", "reviewability": 90, "risk": 10},
            {"number": 2, "action": "ask for CI fix", "reviewability": 30, "risk": 70},
            {"number": 3, "action": "review now", "reviewability": 65, "risk": 35},
        ]

        self.assertEqual(
            [item["number"] for item in filter_analyses(analyses, action="review-now")],
            [1, 3],
        )
        self.assertEqual(
            [item["number"] for item in filter_analyses(analyses, min_score=80)],
            [1],
        )
        self.assertEqual(
            [item["number"] for item in filter_analyses(analyses, max_risk=20)],
            [1],
        )

    def test_hydrate_prs_fetches_detail_and_merges_existing_context(self) -> None:
        calls: list[tuple[str, int | str]] = []

        def viewer(repo: str, number: int | str) -> dict[str, object]:
            calls.append((repo, number))
            return {
                "number": number,
                "body": "Test plan: unit tests.",
                "files": [{"path": "tests/test_parser.py"}],
            }

        hydrated = hydrate_prs(
            [
                {
                    "number": 42,
                    "title": "Fix parser",
                    "labels": [{"name": "bug"}],
                }
            ],
            repository="owner/repo",
            viewer=viewer,
        )

        self.assertEqual(calls, [("owner/repo", 42)])
        self.assertEqual(hydrated[0]["title"], "Fix parser")
        self.assertEqual(hydrated[0]["body"], "Test plan: unit tests.")
        self.assertEqual(hydrated[0]["files"][0]["path"], "tests/test_parser.py")

    def test_hydrate_prs_uses_repository_from_author_search_items(self) -> None:
        calls: list[tuple[str, int | str]] = []

        def viewer(repo: str, number: int | str) -> dict[str, object]:
            calls.append((repo, number))
            return {"number": number, "body": "Validation: local run."}

        hydrated = hydrate_prs(
            [
                {
                    "number": 7,
                    "repository": {"nameWithOwner": "org/project"},
                    "title": "Fix race",
                }
            ],
            viewer=viewer,
        )

        self.assertEqual(calls, [("org/project", 7)])
        self.assertEqual(hydrated[0]["body"], "Validation: local run.")

    def test_hydrate_prs_keeps_items_without_repository_context(self) -> None:
        hydrated = hydrate_prs([{"number": 1, "title": "Unknown repo"}])

        self.assertEqual(hydrated, [{"number": 1, "title": "Unknown repo"}])

    def test_limit_analyses_applies_top_n_after_other_queue_steps(self) -> None:
        analyses = [{"number": 1}, {"number": 2}, {"number": 3}]

        self.assertEqual(limit_analyses(analyses), analyses)
        self.assertEqual(limit_analyses(analyses, 2), [{"number": 1}, {"number": 2}])

    def test_limit_analyses_rejects_non_positive_top_n(self) -> None:
        with self.assertRaises(ValueError):
            limit_analyses([{"number": 1}], 0)
        with self.assertRaises(ValueError):
            limit_analyses([{"number": 1}], -1)

    def test_sort_analyses_supports_priority_score_risk_stale_and_number(self) -> None:
        analyses = [
            {
                "number": 3,
                "action": "ask for CI fix",
                "reviewability": 20,
                "risk": 80,
                "stale_days": 3,
            },
            {
                "number": 1,
                "action": "review now",
                "reviewability": 90,
                "risk": 10,
                "stale_days": 1,
            },
            {
                "number": 2,
                "action": "needs triage",
                "reviewability": 30,
                "risk": 70,
                "stale_days": 12,
            },
        ]

        self.assertEqual([item["number"] for item in sort_analyses(analyses)], [3, 1, 2])
        self.assertEqual(
            [item["number"] for item in sort_analyses(analyses, "action")],
            [1, 3, 2],
        )
        self.assertEqual(
            [item["number"] for item in sort_analyses(analyses, "score")],
            [1, 2, 3],
        )
        self.assertEqual(
            [item["number"] for item in sort_analyses(analyses, "risk")],
            [3, 2, 1],
        )
        self.assertEqual(
            [item["number"] for item in sort_analyses(analyses, "stale")],
            [2, 3, 1],
        )
        self.assertEqual(
            [item["number"] for item in sort_analyses(analyses, "number")],
            [1, 2, 3],
        )

    def test_from_json_review_plan_outputs_markdown_plan(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            result = main(
                [
                    "from-json",
                    "examples/sample-prs.json",
                    "--sort",
                    "action",
                    "--review-plan-minutes",
                    "30",
                    "--now",
                    "2026-06-01",
                ]
            )

        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("Maintainer Radar Review Plan", output)
        self.assertIn("Time budget: 30 minutes", output)
        self.assertIn("| Order | PR | Action | Est. | Next Step | Why |", output)

    def test_from_json_review_plan_outputs_html_plan(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            result = main(
                [
                    "from-json",
                    "examples/sample-prs.json",
                    "--sort",
                    "action",
                    "--format",
                    "html",
                    "--review-plan-minutes",
                    "30",
                    "--now",
                    "2026-06-01",
                ]
            )

        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("<!doctype html>", output)
        self.assertIn("Maintainer Radar Review Plan", output)
        self.assertIn("Time budget", output)
        self.assertIn("Planned Review Work", output)

    def test_from_json_review_plan_outputs_json_plan(self) -> None:
        with patch("sys.stdout", new=StringIO()) as stdout:
            result = main(
                [
                    "from-json",
                    "examples/sample-prs.json",
                    "--sort",
                    "action",
                    "--format",
                    "json",
                    "--review-plan-minutes",
                    "30",
                    "--now",
                    "2026-06-01",
                ]
            )

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["budget_minutes"], 30)
        self.assertIn("queue_summary", payload)
        self.assertIn("planned", payload)
        self.assertIn("watch_only", payload)

    def test_review_plan_rejects_summary_only_and_unsupported_formats(self) -> None:
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()) as stderr:
            summary_result = main(
                [
                    "from-json",
                    "examples/sample-prs.json",
                    "--summary-only",
                    "--review-plan-minutes",
                    "30",
                ]
            )
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()) as csv_stderr:
            csv_result = main(
                [
                    "from-json",
                    "examples/sample-prs.json",
                    "--format",
                    "csv",
                    "--review-plan-minutes",
                    "30",
                ]
            )

        self.assertEqual(summary_result, 2)
        self.assertIn("cannot be combined", stderr.getvalue())
        self.assertEqual(csv_result, 2)
        self.assertIn("supports --format markdown, html, or json", csv_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
