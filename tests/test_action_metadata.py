from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ActionMetadataTests(unittest.TestCase):
    def test_action_metadata_exposes_composite_action_contract(self) -> None:
        action = (ROOT / "action.yml").read_text(encoding="utf-8")

        self.assertIn("name: Maintainer Radar", action)
        self.assertIn("branding:", action)
        self.assertIn("icon: activity", action)
        self.assertIn("using: composite", action)
        self.assertIn("repository:", action)
        self.assertIn("format:", action)
        self.assertIn("label:", action)
        self.assertIn("stale-days:", action)
        self.assertIn("min-score:", action)
        self.assertIn("group-by:", action)
        self.assertIn("review-plan-minutes:", action)
        self.assertIn("config:", action)
        self.assertIn("step-summary:", action)
        self.assertIn("report-path:", action)
        self.assertIn("summary-json:", action)
        self.assertIn("queue-headline:", action)
        self.assertIn("attention-level:", action)
        self.assertIn("attention-reason:", action)
        self.assertIn("workflow-mode:", action)
        self.assertIn("workflow-recommendation:", action)
        self.assertIn("next-session-brief:", action)
        self.assertIn("merge-conflicts:", action)
        self.assertIn("branch-behind:", action)
        self.assertIn("merge-gated:", action)
        self.assertIn("review-requested:", action)
        self.assertIn("maintainer-blocked:", action)
        self.assertIn("quick-unblocks:", action)
        self.assertIn("watch-only:", action)
        self.assertIn("next-session-prs:", action)
        self.assertIn("next-session-minutes:", action)
        self.assertIn("next-session-deferred:", action)
        self.assertIn("average-score:", action)
        self.assertIn("planned-prs:", action)
        self.assertIn("planned-minutes:", action)
        self.assertIn("watch-only-prs:", action)
        self.assertIn("value: ${{ steps.build.outputs.report-path }}", action)
        self.assertIn("value: ${{ steps.build.outputs.queue-headline }}", action)
        self.assertIn("value: ${{ steps.build.outputs.attention-level }}", action)
        self.assertIn("value: ${{ steps.build.outputs.attention-reason }}", action)
        self.assertIn("value: ${{ steps.build.outputs.workflow-mode }}", action)
        self.assertIn("value: ${{ steps.build.outputs.workflow-recommendation }}", action)
        self.assertIn("value: ${{ steps.build.outputs.next-session-brief }}", action)
        self.assertIn("value: ${{ steps.build.outputs.merge-conflicts }}", action)
        self.assertIn("value: ${{ steps.build.outputs.branch-behind }}", action)
        self.assertIn("value: ${{ steps.build.outputs.merge-gated }}", action)
        self.assertIn("value: ${{ steps.build.outputs.review-requested }}", action)
        self.assertIn("value: ${{ steps.build.outputs.maintainer-blocked }}", action)
        self.assertIn("value: ${{ steps.build.outputs.quick-unblocks }}", action)
        self.assertIn("value: ${{ steps.build.outputs.watch-only }}", action)
        self.assertIn("value: ${{ steps.build.outputs.next-session-prs }}", action)
        self.assertIn("value: ${{ steps.build.outputs.next-session-minutes }}", action)
        self.assertIn("value: ${{ steps.build.outputs.next-session-deferred }}", action)
        self.assertIn("value: ${{ steps.build.outputs.average-score }}", action)
        self.assertIn("value: ${{ steps.build.outputs.planned-prs }}", action)

    def test_action_scans_once_and_uses_read_only_cli(self) -> None:
        action = (ROOT / "action.yml").read_text(encoding="utf-8")

        self.assertIn('python -m pip install "$GITHUB_ACTION_PATH"', action)
        self.assertIn('maintainer-radar repo "$repository"', action)
        self.assertEqual(action.count('maintainer-radar repo "$repository"'), 1)
        self.assertIn('--format json > "$ANALYSES_PATH"', action)
        self.assertIn('radar_args+=("--config=$INPUT_CONFIG")', action)
        self.assertIn('radar_args+=("--label=$INPUT_LABEL")', action)
        self.assertIn('radar_args+=("--action=$INPUT_ACTION")', action)
        self.assertIn('radar_args+=("--min-score=$INPUT_MIN_SCORE")', action)
        self.assertIn('summary-json<<MAINTAINER_RADAR_SUMMARY', action)
        self.assertIn('"average-score": "average_score"', action)
        self.assertIn('"merge-conflicts": "merge_conflicts"', action)
        self.assertIn('"branch-behind": "branch_behind"', action)
        self.assertIn('"merge-gated": "merge_gated"', action)
        self.assertIn('"review-requested": "review_requested"', action)
        self.assertIn('"maintainer-blocked": "maintainer_blocked"', action)
        self.assertIn('"attention-level": "attention_level"', action)
        self.assertIn('"attention-reason": "attention_reason"', action)
        self.assertIn('"workflow-mode": "workflow_mode"', action)
        self.assertIn('"workflow-recommendation": "workflow_recommendation"', action)
        self.assertIn('"next-session-brief": "next_session_brief"', action)
        self.assertIn('"quick-unblocks": "quick_unblocks"', action)
        self.assertIn('"watch-only": "watch_only"', action)
        self.assertIn('"next-session-prs": "next_session_prs"', action)
        self.assertIn('"next-session-minutes": "next_session_minutes"', action)
        self.assertIn('"next-session-deferred": "next_session_deferred"', action)
        self.assertIn('"planned-minutes": "planned_minutes"', action)
        self.assertIn("summarize_report", action)
        self.assertIn("summarize_review_plan", action)
        self.assertIn("Maintainer blocked:", action)
        self.assertIn("Workflow mode:", action)
        self.assertIn("Workflow recommendation:", action)
        self.assertIn("Next session:", action)
        self.assertIn("Maintainer Radar Review Plan", action)
        self.assertIn("Estimated active time:", action)
        self.assertIn("Deferred by budget:", action)
        self.assertIn("Watch only:", action)
        self.assertIn("GITHUB_STEP_SUMMARY", action)
        self.assertNotIn("summary_command", action)
        self.assertNotIn("gh pr comment", action)
        self.assertNotIn("pull-requests: write", action)

    def test_action_derives_output_path_from_report_format(self) -> None:
        action = (ROOT / "action.yml").read_text(encoding="utf-8")

        self.assertIn('markdown) default_output="maintainer-radar.md"', action)
        self.assertIn('html) default_output="maintainer-radar.html"', action)
        self.assertIn('json) default_output="maintainer-radar.json"', action)
        self.assertIn('csv) default_output="maintainer-radar.csv"', action)
        self.assertIn('if [ -n "$INPUT_REVIEW_PLAN_MINUTES" ]; then', action)
        self.assertIn('markdown) default_output="review-plan.md"', action)
        self.assertIn('html) default_output="review-plan.html"', action)
        self.assertIn('json) default_output="review-plan.json"', action)
        self.assertIn('output="${INPUT_OUTPUT:-$default_output}"', action)
        self.assertIn("printf 'report-path=%s\\n' \"$output\" >> \"$GITHUB_OUTPUT\"", action)

    def test_action_docs_cover_inputs_and_outputs(self) -> None:
        docs = (ROOT / "docs" / "github-action.md").read_text(encoding="utf-8")

        for name in [
            "repository",
            "format",
            "output",
            "limit",
            "label",
            "author",
            "stale-days",
            "updated-since",
            "action",
            "min-score",
            "max-risk",
            "sort",
            "top",
            "group-by",
            "review-plan-minutes",
            "config",
            "hydrate",
            "step-summary",
            "report-path",
            "summary-json",
            "queue-headline",
            "attention-level",
            "attention-reason",
            "workflow-mode",
            "workflow-recommendation",
            "next-session-brief",
            "merge-conflicts",
            "branch-behind",
            "merge-gated",
            "review-requested",
            "maintainer-blocked",
            "quick-unblocks",
            "watch-only",
            "next-session-prs",
            "next-session-minutes",
            "next-session-deferred",
            "average-score",
            "plan-budget-minutes",
            "planned-prs",
            "planned-minutes",
            "remaining-minutes",
            "deferred-prs",
            "watch-only-prs",
        ]:
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", docs)

    def test_ci_smoke_checks_multiline_summary_json_safely(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("QUEUE_HEADLINE: ${{ steps.radar.outputs.queue-headline }}", workflow)
        self.assertIn("ATTENTION_LEVEL: ${{ steps.radar.outputs.attention-level }}", workflow)
        self.assertIn("ATTENTION_REASON: ${{ steps.radar.outputs.attention-reason }}", workflow)
        self.assertIn("WORKFLOW_MODE: ${{ steps.radar.outputs.workflow-mode }}", workflow)
        self.assertIn(
            "WORKFLOW_RECOMMENDATION: ${{ steps.radar.outputs.workflow-recommendation }}",
            workflow,
        )
        self.assertIn("NEXT_SESSION_BRIEF: ${{ steps.radar.outputs.next-session-brief }}", workflow)
        self.assertIn("SUMMARY_JSON: ${{ steps.radar.outputs.summary-json }}", workflow)
        self.assertIn("printf '%s\\n' \"$SUMMARY_JSON\" > summary.json", workflow)
        self.assertNotIn("cat > summary.json <<'JSON'", workflow)
        self.assertIn('assert "queue_headline" in summary', workflow)
        self.assertIn('assert "attention_level" in summary', workflow)
        self.assertIn('assert "attention_reason" in summary', workflow)
        self.assertIn('assert "workflow_mode" in summary', workflow)
        self.assertIn('assert "workflow_recommendation" in summary', workflow)
        self.assertIn('assert "next_session_brief" in summary', workflow)
        self.assertIn('assert "next_session_prs" in summary', workflow)
        self.assertIn('assert "next_session_minutes" in summary', workflow)
        self.assertNotIn('test -n "${{ steps.radar.outputs.summary-json }}"', workflow)


if __name__ == "__main__":
    unittest.main()
