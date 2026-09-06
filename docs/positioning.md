# Positioning

Maintainer Radar helps a maintainer decide where to spend the next review
session. It is useful when a queue has a mix of ready changes, failing checks,
drafts, and unresolved follow-ups.

> Where should a maintainer spend review attention first?

It reads available PR metadata and produces suggested next steps with visible
reasons. A time-boxed review plan makes the amount of suggested work explicit.
The maintainer still checks the code, discussion, and project context.

## The three entry points

- **Browser demo:** try a fictional queue or preview five recent public PRs.
  Choose a time budget, inspect the evidence, and copy one review plan.
- **CLI:** use an authenticated `gh` session or offline JSON for a larger queue,
  richer context, project configuration, and the full report formats.
- **GitHub Action:** create a report in the repository's existing workflow.

The `recommend` command turns a queue scan into one maintainer decision:
where to start and which command to run next. The browser stays smaller than
the CLI so someone can understand the result without learning every option.

## Boundaries

- It does not approve, reject, merge, label, or comment on pull requests.
- It does not judge the contributor or claim that a score measures code quality.
- It cannot know all the context or how long a review will take.
- It does not need a model key, bot account, or hosted database.

Keep changes focused on clearer decisions, trustworthy signals, and useful
reports. Extra dashboards, scoring summaries, or export buttons should earn
their place by solving a distinct maintainer problem.
