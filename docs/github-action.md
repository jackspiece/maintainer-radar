# GitHub Action

Maintainer Radar ships as a reusable GitHub Action for repositories that want a
read-only pull request queue report in CI.

Use it when you want the report to appear in the GitHub Actions run summary and
also be saved as an artifact.

## Minimal Workflow

{% raw %}
```yaml
name: Maintainer Radar

on:
  workflow_dispatch:
  schedule:
    - cron: "0 8 * * 1-5"

permissions:
  contents: read
  pull-requests: read

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - name: Build PR report
        id: radar
        uses: JackSpiece/maintainer-radar@v0.20.0
        env:
          GH_TOKEN: ${{ github.token }}
        with:
          repository: ${{ github.repository }}
          format: markdown
          output: maintainer-radar.md
          limit: "50"
          sort: action
          hydrate: "true"
      - uses: actions/upload-artifact@v7
        with:
          name: maintainer-radar
          path: ${{ steps.radar.outputs.report-path }}
```
{% endraw %}

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `repository` | current workflow repository | Repository to scan in `owner/name` form. |
| `format` | `markdown` | Report format: `markdown`, `html`, `json`, or `csv`. |
| `output` | format-specific path | Single-line output file path (no CR or LF). Defaults to `maintainer-radar.md`, `.html`, `.json`, or `.csv`; review plans default to `review-plan.md`, `review-plan.html`, or `review-plan.json`. |
| `limit` | `50` | Maximum pull requests to scan. |
| `label` | empty | Only include pull requests with this label. |
| `author` | empty | Only include pull requests by this author. |
| `stale-days` | empty | Only include pull requests quiet for at least N days. |
| `updated-since` | empty | Only include pull requests updated on or after this ISO date. |
| `action` | empty | Only include pull requests with this action slug, such as `review-now`. |
| `min-score` | empty | Only include pull requests with reviewability greater than or equal to N. |
| `max-risk` | empty | Only include pull requests with risk less than or equal to N. |
| `sort` | `action` | Sort order: `input`, `action`, `score`, `risk`, `stale`, or `number`. |
| `top` | empty | Keep only the first N pull requests after sorting. |
| `group-by` | empty | Group Markdown and HTML queue reports. Supported value: `action`. |
| `review-plan-minutes` | empty | Render a Markdown, HTML, or JSON review-session plan for this many maintainer minutes. |
| `config` | empty | Optional path to a Maintainer Radar config JSON file. |
| `hydrate` | `true` | Fetch full PR details for body, file, review, merge readiness, and richer scoring signals. |
| `step-summary` | `true` | Publish Markdown output or a compact summary to the Actions run summary. |

Output paths may contain spaces, Unicode, and leading hyphens. Carriage returns
(CR) and line feeds (LF) are rejected before creating directories, scanning, or
writing Action outputs, so `report-path` always remains one output record.
Labels and config paths beginning with a hyphen are passed as literal CLI values.

## Outputs

| Output | Description |
| --- | --- |
| `report-path` | Path to the generated report file. Use it with `actions/upload-artifact`. |
| `summary-json` | JSON summary for the generated report. |
| `queue-headline` | One-line human summary of the queue state. |
| `attention-level` | Queue attention level: `quiet`, `review`, `triage`, `follow-up`, or `blocked`. |
| `attention-reason` | One-line reason for the queue attention level. |
| `workflow-mode` | Recommended maintainer workflow mode, such as `blocker-sweep`, `review-sprint`, or `author-follow-up`. |
| `workflow-recommendation` | One-line recommended maintainer workflow for the scanned queue. |
| `next-session-brief` | One-line digest of what fits in the next 60 maintainer minutes. |
| `total` | Number of pull requests in the report after filters. |
| `review-now` | Number of pull requests ready for review. |
| `author-follow-up` | Number of pull requests needing author follow-up. |
| `ci-blocked` | Number of pull requests with failing CI. |
| `ci-pending` | Number of pull requests waiting for CI. |
| `merge-conflicts` | Number of pull requests with merge conflicts. |
| `branch-behind` | Number of pull requests behind the base branch. |
| `merge-gated` | Number of pull requests blocked by repository merge gates. |
| `review-requested` | Number of pull requests with requested reviewers or teams. |
| `maintainer-blocked` | Number of pull requests blocked by maintainer feedback or labels. |
| `large-or-triage` | Number of pull requests that are too large or need triage. |
| `stale` | Number of pull requests quiet for 7 or more days. |
| `quick-unblocks` | Number of pull requests that only need quick maintainer unblock action. |
| `watch-only` | Number of pull requests waiting for CI or author action. |
| `next-session-prs` | Number of pull requests that fit in the default 60-minute session digest. |
| `next-session-minutes` | Estimated active maintainer minutes in the default 60-minute session digest. |
| `next-session-deferred` | Number of pull requests deferred by the default 60-minute session digest. |
| `average-score` | Average reviewability score for the report. |
| `plan-budget-minutes` | Review-plan budget in minutes when `review-plan-minutes` is set. |
| `planned-prs` | Number of pull requests included in the review plan. |
| `planned-minutes` | Estimated active maintainer minutes in the review plan. |
| `remaining-minutes` | Unused minutes left in the review-plan budget. |
| `deferred-prs` | Number of pull requests deferred by the review-plan budget. |
| `watch-only-prs` | Number of wait-for-CI or wait-for-author pull requests in the review plan. |

