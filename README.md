# Maintainer Radar

[![CI](https://github.com/JackSpiece/maintainer-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/JackSpiece/maintainer-radar/actions/workflows/ci.yml)

GitHub Action and local CLI for read-only pull request triage reports.

Maintainer Radar helps you choose where to spend your next review session.
It reads PR metadata, identifies likely blockers, and builds a plan around the
time you have. You still review the code and decide what to do.

[**Try the interactive demo**](https://jackspiece.github.io/maintainer-radar/)
with a working example queue, or scan five recent PRs from a public repository.
No installation or sign-in is needed for the demo.

| What is in the queue | What Radar suggests |
| --- | --- |
| A small change with passing checks and tests | Start a review |
| A change with failing CI | Ask for the check failure to be addressed |
| A draft or running checks | Leave it waiting |
| More work than fits your session | Defer some PRs and keep a shorter plan |

These are heuristics, not judgments about a contributor or the quality of their
code. Every suggestion has a visible explanation. Radar does not post, label,
approve, reject, or merge anything.

## Quick Start

To get a report in GitHub, save this as `.github/workflows/maintainer-radar.yml`,
commit it to your default branch, then run **Maintainer Radar** from the Actions
tab. The report appears in the run summary. This uses the published `v0.20.0`:

```yaml
name: Maintainer Radar
on:
  workflow_dispatch:
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
      - uses: JackSpiece/maintainer-radar@v0.20.0
        env:
          GH_TOKEN: ${{ github.token }}
        with:
          hydrate: "true"
          review-plan-minutes: "30"
```

For a local run, install the published source tag from GitHub:

```bash
python -m pip install "git+https://github.com/JackSpiece/maintainer-radar.git@v0.20.0"
gh auth login
maintainer-radar recommend https://github.com/owner/repo/pulls
```

Requires the [GitHub CLI](https://cli.github.com/) for authenticated live scans. Run `gh auth login` once.

To scaffold a config and scheduled workflow:

```bash
maintainer-radar init-repo --profile balanced
```

For stricter queue thresholds:

```bash
maintainer-radar init-config --profile strict --path .maintainer-radar.json
```

## What It Does

It reads pull request metadata through the GitHub CLI, the GitHub Action token, or offline JSON, then reports:

- PRs that appear ready for review
- CI failures, merge conflicts, and author follow-up
- unresolved maintainer feedback
- transparent reviewability and risk signals
- a time-boxed review plan for the next session
- editable draft follow-ups that a maintainer can review before posting

Reports are available as Markdown, JSON, CSV, and standalone HTML.

## Plan a review session

Use `recommend` for a short queue brief and suggested next command. To make a
plan for a specific amount of time:

```bash
maintainer-radar repo owner/repo --hydrate --sort action --review-plan-minutes 30
```

The browser is a small public preview. Use the CLI with your authenticated
`gh` session for a larger queue, private repositories you can access, or fuller
review context. Estimates depend on PR metadata; they cannot know how familiar
you are with the code.

## Common Commands

```bash
# Queue brief for a repository
maintainer-radar repo owner/repo

# Deeper scan with pull request details
maintainer-radar repo owner/repo --hydrate --sort action

# Single pull request breakdown
maintainer-radar pr owner/repo 123

# Offline analysis
maintainer-radar from-json queue.json

# Short review-ready list
maintainer-radar repo owner/repo --action review-now --min-score 80 --top 10
```

Run `maintainer-radar --help` for the complete reference.

## GitHub Action Outputs

The action exposes outputs for notifications, dashboards, and handoffs, including:

`review-now`, `ci-blocked`, `merge-conflicts`, `branch-behind`, `maintainer-blocked`, `attention-level`, `workflow-mode`, `workflow-recommendation`, and `next-session-brief`.

See [GitHub Action usage](docs/github-action.md) and [attention workflows](docs/attention-workflows.md).

## Documentation

- [Two minute quickstart](docs/quickstart.md)
- [Adoption guide](docs/adoption.md)
- [GitHub Action](docs/github-action.md)
- [Review plans](docs/review-plan.md)
- [Scoring heuristics](docs/heuristics.md)
- [Configuration](docs/configuration.md)
- [Privacy and permissions](docs/privacy-permissions.md)
- [Project positioning](docs/positioning.md)
- [GitLab JSON](docs/gitlab-json.md)
- [Forgejo and Gitea JSON](docs/forgejo-gitea-json.md)

## Contributing

Issues and focused pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
