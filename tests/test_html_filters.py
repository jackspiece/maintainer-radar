"""Dependency-free checks for the progressively enhanced standalone queue."""
from __future__ import annotations

from copy import deepcopy
from html.parser import HTMLParser
import unittest

from maintainer_radar.render import (
    QUEUE_FILTER_SCRIPT,
    render_comment_html,
    render_html,
    render_review_plan_html,
)


class Tags(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def named(self, name: str) -> list[dict[str, str | None]]:
        return [attrs for tag, attrs in self.tags if tag == name]

    def element(self, element_id: str) -> dict[str, str | None]:
        return next(attrs for _, attrs in self.tags if attrs.get("id") == element_id)


class HtmlFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.items = [
            {"number": 7, "title": "Café Parser", "action": "review now", "reviewability": 92,
             "url": 'https://example.test/pull/7?check=a&b="quoted"',
             "next_step": "Review the tests", "signals": ["CI passed"], "flags": []},
            {"number": 2, "title": "Fix CI", "action": "ask for CI fix", "reviewability": 20,
             "url": "https://example.test/pull/2", "flags": ["CI failing"]},
            {"number": 9, "title": "文書 update", "action": "review now", "reviewability": 85},
        ]

    def test_controls_are_labeled_and_hidden_until_initialized(self) -> None:
        tags = Tags(render_html(self.items))
        self.assertIn("hidden", tags.element("queue-filters"))
        self.assertEqual(tags.element("queue-filters")["aria-label"], "Filter pull requests")
        labels = [tag["for"] for tag in tags.named("label")]
        self.assertEqual(labels, ["queue-search", "queue-action"])
        self.assertEqual(tags.element("queue-search")["type"], "search")
        self.assertEqual(tags.element("queue-search")["aria-controls"], "queue-results")
        self.assertEqual(tags.element("queue-reset")["type"], "button")
        self.assertEqual(tags.element("queue-count")["role"], "status")
        self.assertEqual(tags.element("queue-count")["aria-live"], "polite")
        self.assertEqual(tags.element("queue-count")["aria-atomic"], "true")
        self.assertEqual(tags.element("queue-results")["tabindex"], "0")

    def test_no_javascript_output_contains_all_rows_in_original_order(self) -> None:
        output = render_html(self.items)
        tags = Tags(output)
        self.assertEqual(len(tags.named("tr")), 4)  # Header plus three unchanged rows.
        self.assertTrue(all("hidden" not in row for row in tags.named("tr")))
        self.assertLess(output.index("#7 Café Parser"), output.index("#2 Fix CI"))
        self.assertLess(output.index("#2 Fix CI"), output.index("#9 文書 update"))
        self.assertIn("Showing 3 of 3 PRs", output)
        self.assertIn("Local filters require JavaScript.", output)
        self.assertEqual(tags.named("a")[0]["href"], self.items[0]["url"])
        self.assertIn('<td class="score">92</td>', output)

    def test_action_options_are_unique_and_keep_first_occurrence_order(self) -> None:
        tags = Tags(render_html(self.items))
        self.assertEqual([item["value"] for item in tags.named("option")],
                         ["", "review now", "ask for CI fix"])

    def test_default_action_matches_the_rendered_row(self) -> None:
        output = render_html([{"number": 1, "title": "Missing action"}])
        self.assertEqual([item["value"] for item in Tags(output).named("option")], ["", "needs triage"])
        self.assertIn('class="action action-needs-triage">needs triage</span>', output)

    def test_hostile_data_is_escaped_and_never_interpolated_in_the_script(self) -> None:
        attack = '\"><img src=x onerror="window.injected=1"></script><script>alert(1)</script> & 文書'
        output = render_html([{
            "number": 1, "title": attack, "action": attack, "next_step": attack,
            "signals": [attack], "flags": [attack], "url": "javascript:alert(1)",
        }])
        tags = Tags(output)
        self.assertFalse(tags.named("img"))
        self.assertFalse(tags.named("a"))
        self.assertEqual(len(tags.named("script")), 2)  # Existing clipboard and local filters only.
        self.assertEqual(tags.named("option")[1]["value"], attack)
        self.assertNotIn(attack, QUEUE_FILTER_SCRIPT)
        self.assertIn("&lt;img", output)

    def test_filter_script_uses_text_and_hidden_without_network_or_storage(self) -> None:
        self.assertIn("textContent", QUEUE_FILTER_SCRIPT)
        self.assertIn("entry.row.hidden = !matches", QUEUE_FILTER_SCRIPT)
        self.assertIn('normalize("NFC").toLowerCase()', QUEUE_FILTER_SCRIPT)
        for forbidden in ("innerHTML", "outerHTML", "eval(", "fetch(", "XMLHttpRequest", "localStorage",
                          "sessionStorage", "sendBeacon", "document.cookie", "location", "setTimeout"):
            self.assertNotIn(forbidden, QUEUE_FILTER_SCRIPT)

    def test_grouped_summary_comment_and_plan_reports_do_not_offer_queue_filters(self) -> None:
        outputs = [
            render_html(self.items, group_by="action"),
            render_html(self.items, group_by="other"),
            render_html(self.items, summary_only=True),
            render_html(self.items, summary_only=True, group_by="action"),
            render_comment_html("Fictional draft"),
            render_review_plan_html(self.items, 30),
        ]
        for output in outputs:
            with self.subTest(title=output.split("<title>")[1].split("</title>")[0]):
                self.assertNotIn('id="queue-filters"', output)
                self.assertNotIn(QUEUE_FILTER_SCRIPT, output)
                self.assertNotIn(".queue-filters {", output)
        self.assertIn("review now <span>2 PRs</span>", outputs[0])
        self.assertIn("ask for CI fix <span>1 PR</span>", outputs[0])

    def test_empty_ungrouped_report_has_zero_count_and_original_empty_message(self) -> None:
        output = render_html([])
        self.assertIn("Showing 0 of 0 PRs", output)
        self.assertIn("No pull requests matched this report.", output)
        self.assertIn("hidden", Tags(output).element("queue-filter-empty"))
        self.assertEqual(Tags(output).named("tr"), [])

    def test_rendering_does_not_change_source_metadata(self) -> None:
        before = deepcopy(self.items)
        self.assertEqual(render_html(self.items), render_html(self.items))
        self.assertEqual(self.items, before)


if __name__ == "__main__":
    unittest.main()
