from __future__ import annotations

import csv
from html import escape
from io import StringIO
import json
import re
from typing import Any


CSV_FIELDS = [
    "number",
    "title",
    "author",
    "action",
    "next_step",
    "reviewability",
    "risk",
    "stale_days",
    "changed_files",
    "additions",
    "deletions",
    "labels",
    "signals",
    "flags",
    "score_breakdown",
    "url",
]

PLAN_ACTION_PRIORITY = {
    "review now": 0,
    "review with caution": 1,
    "needs author follow-up": 2,
    "ask for CI fix": 3,
    "request smaller PR": 4,
    "needs triage": 5,
    "wait for CI": 6,
    "wait for author": 7,
}

FOLLOW_UP_ACTIONS = {
    "ask for CI fix",
    "needs author follow-up",
    "request smaller PR",
    "wait for author",
}

DEFAULT_SESSION_MINUTES = 60

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --text: #111827;
      --muted: #475569;
      --line: #d8dee9;
      --panel: #ffffff;
      --blue: #2563eb;
      --green: #047857;
      --amber: #b45309;
      --red: #b91c1c;
      --purple: #7c3aed;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 32px auto;
    }}
    header {{
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: clamp(28px, 5vw, 42px);
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 16px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 22px 0;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
    }}
    .metric strong {{
      display: block;
      font-size: 24px;
      line-height: 1.1;
    }}
    .metric span {{
      color: var(--muted);
      font-size: 13px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 11px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #eef2f7;
      color: #243041;
      font-size: 13px;
      text-transform: uppercase;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    a {{
      color: var(--blue);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .score {{
      font-variant-numeric: tabular-nums;
      text-align: right;
      white-space: nowrap;
    }}
    .action {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      background: #e5e7eb;
      color: #1f2937;
      white-space: nowrap;
    }}
    .action-review-now {{
      background: #d1fae5;
      color: var(--green);
    }}
    .action-ask-for-ci-fix,
    .action-needs-author-follow-up,
    .action-wait-for-author {{
      background: #fee2e2;
      color: var(--red);
    }}
    .action-wait-for-ci,
    .action-review-with-caution,
    .action-request-smaller-pr {{
      background: #fef3c7;
      color: var(--amber);
    }}
    .signals {{
      color: var(--muted);
    }}
    .impact {{
      color: var(--purple);
      font-size: 14px;
    }}
    .empty {{
      color: var(--muted);
      text-align: center;
    }}
    .action-group {{
      margin-top: 22px;
    }}
    .action-group h2 {{
      margin: 0 0 8px;
      font-size: 18px;
    }}
    .action-group h2 span {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 500;
    }}
    .plan-section {{
      margin-top: 22px;
    }}
    .plan-section h2 {{
      margin: 0 0 8px;
      font-size: 18px;
    }}
    .notice {{
      border: 1px solid #fbbf24;
      border-radius: 8px;
      background: #fffbeb;
      color: #92400e;
      padding: 10px 12px;
      margin: 0 0 18px;
    }}
    pre {{
      white-space: pre-wrap;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 14px;
      overflow-x: auto;
    }}
    details {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 10px 12px;
      margin: 8px 0;
    }}
    summary {{
      cursor: pointer;
      font-weight: 700;
    }}
    details pre {{
      margin-bottom: 0;
    }}
    .draft-tools {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 10px 0;
    }}
    .copy-draft {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #eef2f7;
      color: var(--text);
      cursor: pointer;
      font: inherit;
      font-weight: 700;
      padding: 6px 10px;
    }}
    .copy-draft:hover {{
      background: #e2e8f0;
    }}
    .copy-state {{
      color: var(--muted);
      font-size: 13px;
    }}
    footer {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{title}</h1>
      <p class="subtitle">{subtitle}</p>
    </header>
    {summary}
    {table}
    <footer>Scores route maintainer attention. They do not replace review.</footer>
  </main>
  <script>
    (() => {{
      function fallbackCopy(text) {{
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.left = "-9999px";
        document.body.appendChild(area);
        area.select();
        try {{
          return document.execCommand("copy");
        }} finally {{
          area.remove();
        }}
      }}

      async function copyText(text) {{
        if (navigator.clipboard && window.isSecureContext) {{
          await navigator.clipboard.writeText(text);
          return true;
        }}
        return fallbackCopy(text);
      }}

      function setState(button, text) {{
        const state = button.parentElement.querySelector("[data-copy-state]");
        if (!state) {{
          return;
        }}
        state.textContent = text;
        setTimeout(() => {{
          if (state.textContent === text) {{
            state.textContent = "";
          }}
        }}, 2000);
      }}

      document.addEventListener("click", async (event) => {{
        const target = event.target;
        if (!(target instanceof Element)) {{
          return;
        }}
        const button = target.closest("[data-copy-target]");
        if (!(button instanceof HTMLButtonElement)) {{
          return;
        }}
        const source = document.getElementById(button.dataset.copyTarget || "");
        if (!source) {{
          return;
        }}
        try {{
          const copied = await copyText(source.textContent || "");
          setState(button, copied ? "Copied" : "Select and copy");
        }} catch (error) {{
          setState(button, "Copy failed");
        }}
      }});
    }})();
  </script>
</body>
</html>
"""


def summarize_report(analyses: list[dict[str, Any]]) -> dict[str, int | str]:
    actions = [str(item.get("action") or "") for item in analyses]
    scores = [int(item.get("reviewability") or 0) for item in analyses]
    stale_count = sum(1 for item in analyses if (item.get("stale_days") or 0) >= 7)
    ci_blocked = sum(1 for item in analyses if "CI failing" in (item.get("flags") or []))
    ci_pending = sum(1 for item in analyses if "CI pending" in (item.get("flags") or []))
    merge_conflicts = sum(1 for item in analyses if "merge conflicts" in (item.get("flags") or []))
    branch_behind = sum(1 for item in analyses if "branch behind base" in (item.get("flags") or []))
    merge_gated = sum(
        1
        for item in analyses
        if "merge blocked by repo rules" in (item.get("flags") or [])
        or "merge checks unstable" in (item.get("flags") or [])
    )
    review_requested = sum(1 for item in analyses if int(item.get("review_requests") or 0) > 0)
    maintainer_blocked = sum(
        1
        for item in analyses
        if "maintainer blocker language" in (item.get("flags") or [])
        or "maintainer blocking label" in (item.get("flags") or [])
    )
    summary: dict[str, int | str] = {
        "total": len(analyses),
        "review_now": actions.count("review now"),
        "author_follow_up": actions.count("needs author follow-up"),
        "ci_blocked": ci_blocked,
        "ci_pending": ci_pending,
        "merge_conflicts": merge_conflicts,
        "branch_behind": branch_behind,
        "merge_gated": merge_gated,
        "review_requested": review_requested,
        "maintainer_blocked": maintainer_blocked,
        "large_or_triage": actions.count("request smaller PR") + actions.count("needs triage"),
        "stale": stale_count,
        "average_score": round(sum(scores) / len(scores)) if scores else 0,
    }
    summary.update(_next_session_summary(analyses, DEFAULT_SESSION_MINUTES))
    summary["queue_headline"] = _queue_headline(summary)
    attention_level, attention_reason = _attention_signal(summary)
    summary["attention_level"] = attention_level
    summary["attention_reason"] = attention_reason
    workflow_mode, workflow_recommendation = _workflow_recommendation(summary)
    summary["workflow_mode"] = workflow_mode
    summary["workflow_recommendation"] = workflow_recommendation
    return summary


def _next_session_summary(analyses: list[dict[str, Any]], budget_minutes: int) -> dict[str, int | str]:
    plan = build_review_plan(analyses, budget_minutes)
    quick_unblocks = sum(1 for item in analyses if estimate_review_minutes(item) == 5)
    watch_only = sum(1 for item in analyses if estimate_review_minutes(item) == 0)
    summary: dict[str, int | str] = {
        "next_session_prs": len(plan["planned"]),
        "next_session_minutes": plan["planned_minutes"],
        "next_session_deferred": len(plan["deferred"]),
        "quick_unblocks": quick_unblocks,
        "watch_only": watch_only,
    }
    summary["next_session_brief"] = _next_session_brief(summary, budget_minutes)
    return summary


def _next_session_brief(summary: dict[str, int | str], budget_minutes: int) -> str:
    planned = _int_value(summary.get("next_session_prs"))
    minutes = _int_value(summary.get("next_session_minutes"))
    deferred = _int_value(summary.get("next_session_deferred"))
    quick_unblocks = _int_value(summary.get("quick_unblocks"))
    watch_only = _int_value(summary.get("watch_only"))

    if not planned and not deferred and not quick_unblocks and not watch_only:
        return f"Next {budget_minutes} minutes: no matching PRs need maintainer time."

    if not planned:
        return (
            f"Next {budget_minutes} minutes: no active review work fits yet; "
            f"keep {_pr_count(watch_only)} on watch."
        )

    parts = [f"handle {_pr_count(planned)} in about {minutes} minutes"]
    if quick_unblocks:
        label = "quick unblock" if quick_unblocks == 1 else "quick unblocks"
        parts.append(f"{quick_unblocks} {label}")
    if deferred:
        parts.append(f"{_pr_count(deferred)} deferred by the session budget")
    if watch_only:
        parts.append(f"{_pr_count(watch_only)} watch-only")
    return f"Next {budget_minutes} minutes: {'; '.join(parts)}."


def _queue_headline(summary: dict[str, int | str]) -> str:
    total = _int_value(summary.get("total"))
    if total == 0:
        return "No pull requests matched this scan."

    ci_total = _int_value(summary.get("ci_blocked")) + _int_value(summary.get("ci_pending"))
    parts: list[str] = []
    if _int_value(summary.get("review_now")):
        parts.append(f"{_int_value(summary.get('review_now'))} ready for review")
    if _int_value(summary.get("author_follow_up")):
        parts.append(_needs_phrase(_int_value(summary.get("author_follow_up")), "author follow-up"))
    if ci_total:
        parts.append(f"{ci_total} blocked or waiting on CI")
    if _int_value(summary.get("merge_conflicts")):
        count = _int_value(summary.get("merge_conflicts"))
        parts.append(f"{count} with merge {'conflict' if count == 1 else 'conflicts'}")
    if _int_value(summary.get("branch_behind")):
        parts.append(f"{_int_value(summary.get('branch_behind'))} behind base")
    if _int_value(summary.get("merge_gated")):
        count = _int_value(summary.get("merge_gated"))
        parts.append(f"{count} blocked by merge gates")
    if _int_value(summary.get("maintainer_blocked")):
        count = _int_value(summary.get("maintainer_blocked"))
        verb = "has" if count == 1 else "have"
        blocker = "blocker" if count == 1 else "blockers"
        parts.append(f"{_pr_count(count)} {verb} unresolved maintainer {blocker}")

    if not parts:
        parts.append("no urgent blocker signals")
    return f"{_pr_count(total)} scanned: {'; '.join(parts)}."


def _pr_count(count: int) -> str:
    return f"{count} {'PR' if count == 1 else 'PRs'}"


def _needs_phrase(count: int, noun: str) -> str:
    return f"{count} {'needs' if count == 1 else 'need'} {noun}"


def _attention_signal(summary: dict[str, int | str]) -> tuple[str, str]:
    if _int_value(summary.get("total")) == 0:
        return ("quiet", "No pull requests matched this scan.")
    if _int_value(summary.get("maintainer_blocked")):
        return (
            "blocked",
            _attention_reason(
                _int_value(summary.get("maintainer_blocked")),
                "has unresolved maintainer blocker",
                "have unresolved maintainer blockers",
            ),
        )
    if _int_value(summary.get("merge_conflicts")):
        return (
            "blocked",
            _attention_reason(
                _int_value(summary.get("merge_conflicts")),
                "has merge conflicts",
                "have merge conflicts",
            ),
        )
    if _int_value(summary.get("ci_blocked")):
        return (
            "blocked",
            _attention_reason(
                _int_value(summary.get("ci_blocked")),
                "has failing CI",
                "have failing CI",
            ),
        )
    if _int_value(summary.get("merge_gated")):
        return (
            "blocked",
            _attention_reason(
                _int_value(summary.get("merge_gated")),
                "is blocked by repository merge gates",
                "are blocked by repository merge gates",
            ),
        )
    if _int_value(summary.get("author_follow_up")):
        return (
            "follow-up",
            _attention_reason(
                _int_value(summary.get("author_follow_up")),
                "needs author follow-up",
                "need author follow-up",
            ),
        )
    if _int_value(summary.get("branch_behind")):
        return (
            "follow-up",
            _attention_reason(
                _int_value(summary.get("branch_behind")),
                "is behind base",
                "are behind base",
            ),
        )
    if _int_value(summary.get("ci_pending")):
        return (
            "follow-up",
            _attention_reason(
                _int_value(summary.get("ci_pending")),
                "is waiting on CI",
                "are waiting on CI",
            ),
        )
    if _int_value(summary.get("review_now")):
        return (
            "review",
            _attention_reason(
                _int_value(summary.get("review_now")),
                "is ready for review",
                "are ready for review",
            ),
        )
    if _int_value(summary.get("large_or_triage")):
        return (
            "triage",
            _attention_reason(
                _int_value(summary.get("large_or_triage")),
                "needs triage or scope reduction",
                "need triage or scope reduction",
            ),
        )
    if _int_value(summary.get("stale")):
        return (
            "follow-up",
            _attention_reason(
                _int_value(summary.get("stale")),
                "is stale",
                "are stale",
            ),
        )
    if _int_value(summary.get("review_requested")):
        return (
            "review",
            _attention_reason(
                _int_value(summary.get("review_requested")),
                "has requested reviewers",
                "have requested reviewers",
            ),
        )
    return ("quiet", "No urgent maintainer attention signal was found.")


def _attention_reason(count: int, singular: str, plural: str) -> str:
    phrase = singular if count == 1 else plural
    return f"{_pr_count(count)} {phrase}."


def _workflow_recommendation(summary: dict[str, int | str]) -> tuple[str, str]:
    if _int_value(summary.get("total")) == 0:
        return ("quiet", "No matching PRs. Keep the scheduled scan quiet.")

    if (
        _int_value(summary.get("maintainer_blocked"))
        or _int_value(summary.get("merge_conflicts"))
        or _int_value(summary.get("ci_blocked"))
        or _int_value(summary.get("merge_gated"))
    ):
        return (
            "blocker-sweep",
            "Clear maintainer blockers, merge conflicts, failing CI, or merge gates before assigning review time.",
        )

    if _int_value(summary.get("review_now")):
        return ("review-sprint", "Start a focused review block with the ready PRs.")

    if _int_value(summary.get("author_follow_up")) or _int_value(summary.get("branch_behind")):
        return (
            "author-follow-up",
            "Send author follow-ups for waiting authors or branches behind base.",
        )

    if _int_value(summary.get("large_or_triage")):
        return ("triage-pass", "Classify or split large and unclear PRs before review.")

    if _int_value(summary.get("ci_pending")):
        return ("ci-watch", "Wait for pending checks before spending review time.")

    if _int_value(summary.get("stale")):
        return ("stale-sweep", "Run a stale follow-up pass before assigning review time.")

    if _int_value(summary.get("review_requested")):
        return ("review-sprint", "Handle requested reviews that have no stronger blocker signal.")

    return ("quiet", "No urgent maintainer workflow was found.")


def render_recommendation_markdown(
    analyses: list[dict[str, Any]],
    repository: str,
) -> str:
    summary = summarize_report(analyses)
    commands = build_recommendation_commands(repository, summary)
    lines = [
        "## Maintainer Radar Recommendation",
        "",
        str(summary["queue_headline"]),
        "",
        f"- Attention: `{summary['attention_level']}`",
        f"- Workflow: `{summary['workflow_mode']}`",
        f"- Why: {summary['attention_reason']}",
        f"- Recommendation: {summary['workflow_recommendation']}",
        f"- Next session: {summary['next_session_brief']}",
        "",
        "### Next Commands",
        "",
        f"- Focused report: `{commands['focused_report']}`",
        f"- Review plan: `{commands['review_plan']}`",
        f"- Scheduled workflow: `{commands['scheduled_workflow']}`",
        "",
        "Maintainer Radar is read-only. It does not approve, reject, merge, label, or comment.",
    ]
    return "\n".join(lines) + "\n"


def render_recommendation_json(
    analyses: list[dict[str, Any]],
    repository: str,
) -> str:
    summary = summarize_report(analyses)
    return json.dumps(
        {
            "repository": repository,
            "queue_headline": summary["queue_headline"],
            "attention_level": summary["attention_level"],
            "attention_reason": summary["attention_reason"],
            "workflow_mode": summary["workflow_mode"],
            "workflow_recommendation": summary["workflow_recommendation"],
            "next_session_brief": summary["next_session_brief"],
            "commands": build_recommendation_commands(repository, summary),
        },
        indent=2,
    )


def build_recommendation_commands(
    repository: str,
    summary: dict[str, int | str],
) -> dict[str, str]:
    base = f"maintainer-radar repo {repository} --hydrate"
    mode = str(summary.get("workflow_mode") or "")

    if mode == "review-sprint":
        focused = f"{base} --action review-now --min-score 80 --sort score --top 10"
    elif mode == "stale-sweep":
        focused = f"{base} --stale-days 7 --sort stale --group-by action"
    elif mode == "author-follow-up":
        focused = f"{base} --sort stale --group-by action"
    elif mode == "triage-pass":
        focused = f"{base} --sort risk --group-by action --top 15"
    elif mode == "quiet":
        focused = f"{base} --summary-only"
    else:
        focused = f"{base} --sort action --group-by action"

    return {
        "focused_report": focused,
        "review_plan": f"{base} --sort action --review-plan-minutes 60",
        "scheduled_workflow": (
            "maintainer-radar init-action --sort action --group-by action "
            "--review-plan-minutes 60 --path .github/workflows/maintainer-radar.yml"
        ),
    }


def render_summary_markdown(
    analyses: list[dict[str, Any]],
    title: str = "Maintainer Radar Summary",
) -> str:
    summary = summarize_report(analyses)
    lines = [
        f"## {title}",
        "",
        str(summary["queue_headline"]),
        "",
        f"- Attention level: {summary['attention_level']}",
        f"- Attention reason: {summary['attention_reason']}",
        f"- Workflow mode: {summary['workflow_mode']}",
        f"- Workflow recommendation: {summary['workflow_recommendation']}",
        f"- Next session: {summary['next_session_brief']}",
        f"- PRs scanned: {summary['total']}",
        f"- Review now: {summary['review_now']}",
        f"- Needs author follow-up: {summary['author_follow_up']}",
        f"- CI blocked or pending: {int(summary['ci_blocked']) + int(summary['ci_pending'])}",
        f"- Merge conflicts: {summary['merge_conflicts']}",
        f"- Branch behind base: {summary['branch_behind']}",
        f"- Merge gated: {summary['merge_gated']}",
        f"- Review requested: {summary['review_requested']}",
        f"- Maintainer blocked: {summary['maintainer_blocked']}",
        f"- Large or needs triage: {summary['large_or_triage']}",
        f"- Stale 7+ days: {summary['stale']}",
        f"- Quick unblocks: {summary['quick_unblocks']}",
        f"- Watch only: {summary['watch_only']}",
        f"- Next-session PRs: {summary['next_session_prs']}",
        f"- Next-session active time: {summary['next_session_minutes']} minutes",
        f"- Next-session deferred: {summary['next_session_deferred']}",
        f"- Average reviewability: {summary['average_score']}/100",
        "",
    ]
    return "\n".join(lines)


def render_review_plan_markdown(
    analyses: list[dict[str, Any]],
    budget_minutes: int,
    title: str = "Maintainer Radar Review Plan",
) -> str:
    plan = build_review_plan(analyses, budget_minutes)
    summary = summarize_report(analyses)
    lines = [
        f"## {title}",
        "",
        f"- Time budget: {plan['budget_minutes']} minutes",
        f"- Planned PRs: {len(plan['planned'])}",
        f"- Estimated active time: {plan['planned_minutes']} minutes",
        f"- Left for interrupts: {plan['remaining_minutes']} minutes",
        f"- Queue scanned: {summary['total']} PRs",
        f"- Review now: {summary['review_now']}",
        f"- Maintainer blocked: {summary['maintainer_blocked']}",
        f"- Workflow mode: {summary['workflow_mode']}",
        f"- Workflow recommendation: {summary['workflow_recommendation']}",
        "",
    ]
    if plan["over_budget_minutes"]:
        lines.append(
            f"First planned item exceeds the budget by {plan['over_budget_minutes']} minutes."
        )
        lines.append("")

    if plan["planned"]:
        lines.extend(
            [
                "| Order | PR | Action | Est. | Next Step | Why |",
                "| ---: | --- | --- | ---: | --- | --- |",
            ]
        )
        for index, entry in enumerate(plan["planned"], 1):
            item = entry["item"]
            label = _markdown_pr_label(item)
            lines.append(
                f"| {index} | {label} | {markdown_cell(item.get('action'))} | "
                f"{entry['estimated_minutes']}m | {markdown_cell(_next_step(item))} | "
                f"{markdown_cell(entry['reason'])} |"
            )
    else:
        lines.append("No active maintainer work was found for this budget.")

    if plan["deferred"]:
        lines.extend(["", "### Deferred by Budget", ""])
        for entry in plan["deferred"][:5]:
            item = entry["item"]
            lines.append(
                f"- {_markdown_pr_label(item)}: {entry['estimated_minutes']}m, "
                f"{markdown_cell(item.get('action'))}"
            )

    if plan["waiting"]:
        lines.extend(["", "### Watch Only", ""])
        for entry in plan["waiting"][:5]:
            item = entry["item"]
            lines.append(f"- {_markdown_pr_label(item)}: {markdown_cell(_next_step(item))}")

    follow_ups = _review_plan_follow_up_entries(plan)
    if follow_ups:
        lines.extend(["", "### Draft Follow-ups", ""])
        for entry in follow_ups:
            item = entry["item"]
            lines.extend(
                [
                    f"#### {_markdown_pr_label(item)}",
                    "",
                    "```markdown",
                    _draft_follow_up_comment(item),
                    "```",
                    "",
                ]
            )

    lines.extend(["", "Generated by Maintainer Radar. Use the plan to spend attention, not to skip review."])
    return "\n".join(lines) + "\n"


def render_review_plan_html(
    analyses: list[dict[str, Any]],
    budget_minutes: int,
    title: str = "Maintainer Radar Review Plan",
) -> str:
    plan = build_review_plan(analyses, budget_minutes)
    summary = summarize_report(analyses)
    summary_html = _render_plan_html_summary(plan, summary)
    plan_html = _render_plan_html_sections(plan)
    return HTML_TEMPLATE.format(
        title=escape(title),
        subtitle="Deterministic maintainer review plan.",
        summary=summary_html,
        table=plan_html,
    )


def render_review_plan_json(analyses: list[dict[str, Any]], budget_minutes: int) -> str:
    plan = build_review_plan(analyses, budget_minutes)
    payload = {
        "budget_minutes": plan["budget_minutes"],
        "planned_minutes": plan["planned_minutes"],
        "remaining_minutes": plan["remaining_minutes"],
        "over_budget_minutes": plan["over_budget_minutes"],
        "queue_summary": summarize_report(analyses),
        "planned": [_review_plan_json_entry(entry) for entry in plan["planned"]],
        "deferred": [_review_plan_json_entry(entry) for entry in plan["deferred"]],
        "watch_only": [_review_plan_json_entry(entry) for entry in plan["waiting"]],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_csv(analyses: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in analyses:
        writer.writerow(
            {
                "number": item.get("number"),
                "title": item.get("title") or "",
                "author": item.get("author") or "",
                "action": item.get("action") or "",
                "next_step": _next_step(item),
                "reviewability": item.get("reviewability", ""),
                "risk": item.get("risk", ""),
                "stale_days": item.get("stale_days", ""),
                "changed_files": item.get("changed_files", ""),
                "additions": item.get("additions", ""),
                "deletions": item.get("deletions", ""),
                "labels": _join_csv_value(item.get("labels")),
                "signals": _join_csv_value(item.get("signals")),
                "flags": _join_csv_value(item.get("flags")),
                "score_breakdown": _join_score_breakdown(item.get("score_breakdown")),
                "url": item.get("url") or "",
            }
        )
    return output.getvalue()


def render_summary_csv(analyses: list[dict[str, Any]]) -> str:
    summary = summarize_report(analyses)
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(summary), lineterminator="\n")
    writer.writeheader()
    writer.writerow(summary)
    return output.getvalue()


def render_comment_csv(comment: str) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["comment"], lineterminator="\n")
    writer.writeheader()
    writer.writerow({"comment": comment})
    return output.getvalue()


def render_html(
    analyses: list[dict[str, Any]],
    title: str = "Maintainer Radar Report",
    *,
    summary_only: bool = False,
    group_by: str | None = None,
) -> str:
    safe_title = escape(title)
    summary_html = _render_html_summary(analyses)
    table_html = "" if summary_only else _render_html_table(analyses, group_by=group_by)
    return HTML_TEMPLATE.format(
        title=safe_title,
        subtitle="Deterministic maintainer triage report.",
        summary=summary_html,
        table=table_html,
    )


def render_comment_html(comment: str) -> str:
    title = "Maintainer Radar Comment Draft"
    body = f"<pre>{escape(comment)}</pre>"
    return HTML_TEMPLATE.format(
        title=title,
        subtitle="Draft maintainer follow-up comment.",
        summary="",
        table=body,
    )


def _join_csv_value(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item)
    return str(value)


def _next_step(item: dict[str, Any]) -> str:
    return str(item.get("next_step") or "Triage manually before assigning reviewer time.")


def markdown_cell(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|").strip()


def _markdown_pr_label(item: dict[str, Any]) -> str:
    number = item.get("number")
    title_text = markdown_cell(item.get("title") or "Untitled")
    label = f"#{number} {title_text}" if number else title_text
    url = str(item.get("url") or "")
    if url.startswith(("https://", "http://")):
        return f"[{label}]({url})"
    return label


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def estimate_review_minutes(item: dict[str, Any]) -> int:
    action = str(item.get("action") or "needs triage")
    changed_files = _int_value(item.get("changed_files"))
    total_diff = _int_value(item.get("additions")) + _int_value(item.get("deletions"))
    signals = item.get("signals") or []

    if action in {"wait for CI", "wait for author"}:
        return 0
    if action in {"ask for CI fix", "needs author follow-up", "request smaller PR"}:
        return 5
    if action == "needs triage":
        return 8

    if "docs-only shape" in signals:
        base = 6
    elif total_diff > 500 or changed_files > 10:
        base = 25
    elif total_diff > 150 or changed_files > 5:
        base = 18
    else:
        base = 12

    if action == "review with caution":
        base += 8
    return base


def build_review_plan(analyses: list[dict[str, Any]], budget_minutes: int) -> dict[str, Any]:
    if budget_minutes < 1:
        raise ValueError("--review-plan-minutes must be 1 or greater")

    candidates = sorted(
        analyses,
        key=lambda item: (
            PLAN_ACTION_PRIORITY.get(str(item.get("action") or ""), 99),
            estimate_review_minutes(item),
            -_int_value(item.get("reviewability")),
            _int_value(item.get("number")),
        ),
    )
    planned: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    used = 0

    for item in candidates:
        minutes = estimate_review_minutes(item)
        entry = {
            "item": item,
            "estimated_minutes": minutes,
            "reason": _plan_reason(item),
        }
        if minutes == 0:
            waiting.append(entry)
            continue
        if used + minutes <= budget_minutes or not planned:
            planned.append(entry)
            used += minutes
        else:
            deferred.append(entry)

    return {
        "budget_minutes": budget_minutes,
        "planned_minutes": used,
        "remaining_minutes": max(0, budget_minutes - used),
        "over_budget_minutes": max(0, used - budget_minutes),
        "planned": planned,
        "deferred": deferred,
        "waiting": waiting,
    }


def summarize_review_plan(analyses: list[dict[str, Any]], budget_minutes: int) -> dict[str, int]:
    plan = build_review_plan(analyses, budget_minutes)
    return {
        "plan_budget_minutes": plan["budget_minutes"],
        "planned_prs": len(plan["planned"]),
        "planned_minutes": plan["planned_minutes"],
        "remaining_minutes": plan["remaining_minutes"],
        "over_budget_minutes": plan["over_budget_minutes"],
        "deferred_prs": len(plan["deferred"]),
        "watch_only_prs": len(plan["waiting"]),
    }


def _render_plan_html_summary(plan: dict[str, Any], summary: dict[str, int | str]) -> str:
    metrics = [
        ("Time budget", f"{plan['budget_minutes']} minutes"),
        ("Planned PRs", len(plan["planned"])),
        ("Active time", f"{plan['planned_minutes']} minutes"),
        ("Open time", f"{plan['remaining_minutes']} minutes"),
        ("Queue scanned", summary["total"]),
        ("Review now", summary["review_now"]),
        ("Merge conflicts", summary["merge_conflicts"]),
        ("Branch behind", summary["branch_behind"]),
        ("Merge gated", summary["merge_gated"]),
        ("Maintainer blocked", summary["maintainer_blocked"]),
    ]
    items = "\n".join(
        f'<div class="metric"><strong>{escape(str(value))}</strong><span>{escape(label)}</span></div>'
        for label, value in metrics
    )
    notice = ""
    if plan["over_budget_minutes"]:
        notice = (
            '<p class="notice">'
            f"First planned item exceeds the budget by {escape(str(plan['over_budget_minutes']))} minutes."
            "</p>"
        )
    workflow = (
        '<p class="notice">'
        f"<strong>{escape(str(summary['workflow_mode']))}</strong>: "
        f"{escape(str(summary['workflow_recommendation']))}"
        "</p>"
    )
    return f'{notice}{workflow}<section class="metrics">{items}</section>'


def _render_plan_html_sections(plan: dict[str, Any]) -> str:
    sections: list[str] = []
    if plan["planned"]:
        rows = "\n".join(
            _render_plan_html_row(str(index), entry)
            for index, entry in enumerate(plan["planned"], 1)
        )
        sections.append(_render_plan_html_section("Planned Review Work", rows))
    else:
        sections.append(
            '<section class="plan-section"><h2>Planned Review Work</h2>'
            '<p class="empty">No active maintainer work was found for this budget.</p></section>'
        )

    if plan["deferred"]:
        rows = "\n".join(
            _render_plan_html_row("defer", entry) for entry in plan["deferred"][:5]
        )
        sections.append(_render_plan_html_section("Deferred by Budget", rows))

    if plan["waiting"]:
        rows = "\n".join(
            _render_plan_html_row("watch", entry) for entry in plan["waiting"][:5]
        )
        sections.append(_render_plan_html_section("Watch Only", rows))

    follow_ups = _review_plan_follow_up_entries(plan)
    if follow_ups:
        items = "\n".join(
            _render_plan_html_follow_up(entry, index)
            for index, entry in enumerate(follow_ups, 1)
        )
        sections.append(f'<section class="plan-section"><h2>Draft Follow-ups</h2>{items}</section>')

    return "\n".join(sections)


def _render_plan_html_section(title: str, rows: str) -> str:
    return (
        '<section class="plan-section">'
        f"<h2>{escape(title)}</h2>"
        "<table>"
        "<thead><tr>"
        "<th>Order</th><th>PR</th><th>Action</th><th>Est.</th><th>Next step</th><th>Why</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        "</section>"
    )


def _render_plan_html_row(order: str, entry: dict[str, Any]) -> str:
    item = entry["item"]
    minutes = int(entry["estimated_minutes"] or 0)
    estimate = f"{minutes}m" if minutes else "watch"
    action = str(item.get("action") or "needs triage")
    return (
        "<tr>"
        f'<td class="score">{escape(order)}</td>'
        f"<td>{_html_pr_label(item)}</td>"
        f'<td><span class="action {_action_class(action)}">{escape(action)}</span></td>'
        f'<td class="score">{escape(estimate)}</td>'
        f"<td>{escape(_next_step(item))}</td>"
        f"<td>{escape(str(entry.get('reason') or 'no notable signals'))}</td>"
        "</tr>"
    )


def _html_pr_label(item: dict[str, Any]) -> str:
    number = item.get("number")
    title_text = str(item.get("title") or "Untitled")
    label = f"#{number} {title_text}" if number else title_text
    url = _safe_url(item.get("url"))
    if url:
        return f'<a href="{url}">{escape(label)}</a>'
    return escape(label)


def _review_plan_json_entry(entry: dict[str, Any]) -> dict[str, Any]:
    item = entry["item"]
    return {
        "number": item.get("number"),
        "title": item.get("title") or "Untitled",
        "url": item.get("url") or "",
        "action": item.get("action") or "needs triage",
        "next_step": _next_step(item),
        "estimated_minutes": int(entry.get("estimated_minutes") or 0),
        "reason": entry.get("reason") or "no notable signals",
        "reviewability": _int_value(item.get("reviewability")),
        "risk": _int_value(item.get("risk")),
        "signals": [str(value) for value in item.get("signals") or [] if value],
        "flags": [str(value) for value in item.get("flags") or [] if value],
        "draft_follow_up_comment": _draft_follow_up_comment(item),
    }


def _review_plan_follow_up_entries(
    plan: dict[str, Any],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for section in ("planned", "deferred", "waiting"):
        for entry in plan[section]:
            item = entry["item"]
            if _draft_follow_up_comment(item):
                entries.append(entry)
            if len(entries) >= limit:
                return entries
    return entries


def _draft_follow_up_comment(item: dict[str, Any]) -> str:
    action = str(item.get("action") or "")
    if action not in FOLLOW_UP_ACTIONS:
        return ""
    return render_comment_template(item).rstrip()


def _render_plan_html_follow_up(entry: dict[str, Any], index: int) -> str:
    item = entry["item"]
    comment = _draft_follow_up_comment(item)
    copy_id = f"draft-follow-up-{index}"
    return (
        "<details>"
        f"<summary>{_html_pr_label(item)}</summary>"
        '<div class="draft-tools">'
        f'<button class="copy-draft" type="button" data-copy-target="{copy_id}">Copy Draft</button>'
        '<span class="copy-state" data-copy-state aria-live="polite"></span>'
        "</div>"
        f'<pre id="{copy_id}">{escape(comment)}</pre>'
        "</details>"
    )


def _plan_reason(item: dict[str, Any]) -> str:
    flags = [str(value) for value in item.get("flags") or [] if value]
    signals = [str(value) for value in item.get("signals") or [] if value]
    visible = flags[:2] or signals[:2]
    return ", ".join(visible) if visible else "no notable signals"


def _format_risk_delta(value: Any) -> str:
    try:
        delta = int(value)
    except (TypeError, ValueError):
        return "0"
    return f"+{delta}" if delta > 0 else str(delta)


def _join_score_breakdown(value: Any) -> str:
    if not value:
        return ""
    items: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        if not label:
            continue
        delta = _format_risk_delta(entry.get("risk_delta"))
        items.append(f"{label} ({delta} risk)")
    return "; ".join(items)


def _render_html_summary(analyses: list[dict[str, Any]]) -> str:
    summary = summarize_report(analyses)
    metrics = [
        ("PRs scanned", summary["total"]),
        ("Next-session PRs", summary["next_session_prs"]),
        ("Next-session time", f"{summary['next_session_minutes']} minutes"),
        ("Quick unblocks", summary["quick_unblocks"]),
        ("Watch only", summary["watch_only"]),
        ("Review now", summary["review_now"]),
        ("Author follow-up", summary["author_follow_up"]),
        ("CI blocked", int(summary["ci_blocked"]) + int(summary["ci_pending"])),
        ("Merge conflicts", summary["merge_conflicts"]),
        ("Branch behind", summary["branch_behind"]),
        ("Merge gated", summary["merge_gated"]),
        ("Review requested", summary["review_requested"]),
        ("Maintainer blocked", summary["maintainer_blocked"]),
        ("Large or triage", summary["large_or_triage"]),
        ("Stale 7+ days", summary["stale"]),
        ("Average score", f"{summary['average_score']}/100"),
    ]
    items = "\n".join(
        f'<div class="metric"><strong>{escape(str(value))}</strong><span>{escape(label)}</span></div>'
        for label, value in metrics
    )
    workflow = (
        '<p class="notice">'
        f"<strong>{escape(str(summary['workflow_mode']))}</strong>: "
        f"{escape(str(summary['workflow_recommendation']))}"
        "</p>"
    )
    session = f'<p class="notice">{escape(str(summary["next_session_brief"]))}</p>'
    return f'{workflow}{session}<section class="metrics">{items}</section>'


def _render_html_table(analyses: list[dict[str, Any]], *, group_by: str | None = None) -> str:
    if not analyses:
        return '<p class="empty">No pull requests matched this report.</p>'

    if group_by == "action":
        groups = []
        for action, items in _group_by_action(analyses):
            heading = escape(action)
            count = len(items)
            label = "PR" if count == 1 else "PRs"
            rows = "\n".join(_render_html_row(item) for item in items)
            groups.append(
                "<section class=\"action-group\">"
                f"<h2>{heading} <span>{count} {label}</span></h2>"
                f"{_render_html_table_shell(rows)}"
                "</section>"
            )
        return "\n".join(groups)

    rows = "\n".join(_render_html_row(item) for item in analyses)
    return _render_html_table_shell(rows)


def _render_html_table_shell(rows: str) -> str:
    return (
        "<table>"
        "<thead><tr>"
        "<th>PR</th><th>Action</th><th>Next step</th><th>Score</th><th>Risk impact</th><th>Signals</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def _render_html_row(item: dict[str, Any]) -> str:
    number = item.get("number")
    title_text = str(item.get("title") or "Untitled")
    label = f"#{number} {title_text}" if number else title_text
    url = _safe_url(item.get("url"))
    if url:
        pr_html = f'<a href="{url}">{escape(label)}</a>'
    else:
        pr_html = escape(label)

    action = str(item.get("action") or "needs triage")
    signals = item.get("signals") or []
    flags = item.get("flags") or []
    impact_text = _join_score_breakdown(item.get("score_breakdown")) or "no score changes"
    signal_text = _join_csv_value([*signals, *flags]) or "no notable signals"
    return (
        "<tr>"
        f"<td>{pr_html}</td>"
        f'<td><span class="action {_action_class(action)}">{escape(action)}</span></td>'
        f"<td>{escape(_next_step(item))}</td>"
        f'<td class="score">{escape(str(item.get("reviewability") or 0))}</td>'
        f'<td class="impact">{escape(impact_text)}</td>'
        f'<td class="signals">{escape(signal_text)}</td>'
        "</tr>"
    )


def _safe_url(value: Any) -> str | None:
    url = str(value or "")
    if not url.startswith(("https://", "http://")):
        return None
    return escape(url, quote=True)


def _action_class(action: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", action.lower()).strip("-")
    return f"action-{slug}" if slug else "action-default"


def render_markdown(
    analyses: list[dict[str, Any]],
    title: str = "Maintainer Radar Report",
    *,
    group_by: str | None = None,
) -> str:
    lines = [
        render_summary_markdown(analyses, title=title).rstrip(),
        "",
    ]
    if group_by == "action" and analyses:
        for action, items in _group_by_action(analyses):
            count = len(items)
            label = "PR" if count == 1 else "PRs"
            lines.extend([f"### {action} ({count} {label})", ""])
            _append_markdown_table(lines, items)
            lines.append("")
    else:
        _append_markdown_table(lines, analyses)

    lines.extend(
        [
            "",
            "Scores are deterministic heuristics. They route maintainer attention, not merge authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def _append_markdown_table(lines: list[str], analyses: list[dict[str, Any]]) -> None:
    lines.extend(
        [
            "| PR | Action | Next Step | Score | Risk Impact | Signals |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for item in analyses:
        lines.append(_render_markdown_row(item))


def _render_markdown_row(item: dict[str, Any]) -> str:
    number = item.get("number")
    title_text = item.get("title") or "Untitled"
    url = item.get("url")
    label = f"#{number} {title_text}" if number else title_text
    if url:
        label = f"[{label}]({url})"
    signals = item.get("signals") or []
    flags = item.get("flags") or []
    impact_text = _join_score_breakdown(item.get("score_breakdown")) or "no score changes"
    signal_text = ", ".join([*signals, *flags]) or "no notable signals"
    return (
        f"| {label} | {item.get('action')} | {_next_step(item)} | "
        f"{item.get('reviewability')} | {impact_text} | {signal_text} |"
    )


def _group_by_action(analyses: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    by_action: dict[str, list[dict[str, Any]]] = {}
    for item in analyses:
        action = str(item.get("action") or "needs triage")
        if action not in by_action:
            by_action[action] = []
            groups.append((action, by_action[action]))
        by_action[action].append(item)
    return groups


def render_detail(item: dict[str, Any]) -> str:
    lines = [
        f"## PR #{item.get('number')} Maintainer Brief",
        "",
        f"- **Title:** {item.get('title')}",
        f"- **Action:** {item.get('action')}",
        f"- **Next step:** {_next_step(item)}",
        f"- **Reviewability:** {item.get('reviewability')}/100",
        f"- **Risk:** {item.get('risk')}/100",
    ]
    raw_risk = item.get("raw_risk")
    if raw_risk is not None and raw_risk != item.get("risk"):
        lines.append(f"- **Raw risk before clamp:** {raw_risk}")
    if item.get("url"):
        lines.append(f"- **URL:** {item.get('url')}")
    if item.get("author"):
        lines.append(f"- **Author:** {item.get('author')}")
    if item.get("stale_days") is not None:
        lines.append(f"- **Last activity:** {item.get('stale_days')} days ago")

    checks = item.get("checks") or {}
    files = item.get("files") or {}
    lines.extend(
        [
            "",
            "### Checks",
            "",
            f"- Passed: {checks.get('passed', 0)}",
            f"- Failed: {checks.get('failed', 0)}",
            f"- Pending: {checks.get('pending', 0)}",
            f"- Skipped: {checks.get('skipped', 0)}",
            "",
            "### Diff Shape",
            "",
            f"- Additions: {item.get('additions', 0)}",
            f"- Deletions: {item.get('deletions', 0)}",
            f"- Changed files: {item.get('changed_files', 0)}",
            f"- Code files: {files.get('code_files', 0)}",
            f"- Test files: {files.get('test_files', 0)}",
            f"- Docs files: {files.get('doc_files', 0)}",
        ]
    )

    lines.extend(["", "### Score Breakdown", ""])
    score_breakdown = item.get("score_breakdown") or []
    if score_breakdown:
        for entry in score_breakdown:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label") or "").strip()
            if label:
                delta = _format_risk_delta(entry.get("risk_delta"))
                lines.append(f"- {label}: {delta} risk")
    else:
        lines.append("- No score adjustments detected")

    flags = item.get("flags") or []
    signals = item.get("signals") or []
    lines.extend(["", "### Signals", ""])
    if signals:
        lines.extend(f"- {signal}" for signal in signals)
    else:
        lines.append("- No positive signals detected")

    lines.extend(["", "### Flags", ""])
    if flags:
        lines.extend(f"- {flag}" for flag in flags)
    else:
        lines.append("- No risk flags detected")

    return "\n".join(lines) + "\n"


def render_comment_template(item: dict[str, Any]) -> str:
    flags = [str(flag) for flag in item.get("flags") or []]

    requests: list[str] = []
    if any("CI failing" in flag for flag in flags):
        requests.append("Get CI passing or explain why the failing check is unrelated.")
    if any("CI pending" in flag for flag in flags):
        requests.append("Wait for CI to finish before requesting another review.")
    if any("no test plan" in flag for flag in flags):
        requests.append("Add a short validation or test plan to the PR body.")
    if any("code changed without tests" in flag for flag in flags):
        requests.append("Add regression coverage, or explain why tests are not practical for this change.")
    if any("maintainer blocker language" in flag for flag in flags):
        requests.append("Respond to the unresolved maintainer feedback before the next review pass.")
    if any("merge conflicts" in flag for flag in flags):
        requests.append("Resolve merge conflicts before requesting another review pass.")
    if any("branch behind base" in flag for flag in flags):
        requests.append("Update the branch with the base branch, then rerun checks.")
    if any("large diff" in flag or "very large diff" in flag for flag in flags):
        requests.append("Consider splitting the PR or explaining why the current scope needs to stay together.")
    if any(flag.startswith("stale ") or flag.startswith("quiet ") for flag in flags):
        requests.append("Rebase or leave a short status update so reviewers know the PR is still active.")
    if not requests:
        requests.append("Keep CI green and leave any extra context that would make review easier.")

    lines = [
        "Thanks for the PR.",
        "",
        "Before the next review, could you please:",
    ]
    lines.append("")
    lines.extend(f"- {request}" for request in requests)
    lines.extend(
        [
            "",
            "_Generated as a draft with Maintainer Radar. Please edit before posting._",
            "",
        ]
    )
    return "\n".join(lines)
