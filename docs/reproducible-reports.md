# Reproducible Reports

Maintainer Radar uses the current time when calculating stale PR signals. Use
`--now` when a report needs stable output for examples, tests, or scheduled
comparisons.

## Usage

```bash
maintainer-radar from-json examples/sample-prs.json --now 2026-06-01T00:00:00Z
maintainer-radar repo owner/repo --hydrate --now 2026-06-01T00:00:00Z
```

The value must be an ISO date or datetime. Dates without a timezone are treated
as UTC.

## Sample Outputs

The files in [../examples/output](../examples/output) are generated from
`examples/sample-prs.json` with:

```bash
PYTHONPATH=src python -m maintainer_radar from-json examples/sample-prs.json \
  --now 2026-06-01T00:00:00Z
```

To refresh all four report formats and the 15/30-minute plans with default
configuration, run `python scripts/generate_examples.py`. Use `--check` to
verify them without writing. The generator isolates the command from any local
`.maintainer-radar.json` so a personal config cannot silently alter the fixtures.
See the [worked example](worked-example.md) for a step-by-step interpretation.
