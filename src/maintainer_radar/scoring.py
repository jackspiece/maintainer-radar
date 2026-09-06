from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from .config import DEFAULT_CONFIG

CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}

TEST_HINTS = (
    "/test/",
    "/tests/",
    "__tests__",
    ".spec.",
    ".test.",
    "_test.",
    "test_",
)

DOC_HINTS = (
    ".md",
    ".mdx",
    "/docs/",
    "docs/",
    "readme",
    "changelog",
    "license",
)

GENERATED_HINTS = (
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "cargo.lock",
    "go.sum",
    "dist/",
    "build/",
    "vendor/",
    "generated",
)

BLOCKER_RE = re.compile(
    r"\b("
    r"not working|doesn'?t work|fails?|failure|broken|blocked|blocker|"
    r"changes requested|please fix|needs? changes?|regression|"
    r"cannot merge|won'?t merge|missing tests?|please test"
    r")\b",
    re.IGNORECASE,
)

LABEL_BLOCKER_RE = re.compile(
    r"\b("
    r"blocked|blocker|do not merge|dnm|"
    r"changes requested|needs? changes?|"
    r"needs? tests?|missing tests?|"
    r"waiting on author|needs? author|author action|author follow up|"
    r"waiting on dependency|waiting for dependency|needs? dependency|"
    r"dependency blocked|blocked upstream|blocked by upstream|upstream blocked"
    r")\b",
    re.IGNORECASE,
)

