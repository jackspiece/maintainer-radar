# JSON Output

Maintainer Radar supports JSON output for scripts and dashboards.

## Full Queue Output

```bash
maintainer-radar repo owner/repo --format json
```

The command returns a list of analyzed pull requests.

Important fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `number` | integer | Pull request number |
| `title` | string | Pull request title |
| `url` | string | Pull request URL |
| `author` | string | Author login |
| `risk` | integer | Risk score from 0 to 100 |
| `reviewability` | integer | Reviewability score from 0 to 100 |
| `action` | string | Recommended maintainer action |
| `next_step` | string | Suggested next maintainer move |
| `signals` | array | Positive review signals |
| `flags` | array | Risk flags |
| `score_breakdown` | array | Heuristics that changed the PR risk score |
| `raw_risk` | integer | Risk before clamping to the 0 to 100 range |
| `checks` | object | Check summary |
| `files` | object | File shape summary |
| `merge_state_status` | string | Normalized merge state, when available |
| `mergeable` | string | Normalized mergeability state, when available |
| `review_requests` | integer | Requested reviewer and team count |
| `stale_days` | integer or null | Days since last update |

Each score breakdown entry has:

| Field | Type | Meaning |
| --- | --- | --- |
| `label` | string | Heuristic name |
| `risk_delta` | integer | Risk change from that heuristic |
| `kind` | string | `signal` or `flag` |

## Opt-in capture provenance (unreleased source)

`repo`, `author`, and `from-json` support `--format json --snapshot` for full
queue reports. This emits a versioned object with `items` and `provenance`,
including the effective config and capture settings. Ordinary `--format json`
continues to emit the same array. Use `compare` with either format; existing
array consumers should keep using the default or select the envelope's `items`.

See [snapshot capture settings](snapshot-provenance.md) for the schema, a
reproducible config-change example, privacy notes, and compatibility limits.

## Summary Output

```bash
maintainer-radar repo owner/repo --summary-only --format json
```

Example:

```json
{
  "total": 30,
  "review_now": 8,
  "author_follow_up": 6,
  "ci_blocked": 2,
  "ci_pending": 3,
  "merge_conflicts": 1,
  "branch_behind": 2,
  "merge_gated": 3,
  "review_requested": 7,
  "maintainer_blocked": 5,
  "large_or_triage": 4,
  "stale": 9,
  "average_score": 72,
  "next_session_prs": 6,
  "next_session_minutes": 55,
  "next_session_deferred": 7,
  "quick_unblocks": 3,
  "watch_only": 4,
  "next_session_brief": "Next 60 minutes: handle 6 PRs in about 55 minutes; 3 quick unblocks; 7 PRs deferred by the session budget; 4 PRs watch-only.",
  "queue_headline": "30 PRs scanned: 8 ready for review; 6 need author follow-up; 5 blocked or waiting on CI; 1 with merge conflict; 2 behind base; 3 blocked by merge gates; 5 PRs have unresolved maintainer blockers.",
  "attention_level": "blocked",
  "attention_reason": "5 PRs have unresolved maintainer blockers.",
  "workflow_mode": "blocker-sweep",
  "workflow_recommendation": "Clear maintainer blockers, merge conflicts, failing CI, or merge gates before assigning review time."
}
```

Summary fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `total` | integer | Number of analyzed PRs after filters |
| `review_now` | integer | PRs recommended for immediate review |
| `author_follow_up` | integer | PRs needing author response |
| `ci_blocked` | integer | PRs with failing CI |
| `ci_pending` | integer | PRs waiting for CI |
| `merge_conflicts` | integer | PRs with merge conflicts |
| `branch_behind` | integer | PRs behind the base branch |
| `merge_gated` | integer | PRs blocked by repository merge gates |
| `review_requested` | integer | PRs with requested reviewers or teams |
| `maintainer_blocked` | integer | PRs blocked by maintainer feedback or labels |
| `large_or_triage` | integer | PRs that are too large or need triage |
| `stale` | integer | PRs quiet for 7+ days |
| `average_score` | integer | Average reviewability score |
| `next_session_prs` | integer | PRs that fit in the default 60-minute maintainer session digest |
| `next_session_minutes` | integer | Estimated active maintainer minutes in that default session |
| `next_session_deferred` | integer | PRs deferred by the default session budget |
| `quick_unblocks` | integer | PRs that only need a quick unblock action |
| `watch_only` | integer | PRs waiting for CI or author action |
| `next_session_brief` | string | One-line 60-minute maintainer session digest |
| `queue_headline` | string | One-line human summary of the queue state |
| `attention_level` | string | Queue attention level: `quiet`, `review`, `triage`, `follow-up`, or `blocked` |
| `attention_reason` | string | One-line reason for the queue attention level |
| `workflow_mode` | string | Recommended workflow mode, such as `blocker-sweep`, `review-sprint`, `author-follow-up`, `triage-pass`, `ci-watch`, `stale-sweep`, or `quiet` |
| `workflow_recommendation` | string | One-line recommended maintainer workflow for the scanned queue |

## Script Example

```bash
score=$(maintainer-radar repo owner/repo --summary-only --format json |
  python -c 'import json,sys; print(json.load(sys.stdin)["average_score"])')

echo "Average reviewability: $score"
```

## Stdin Input

Use `from-json -` to read PR data from stdin:

```bash
cat examples/sample-prs.json | maintainer-radar from-json -
gh api repos/owner/repo/pulls | maintainer-radar from-json -
```
