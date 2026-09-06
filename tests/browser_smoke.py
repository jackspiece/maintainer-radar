"""Exercise the static demo in Firefox with mocked GitHub responses.

Requires Playwright and its Firefox browser. For an existing compatible browser:
    python tests/browser_smoke.py --executable /path/to/firefox
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread

from playwright.sync_api import Error, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def run(executable: str | None, artifacts: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "docs")))
    Thread(target=server.serve_forever, daemon=True).start()
    artifacts.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{server.server_port}/"
    try:
        with sync_playwright() as playwright:
            browser = playwright.firefox.launch(executable_path=executable, headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
            errors: list[str] = []
            requests: list[str] = []
            held = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            mode = "success"
            title = '<img src=x onerror="document.body.dataset.injected=1"> & a useful fix'
            detail = {
                "number": 7, "title": title, "body": "Test plan: unit tests pass.",
                "html_url": "https://github.com/example/project/pull/7",
                "updated_at": datetime.now(timezone.utc).isoformat(), "head": {"sha": "abc"},
                "additions": 42, "deletions": 12, "changed_files": 2, "draft": False,
            }

            def route_api(route) -> None:
                path = route.request.url
                requests.append(path)
                if mode == "held":
                    held.append(route)
                    return
                if mode == "network":
                    route.abort()
                    return
                status = 200
                headers = {"content-type": "application/json", "access-control-allow-origin": "*",
                           "access-control-expose-headers": "x-ratelimit-remaining"}
                if mode == "missing":
                    status, data = 404, {}
                elif mode == "rate":
                    status, data = 403, {}
                    headers["x-ratelimit-remaining"] = "0"
                elif "/pulls?" in path:
                    data = [] if mode == "empty" else [{"number": 7}]
                    if mode == "partial":
                        data.append({"number": 8})
                elif "/pulls/8" in path:
                    status, data = 500, {}
                elif "/files?" in path:
                    data = [{"filename": "src/parser.py"}, {"filename": "tests/test_parser.py"}]
                elif "/check-runs?" in path:
                    data = {"total_count": 1, "check_runs": [{"status": "COMPLETED", "conclusion": "SUCCESS"}]}
                    if mode == "ci-missing":
                        status, data = 403, {}
                elif "/status?" in path:
                    data = {"total_count": 0, "statuses": []}
                    if mode == "legacy-failure":
                        data = {"total_count": 1, "statuses": [{"state": "failure"}]}
                else:
                    data = {**detail, "changed_files": 101} if mode == "large" else detail
                route.fulfill(status=status, headers=headers, body=json.dumps(data))

            page.route("https://api.github.com/**", route_api)
            def fill_input(selector: str, value: str) -> None:
                field = page.locator(selector)
                field.click()
                field.press("ControlOrMeta+A")
                field.press("Backspace")
                field.press_sequentially(value)

            page.goto(url)
            expect(page.locator(".pr-card")).to_have_count(5)
            assert requests == [], "The initial sample must work without GitHub"
            expect(page.locator("#plan-meta")).to_have_text("23 min estimated · 7 min left")
            page.locator('[data-budget="15"]').click()
            expect(page.locator("#plan-meta")).to_have_text("11 min estimated · 4 min left")
            expect(page.locator("#plan-body .plan-row")).to_have_count(2)
            fill_input("#plan-minutes", "1")
            expect(page.locator("#plan-overflow")).to_contain_text("5 min over")
            fill_input("#plan-minutes", "0")
            expect(page.locator("#budget-error")).to_be_visible()
            expect(page.locator("#copy-plan")).to_be_disabled()
            page.locator('[data-budget="30"]').click()
            page.locator(".pr-details summary").first.click()
            expect(page.locator(".pr-score").first).to_be_visible()
            page.locator(".pr-details summary").first.click()

            page.add_script_tag(content="Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText: async text => {document.body.dataset.copied = text}}})")
            page.locator("#copy-plan").click()
            expect(page.locator("#demo-status")).to_contain_text("Copied the 30 minute example")
            assert "fictional pull requests" in page.locator("body").get_attribute("data-copied")
            page.add_script_tag(content="Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText: async () => {throw Error('denied')}}})")
            page.locator("#copy-plan").click()
            expect(page.locator("#export-dialog")).to_be_visible()
            assert "Estimated work: 23 minutes" in page.locator("#export-text").input_value()
            expect(page.locator("#export-download")).to_have_attribute("download", "review-plan.md")
            page.keyboard.press("Escape")
            expect(page.locator("#export-dialog")).not_to_be_visible()

            for width, height, name in [(1280, 900, "desktop"), (390, 844, "mobile"), (320, 740, "small-mobile")]:
                page.set_viewport_size({"width": width, "height": height})
                page.evaluate("window.scrollTo(0, 0)")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Horizontal overflow at {width}px"
                page.screenshot(path=str(artifacts / f"demo-{name}.png"), full_page=True)
            page.set_viewport_size({"width": 1280, "height": 900})

            def scan(next_mode: str) -> None:
                nonlocal mode
                mode = next_mode
                fill_input("#repo-input", "https://github.com/example/project/pulls")
                page.locator("#repo-submit").click()

            scan("success")
            expect(page.locator("#source-badge")).to_have_text("Live GitHub data")
            expect(page.locator(".pr-card")).to_have_count(1)
            expect(page.locator(".pr-card h4")).to_contain_text(title)
            assert page.locator(".pr-card img").count() == 0
            assert page.locator("body").get_attribute("data-injected") is None
            assert "repo=example%2Fproject" in page.url
            scan("missing")
            expect(page.locator("#scan-error")).to_be_visible()
            expect(page.locator("#results")).not_to_be_visible()
            expect(page.locator("#scan-error-message")).to_contain_text("couldn't find")
            mode = "success"
            page.locator("#scan-retry").click()
            expect(page.locator("#results")).to_be_visible()
            expect(page.locator("#scan-error")).not_to_be_visible()
            scan("empty")
            expect(page.locator("#queue-body")).to_contain_text("No open pull requests")
            expect(page.locator("#copy-plan")).to_be_disabled()
            expect(page.locator("#plan-body")).to_contain_text("No open pull requests to plan")
            scan("partial")
            expect(page.locator("#demo-status")).to_contain_text("Loaded 1 of 2")
            expect(page.locator("#scan-warning")).to_contain_text("#8 wasn't analyzed")
            expect(page.locator(".pr-card")).to_have_count(1)
            scan("ci-missing")
            expect(page.locator("#scan-warning")).to_contain_text("CI data for #7")
            expect(page.locator(".pr-metadata")).to_contain_text("CI not verified")
            scan("legacy-failure")
            expect(page.locator(".pr-card")).to_contain_text("ask for CI fix")
            scan("large")
            expect(page.locator("#scan-error-message")).to_contain_text("100-file preview limit")
            expect(page.locator("#results")).not_to_be_visible()
            scan("rate")
            expect(page.locator("#scan-error-message")).to_contain_text("public request limit")
            scan("network")
            expect(page.locator("#scan-error-message")).to_contain_text("Couldn't reach GitHub")

            scan("held")
            expect(page.locator("#scan-cancel")).to_be_visible()
            page.locator("#load-sample").click()
            expect(page.locator("#source-badge")).to_have_text("Interactive example")
            expect(page.locator(".pr-card")).to_have_count(5)
            for route in held:
                try:
                    route.fulfill(status=200, body="[]", content_type="application/json")
                except Error:
                    pass  # The browser may already have cancelled the request.
            held.clear()
            expect(page.locator("#source-badge")).to_have_text("Interactive example")
            assert "repo=" not in page.url
            scan("held")
            page.locator("#scan-cancel").click()
            expect(page.locator("#demo-status")).to_contain_text("Scan cancelled")
            expect(page.locator("#repo-submit")).to_be_enabled()

            # Shorten only the demo's deadline; avoid a real 30-second wait.
            page.add_script_tag(content="window.realTimeout = window.setTimeout; window.setTimeout = (fn, ms, ...args) => window.realTimeout(fn, ms === 30000 ? 50 : ms, ...args)")
            scan("held")
            expect(page.locator("#scan-error-message")).to_contain_text("longer than 30 seconds")
            expect(page.locator("#repo-submit")).to_be_enabled()
            page.add_script_tag(content="window.setTimeout = window.realTimeout")
            mode = "success"
            page.goto(url + "?repo=example/project&plan=15")
            expect(page.locator("#source-badge")).to_have_text("Live GitHub data")
            expect(page.locator("#plan-title")).to_have_text("15 minute review plan")
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print("Browser checks passed: sample, budgets, clipboard, mobile, live scan, errors, partial data, cancellation, timeout, and shared URLs.")
    print(f"Screenshots: {artifacts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", help="Path to an existing Playwright-compatible Firefox browser")
    parser.add_argument("--artifacts", type=Path, default=Path(tempfile.gettempdir()) / "maintainer-radar-browser")
    args = parser.parse_args()
    run(args.executable, args.artifacts)