Use summary outputs in later workflow steps:

{% raw %}
```yaml
- run: |
    echo "${{ steps.radar.outputs.queue-headline }}"
    echo "Attention: ${{ steps.radar.outputs.attention-level }}"
    echo "${{ steps.radar.outputs.attention-reason }}"
    echo "Workflow: ${{ steps.radar.outputs.workflow-mode }}"
    echo "${{ steps.radar.outputs.workflow-recommendation }}"
    echo "${{ steps.radar.outputs.next-session-brief }}"
    echo "${{ steps.radar.outputs.review-now }} PRs are ready for review"
```
{% endraw %}

Use `queue-headline` when a later workflow step needs a concise notification
line without parsing `summary-json`. Use `attention-level` when a workflow needs
to decide whether to notify humans. Use `workflow-mode` when a workflow or
handoff note needs to choose the next maintainer session shape.

Use `next-session-brief` when a notification should tell maintainers what can
fit in the next hour without opening the full artifact. Use
`next-session-prs`, `next-session-minutes`, `next-session-deferred`,
`quick-unblocks`, and `watch-only` when a dashboard needs the same digest as
structured numbers.

For handoff or escalation workflows, use `maintainer-blocked` to detect PRs
that already have maintainer feedback or blocking labels.

Use `merge-conflicts`, `branch-behind`, and `merge-gated` when a dashboard or
notification should separate author-fixable merge readiness work from ordinary
review queue work.

For review-plan workflows, use `planned-prs`, `planned-minutes`,
`remaining-minutes`, `deferred-prs`, and `watch-only-prs` in later notification
or dashboard steps without parsing the Markdown artifact.

## Report Formats

Markdown is best for a run summary. HTML is best when maintainers want a local
browser-friendly artifact. JSON and CSV are useful for dashboards and
spreadsheets.

{% raw %}
```yaml
with:
  repository: ${{ github.repository }}
  format: html
  output: maintainer-radar.html
```
{% endraw %}

For HTML, JSON, and CSV reports, the action still writes a compact Markdown
summary to the run summary by default. Disable that with:

```yaml
with:
  step-summary: "false"
```

For HTML and JSON review-plan artifacts, the run summary also includes the plan
budget, planned PR count, estimated active time, remaining minutes, deferred
count, and watch-only count.

Review plans also include draft follow-up comments for PRs that need author
action. The Action does not post those comments; it only writes the draft text
to the report artifact or JSON fields. HTML review-plan artifacts include Copy
Draft buttons for those drafts.

## Focused Reports

Use filters when a scheduled report should answer one review-session question
instead of listing the whole queue:

{% raw %}
```yaml
with:
  repository: ${{ github.repository }}
  action: review-now
  min-score: "80"
  top: "10"
  group-by: action
```
{% endraw %}

For a time-boxed maintainer session, add a review plan. Use Markdown when you
want the plan in the run summary:

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

Use HTML when you want a browser-friendly plan artifact:

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

See [review-plan.md](review-plan.md) for how the estimates work.

For stale follow-up sweeps:

{% raw %}
```yaml
with:
  repository: ${{ github.repository }}
  stale-days: "14"
  sort: stale
```
{% endraw %}

## Project Config

Use the `config` input when a repository has custom size, stale, test path, doc
path, or generated file thresholds:

{% raw %}
```yaml
with:
  repository: ${{ github.repository }}
  config: .maintainer-radar.json
```
{% endraw %}

## Bootstrap Command

If you already use the CLI locally, generate the workflow instead of writing YAML
by hand. Text options must be single-line values and cannot contain characters
excluded by YAML's printable character set; invalid values fail with an option-specific
error before a workflow is printed or written. Tabs and printable Unicode remain
supported:

```bash
maintainer-radar init-action --path .github/workflows/maintainer-radar.yml
maintainer-radar init-action --config .maintainer-radar.json --path .github/workflows/maintainer-radar.yml
maintainer-radar init-action --action review-now --min-score 80 --top 10 --path .github/workflows/review-ready.yml
maintainer-radar init-action --review-plan-minutes 30 --path .github/workflows/review-plan.yml
```

`--action-ref` supplies the text of the action's `uses` value, such as
`owner/repository@tag`, `owner/repository/path@commit`, `./local-action`, or
`docker://image:tag`. Leading and trailing whitespace is trimmed; an empty
value uses the default published tag. The generator serializes this value as
one YAML string, quoting and escaping when needed, including U+0085, U+2028,
and U+2029 separators. Simple repository, local-path, and Docker references
retain their unquoted output.
Quotes in the supplied value are literal data, not preformatted YAML.

This is YAML serialization, not validation that a reference exists or that
GitHub accepts it. Expression-like text is preserved, and expression support
in each workflow field remains subject to GitHub's rules. The generator does
not evaluate expressions or change the existing expression-bearing inputs.

## Permissions

The action is read-only. It needs:

```yaml
permissions:
  contents: read
  pull-requests: read
```

It does not approve, reject, merge, label, or comment on pull requests.

## Troubleshooting

- If the action cannot read pull requests, confirm {% raw %}`GH_TOKEN: ${{ github.token }}`{% endraw %}
  is present on the action step.
- If the report is shallow, keep `hydrate: "true"` so the action can inspect PR
  bodies, files, reviews, and richer signals.
- If the workflow is too slow for a large queue, lower `limit` or set `top`.
- If you only want downloadable artifacts, set `step-summary: "false"`.
