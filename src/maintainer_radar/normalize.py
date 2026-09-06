from __future__ import annotations

from typing import Any


GITLAB_PIPELINE_CONCLUSIONS = {
    "success": "SUCCESS",
    "failed": "FAILURE",
    "canceled": "CANCELLED",
    "cancelled": "CANCELLED",
    "skipped": "SKIPPED",
}

GITLAB_PENDING_STATUSES = {
    "created",
    "manual",
    "pending",
    "preparing",
    "running",
    "scheduled",
    "waiting_for_resource",
}


FORGEJO_STATUS_CONCLUSIONS = {
    "success": "SUCCESS",
    "successful": "SUCCESS",
    "failure": "FAILURE",
    "failed": "FAILURE",
    "error": "FAILURE",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
    "skipped": "SKIPPED",
}

FORGEJO_PENDING_STATUSES = {
    "created",
    "pending",
    "queued",
    "running",
    "waiting",
    "in_progress",
}


def normalize_items(data: Any, *, source: str) -> list[dict[str, Any]]:
    source = source.lower()
    items = _as_items(data)
    if source == "github":
        return items
    if source == "gitlab":
        return [normalize_gitlab_mr(item) for item in items]
    if source in {"forgejo", "gitea"}:
        return [normalize_forgejo_pr(item) for item in items]
    raise ValueError(f"Unsupported source: {source}")


def _as_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        if any(not isinstance(item, dict) for item in data):
            raise ValueError("Each pull request in the JSON list must be an object")
        return data
    if isinstance(data, dict):
        for key in (
            "items",
            "merge_requests",
            "mergeRequests",
            "pull_requests",
            "pullRequests",
            "pulls",
        ):
            if isinstance(data.get(key), list):
                return _as_items(data[key])
        return [data]
    raise ValueError("JSON input must be an object, a list, or an object with items")


def normalize_gitlab_mr(mr: dict[str, Any]) -> dict[str, Any]:
    author = mr.get("author") or {}
    changes = _changes(mr)
    additions, deletions = _diff_stats(mr, changes)
    labels = _labels(mr.get("labels"))
    comments = _comments(mr)
    pipeline = mr.get("head_pipeline") or mr.get("pipeline") or {}

    normalized: dict[str, Any] = {
        "number": mr.get("iid") or mr.get("number") or mr.get("id"),
        "title": mr.get("title"),
        "url": mr.get("web_url") or mr.get("url"),
        "author": {
            "login": author.get("username") or author.get("name") or mr.get("author_username")
        },
        "updatedAt": mr.get("updated_at") or mr.get("updatedAt"),
        "createdAt": mr.get("created_at") or mr.get("createdAt"),
        "isDraft": bool(mr.get("draft") or mr.get("work_in_progress") or _title_is_draft(mr)),
        "labels": labels,
        "reviewDecision": _review_decision(mr),
        "mergeStateStatus": _gitlab_merge_state_status(mr),
        "mergeable": _gitlab_mergeable(mr),
        "reviewRequests": _gitlab_review_requests(mr),
        "statusCheckRollup": [_pipeline_check(pipeline)] if pipeline else [],
        "comments": comments,
        "latestReviews": _latest_reviews(mr),
        "files": _files(changes),
        "additions": additions,
        "deletions": deletions,
        "changedFiles": _changed_files(mr, changes),
    }
    # Only expose a body when the export actually carried one, so shallow
    # GitLab exports score like shallow GitHub scans instead of being
    # penalized for a missing test plan.
    if "description" in mr or "body" in mr:
        normalized["body"] = mr.get("description") or mr.get("body") or ""
    return normalized


def normalize_forgejo_pr(pr: dict[str, Any]) -> dict[str, Any]:
    user = pr.get("user") or pr.get("poster") or pr.get("author") or {}
    files = _forgejo_files(pr)
    additions, deletions = _forgejo_diff_stats(pr, files)
    reviews = _forgejo_reviews(pr)

    normalized: dict[str, Any] = {
        "number": pr.get("number") or pr.get("id") or pr.get("index"),
        "title": pr.get("title"),
        "url": pr.get("html_url") or pr.get("url"),
        "author": {"login": _forgejo_author_login(user)},
        "updatedAt": pr.get("updated_at") or pr.get("updatedAt"),
        "createdAt": pr.get("created_at") or pr.get("createdAt"),
        "isDraft": bool(pr.get("draft") or _title_is_draft(pr)),
        "labels": _labels(pr.get("labels")),
        "reviewDecision": _forgejo_review_decision(reviews),
        "mergeStateStatus": _forgejo_merge_state_status(pr),
        "mergeable": _forgejo_mergeable(pr),
        "reviewRequests": _forgejo_review_requests(pr),
        "statusCheckRollup": _forgejo_checks(pr),
        "comments": _forgejo_comments(pr),
        "latestReviews": reviews,
        "files": files,
        "additions": additions,
        "deletions": deletions,
        "changedFiles": _forgejo_changed_files(pr, files),
    }
    # Match the GitHub shallow-scan shape: only include a body key when the
    # export included one.
    if "body" in pr:
        normalized["body"] = pr.get("body") or ""
    return normalized


