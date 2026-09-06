# Changelog

## Unreleased (0.21.0)

- Avoid missing-test and docs-only conclusions from incomplete file lists.
  Mixed documentation changes no longer receive the docs-only score adjustment
  or shorter review estimate. Keep the Python and browser rules aligned.
- Fixed generated workflows to use a published Action tag and check out the
  repository when a config file is requested. Missing explicit configs and
  non-integer thresholds now fail clearly.
- Count external CI commit statuses alongside check runs; incomplete checks
  no longer disappear from scoring. Added shared Python/browser regressions.
- Reject malformed JSON list entries without a traceback, remove numeric
  grades from author-facing draft replies, and make type checking required.
- Simplified the browser demo to one PR queue and a copyable review plan, with
  an interactive offline example, expandable evidence, and a responsive layout.
  Removed duplicate summary panels, badge/workflow generators, and extra export
  controls from the demo; full reporting remains in the CLI and GitHub Action.
- Fixed sample controls, selected-budget planning, stale results after scan
  failures, clipboard fallback, and incomplete PR/CI fetch handling.
- Aligned browser test-plan evidence and file categories with the Python defaults.
- Clarified the demo's limits and documented batching changes into releases
  instead of incrementing the version for every small edit.

- Fixed `--stale-days` filtering to honor `--now`, so reproducible runs filter
  and score with the same clock.
- Tightened test-plan detection: evidence must be an explicit section, label,
  or testing statement. Casual mentions of "tests" or "ci" no longer count.
- Blocker detection now ignores the PR author's own comments and reviews, and
  no longer scans review states as text, which double-counted
  `CHANGES_REQUESTED` on top of the review-decision penalty.
- File categories are now mutually exclusive, so test-only PRs are no longer
  flagged as "code changed without tests".
- GitLab and Forgejo normalizers only emit a `body` key when the export
  actually carried one, matching shallow GitHub scan scoring.
- `--top` now consistently requires 1 or greater in the CLI, matching
  generated workflow validation.
- The composite GitHub Action now scans the queue exactly once and renders the
  report, summary outputs, review-plan outputs, and step summary locally from
  that JSON, instead of scanning up to three times.
- Hydrated scans fetch PR details concurrently, and `gh` subprocess calls time
  out after 120 seconds instead of hanging forever.
- Author scans pass through `commentsCount` instead of fabricating placeholder
  comment objects.
- Added `--action-ref` to `init-action` and `init-repo` for SHA-pinned
  workflows, and generated YAML now escapes backslashes in quoted values.
- CI now runs `ruff` (enforced) and `mypy` (advisory), and the action smoke
  test writes `summary-json` through an environment variable instead of
  expanding an expression inside a heredoc.
- Single-sourced the package version from `maintainer_radar.__version__`,
  moved to `setuptools>=77` for the SPDX license string, and shipped a
  `py.typed` marker.
- Added a PyPI release workflow (trusted publishing), Dependabot updates for
  Actions and pip, `CODEOWNERS`, a full Contributor Covenant 2.1 code of
  conduct, and an expanded contributing guide.
- Renamed the config integer validator to `_non_negative_int` to match its
  actual behavior.

## 0.20.0

- Added `maintainer-radar init-repo`, a one-command setup path that writes both
  `.maintainer-radar.json` and a read-only scheduled GitHub Actions workflow.
- `init-repo` references the generated config from the workflow, defaults to
  grouped action-sorted reports, and refuses partial setup when either target
  file already exists unless `--force` is passed.
- Updated the homepage, README, quickstart, adoption, configuration, and
  examples docs to make one-command setup the default path.

## 0.19.0

- Added `maintainer-radar init-config`, which prints or writes a
  `.maintainer-radar.json` scoring config without hand-writing JSON.
- Added `balanced`, `strict`, and `large-repo` config profiles. The command
  protects existing files unless `--force` is passed.
- Updated quickstart, adoption, configuration, examples, and README docs to show
  config bootstrapping before scheduled report setup.

## 0.18.0

- Added `maintainer-radar recommend owner/repo`, a short maintainer workflow
  recommendation that prints the queue headline, attention level, workflow mode,
  reason, next-session brief, and exact follow-up commands.
