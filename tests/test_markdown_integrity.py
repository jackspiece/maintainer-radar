"""Markdown rendering boundaries; optional independent parser checks need dev tools."""
from __future__ import annotations

from copy import deepcopy
import csv
from html.parser import HTMLParser
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from maintainer_radar.render import (
    _markdown_link,
    _markdown_pr_label,
    _markdown_text,
    markdown_cell,
    render_csv,
    render_detail,
    render_markdown,
    render_review_plan_json,
    render_review_plan_markdown,
    render_summary_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests/fixtures/markdown-output.json").read_text(encoding="utf-8"))
URL = "https://github.com/example/project/pull/9"


def item_for(title: str, url: str = URL) -> dict:
    return {
        "number": 9, "title": title, "url": url, "author": "fixture-author",
        "action": "review now", "next_step": "Review the change.", "reviewability": 90,
        "signals": ["CI passed"], "flags": [], "score_breakdown": [],
    }


def flattened(text: str) -> str:
    return re.sub(r"\r\n?|\n", " ", text)


class RenderedDocument(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.links: list[dict[str, str]] = []
        self.tags: list[str] = []
        self.text: list[str] = []
        self._row: list[str] = []
        self._cell: list[str] | None = None
        self._link: dict[str, str] | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        if tag == "tr":
            self._row = []
        if tag == "td":
            self._cell = []
        if tag == "a":
            self._link = {"href": dict(attrs).get("href") or "", "text": ""}
            self.links.append(self._link)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        if tag == "tr" and self._row:
            self.rows.append(self._row)
        if tag == "a":
            self._link = None

    def handle_data(self, value: str) -> None:
        self.text.append(value)
        if self._cell is not None:
            self._cell.append(value)
        if self._link is not None:
            self._link["text"] += value


class MarkdownIntegrityTests(unittest.TestCase):
    def test_literal_inline_and_table_escaping(self) -> None:
        self.assertEqual(_markdown_text("A\r\nB\rC\nD"), "A B C D")
        self.assertEqual(markdown_cell(r"left\|right"), r"left\\&#124;right")
        self.assertEqual(markdown_cell(0), "0")
        self.assertEqual(markdown_cell(None), "")
        self.assertEqual(_markdown_text("&lt; <b>x</b>"), "&amp;lt; &lt;b&gt;x&lt;/b&gt;")
        self.assertEqual(_markdown_text("**x** _y_ `z` ~~s~~ [q] ##"),
                         r"\*\*x\*\* \_y\_ \`z\` \~\~s\~\~ \[q\] \#\#")

    def test_title_cannot_close_link_or_create_comment(self) -> None:
        title = "release](https://example.invalid/redirect)<!--"
        expected = r"[\#9 release\]\(https://example.invalid/redirect\)&lt;\!--](" + URL + ")"
        self.assertEqual(_markdown_pr_label(item_for(title)), expected)
        for render in (render_markdown, lambda items: render_review_plan_markdown(items, 30)):
            self.assertIn(expected, render([item_for(title)]))

    def test_urls_keep_entities_and_encode_markdown_delimiters(self) -> None:
        for case in FIXTURES["destinations"]:
            with self.subTest(url=case["url"]):
                expected = case["href"].replace("&", "&amp;")
                self.assertEqual(_markdown_link("label", case["url"]), f"[label]({expected})")
        url = URL + '/)\\\r\n<>|"[x]'
        self.assertEqual(_markdown_link("label", url),
                         f"[label]({URL}/%29%5C%0D%0A%3C%3E%7C%22%5Bx%5D)")

    def test_unsafe_urls_render_as_literal_labels(self) -> None:
        for url in ("javascript:alert(1)", "data:text/html,<b>x</b>", "file:///tmp/example", "//evil.test", URL + "\ud800"):
            with self.subTest(url=url):
                self.assertEqual(_markdown_link("[x]", url), r"\[x\]")
                self.assertNotIn(url, render_markdown([item_for("[x]", url)]))
        self.assertEqual(_markdown_link("x", "http://forge.example/pull/9"),
                         "[x](http://forge.example/pull/9)")

    def test_every_table_field_is_escaped_without_changing_metadata(self) -> None:
        value = "left\\|right\r\n**[x]**<b>"
        item = item_for(value)
        item.update(action=value, next_step=value, signals=[value], flags=[value],
                    score_breakdown=[{"label": value, "risk_delta": 1}])
        before = deepcopy(item)
        output = render_markdown([item], group_by="action")
        row = next(line for line in output.splitlines() if line.startswith(r"| [\#9"))
        self.assertEqual(row.count("|"), 7)
        self.assertEqual(row.count(markdown_cell(value)), 6)
        self.assertNotIn("\r", output)
        self.assertEqual(item, before)
        self.assertIn(_markdown_text(value), render_detail(item))

    def test_headings_and_detail_metadata_are_literal(self) -> None:
        title = "a\r\n# heading <b> &amp;"
        item = item_for(title)
        item["author"] = title
        self.assertIn("## " + _markdown_text(title) + "\n", render_summary_markdown([], title))
        self.assertIn("## " + _markdown_text(title) + "\n", render_review_plan_markdown([], 30, title))
        brief = render_detail(item)
        self.assertIn("- **Title:** " + _markdown_text(title), brief)
        self.assertIn("- **Author:** " + _markdown_text(title), brief)
        self.assertNotIn("\r", brief)

    def test_json_csv_and_source_titles_are_not_sanitized(self) -> None:
        for title in FIXTURES["titles"]:
            with self.subTest(title=title):
                item = item_for(title)
                original = deepcopy(item)
                render_markdown([item])
                render_review_plan_markdown([item], 30)
                rows = list(csv.DictReader(StringIO(render_csv([item]), newline="")))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["title"], title)
                self.assertEqual(json.loads(render_review_plan_json([item], 30))["planned"][0]["title"], title)
                self.assertEqual(item, original)

    @unittest.skipUnless(shutil.which("node"), "Demo parity needs Node.js")
    def test_demo_pr_labels_match_python_inline_context(self) -> None:
        items = [item_for(title) for title in FIXTURES["titles"]]
        items.extend(item_for("URL fixture", case["url"]) for case in FIXTURES["destinations"])
        items.extend(item_for("Unsafe [title]", url) for url in ("", "javascript:alert(1)"))
        outputs = self._demo_outputs(items)
        for item, output in zip(items, outputs):
            with self.subTest(item=item):
                self.assertIn(_markdown_pr_label(item), output)
                self.assertNotIn("\r", output)

    def _demo_outputs(self, items: list[dict]) -> list[str]:
        script = """
const fs = require('node:fs');
const demo = require('./docs/assets/demo.js');
const items = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(items.map(item => demo.renderReviewPlanMarkdown(
  [{...item, nextStep: item.next_step}], 'example/project', 30))));
"""
        result = subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps(items),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _parser_cases(self) -> list[dict]:
        cases = []
        items = [item_for(title) for title in FIXTURES["titles"]]
        items.extend(item_for("URL fixture", case["url"]) for case in FIXTURES["destinations"])
        hrefs = [URL] * len(FIXTURES["titles"]) + [case["href"] for case in FIXTURES["destinations"]]
        for item, href in zip(items, hrefs):
            for kind, markdown, column in (
                ("report", render_markdown([item]), 0),
                ("plan", render_review_plan_markdown([item], 30), 1),
            ):
                cases.append({"kind": kind, "markdown": markdown, "item": item, "href": href, "column": column})
        if shutil.which("node"):
            for item, href, output in zip(items, hrefs, self._demo_outputs(items)):
                cases.append({"kind": "demo", "markdown": output, "item": item, "href": href, "column": None})
        value = "left\\|right\r\n**[x]**<b> &#124;"
        item = item_for(value)
        item.update(next_step=value, signals=[value], flags=[value],
                    score_breakdown=[{"label": value, "risk_delta": 1}])
        cases.append({
            "kind": "cells", "markdown": render_markdown([item]), "item": item, "href": URL, "column": 0,
            "cells": [f"#9 {flattened(value)}", "review now", flattened(value), "90",
                      f"{flattened(value)} (+1 risk)", f"{flattened(value)}, {flattened(value)}"],
        })
        # Every review-plan section uses the same safe label renderer, including headings.
        for action in ("ask for CI fix", "wait for author"):
            item = item_for("release](https://example.invalid/redirect)<!-- | ~~x~~")
            item["action"] = action
            item["number"] = 10
            first = item_for("First")
            first["url"] = ""
            output = render_review_plan_markdown([first, item], 12)
            cases.append({"kind": "sections", "markdown": output, "item": item, "href": URL, "column": None})
        return cases

    def _assert_parsed(self, cases: list[dict], outputs: list[str]) -> None:
        self.assertEqual(len(outputs), len(cases))
        for case, output in zip(cases, outputs):
            with self.subTest(kind=case["kind"], title=case["item"]["title"], href=case["href"]):
                doc = RenderedDocument(output)
                title = f"#{case['item']['number']} {flattened(case['item']['title'])}"
                self.assertEqual(len(doc.links), 2 if case["kind"] == "sections" else 1, output)
                for link in doc.links:
                    self.assertEqual(link, {"href": case["href"], "text": title})
                if case["column"] is not None:
                    self.assertEqual(len(doc.rows), 1, output)
                    self.assertEqual(len(doc.rows[0]), 6, output)
                    self.assertEqual(doc.rows[0][case["column"]], title)
                if "cells" in case:
                    self.assertEqual(doc.rows[0], case["cells"])
                if case["kind"] != "sections":
                    self.assertNotIn("code", doc.tags, output)
                for tag in ("svg", "b", "img", "em", "strong", "del", "script"):
                    self.assertNotIn(tag, doc.tags, output)

    @unittest.skipUnless(importlib.util.find_spec("markdown_it"), "Optional: install markdown-it-py")
    def test_commonmark_table_parser_preserves_labels_destinations_and_rows(self) -> None:
        from markdown_it import MarkdownIt
        parser = MarkdownIt("commonmark").enable(["table", "strikethrough"])
        cases = self._parser_cases()
        self._assert_parsed(cases, [parser.render(case["markdown"]) for case in cases])

    @unittest.skipUnless(shutil.which("node"), "Optional Marked parser needs Node.js")
    def test_marked_gfm_parser_preserves_labels_destinations_and_rows(self) -> None:
        # MARKED_MODULE may name an installed package or the absolute ESM module path.
        script = """
const fs = require('node:fs');
(async () => {
  let module;
  try { module = await import(process.env.MARKED_MODULE || 'marked'); }
  catch (error) { if (error.code === 'ERR_MODULE_NOT_FOUND') process.exit(77); throw error; }
  const inputs = JSON.parse(fs.readFileSync(0, 'utf8'));
  process.stdout.write(JSON.stringify(inputs.map(text => module.marked.parse(text, { gfm: true }))));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        cases = self._parser_cases()
        result = subprocess.run(["node", "-e", script], cwd=ROOT, env=os.environ.copy(),
                                input=json.dumps([case["markdown"] for case in cases]),
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 77:
            self.skipTest("Optional: install marked or set MARKED_MODULE to its ESM module")
        self.assertEqual(result.returncode, 0, result.stderr)
        self._assert_parsed(cases, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