def _title_is_draft(mr: dict[str, Any]) -> bool:
    title = str(mr.get("title") or "").lower().strip()
    return title.startswith("draft:") or title.startswith("wip:")


def _labels(value: Any) -> list[dict[str, str]]:
    if not value:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        parts = [str(item.get("name") if isinstance(item, dict) else item).strip() for item in value]
    else:
        parts = []
    return [{"name": part} for part in parts if part]


def _forgejo_author_login(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("login") or value.get("username") or value.get("full_name")
    return str(value) if value else None


def _pipeline_check(pipeline: dict[str, Any]) -> dict[str, str | None]:
    status = str(pipeline.get("status") or "").lower()
    if status in GITLAB_PENDING_STATUSES:
        return {
            "name": pipeline.get("ref") or "pipeline",
            "status": status.upper(),
            "conclusion": None,
        }
    return {
        "name": pipeline.get("ref") or "pipeline",
        "status": "COMPLETED" if status else "",
        "conclusion": GITLAB_PIPELINE_CONCLUSIONS.get(status, status.upper() or None),
    }


def _forgejo_checks(pr: dict[str, Any]) -> list[dict[str, str | None]]:
    checks: list[dict[str, str | None]] = []
    for key in ("statusCheckRollup", "statuses", "checks"):
        value = pr.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    checks.append(_forgejo_check(item))
    status = pr.get("status")
    if isinstance(status, dict):
        checks.append(_forgejo_check(status))
    return checks


def _forgejo_check(item: dict[str, Any]) -> dict[str, str | None]:
    name = item.get("name") or item.get("context") or "status"
    if item.get("conclusion") is not None:
        conclusion = str(item.get("conclusion") or "").upper() or None
        return {
            "name": name,
            "status": str(item.get("status") or "COMPLETED").upper(),
            "conclusion": conclusion,
        }

    state = str(item.get("status") or item.get("state") or "").lower()
    if state in FORGEJO_PENDING_STATUSES:
        return {
            "name": name,
            "status": state.upper(),
            "conclusion": None,
        }
    return {
        "name": name,
        "status": "COMPLETED" if state else "",
        "conclusion": FORGEJO_STATUS_CONCLUSIONS.get(state, state.upper() or None),
    }


def _review_decision(mr: dict[str, Any]) -> str:
    if mr.get("blocking_discussions_resolved") is False:
        return "CHANGES_REQUESTED"
    if mr.get("approved") or mr.get("approved_by"):
        return "APPROVED"
    if str(mr.get("detailed_merge_status") or "").lower() in {
        "discussions_not_resolved",
        "ci_must_pass",
        "not_approved",
    }:
        return "CHANGES_REQUESTED"
    return "REVIEW_REQUIRED"


def _gitlab_merge_state_status(mr: dict[str, Any]) -> str:
    if mr.get("has_conflicts"):
        return "DIRTY"
    status = str(mr.get("detailed_merge_status") or mr.get("merge_status") or "").lower()
    if status in {"mergeable", "can_be_merged"}:
        return "CLEAN"
    if status in {"need_rebase"}:
        return "BEHIND"
    if status in {"discussions_not_resolved", "ci_must_pass", "not_approved", "blocked_status"}:
        return "BLOCKED"
    if status in {"cannot_be_merged", "conflict"}:
        return "DIRTY"
    return status.upper() if status else ""


def _gitlab_mergeable(mr: dict[str, Any]) -> str:
    if mr.get("has_conflicts"):
        return "CONFLICTING"
    status = str(mr.get("merge_status") or mr.get("detailed_merge_status") or "").lower()
    if status in {"can_be_merged", "mergeable"}:
        return "MERGEABLE"
    if status in {"cannot_be_merged", "conflict"}:
        return "CONFLICTING"
    return ""


def _gitlab_review_requests(mr: dict[str, Any]) -> list[Any]:
    for key in ("reviewers", "review_requests", "requested_reviewers"):
        value = mr.get(key)
        if isinstance(value, list):
            return value
    return []


def _forgejo_review_decision(reviews: list[dict[str, str]]) -> str:
    approved = False
    for review in reviews:
        state = str(review.get("state") or "").upper().replace("-", "_").replace(" ", "_")
        if state in {"CHANGES_REQUESTED", "REQUEST_CHANGES", "REQUESTED_CHANGES"}:
            return "CHANGES_REQUESTED"
        if state == "APPROVED":
            approved = True
    return "APPROVED" if approved else "REVIEW_REQUIRED"


def _forgejo_merge_state_status(pr: dict[str, Any]) -> str:
    value = pr.get("mergeStateStatus") or pr.get("merge_state_status") or pr.get("mergeable_state")
    if value:
        return str(value).upper().replace("-", "_").replace(" ", "_")
    if pr.get("has_conflicts"):
        return "DIRTY"
    if pr.get("mergeable") is True:
        return "CLEAN"
    if pr.get("mergeable") is False:
        return "DIRTY"
    return ""


def _forgejo_mergeable(pr: dict[str, Any]) -> str:
    value = pr.get("mergeable")
    if isinstance(value, bool):
        return "MERGEABLE" if value else "CONFLICTING"
    return str(value or "").upper().replace("-", "_").replace(" ", "_")


def _forgejo_review_requests(pr: dict[str, Any]) -> list[Any]:
    for key in ("reviewRequests", "review_requests", "requested_reviewers", "requestedReviewers"):
        value = pr.get(key)
        if isinstance(value, list):
            return value
    return []


def _changes(mr: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("changes", "diffs"):
        value = mr.get(key)
        if isinstance(value, list):
            return value
    return []


def _files(changes: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for change in changes:
        path = change.get("new_path") or change.get("old_path") or change.get("path")
        if path:
            result.append({"path": str(path)})
    return result


def _forgejo_files(pr: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("files", "changedFiles", "affected_files"):
        value = pr.get(key)
        if isinstance(value, list):
            return _forgejo_file_paths(value)
        if isinstance(value, dict) and isinstance(value.get("files"), list):
            return _forgejo_file_paths(value["files"])
    return []


def _forgejo_file_paths(items: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            path = item.get("filename") or item.get("path") or item.get("name")
        else:
            path = item
        if path:
            file_info: dict[str, Any] = {"path": str(path)}
            if isinstance(item, dict):
                for key in ("additions", "deletions"):
                    if item.get(key) is not None:
                        file_info[key] = item[key]
            result.append(file_info)
    return result


def _changed_files(mr: dict[str, Any], changes: list[dict[str, Any]]) -> int:
    for key in ("changes_count", "changed_files", "changedFiles"):
        value = mr.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return len(changes)


def _forgejo_changed_files(pr: dict[str, Any], files: list[dict[str, Any]]) -> int:
    for key in ("changed_files", "changedFiles", "files_changed"):
        value = pr.get(key)
        if isinstance(value, list):
            return len(value)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return len(files)


def _diff_stats(mr: dict[str, Any], changes: list[dict[str, Any]]) -> tuple[int, int]:
    stats = mr.get("stats") or {}
    additions = _int_or_none(stats.get("additions") or mr.get("additions"))
    deletions = _int_or_none(stats.get("deletions") or mr.get("deletions"))
    if additions is not None or deletions is not None:
        return additions or 0, deletions or 0

    added = removed = 0
    for change in changes:
        diff = str(change.get("diff") or "")
        for line in diff.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
    return added, removed


def _forgejo_diff_stats(pr: dict[str, Any], files: list[dict[str, Any]]) -> tuple[int, int]:
    additions = _int_or_none(pr.get("additions"))
    deletions = _int_or_none(pr.get("deletions"))
    if additions is not None or deletions is not None:
        return additions or 0, deletions or 0

    added = removed = 0
    for file_info in files:
        added += _int_or_none(file_info.get("additions")) or 0
        removed += _int_or_none(file_info.get("deletions")) or 0
    return added, removed


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _comments(mr: dict[str, Any]) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    for key in ("comments", "notes"):
        value = mr.get(key)
        if isinstance(value, list):
            for note in value:
                body = note.get("body") if isinstance(note, dict) else str(note)
                if body:
                    comments.append({"body": str(body)})
    discussions = mr.get("discussions")
    if isinstance(discussions, list):
        for discussion in discussions:
            notes = discussion.get("notes") if isinstance(discussion, dict) else None
            if not isinstance(notes, list):
                continue
            for note in notes:
                body = note.get("body") if isinstance(note, dict) else str(note)
                if body:
                    comments.append({"body": str(body)})
    return comments


def _forgejo_comments(pr: dict[str, Any]) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    for key in ("comments", "issue_comments", "review_comments"):
        value = pr.get(key)
        if isinstance(value, list):
            comments.extend(_comment_bodies(value))
    timeline = pr.get("timeline")
    if isinstance(timeline, list):
        comments.extend(_comment_bodies(timeline))
    return comments


def _comment_bodies(items: list[Any]) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    for item in items:
        body = item.get("body") if isinstance(item, dict) else str(item)
        if body:
            comments.append({"body": str(body)})
    return comments


def _latest_reviews(mr: dict[str, Any]) -> list[dict[str, str]]:
    if mr.get("blocking_discussions_resolved") is False:
        return [{"state": "CHANGES_REQUESTED", "body": "Blocking discussions are unresolved."}]
    if mr.get("approved") or mr.get("approved_by"):
        return [{"state": "APPROVED", "body": ""}]
    return []


def _forgejo_reviews(pr: dict[str, Any]) -> list[dict[str, str]]:
    reviews: list[dict[str, str]] = []
    for key in ("reviews", "latestReviews"):
        value = pr.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            state = item.get("state") or item.get("type")
            body = item.get("body") or item.get("content") or item.get("message") or ""
            if state or body:
                reviews.append({"state": str(state or ""), "body": str(body)})
    return reviews
