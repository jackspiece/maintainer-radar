from __future__ import annotations

from typing import Final

REPORT_EXTENSIONS: Final[dict[str, str]] = {
    "markdown": "md",
    "html": "html",
    "json": "json",
    "csv": "csv",
}

WORKFLOW_SORTS: Final[set[str]] = {"input", "action", "score", "risk", "stale", "number"}
WORKFLOW_ACTION_FILTERS: Final[set[str]] = {
    "ask-for-ci-fix",
    "needs-author-follow-up",
    "needs-triage",
    "request-smaller-pr",
    "review-now",
    "review-with-caution",
    "wait-for-author",
    "wait-for-ci",
}
ACTION_REPOSITORY: Final[str] = "JackSpiece/maintainer-radar"
# Update only after publishing a release; development versions may have no tag.
DEFAULT_ACTION_REF: Final[str] = f"{ACTION_REPOSITORY}@v0.20.0"


def render_github_action_workflow(
    *,
    report_format: str = "markdown",
    schedule: str = "0 8 * * 1-5",
    limit: int = 50,
    sort: str = "action",
    hydrate: bool = True,
    top: int | None = None,
    group_by: str | None = None,
    review_plan_minutes: int | None = None,
    label: str | None = None,
    author: str | None = None,
    stale_days: int | None = None,
    updated_since: str | None = None,
    action_filter: str | None = None,
    min_score: int | None = None,
    max_risk: int | None = None,
    config: str | None = None,
    step_summary: bool = True,
    action_ref: str | None = None,
) -> str:
    if report_format not in REPORT_EXTENSIONS:
        formats = ", ".join(sorted(REPORT_EXTENSIONS))
        raise ValueError(f"--report-format must be one of: {formats}")
    if sort not in WORKFLOW_SORTS:
        sorts = ", ".join(sorted(WORKFLOW_SORTS))
        raise ValueError(f"--sort must be one of: {sorts}")
    if limit < 1:
        raise ValueError("--limit must be 1 or greater")
    if top is not None and top < 1:
        raise ValueError("--top must be 1 or greater")
    if review_plan_minutes is not None and review_plan_minutes < 1:
        raise ValueError("--review-plan-minutes must be 1 or greater")
    if review_plan_minutes is not None and report_format not in {"markdown", "html", "json"}:
        raise ValueError("--review-plan-minutes requires --report-format markdown, html, or json")
    if stale_days is not None and stale_days < 1:
        raise ValueError("--stale-days must be 1 or greater")
    if min_score is not None and min_score < 0:
        raise ValueError("--min-score must be 0 or greater")
    if max_risk is not None and max_risk < 0:
        raise ValueError("--max-risk must be 0 or greater")
    clean_action_filter = _clean_single_line(action_filter, "--action")
    if clean_action_filter and clean_action_filter not in WORKFLOW_ACTION_FILTERS:
        actions = ", ".join(sorted(WORKFLOW_ACTION_FILTERS))
        raise ValueError(f"--action must be one of: {actions}")
    clean_group_by = _clean_single_line(group_by, "--group-by")
    if clean_group_by and clean_group_by != "action":
        raise ValueError("--group-by must be action")
    clean_config = _clean_single_line(config, "--config")
    clean_label = _clean_single_line(label, "--label")
    clean_author = _clean_single_line(author, "--author")
    clean_updated_since = _clean_single_line(updated_since, "--updated-since")
    clean_action_ref = _clean_single_line(action_ref, "--action-ref")
    clean_schedule = schedule.strip()
    if not clean_schedule or "\n" in clean_schedule or "\r" in clean_schedule:
        raise ValueError("--schedule must be a single-line cron expression")

    extension = REPORT_EXTENSIONS[report_format]
    is_review_plan = review_plan_minutes is not None
    output_stem = "review-plan" if is_review_plan else "maintainer-radar"
    output_path = f"{output_stem}.{extension}"
    if is_review_plan and report_format == "markdown":
        artifact_name = "review-plan"
    else:
        artifact_name = f"{output_stem}-{report_format}"
    workflow_name = "Maintainer Radar Review Plan" if is_review_plan else "Maintainer Radar Report"
    step_name = (
        f"Build {review_plan_minutes} minute review plan"
        if is_review_plan
        else f"Build {report_format} report"
    )
    action = clean_action_ref or DEFAULT_ACTION_REF
    checkout = "      - uses: actions/checkout@v7\n" if clean_config else ""
    filter_inputs = "".join(
        [
            _yaml_input("label", clean_label),
            _yaml_input("author", clean_author),
            _yaml_input("stale-days", stale_days),
            _yaml_input("updated-since", clean_updated_since),
            _yaml_input("action", clean_action_filter),
            _yaml_input("min-score", min_score),
            _yaml_input("max-risk", max_risk),
            _yaml_input("top", top),
            _yaml_input("group-by", clean_group_by),
            _yaml_input("review-plan-minutes", review_plan_minutes),
            _yaml_input("config", clean_config),
        ]
    )

    escaped_schedule = _escape_yaml_value(clean_schedule)
    return f"""name: {workflow_name}

on:
  workflow_dispatch:
  schedule:
    - cron: "{escaped_schedule}"

permissions:
  contents: read
  pull-requests: read

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
{checkout}      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - name: {step_name}
        id: radar
        uses: {action}
        env:
          GH_TOKEN: ${{{{ github.token }}}}
        with:
          repository: ${{{{ github.repository }}}}
          format: {report_format}
          output: {output_path}
          limit: "{limit}"
          sort: {sort}
{filter_inputs}          hydrate: "{str(hydrate).lower()}"
          step-summary: "{str(step_summary).lower()}"
      - uses: actions/upload-artifact@v7
        with:
          name: {artifact_name}
          path: ${{{{ steps.radar.outputs.report-path }}}}
"""


def _clean_single_line(value: str | None, option_name: str) -> str:
    cleaned = (value or "").strip()
    if "\n" in cleaned or "\r" in cleaned:
        raise ValueError(f"{option_name} must be a single-line value")
    return cleaned


def _escape_yaml_value(value: str) -> str:
    # Escape backslashes before quotes so a value like foo\" cannot break
    # out of the double-quoted YAML scalar.
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _yaml_input(name: str, value: str | int | None) -> str:
    if value is None or value == "":
        return ""
    escaped = _escape_yaml_value(str(value))
    return f'          {name}: "{escaped}"\n'
