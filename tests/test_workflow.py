from __future__ import annotations

import unittest

from maintainer_radar.workflow import DEFAULT_ACTION_REF, render_github_action_workflow


class WorkflowTests(unittest.TestCase):
    def test_render_github_action_workflow_defaults_to_read_only_markdown_artifact(self) -> None:
        output = render_github_action_workflow()

        self.assertIn("name: Maintainer Radar Report", output)
        self.assertIn("workflow_dispatch:", output)
        self.assertIn('cron: "0 8 * * 1-5"', output)
        self.assertIn("contents: read", output)
        self.assertIn("pull-requests: read", output)
        self.assertIn('GH_TOKEN: ${{ github.token }}', output)
        self.assertIn(f"uses: {DEFAULT_ACTION_REF}", output)
        self.assertNotIn("actions/checkout", output)
        self.assertIn("uses: actions/upload-artifact@v7", output)
        self.assertIn("id: radar", output)
        self.assertIn("format: markdown", output)
        self.assertIn('sort: action', output)
        self.assertIn('step-summary: "true"', output)
        self.assertIn("path: ${{ steps.radar.outputs.report-path }}", output)

    def test_render_github_action_workflow_supports_html_without_hydration(self) -> None:
        output = render_github_action_workflow(
            report_format="html",
            schedule="15 7 * * 1",
            limit=25,
            sort="risk",
            hydrate=False,
            top=10,
            group_by="action",
            label="bug",
            author="alice",
            stale_days=14,
            updated_since="2026-06-01",
            action_filter="review-now",
            min_score=80,
            max_risk=20,
            config=".maintainer-radar.json",
        )

        self.assertIn('cron: "15 7 * * 1"', output)
        self.assertIn('limit: "25"', output)
        self.assertIn('hydrate: "false"', output)
        self.assertIn("sort: risk", output)
        self.assertIn('group-by: "action"', output)
        self.assertIn('label: "bug"', output)
        self.assertIn('author: "alice"', output)
        self.assertIn('stale-days: "14"', output)
        self.assertIn('updated-since: "2026-06-01"', output)
        self.assertIn('action: "review-now"', output)
        self.assertIn('min-score: "80"', output)
        self.assertIn('max-risk: "20"', output)
        self.assertIn('top: "10"', output)
        self.assertIn('config: ".maintainer-radar.json"', output)
        self.assertLess(output.index("actions/checkout@v7"), output.index("id: radar"))
        self.assertIn("format: html", output)
        self.assertIn("maintainer-radar.html", output)
        self.assertIn('step-summary: "true"', output)

    def test_render_github_action_workflow_can_skip_step_summary(self) -> None:
        output = render_github_action_workflow(step_summary=False)

        self.assertIn('step-summary: "false"', output)

    def test_render_github_action_workflow_supports_review_plan_minutes(self) -> None:
        output = render_github_action_workflow(review_plan_minutes=30)

        self.assertIn("name: Maintainer Radar Review Plan", output)
        self.assertIn("Build 30 minute review plan", output)
        self.assertIn('review-plan-minutes: "30"', output)
        self.assertIn("format: markdown", output)
        self.assertIn("output: review-plan.md", output)
        self.assertIn("name: review-plan", output)

    def test_render_github_action_workflow_supports_html_review_plan(self) -> None:
        output = render_github_action_workflow(report_format="html", review_plan_minutes=45)

        self.assertIn("Build 45 minute review plan", output)
        self.assertIn('review-plan-minutes: "45"', output)
        self.assertIn("format: html", output)
        self.assertIn("output: review-plan.html", output)
        self.assertIn("name: review-plan-html", output)

    def test_render_github_action_workflow_supports_json_review_plan(self) -> None:
        output = render_github_action_workflow(report_format="json", review_plan_minutes=20)

        self.assertIn("Build 20 minute review plan", output)
        self.assertIn('review-plan-minutes: "20"', output)
        self.assertIn("format: json", output)
        self.assertIn("output: review-plan.json", output)
        self.assertIn("name: review-plan-json", output)

    def test_render_github_action_workflow_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            render_github_action_workflow(report_format="xml")
        with self.assertRaises(ValueError):
            render_github_action_workflow(limit=0)
        with self.assertRaises(ValueError):
            render_github_action_workflow(top=0)
        with self.assertRaises(ValueError):
            render_github_action_workflow(review_plan_minutes=0)
        with self.assertRaises(ValueError):
            render_github_action_workflow(report_format="csv", review_plan_minutes=30)
        with self.assertRaises(ValueError):
            render_github_action_workflow(stale_days=0)
        with self.assertRaises(ValueError):
            render_github_action_workflow(min_score=-1)
        with self.assertRaises(ValueError):
            render_github_action_workflow(max_risk=-1)
        with self.assertRaises(ValueError):
            render_github_action_workflow(action_filter="review now")
        with self.assertRaises(ValueError):
            render_github_action_workflow(group_by="label")
        with self.assertRaises(ValueError):
            render_github_action_workflow(label="bug\nname: injected")
        with self.assertRaises(ValueError):
            render_github_action_workflow(config="config.json\nname: injected")
        with self.assertRaises(ValueError):
            render_github_action_workflow(schedule="0 8 * * 1\nname: injected")


if __name__ == "__main__":
    unittest.main()
