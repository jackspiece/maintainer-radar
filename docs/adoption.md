# Adoption Guide

Use Maintainer Radar in one repository first. The goal is a useful queue brief,
not another required maintainer ritual.

## Preview A Real Queue

Start with the browser preview on a public repository:

```text
https://jackspiece.github.io/maintainer-radar/?repo=owner/repo&group=action
```

If the grouped view matches how maintainers already think about the queue, add a
scheduled workflow.

From a terminal, start with a recommendation when you want a short answer before
opening the full report:

```bash
maintainer-radar recommend https://github.com/owner/repo/pulls
```

The recommendation prints the queue headline, attention level, suggested
workflow, next-session brief, and the exact report or workflow command to run
next.

If the first scan is too noisy or too forgiving for the repository, generate a
profiled config before wiring the scheduled report:

```bash
maintainer-radar init-config --profile strict --path .maintainer-radar.json
maintainer-radar init-config --profile large-repo --path .maintainer-radar.json
```

For the common case, write both the config and scheduled workflow in one step:

```bash
maintainer-radar init-repo --profile balanced
```

## Daily Queue Brief

Use this when maintainers want one read-only report every weekday:

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
          group-by: action
          hydrate: "true"
      - uses: actions/upload-artifact@v7
        with:
          name: maintainer-radar
          path: ${{ steps.radar.outputs.report-path }}
```
{% endraw %}

The Markdown report appears in the run summary and is also uploaded as an
artifact.

## Review-Ready Queue

Use this when the queue is large and maintainers only want PRs likely to be
worth reviewing now:

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
    sort: score
    group-by: action
    hydrate: "true"
```
{% endraw %}

This keeps the report short enough to scan during a review session.

## 30 Minute Review Plan

Use this when maintainers want a concrete plan for a short review block:

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
```
{% endraw %}

The plan estimates active maintainer time, lists PRs that fit the budget, and
keeps wait-for-CI or wait-for-author items in a watch-only section.

Every summary also includes a default next-session digest for the next 60
minutes, even when a custom review plan is not requested. Use that for quick
notifications where maintainers only need to know whether review time is worth
spending now.

## Stale Follow-Up Queue

Use this when the team needs to clear old contributor threads:

{% raw %}
```yaml
- name: Build stale follow-up report
  id: radar
  uses: JackSpiece/maintainer-radar@v0.20.0
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: markdown
    output: stale-follow-up.md
    stale-days: "14"
    sort: action
    group-by: action
    hydrate: "true"
```
{% endraw %}

Read the next-step column before writing replies. Maintainer Radar drafts
priorities, not decisions.

## Merge Readiness Watch

Use Action outputs when maintainers want a dashboard or notification to separate
author-fixable branch work from normal review work:

{% raw %}
```yaml
- name: Build queue brief
  id: radar
  uses: JackSpiece/maintainer-radar@v0.20.0
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    format: markdown
    output: maintainer-radar.md
    sort: action
    hydrate: "true"

- name: Print merge readiness totals
  run: |
    echo "${{ steps.radar.outputs.queue-headline }}"
    echo "Attention: ${{ steps.radar.outputs.attention-level }}"
    echo "${{ steps.radar.outputs.attention-reason }}"
    echo "Workflow: ${{ steps.radar.outputs.workflow-mode }}"
    echo "${{ steps.radar.outputs.workflow-recommendation }}"
    echo "${{ steps.radar.outputs.next-session-brief }}"
    echo "Merge conflicts: ${{ steps.radar.outputs.merge-conflicts }}"
    echo "Branch behind: ${{ steps.radar.outputs.branch-behind }}"
    echo "Merge gated: ${{ steps.radar.outputs.merge-gated }}"
    echo "Review requested: ${{ steps.radar.outputs.review-requested }}"
```
{% endraw %}

This keeps merge conflicts, stale branches, repository merge gates, and reviewer
requests visible without parsing the report artifact.

## First Run Checklist

- Run the workflow manually with `workflow_dispatch`.
- Confirm the report appears in the Actions run summary.
- Open the uploaded artifact if the summary is too long.
- Check that the top few PRs feel correctly grouped.
- If the queue is noisy, tighten the workflow with `action`, `min-score`,
  `stale-days`, `label`, `author`, or `top`.

## Keep It Read-Only

Maintainer Radar does not approve, reject, merge, label, or comment on pull
requests. Treat the report as a queue map for humans.