# Test-plan evidence must appear as an explicit section, label, or testing
# statement at the start of a line. Bare mentions of words like "test" or
# "ci" inside prose no longer count, so PR bodies cannot game the signal
# with sentences like "this should make the ci faster".
TEST_PLAN_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*|[-*]\s+|>\s*)?(?:\*\*|__)?\s*(?:"
    r"(?:test plan|testing (?:done|notes|steps|strategy)|"
    r"tests? (?:added|updated|written|performed|run)|"
    r"how (?:i|we|this was) tested|manual test(?:ing)?|"
    r"validation(?: steps)?|verification(?: steps)?|"
    r"repro(?:duction)?(?: steps)?)"
    r"\s*(?:\*\*|__)?\s*(?:[:\-\u2013]|\.\s*$|$)"
    r"|(?:tested|verified)\s+(?:locally|manually|end[- ]to[- ]end|with|via|using|by|on|in)\b"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class CheckSummary:
    passed: int = 0
    failed: int = 0
    pending: int = 0
    skipped: int = 0
    total: int = 0


@dataclass(frozen=True)
class FileSummary:
    code_files: int = 0
    doc_files: int = 0
    test_files: int = 0
    generated_files: int = 0
    total_files: int = 0


def parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def days_since(value: str | None, now: datetime | None = None) -> int | None:
    dt = parse_github_datetime(value)
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def summarize_checks(items: list[dict[str, Any]] | None) -> CheckSummary:
    passed = failed = pending = skipped = 0
    for item in items or []:
        status = str(item.get("status") or "").upper()
        # gh rollups contain both CheckRun and legacy StatusContext objects.
        conclusion = str(item.get("conclusion") or item.get("state") or "").upper()
        if status and status != "COMPLETED":
            pending += 1
        elif conclusion in {"SUCCESS", "NEUTRAL"}:
            passed += 1
        elif conclusion == "SKIPPED":
            skipped += 1
        elif conclusion in {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}:
            failed += 1
        else:
            pending += 1
    return CheckSummary(
        passed=passed,
        failed=failed,
        pending=pending,
        skipped=skipped,
        total=passed + failed + pending + skipped,
    )


def summarize_files(
    files: list[dict[str, Any]] | None,
    config: dict[str, Any] | None = None,
) -> FileSummary:
    config = config or DEFAULT_CONFIG
    test_hints = (*TEST_HINTS, *config.get("test_hints", []))
    doc_hints = (*DOC_HINTS, *config.get("doc_hints", []))
    generated_hints = (*GENERATED_HINTS, *config.get("generated_hints", []))
    code_files = doc_files = test_files = generated_files = 0
    for file_info in files or []:
        path = str(file_info.get("path") or file_info.get("filename") or "").lower()
        if not path:
            continue
        # Categories are mutually exclusive so one file can never count as
        # both a test file and a code file (e.g. tests/test_parser.py).
        # Priority: generated, then test, then doc, then code.
        if any(hint in path for hint in generated_hints):
            generated_files += 1
        elif any(hint in path for hint in test_hints):
            test_files += 1
        elif any(path.endswith(hint) or hint in path for hint in doc_hints):
            doc_files += 1
        elif any(path.endswith(ext) for ext in CODE_EXTENSIONS):
            code_files += 1
    return FileSummary(
        code_files=code_files,
        doc_files=doc_files,
        test_files=test_files,
        generated_files=generated_files,
        total_files=len(files or []),
    )


def _body(pr: dict[str, Any]) -> str:
    return str(pr.get("body") or "")


def _actor_login(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("login") or value.get("username") or "").lower()
    return str(value or "").lower()


def _comments_and_reviews(pr: dict[str, Any]) -> list[str]:
    """Comment and review bodies, excluding the PR author's own text.

    Review states are intentionally not scanned as text: a CHANGES_REQUESTED
    state is already scored through reviewDecision, and matching the state
    string here would double-count the same condition.
    """
    pr_author = _actor_login(pr.get("author"))
    text: list[str] = []
    for comment in pr.get("comments") or []:
        if not isinstance(comment, dict):
            continue
        commenter = _actor_login(comment.get("author") or comment.get("user"))
        if pr_author and commenter and commenter == pr_author:
            continue
        text.append(str(comment.get("body") or ""))
    for review in pr.get("latestReviews") or pr.get("reviews") or []:
        if not isinstance(review, dict):
            continue
        reviewer = _actor_login(review.get("author") or review.get("user"))
        if pr_author and reviewer and reviewer == pr_author:
            continue
        text.append(str(review.get("body") or ""))
    return text


def _has_blocker(pr: dict[str, Any]) -> bool:
    return any(BLOCKER_RE.search(text) for text in _comments_and_reviews(pr))


def _has_test_plan(pr: dict[str, Any]) -> bool:
    body = _body(pr)
    return bool(body and TEST_PLAN_RE.search(body))


def _label_names(pr: dict[str, Any]) -> list[str]:
    labels = pr.get("labels") or []
    result: list[str] = []
    for label in labels:
        if isinstance(label, str):
            result.append(label)
        else:
            result.append(str(label.get("name") or ""))
    return [name for name in result if name]


def _normalize_label_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[-_:/]+", " ", value.lower())).strip()


def _has_blocking_label(pr: dict[str, Any]) -> bool:
    return any(LABEL_BLOCKER_RE.search(_normalize_label_name(name)) for name in _label_names(pr))


def _merge_state_status(pr: dict[str, Any]) -> str:
    value = pr.get("mergeStateStatus") or pr.get("merge_state_status") or pr.get("mergeable_state")
    return str(value or "").upper().replace("-", "_").replace(" ", "_")


def _mergeable_state(pr: dict[str, Any]) -> str:
    value = pr.get("mergeable")
    if isinstance(value, bool):
        return "MERGEABLE" if value else "CONFLICTING"
    return str(value or "").upper().replace("-", "_").replace(" ", "_")


def _review_request_count(pr: dict[str, Any]) -> int:
    count = 0
    for key in ("reviewRequests", "review_requests", "requested_reviewers", "requestedReviewers"):
        value = pr.get(key)
        if isinstance(value, list):
            count += len(value)
        elif isinstance(value, dict):
            for nested_key in ("nodes", "items"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    count += len(nested)
                    break
    for key in ("requested_teams", "requestedTeams"):
        value = pr.get(key)
        if isinstance(value, list):
            count += len(value)
    return count


def _record_score(
    breakdown: list[dict[str, Any]],
    label: str,
    risk_delta: int,
    *,
    kind: str,
) -> None:
    breakdown.append(
        {
            "label": label,
            "risk_delta": risk_delta,
            "kind": kind,
        }
    )


def analyze_pr(
    pr: dict[str, Any],
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic maintainer triage metadata for one PR dictionary."""
    config = config or DEFAULT_CONFIG
    checks = summarize_checks(pr.get("statusCheckRollup"))
    files = summarize_files(pr.get("files"), config=config)
    additions = int(pr.get("additions") or 0)
    deletions = int(pr.get("deletions") or 0)
    changed_files = int(pr.get("changedFiles") or files.total_files or 0)
    files_complete = files.total_files >= changed_files
    total_diff = additions + deletions
    review_decision = str(pr.get("reviewDecision") or "").upper()
    merge_state_status = _merge_state_status(pr)
    mergeable = _mergeable_state(pr)
    review_request_count = _review_request_count(pr)
    is_draft = bool(pr.get("isDraft") or pr.get("draft"))
    stale_days = days_since(pr.get("updatedAt"), now)
    has_blocker = _has_blocker(pr)
    has_blocking_label = _has_blocking_label(pr)
    has_test_plan = _has_test_plan(pr)
    has_body = "body" in pr

    risk = 0
    signals: list[str] = []
    flags: list[str] = []
    score_breakdown: list[dict[str, Any]] = []

    if is_draft:
        risk += 25
        flags.append("draft PR")
        _record_score(score_breakdown, "draft PR", 25, kind="flag")

    if total_diff > config["very_large_diff_lines"] or changed_files > config["very_large_file_count"]:
        risk += 30
        flags.append("very large diff")
        _record_score(score_breakdown, "very large diff", 30, kind="flag")
    elif total_diff > config["large_diff_lines"] or changed_files > config["large_file_count"]:
        risk += 15
        flags.append("large diff")
        _record_score(score_breakdown, "large diff", 15, kind="flag")

    if checks.total == 0:
        risk += 8
        flags.append("no visible checks")
        _record_score(score_breakdown, "no visible checks", 8, kind="flag")
    elif checks.failed:
        risk += 30
        flags.append("CI failing")
        _record_score(score_breakdown, "CI failing", 30, kind="flag")
    elif checks.pending:
        risk += 10
        flags.append("CI pending")
        _record_score(score_breakdown, "CI pending", 10, kind="flag")
    elif checks.passed:
        risk -= 8
        signals.append("CI passed")
        _record_score(score_breakdown, "CI passed", -8, kind="signal")

    if review_decision == "APPROVED":
        risk -= 10
        signals.append("approved")
        _record_score(score_breakdown, "approved", -10, kind="signal")
    elif review_decision == "CHANGES_REQUESTED":
        risk += 25
        flags.append("changes requested")
        _record_score(score_breakdown, "changes requested", 25, kind="flag")
    elif review_decision == "REVIEW_REQUIRED":
        signals.append("review required")

    if mergeable == "CONFLICTING" or merge_state_status == "DIRTY":
        risk += 20
        flags.append("merge conflicts")
        _record_score(score_breakdown, "merge conflicts", 20, kind="flag")
    elif merge_state_status == "BEHIND":
        risk += 8
        flags.append("branch behind base")
        _record_score(score_breakdown, "branch behind base", 8, kind="flag")
    elif merge_state_status == "BLOCKED":
        risk += 6
        flags.append("merge blocked by repo rules")
        _record_score(score_breakdown, "merge blocked by repo rules", 6, kind="flag")
    elif merge_state_status == "UNSTABLE" and checks.total == 0:
        risk += 12
        flags.append("merge checks unstable")
        _record_score(score_breakdown, "merge checks unstable", 12, kind="flag")
    elif merge_state_status == "CLEAN" or mergeable == "MERGEABLE":
        signals.append("mergeable")

    if review_request_count:
        label = (
            "review requested"
            if review_request_count == 1
            else f"{review_request_count} reviews requested"
        )
        signals.append(label)

    if stale_days is not None:
        if stale_days >= config["stale_days"]:
            risk += 15
            label = f"stale {stale_days} days"
            flags.append(label)
            _record_score(score_breakdown, label, 15, kind="flag")
        elif stale_days >= config["quiet_days"]:
            risk += 8
            label = f"quiet {stale_days} days"
            flags.append(label)
            _record_score(score_breakdown, label, 8, kind="flag")

    if has_blocker:
        risk += 25
        flags.append("maintainer blocker language")
        _record_score(score_breakdown, "maintainer blocker language", 25, kind="flag")

    if has_blocking_label:
        risk += 18
        flags.append("maintainer blocking label")
        _record_score(score_breakdown, "maintainer blocking label", 18, kind="flag")

    if has_body and not has_test_plan and files.code_files:
        risk += 8
        flags.append("no test plan found")
        _record_score(score_breakdown, "no test plan found", 8, kind="flag")
    elif has_test_plan:
        signals.append("test plan present")

    if "files" in pr and not files_complete:
        flags.append("incomplete file list")

    if files_complete and files.code_files and not files.test_files:
        risk += 10
        flags.append("code changed without tests")
        _record_score(score_breakdown, "code changed without tests", 10, kind="flag")
    elif files.test_files:
        signals.append("tests changed")

    if files.generated_files:
        generated_risk = min(12, files.generated_files * 3)
        risk += generated_risk
        flags.append("generated or lockfile changes")
        _record_score(score_breakdown, "generated or lockfile changes", generated_risk, kind="flag")

    if files_complete and files.doc_files and files.doc_files == files.total_files:
        risk -= 6
        signals.append("docs-only shape")
        _record_score(score_breakdown, "docs-only shape", -6, kind="signal")

    raw_risk = risk
    risk = max(0, min(100, risk))
    reviewability = 100 - risk
    action = choose_action(
        reviewability=reviewability,
        is_draft=is_draft,
        checks=checks,
        has_blocker=has_blocker,
        has_blocking_label=has_blocking_label,
        merge_conflict="merge conflicts" in flags,
        branch_behind="branch behind base" in flags,
        total_diff=total_diff,
        changed_files=changed_files,
        review_decision=review_decision,
        config=config,
    )
    next_step = recommend_next_step(
        action=action,
        flags=flags,
        signals=signals,
    )

    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "author": (pr.get("author") or {}).get("login") if isinstance(pr.get("author"), dict) else pr.get("author"),
        "labels": _label_names(pr),
        "risk": risk,
        "reviewability": reviewability,
        "action": action,
        "next_step": next_step,
        "flags": flags,
        "signals": signals,
        "score_breakdown": score_breakdown,
        "raw_risk": raw_risk,
        "checks": checks.__dict__,
        "files": files.__dict__,
        "merge_state_status": merge_state_status,
        "mergeable": mergeable,
        "review_requests": review_request_count,
        "stale_days": stale_days,
        "additions": additions,
        "deletions": deletions,
        "changed_files": changed_files,
    }


def choose_action(
    *,
    reviewability: int,
    is_draft: bool,
    checks: CheckSummary,
    has_blocker: bool,
    has_blocking_label: bool,
    total_diff: int,
    changed_files: int,
    review_decision: str,
    merge_conflict: bool = False,
    branch_behind: bool = False,
    config: dict[str, Any] | None = None,
) -> str:
    config = config or DEFAULT_CONFIG
    if is_draft:
        return "wait for author"
    if checks.failed:
        return "ask for CI fix"
    if checks.pending:
        return "wait for CI"
    if merge_conflict or branch_behind:
        return "needs author follow-up"
    if review_decision == "CHANGES_REQUESTED" or has_blocker or has_blocking_label:
        return "needs author follow-up"
    if total_diff > config["very_large_diff_lines"] or changed_files > config["very_large_file_count"]:
        return "request smaller PR"
    if reviewability >= 75:
        return "review now"
    if reviewability >= 55:
        return "review with caution"
    return "needs triage"


def recommend_next_step(
    *,
    action: str,
    flags: list[str] | None = None,
    signals: list[str] | None = None,
) -> str:
    flags = flags or []
    signals = signals or []
    if action == "wait for author":
        return "Wait for the author to mark the PR ready for review."
    if action == "ask for CI fix":
        return "Ask the author to get failing checks green before deeper review."
    if action == "wait for CI":
        return "Wait for checks to finish before spending review time."
    if action == "needs author follow-up":
        if "merge conflicts" in flags:
            return "Ask the author to resolve merge conflicts before another review pass."
        if "branch behind base" in flags:
            return "Ask the author to update the branch with the base branch before review."
        if "maintainer blocker language" in flags or "maintainer blocking label" in flags:
            return "Ask the author to respond to unresolved maintainer feedback."
        return "Ask the author to address requested changes before another review pass."
    if action == "request smaller PR":
        return "Ask for a smaller split or a clear scope explanation."
    if action == "review now":
        if "docs-only shape" in signals:
            return "Review now as a likely low-risk docs-only change."
        return "Review now while the PR appears small, active, and low risk."
    if action == "review with caution":
        return "Review, but inspect the risk flags before approving."
    return "Triage manually before assigning reviewer time."
