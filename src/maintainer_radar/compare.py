"""Read-only comparison of Radar's analyzed queue JSON snapshots.

This deliberately compares saved observations without scoring them again. Raw
forge exports, review plans, and summary objects are not snapshot inputs.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlsplit

from .normalize import normalize_items
from .snapshot import PROVENANCE_LIMITATION, compare_provenance, snapshot_parts

MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_SNAPSHOT_RECORDS = 10_000
CHECK_FIELDS = ("passed", "failed", "pending", "skipped", "total")
COMPARISON_FIELDS = (
    "title", "action", "risk", "reviewability", "next_step", "checks", "flags", "signals",
)
LIMITATIONS = (
    "Snapshots may cover different filters, scan limits, hydration, times, configurations, or Radar versions; "
    "queue JSON does not record that provenance. Compare equivalent captures where possible.",
    "Newly observed and no longer observed describe only these snapshots. "
    "Absence does not establish that a pull request was closed or merged.",
    "Score and action differences are saved observations, not proof of code progress or a cause of change. "
    "No records are re-scored and no network requests are made.",
)


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("snapshot numbers must be finite")
    return parsed


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_snapshot(path: str | Path) -> list[dict[str, Any]] | dict[str, Any]:
    """Bound input reads and fully validate before returning any observations."""
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"snapshot must be a regular JSON file: {source}")
    with source.open("rb") as stream:
        payload = stream.read(MAX_SNAPSHOT_BYTES + 1)
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError(f"snapshot exceeds {MAX_SNAPSHOT_BYTES} bytes: {source}")
    try:
        data = json.loads(
            payload.decode("utf-8"), parse_constant=_reject_constant,
            parse_float=_finite_float, object_pairs_hook=_unique_keys,
        )
        records = validate_snapshot(data)
        return {**data, "items": records} if isinstance(data, dict) else records
    except (ValueError, RecursionError) as exc:
        raise ValueError(f"invalid snapshot {source}: {exc}") from exc


def _integer(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        limit = f"{minimum}..{maximum}" if maximum is not None else f">= {minimum}"
        raise ValueError(f"{name} must be an integer {limit} (not a boolean)")
    return int(value)


def _string(value: Any, name: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ValueError(f"{name} must be {'a non-empty' if nonempty else 'a'} string")
    # Unpaired surrogate escapes cannot be emitted as UTF-8 Markdown safely.
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError(f"{name} must contain valid Unicode")
    return value


def _identity(value: Any, number: int) -> str:
    url = _string(value, "url", nonempty=True)
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url) or "\\" in url:
        raise ValueError("url must not contain whitespace, control characters, or backslashes")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ValueError("url must be a valid repository-qualified HTTP(S) pull request URL") from exc
    if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username is not None:
        raise ValueError("url must be an HTTP(S) pull request URL without credentials")
    if port == 0:
        raise ValueError("url must have a valid port")
    segments = parts.path.split("/")[1:]
    if len(segments) >= 5 and segments[-3:-1] == ["-", "merge_requests"]:
        repository = segments[:-3]
    elif len(segments) >= 4 and segments[-2] in {"pull", "pulls"}:
        repository = segments[:-2]
    else:
        raise ValueError("url must include a repository and pull/<number>, pulls/<number>, or -/merge_requests/<number>")
    if len(repository) < 2 or any(part in {"", ".", ".."} for part in repository):
        raise ValueError("url must include an owner/group and repository")
    if not re.fullmatch(r"[1-9][0-9]*", segments[-1]) or int(segments[-1]) != number:
        raise ValueError("url pull request number must match number")
    # Exact strings intentionally preserve repositories, forge hosts, casing,
    # query strings and fragments. We do not guess URL aliases.
    return url


def validate_snapshot(data: Any) -> list[dict[str, Any]]:
    """Validate the documented full-queue schema and select compared fields."""
    data, _ = snapshot_parts(data)
    if len(data) > MAX_SNAPSHOT_RECORDS:
        raise ValueError(f"snapshot exceeds {MAX_SNAPSHOT_RECORDS} pull requests")
    items = normalize_items(data, source="github")
    result = []
    seen = set()
    for index, item in enumerate(items):
        try:
            number = _integer(item.get("number"), "number", minimum=1)
            url = _identity(item.get("url"), number)
            if url in seen:
                raise ValueError("duplicate pull request URL")
            seen.add(url)
            record: dict[str, Any] = {"url": url, "number": number}
            for field in ("title", "action", "next_step"):
                record[field] = _string(item.get(field), field, nonempty=field == "action")
            for field in ("risk", "reviewability"):
                record[field] = _integer(item.get(field), field, maximum=100)
            checks = item.get("checks")
            if not isinstance(checks, dict) or set(checks) != set(CHECK_FIELDS):
                raise ValueError("checks must contain passed, failed, pending, skipped, and total counts")
            record["checks"] = {key: _integer(checks[key], f"checks.{key}") for key in CHECK_FIELDS}
            if sum(record["checks"][key] for key in CHECK_FIELDS[:-1]) != record["checks"]["total"]:
                raise ValueError("checks.total must equal passed + failed + pending + skipped")
            for field in ("flags", "signals"):
                values = item.get(field)
                if not isinstance(values, list):
                    raise ValueError(f"{field} must be an array of strings")
                record[field] = sorted({_string(value, field) for value in values})
            result.append(record)
        except ValueError as exc:
            raise ValueError(f"record {index + 1}: {exc}") from exc
    return sorted(result, key=lambda item: item["url"])


def compare_snapshots(before: Any, after: Any) -> dict[str, Any]:
    """Compare supported values; input ordering never changes report ordering."""
    _, before_provenance = snapshot_parts(before)
    _, after_provenance = snapshot_parts(after)
    old = {item["url"]: item for item in validate_snapshot(before)}
    new = {item["url"]: item for item in validate_snapshot(after)}
    added = [new[url] for url in sorted(new.keys() - old.keys())]
    missing = [old[url] for url in sorted(old.keys() - new.keys())]
    changed = []
    unchanged = []
    for url in sorted(old.keys() & new.keys()):
        changes = [
            {"field": field, "before": old[url][field], "after": new[url][field]}
            for field in COMPARISON_FIELDS if old[url][field] != new[url][field]
        ]
        if changes:
            changed.append({"url": url, "number": new[url]["number"],
                            "before": old[url], "after": new[url], "changes": changes})
        else:
            unchanged.append(new[url])
    report = {
        "schema_version": 1,
        "comparison_fields": list(COMPARISON_FIELDS),
        "limitations": list(LIMITATIONS),
        "summary": {"before": len(old), "after": len(new), "newly_observed": len(added),
                    "no_longer_observed": len(missing), "changed": len(changed), "unchanged": len(unchanged)},
        "newly_observed": added,
        "no_longer_observed": missing,
        "changed": changed,
        "unchanged": unchanged,
    }
    if before_provenance is not None or after_provenance is not None:
        report["provenance"] = compare_provenance(before_provenance, after_provenance)
        report["limitations"] = [PROVENANCE_LIMITATION, *LIMITATIONS[1:]]
    return report


def _markdown_text(value: str) -> str:
    # Escape every ASCII punctuation character using entities. This also keeps
    # pipes, brackets, backticks, entities and HTML inert inside table cells.
    # All Unicode line separators/control whitespace become ordinary spaces.
    text = " ".join(value.split())
    return "".join(
        f"&#{ord(char)};" if (char.isascii() and not char.isalnum() and char != " ") or ord(char) < 32
        else char for char in text
    )


def _display(value: Any) -> str:
    if isinstance(value, str):
        return _markdown_text(value)
    return _markdown_text(json.dumps(value, ensure_ascii=True, sort_keys=True))


def _pr_link(item: dict[str, Any]) -> str:
    # Validation is repeated for renderer callers, and URL punctuation that can
    # close a Markdown link is encoded without changing the JSON identity.
    url = _identity(item["url"], item["number"])
    destination = quote(url, safe=":/?#@%=&+;,~.-_").replace("&", "&amp;")
    return f"[#{item['number']} {_markdown_text(item['title'])}](<{destination}>)"


def render_comparison(report: dict[str, Any], fmt: str = "markdown") -> str:
    if fmt == "json":
        return json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if fmt != "markdown":
        raise ValueError("compare supports --format markdown or json")
    summary = report["summary"]
    lines = [
        "# Queue snapshot comparison", "",
        f"Before: {summary['before']} PRs. After: {summary['after']} PRs.", "",
        f"Newly observed: {summary['newly_observed']}. No longer observed: {summary['no_longer_observed']}. "
        f"Changed: {summary['changed']}. Unchanged in compared fields: {summary['unchanged']}.", "",
    ]
    provenance = report.get("provenance")
    if provenance is not None:
        lines.extend(["## Capture settings", ""])
        messages = {
            "recorded-settings-match": "Recorded settings match. This does not prove comparable coverage.",
            "recorded-settings-differ": "Recorded settings differ. Interpret score and queue changes with caution.",
            "unknown": "Capture comparability is unknown: one input is a legacy array without provenance.",
        }
        lines.extend([messages[provenance["status"]], ""])
        for label in ("before", "after"):
            context = provenance[label]
            if context is not None:
                lines.append(f"- {label.title()}: Radar {_display(context['radar_version'])}; "
                             f"analysis time {_display(context['analysis_time'])}; "
                             f"observed {context['counts']['observed']}, emitted {context['counts']['emitted']}.")
        lines.append("")
        if provenance["differences"]:
            lines.extend(["| Setting | Before | After |", "| --- | --- | --- |"])
            for change in provenance["differences"]:
                lines.append(f"| {change['field']} | {_display(change['before'])} | {_display(change['after'])} |")
            lines.append("")
    lines.extend(f"- {text}" for text in report["limitations"])
    lines.extend(["", "Compared fields: " + ", ".join(COMPARISON_FIELDS) + ".", ""])
    for key, heading in (("newly_observed", "Newly observed"), ("no_longer_observed", "No longer observed")):
        lines.extend([f"## {heading}", ""])
        if not report[key]:
            lines.extend(["None.", ""])
            continue
        for item in report[key]:
            lines.append(f"- {_pr_link(item)}: {_display(item['action'])}; "
                         f"risk {item['risk']}; reviewability {item['reviewability']}.")
        lines.append("")
    lines.extend(["## Changed observations", ""])
    if not report["changed"]:
        lines.extend(["None.", ""])
    for item in report["changed"]:
        lines.extend([f"### {_pr_link(item['after'])}", "", "| Field | Before | After |", "| --- | --- | --- |"])
        for change in item["changes"]:
            lines.append(f"| {change['field']} | {_display(change['before'])} | {_display(change['after'])} |")
        lines.append("")
    return "\n".join(lines)