- `recommend` accepts pasted GitHub repository URLs and supports Markdown or
  JSON output. It hydrates PR details by default, with `--no-hydrate` available
  for faster shallow scans.
- README, quickstart, adoption, positioning, homepage, and examples now surface
  `recommend` as the first local answer before opening a full report.

## 0.17.1

- CLI repository commands now accept common GitHub repository URL shapes, such
  as `https://github.com/owner/repo` and
  `https://github.com/owner/repo/pulls`.
- `maintainer-radar pr` can now analyze a pasted GitHub pull request URL without
  requiring the PR number as a separate argument.
- README and maintainer workflow docs now show the paste-a-URL flow.

## 0.17.0

- Summary output now includes a default 60-minute next-session digest, with
  planned PR count, estimated active minutes, deferred PR count, quick unblock
  count, watch-only count, and a one-line `next_session_brief`.
- The reusable GitHub Action now exposes the same digest as
  `next-session-brief`, `next-session-prs`, `next-session-minutes`,
  `next-session-deferred`, `quick-unblocks`, and `watch-only` outputs.
- The browser preview, README preview image, docs, generated samples, and social
  preview now emphasize next-session planning as the project's core
  differentiator.

## 0.16.33

- Summary output now includes merge readiness counts for merge conflicts, branch
  behind base, repository merge gates, and PRs with requested reviewers.
- The reusable GitHub Action now exposes those counts as `merge-conflicts`,
  `branch-behind`, `merge-gated`, and `review-requested` outputs.
- Markdown, JSON, CSV, HTML, and review-plan summaries now surface the same
  merge readiness totals.

## 0.16.32

- Hydrated scans now include merge readiness signals from GitHub, including
  merge conflicts, branch-behind state, repository merge gates, mergeability,
  and requested reviewers.
- Merge conflicts and branch-behind states route to author follow-up, and draft
  follow-ups include targeted requests for those cases.
- Browser preview scoring now shows the same merge readiness signals when the
  public GitHub API exposes them.

## 0.16.31

- The public browser preview now shows a Draft Follow-ups panel under the review
  plan preview.
- Each visible draft has a Copy Draft button, so maintainers can copy one
  editable author ask without first copying the whole review plan.

## 0.16.30

- HTML review-plan artifacts now show Copy Draft buttons for generated draft
  follow-up comments.
- The HTML copy helper stays local to the static artifact and does not post,
  label, approve, or mutate pull requests.

## 0.16.29

- Review plans now include draft follow-up comments for PRs that need author
  action, CI fixes, smaller scope, or a ready-for-review update.
- JSON review-plan entries now include `draft_follow_up_comment` so dashboards
  and handoff tooling can surface the same read-only draft text.
- The browser preview's Copy Plan and Copy JSON actions now include the draft
  follow-up text too.

## 0.16.28

- HTML and JSON review-plan Action runs now add compact review-plan metrics to
  the GitHub Actions run summary.
- The compact plan summary includes budget, planned PRs, active time, remaining
  minutes, deferred PRs, and watch-only PRs.

## 0.16.27

- Added Copy JSON to the browser preview so scanned repositories can copy the
  current review plan as structured JSON.
- Browser review-plan JSON includes planned, deferred, and watch-only PR arrays
  for dashboards, scripts, and handoff tooling.

## 0.16.26

- Added structured JSON review-plan output for
  `--review-plan-minutes --format json`.
- Generated workflows and direct Action usage can now create
  `review-plan.json` artifacts for dashboards and automation.

## 0.16.25

- Generated review-plan workflows now default to `review-plan.md` or
  `review-plan.html` instead of generic `maintainer-radar` artifact paths.
- Direct Action usage with `review-plan-minutes` now gets the same review-plan
  default output paths when no `output` is set.

## 0.16.24

- Added HTML review-plan output for `--review-plan-minutes --format html`.
- Allowed generated workflows to combine `--report-format html` with
  `--review-plan-minutes` for browser-friendly plan artifacts.

## 0.16.23

- Added shareable browser demo links that preserve the current review-plan
  minutes with `?plan=30`.
- Copy Link, Copy Badge, copied Markdown, and the address bar now keep the
  current plan minutes after a scan.

## 0.16.22

