from __future__ import annotations

import json
import unittest

from maintainer_radar.render import (
    build_recommendation_commands,
    build_review_plan,
    estimate_review_minutes,
    render_comment_csv,
    render_comment_html,
    render_csv,
    render_comment_template,
    render_detail,
    render_html,
    render_markdown,
    render_recommendation_json,
    render_recommendation_markdown,
    render_review_plan_html,
    render_review_plan_json,
    render_review_plan_markdown,
    render_summary_csv,
    render_summary_markdown,
    summarize_review_plan,
    summarize_report,
)


class RenderTests(unittest.TestCase):
    def test_markdown_table_contains_action_and_score(self) -> None:
        output = render_markdown(
            [
                {
                    "number": 1,
                    "title": "Fix bug",
                    "url": "https://example.test/pull/1",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "signals": ["CI passed"],
                    "flags": [],
                    "score_breakdown": [
                        {"label": "CI passed", "risk_delta": -8, "kind": "signal"},
                    ],
                }
            ]
        )

        self.assertIn("Maintainer Radar Report", output)
        self.assertIn("PRs scanned: 1", output)
        self.assertIn("review now", output)
        self.assertIn("Review now while the PR appears small, active, and low risk.", output)
        self.assertIn("90", output)
        self.assertIn("CI passed (-8 risk)", output)
        self.assertIn("Average reviewability: 90/100\n\n| PR |", output)

    def test_markdown_can_group_queue_by_action(self) -> None:
        output = render_markdown(
            [
                {
                    "number": 1,
                    "title": "Ready",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "signals": ["CI passed"],
                    "flags": [],
                },
                {
                    "number": 2,
                    "title": "Fix CI",
                    "action": "ask for CI fix",
                    "next_step": "Ask the author to get failing checks green before deeper review.",
                    "reviewability": 20,
                    "signals": [],
                    "flags": ["CI failing"],
                },
            ],
            group_by="action",
        )

        self.assertIn("### review now (1 PR)", output)
        self.assertIn("### ask for CI fix (1 PR)", output)
        self.assertLess(output.index("### review now"), output.index("#1 Ready"))
        self.assertLess(output.index("### ask for CI fix"), output.index("#2 Fix CI"))

    def test_summary_counts_actions(self) -> None:
        summary = summarize_report(
            [
                {"action": "review now", "reviewability": 90, "stale_days": 0},
                {
                    "action": "ask for CI fix",
                    "reviewability": 30,
                    "stale_days": 8,
                    "flags": ["CI failing", "maintainer blocker language", "merge conflicts"],
                },
                {
                    "action": "needs triage",
                    "reviewability": 20,
                    "stale_days": 1,
                    "flags": ["maintainer blocking label", "branch behind base"],
                    "review_requests": 1,
                },
                {
                    "action": "review now",
                    "reviewability": 80,
                    "stale_days": 0,
                    "flags": ["merge blocked by repo rules"],
                },
            ]
        )

        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["review_now"], 2)
        self.assertEqual(summary["ci_blocked"], 1)
        self.assertEqual(summary["merge_conflicts"], 1)
        self.assertEqual(summary["branch_behind"], 1)
        self.assertEqual(summary["merge_gated"], 1)
        self.assertEqual(summary["review_requested"], 1)
        self.assertEqual(summary["maintainer_blocked"], 2)
        self.assertEqual(summary["large_or_triage"], 1)
        self.assertEqual(summary["stale"], 1)
        self.assertEqual(summary["next_session_prs"], 4)
        self.assertEqual(summary["next_session_minutes"], 37)
        self.assertEqual(summary["next_session_deferred"], 0)
        self.assertEqual(summary["quick_unblocks"], 1)
        self.assertEqual(summary["watch_only"], 0)
        self.assertEqual(
            summary["next_session_brief"],
            "Next 60 minutes: handle 4 PRs in about 37 minutes; 1 quick unblock.",
        )
        self.assertEqual(
            summary["queue_headline"],
            "4 PRs scanned: 2 ready for review; 1 blocked or waiting on CI; "
            "1 with merge conflict; 1 behind base; 1 blocked by merge gates; "
            "2 PRs have unresolved maintainer blockers.",
        )
        self.assertEqual(summary["attention_level"], "blocked")
        self.assertEqual(
            summary["attention_reason"],
            "2 PRs have unresolved maintainer blockers.",
        )
        self.assertEqual(summary["workflow_mode"], "blocker-sweep")
        self.assertEqual(
            summary["workflow_recommendation"],
            "Clear maintainer blockers, merge conflicts, failing CI, or merge gates before assigning review time.",
        )

    def test_summary_counts_ci_flags_even_when_action_differs(self) -> None:
        summary = summarize_report(
            [
                {
                    "action": "wait for author",
                    "reviewability": 0,
                    "stale_days": 0,
                    "flags": ["draft PR", "CI failing"],
                }
            ]
        )

        self.assertEqual(summary["ci_blocked"], 1)
        self.assertEqual(summary["attention_level"], "blocked")
        self.assertEqual(summary["attention_reason"], "1 PR has failing CI.")

    def test_summary_attention_level_routes_common_queue_states(self) -> None:
        cases = [
            ([], "quiet", "No pull requests matched this scan."),
            (
                [{"action": "review now", "reviewability": 90}],
                "review",
                "1 PR is ready for review.",
            ),
            (
                [{"action": "needs triage", "reviewability": 20}],
                "triage",
                "1 PR needs triage or scope reduction.",
            ),
            (
                [{"action": "needs author follow-up", "reviewability": 35}],
                "follow-up",
                "1 PR needs author follow-up.",
            ),
        ]

        for analyses, level, reason in cases:
            with self.subTest(level=level):
                summary = summarize_report(analyses)

                self.assertEqual(summary["attention_level"], level)
                self.assertEqual(summary["attention_reason"], reason)

    def test_summary_workflow_recommendation_routes_common_queue_states(self) -> None:
        cases = [
            ([], "quiet", "No matching PRs. Keep the scheduled scan quiet."),
            (
                [{"action": "review now", "reviewability": 90}],
                "review-sprint",
                "Start a focused review block with the ready PRs.",
            ),
            (
                [{"action": "needs author follow-up", "reviewability": 35}],
                "author-follow-up",
                "Send author follow-ups for waiting authors or branches behind base.",
            ),
            (
                [{"action": "needs triage", "reviewability": 20}],
                "triage-pass",
                "Classify or split large and unclear PRs before review.",
            ),
            (
                [{"action": "wait for CI", "reviewability": 60, "flags": ["CI pending"]}],
                "ci-watch",
                "Wait for pending checks before spending review time.",
            ),
            (
                [{"action": "wait for author", "reviewability": 60, "stale_days": 9}],
                "stale-sweep",
                "Run a stale follow-up pass before assigning review time.",
            ),
        ]

        for analyses, mode, recommendation in cases:
            with self.subTest(mode=mode):
                summary = summarize_report(analyses)

                self.assertEqual(summary["workflow_mode"], mode)
                self.assertEqual(summary["workflow_recommendation"], recommendation)

    def test_recommendation_markdown_turns_summary_into_next_commands(self) -> None:
        output = render_recommendation_markdown(
            [
                {
                    "number": 1,
                    "title": "Fix parser",
                    "action": "review now",
                    "reviewability": 90,
                    "stale_days": 0,
                    "signals": ["CI passed"],
                    "flags": [],
                }
            ],
            "owner/repo",
        )

        self.assertIn("Maintainer Radar Recommendation", output)
        self.assertIn("1 PR scanned: 1 ready for review.", output)
        self.assertIn("- Attention: `review`", output)
        self.assertIn("- Workflow: `review-sprint`", output)
        self.assertIn("Start a focused review block with the ready PRs.", output)
        self.assertIn(
            "maintainer-radar repo owner/repo --hydrate --action review-now --min-score 80 --sort score --top 10",
            output,
        )
        self.assertIn("maintainer-radar repo owner/repo --hydrate --sort action --review-plan-minutes 60", output)
        self.assertIn("maintainer-radar init-action --sort action --group-by action", output)
        self.assertIn("does not approve, reject, merge, label, or comment", output)

    def test_recommendation_json_exposes_automation_fields(self) -> None:
        output = json.loads(
            render_recommendation_json(
                [
                    {
                        "number": 2,
                        "title": "Fix CI",
                        "action": "ask for CI fix",
                        "reviewability": 20,
                        "stale_days": 0,
                        "flags": ["CI failing"],
                    }
                ],
                "owner/repo",
            )
        )

        self.assertEqual(output["repository"], "owner/repo")
        self.assertEqual(output["attention_level"], "blocked")
        self.assertEqual(output["workflow_mode"], "blocker-sweep")
        self.assertIn("failing CI", output["attention_reason"])
        self.assertIn("--sort action --group-by action", output["commands"]["focused_report"])

    def test_recommendation_commands_are_tailored_to_workflow_mode(self) -> None:
        review_commands = build_recommendation_commands(
            "owner/repo",
            {"workflow_mode": "review-sprint"},
        )
        stale_commands = build_recommendation_commands(
            "owner/repo",
            {"workflow_mode": "stale-sweep"},
        )

        self.assertIn("--action review-now", review_commands["focused_report"])
        self.assertIn("--stale-days 7", stale_commands["focused_report"])

    def test_review_plan_builds_budgeted_maintainer_session(self) -> None:
        analyses = [
            {
                "number": 1,
                "title": "Ready",
                "url": "https://example.test/pull/1",
                "action": "review now",
                "next_step": "Review now while the PR appears small, active, and low risk.",
                "reviewability": 90,
                "changed_files": 2,
                "additions": 40,
                "deletions": 10,
                "signals": ["CI passed"],
                "flags": [],
            },
            {
                "number": 2,
                "title": "Fix CI",
                "action": "ask for CI fix",
                "next_step": "Ask the author to get failing checks green before deeper review.",
                "reviewability": 20,
                "flags": ["CI failing"],
            },
            {
                "number": 3,
                "title": "Wait",
                "action": "wait for CI",
                "next_step": "Wait for checks to finish before spending review time.",
                "reviewability": 65,
                "flags": ["CI pending"],
            },
        ]

        plan = build_review_plan(analyses, 15)

        self.assertEqual(plan["planned_minutes"], 12)
        self.assertEqual([entry["item"]["number"] for entry in plan["planned"]], [1])
        self.assertEqual([entry["item"]["number"] for entry in plan["deferred"]], [2])
        self.assertEqual([entry["item"]["number"] for entry in plan["waiting"]], [3])
        self.assertEqual(estimate_review_minutes(analyses[2]), 0)

    def test_review_plan_markdown_contains_budget_estimates_and_waiting_items(self) -> None:
        output = render_review_plan_markdown(
            [
                {
                    "number": 1,
                    "title": "Ready",
                    "url": "https://example.test/pull/1",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "changed_files": 2,
                    "additions": 40,
                    "deletions": 10,
                    "signals": ["CI passed"],
                    "flags": [],
                },
                {
                    "number": 2,
                    "title": "Wait",
                    "action": "wait for CI",
                    "next_step": "Wait for checks to finish before spending review time.",
                    "reviewability": 65,
                    "flags": ["CI pending"],
                },
            ],
            30,
        )

        self.assertIn("Maintainer Radar Review Plan", output)
        self.assertIn("Time budget: 30 minutes", output)
        self.assertIn("Estimated active time: 12 minutes", output)
        self.assertIn("Workflow mode: review-sprint", output)
        self.assertIn("Workflow recommendation: Start a focused review block", output)
        self.assertIn("| Order | PR | Action | Est. | Next Step | Why |", output)
        self.assertIn("[#1 Ready](https://example.test/pull/1)", output)
        self.assertIn("12m", output)
        self.assertIn("### Watch Only", output)
        self.assertIn("#2 Wait", output)

    def test_review_plan_markdown_includes_draft_follow_ups(self) -> None:
        output = render_review_plan_markdown(
            [
                {
                    "number": 2,
                    "title": "Fix CI",
                    "url": "https://example.test/pull/2",
                    "action": "ask for CI fix",
                    "next_step": "Ask the author to get failing checks green before deeper review.",
                    "reviewability": 20,
                    "flags": ["CI failing", "no test plan found"],
                }
            ],
            10,
        )

        self.assertIn("### Draft Follow-ups", output)
        self.assertIn("#### [#2 Fix CI](https://example.test/pull/2)", output)
        self.assertIn("```markdown", output)
        self.assertIn("Before the next review, could you please:", output)
        self.assertNotIn("Reviewability score", output)
        self.assertIn("Get CI passing", output)
        self.assertIn("Add a short validation", output)
        self.assertIn("Please edit before posting", output)

    def test_review_plan_html_contains_budget_sections_and_escapes_content(self) -> None:
        output = render_review_plan_html(
            [
                {
                    "number": 1,
                    "title": "Ready <now>",
                    "url": "https://example.test/pull/1",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "changed_files": 2,
                    "additions": 40,
                    "deletions": 10,
                    "signals": ["CI passed"],
                    "flags": [],
                },
                {
                    "number": 2,
                    "title": "Wait",
                    "url": "javascript:alert(1)",
                    "action": "wait for CI",
                    "next_step": "Wait for checks to finish before spending review time.",
                    "reviewability": 65,
                    "flags": ["CI pending"],
                },
            ],
            30,
        )

        self.assertIn("<!doctype html>", output)
        self.assertIn("Maintainer Radar Review Plan", output)
        self.assertIn("Deterministic maintainer review plan.", output)
        self.assertIn("Time budget", output)
        self.assertIn("30 minutes", output)
        self.assertIn("review-sprint", output)
        self.assertIn("Start a focused review block", output)
        self.assertIn("Planned Review Work", output)
        self.assertIn("Watch Only", output)
        self.assertIn("#1 Ready &lt;now&gt;", output)
        self.assertIn("12m", output)
        self.assertIn("watch", output)
        self.assertNotIn("javascript:alert", output)

    def test_review_plan_html_includes_escaped_draft_follow_ups(self) -> None:
        output = render_review_plan_html(
            [
                {
                    "number": 7,
                    "title": "Needs <tests>",
                    "action": "needs author follow-up",
                    "next_step": "Ask the author to address requested changes before another review pass.",
                    "reviewability": 48,
                    "flags": ["code changed without tests"],
                }
            ],
            10,
        )

        self.assertIn("Draft Follow-ups", output)
        self.assertIn("<details>", output)
        self.assertIn("Copy Draft", output)
        self.assertIn('data-copy-target="draft-follow-up-1"', output)
        self.assertIn('id="draft-follow-up-1"', output)
        self.assertIn("navigator.clipboard", output)
        self.assertIn("#7 Needs &lt;tests&gt;", output)
        self.assertIn("Add regression coverage", output)

    def test_review_plan_json_contains_structured_plan_entries(self) -> None:
        output = render_review_plan_json(
            [
                {
                    "number": 1,
                    "title": "Ready",
                    "url": "https://example.test/pull/1",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "risk": 10,
                    "changed_files": 2,
                    "additions": 40,
                    "deletions": 10,
                    "signals": ["CI passed"],
                    "flags": [],
                },
                {
                    "number": 2,
                    "title": "Wait",
                    "action": "wait for CI",
                    "next_step": "Wait for checks to finish before spending review time.",
                    "reviewability": 65,
                    "risk": 35,
                    "flags": ["CI pending"],
                },
            ],
            30,
        )

        payload = json.loads(output)
        self.assertEqual(payload["budget_minutes"], 30)
        self.assertEqual(payload["planned_minutes"], 12)
        self.assertEqual(payload["queue_summary"]["total"], 2)
        self.assertEqual(payload["planned"][0]["number"], 1)
        self.assertEqual(payload["planned"][0]["estimated_minutes"], 12)
        self.assertEqual(payload["planned"][0]["reason"], "CI passed")
        self.assertEqual(payload["watch_only"][0]["number"], 2)
        self.assertEqual(payload["watch_only"][0]["estimated_minutes"], 0)
        self.assertEqual(payload["planned"][0]["draft_follow_up_comment"], "")
        self.assertEqual(payload["watch_only"][0]["draft_follow_up_comment"], "")

    def test_review_plan_json_includes_draft_follow_up_comments(self) -> None:
        output = render_review_plan_json(
            [
                {
                    "number": 2,
                    "title": "Fix CI",
                    "action": "ask for CI fix",
                    "next_step": "Ask the author to get failing checks green before deeper review.",
                    "reviewability": 20,
                    "risk": 80,
                    "flags": ["CI failing"],
                }
            ],
            10,
        )

        payload = json.loads(output)
        self.assertIn("Get CI passing", payload["planned"][0]["draft_follow_up_comment"])
        self.assertIn("Please edit before posting", payload["planned"][0]["draft_follow_up_comment"])

    def test_comment_template_includes_merge_readiness_requests(self) -> None:
        comment = render_comment_template(
            {
                "number": 9,
                "title": "Refresh branch",
                "action": "needs author follow-up",
                "reviewability": 52,
                "flags": ["merge conflicts", "branch behind base"],
            }
        )

        self.assertIn("Resolve merge conflicts", comment)
        self.assertIn("Update the branch with the base branch", comment)

    def test_review_plan_rejects_non_positive_budget(self) -> None:
        with self.assertRaises(ValueError):
            build_review_plan([], 0)

    def test_review_plan_summary_returns_structured_counts(self) -> None:
        summary = summarize_review_plan(
            [
                {
                    "number": 1,
                    "title": "Ready",
                    "action": "review now",
                    "reviewability": 90,
                    "changed_files": 2,
                    "additions": 40,
                    "deletions": 10,
                    "signals": ["CI passed"],
                    "flags": [],
                },
                {
                    "number": 2,
                    "title": "Fix CI",
                    "action": "ask for CI fix",
                    "reviewability": 20,
                    "flags": ["CI failing"],
                },
                {
                    "number": 3,
                    "title": "Wait",
                    "action": "wait for CI",
                    "reviewability": 65,
                    "flags": ["CI pending"],
                },
            ],
            15,
        )

        self.assertEqual(summary["plan_budget_minutes"], 15)
        self.assertEqual(summary["planned_prs"], 1)
        self.assertEqual(summary["planned_minutes"], 12)
        self.assertEqual(summary["remaining_minutes"], 3)
        self.assertEqual(summary["deferred_prs"], 1)
        self.assertEqual(summary["watch_only_prs"], 1)

    def test_summary_only_output_has_no_table(self) -> None:
        output = render_summary_markdown(
            [
                {"action": "review now", "reviewability": 90, "stale_days": 0},
            ]
        )

        self.assertIn("Maintainer Radar Summary", output)
        self.assertIn("Review now: 1", output)
        self.assertIn("Workflow mode: review-sprint", output)
        self.assertIn("Workflow recommendation: Start a focused review block", output)
        self.assertIn("Next session: Next 60 minutes: handle 1 PR in about 12 minutes.", output)
        self.assertIn("Next-session active time: 12 minutes", output)
        self.assertIn("Merge conflicts: 0", output)
        self.assertIn("Branch behind base: 0", output)
        self.assertIn("Merge gated: 0", output)
        self.assertIn("Review requested: 0", output)
        self.assertIn("Maintainer blocked: 0", output)
        self.assertNotIn("| PR |", output)

    def test_csv_output_contains_stable_columns(self) -> None:
        output = render_csv(
            [
                {
                    "number": 42,
                    "title": "Fix parser cache race",
                    "author": "alice",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "risk": 10,
                    "stale_days": 0,
                    "changed_files": 2,
                    "additions": 12,
                    "deletions": 3,
                    "labels": ["bug", "backend"],
                    "signals": ["CI passed"],
                    "flags": ["no test plan found"],
                    "score_breakdown": [
                        {"label": "no test plan found", "risk_delta": 8, "kind": "flag"},
                    ],
                    "url": "https://example.test/pull/42",
                }
            ]
        )

        self.assertIn("number,title,author,action,next_step,reviewability,risk", output)
        self.assertIn("score_breakdown,url", output)
        self.assertIn("42,Fix parser cache race,alice,review now", output)
        self.assertIn("Review now while the PR appears small, active, and low risk.", output)
        self.assertIn("bug; backend", output)
        self.assertIn("no test plan found (+8 risk)", output)
        self.assertIn("no test plan found", output)

    def test_summary_csv_output_contains_one_summary_row(self) -> None:
        output = render_summary_csv(
            [
                {"action": "review now", "reviewability": 90, "stale_days": 0},
                {
                    "action": "ask for CI fix",
                    "reviewability": 30,
                    "stale_days": 8,
                    "flags": ["CI failing", "merge conflicts"],
                    "review_requests": 1,
                },
            ]
        )

        self.assertIn(
            "total,review_now,author_follow_up,ci_blocked,ci_pending,"
            "merge_conflicts,branch_behind,merge_gated,review_requested",
            output,
        )
        self.assertIn(
            "average_score,next_session_prs,next_session_minutes,next_session_deferred,"
            "quick_unblocks,watch_only,next_session_brief,queue_headline,"
            "attention_level,attention_reason,workflow_mode,workflow_recommendation",
            output,
        )
        self.assertIn("2,1,0,1,0,1,0,0,1,0,0,1,60,2,17,0,1,0", output)
        self.assertIn(
            "Next 60 minutes: handle 2 PRs in about 17 minutes; 1 quick unblock.",
            output,
        )
        self.assertIn(
            "2 PRs scanned: 1 ready for review; 1 blocked or waiting on CI; "
            "1 with merge conflict.",
            output,
        )
        self.assertIn(
            "blocked,1 PR has merge conflicts.,blocker-sweep,"
            "\"Clear maintainer blockers, merge conflicts, failing CI, or merge gates "
            "before assigning review time.\"",
            output,
        )

    def test_comment_csv_output_quotes_multiline_comment(self) -> None:
        output = render_comment_csv("Thanks.\nPlease add tests.")

        self.assertTrue(output.startswith("comment\n"))
        self.assertIn('"Thanks.\nPlease add tests."', output)

    def test_html_output_contains_summary_and_escapes_content(self) -> None:
        output = render_html(
            [
                {
                    "number": 42,
                    "title": "Fix <parser>",
                    "url": "javascript:alert(1)",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "signals": ["CI passed"],
                    "flags": ["needs <tests>"],
                    "score_breakdown": [
                        {"label": "needs <tests>", "risk_delta": 8, "kind": "flag"},
                    ],
                }
            ]
        )

        self.assertIn("<!doctype html>", output)
        self.assertIn("PRs scanned", output)
        self.assertIn("review-sprint", output)
        self.assertIn("Start a focused review block", output)
        self.assertIn("#42 Fix &lt;parser&gt;", output)
        self.assertIn("Review now while the PR appears small, active, and low risk.", output)
        self.assertIn("needs &lt;tests&gt;", output)
        self.assertIn("needs &lt;tests&gt; (+8 risk)", output)
        self.assertNotIn("javascript:alert", output)

    def test_html_can_group_queue_by_action(self) -> None:
        output = render_html(
            [
                {
                    "number": 1,
                    "title": "Ready",
                    "action": "review now",
                    "next_step": "Review now while the PR appears small, active, and low risk.",
                    "reviewability": 90,
                    "signals": ["CI passed"],
                    "flags": [],
                },
                {
                    "number": 2,
                    "title": "Fix CI",
                    "action": "ask for CI fix",
                    "next_step": "Ask the author to get failing checks green before deeper review.",
                    "reviewability": 20,
                    "signals": [],
                    "flags": ["CI failing"],
                },
            ],
            group_by="action",
        )

        self.assertIn('class="action-group"', output)
        self.assertIn("<h2>review now <span>1 PR</span></h2>", output)
        self.assertIn("<h2>ask for CI fix <span>1 PR</span></h2>", output)

    def test_summary_html_output_omits_table(self) -> None:
        output = render_html(
            [{"number": 1, "action": "review now", "reviewability": 90}],
            summary_only=True,
        )

        self.assertIn("Maintainer Radar Report", output)
        self.assertNotIn("<table>", output)

    def test_comment_html_output_escapes_comment(self) -> None:
        output = render_comment_html("Thanks.\n<script>alert(1)</script>")

        self.assertIn("<pre>", output)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", output)

    def test_detail_contains_sections(self) -> None:
        output = render_detail(
            {
                "number": 1,
                "title": "Fix bug",
                "action": "review now",
                "next_step": "Review now while the PR appears small, active, and low risk.",
                "reviewability": 90,
                "risk": 10,
                "raw_risk": 10,
                "checks": {"passed": 1},
                "files": {"code_files": 1, "test_files": 1, "doc_files": 0},
                "signals": ["CI passed"],
                "flags": [],
                "score_breakdown": [
                    {"label": "CI passed", "risk_delta": -8, "kind": "signal"},
                ],
            }
        )

        self.assertIn("Maintainer Brief", output)
        self.assertIn("Next step:", output)
        self.assertIn("Review now while the PR appears small, active, and low risk.", output)
        self.assertIn("### Checks", output)
        self.assertIn("### Score Breakdown", output)
        self.assertIn("CI passed: -8 risk", output)
        self.assertIn("### Flags", output)

    def test_comment_template_is_draft_and_uses_flags(self) -> None:
        output = render_comment_template(
            {
                "action": "needs author follow-up",
                "reviewability": 42,
                "flags": [
                    "CI failing",
                    "no test plan found",
                    "code changed without tests",
                    "maintainer blocker language",
                ],
            }
        )

        self.assertIn("Before the next review", output)
        self.assertIn("Get CI passing", output)
        self.assertIn("Add a short validation", output)
        self.assertIn("Generated as a draft", output)


if __name__ == "__main__":
    unittest.main()
