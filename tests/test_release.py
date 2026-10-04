from __future__ import annotations

from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = runpy.run_path(str(ROOT / "scripts/check_release.py"))
validate_release = CHECK["validate_release"]


class ReleaseTests(unittest.TestCase):
    def test_checkout_metadata_is_consistent(self) -> None:
        validate_release(CHECK["read_version"](), (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_unreleased_version_can_be_built_but_not_published(self) -> None:
        changelog = "# Changelog\n\n## Unreleased (0.21.0)\n\n- A verified change.\n"
        validate_release("0.21.0", changelog)
        with self.assertRaisesRegex(ValueError, "Finalize the changelog"):
            validate_release("0.21.0", changelog, "v0.21.0")

    def test_matching_finalized_release_can_be_published(self) -> None:
        validate_release("0.21.0", "## 0.21.0\n\n- A verified change.\n", "v0.21.0")
        validate_release("0.21.0", "## Unreleased\n\n## 0.21.0\n\n- A verified change.\n", "v0.21.0")

    def test_pending_generic_unreleased_notes_block_publication(self) -> None:
        changelog = "## Unreleased\n\n- Pending fix.\n\n## 0.21.0\n\n- A release.\n"
        validate_release("0.21.0", changelog)
        with self.assertRaisesRegex(ValueError, "Move pending Unreleased"):
            validate_release("0.21.0", changelog, "v0.21.0")

    def test_mismatched_tag_is_rejected(self) -> None:
        for tag in ("v0.20.0", "0.21.0", "main", ""):
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, "does not match"):
                validate_release("0.21.0", "## 0.21.0\n\n- A verified change.\n", tag)

    def test_missing_stale_or_empty_notes_are_rejected(self) -> None:
        for changelog in (
            "# Changelog\n", "## 0.20.0\n\n- An older release.\n",
            "## Unreleased (0.22.0)\n\n- Future work.\n\n## 0.21.0\n\n- A release.\n",
            "## 0.21.0\n\n## 0.20.0\n\n- An older release.\n",
        ):
            with self.subTest(changelog=changelog), self.assertRaises(ValueError):
                validate_release("0.21.0", changelog)

    def test_invalid_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "X.Y.Z"):
            validate_release("0.21", "## 0.21\n\n- A change.\n")


if __name__ == "__main__":
    unittest.main()
