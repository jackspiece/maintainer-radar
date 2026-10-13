from __future__ import annotations

from pathlib import Path
import re
import unittest

from maintainer_radar import __version__
from maintainer_radar.github import PR_LIST_FIELDS, PR_VIEW_FIELDS


ROOT = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    def test_package_version_is_single_sourced_from_the_package(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIsNone(re.search(r'^version = "', pyproject, re.MULTILINE))
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIn('version = { attr = "maintainer_radar.__version__" }', pyproject)
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")

    def test_readme_quick_start_leads_with_github_action(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        action_ref = "JackSpiece/maintainer-radar@v0.21.0"
        source_install = (
            'python -m pip install '
            '"git+https://github.com/JackSpiece/maintainer-radar.git@v0.21.0"'
        )

        self.assertIn("## Quick Start", readme)
        self.assertIn("GitHub Action and local CLI for read-only pull request triage reports", readme)
        self.assertIn(action_ref, readme)
        self.assertIn(source_install, readme)
        self.assertLess(readme.index(action_ref), readme.index(source_install))
        self.assertNotIn("pip install maintainer-radar", readme)

    def test_project_description_mentions_action_and_read_only_triage(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn(
            'description = "GitHub Action and local CLI for read-only pull request triage reports."',
            pyproject,
        )

    def test_github_fields_include_merge_readiness(self) -> None:
        for field in ("mergeable", "mergeStateStatus", "reviewRequests"):
            with self.subTest(field=field):
                self.assertIn(field, PR_LIST_FIELDS)
                self.assertIn(field, PR_VIEW_FIELDS)


if __name__ == "__main__":
    unittest.main()
