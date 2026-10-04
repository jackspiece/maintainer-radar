from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable

from .compare import compare_snapshots, load_snapshot, render_comparison
from .config import CONFIG_PROFILES, load_config, render_config_profile
from .github import GitHubCliError, list_repo_prs, search_author_prs, view_pr
from .normalize import normalize_items
from .render import (
    render_comment_template,
    render_comment_csv,
    render_comment_html,
    render_csv,
    render_detail,
    render_html,
    render_markdown,
    render_recommendation_json,
    render_recommendation_markdown,
    render_review_plan_html,
    render_review_plan_json,
    render_review_plan_markdown,
    render_summary_csv,
    render_summary_markdown,
    summarize_report,
)
from .scoring import analyze_pr, days_since, parse_github_datetime
from .workflow import render_github_action_workflow

ACTION_SLUGS = {
    "review-now": "review now",
    "review-with-caution": "review with caution",
    "wait-for-author": "wait for author",
    "wait-for-ci": "wait for CI",
    "ask-for-ci-fix": "ask for CI fix",
    "needs-author-follow-up": "needs author follow-up",
    "request-smaller-pr": "request smaller PR",
    "needs-triage": "needs triage",
}

ACTION_PRIORITY = {
    "review now": 0,
    "review with caution": 1,
    "ask for CI fix": 2,
    "wait for CI": 3,
    "needs author follow-up": 4,
    "wait for author": 5,
    "request smaller PR": 6,
    "needs triage": 7,
}

SORT_CHOICES = ["input", "action", "score", "risk", "stale", "number"]

HYDRATE_MAX_WORKERS = 8

