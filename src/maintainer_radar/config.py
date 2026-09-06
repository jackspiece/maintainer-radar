from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "large_diff_lines": 500,
    "very_large_diff_lines": 1500,
    "large_file_count": 10,
    "very_large_file_count": 25,
    "quiet_days": 7,
    "stale_days": 14,
    "test_hints": [],
    "doc_hints": [],
    "generated_hints": [],
}

CONFIG_PROFILES: dict[str, dict[str, Any]] = {
    "balanced": DEFAULT_CONFIG,
    "strict": {
        "large_diff_lines": 300,
        "very_large_diff_lines": 900,
        "large_file_count": 6,
        "very_large_file_count": 15,
        "quiet_days": 5,
        "stale_days": 10,
        "test_hints": [],
        "doc_hints": [],
        "generated_hints": [],
    },
    "large-repo": {
        "large_diff_lines": 1000,
        "very_large_diff_lines": 3000,
        "large_file_count": 20,
        "very_large_file_count": 50,
        "quiet_days": 14,
        "stale_days": 30,
        "test_hints": [],
        "doc_hints": [],
        "generated_hints": [],
    },
}


def load_config(path: str | None = None) -> dict[str, Any]:
    config = _copy_config(DEFAULT_CONFIG)
    config_path = Path(path) if path else Path(".maintainer-radar.json")
    if not path and not config_path.exists():
        return config

    with config_path.open("r", encoding="utf-8") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        raise ValueError("Config file must contain a JSON object")

    for key, value in loaded.items():
        if key not in DEFAULT_CONFIG:
            raise ValueError(f"Unknown config key: {key}")
        if key.endswith("_hints"):
            config[key] = _string_list(value, key)
        else:
            config[key] = _non_negative_int(value, key)
    return config


def config_profile(profile: str) -> dict[str, Any]:
    if profile not in CONFIG_PROFILES:
        raise ValueError(f"Unknown config profile: {profile}")
    return _copy_config(CONFIG_PROFILES[profile])


def render_config_profile(profile: str = "balanced") -> str:
    return json.dumps(config_profile(profile), indent=2) + "\n"


def _copy_config(config: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in config.items():
        copied[key] = list(value) if isinstance(value, list) else value
    return copied


def _non_negative_int(value: Any, key: str) -> int:
    if isinstance(value, (bool, float)):
        raise ValueError(f"Config key {key} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config key {key} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"Config key {key} must be non-negative")
    return parsed


def _string_list(value: Any, key: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Config key {key} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Config key {key} must be a list of strings")
        normalized = item.strip().lower()
        if normalized:
            result.append(normalized)
    return result
