# Filter an exported HTML queue

Full, ungrouped HTML reports include local text search, an action selector, a
**Reset filters** button and a live **Showing N of M PRs** count. Open the saved
file in a browser; no server, network connection or account is needed.

```sh
maintainer-radar from-json examples/sample-prs.json \
  --now 2026-06-01T00:00:00Z --format html > report.html
```

The committed [fictional report](../examples/output/sample-report.html) is a
ready-to-open example. Download or open the actual HTML file in a browser;
a repository's source viewer does not execute its local controls.

1. Search for `parser` to find the cache-race PR.
2. Choose **review now** to combine the text and action filters.
3. Choose another action to see the empty state when nothing matches.
4. Select **Reset filters** to restore every row and return focus to Search queue.

## Search and counts

- Search matches literal text anywhere in the displayed cells: PR number/title,
  action, next step, score, risk impact and signals. It does not search hidden
  metadata, author fields or link destinations.
- Leading and trailing query whitespace is ignored. Text and query use Unicode
  NFC normalization and JavaScript's locale-neutral lowercase conversion.
  `CAFÉ` and a decomposed `CAFÉ` match `Café`; accents remain significant, so
  `cafe` does not. This is not locale-specific collation or fuzzy matching.
- Text and action filters combine with AND. Action selection matches the exact
  action label; the menu contains each action present in this report once.
- Filtering hides rows without changing their order, scores, text or links.
  The count refers to this exported queue, which may already have been limited
  by CLI options. The summary metrics above it always describe the full export.
- Nothing is sent, fetched, stored or remembered by these filters. Existing PR
  links still open their original destinations when you intentionally follow
  one. Filter terms are never put in the file URL or a form submission.

## Keyboard, small screens and JavaScript

Search, Action and Reset have visible labels and native keyboard controls.
Reset puts focus in the search field. The count is a polite live status for
assistive technology. The table is a labeled, focusable horizontal scroll
region on narrow screens; the document itself does not need horizontal scrolling.

The original rows are in the HTML. If JavaScript is disabled or unavailable,
all rows and links remain readable, the interactive controls stay hidden, and
a fallback message explains why. A genuinely empty report keeps its ordinary
empty-report message and a 0-of-0 count.

This first version is intentionally limited to full, ungrouped HTML reports.
Grouped reports, summaries, review plans and comment drafts keep their existing
behavior and counts. Markdown, CSV, JSON and the separate hosted demo are
unchanged. To export a filterable queue, omit `--group-by action`, `--summary-only`
and review-plan/comment options.

## Verification

The Python suite checks progressive enhancement, labels, escaping, fallback
content, action order, non-mutating rendering and excluded report modes.
Optional browser checks open the reports directly with `file://` URLs, exercise
keyboard and repeated flows, Unicode/hostile text, no matches, reset, original
links, no-JavaScript behavior and 1280/390/320-pixel widths. They reject attempted
HTTP(S) requests and use fictional records only.

```sh
PYTHONPATH=src python -m unittest discover -s tests
# Requires Playwright plus an installed compatible browser:
PYTHONPATH=src python tests/browser_report_filters.py
PYTHONPATH=src python tests/browser_report_filters.py \
  --executable /path/to/compatible/firefox --artifacts /tmp/radar-report-check
# Chromium can be selected in environments that support it:
PYTHONPATH=src python tests/browser_report_filters.py --engine chromium
```

These focused checks do not claim a comprehensive accessibility audit or
verification on a physical mobile device.