GITHUB_REPO_URL_RE = re.compile(
    r"^(?:https?://)?github\.com/(?P<owner>[^/\s?#]+)/(?P<repo>[^/\s?#]+)(?:[/?#].*)?$",
    re.IGNORECASE,
)
GITHUB_PR_URL_RE = re.compile(
    r"^(?:https?://)?github\.com/(?P<owner>[^/\s?#]+)/(?P<repo>[^/\s?#]+)/pull/(?P<number>\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)


def _load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _parse_now(value: str | None) -> datetime | None:
    if not value:
        return None
    now = parse_github_datetime(value)
    if now is None:
        raise ValueError("--now must be an ISO date, for example 2026-06-01")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now


def _as_pr_list(data: Any, *, source: str = "github") -> list[dict[str, Any]]:
    return normalize_items(data, source=source)


def _normalize_repository_arg(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return cleaned

    pr_match = GITHUB_PR_URL_RE.match(cleaned)
    if pr_match:
        repo = _strip_git_suffix(pr_match.group("repo"))
        return f"{pr_match.group('owner')}/{repo}"

    repo_match = GITHUB_REPO_URL_RE.match(cleaned)
    if repo_match:
        repo = _strip_git_suffix(repo_match.group("repo"))
        return f"{repo_match.group('owner')}/{repo}"

    parts = cleaned.split("/")
    if len(parts) >= 2 and not cleaned.lower().startswith(("http://", "https://")):
        return f"{parts[0]}/{_strip_git_suffix(parts[1])}"
    return cleaned


def _strip_git_suffix(value: str) -> str:
    return value[:-4] if value.endswith(".git") else value


def _parse_pr_reference(repository: str, number: str | None) -> tuple[str, str]:
    if number is not None:
        return _normalize_repository_arg(repository), str(number)

    match = GITHUB_PR_URL_RE.match(str(repository or "").strip())
    if not match:
        raise ValueError(
            "pr requires a pull request number unless the repository argument is a GitHub PR URL"
        )
    repo = _strip_git_suffix(match.group("repo"))
    return f"{match.group('owner')}/{repo}", match.group("number")


def _label_names(pr: dict[str, Any]) -> set[str]:
    labels = pr.get("labels") or []
    names: set[str] = set()
    for label in labels:
        if isinstance(label, str):
            names.add(label.lower())
        elif isinstance(label, dict) and label.get("name"):
            names.add(str(label["name"]).lower())
    return names


def _author_login(pr: dict[str, Any]) -> str:
    author = pr.get("author")
    if isinstance(author, dict):
        return str(author.get("login") or "").lower()
    return str(author or "").lower()


def filter_prs(
    prs: list[dict[str, Any]],
    *,
    label: str | None = None,
    author: str | None = None,
    stale_days: int | None = None,
    updated_since: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    result = prs
    if label:
        wanted = label.lower()
        result = [pr for pr in result if wanted in _label_names(pr)]
    if author:
        wanted_author = author.lower()
        result = [pr for pr in result if _author_login(pr) == wanted_author]
    if stale_days is not None:
        stale_result: list[dict[str, Any]] = []
        for pr in result:
            quiet_days = days_since(pr.get("updatedAt"), now)
            if quiet_days is not None and quiet_days >= stale_days:
                stale_result.append(pr)
        result = stale_result
    if updated_since:
        since = parse_github_datetime(updated_since)
        if since is None:
            raise ValueError("--updated-since must be an ISO date, for example 2026-06-01")
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        updated_result: list[dict[str, Any]] = []
        for pr in result:
            updated_at = parse_github_datetime(pr.get("updatedAt"))
            if updated_at is None:
                continue
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if updated_at >= since:
                updated_result.append(pr)
        result = updated_result
    return result


def hydrate_prs(
    prs: list[dict[str, Any]],
    *,
    repository: str | None = None,
    viewer: Callable[[str, str | int], dict[str, Any]] = view_pr,
    max_workers: int = HYDRATE_MAX_WORKERS,
) -> list[dict[str, Any]]:
    def hydrate_one(pr: dict[str, Any]) -> dict[str, Any]:
        repo_name = repository or _repository_name(pr.get("repository"))
        number = pr.get("number")
        if not repo_name or number is None:
            return pr
        detail = viewer(repo_name, number)
        return {**pr, **detail}

    if max_workers <= 1 or len(prs) <= 1:
        return [hydrate_one(pr) for pr in prs]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(prs))) as pool:
        return list(pool.map(hydrate_one, prs))


def _repository_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    if value.get("nameWithOwner"):
        return str(value["nameWithOwner"])
    if value.get("fullName"):
        return str(value["fullName"])
    owner = value.get("owner")
    owner_name = owner.get("login") if isinstance(owner, dict) else owner
    if owner_name and value.get("name"):
        return f"{owner_name}/{value['name']}"
    return None


def filter_analyses(
    analyses: list[dict[str, Any]],
    *,
    action: str | None = None,
    min_score: int | None = None,
    max_risk: int | None = None,
) -> list[dict[str, Any]]:
    result = analyses
    if action:
        wanted_action = ACTION_SLUGS[action]
        result = [item for item in result if item.get("action") == wanted_action]
    if min_score is not None:
        result = [item for item in result if int(item.get("reviewability") or 0) >= min_score]
    if max_risk is not None:
        result = [item for item in result if int(item.get("risk") or 0) <= max_risk]
    return result


def sort_analyses(analyses: list[dict[str, Any]], sort_by: str = "input") -> list[dict[str, Any]]:
    if sort_by == "input":
        return analyses
    if sort_by == "action":
        return sorted(
            analyses,
            key=lambda item: (
                ACTION_PRIORITY.get(str(item.get("action") or ""), 99),
                -int(item.get("reviewability") or 0),
                _number_value(item),
            ),
        )
    if sort_by == "score":
        return sorted(
            analyses,
            key=lambda item: (-int(item.get("reviewability") or 0), _number_value(item)),
        )
    if sort_by == "risk":
        return sorted(
            analyses,
            key=lambda item: (-int(item.get("risk") or 0), _number_value(item)),
        )
    if sort_by == "stale":
        return sorted(
            analyses,
            key=lambda item: (-int(item.get("stale_days") or 0), _number_value(item)),
        )
    if sort_by == "number":
        return sorted(analyses, key=_number_value)
    raise ValueError(f"Unsupported sort: {sort_by}")


def limit_analyses(analyses: list[dict[str, Any]], top: int | None = None) -> list[dict[str, Any]]:
    if top is None:
        return analyses
    if top < 1:
        raise ValueError("--top must be 1 or greater")
    return analyses[:top]


def _number_value(item: dict[str, Any]) -> int:
    try:
        return int(item.get("number") or 0)
    except (TypeError, ValueError):
        return 0


def _emit(
    analyses: list[dict[str, Any]],
    fmt: str,
    *,
    detail: bool = False,
    summary_only: bool = False,
    group_by: str | None = None,
    review_plan_minutes: int | None = None,
) -> None:
    if review_plan_minutes is not None:
        if summary_only:
            raise ValueError("--review-plan-minutes cannot be combined with --summary-only")
        if detail:
            raise ValueError("--review-plan-minutes is only available for queue reports")
        if fmt not in {"markdown", "html", "json"}:
            raise ValueError(
                "--review-plan-minutes currently supports --format markdown, html, or json"
            )
        if fmt == "json":
            print(render_review_plan_json(analyses, review_plan_minutes), end="")
            return
        if fmt == "html":
            print(render_review_plan_html(analyses, review_plan_minutes), end="")
            return
        print(render_review_plan_markdown(analyses, review_plan_minutes), end="")
        return
    if fmt == "json":
        if summary_only:
            print(json.dumps(summarize_report(analyses), indent=2))
        else:
            print(json.dumps(analyses[0] if detail and len(analyses) == 1 else analyses, indent=2))
        return
    if fmt == "csv":
        if summary_only:
            print(render_summary_csv(analyses), end="")
        else:
            print(render_csv(analyses), end="")
        return
    if fmt == "html":
        print(render_html(analyses, summary_only=summary_only, group_by=group_by), end="")
        return
    if summary_only:
        print(render_summary_markdown(analyses), end="")
        return
    if detail and len(analyses) == 1:
        print(render_detail(analyses[0]), end="")
    else:
        print(render_markdown(analyses, group_by=group_by), end="")


def _emit_recommendation(analyses: list[dict[str, Any]], fmt: str, repository: str) -> None:
    if fmt == "json":
        print(render_recommendation_json(analyses, repository))
        return
    if fmt != "markdown":
        raise ValueError("recommend currently supports --format markdown or json")
    print(render_recommendation_markdown(analyses, repository), end="")


def _ensure_paths_writable(paths: list[Path], *, force: bool) -> None:
    if force:
        return
    for path in paths:
        if path.exists():
            raise ValueError(f"{path} already exists; pass --force to overwrite")


def _write_output_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maintainer-radar",
        description="Generate local-first maintainer triage reports for GitHub pull requests.",
    )

    def add_format_argument(target: argparse.ArgumentParser, *, default: str | object) -> None:
        target.add_argument(
            "--format",
            choices=["markdown", "json", "csv", "html"],
            default=default,
            help="Output format. Default: markdown.",
        )

    def add_recommend_format_argument(
        target: argparse.ArgumentParser,
        *,
        default: str | object,
    ) -> None:
        target.add_argument(
            "--format",
            choices=["markdown", "json"],
            default=default,
            help="Output format. Default: markdown.",
        )

    def add_config_argument(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--config",
            help="Path to config JSON. Defaults to .maintainer-radar.json when present.",
        )

    def add_sort_argument(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--sort",
            choices=SORT_CHOICES,
            default="input",
            help="Sort queue output. Default: input.",
        )

    def add_hydrate_argument(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--hydrate",
            action="store_true",
            help="Fetch full PR detail before scoring. Slower, but enables body, file, and review signals.",
        )

    def add_now_argument(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--now",
            help="Override the current time for stale calculations. Use an ISO date.",
        )

    def add_top_argument(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--top",
            type=int,
            help="Only emit the first N PRs after filtering and sorting.",
        )

    def add_group_by_argument(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--group-by",
            choices=["action"],
            help="Group Markdown and HTML queue reports by a field.",
        )

    def add_review_plan_argument(target: argparse.ArgumentParser) -> None:
        target.add_argument(
            "--review-plan-minutes",
            type=int,
            help="Render a Markdown, HTML, or JSON review-session plan for this many maintainer minutes.",
        )

    add_format_argument(parser, default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    repo = sub.add_parser("repo", help="Analyze pull requests in a repository.")
    add_format_argument(repo, default=argparse.SUPPRESS)
    add_config_argument(repo)
    add_now_argument(repo)
    repo.add_argument("repository", help="Repository in owner/name form or a GitHub repository URL.")
    repo.add_argument("--state", default="open", choices=["open", "closed", "all"])
    repo.add_argument("--limit", type=int, default=30)
    repo.add_argument("--label", help="Only include PRs with this label.")
    repo.add_argument("--author", help="Only include PRs by this author.")
    repo.add_argument("--stale-days", type=int, help="Only include PRs quiet for at least N days.")
    repo.add_argument("--updated-since", help="Only include PRs updated on or after this ISO date.")
    repo.add_argument(
        "--action",
        choices=sorted(ACTION_SLUGS),
        help="Only include PRs with this recommended action.",
    )
    repo.add_argument("--min-score", type=int, help="Only include PRs with reviewability >= N.")
    repo.add_argument("--max-risk", type=int, help="Only include PRs with risk <= N.")
    repo.add_argument("--summary-only", action="store_true", help="Print only the queue summary.")
    add_sort_argument(repo)
    add_hydrate_argument(repo)
    add_top_argument(repo)
    add_group_by_argument(repo)
    add_review_plan_argument(repo)

    recommend = sub.add_parser(
        "recommend",
        help="Recommend the next maintainer workflow for a repository queue.",
    )
    add_recommend_format_argument(recommend, default=argparse.SUPPRESS)
    add_config_argument(recommend)
    add_now_argument(recommend)
    recommend.add_argument(
        "repository",
        help="Repository in owner/name form or a GitHub repository URL.",
    )
    recommend.add_argument("--state", default="open", choices=["open", "closed", "all"])
    recommend.add_argument("--limit", type=int, default=30)
    recommend.add_argument("--label", help="Only include PRs with this label.")
    recommend.add_argument("--author", help="Only include PRs by this author.")
    recommend.add_argument("--stale-days", type=int, help="Only include PRs quiet for at least N days.")
    recommend.add_argument(
        "--updated-since",
        help="Only include PRs updated on or after this ISO date.",
    )
    recommend.add_argument(
        "--no-hydrate",
        action="store_true",
        help="Skip full PR detail for a faster but shallower recommendation.",
    )

    pr = sub.add_parser("pr", help="Analyze one pull request.")
    add_format_argument(pr, default=argparse.SUPPRESS)
    add_config_argument(pr)
    add_now_argument(pr)
    pr.add_argument("repository", help="Repository in owner/name form, or a GitHub pull request URL.")
    pr.add_argument("number", nargs="?", help="Pull request number.")
    pr.add_argument(
        "--comment-template",
        action="store_true",
        help="Render a draft maintainer follow-up comment. Does not post it.",
    )

    author = sub.add_parser("author", help="Analyze pull requests by author.")
    add_format_argument(author, default=argparse.SUPPRESS)
    add_config_argument(author)
    add_now_argument(author)
    author.add_argument("username", help="GitHub username.")
    author.add_argument("--state", default="open", choices=["open", "closed"])
    author.add_argument("--limit", type=int, default=50)
    author.add_argument(
        "--action",
        choices=sorted(ACTION_SLUGS),
        help="Only include PRs with this recommended action.",
    )
    author.add_argument("--min-score", type=int, help="Only include PRs with reviewability >= N.")
    author.add_argument("--max-risk", type=int, help="Only include PRs with risk <= N.")
    author.add_argument("--summary-only", action="store_true", help="Print only the queue summary.")
    add_sort_argument(author)
    add_hydrate_argument(author)
    add_top_argument(author)
    add_group_by_argument(author)
    add_review_plan_argument(author)

    from_json = sub.add_parser("from-json", help="Analyze offline JSON fixture data.")
    add_format_argument(from_json, default=argparse.SUPPRESS)
    add_config_argument(from_json)
    add_now_argument(from_json)
    from_json.add_argument("path", help="Path to JSON file, or - for stdin.")
    from_json.add_argument(
        "--source",
        choices=["github", "gitlab", "forgejo", "gitea"],
        default="github",
        help="Input JSON source shape. Default: github.",
    )
    from_json.add_argument("--detail", action="store_true", help="Render a detailed single-PR brief.")
    from_json.add_argument(
        "--action",
        choices=sorted(ACTION_SLUGS),
        help="Only include PRs with this recommended action.",
    )
    from_json.add_argument("--min-score", type=int, help="Only include PRs with reviewability >= N.")
    from_json.add_argument("--max-risk", type=int, help="Only include PRs with risk <= N.")
    from_json.add_argument("--summary-only", action="store_true", help="Print only the queue summary.")
    add_sort_argument(from_json)
    add_top_argument(from_json)
    add_group_by_argument(from_json)
    add_review_plan_argument(from_json)

    compare = sub.add_parser("compare", help="Compare two saved full-queue JSON reports offline.")
    add_recommend_format_argument(compare, default=argparse.SUPPRESS)
    compare.add_argument("before", help="Earlier analyzed queue JSON file (not a raw forge export).")
    compare.add_argument("after", help="Later analyzed queue JSON file (not a summary or review plan).")

    init_action = sub.add_parser(
        "init-action",
        help="Print or write a read-only GitHub Actions triage workflow.",
    )
    init_action.add_argument(
        "--report-format",
        choices=["markdown", "html", "json", "csv"],
        default="markdown",
        help="Report artifact format. Default: markdown.",
    )
    init_action.add_argument(
        "--schedule",
        default="0 8 * * 1-5",
        help='Cron schedule for the report. Default: "0 8 * * 1-5".',
    )
    init_action.add_argument("--limit", type=int, default=50, help="Maximum PRs to scan.")
    init_action.add_argument("--sort", choices=SORT_CHOICES, default="action")
    init_action.add_argument("--top", type=int, help="Only include the first N PRs after sorting.")
    init_action.add_argument(
        "--group-by",
        choices=["action"],
        help="Group Markdown and HTML queue reports by a field in the workflow.",
    )
    init_action.add_argument(
        "--review-plan-minutes",
        type=int,
        help="Render a Markdown, HTML, or JSON review-session plan in the generated workflow.",
    )
    init_action.add_argument("--label", help="Only include PRs with this label in the workflow.")
    init_action.add_argument("--author", help="Only include PRs by this author in the workflow.")
    init_action.add_argument(
        "--stale-days",
        type=int,
        help="Only include PRs quiet for at least N days in the workflow.",
    )
    init_action.add_argument(
        "--updated-since",
        help="Only include PRs updated on or after this ISO date in the workflow.",
    )
    init_action.add_argument(
        "--action",
        choices=sorted(ACTION_SLUGS),
        help="Only include PRs with this recommended action in the workflow.",
    )
    init_action.add_argument(
        "--min-score",
        type=int,
        help="Only include PRs with reviewability >= N in the workflow.",
    )
    init_action.add_argument(
        "--max-risk",
        type=int,
        help="Only include PRs with risk <= N in the workflow.",
    )
    init_action.add_argument(
        "--config",
        help="Add a config JSON path to the generated workflow.",
    )
    init_action.add_argument(
        "--action-ref",
        help=(
            "Action reference to pin in the generated workflow, for example "
            "JackSpiece/maintainer-radar@<commit-sha>. Defaults to the released tag."
        ),
    )
    init_action.add_argument(
        "--no-hydrate",
        action="store_true",
        help="Skip full PR hydration for a faster but shallower workflow.",
    )
    init_action.add_argument(
        "--no-step-summary",
        action="store_true",
        help="Skip publishing a Markdown report or summary to the Actions run summary.",
    )
    init_action.add_argument(
        "--path",
        help="Write the workflow to this path instead of stdout, for example .github/workflows/maintainer-radar.yml.",
    )
    init_action.add_argument(
        "--force",
        action="store_true",
        help="Overwrite --path when it already exists.",
    )

    init_config = sub.add_parser(
        "init-config",
        help="Print or write a Maintainer Radar scoring config.",
    )
    init_config.add_argument(
        "--profile",
        choices=sorted(CONFIG_PROFILES),
        default="balanced",
        help="Config profile to generate. Default: balanced.",
    )
    init_config.add_argument(
        "--path",
        help="Write the config to this path instead of stdout, for example .maintainer-radar.json.",
    )
    init_config.add_argument(
        "--force",
        action="store_true",
        help="Overwrite --path when it already exists.",
    )

    init_repo = sub.add_parser(
        "init-repo",
        help="Write a tuned config and read-only GitHub Actions workflow.",
    )
    init_repo.add_argument(
        "--profile",
        choices=sorted(CONFIG_PROFILES),
        default="balanced",
        help="Config profile to write. Default: balanced.",
    )
    init_repo.add_argument(
        "--config-path",
        default=".maintainer-radar.json",
        help="Config path to write and reference in the workflow.",
    )
    init_repo.add_argument(
        "--workflow-path",
        default=".github/workflows/maintainer-radar.yml",
        help="Workflow path to write.",
    )
    init_repo.add_argument(
        "--report-format",
        choices=["markdown", "html", "json", "csv"],
        default="markdown",
        help="Report artifact format. Default: markdown.",
    )
    init_repo.add_argument(
        "--schedule",
        default="0 8 * * 1-5",
        help='Cron schedule for the report. Default: "0 8 * * 1-5".',
    )
    init_repo.add_argument("--limit", type=int, default=50, help="Maximum PRs to scan.")
    init_repo.add_argument("--sort", choices=SORT_CHOICES, default="action")
    init_repo.add_argument(
        "--group-by",
        choices=["action"],
        default="action",
        help="Group Markdown and HTML reports by a field. Default: action.",
    )
    init_repo.add_argument(
        "--action-ref",
        help=(
            "Action reference to pin in the generated workflow, for example "
            "JackSpiece/maintainer-radar@<commit-sha>. Defaults to the released tag."
        ),
    )
    init_repo.add_argument(
        "--no-hydrate",
        action="store_true",
        help="Skip full PR hydration for a faster but shallower workflow.",
    )
    init_repo.add_argument(
        "--no-step-summary",
        action="store_true",
        help="Skip publishing a Markdown report or summary to the Actions run summary.",
    )
    init_repo.add_argument(
        "--force",
        action="store_true",
        help="Overwrite generated files when they already exist.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "compare":
            if args.format not in {"markdown", "json"}:
                raise ValueError("compare supports --format markdown or json")
            report = compare_snapshots(load_snapshot(args.before), load_snapshot(args.after))
            print(render_comparison(report, args.format), end="")
            return 0

        if args.command == "init-action":
            workflow = render_github_action_workflow(
                report_format=args.report_format,
                schedule=args.schedule,
                limit=args.limit,
                sort=args.sort,
                hydrate=not args.no_hydrate,
                top=args.top,
                group_by=args.group_by,
                review_plan_minutes=args.review_plan_minutes,
                label=args.label,
                author=args.author,
                stale_days=args.stale_days,
                updated_since=args.updated_since,
                action_filter=args.action,
                min_score=args.min_score,
                max_risk=args.max_risk,
                config=args.config,
                step_summary=not args.no_step_summary,
                action_ref=args.action_ref,
            )
            if args.path:
                output_path = Path(args.path)
                _ensure_paths_writable([output_path], force=args.force)
                _write_output_file(output_path, workflow)
                print(f"Wrote {output_path}")
            else:
                print(workflow, end="")
            return 0

        if args.command == "init-config":
            rendered_config = render_config_profile(args.profile)
            if args.path:
                output_path = Path(args.path)
                _ensure_paths_writable([output_path], force=args.force)
                _write_output_file(output_path, rendered_config)
                print(f"Wrote {output_path}")
            else:
                print(rendered_config, end="")
            return 0

        if args.command == "init-repo":
            config_path = Path(args.config_path)
            workflow_path = Path(args.workflow_path)
            _ensure_paths_writable([config_path, workflow_path], force=args.force)
            rendered_config = render_config_profile(args.profile)
            workflow = render_github_action_workflow(
                report_format=args.report_format,
                schedule=args.schedule,
                limit=args.limit,
                sort=args.sort,
                hydrate=not args.no_hydrate,
                group_by=args.group_by,
                config=args.config_path,
                step_summary=not args.no_step_summary,
                action_ref=args.action_ref,
            )
            _write_output_file(config_path, rendered_config)
            _write_output_file(workflow_path, workflow)
            print(f"Wrote {config_path}")
            print(f"Wrote {workflow_path}")
            return 0

        config = load_config(getattr(args, "config", None))
        now = _parse_now(getattr(args, "now", None))
        if args.command == "repo":
            repository = _normalize_repository_arg(args.repository)
            prs = list_repo_prs(repository, state=args.state, limit=args.limit)
            prs = filter_prs(
                prs,
                label=args.label,
                author=args.author,
                stale_days=args.stale_days,
                updated_since=args.updated_since,
                now=now,
            )
            if args.hydrate:
                prs = hydrate_prs(prs, repository=repository, viewer=view_pr)
            analyses = [analyze_pr(pr, config=config, now=now) for pr in prs]
            analyses = filter_analyses(
                analyses,
                action=args.action,
                min_score=args.min_score,
                max_risk=args.max_risk,
            )
            analyses = sort_analyses(analyses, args.sort)
            analyses = limit_analyses(analyses, args.top)
            _emit(
                analyses,
                args.format,
                summary_only=args.summary_only,
                group_by=args.group_by,
                review_plan_minutes=args.review_plan_minutes,
            )
        elif args.command == "recommend":
            repository = _normalize_repository_arg(args.repository)
            prs = list_repo_prs(repository, state=args.state, limit=args.limit)
            prs = filter_prs(
                prs,
                label=args.label,
                author=args.author,
                stale_days=args.stale_days,
                updated_since=args.updated_since,
                now=now,
            )
            if not args.no_hydrate:
                prs = hydrate_prs(prs, repository=repository, viewer=view_pr)
            analyses = [analyze_pr(pr, config=config, now=now) for pr in prs]
            analyses = sort_analyses(analyses, "action")
            _emit_recommendation(analyses, args.format, repository)
        elif args.command == "pr":
            repository, number = _parse_pr_reference(args.repository, args.number)
            pr = view_pr(repository, number)
            analysis = analyze_pr(pr, config=config, now=now)
            if args.comment_template:
                if args.format == "json":
                    print(json.dumps({"comment": render_comment_template(analysis)}, indent=2))
                elif args.format == "csv":
                    print(render_comment_csv(render_comment_template(analysis)), end="")
                elif args.format == "html":
                    print(render_comment_html(render_comment_template(analysis)), end="")
                else:
                    print(render_comment_template(analysis), end="")
            else:
                _emit([analysis], args.format, detail=True)
        elif args.command == "author":
            prs = search_author_prs(args.username, state=args.state, limit=args.limit)
            if args.hydrate:
                prs = hydrate_prs(prs, viewer=view_pr)
            analyses = [analyze_pr(pr, config=config, now=now) for pr in prs]
            analyses = filter_analyses(
                analyses,
                action=args.action,
                min_score=args.min_score,
                max_risk=args.max_risk,
            )
            analyses = sort_analyses(analyses, args.sort)
            analyses = limit_analyses(analyses, args.top)
            _emit(
                analyses,
                args.format,
                summary_only=args.summary_only,
                group_by=args.group_by,
                review_plan_minutes=args.review_plan_minutes,
            )
        elif args.command == "from-json":
            prs = _as_pr_list(_load_json(args.path), source=args.source)
            detail = bool(args.detail and len(prs) == 1)
            analyses = [analyze_pr(pr, config=config, now=now) for pr in prs]
            analyses = filter_analyses(
                analyses,
                action=args.action,
                min_score=args.min_score,
                max_risk=args.max_risk,
            )
            analyses = sort_analyses(analyses, args.sort)
            analyses = limit_analyses(analyses, args.top)
            _emit(
                analyses,
                args.format,
                detail=detail,
                summary_only=args.summary_only,
                group_by=args.group_by,
                review_plan_minutes=args.review_plan_minutes,
            )
        else:
            parser.error("unknown command")
    except (GitHubCliError, OSError, ValueError) as exc:
        print(f"maintainer-radar: {exc}", file=sys.stderr)
        return 2
    return 0
