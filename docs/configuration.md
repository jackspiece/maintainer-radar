# Configuration

Maintainer Radar can read project-specific thresholds from
`.maintainer-radar.json` in the current directory.

Use `--config path/to/config.json` to load a different file. An explicitly
named file must exist; a missing file fails instead of silently using defaults.
Numeric thresholds must be non-negative integers.

Generate a starter config instead of writing JSON by hand:

```bash
maintainer-radar init-config --profile balanced --path .maintainer-radar.json
maintainer-radar init-config --profile strict --path .maintainer-radar.json
maintainer-radar init-config --profile large-repo --path .maintainer-radar.json
```

`init-config` refuses to overwrite an existing file unless you pass `--force`.

If you also want the scheduled GitHub Actions workflow, use `init-repo`:

```bash
maintainer-radar init-repo --profile balanced
```

This writes both `.maintainer-radar.json` and
`.github/workflows/maintainer-radar.yml`.

## Profiles

| Profile | Best For | Behavior |
| --- | --- | --- |
| `balanced` | Most repositories | Uses the default thresholds |
| `strict` | Small teams or high-signal queues | Flags large diffs and quiet PRs earlier |
| `large-repo` | High-volume repositories | Allows larger PRs and longer quiet windows |

## Example

```json
{
  "large_diff_lines": 500,
  "very_large_diff_lines": 1500,
  "large_file_count": 10,
  "very_large_file_count": 25,
  "quiet_days": 7,
  "stale_days": 14,
  "test_hints": ["specs/"],
  "doc_hints": ["guides/"],
  "generated_hints": ["snapshots/"]
}
```

## Fields

| Field | Default | Meaning |
| --- | ---: | --- |
| `large_diff_lines` | 500 | Diff line count that adds a `large diff` flag |
| `very_large_diff_lines` | 1500 | Diff line count that adds a `very large diff` flag |
| `large_file_count` | 10 | Changed file count that adds a `large diff` flag |
| `very_large_file_count` | 25 | Changed file count that adds a `very large diff` flag |
| `quiet_days` | 7 | Days without updates before a `quiet N days` flag |
| `stale_days` | 14 | Days without updates before a `stale N days` flag |
| `test_hints` | `[]` | Extra lowercase path fragments that count as tests |
| `doc_hints` | `[]` | Extra lowercase path fragments that count as docs |
| `generated_hints` | `[]` | Extra lowercase path fragments that count as generated files |

Unknown keys fail fast so configuration mistakes do not silently change scoring.

## Usage

```bash
maintainer-radar repo owner/repo --config .maintainer-radar.json
maintainer-radar from-json queue.json --config strict-config.json
```

For scheduled GitHub Action reports, pass the same file path with the `config`
input. Check out the repository before running the Action so the file exists
on the runner. Generated workflows include this step when `--config` is set:

{% raw %}
```yaml
steps:
  - uses: actions/checkout@v7
  - uses: actions/setup-python@v7
    with:
      python-version: "3.12"
  - uses: JackSpiece/maintainer-radar@v0.20.0
    env:
      GH_TOKEN: ${{ github.token }}
    with:
      repository: ${{ github.repository }}
      config: .maintainer-radar.json
```
{% endraw %}

Generate both files locally:

```bash
maintainer-radar init-repo --profile balanced
```

Or keep config and workflow generation separate:

```bash
maintainer-radar init-config --profile balanced --path .maintainer-radar.json
maintainer-radar init-action --config .maintainer-radar.json --path .github/workflows/maintainer-radar.yml
```
