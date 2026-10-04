# Examples

This directory contains sample inputs and copy-paste workflow examples.

## Offline Data

- `sample-prs.json`: fictional two-PR GitHub-shaped queue for trying `from-json`
- `maintainer-radar-config.json`: sample project-specific threshold config

Generate a fresh config profile with:

```bash
maintainer-radar init-config --profile strict --path .maintainer-radar.json
```

Generate both the config and scheduled workflow with:

```bash
maintainer-radar init-repo --profile balanced
```

## GitHub Actions

- `github-actions/daily-markdown-report.yml`: scheduled Markdown artifact
- `github-actions/daily-html-report.yml`: scheduled HTML artifact
- `github-actions/review-ready-report.yml`: focused scheduled report for high-score PRs

Copy one workflow into `.github/workflows/` in a repository that uses GitHub pull
requests, then run it manually from the Actions tab or wait for the schedule.
The examples use the reusable `JackSpiece/maintainer-radar` GitHub Action and
upload the generated report path exposed by the action. The review-ready example
uses the Action filters to keep only `review-now` PRs with a score of at least
80.

## Generated Output

- `output/sample-report.md`
- `output/sample-report.json`
- `output/sample-report.csv`
- `output/sample-report.html`
- `output/sample-review-plan-15.md`
- `output/sample-review-plan-30.md`

These files show the same fictional sample queue in all four output formats,
plus review plans for 15 and 30 minutes. They are generated with default
configuration and a fixed report time of `2026-06-01T00:00:00Z`:

```bash
python scripts/generate_examples.py
python scripts/generate_examples.py --check
```

The generator ignores a local `.maintainer-radar.json` so outputs are stable.
Tests fail if a committed example no longer matches the current CLI.
Read the [worked example](../docs/worked-example.md) for the inputs, expected
results, incomplete-file caveats, and what the estimates do not establish.

## Offline snapshot comparison

The unreleased `compare` command uses the fictional analyzed queue snapshots
`snapshots/before.json` and `snapshots/after.json`. They cover a changed CI/action
observation, one newly observed PR, one no longer observed PR, and one unchanged
PR. These are saved analyses, unlike the raw fixture `sample-prs.json`.

```bash
PYTHONPATH=src python -m maintainer_radar compare \
  examples/snapshots/before.json examples/snapshots/after.json
```

`output/sample-comparison.md` and `output/sample-comparison.json` are generated
from that pair by the same examples script. See the [comparison guide](../docs/snapshot-comparison.md)
for accepted inputs and the limits on conclusions from missing PRs or changed scores.
