# Save capture settings with a snapshot

A changed score can reflect a different scoring threshold, Radar version,
filter, or hydration option. The unreleased source adds `--snapshot` to retain
these settings alongside a full JSON queue, so a later comparison can show
known differences rather than leaving you to reconstruct the command.

This is opt-in. Existing `--format json` arrays, summary JSON, review plans,
GitHub Action output, and browser-demo exports do not change. The published
v0.20.0 does not include this option or `compare` yet.

## Capture and compare

```bash
maintainer-radar repo owner/repo --hydrate --format json --snapshot > before.json
# Later, repeat the capture with the same intended options:
maintainer-radar repo owner/repo --hydrate --format json --snapshot > after.json
maintainer-radar compare before.json after.json
maintainer-radar compare before.json after.json --format json
```

`author` and `from-json` also support `--snapshot`. It requires `--format json`
and rejects `--summary-only`, `--detail`, `--review-plan-minutes`, and `--group-by`.
Invalid combinations or invalid recorded settings fail before a GitHub request
or input-file read. The capture still uses normal filtering, sorting, and
`--top`. The JSON envelope's `items` contains the same full analyzed records as
ordinary queue JSON, in the selected order.

Captures need repository-qualified PR URLs and all required comparison fields.
Incomplete raw exports that ordinary reports tolerate may therefore fail
snapshot validation. Like comparison inputs, captures are limited to 10,000
emitted records and 16 MiB of JSON. Failures return code 2, with a diagnostic on
stderr and no partial report on stdout. Commands do not write output files;
choose a redirection destination different from every input/config file.

## Reproduce a config-only change

Run these commands from the source root:

```bash
PYTHONPATH=src python -m maintainer_radar from-json examples/sample-prs.json \
  --now 2026-06-01T00:00:00Z --format json --snapshot > default-snapshot.json
PYTHONPATH=src python -m maintainer_radar from-json examples/sample-prs.json \
  --now 2026-06-01T00:00:00Z --format json --snapshot \
  --config examples/snapshots/lower-threshold-config.json > lower-threshold-snapshot.json
PYTHONPATH=src python -m maintainer_radar compare \
  default-snapshot.json lower-threshold-snapshot.json
```

The fixture config lowers `large_diff_lines` from 500 to 50. The raw PRs and
analysis time stay fixed. The report highlights that setting difference and
the saved score/flag changes for #42. In this controlled example the PR code
has not changed. The comparator itself does not infer a cause in ordinary use.
If your source directory has a `.maintainer-radar.json`, it affects the first
command; the example generator uses a clean directory instead.

Read the generated [comparison](../examples/output/sample-provenance-comparison.md),
[comparison JSON](../examples/output/sample-provenance-comparison.json),
[default snapshot](../examples/output/sample-snapshot.json), and
[lower-threshold snapshot](../examples/output/sample-snapshot-lower-threshold.json).
`python scripts/generate_examples.py --check` recreates all four offline and
checks their exact bytes. `--now` makes the capture reproducible; without it,
one current UTC clock is selected for filtering, scoring, and provenance.

## What comparison reports

- `recorded-settings-match`: version, config, and capture settings are equal.
  This does **not** establish equivalent or complete repository coverage.
- `recorded-settings-differ`: one or more recorded settings differ. Markdown
  and JSON list each dotted field name and its before/after value. Saved PR
  observations are still compared, with a caution about interpreting changes.
- `unknown`: one input is a legacy JSON array without provenance. The known
  side's metadata is preserved; differences cannot be determined.

Two legacy arrays retain the existing report and provenance-limitation warning,
without a new `provenance` key. Comparisons never re-score observations, load
local config, contact GitHub, or modify snapshots. A metadata-only difference
can appear even when no compared PR fields changed.

Analysis time and observed/output counts are displayed as context, excluded
from settings differences. Different times are normal between captures, but
can affect staleness and filters. Equal counts do not establish equal coverage.
The package version is recorded, not an exact source-commit or build identity;
two unreleased builds may share a version. All metadata is self-reported and
can be edited. It is not an integrity certificate.

## Envelope schema version 1

The top-level object contains exactly:

- `kind`: `maintainer-radar.snapshot`
- `schema_version`: integer `1` (separate from comparison report schema 1)
- `items`: full analyzed queue records, with the existing [comparison contract](snapshot-comparison.md#input-contract-and-identity)
- `provenance`: the object described below

`provenance` contains exactly:

- `radar_version`: the package version used by the capture
- `analysis_time`: an ISO timestamp with a timezone, emitted in UTC; when
  `--now` is used this is the requested analysis clock, not the wall-clock time
  at which the raw export was fetched
- `config`: all nine effective scoring config keys, including defaults and
  normalized custom hints; config filenames/paths are omitted
- `capture`: command options described below
- `counts`: `observed` is the number returned by the forge command or normalized
  offline input before local filtering; `emitted` is `items` length after
  filtering and `--top`. `observed` must be at least `emitted`

`capture` always contains these keys (unavailable options are JSON `null`):

- `command`: `repo`, `author`, or `from-json`
- `source`: `github`, `gitlab`, `forgejo`, or `gitea`
- `repository`: normalized `owner/repo` for a live repository capture
- `author`: the requested username for an `author` capture, distinct from the
  repository command's author filter
- `state`, `limit`, `hydrate`: the live query state/limit and requested hydration
- `filters`: `label`, `author`, `stale_days`, `updated_since`, `action`,
  `min_score`, `max_risk`
- `sort`, `top`: output ordering and truncation options

For offline exports, `repository`, `author`, `state`, `limit`, and `hydrate`
are null. Radar cannot establish the export's original scope or hydration;
URLs in records still identify the PRs. A live `limit` is a requested scan cap,
not proof the queue is complete; a `hydrate` value records the requested option,
not proof every upstream field exists. Exact option strings and hint-list order
are preserved, so semantically equivalent spellings may still be shown as a
settings difference. No input/config path, raw command line, environment
variable, credential, or automatic source-file fingerprint is recorded.

## Compatibility and privacy

The loader rejects unsupported envelope kinds/versions, missing or extra schema
keys, unknown config keys, wrong types, invalid counts, duplicate JSON keys,
non-finite numbers, invalid Unicode, and oversized inputs rather than silently
discarding metadata. It also validates every PR observation. The schema knows
the current config keys; a future shape change needs an explicit compatibility
update. A different Radar version string with the same supported schema is
accepted and highlighted as a setting difference.

Older Radar versions that only understand arrays cannot consume envelopes.
Keep using ordinary `--format json` for those tools, or explicitly extract the
`items` array with a JSON tool, accepting that this discards provenance. Feed
analyzed snapshots to `compare`; `from-json` is for raw forge exports, not for
re-scoring snapshot envelopes. Comparison JSON schema 1 adds the optional
`provenance` object only when metadata exists; consumers should tolerate that
additive field or keep using legacy arrays.

Snapshots contain the same private PR titles, URLs, and other analyzed fields
as ordinary reports, plus repository/author scope, label filters, and project
config hints that may themselves be private. Review the contents before
sharing. Snapshot capture adds no upload, background service, scheduling,
automatic storage, posting, or GitHub Action input.
