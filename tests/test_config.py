from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from maintainer_radar.config import (
    DEFAULT_CONFIG,
    config_profile,
    load_config,
    render_config_profile,
)


class ConfigTests(unittest.TestCase):
    def test_missing_implicit_config_returns_defaults(self) -> None:
        with patch.object(Path, "exists", return_value=False):
            self.assertEqual(load_config(), DEFAULT_CONFIG)

    def test_missing_explicit_config_fails(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_config("/no/such/file.json")

    def test_non_integer_thresholds_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            for value in (True, False, 3.7, -1):
                with self.subTest(value=value):
                    path.write_text(json.dumps({"quiet_days": value}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_config(str(path))

    def test_load_config_merges_known_keys(self) -> None:
        config = load_config("tests/fixtures/maintainer-radar-config.json")

        self.assertEqual(config["large_diff_lines"], 20)
        self.assertEqual(config["stale_days"], 10)
        self.assertIn("specs/", config["test_hints"])

    def test_unknown_config_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"surprise": 1}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_config(str(path))

    def test_config_profiles_are_renderable_and_loadable(self) -> None:
        strict = config_profile("strict")
        large_repo = config_profile("large-repo")

        self.assertLess(strict["large_diff_lines"], DEFAULT_CONFIG["large_diff_lines"])
        self.assertGreater(large_repo["large_diff_lines"], DEFAULT_CONFIG["large_diff_lines"])

        rendered = render_config_profile("strict")
        parsed = json.loads(rendered)

        self.assertEqual(parsed["quiet_days"], 5)
        self.assertEqual(parsed["stale_days"], 10)

    def test_unknown_config_profile_fails(self) -> None:
        with self.assertRaises(ValueError):
            config_profile("surprise")


if __name__ == "__main__":
    unittest.main()
