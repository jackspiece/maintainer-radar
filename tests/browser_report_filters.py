"""Exercise exported HTML locally, with no web server or live GitHub data.

Requires Playwright and a compatible Firefox or Chromium browser:
    PYTHONPATH=src python tests/browser_report_filters.py --executable /path/to/firefox
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from typing import Any

from playwright.sync_api import expect, sync_playwright

from maintainer_radar.render import (
    render_comment_html,
    render_html,
    render_review_plan_html,
)

ROOT = Path(__file__).resolve().parents[1]
ATTACK = '<img src="https://example.test/pixel" onerror="window.injected=1"> </script><script>alert(1)</script>'
ODD_ACTION = '\"><svg onload="window.injected=2"> & "check"'
ITEMS: list[dict[str, Any]] = [
    {"number": 7, "title": "Café parser 文書 😀", "action": "review now", "reviewability": 92,
     "url": 'https://example.test/acme/parser/pull/7?check=a&b="quoted"',
     "next_step": "Review the Unicode tests.", "signals": ["CI passed"], "flags": []},
    {"number": 2, "title": "Parser pipeline", "action": "ask for CI fix", "reviewability": 20,
     "url": "https://example.test/acme/parser/pull/2", "flags": ["CI failing"]},
    {"number": 9, "title": "Документы ΔΟΚΙΜΉ", "action": "review now", "reviewability": 85,
     "url": "https://example.test/acme/parser/pull/9"},
    {"number": 4, "title": ATTACK, "action": ODD_ACTION, "reviewability": 50,
     "url": "javascript:alert(1)", "next_step": "Keep hostile text literal."},
    {"number": 11, "title": "Long literal " + "x" * 400, "action": "wait for CI", "reviewability": 61},
]


def run(engine: str, executable: str | None, artifacts: Path) -> None:
    artifacts.mkdir(parents=True, exist_ok=True)
    original = deepcopy(ITEMS)
    documents = {
        "queue": render_html(ITEMS, title="Fictional local filter demo"),
        "grouped": render_html(ITEMS, group_by="action"),
        "summary": render_html(ITEMS, summary_only=True),
        "plan": render_review_plan_html(ITEMS, 30),
        "comment": render_comment_html("Fictional draft"),
        "empty": render_html([]),
    }
    for name, html in documents.items():
        (artifacts / f"{name}.html").write_text(html, encoding="utf-8")
    assert ITEMS == original
    findings: list[str] = []
    network: list[str] = []
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch(executable_path=executable, headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 1000}, reduced_motion="reduce")
        context.on("request", lambda request: network.append(request.url) if request.url.startswith(
            ("http:", "https:", "ws:", "wss:")) else None)
        # A regression must never cause fixture data to be sent out during the check.
        context.route("http://**/*", lambda route: route.abort())
        context.route("https://**/*", lambda route: route.abort())
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((artifacts / "queue.html").resolve().as_uri())
        rows = page.locator("#queue-results tbody tr")
        visible = page.locator("#queue-results tbody tr:not([hidden])")
        search = page.get_by_role("searchbox", name="Search queue")
        action = page.get_by_role("combobox", name="Action", exact=True)
        reset = page.get_by_role("button", name="Reset filters")
        expect(search).to_be_visible()
        expect(visible).to_have_count(5)
        expect(page.get_by_role("status")).to_have_text("Showing 5 of 5 PRs")
        baseline = rows.evaluate_all("rows => rows.map(row => row.innerHTML)")
        metrics = page.locator(".metrics").inner_text()
        links = page.locator("#queue-results a").evaluate_all(
            "links => links.map(link => link.getAttribute('href'))")
        assert links == [ITEMS[i]["url"] for i in (0, 1, 2)]
        assert page.locator("#queue-results img, #queue-results svg, #queue-results script").count() == 0
        assert page.evaluate("window.injected") is None

        search.fill("  PARSER  ")
        expect(visible).to_have_count(2)
        action.select_option("review now")
        expect(visible).to_have_count(1)
        expect(visible).to_contain_text("#7 Café parser")
        expect(page.get_by_role("status")).to_have_text("Showing 1 of 5 PRs")
        assert page.locator(".metrics").inner_text() == metrics
        search.press("Enter")
        assert page.url.endswith("queue.html"), "Enter must not navigate or submit a URL."
        action.select_option("wait for CI")
        expect(visible).to_have_count(0)
        expect(page.locator("#queue-filter-empty")).to_be_visible()
        expect(page.get_by_role("status")).to_have_text("Showing 0 of 5 PRs")
        reset.click()
        expect(search).to_be_focused()
        expect(search).to_have_value("")
        expect(action).to_have_value("")
        expect(visible).to_have_count(5)
        expect(page.locator("#queue-filter-empty")).to_be_hidden()
        findings.append("Combined text/action filters, empty state, Enter suppression, reset and summary scope")

        for query, expected in [("CAFE\u0301", "#7"), ("文書", "#7"), ("😀", "#7"),
                                ("ДОКУМЕНТЫ", "#9"), ("δοκιμή", "#9"), ("CI failing", "#2"),
                                ("Unicode tests", "#7"), ("92", "#7"), (ATTACK, "#4")]:
            search.fill(query)
            expect(visible).to_have_count(1)
            expect(visible).to_contain_text(expected)
        search.fill("cafe")  # Accents remain significant.
        expect(visible).to_have_count(0)
        reset.click()
        action.select_option(ODD_ACTION)
        expect(visible).to_have_count(1)
        expect(visible).to_contain_text(ATTACK)
        for _ in range(12):
            search.fill("definitely absent")
            expect(visible).to_have_count(0)
            search.fill("<img")
            expect(visible).to_have_count(1)
            reset.click()
            expect(visible).to_have_count(5)
            action.select_option(ODD_ACTION)
        reset.click()
        assert rows.evaluate_all("rows => rows.map(row => row.innerHTML)") == baseline
        assert page.locator("#queue-results a").evaluate_all(
            "links => links.map(link => link.getAttribute('href'))") == links
        assert not context.cookies()
        findings.append("Unicode NFC/lowercase, literal hostile text/action, repeated changes and exact row/link preservation")

        # Keyboard focus order, native select, Reset through Enter and accessible scroll region.
        search.focus()
        search.fill("parser")
        search.press("Tab")
        expect(action).to_be_focused()
        action.press("Home")
        action.press("ArrowDown")
        action.press("Tab")
        expect(reset).to_be_focused()
        reset.press("Enter")
        expect(search).to_be_focused()
        expect(visible).to_have_count(5)
        search.press("Tab")
        action.press("Tab")
        reset.press("Tab")
        expect(page.locator("#queue-results")).to_be_focused()
        findings.append("Keyboard labels, tab order, native action selection, Reset and focusable table region")

        for width, height, label in ((1280, 1000, "desktop"), (390, 844, "mobile"), (320, 740, "narrow")):
            page.set_viewport_size({"width": width, "height": height})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Page overflow at {width}"
            for control in (search, action, reset):
                box = control.bounding_box()
                assert box and box["width"] <= width and box["height"] >= 44
            page.locator("#queue-filters").scroll_into_view_if_needed()
            page.screenshot(path=str(artifacts / f"filters-{label}.png"), full_page=True)
            if width == 320:
                region = page.locator("#queue-results")
                assert region.evaluate("el => el.scrollWidth > el.clientWidth")
                region.focus()
                region.press("End")
                region.evaluate("el => { el.scrollLeft = el.scrollWidth; }")
                assert region.evaluate("el => el.scrollLeft > 0")
        findings.append("1280px, 390px and 320px widths without document overflow; 44px controls and local table scrolling")

        for name in ("grouped", "summary", "plan", "comment"):
            page.goto((artifacts / f"{name}.html").resolve().as_uri())
            expect(page.locator("#queue-filters")).to_have_count(0)
            if name == "grouped":
                expect(page.locator("tbody tr")).to_have_count(5)
                expect(page.locator(".action-group h2").first).to_have_text("review now 2 PRs")
                assert page.locator("tbody tr[hidden]").count() == 0
        page.goto((artifacts / "empty.html").resolve().as_uri())
        expect(page.get_by_role("status")).to_have_text("Showing 0 of 0 PRs")
        expect(page.get_by_text("No pull requests matched this report.", exact=True)).to_be_visible()
        expect(page.locator("#queue-filter-empty")).to_be_hidden()
        page.get_by_role("searchbox").fill("anything")
        page.get_by_role("button", name="Reset filters").click()
        expect(page.get_by_role("status")).to_have_text("Showing 0 of 0 PRs")
        findings.append("Grouped, summary, review-plan and comment reports guarded; genuinely empty queue handled")

        # The committed fictional example is also a usable, standalone filtered report.
        page.goto((ROOT / "examples/output/sample-report.html").as_uri())
        expect(page.get_by_role("searchbox", name="Search queue")).to_be_visible()
        page.get_by_role("searchbox", name="Search queue").fill("parser")
        expect(page.locator("#queue-results tbody tr:not([hidden])")).to_have_count(1)
        page.get_by_role("button", name="Reset filters").click()
        expect(page.locator("#queue-results tbody tr:not([hidden])")).to_have_count(2)
        findings.append("Committed fictional sample opened directly as a local file and filtered")
        context.close()

        nojs = browser.new_context(java_script_enabled=False, viewport={"width": 320, "height": 740})
        nojs.on("request", lambda request: network.append(request.url) if request.url.startswith(
            ("http:", "https:", "ws:", "wss:")) else None)
        nojs.route("http://**/*", lambda route: route.abort())
        nojs.route("https://**/*", lambda route: route.abort())
        page = nojs.new_page()
        page.goto((artifacts / "queue.html").resolve().as_uri())
        expect(page.locator("#queue-filters")).to_be_hidden()
        expect(page.locator("#queue-results tbody tr")).to_have_count(5)
        for row in page.locator("#queue-results tbody tr").all():
            expect(row).to_be_visible()
        expect(page.locator("#queue-filter-fallback")).to_be_visible()
        expect(page.get_by_role("status")).to_have_text("Showing 5 of 5 PRs")
        assert page.locator("#queue-results a").count() == 3
        page.screenshot(path=str(artifacts / "filters-no-javascript.png"), full_page=True)
        nojs.close()
        browser.close()
        findings.append("JavaScript-disabled local file retains every row, score, original link and fallback explanation")

    assert not network, f"Unexpected network requests: {network}"
    assert not errors, errors
    findings.append("Zero attempted HTTP(S)/WebSocket requests and zero page errors")
    result = {"engine": engine, "executable": executable, "checks": findings,
              "network_requests": network, "page_errors": errors, "status": "passed"}
    (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Standalone HTML filter checks passed:\n- " + "\n- ".join(findings))
    print(f"Evidence: {artifacts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("firefox", "chromium"), default="firefox")
    parser.add_argument("--executable", help="Existing compatible browser executable")
    parser.add_argument("--artifacts", type=Path, default=Path(tempfile.gettempdir()) / "radar-html-filters")
    args = parser.parse_args()
    run(args.engine, args.executable, args.artifacts)
