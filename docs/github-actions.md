# GitHub Actions Integration

Maintainer Radar can run in CI and upload Markdown or HTML triage reports as
artifacts. This is useful for maintainers who want a daily queue snapshot
without installing another GitHub App.

For the reusable action contract, inputs, outputs, and troubleshooting, see
[github-action.md](github-action.md).

The fastest setup is the bootstrap command:

```bash
maintainer-radar init-action --path .github/workflows/maintainer-radar.yml
```

This writes a workflow that uses the reusable action:

{% raw %}
```yaml
- uses: actions/setup-python@v7
  with:
    python-version: "3.12"
- uses: JackSpiece/maintainer-radar@v0.20.0
  id: radar
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: markdown
```
{% endraw %}

For an HTML artifact:

```bash
maintainer-radar init-action \
  --report-format html \
  --path .github/workflows/maintainer-radar.yml
```

For a focused review-ready report:

```bash
maintainer-radar init-action \
  --action review-now \
  --min-score 80 \
  --top 10 \
  --group-by action \
  --path .github/workflows/review-ready.yml
```

For a daily time-boxed review plan:

```bash
maintainer-radar init-action \
  --review-plan-minutes 30 \
  --group-by action \
  --path .github/workflows/review-plan.yml
```

The command prints YAML to stdout when `--path` is omitted. When `--path` is
provided, it creates parent directories and refuses to overwrite an existing
workflow unless `--force` is passed.

Generated review-plan workflows use `review-plan.md`, `review-plan.html`, or
`review-plan.json` as the artifact path so the uploaded file is easy to
identify.

The action publishes Markdown output to the GitHub Actions run summary by
default. For HTML, JSON, and CSV artifacts, it also publishes a compact Markdown
summary so the first read does not require downloading an artifact. Use
`--no-step-summary` with `init-action`, or `step-summary: "false"` in direct
action usage, if you only want uploaded artifacts.

The reusable Action also exposes summary outputs such as `queue-headline`,
`attention-level`, `attention-reason`, `workflow-mode`,
`workflow-recommendation`, `next-session-brief`, `next-session-prs`,
`next-session-minutes`, `quick-unblocks`, `watch-only`, `review-now`,
`ci-blocked`, `maintainer-blocked`, `stale`, and `average-score` for later
workflow steps.

When `review-plan-minutes` is set, it also exposes plan outputs such as
`planned-prs`, `planned-minutes`, `remaining-minutes`, `deferred-prs`, and
`watch-only-prs`.

Copy-paste examples are available in:

- [examples/github-actions/daily-markdown-report.yml](../examples/github-actions/daily-markdown-report.yml)
- [examples/github-actions/daily-html-report.yml](../examples/github-actions/daily-html-report.yml)
- [examples/github-actions/review-ready-report.yml](../examples/github-actions/review-ready-report.yml)
- [examples/github-actions/review-plan-report.yml](../examples/github-actions/review-plan-report.yml)

## Scheduled Queue Report

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
  triage:
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

## Focused Review-Ready Report

For a smaller scheduled report that only shows PRs ready for maintainer review:

{% raw %}
```yaml
- name: Build review-ready report
  id: radar
  uses: JackSpiece/maintainer-radar@v0.20.0
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: markdown
    output: review-ready.md
    action: review-now
    min-score: "80"
    top: "10"
    group-by: action
    sort: score
    hydrate: "true"
- uses: actions/upload-artifact@v7
  with:
    name: review-ready
    path: ${{ steps.radar.outputs.report-path }}
```
{% endraw %}

## Time-Boxed Review Plan

For a scheduled report that tells maintainers what fits in the next review
session, use Markdown when you want the plan in the run summary:

{% raw %}
```yaml
- name: Build 30 minute review plan
  id: radar
  uses: JackSpiece/maintainer-radar@v0.20.0
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: markdown
    output: review-plan.md
    review-plan-minutes: "30"
    sort: action
    hydrate: "true"
- uses: actions/upload-artifact@v7
  with:
    name: review-plan
    path: ${{ steps.radar.outputs.report-path }}
```
{% endraw %}

Use HTML when you want a browser-friendly plan artifact:

{% raw %}
```yaml
- name: Build HTML review plan
  id: radar
  uses: JackSpiece/maintainer-radar@v0.20.0
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: html
    output: review-plan.html
    review-plan-minutes: "30"
    sort: action
    hydrate: "true"
- uses: actions/upload-artifact@v7
  with:
    name: review-plan-html
    path: ${{ steps.radar.outputs.report-path }}
```
{% endraw %}

Use JSON when a dashboard or later workflow step should consume the plan:

{% raw %}
```yaml
- name: Build JSON review plan
  id: radar
  uses: JackSpiece/maintainer-radar@v0.20.0
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: json
    output: review-plan.json
    review-plan-minutes: "30"
    sort: action
    hydrate: "true"
- uses: actions/upload-artifact@v7
  with:
    name: review-plan-json
    path: ${{ steps.radar.outputs.report-path }}
```
{% endraw %}

## HTML Artifact

For a static browser-friendly report:

{% raw %}
```yaml
- name: Build HTML report
  id: radar
  uses: JackSpiece/maintainer-radar@v0.20.0
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: html
    output: maintainer-radar.html
    limit: "50"
    sort: action
    hydrate: "true"
- uses: actions/upload-artifact@v7
  with:
    name: maintainer-radar-html
    path: ${{ steps.radar.outputs.report-path }}
```
{% endraw %}

## Summary-Only Report

For a compact status artifact:

{% raw %}
```yaml
- name: Build PR summary
  env:
    GH_TOKEN: ${{ github.token }}
  run: maintainer-radar repo ${{ github.repository }} --limit 100 --summary-only > maintainer-radar-summary.md
```
{% endraw %}

## Notes

- The tool uses `gh` for live GitHub data.
- GitHub-hosted runners include `gh` by default.
- The report is advisory. It does not approve, reject, or modify pull requests.
- Keep permissions read-only unless your own workflow adds posting behavior.
