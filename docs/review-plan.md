# Review Plans

Review plans turn a pull request queue into a time-boxed maintainer session.

Use this when the question is not "what is in the queue?" but "what should I do
with the next 30 minutes?"

```bash
maintainer-radar repo owner/repo --hydrate --sort action --review-plan-minutes 30
```

The plan can be Markdown for a terminal, GitHub Actions run summary, issue, or
maintainer handoff note. It can be HTML for a browser-friendly artifact, or JSON
for dashboards and automation:

```bash
maintainer-radar repo owner/repo --hydrate --sort action --format html --review-plan-minutes 30
maintainer-radar repo owner/repo --hydrate --sort action --format json --review-plan-minutes 30
```

You can also try this without installing anything in the browser preview:

```text
https://jackspiece.github.io/maintainer-radar/?repo=python/cpython
```

Scan a public repository, set the plan minutes, and use **Copy Plan**.

## What The Plan Includes

- the time budget
- planned PRs that fit the budget
- estimated active maintainer time per PR
- next-step guidance for each planned PR
- deferred PRs that did not fit the budget
- watch-only PRs that are waiting for CI or author action
- draft follow-up comments for PRs that need author action, CI fixes, smaller
  scope, or a ready-for-review update

## How Time Is Estimated

The estimate is deterministic and intentionally rough. It is meant to help
maintainers budget attention, not predict exact review time.

- small review-now PRs usually count as 12 minutes
- docs-only review-now PRs count lower
- medium or larger reviewable PRs count higher
- review-with-caution PRs add extra inspection time
- quick unblock actions such as CI fix, author follow-up, or smaller-PR request
  count as 5 minutes
- wait-for-CI and wait-for-author PRs are listed as watch-only items

## Draft Follow-ups

Review plans stay read-only. They do not post comments, label PRs, or contact
authors. When a planned or deferred item needs author action, the plan includes
a draft follow-up comment that a maintainer can edit before posting.

HTML review-plan artifacts include a **Copy Draft** button for each draft
follow-up. This is meant for CI artifacts and local handoff files where the
maintainer wants to copy the ask quickly, then edit it before posting.

JSON plans include the same text in `draft_follow_up_comment` for each entry, so
handoff tools and dashboards can show the draft without scraping Markdown.

## Scheduled Review Plan

Generate a workflow that puts the review plan in the run summary every weekday:

```bash
maintainer-radar init-action \
  --review-plan-minutes 30 \
  --group-by action \
  --path .github/workflows/maintainer-radar.yml
```

Or configure the reusable Action directly:

{% raw %}
```yaml
with:
  repository: ${{ github.repository }}
  format: markdown
  sort: action
  review-plan-minutes: "30"
  hydrate: "true"
```
{% endraw %}

Use Markdown output when you want the plan in the Actions run summary. Use HTML
output when you want a downloadable browser-friendly plan artifact. Use JSON
output when a later workflow or dashboard should consume the plan:

{% raw %}
```yaml
with:
  repository: ${{ github.repository }}
  format: html
  output: review-plan.html
  sort: action
  review-plan-minutes: "30"
  hydrate: "true"
```
{% endraw %}

{% raw %}
```yaml
with:
  repository: ${{ github.repository }}
  format: json
  output: review-plan.json
  sort: action
  review-plan-minutes: "30"
  hydrate: "true"
```
{% endraw %}

When the reusable Action runs with `review-plan-minutes`, it also exposes
structured plan outputs for later workflow steps:

- `planned-prs`
- `planned-minutes`
- `remaining-minutes`
- `deferred-prs`
- `watch-only-prs`

For example:

{% raw %}
```yaml
- run: echo "${{ steps.radar.outputs.planned-prs }} PRs fit this review block"
```
{% endraw %}

## Why This Is Different

AI reviewers inspect code after someone chooses a PR. Maintainer Radar helps
choose where maintainer attention should go before that review starts. It stays
read-only and does not approve, reject, merge, label, or comment on pull
requests.

## Literal Metadata in Markdown

Markdown reports, review plans, and browser exports display titles and other
metadata as literal text. Pipes cannot create extra table columns, and LF, CR,
and CRLF line endings become spaces at the rendering boundary. Markdown syntax
and HTML in a title are displayed rather than interpreted. Link destinations
encode Markdown delimiters without changing existing percent escapes or
entity-looking query values.

The CLI renders HTTP(S) links, including links to other forges; the browser demo
continues to accept only HTTPS GitHub links. This is a scheme/format check, not
a guarantee that a destination is trustworthy. JSON and CSV preserve the source
metadata, including its original line endings and punctuation.
