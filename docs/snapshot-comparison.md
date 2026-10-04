# Compare offline queue snapshots

`compare` answers: **what changed between two saved Radar observations?**
It reads full analyzed queue JSON reports, matches PRs by their exact full URL,
and prints a deterministic Markdown or JSON comparison. It does not contact a
forge, re-score a PR, post a comment, or modify the input files.

This command is part of the unreleased source checkout. The published v0.20.0
installation shown in the main quickstart does not include it yet.

## Try the fictional example

From the repository root, without installing anything:

```bash
PYTHONPATH=src python -m maintainer_radar compare \
  examples/snapshots/before.json examples/snapshots/after.json

PYTHONPATH=src python -m maintainer_radar compare \
  examples/snapshots/before.json examples/snapshots/after.json --format json
```

The paired fixtures contain fictional saved analyses. They demonstrate all four
categories:

- **Newly observed:** PR #45 is present only in the second snapshot.
- **No longer observed:** PR #43 is present only in the first snapshot. This does
  not tell us whether it was closed, merged, filtered out, or omitted by a limit.
- **Changed:** PR #42 moves from `ask for CI fix` to `review now`, with the saved
  failing-check count moving from 1 to 0 and risk from 30 to 0. The report shows
  both values and the changed flags and signals; it does not assert why they
  changed.
- **Unchanged:** PR #44 has the same values in all compared fields.

Read the generated [Markdown comparison](../examples/output/sample-comparison.md)
or [JSON comparison](../examples/output/sample-comparison.json). Regenerate or
verify them with `python scripts/generate_examples.py` and `--check`.

## Capture your own snapshots

With a source-checkout installation, save ordinary full-queue reports:

```bash
maintainer-radar repo owner/repo --hydrate --format json > before.json
# Later, repeat the same capture options and configuration:
maintainer-radar repo owner/repo --hydrate --format json > after.json
maintainer-radar compare before.json after.json
```

Offline GitHub, GitLab, Forgejo, and Gitea exports can first be analyzed with
`from-json` and the appropriate `--source`, then saved with `--format json`.
Pass the analyzed reports to `compare`, not the raw forge exports.

Keep repository coverage, filters, limits, hydration, configuration and Radar
version equivalent where possible. Record those capture details yourself:
current queue JSON does not embed them, so the comparator cannot verify them.
A warning about this limitation is always included, even for identical inputs.

The command only writes stdout. It has no output-path or overwrite option.
If you redirect a report, choose a **different destination from both inputs**:
a shell can truncate an input before the command starts. Validation failures
return exit code 2 and emit a diagnostic on stderr with no partial report.

## Input contract and identity

Each file must be a UTF-8 JSON array of full analyzed queue records. Empty
arrays are valid. Summary/recommendation/review-plan objects, raw forge exports,
stdin, directories, and malformed or ambiguous records are rejected.

Required fields are `number`, `url`, `title`, `action`, `risk`, `reviewability`,
`next_step`, `checks`, `flags`, and `signals`:

- `number` is a positive integer; scores are integers from 0 to 100. Booleans
  do not count as integers. Non-finite JSON numbers and duplicate JSON object
  keys are rejected.
- `checks` contains exactly the non-negative integer counts `passed`, `failed`,
  `pending`, `skipped`, and `total`; their sum must agree with `total`.
- `title`, `action`, and `next_step` are strings; `action` cannot be empty.
  `flags` and `signals` are arrays of strings.
- `url` is an absolute HTTP(S) URL with an owner/group, repository, and a
  `pull/<number>`, `pulls/<number>`, or `-/merge_requests/<number>` path. Its
  number must match the record. Credentials, control characters, whitespace,
  and backslashes are rejected.
- Each exact URL may appear only once per snapshot. PR numbers alone are never
  identities: repositories and forge hosts remain distinct. URL casing,
  query strings and fragments are preserved, with no speculative alias
  matching. Different URL strings are separate observations.
- Each input is limited to 16 MiB and 10,000 records. Oversized files and
  excessive JSON nesting fail cleanly before any report is printed.

Both snapshots must satisfy this same contract. There is no claim that merely
validating their shape proves equivalent capture settings or complete coverage.
The comparison JSON has `schema_version: 1`; that version describes this report
format and is not a version or provenance claim about the input snapshots.

## Compared fields and JSON output

Comparison covers `title`, `action`, `risk`, `reviewability`, `next_step`,
`checks`, `flags`, and `signals`. Other metadata is ignored, including author,
file summaries, staleness, and score-breakdown entries. “Unchanged” means only
unchanged in the listed fields. Radar does not infer a code-level cause from a
changed score or action. To inspect other details, retain the original reports.

Input record ordering, JSON object-key ordering, and flag/signal ordering do not
create changes. Flags/signals are treated as sets (duplicate strings collapse).
Records are ordered by exact URL; changed fields follow the documented field
order. No generation timestamp or input path is added, so equivalent inputs
produce byte-identical output anywhere.

JSON includes `summary`, `limitations`, `comparison_fields`, and four arrays:
`newly_observed`, `no_longer_observed`, `changed`, and `unchanged`. Added/missing/
unchanged entries contain the compared observation. Each changed entry includes
its URL and number, full compared `before` and `after` observations, and a
`changes` array of `{field, before, after}` values. Titles and strings remain
unaltered in JSON; the human report escapes Markdown markup and link targets.

This feature does not add alerting, automatic snapshots, persistence, GitHub
Action inputs, a browser-demo panel, or a merge/closure detector.