- Added structured review-plan outputs to the reusable GitHub Action:
  `planned-prs`, `planned-minutes`, `remaining-minutes`, `deferred-prs`, and
  `watch-only-prs`.
- Added a reusable review-plan summary helper for plan output metrics.

## 0.16.21

- Updated browser Copy Workflow to generate a scheduled review-plan workflow
  using the current plan minutes value.

## 0.16.20

- Added a visible review-plan preview to the public browser demo, showing planned
  PRs, estimated active time, and remaining time before copying Markdown.

## 0.16.19

- Added Copy Plan to the public browser preview so visitors can copy a
  time-boxed review plan without installing the CLI.
- Added a plan-minutes control to the browser preview and documented the
  no-install review-plan flow.

## 0.16.18

- Added `--review-plan-minutes` for Markdown review-session plans that turn a
  PR queue into a time-boxed maintainer plan.
- Added `review-plan-minutes` support to generated workflows and the reusable
  GitHub Action.
- Added review plan docs and a copy-paste review-plan workflow example.

## 0.16.17

- Added a Maintainer blocked metric to the public browser preview and copied
  Markdown briefs.
- Documented the browser metric so the public demo matches the CLI and Action
  summary output.

## 0.16.16

- Added `maintainer_blocked` to summary output and `maintainer-blocked` to the
  reusable GitHub Action outputs.
- Added Maintainer blocked to Markdown, HTML, JSON, CSV, and compact Action run
  summaries.

## 0.16.15

- Expanded label-aware blocker scoring for dependency and upstream blocked PR
  labels such as `blocked-upstream` and `waiting-for-dependency`.

## 0.16.14

- Added label-aware blocker scoring for labels like blocked, do not merge,
  needs tests, changes requested, and waiting on author.
- Mirrored the label-aware blocker rule in the browser preview.

## 0.16.13

- Added a Copy CLI button to the public browser preview for copying the local
  command matching the current repository and grouped view.

## 0.16.12

- Added a Copy Badge button to the public browser preview for sharing a static
  README badge linked to the current scan.
- Documented the badge flow in the browser preview guide.

## 0.16.11

- Added shareable grouped browser preview links with `?group=action`.
- Made Copy Link and the address bar preserve the current Group by action view.

## 0.16.10

- Added a Group by action toggle to the public browser preview and made copied Markdown respect the grouped view.
- Updated the browser Copy Workflow output to include action-grouped reports.

## 0.16.9

- Added optional `--group-by action` support for Markdown and HTML reports so queues can be split into action sections.
- Added `group-by` support to the reusable GitHub Action, generated workflows, review-ready examples, docs, and CI smoke coverage.

## 0.16.8

- Added structured summary outputs to the reusable GitHub Action, including total, review-now, author-follow-up, CI, stale, and average-score counts.
- Updated Action docs and CI smoke coverage so workflows can consume report metrics without parsing artifacts.

## 0.16.7

- Added focused report filters to the reusable GitHub Action: label, author, stale-days, updated-since, action, min-score, and max-risk.
- Added matching `init-action` filter flags, focused Action docs, and a review-ready scheduled workflow example.

## 0.16.6

- Added deterministic `next_step` guidance to PR analyses so reports translate each action into a concrete maintainer move.
- Surfaced next steps in Markdown, HTML, CSV, JSON, detail output, generated samples, and the browser preview.

## 0.16.5

- Added a `config` input to the reusable GitHub Action so scheduled reports can use project-specific scoring thresholds.
- Added `maintainer-radar init-action --config` support and documented the Action config path in README and configuration docs.

## 0.16.4

- Updated README, package, Pages, and social-preview source descriptions to lead with the GitHub Action and read-only PR triage positioning.
- Added tests to keep public metadata aligned with the Action-first positioning.

## 0.16.3

- Added Copy Workflow to the browser demo so visitors can copy a ready scheduled GitHub Action workflow from the public preview.
- Added browser demo smoke coverage for workflow rendering and documented the new Copy Workflow button.

## 0.16.2

- Reworked the README quick start to lead with the reusable GitHub Action before local CLI install.
- Added a README ordering test so the Action adoption path stays prominent.

## 0.16.1

- Added dedicated GitHub Action usage documentation with copy-paste workflow, inputs, outputs, permissions, and troubleshooting.
- Linked GitHub Action docs from README, homepage navigation, and the GitHub Actions guide.
- Added tests that keep the action documentation discoverable and aligned with the action contract.

