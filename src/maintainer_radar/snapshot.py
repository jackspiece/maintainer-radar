"""Opt-in capture metadata, without paths, environment, or completeness claims."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import DEFAULT_CONFIG

SNAPSHOT_KIND = "maintainer-radar.snapshot"
FILTER_FIELDS = ("label", "author", "stale_days", "updated_since", "action", "min_score", "max_risk")
CAPTURE_FIELDS = ("command", "source", "repository", "author", "state", "limit", "hydrate", "filters", "sort", "top")
PROVENANCE_LIMITATION = (
    "Capture settings are self-reported, not independently verified. Matching recorded settings do not establish "
    "equivalent or complete coverage. Offline export coverage and hydration are unknown; analysis times and "
    "observed/output counts are context, not comparable settings."
)


def _object(value: Any, keys: tuple[str, ...], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{name} must contain exactly {', '.join(keys)}")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError(f"{name} must not contain control characters or invalid Unicode")
    return value


def _integer(value: Any, name: str, minimum: int = 0, maximum: int | None = None) -> None:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum or 'unbounded'}")


def validate_provenance(value: Any, emitted: int) -> dict[str, Any]:
    """Reject incomplete/ambiguous metadata instead of silently trusting it."""
    data = _object(value, ("radar_version", "analysis_time", "config", "capture", "counts"), "provenance")
    _text(data["radar_version"], "radar_version")
    timestamp = _text(data["analysis_time"], "analysis_time")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("analysis_time must be an ISO timestamp with timezone") from exc
    if parsed.tzinfo is None:
        raise ValueError("analysis_time must be an ISO timestamp with timezone")
    config = _object(data["config"], tuple(DEFAULT_CONFIG), "config")
    for key, item in config.items():
        if key.endswith("_hints"):
            if not isinstance(item, list):
                raise ValueError(f"config.{key} must be an array of strings")
            for hint in item:
                _text(hint, f"config.{key}")
        else:
            _integer(item, f"config.{key}")
    capture = _object(data["capture"], CAPTURE_FIELDS, "capture")
    command = _text(capture["command"], "capture.command")
    source = _text(capture["source"], "capture.source")
    if command not in {"repo", "author", "from-json"} or source not in {"github", "gitlab", "forgejo", "gitea"}:
        raise ValueError("unsupported snapshot capture command or source")
    if command == "from-json":
        if any(capture[key] is not None for key in ("repository", "author", "state", "limit", "hydrate")):
            raise ValueError("offline capture scope, limit, and hydration must be null (unknown)")
    else:
        scope, unused = ("repository", "author") if command == "repo" else ("author", "repository")
        _text(capture[scope], f"capture.{scope}")
        states = ("open", "closed", "all") if command == "repo" else ("open", "closed")
        if source != "github" or capture[unused] is not None or capture["state"] not in states:
            raise ValueError("invalid live capture source, scope, or state")
        _integer(capture["limit"], "capture.limit", 1)
        if type(capture["hydrate"]) is not bool:
            raise ValueError("live capture.hydrate must be a boolean")
    filters = _object(capture["filters"], FILTER_FIELDS, "capture.filters")
    for key, item in filters.items():
        if item is None:
            continue
        if key in {"stale_days", "min_score", "max_risk"}:
            _integer(item, f"filters.{key}", maximum=None if key == "stale_days" else 100)
        else:
            _text(item, f"filters.{key}")
        if command != "repo" and key in {"label", "author", "stale_days", "updated_since"}:
            raise ValueError(f"filters.{key} is not supported for {command} snapshots")
    if capture["sort"] not in ("input", "action", "score", "risk", "stale", "number"):
        raise ValueError("invalid capture.sort")
    if capture["top"] is not None:
        _integer(capture["top"], "capture.top", 1)
    counts = _object(data["counts"], ("observed", "emitted"), "counts")
    _integer(counts["observed"], "counts.observed")
    _integer(counts["emitted"], "counts.emitted")
    if counts["emitted"] != emitted or counts["observed"] < emitted:
        raise ValueError("counts must match emitted records and observed must be >= emitted")
    if capture["top"] is not None and emitted > capture["top"]:
        raise ValueError("emitted records must not exceed capture.top")
    return data


def snapshot_parts(data: Any) -> tuple[Any, dict[str, Any] | None]:
    """Split an envelope or a legacy array; validate all recorded metadata."""
    if isinstance(data, list):
        return data, None
    envelope = _object(data, ("kind", "schema_version", "provenance", "items"), "snapshot envelope")
    if envelope["kind"] != SNAPSHOT_KIND or type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1:
        raise ValueError("unsupported snapshot kind or schema_version")
    if not isinstance(envelope["items"], list):
        raise ValueError("snapshot items must be an array")
    return envelope["items"], validate_provenance(envelope["provenance"], len(envelope["items"]))


def compare_provenance(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    """Compare settings, while keeping time/count context separate."""
    differences = []
    if before is not None and after is not None:
        def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
            result = {}
            for key, value in sorted(data.items()):
                name = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    result.update(flatten(value, name))
                else:
                    result[name] = value
            return result

        old = flatten({key: before[key] for key in ("radar_version", "config", "capture")})
        new = flatten({key: after[key] for key in ("radar_version", "config", "capture")})
        differences = [{"field": key, "before": old[key], "after": new[key]}
                       for key in sorted(old) if old[key] != new[key]]
        status = "recorded-settings-differ" if differences else "recorded-settings-match"
    else:
        status = "unknown"
    return {"status": status, "before": before, "after": after, "differences": differences}
