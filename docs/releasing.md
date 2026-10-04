# Release checklist

The package version is defined only in `src/maintainer_radar/__init__.py`.
The current development batch is **0.21.0**, still marked **Unreleased**.
Installation examples and generated workflows stay on the published
**v0.20.0** until a new tag is actually available.

## Prepare and verify

From the repository root, with Python 3.10 or newer:

```bash
python -m pip install -e . build twine "ruff==0.16.0" "mypy==2.3.0"
python -m unittest discover -s tests
ruff check src tests scripts
mypy src
node --check docs/assets/demo.js
node tests/demo_smoke.js
python scripts/check_release.py
python scripts/generate_examples.py --check
python -m build
python -m twine check --strict dist/*
```

The test suite checks all six committed offline reports against the current
CLI. When scoring or rendering changes intentionally, run
`python scripts/generate_examples.py` and review the output diff.

Exercise the browser separately with mocked GitHub responses:

```bash
python -m pip install playwright
python -m playwright install firefox
python tests/browser_smoke.py
```

Also install the wheel in a fresh virtual environment and run an offline
command. CI and the release workflow run the full test suite from the unpacked source
archive and perform this installed-wheel smoke check automatically:

```bash
python -m venv /tmp/radar-wheel-check
/tmp/radar-wheel-check/bin/python -m pip install --no-deps dist/*.whl
/tmp/radar-wheel-check/bin/maintainer-radar --help
/tmp/radar-wheel-check/bin/maintainer-radar from-json examples/sample-prs.json \
  --now 2026-06-01T00:00:00Z
```

Use a fresh output directory when building a later version so old artifacts
are not included by the `dist/*` glob. A local test pass is not a substitute for
the Python 3.10/3.11/3.12 and authenticated Action checks on the final commit.

## Finalize only when publishing is intended

1. Review the batch and change `## Unreleased (0.21.0)` to `## 0.21.0` in the
   changelog. Keep the package version and intended tag aligned.
2. Run `python scripts/check_release.py --tag v0.21.0`. An unreleased heading,
   missing notes, or mismatched tag must fail before upload.
3. Merge the reviewed candidate, check CI on that commit, then create the
   matching tag and publish its GitHub release. Do not move an existing tag.
4. Verify the release workflow and uploaded package before changing install
   examples or `DEFAULT_ACTION_REF` to the new published tag.

Publishing a GitHub release triggers the PyPI publishing job. The `pypi`
environment and PyPI trusted publisher must already be configured correctly;
this checklist does not create credentials or grant access. A manual run of
the Release workflow builds and checks artifacts without publishing to PyPI.

The release workflow repeats the unit tests, lint, type checks, Node demo checks,
distribution checks, and installed-wheel smoke test. It rejects a published
release whose tag, package version, or finalized notes disagree. The browser
smoke and live Action CI remain separate release checklist checks.
