# Hydrated GitHub Scans

`maintainer-radar repo` uses the fast `gh pr list` shape by default. That is
good for a quick queue scan, but GitHub list output does not include every field
the scorer can use.

Add `--hydrate` when accuracy matters more than speed:

```bash
maintainer-radar repo owner/repo --hydrate
maintainer-radar repo owner/repo --hydrate --sort action
```

GitHub repository URLs are accepted too:

```bash
maintainer-radar repo https://github.com/owner/repo/pulls --hydrate --sort action
```

Hydrated scans fetch each visible PR with `gh pr view` before scoring. This
enables deeper signals from:

- PR body and test-plan text
- changed file paths
- latest reviews
- detailed comments

Hydration can still return incomplete metadata. If the supplied file list is
shorter than the PR's changed file count, the report flags `incomplete file
list` and avoids claiming that tests are absent or that the change is docs-only.
Check the full diff on GitHub before relying on either conclusion.

## Tradeoff

Hydration makes one extra GitHub CLI request per PR after repo filters are
applied. For large queues, use `--limit`, `--label`, `--author`, or
`--updated-since` to keep the scan focused:

```bash
maintainer-radar repo owner/repo --label bug --limit 20 --hydrate
```

The fast path remains the default. Hydration does not add a hosted service,
webhook, token storage, or AI dependency.

## Author Queues

`author` also supports `--hydrate` when the search result includes repository
context:

```bash
maintainer-radar author contributor --limit 20 --hydrate
```
