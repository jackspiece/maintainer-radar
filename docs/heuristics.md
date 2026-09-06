# Heuristics

Maintainer Radar uses deterministic rules. The score is not truth. It is a
routing hint for maintainer attention.

Every analyzed PR includes a `score_breakdown` list. Each item names the
heuristic, shows its `risk_delta`, and marks it as a `signal` or `flag`. Positive
values raise risk. Negative values lower risk. The final risk score is clamped to
the 0 to 100 range, then reviewability is calculated as `100 - risk`.

Each analyzed PR also includes `next_step`, a deterministic sentence that turns
the selected action and strongest flags into a concrete maintainer move.

Example:

```json
[
  { "label": "CI passed", "risk_delta": -8, "kind": "signal" },
  { "label": "code changed without tests", "risk_delta": 10, "kind": "flag" }
]
```

## Positive Signals

- CI passed
- PR is approved
- PR is mergeable
- review has been requested
- test plan language is present
- tests changed
- docs-only shape

## Risk Flags

- draft PR
- large or very large diff
- no visible checks
- CI failing or pending
- changes requested
- merge conflicts
- branch behind base
- merge blocked by repository rules
- merge checks unstable
- stale update window
- maintainer blocker language
- maintainer blocking label
- no test plan found for code changes
- code changed without tests
- generated or lockfile changes

## File evidence

`docs-only shape` requires a complete file list with every file classified as
documentation. A README alongside a lockfile, test, or unclassified file does
not receive the docs-only score adjustment or shorter review estimate.

When the supplied file list contains fewer entries than the reported changed
file count, Radar shows `incomplete file list`. It still uses visible evidence,
such as a test file that was returned, but does not infer that tests are absent.
The incomplete-list warning itself does not add risk points.

## Maintainer Blocker Language

Blocker detection intentionally looks for plain maintainer feedback patterns:

- not working
- broken
- failing or failed
- changes requested
- please fix
- regression
- cannot merge
- missing tests

This is not sentiment analysis. The goal is to catch comments that usually mean
"do not spend full review time until the author follows up."

## Maintainer Blocking Labels

Label detection looks for labels that usually mean the PR is not ready for
review:

- blocked
- do not merge
- changes requested
- needs tests
- waiting on author
- waiting for dependency
- blocked upstream

These labels route the PR to author follow-up even when CI is green.

## Merge Readiness

Hydrated GitHub scans also read merge readiness fields such as `mergeable`,
`mergeStateStatus`, and requested reviewers.

- Merge conflicts route the PR to author follow-up.
- A branch behind the base branch routes the PR to author follow-up.
- Repository rule blocking is shown as a risk flag, but it does not automatically
  blame the author.
- Requested reviewers are shown as positive queue context.

## Fixture Corpus

The test suite includes `tests/fixtures/blocker-prs.json` to keep blocker
detection concrete. Add new fixture cases when a real maintainer pattern should
be detected.
