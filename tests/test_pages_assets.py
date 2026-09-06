from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PagesAssetTests(unittest.TestCase):
    def test_demo_assets_and_interactive_controls_are_wired(self) -> None:
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        ids: list[str] = []
        labels: list[str] = []
        assets: list[str] = []

        class Elements(HTMLParser):
            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                values = dict(attrs)
                if values.get("id"):
                    ids.append(values["id"] or "")
                if tag == "label" and values.get("for"):
                    labels.append(values["for"] or "")
                if tag in {"script", "img", "link"}:
                    src = values.get("src") or values.get("href") or ""
                    if src.startswith("assets/"):
                        assets.append(src)

        Elements().feed(html)
        self.assertEqual([key for key, count in Counter(ids).items() if count > 1], [])
        self.assertTrue(set(labels).issubset(ids), "Every label must target an existing input")
        for asset in assets:
            self.assertTrue((ROOT / "docs" / asset).is_file(), asset)
        for control in ("repo-form", "repo-input", "repo-submit", "load-sample", "scan-cancel",
                        "scan-error", "scan-warning", "results", "queue-body", "plan-minutes",
                        "plan-body", "copy-plan", "export-dialog", "export-text"):
            self.assertIn(control, ids)
        self.assertIn('role="status"', html)
        self.assertIn('role="alert"', html)
        self.assertIn("<noscript>", html)
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)

    def test_quickstart_docs_show_first_run_path(self) -> None:
        docs = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Two Minute Quickstart", docs)
        self.assertIn("?repo=owner/repo", docs)
        self.assertIn("JackSpiece/maintainer-radar@v0.20.0", docs)
        self.assertIn("workflow_dispatch", docs)
        self.assertIn("contents: read", docs)
        self.assertIn("pull-requests: read", docs)
        self.assertIn("GH_TOKEN: ${{ github.token }}", docs)
        self.assertIn("maintainer-radar init-repo --profile balanced", docs)
        self.assertIn("maintainer-radar recommend https://github.com/owner/repo/pulls", docs)
        self.assertIn("maintainer-radar init-config --profile strict", docs)
        self.assertIn("maintainer-radar init-config --profile large-repo", docs)
        self.assertIn("maintainer-radar repo https://github.com/owner/repo/pulls", docs)
        self.assertIn("maintainer-radar pr https://github.com/owner/repo/pull/123", docs)
        self.assertIn("attention-level", docs)
        self.assertIn("workflow-mode", docs)
        self.assertIn("next-session-brief", docs)
        self.assertIn("does not approve, reject, merge, label, or comment", docs)
        self.assertIn("docs/quickstart.md", readme)

    def test_privacy_permissions_docs_explain_data_flow(self) -> None:
        docs = (ROOT / "docs" / "privacy-permissions.md").read_text(encoding="utf-8")
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Privacy and Permissions", docs)
        self.assertIn("contents: read", docs)
        self.assertIn("pull-requests: read", docs)
        self.assertIn("GH_TOKEN: ${{ github.token }}", docs)
        self.assertIn("does not send queue data to a hosted service", docs)
        self.assertIn("does not read repository secrets", docs)
        self.assertIn("does not ask for a token", docs)
        self.assertIn("does not post comments", docs)
        self.assertIn("does not", docs)
        self.assertIn("docs/privacy-permissions.md", security)
        self.assertIn("docs/privacy-permissions.md", readme)

    def test_attention_workflows_docs_explain_notification_gates(self) -> None:
        docs = (ROOT / "docs" / "attention-workflows.md").read_text(encoding="utf-8")

        self.assertIn("Attention Workflows", docs)
        self.assertIn("queue-headline", docs)
        self.assertIn("attention-level", docs)
        self.assertIn("attention-reason", docs)
        self.assertIn("Warn on active queue", docs)
        self.assertIn("steps.radar.outputs.attention-level != 'quiet'", docs)
        self.assertIn("steps.radar.outputs.attention-level == 'blocked'", docs)
        self.assertIn("stale-days", docs)
        self.assertIn("JackSpiece/maintainer-radar@v0.20.0", docs)
        self.assertIn("does not approve, reject, merge, label, or comment", docs)

    def test_adoption_guide_has_copy_paste_workflows(self) -> None:
        docs = (ROOT / "docs" / "adoption.md").read_text(encoding="utf-8")

        self.assertIn("Adoption Guide", docs)
        self.assertIn("Daily Queue Brief", docs)
        self.assertIn("Review-Ready Queue", docs)
        self.assertIn("maintainer-radar recommend https://github.com/owner/repo/pulls", docs)
        self.assertIn("exact report or workflow command", docs)
        self.assertIn("to run\nnext", docs)
        self.assertIn("maintainer-radar init-config --profile strict", docs)
        self.assertIn("maintainer-radar init-config --profile large-repo", docs)
        self.assertIn("maintainer-radar init-repo --profile balanced", docs)
        self.assertIn("30 Minute Review Plan", docs)
        self.assertIn("Stale Follow-Up Queue", docs)
        self.assertIn("Merge Readiness Watch", docs)
        self.assertIn("JackSpiece/maintainer-radar@v0.20.0", docs)
        self.assertIn("review-plan-minutes", docs)
        self.assertIn("merge-conflicts", docs)
        self.assertIn("branch-behind", docs)
        self.assertIn("merge-gated", docs)
        self.assertIn("review-requested", docs)
        self.assertIn("queue-headline", docs)
        self.assertIn("attention-level", docs)
        self.assertIn("attention-reason", docs)
        self.assertIn("workflow-mode", docs)
        self.assertIn("workflow-recommendation", docs)
        self.assertIn("next-session-brief", docs)
        self.assertIn("group-by: action", docs)
        self.assertIn("does not approve, reject, merge, label, or comment", docs)

    def test_pages_markdown_keeps_actions_expressions_in_raw_blocks(self) -> None:
        for path in sorted((ROOT / "docs").glob("*.md")):
            in_raw_block = False
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "{% raw %}" in line:
                    self.assertFalse(in_raw_block, f"{path}:{lineno} nested raw block")
                    in_raw_block = True

                if "${{" in line:
                    self.assertTrue(in_raw_block, f"{path}:{lineno} needs a Liquid raw block")

                if "{% endraw %}" in line:
                    self.assertTrue(in_raw_block, f"{path}:{lineno} raw block was not open")
                    in_raw_block = False

            self.assertFalse(in_raw_block, f"{path} has an unclosed raw block")

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("{% raw %}", readme)
        self.assertNotIn("{% endraw %}", readme)

    def test_positioning_keeps_before_review_message(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "positioning.md").read_text(encoding="utf-8")

        self.assertIn("You still review the code and decide what to do.", readme)
        self.assertIn("time-boxed review plan", readme)
        self.assertIn("maintainer-radar recommend https://github.com/owner/repo/pulls", readme)
        self.assertIn("docs/attention-workflows.md", readme)
        self.assertIn("## Plan a review session", readme)
        self.assertIn("Where should a maintainer spend review attention first?", docs)
        self.assertIn("The `recommend` command turns a queue scan into one maintainer decision", docs)
        self.assertIn("## Boundaries", docs)
        self.assertIn("does not approve, reject, merge, label, or comment", docs)

    def test_social_preview_png_has_expected_dimensions(self) -> None:
        data = (ROOT / "docs" / "assets" / "social-preview.png").read_bytes()

        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (1200, 630))

    def test_social_preview_svg_keeps_source_text(self) -> None:
        svg = (ROOT / "docs" / "assets" / "social-preview.svg").read_text(encoding="utf-8")

        self.assertIn("Maintainer Radar", svg)
        self.assertIn("PR triage for the next maintainer session", svg)
        self.assertIn("Blocker sweep, review sprint, or 60-minute digest.", svg)
        self.assertIn("blocker-sweep", svg)
        self.assertIn("review-sprint", svg)
        self.assertIn("60m digest", svg)
        self.assertIn("uses: JackSpiece/maintainer-radar", svg)
        self.assertIn("jackspiece.github.io/maintainer-radar", svg)

    def test_browser_preview_docs_explain_network_and_limits(self) -> None:
        docs = (ROOT / "docs" / "browser-preview.md").read_text(encoding="utf-8")
        for contract in ("public GitHub API", "does not ask for a GitHub token",
                         "does not post comments", "rate-limit", "fictional",
                         "5 most recently updated", "100 changed files", "30 seconds",
                         "Copy Plan", "clipboard", "partial", "example queue",
                         "?repo=python/cpython&plan=30", "--review-plan-minutes 30"):
            self.assertIn(contract, docs)

    def test_github_action_docs_explain_contract_and_guardrails(self) -> None:
        docs = (ROOT / "docs" / "github-action.md").read_text(encoding="utf-8")

        self.assertIn("JackSpiece/maintainer-radar@v0.20.0", docs)
        self.assertIn("report-path", docs)
        self.assertIn("step-summary", docs)
        self.assertIn("maintainer-blocked", docs)
        self.assertIn("queue-headline", docs)
        self.assertIn("attention-level", docs)
        self.assertIn("attention-reason", docs)
        self.assertIn("workflow-mode", docs)
        self.assertIn("workflow-recommendation", docs)
        self.assertIn("next-session-brief", docs)
        self.assertIn('echo "Attention: ${{ steps.radar.outputs.attention-level }}"', docs)
        self.assertIn('echo "Workflow: ${{ steps.radar.outputs.workflow-mode }}"', docs)
        self.assertNotIn('echo "${{ steps.radar.outputs.attention-level }}:', docs)
        self.assertIn("review-plan-minutes", docs)
        self.assertIn("contents: read", docs)
        self.assertIn("pull-requests: read", docs)
        self.assertIn("format: html", docs)
        self.assertIn("review-plan.html", docs)
        self.assertIn("review-plan.json", docs)
        self.assertIn(
            "review plans default to `review-plan.md`, `review-plan.html`, or `review-plan.json`",
            docs,
        )
        self.assertIn("estimated active time", docs)
        self.assertIn("watch-only count", docs)
        self.assertIn("draft follow-up comments", docs)
        self.assertIn("Copy\nDraft buttons", docs)
        self.assertIn("does not approve, reject, merge, label, or comment", docs)

    def test_configuration_docs_explain_init_config_profiles(self) -> None:
        docs = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
        examples = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("maintainer-radar init-config --profile balanced", docs)
        self.assertIn("maintainer-radar init-config --profile strict", docs)
        self.assertIn("maintainer-radar init-config --profile large-repo", docs)
        self.assertIn("maintainer-radar init-repo --profile balanced", docs)
        self.assertIn("refuses to overwrite an existing file", docs)
        self.assertIn("Small teams or high-signal queues", docs)
        self.assertIn("High-volume repositories", docs)
        self.assertIn("maintainer-radar init-config --profile strict", examples)
        self.assertIn("maintainer-radar init-config --profile strict", readme)
        self.assertIn("maintainer-radar init-repo --profile balanced", examples)
        self.assertIn("maintainer-radar init-repo --profile balanced", readme)

    def test_review_plan_docs_explain_time_boxed_workflow(self) -> None:
        docs = (ROOT / "docs" / "review-plan.md").read_text(encoding="utf-8")

        self.assertIn("Review Plans", docs)
        self.assertIn("--review-plan-minutes 30", docs)
        self.assertIn("--format html --review-plan-minutes 30", docs)
        self.assertIn("--format json --review-plan-minutes 30", docs)
        self.assertIn("review-plan-minutes", docs)
        self.assertIn("browser-friendly", docs)
        self.assertIn("dashboards and automation", docs)
        self.assertIn("watch-only", docs)
        self.assertIn("Draft Follow-ups", docs)
        self.assertIn("Copy Draft", docs)
        self.assertIn("draft_follow_up_comment", docs)
        self.assertIn("does not approve, reject, merge, label, or comment", docs)

    def test_html_output_docs_explain_copyable_review_plan_drafts(self) -> None:
        docs = (ROOT / "docs" / "html-output.md").read_text(encoding="utf-8")

        self.assertIn("HTML Output", docs)
        self.assertIn("Copy Draft", docs)
        self.assertIn("embedded copy\nhelper", docs)
        self.assertIn("does not load external JavaScript", docs)

    def test_summary_output_docs_include_maintainer_blocked(self) -> None:
        json_docs = (ROOT / "docs" / "json-output.md").read_text(encoding="utf-8")
        csv_docs = (ROOT / "docs" / "csv-output.md").read_text(encoding="utf-8")

        self.assertIn("maintainer_blocked", json_docs)
        self.assertIn("merge_state_status", json_docs)
        self.assertIn("review_requests", json_docs)
        self.assertIn("merge_conflicts", json_docs)
        self.assertIn("branch_behind", json_docs)
        self.assertIn("merge_gated", json_docs)
        self.assertIn("review_requested", json_docs)
        self.assertIn("queue_headline", json_docs)
        self.assertIn("attention_level", json_docs)
        self.assertIn("attention_reason", json_docs)
        self.assertIn("workflow_mode", json_docs)
        self.assertIn("workflow_recommendation", json_docs)
        self.assertIn("next_session_brief", json_docs)
        self.assertIn("quick_unblocks", json_docs)
        self.assertIn("PRs blocked by maintainer feedback or labels", json_docs)
        self.assertIn("maintainer_blocked", csv_docs)
        self.assertIn("merge_conflicts", csv_docs)
        self.assertIn("branch_behind", csv_docs)
        self.assertIn("merge_gated", csv_docs)
        self.assertIn("review_requested", csv_docs)
        self.assertIn("queue_headline", csv_docs)
        self.assertIn("attention_level", csv_docs)
        self.assertIn("attention_reason", csv_docs)
        self.assertIn("workflow_mode", csv_docs)
        self.assertIn("workflow_recommendation", csv_docs)
        self.assertIn("next_session_brief", csv_docs)
        self.assertIn("quick_unblocks", csv_docs)

    def test_heuristics_docs_explain_label_blockers(self) -> None:
        docs = (ROOT / "docs" / "heuristics.md").read_text(encoding="utf-8")

        self.assertIn("maintainer blocking label", docs)
        self.assertIn("waiting on author", docs)
        self.assertIn("waiting for dependency", docs)
        self.assertIn("blocked upstream", docs)
        self.assertIn("These labels route the PR to author follow-up", docs)
        self.assertIn("Merge Readiness", docs)
        self.assertIn("Merge conflicts route the PR to author follow-up", docs)
        self.assertIn("Requested reviewers are shown as positive queue context", docs)


if __name__ == "__main__":
    unittest.main()
