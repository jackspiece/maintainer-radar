# Worked example: two PRs, one review session

This is a reproducible walkthrough using **fictional pull requests**, not a
customer case study or evidence of time saved. It shows exactly what the
current development version does with a small queue, including incomplete data.

## The decision

You have 15 minutes before your next meeting. One PR is a small parser fix;
another is a large plugin change with failing CI and unresolved feedback.
Which work fits, and what should wait?

The input is [sample-prs.json](../examples/sample-prs.json). The clock is fixed
at **2026-06-01 00:00 UTC** so that stale-age signals do not change tomorrow.

| Input | #42: parser cache fix | #43: plugin system |
| --- | --- | --- |
| Diff size | 60 changed lines, 3 declared files | 2,320 changed lines, 40 declared files |
| CI | Two passing checks | One failing check |
| Description | Explicit test plan | No test plan |
| Review and merge state | Review required, mergeable | Changes requested, merge conflict |
| Available file list | 2 of 3 files, including a test | 1 of 40 files |

Both file lists are incomplete. Radar can report the test file it sees on #42,
but cannot claim that #43 changed code without tests when 39 files are missing.
The report exposes this uncertainty as `incomplete file list`.

## Reproduce it without an account or network

From a checkout of this version, run:

```bash
PYTHONPATH=src python -m maintainer_radar from-json examples/sample-prs.json \
  --now 2026-06-01T00:00:00Z --review-plan-minutes 15

PYTHONPATH=src python -m maintainer_radar from-json examples/sample-prs.json \
  --now 2026-06-01T00:00:00Z --review-plan-minutes 30
```

These commands use the default scoring configuration. If you have created a
local `.maintainer-radar.json`, use `python scripts/generate_examples.py`
to reproduce the committed examples independently of that local config.

The [15-minute plan](../examples/output/sample-review-plan-15.md) selects #42,
estimates 12 minutes of active review, and leaves 3 minutes. #43's estimated
5-minute author follow-up is deferred by the budget.

The [30-minute plan](../examples/output/sample-review-plan-30.md) includes both:
12 minutes to review #42, then 5 minutes to prepare an author follow-up for #43.
It leaves 13 minutes for interruptions or a longer-than-expected review.
The 5-minute estimate covers preparing the follow-up, **not fixing the PR**.

The queue-level recommendation calls out a blocker sweep, while the planner
currently orders review-ready work first. Treat the ordering as a starting
point: a maintainer may reasonably choose to unblock #43 before reviewing #42.

## Inspect the evidence, then decide

Open the [full Markdown report](../examples/output/sample-report.md) or
[machine-readable JSON](../examples/output/sample-report.json). The current
heuristics route #42 to `review now` and #43 to `ask for CI fix`.

The generated draft for #43 asks about CI, the test plan, unresolved feedback,
merge conflicts, scope, and its stale status. It is editable text in the report;
Radar does not send it. A maintainer still checks which requests are accurate
and relevant before posting anything.

A score of 100 does not prove #42 is correct or safe to merge, and a score of
0 does not measure #43's contributor or code quality. These are routing
heuristics from limited metadata. Review estimates have not been calibrated
against measured maintainer time in this example.

## Try a different queue

The [interactive browser demo](https://jackspiece.github.io/maintainer-radar/)
starts with a separate five-PR fictional queue. Its 15/30-minute results will
therefore differ from this two-PR CLI fixture. You can also preview the five
most recently updated PRs in a public repository; see [demo limits](browser-preview.md).

For a real evaluation, record the repository, scan time, tool version, and
config; compare each suggested action with a maintainer's judgment. Report
incorrect routing and missing evidence, and measure actual review time before
claiming a productivity improvement. The
[maintainer feedback form](https://github.com/JackSpiece/maintainer-radar/issues/new?template=maintainer-feedback.yml)
provides a place to share that feedback. Do not include private PR data in a
public issue.
