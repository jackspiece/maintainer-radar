# Browser Preview

[Open the demo](https://jackspiece.github.io/maintainer-radar/).

The demo starts with five fictional pull requests. The example queue works
without network access and uses the same analysis function as a live scan.
Change the time budget to see which tasks fit, or expand a PR to see the
signals behind its suggested next step.

## Try your repository

Enter `owner/repo` or paste a GitHub repository URL. The browser reads the
public GitHub API directly and analyzes the **5 most recently updated** open
pull requests. The source label distinguishes the example from live data.
This small preview does not represent the entire backlog.

Use **Load example queue** to return to the sample. You can also cancel a scan.
If a scan fails, its results stay hidden and you can retry; old results are
never presented under the new repository name.

A successful live scan updates the address bar. Copy that URL to share the
repository and selected review time:

```text
https://jackspiece.github.io/maintainer-radar/?repo=python/cpython&plan=30
```

## Use the plan

Choose 15, 30, or 60 minutes, or enter a whole number from 1 to 240. The plan
lists every selected task, estimated active time, and how many PRs are deferred
or waiting. If the first task alone exceeds your budget, that is stated next
to the estimate. These are rough estimates, not timing guarantees.

**Copy Plan** copies a Markdown brief with the current budget. If clipboard
access is unavailable, the text opens in a dialog where you can copy it
manually or download `review-plan.md`. Example exports are labeled fictional.

## Limits and data

- Each scan reads the PR list, details, changed files, public check runs, and
  commit statuses from external CI services.
- GitHub can rate-limit unauthenticated requests. Scans stop after 30 seconds.
- A PR with more than 100 changed files is skipped rather than scored from an
  incomplete file list. Use the CLI for larger changes.
- A failed PR fetch produces a partial report when other PRs loaded. The page
  identifies skipped PRs and missing or incomplete CI data.
- A score is a metadata heuristic, not a code-quality rating or approval.
  The browser does not read the full review discussion or private CI results.
- The demo does not ask for a GitHub token and cannot access private repos.
- It does not post comments, approve PRs, or write to repositories.
- It does not store your scanned queue or send it to a Maintainer Radar server.

For the full reporting options, use the CLI or GitHub Action:

```bash
maintainer-radar repo owner/repo --hydrate --sort action --review-plan-minutes 30
```

The CLI supports Markdown, JSON, CSV, HTML, grouped reports, configuration, and
draft follow-ups. See the [quickstart](quickstart.md) or
[GitHub Action guide](github-action.md).

If a suggestion seems wrong, [report it](https://github.com/JackSpiece/maintainer-radar/issues/new/choose)
with the public PR link, expected next step, and missing or misleading signal.
