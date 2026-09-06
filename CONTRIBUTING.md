# Contributing

Thanks for helping improve Maintainer Radar.

The project favors small, reviewable PRs with clear examples.

## Local Setup

```bash
python -m pip install -e .
python -m unittest discover -s tests
```

Without installing:

```bash
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src python -m maintainer_radar from-json examples/sample-prs.json
```

## Tests, Lint, and Types

CI runs the unit test suite on Python 3.10, 3.11, and 3.12, plus `ruff` for
linting and `mypy` for advisory type checking. Run them locally before opening
a PR:

```bash
make test
make lint       # requires: python -m pip install "ruff==0.16.0"
make typecheck  # requires: python -m pip install "mypy==2.3.0"
```

For changes to the demo, also run:

```bash
node tests/demo_smoke.js
# Optional dependency for the real-browser regression checks:
python -m pip install playwright
python -m playwright install firefox
python tests/browser_smoke.py
```

The browser checks use mocked GitHub responses and an ephemeral browser profile.
They cover the sample, budgets, exports, small screens, partial scans, and errors.

## Good Contributions

- new scoring fixtures from real maintainer workflows
- clearer Markdown reports
- more accurate risk flags
- support for exported JSON from other forges
- docs that help maintainers adopt the tool

If you try Maintainer Radar on a public repository, the maintainer feedback
issue template is the best place to share what queue routing felt useful or
wrong.

## Pull Request Checklist

- Add or update tests for scoring changes.
- Keep output deterministic.
- Do not add a network service or persistent token storage.
- Explain any new heuristic in plain language.
- Keep the browser demo scoring (docs/assets/demo.js) in sync when changing
  Python scoring heuristics, or call out the divergence in the PR.

## Release Process

A commit does not need a new version. Keep related work together under the
existing **Unreleased** changelog section until it is ready for users.

- Copy changes, demo styling, documentation, and internal refactors can land
  without a package release. GitHub Pages can update separately.
- Batch fixes into a patch release. Use a minor release for a coherent set of
  new capabilities or intentional behavior changes while the project is 0.x.
- Choose the version when preparing the release, not during each small edit.
  Describe the user-visible change and how it was verified.
- Keep installation examples pinned to the latest published tag until the new
  release is actually available. Never move an existing version tag.

When the batch is ready:

1. Check the unit tests, browser smoke checks, lint, types, and sample commands.
2. Set `__version__` in `src/maintainer_radar/__init__.py`, which is the package
   version source, and finalize that release's changelog entry.
3. Merge to `main`, create the matching `vX.Y.Z` tag, and publish its release.
4. Update installation examples and `DEFAULT_ACTION_REF` in
   `src/maintainer_radar/workflow.py` to that published tag.

Publishing a release triggers the existing PyPI workflow. Trusted publishing
must be configured for the `pypi` environment before using it.