## 0.16.0

- Added a reusable composite GitHub Action via `action.yml`.
- Updated generated workflows and bundled examples to use `JackSpiece/maintainer-radar@v0.16.0`.
- Added action metadata tests for inputs, outputs, run-summary behavior, and read-only guardrails.
- Added CI smoke coverage that runs the action locally with `uses: ./`.

## 0.15.1

- Updated generated GitHub Actions workflows to publish Markdown reports or summaries to the Actions run summary by default.
- Added `--no-step-summary` for artifact-only workflows.
- Added step-summary coverage for Markdown and non-Markdown workflow artifacts.

## 0.15.0

- Added `init-action` to print or write a read-only GitHub Actions workflow.
- Added workflow rendering tests and CLI overwrite protection.
- Documented one-command workflow bootstrap in the README and GitHub Actions guide.

## 0.14.2

- Added Copy Markdown to the browser demo for paste-ready queue briefs.
- Added browser-demo Markdown rendering tests and documentation.

## 0.14.1

- Added shareable browser demo links with `?repo=owner/repo`.
- Added a Copy Link flow after scanning a public repository in the browser demo.

## 0.14.0

- Added a no-install browser preview for public GitHub repositories.
- Added public check-run signals to the browser preview for CI passed, failing, pending, or absent states.
- Added GitHub Pages demo metadata, social preview image, browser-preview documentation, and feedback links.
- Added CI coverage for browser demo assets, Pages metadata, and package version alignment.

## 0.13.0

- Added score breakdowns that show which heuristics changed each PR's risk score.
- Added risk impact output to Markdown, HTML, CSV, JSON, and detailed PR briefs.

## 0.12.0

- Added `--now` for reproducible stale calculations.
- Added generated sample output artifacts for Markdown, JSON, CSV, and HTML.

## 0.11.1

- Expanded maintainer workflow documentation with current CLI examples.

## 0.11.0

- Added stdin support for offline JSON with `from-json -`.
- Added stdin pipeline documentation.

## 0.10.0

- Added `--top` for focused queue reports after filtering and sorting.
- Added focused report documentation.

## 0.9.1

- Added copy-paste GitHub Actions workflow examples for Markdown and HTML artifacts.
- Added examples documentation.

## 0.9.0

- Added standalone static HTML report output.
- Added HTML output documentation.

## 0.8.0

- Added opt-in hydrated live GitHub scans with `--hydrate`.
- Added documentation for fast versus hydrated scan tradeoffs.

## 0.7.0

- Added queue sorting with `--sort` for action, score, risk, stale days, and PR number.
- Added queue sorting documentation.

## 0.6.0

- Added CSV output for queue reports and summary reports.
- Added CSV documentation for spreadsheet triage workflows.

## 0.5.1

- Added a README quickstart screenshot sequence using sample data.

## 0.5.0

- Added Forgejo and Gitea pull request JSON normalization.
- Added Forgejo/Gitea fixture coverage and documentation.

## 0.4.1

- Added `.maintainer-radar.json` configuration support for thresholds and path hints.

## 0.4.0

- Added GitLab merge request JSON normalization.
- Added GitLab fixture coverage and documentation.

## 0.3.0

- Added `pr --comment-template` for draft maintainer follow-up comments.

## 0.2.3

- Added JSON output documentation for scripts and dashboards.

## 0.2.2

- Added maintainer blocker fixture corpus.
- Added heuristic documentation.

## 0.2.1

- Added output filters for recommended action, minimum reviewability score, and maximum risk.

## 0.2.0

- Added `--summary-only` for queue commands.
- Added a terminal preview image to the README.
- Added GitHub Actions integration documentation.

## 0.1.3

- Added maintainer handoff and follow-up examples.

## 0.1.2

- Added label, author, stale-days, and updated-since filters for repo scans.

## 0.1.1

- Added a repo-level report summary.
- Updated GitHub Actions workflow to current official actions.

## 0.1.0

- Initial public release.
- Added deterministic PR scoring.
- Added Markdown and JSON output.
- Added GitHub CLI repository, PR, and author modes.
- Added offline JSON analysis mode.
- Added tests and CI.
