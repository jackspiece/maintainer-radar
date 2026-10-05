# Queue snapshot comparison

Before: 2 PRs. After: 2 PRs.

Newly observed: 0. No longer observed: 0. Changed: 1. Unchanged in compared fields: 1.

## Capture settings

Recorded settings differ. Interpret score and queue changes with caution.

- Before: Radar 0&#46;21&#46;0; analysis time 2026&#45;06&#45;01T00&#58;00&#58;00Z; observed 2, emitted 2.
- After: Radar 0&#46;21&#46;0; analysis time 2026&#45;06&#45;01T00&#58;00&#58;00Z; observed 2, emitted 2.

| Setting | Before | After |
| --- | --- | --- |
| config.large_diff_lines | 500 | 50 |

- Capture settings are self-reported, not independently verified. Matching recorded settings do not establish equivalent or complete coverage. Offline export coverage and hydration are unknown; analysis times and observed/output counts are context, not comparable settings.
- Newly observed and no longer observed describe only these snapshots. Absence does not establish that a pull request was closed or merged.
- Score and action differences are saved observations, not proof of code progress or a cause of change. No records are re-scored and no network requests are made.

Compared fields: title, action, risk, reviewability, next_step, checks, flags, signals.

## Newly observed

None.

## No longer observed

None.

## Changed observations

### [#42 Fix parser cache race](<https://github.com/example/project/pull/42>)

| Field | Before | After |
| --- | --- | --- |
| risk | 0 | 7 |
| reviewability | 100 | 93 |
| flags | &#91;&#34;incomplete file list&#34;&#93; | &#91;&#34;incomplete file list&#34;&#44; &#34;large diff&#34;&#93; |
