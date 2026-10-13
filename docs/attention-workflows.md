# Attention Workflows

Maintainer Radar exposes queue attention outputs so scheduled workflows can
decide whether a maintainer needs to look at the queue now.

Use these when the full report is useful, but the first question is:

> Should this queue interrupt a maintainer today?

## Outputs

| Output | Meaning |
| --- | --- |
| `queue-headline` | One-line summary of the queue state |
| `attention-level` | `quiet`, `review`, `triage`, `follow-up`, or `blocked` |
| `attention-reason` | One-line reason for the attention level |
| `workflow-mode` | Suggested maintainer session shape |
| `workflow-recommendation` | One-line recommendation for the next maintainer workflow |
| `next-session-brief` | One-line digest of what fits in the next 60 maintainer minutes |
| `next-session-prs` | PRs that fit in the default 60-minute session digest |
| `next-session-minutes` | Estimated active maintainer minutes in that default session |
| `quick-unblocks` | PRs that only need quick unblock action |
| `watch-only` | PRs waiting for CI or author action |

The levels are ordered for maintainer urgency:

- `blocked`: failing CI, merge conflicts, merge gates, or unresolved maintainer blockers
- `follow-up`: author follow-up, branch-behind state, pending CI, or stale work
- `triage`: large or unclear work that needs manual routing
- `review`: at least one PR appears ready for maintainer review
- `quiet`: no urgent signal in the filtered queue

## Print A Queue Brief

{% raw %}
```yaml
- name: Print queue attention
  run: |
    echo "${{ steps.radar.outputs.queue-headline }}"
    echo "Attention: ${{ steps.radar.outputs.attention-level }}"
    echo "${{ steps.radar.outputs.attention-reason }}"
    echo "Workflow: ${{ steps.radar.outputs.workflow-mode }}"
    echo "${{ steps.radar.outputs.workflow-recommendation }}"
    echo "${{ steps.radar.outputs.next-session-brief }}"
```
{% endraw %}

## Warn Only When Humans Should Look

{% raw %}
```yaml
- name: Warn on active queue
  if: steps.radar.outputs.attention-level != 'quiet'
  run: |
    echo "::warning title=Maintainer Radar::${{ steps.radar.outputs.queue-headline }}"
    echo "${{ steps.radar.outputs.attention-reason }}"
    echo "${{ steps.radar.outputs.workflow-recommendation }}"
```
{% endraw %}

This keeps the scheduled workflow read-only while still making active queues
visible in the run.

## Separate Blocked Queues From Review Queues

{% raw %}
```yaml
- name: Blocked queue note
  if: steps.radar.outputs.attention-level == 'blocked'
  run: |
    echo "Blocked queue: ${{ steps.radar.outputs.attention-reason }}"

- name: Review queue note
  if: steps.radar.outputs.attention-level == 'review'
  run: |
    echo "Review queue: ${{ steps.radar.outputs.queue-headline }}"
```
{% endraw %}

Use this when maintainers want merge conflicts, failing CI, and unresolved
feedback to be handled differently from normal review-ready work.

## Filter Before Notifying

Attention outputs respect the report filters. For example, this workflow only
decides attention level for stale PRs:

{% raw %}
```yaml
- uses: JackSpiece/maintainer-radar@v0.21.0
  id: radar
  env:
    GH_TOKEN: ${{ github.token }}
  with:
    repository: ${{ github.repository }}
    stale-days: "14"
    sort: stale
    hydrate: "true"

- name: Stale queue attention
  if: steps.radar.outputs.attention-level != 'quiet'
  run: |
    echo "${{ steps.radar.outputs.queue-headline }}"
    echo "${{ steps.radar.outputs.attention-reason }}"
    echo "${{ steps.radar.outputs.workflow-recommendation }}"
```
{% endraw %}

The Action still does not approve, reject, merge, label, or comment on pull
requests.
