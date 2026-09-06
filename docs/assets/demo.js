(() => {
  const MAX_PULLS = 5;
  const CODE_EXTENSIONS = [
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
  ];
  const TEST_HINTS = ["/test/", "/tests/", "__tests__", ".spec.", ".test.", "_test.", "test_"];
  const DOC_HINTS = [".md", ".mdx", "/docs/", "docs/", "readme", "changelog", "license"];
  const GENERATED_HINTS = [
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
  ];
  // Keep these evidence rules aligned with scoring.py; see the shared parity tests.
  const TEST_PLAN_RE = /^\s{0,3}(?:#{1,6}\s*|[-*]\s+|>\s*)?(?:\*\*|__)?\s*(?:(?:test plan|testing (?:done|notes|steps|strategy)|tests? (?:added|updated|written|performed|run)|how (?:i|we|this was) tested|manual test(?:ing)?|validation(?: steps)?|verification(?: steps)?|repro(?:duction)?(?: steps)?)\s*(?:\*\*|__)?\s*(?:[:\-\u2013]|\.\s*$|$)|(?:tested|verified)\s+(?:locally|manually|end[- ]to[- ]end|with|via|using|by|on|in)\b)/im;
  const LABEL_BLOCKER_RE =
    /\b(blocked|blocker|do not merge|dnm|changes requested|needs? changes?|needs? tests?|missing tests?|waiting on author|needs? author|author action|author follow up|waiting on dependency|waiting for dependency|needs? dependency|dependency blocked|blocked upstream|blocked by upstream|upstream blocked)\b/i;
  const PLAN_ACTION_PRIORITY = {
    "review now": 0,
    "review with caution": 1,
    "needs author follow-up": 2,
    "ask for CI fix": 3,
    "request smaller PR": 4,
    "needs triage": 5,
    "wait for CI": 6,
    "wait for author": 7,
  };
  function normalizeRepository(value) {
    let path = String(value || "").trim();
    if (/^(?:https?:\/\/)?github\.com\//i.test(path)) {
      try {
        const url = new URL(/^https?:\/\//i.test(path) ? path : `https://${path}`);
        if (url.protocol !== "https:" || url.hostname !== "github.com") return "";
        path = url.pathname.slice(1);
      } catch (_) { return ""; }
    } else {
      path = path.split(/[?#]/)[0];
    }
    const match = path.match(/^([A-Za-z0-9][A-Za-z0-9-]*)\/([A-Za-z0-9_.-]+)(?:\/pulls?(?:\/\d+)?)?\/?$/);
    return match && ![".", ".."].includes(match[2]) ? `${match[1]}/${match[2]}` : "";
  }

  function repositoryFromSearch(search) {
    const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
    return normalizeRepository(params.get("repo"));
  }

  function normalizePlanMinutes(value, fallback = 30) {
    const number = Number(value);
    if (Number.isFinite(number) && number >= 1) {
      return Math.min(240, Math.trunc(number));
    }
    const fallbackNumber = Number(fallback);
    if (Number.isFinite(fallbackNumber) && fallbackNumber >= 1) {
      return Math.min(240, Math.trunc(fallbackNumber));
    }
    return 0;
  }

  function planMinutesFromSearch(search) {
    const params = new URLSearchParams(String(search || "").replace(/^\?/, ""));
    const value =
      params.get("plan") ?? params.get("plan-minutes") ?? params.get("review-plan-minutes");
    return value === null ? "" : normalizePlanMinutes(value, 30);
  }

  function summarizeFiles(files) {
    let codeFiles = 0;
    let docFiles = 0;
    let testFiles = 0;
    let generatedFiles = 0;

    for (const file of files || []) {
      const path = String(file.filename || file.path || "").toLowerCase();
      if (!path) {
        continue;
      }
      if (GENERATED_HINTS.some((hint) => path.includes(hint))) {
        generatedFiles += 1;
      } else if (TEST_HINTS.some((hint) => path.includes(hint))) {
        testFiles += 1;
      } else if (DOC_HINTS.some((hint) => path.endsWith(hint) || path.includes(hint))) {
        docFiles += 1;
      } else if (CODE_EXTENSIONS.some((ext) => path.endsWith(ext))) {
        codeFiles += 1;
      }
    }

    return {
      codeFiles,
      docFiles,
      testFiles,
      generatedFiles,
      totalFiles: (files || []).length,
    };
  }

  function summarizeCheckRuns(checkRuns) {
    let passed = 0;
    let failed = 0;
    let pending = 0;
    let skipped = 0;

    for (const item of checkRuns || []) {
      const status = String(item.status || "").toUpperCase();
      const conclusion = String(item.conclusion || item.state || "").toUpperCase();
      if (status && status !== "COMPLETED") {
        pending += 1;
      } else if (conclusion === "SUCCESS" || conclusion === "NEUTRAL") {
        passed += 1;
      } else if (conclusion === "SKIPPED") {
        skipped += 1;
      } else if (["FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"].includes(conclusion)) {
        failed += 1;
      } else {
        pending += 1;
      }
    }

    return {
      passed,
      failed,
      pending,
      skipped,
      total: passed + failed + pending + skipped,
    };
  }

  function labelNames(pr) {
    const labels = pr && Array.isArray(pr.labels) ? pr.labels : [];
    return labels
      .map((label) => {
        if (typeof label === "string") {
          return label;
        }
        return String((label && label.name) || "");
      })
      .filter(Boolean);
  }

  function normalizeLabelName(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[-_:/]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function hasBlockingLabel(pr) {
    return labelNames(pr).some((label) => LABEL_BLOCKER_RE.test(normalizeLabelName(label)));
  }

  function mergeStateStatus(pr) {
    return String(
      (pr && (pr.mergeStateStatus || pr.merge_state_status || pr.mergeable_state)) || ""
    )
      .toUpperCase()
      .replace(/[-\s]+/g, "_");
  }

  function mergeableState(pr) {
    const value = pr && pr.mergeable;
    if (typeof value === "boolean") {
      return value ? "MERGEABLE" : "CONFLICTING";
    }
    return String(value || "")
      .toUpperCase()
      .replace(/[-\s]+/g, "_");
  }

  function reviewRequestCount(pr) {
    let count = 0;
    for (const key of [
      "reviewRequests",
      "review_requests",
      "requested_reviewers",
      "requestedReviewers",
    ]) {
      const value = pr && pr[key];
      if (Array.isArray(value)) {
        count += value.length;
      } else if (value && typeof value === "object") {
        for (const nestedKey of ["nodes", "items"]) {
          if (Array.isArray(value[nestedKey])) {
            count += value[nestedKey].length;
            break;
          }
        }
      }
    }
    for (const key of ["requested_teams", "requestedTeams"]) {
      const value = pr && pr[key];
      if (Array.isArray(value)) {
        count += value.length;
      }
    }
    return count;
  }

  function daysSince(value, now = new Date()) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return null;
    }
    return Math.max(0, Math.floor((now.getTime() - date.getTime()) / 86400000));
  }

  function addImpact(scoreBreakdown, label, riskDelta, kind) {
    scoreBreakdown.push({ label, riskDelta, kind });
  }

  function clampRisk(value) {
    return Math.max(0, Math.min(100, value));
  }

  function resolveAnalysisOptions(value) {
    if (value instanceof Date) {
      return { now: value, checkRuns: null };
    }
    return {
      now: value && value.now ? value.now : new Date(),
      checkRuns: value && Array.isArray(value.checkRuns) ? value.checkRuns : null,
    };
  }

  function analyzePullRequest(pr, files, optionsValue = {}) {
    const options = resolveAnalysisOptions(optionsValue);
    const fileSummary = summarizeFiles(files);
    const checkSummary = summarizeCheckRuns(options.checkRuns);
    const additions = Number(pr.additions || 0);
    const deletions = Number(pr.deletions || 0);
    const changedFiles = Number(pr.changed_files || fileSummary.totalFiles || 0);
    const filesComplete = fileSummary.totalFiles >= changedFiles;
    const totalDiff = additions + deletions;
    const staleDays = daysSince(pr.updated_at, options.now);
    const hasBody = Object.prototype.hasOwnProperty.call(pr, "body");
    const hasTestPlan = TEST_PLAN_RE.test(String(pr.body || ""));
    const isDraft = Boolean(pr.draft);
    const hasCheckData = Array.isArray(options.checkRuns);
    const hasLabelBlocker = hasBlockingLabel(pr);
    const mergeState = mergeStateStatus(pr);
    const mergeable = mergeableState(pr);
    const reviewRequests = reviewRequestCount(pr);

    let risk = 0;
    const signals = [];
    const flags = [];
    const scoreBreakdown = [];

    if (isDraft) {
      risk += 25;
      flags.push("draft PR");
      addImpact(scoreBreakdown, "draft PR", 25, "flag");
    }

    if (totalDiff > 1500 || changedFiles > 25) {
      risk += 30;
      flags.push("very large diff");
      addImpact(scoreBreakdown, "very large diff", 30, "flag");
    } else if (totalDiff > 500 || changedFiles > 10) {
      risk += 15;
      flags.push("large diff");
      addImpact(scoreBreakdown, "large diff", 15, "flag");
    }

    if (hasCheckData) {
      if (checkSummary.total === 0) {
        risk += 8;
        flags.push("no visible checks");
        addImpact(scoreBreakdown, "no visible checks", 8, "flag");
      } else if (checkSummary.failed) {
        risk += 30;
        flags.push("CI failing");
        addImpact(scoreBreakdown, "CI failing", 30, "flag");
      } else if (checkSummary.pending) {
        risk += 10;
        flags.push("CI pending");
        addImpact(scoreBreakdown, "CI pending", 10, "flag");
      } else if (checkSummary.passed) {
        risk -= 8;
        signals.push("CI passed");
        addImpact(scoreBreakdown, "CI passed", -8, "signal");
      }
    }

    if (staleDays !== null) {
      if (staleDays >= 14) {
        const label = `stale ${staleDays} days`;
        risk += 15;
        flags.push(label);
        addImpact(scoreBreakdown, label, 15, "flag");
      } else if (staleDays >= 7) {
        const label = `quiet ${staleDays} days`;
        risk += 8;
        flags.push(label);
        addImpact(scoreBreakdown, label, 8, "flag");
      }
    }

    if (hasBody && !hasTestPlan && fileSummary.codeFiles) {
      risk += 8;
      flags.push("no test plan found");
      addImpact(scoreBreakdown, "no test plan found", 8, "flag");
    } else if (hasTestPlan) {
      signals.push("test plan present");
    }

    if (hasLabelBlocker) {
      risk += 18;
      flags.push("maintainer blocking label");
      addImpact(scoreBreakdown, "maintainer blocking label", 18, "flag");
    }

    if (mergeable === "CONFLICTING" || mergeState === "DIRTY") {
      risk += 20;
      flags.push("merge conflicts");
      addImpact(scoreBreakdown, "merge conflicts", 20, "flag");
    } else if (mergeState === "BEHIND") {
      risk += 8;
      flags.push("branch behind base");
      addImpact(scoreBreakdown, "branch behind base", 8, "flag");
    } else if (mergeState === "BLOCKED") {
      risk += 6;
      flags.push("merge blocked by repo rules");
      addImpact(scoreBreakdown, "merge blocked by repo rules", 6, "flag");
    } else if (mergeState === "UNSTABLE" && !checkSummary.total) {
      risk += 12;
      flags.push("merge checks unstable");
      addImpact(scoreBreakdown, "merge checks unstable", 12, "flag");
    } else if (mergeState === "CLEAN" || mergeable === "MERGEABLE") {
      signals.push("mergeable");
    }

    if (reviewRequests) {
      signals.push(reviewRequests === 1 ? "review requested" : `${reviewRequests} reviews requested`);
    }

    if (Array.isArray(files) && !filesComplete) {
      flags.push("incomplete file list");
    }

    if (filesComplete && fileSummary.codeFiles && !fileSummary.testFiles) {
      risk += 10;
      flags.push("code changed without tests");
      addImpact(scoreBreakdown, "code changed without tests", 10, "flag");
    } else if (fileSummary.testFiles) {
      signals.push("tests changed");
    }

    if (fileSummary.generatedFiles) {
      const generatedRisk = Math.min(12, fileSummary.generatedFiles * 3);
      risk += generatedRisk;
      flags.push("generated or lockfile changes");
      addImpact(scoreBreakdown, "generated or lockfile changes", generatedRisk, "flag");
    }

    if (filesComplete && fileSummary.docFiles && fileSummary.docFiles === fileSummary.totalFiles) {
      risk -= 6;
      signals.push("docs-only shape");
      addImpact(scoreBreakdown, "docs-only shape", -6, "signal");
    }

    const rawRisk = risk;
    risk = clampRisk(risk);
    const reviewability = 100 - risk;
    const action = chooseAction({
      reviewability,
      isDraft,
      checks: checkSummary,
      hasCheckData,
      hasLabelBlocker,
      hasMergeConflict: flags.includes("merge conflicts"),
      isBranchBehind: flags.includes("branch behind base"),
      totalDiff,
      changedFiles,
    });

    return {
      number: pr.number,
      title: pr.title || "Untitled",
      url: pr.html_url || "",
      action,
      nextStep: recommendNextStep({ action, flags, signals }),
      reviewability,
      risk,
      rawRisk,
      signals,
      flags,
      scoreBreakdown,
      additions,
      deletions,
      changedFiles,
      staleDays,
      mergeStateStatus: mergeState,
      mergeable,
      reviewRequests,
      checksKnown: hasCheckData,
    };
  }

  function chooseAction({
    reviewability,
    isDraft,
    checks,
    hasCheckData,
    hasLabelBlocker,
    hasMergeConflict,
    isBranchBehind,
    totalDiff,
    changedFiles,
  }) {
    if (isDraft) {
      return "wait for author";
    }
    if (hasCheckData && checks && checks.failed) {
      return "ask for CI fix";
    }
    if (hasCheckData && checks && checks.pending) {
      return "wait for CI";
    }
    if (hasMergeConflict || isBranchBehind) {
      return "needs author follow-up";
    }
    if (hasLabelBlocker) {
      return "needs author follow-up";
    }
    if (totalDiff > 1500 || changedFiles > 25) {
      return "request smaller PR";
    }
    if (reviewability >= 75) {
      return "review now";
    }
    if (reviewability >= 55) {
      return "review with caution";
    }
    return "needs triage";
  }

  function recommendNextStep({ action, flags = [], signals = [] }) {
    if (action === "wait for author") {
      return "Wait for the author to mark the PR ready for review.";
    }
    if (action === "ask for CI fix") {
      return "Ask the author to get failing checks green before deeper review.";
    }
    if (action === "wait for CI") {
      return "Wait for checks to finish before spending review time.";
    }
    if (action === "needs author follow-up") {
      if (flags.includes("merge conflicts")) {
        return "Ask the author to resolve merge conflicts before another review pass.";
      }
      if (flags.includes("branch behind base")) {
        return "Ask the author to update the branch with the base branch before review.";
      }
      if (flags.includes("maintainer blocker language") || flags.includes("maintainer blocking label")) {
        return "Ask the author to respond to unresolved maintainer feedback.";
      }
      return "Ask the author to address requested changes before another review pass.";
    }
    if (action === "request smaller PR") {
      return "Ask for a smaller split or a clear scope explanation.";
    }
    if (action === "review now") {
      if (signals.includes("docs-only shape")) {
        return "Review now as a likely low-risk docs-only change.";
      }
      return "Review now while the PR appears small, active, and low risk.";
    }
    if (action === "review with caution") {
      return "Review, but inspect the risk flags before approving.";
    }
    return "Triage manually before assigning reviewer time.";
  }

  function markdownCell(value) {
    return String(value || "")
      .replaceAll("\n", " ")
      .replaceAll("|", "\\|")
      .trim();
  }

  function markdownPrLabel(item) {
    const title = markdownCell(`#${item.number} ${item.title}`);
    const url = safePullUrl(item.url);
    return url ? `[${title}](${url})` : title;
  }

  function intValue(value) {
    const number = Number(value || 0);
    return Number.isFinite(number) ? Math.trunc(number) : 0;
  }

  function estimateReviewMinutes(item) {
    const action = String((item && item.action) || "needs triage");
    const changedFiles = intValue(item && item.changedFiles);
    const totalDiff = intValue(item && item.additions) + intValue(item && item.deletions);
    const signals = item && Array.isArray(item.signals) ? item.signals : [];

    if (action === "wait for CI" || action === "wait for author") {
      return 0;
    }
    if (
      action === "ask for CI fix" ||
      action === "needs author follow-up" ||
      action === "request smaller PR"
    ) {
      return 5;
    }
    if (action === "needs triage") {
      return 8;
    }

    let base;
    if (signals.includes("docs-only shape")) {
      base = 6;
    } else if (totalDiff > 500 || changedFiles > 10) {
      base = 25;
    } else if (totalDiff > 150 || changedFiles > 5) {
      base = 18;
    } else {
      base = 12;
    }

    return action === "review with caution" ? base + 8 : base;
  }

  function planReason(item) {
    const flags = item && Array.isArray(item.flags) ? item.flags.filter(Boolean) : [];
    const signals = item && Array.isArray(item.signals) ? item.signals.filter(Boolean) : [];
    const visible = flags.length ? flags.slice(0, 2) : signals.slice(0, 2);
    return visible.length ? visible.join(", ") : "no notable signals";
  }

  function buildReviewPlan(items, budgetMinutes) {
    const budget = intValue(budgetMinutes);
    if (budget < 1) {
      throw new Error("Plan minutes must be 1 or greater.");
    }
    const candidates = [...(items || [])].sort((a, b) => {
      const aAction = String((a && a.action) || "");
      const bAction = String((b && b.action) || "");
      const priorityDelta =
        (PLAN_ACTION_PRIORITY[aAction] ?? 99) - (PLAN_ACTION_PRIORITY[bAction] ?? 99);
      if (priorityDelta) {
        return priorityDelta;
      }
      const minuteDelta = estimateReviewMinutes(a) - estimateReviewMinutes(b);
      if (minuteDelta) {
        return minuteDelta;
      }
      const scoreDelta = intValue(b && b.reviewability) - intValue(a && a.reviewability);
      if (scoreDelta) {
        return scoreDelta;
      }
      return intValue(a && a.number) - intValue(b && b.number);
    });

    const planned = [];
    const deferred = [];
    const waiting = [];
    let used = 0;

    for (const item of candidates) {
      const estimatedMinutes = estimateReviewMinutes(item);
      const entry = { item, estimatedMinutes, reason: planReason(item) };
      if (estimatedMinutes === 0) {
        waiting.push(entry);
      } else if (used + estimatedMinutes <= budget || planned.length === 0) {
        planned.push(entry);
        used += estimatedMinutes;
      } else {
        deferred.push(entry);
      }
    }

    return {
      budgetMinutes: budget,
      plannedMinutes: used,
      remainingMinutes: Math.max(0, budget - used),
      overBudgetMinutes: Math.max(0, used - budget),
      planned,
      deferred,
      waiting,
    };
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function sampleQueue() {
    // Fictional data stays deterministic and never makes a network request.
    const now = new Date("2026-01-15T12:00:00Z");
    const base = {
      updated_at: "2026-01-15T10:00:00Z", body: "Test plan: regression tests pass locally.",
      additions: 34, deletions: 8, changed_files: 2, mergeable: true, draft: false,
    };
    const sourceAndTest = [{ filename: "src/queue.py" }, { filename: "tests/test_queue.py" }];
    const passed = [{ status: "COMPLETED", conclusion: "SUCCESS" }];
    return [
      [{ number: 128, title: "Handle repositories with no open pull requests" }, sourceAndTest, passed],
      [{ number: 127, title: "Clarify the GitHub Action permissions", additions: 18, deletions: 4, changed_files: 1, body: "Documentation update." }, [{ filename: "docs/github-action.md" }], passed],
      [{ number: 126, title: "Cache hydrated pull request details", additions: 82, deletions: 21 }, sourceAndTest, [{ status: "COMPLETED", conclusion: "FAILURE" }]],
      [{ number: 125, title: "Add CSV output for review plans", additions: 56, deletions: 10 }, sourceAndTest, [{ status: "IN_PROGRESS", conclusion: null }]],
      [{ number: 124, title: "Support archived repository exports", draft: true, additions: 112, deletions: 16 }, sourceAndTest, passed],
    ].map(([pr, files, checkRuns]) => analyzePullRequest({ ...base, ...pr }, files, { now, checkRuns }));
  }

  function safePullUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && url.hostname === "github.com" ? url.href : "";
    } catch (_) { return ""; }
  }

  function renderReviewPlanMarkdown(items, repository, budgetMinutes, source = "live") {
    const plan = buildReviewPlan(items, budgetMinutes);
    const label = source === "sample" ? "Example queue (fictional pull requests)" : repository;
    const lines = [
      `## Review plan: ${label}`, "",
      `Time available: ${plan.budgetMinutes} minutes. Estimated work: ${plan.plannedMinutes} minutes.`,
      `Based on ${items.length} ${source === "sample" ? "example" : "recent open"} pull requests. Estimates are approximate.`, "",
    ];
    if (plan.overBudgetMinutes) {
      lines.push(`The first task is estimated to exceed this budget by ${plan.overBudgetMinutes} minutes.`, "");
    }
    if (!plan.planned.length) lines.push("No active review work in this queue.", "");
    for (const [index, entry] of plan.planned.entries()) {
      lines.push(`${index + 1}. ${markdownPrLabel(entry.item)} (${entry.estimatedMinutes} min)`, `   ${entry.item.nextStep}`, "");
    }
    for (const [heading, entries] of [["Leave for later", plan.deferred], ["Waiting on someone else or CI", plan.waiting]]) {
      if (!entries.length) continue;
      lines.push(`### ${heading}`, "");
      for (const { item } of entries) lines.push(`- ${markdownPrLabel(item)}: ${item.nextStep}`);
      lines.push("");
    }
    lines.push("Prepared with Maintainer Radar. Check the code and discussion before acting.", "");
    return lines.join("\n");
  }

  async function requestJson(path, signal) {
    const response = await fetch(`https://api.github.com${path}`, {
      headers: { Accept: "application/vnd.github+json" }, signal,
    });
    if (!response.ok) {
      const remaining = response.headers.get("x-ratelimit-remaining");
      if (response.status === 429 || (response.status === 403 && remaining === "0")) {
        throw new Error("GitHub's public request limit has been reached. Try later, explore the example queue, or use the CLI with your GitHub account.");
      }
      if (response.status === 404) throw new Error("GitHub couldn't find that public resource. Check the repository name; private repositories aren't available in this demo.");
      throw new Error(`GitHub returned HTTP ${response.status}. Try again later or use the example queue.`);
    }
    return response.json();
  }

  async function fetchPreview(repository, { signal, onProgress = () => {} } = {}) {
    const pulls = await requestJson(`/repos/${repository}/pulls?state=open&sort=updated&direction=desc&per_page=${MAX_PULLS}`, signal);
    let completed = 0;
    const warnings = [];
    const results = await Promise.allSettled(pulls.slice(0, MAX_PULLS).map(async (pull) => {
      try {
        const [detail, files] = await Promise.all([
          requestJson(`/repos/${repository}/pulls/${pull.number}`, signal),
          requestJson(`/repos/${repository}/pulls/${pull.number}/files?per_page=100`, signal),
        ]);
        // Do not score an incomplete file list as if missing tests were confirmed.
        if (detail.changed_files > files.length) throw new Error(`PR #${pull.number} exceeds the browser's 100-file preview limit. Use the CLI for the complete file list.`);
        let checkRuns = null;
        if (detail.head && detail.head.sha) {
          try {
            const [checks, statuses] = await Promise.all([
              requestJson(`/repos/${repository}/commits/${detail.head.sha}/check-runs?per_page=100`, signal),
              requestJson(`/repos/${repository}/commits/${detail.head.sha}/status?per_page=100`, signal),
            ]);
            if (Array.isArray(checks.check_runs) && checks.total_count <= checks.check_runs.length &&
                Array.isArray(statuses.statuses) && statuses.total_count <= statuses.statuses.length) {
              checkRuns = [...checks.check_runs, ...statuses.statuses];
            }
          } catch (error) {
            if (signal && signal.aborted) throw error;
          }
        }
        if (!checkRuns) warnings.push(`CI data for #${pull.number} was unavailable or incomplete. Verify its checks on GitHub.`);
        return analyzePullRequest(detail, files, { checkRuns });
      } finally {
        completed += 1;
        onProgress(completed, Math.min(pulls.length, MAX_PULLS));
      }
    }));
    if (signal && signal.aborted) throw new DOMException("Scan cancelled", "AbortError");
    const items = [];
    results.forEach((result, index) => {
      if (result.status === "fulfilled") items.push(result.value);
      else warnings.push(`#${pulls[index].number} wasn't analyzed. ${result.reason instanceof Error ? result.reason.message : "Its data could not be loaded."}`);
    });
    if (pulls.length && !items.length) throw new Error(warnings.join(" ") || "None of the pull requests could be loaded.");
    return { items, warnings, requested: Math.min(pulls.length, MAX_PULLS) };
  }

  function actionClass(action) {
    if (action === "review now") return "review";
    if (action.startsWith("wait for")) return "waiting";
    if (action === "needs author follow-up" || action === "ask for CI fix") return "followup";
    return "caution";
  }

  function pullTitle(item) {
    const title = escapeHtml(item.title);
    const url = safePullUrl(item.url);
    return url ? `<a href="${escapeHtml(url)}">${title} <svg class="arrow-icon" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M3 9 9 3M3 3h6v6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg></a>` : title;
  }

  function renderQueue(items, source) {
    const body = document.querySelector("#queue-body");
    if (!items.length) {
      body.innerHTML = '<div class="empty-state"><strong>No open pull requests.</strong><p>This repository has no open PRs to review. Try another repository or load the example queue.</p></div>';
      return;
    }
    const sorted = [...items].sort((a, b) => (PLAN_ACTION_PRIORITY[a.action] ?? 99) - (PLAN_ACTION_PRIORITY[b.action] ?? 99) || a.number - b.number);
    body.innerHTML = sorted.map((item) => {
      const minutes = estimateReviewMinutes(item);
      const flags = item.flags.map((flag) => `<li>${escapeHtml(flag)}</li>`).join("");
      const signals = item.signals.map((signal) => `<li>${escapeHtml(signal)}</li>`).join("");
      const impacts = item.scoreBreakdown.map((entry) => `${escapeHtml(entry.label)} (${entry.riskDelta > 0 ? "+" : ""}${entry.riskDelta})`).join("; ");
      return `<article class="pr-card" data-pr="${item.number}">
        <div class="pr-card-main"><div class="pr-topline"><span class="pr-number">#${item.number}</span><span class="pill ${actionClass(item.action)}">${escapeHtml(item.action)}</span></div>
          <h4>${pullTitle(item)}</h4><p class="pr-next">${escapeHtml(item.nextStep)}</p>
          <div class="pr-metadata"><span>${item.changedFiles} ${item.changedFiles === 1 ? "file" : "files"}</span><span><span class="diff-add">+${item.additions}</span> <span class="diff-remove">−${item.deletions}</span></span><span>${minutes ? `~${minutes} min` : "Waiting"}</span>${!item.checksKnown ? '<span>CI not verified</span>' : ""}</div>
        </div>
        <details class="pr-details"><summary>Why this suggestion?</summary><div class="pr-evidence"><div><h5>Signals found</h5><ul>${signals || "<li>No positive signals available.</li>"}</ul></div><div><h5>Things to check</h5><ul>${flags || "<li>No blocker signals found in this metadata.</li>"}${!item.checksKnown ? "<li>CI data unavailable; check GitHub before reviewing.</li>" : ""}</ul></div><p class="pr-score"><strong>Heuristic score: ${item.reviewability}/100.</strong> This measures reviewability, not code quality.<br>${impacts || "No score adjustments."}</p></div></details>
      </article>`;
    }).join("");
  }

  function renderPlan(items, budget) {
    const plan = buildReviewPlan(items, budget);
    document.querySelector("#plan-title").textContent = `${budget} minute review plan`;
    document.querySelector("#plan-meta").textContent = `${plan.plannedMinutes} min estimated · ${plan.remainingMinutes} min left`;
    const progress = document.querySelector("#plan-progress");
    progress.style.width = `${Math.min(100, plan.plannedMinutes / budget * 100)}%`;
    progress.parentElement.dataset.over = String(Boolean(plan.overBudgetMinutes));
    document.querySelector("#plan-body").innerHTML = plan.planned.length ? plan.planned.map(({ item, estimatedMinutes }, index) =>
      `<div class="plan-row"><span class="plan-order">${index + 1}</span><strong>#${item.number} ${pullTitle(item)}</strong><span>${escapeHtml(item.action)} · ~${estimatedMinutes} min</span></div>`
    ).join("") : `<p class="plan-empty">${items.length ? 'No active review work. These PRs are waiting on CI or their authors.' : 'No open pull requests to plan.'}</p>`;
    const overflow = document.querySelector("#plan-overflow");
    overflow.dataset.over = String(Boolean(plan.overBudgetMinutes));
    overflow.textContent = plan.overBudgetMinutes
      ? `The first task alone is about ${plan.overBudgetMinutes} min over your budget. Allow more time or leave it for later.`
      : [plan.deferred.length ? `${plan.deferred.length} left for later` : "", plan.waiting.length ? `${plan.waiting.length} waiting on CI or authors` : ""].filter(Boolean).join(" · ");
  }

  function init() {
    const form = document.querySelector("#repo-form");
    if (!form) return;
    const input = document.querySelector("#repo-input");
    const submit = document.querySelector("#repo-submit");
    const sample = document.querySelector("#load-sample");
    const cancel = document.querySelector("#scan-cancel");
    const status = document.querySelector("#demo-status");
    const results = document.querySelector("#results");
    const errorPanel = document.querySelector("#scan-error");
    const warning = document.querySelector("#scan-warning");
    const minutes = document.querySelector("#plan-minutes");
    const copy = document.querySelector("#copy-plan");
    const dialog = document.querySelector("#export-dialog");
    let items = [], repository = "", source = "sample", controller = null, exportUrl = "";

    function setStatus(message, kind = "info") { status.textContent = message; status.dataset.kind = kind; }
    function currentBudget() { return minutes.validity.valid && minutes.value !== "" ? Number(minutes.value) : null; }
    function writeLocation() {
      const url = new URL(window.location.href);
      for (const key of ["repo", "group", "group-by", "plan", "plan-minutes", "review-plan-minutes"]) url.searchParams.delete(key);
      if (repository) url.searchParams.set("repo", repository);
      if (currentBudget() !== null) url.searchParams.set("plan", String(currentBudget()));
      window.history.replaceState(null, "", url);
    }
    function updatePlan() {
      const budget = currentBudget();
      document.querySelector("#budget-error").hidden = budget !== null;
      copy.disabled = budget === null || results.hidden || !items.length;
      document.querySelectorAll("[data-budget]").forEach((button) => button.setAttribute("aria-pressed", String(Number(button.dataset.budget) === budget)));
      if (budget !== null) { renderPlan(items, budget); writeLocation(); }
    }
    function render() {
      results.hidden = false;
      const badge = document.querySelector("#source-badge");
      badge.textContent = source === "sample" ? "Interactive example" : "Live GitHub data";
      badge.dataset.live = String(source === "live");
      document.querySelector("#queue-source").textContent = source === "sample" ? "Example queue" : "Public repository";
      document.querySelector("#queue-title").textContent = source === "sample" ? "A small project, a familiar backlog." : repository;
      document.querySelector("#queue-description").textContent = source === "sample" ? "Fictional pull requests, analyzed with the same rules as a live scan." : `${items.length} of the most recently updated open PRs analyzed. This is a preview, not the whole backlog.`;
      document.querySelector("#metric-total").textContent = items.length;
      const ready = items.filter((item) => item.action === "review now").length;
      document.querySelector("#metric-review").textContent = ready;
      document.querySelector("#metric-followup").textContent = items.length - ready;
      renderQueue(items, source);
      updatePlan();
    }
    function stopScan() {
      if (controller) controller.abort();
      controller = null;
      submit.disabled = false;
      cancel.hidden = true;
      results.setAttribute("aria-busy", "false");
    }
    function showSample() {
      stopScan();
      source = "sample"; repository = ""; items = sampleQueue();
      errorPanel.hidden = true; warning.hidden = true;
      render();
      setStatus("Example data. Change the review time or expand a PR to try it out. No GitHub requests are made.");
    }
    async function scan() {
      const requested = normalizeRepository(input.value);
      if (!requested) {
        input.setCustomValidity("Enter owner/repo or a public GitHub repository URL."); input.reportValidity(); return;
      }
      input.setCustomValidity("");
      stopScan();
      const active = new AbortController(); controller = active;
      const timeout = setTimeout(() => active.abort(), 30000);
      errorPanel.hidden = true; warning.hidden = true; results.hidden = true;
      results.setAttribute("aria-busy", "true");
      submit.disabled = true; cancel.hidden = false; copy.disabled = true;
      setStatus(`Loading recent pull requests from ${requested}…`, "loading");
      try {
        const scanResult = await fetchPreview(requested, { signal: active.signal, onProgress(done, total) {
          if (controller === active && !active.signal.aborted) setStatus(`Reading ${requested}: ${done} of ${total} PRs loaded…`, "loading");
        } });
        if (controller !== active) return;
        items = scanResult.items; repository = requested; source = "live";
        render();
        warning.hidden = !scanResult.warnings.length;
        warning.textContent = scanResult.warnings.join(" ");
        setStatus(`Loaded ${items.length} of ${scanResult.requested} recent open PRs from ${repository}.`);
      } catch (error) {
        if (controller !== active) return;
        errorPanel.hidden = false;
        document.querySelector("#scan-error-message").textContent = active.signal.aborted
          ? "The scan took longer than 30 seconds. Try again or explore the example queue."
          : error instanceof TypeError ? "Couldn't reach GitHub. Check your connection, try again, or explore the example queue."
            : error instanceof Error ? error.message : "The scan failed. Try again or explore the example queue.";
        setStatus("No results shown for this scan.");
      } finally {
        clearTimeout(timeout);
        if (controller === active) stopScan();
      }
    }
    form.addEventListener("submit", (event) => { event.preventDefault(); scan(); });
    input.addEventListener("input", () => input.setCustomValidity(""));
    sample.addEventListener("click", showSample);
    cancel.addEventListener("click", () => { showSample(); setStatus("Scan cancelled. The example queue is shown."); });
    document.querySelector("#scan-retry").addEventListener("click", scan);
    minutes.addEventListener("input", updatePlan);
    document.querySelectorAll("[data-budget]").forEach((button) => button.addEventListener("click", () => { minutes.value = button.dataset.budget; updatePlan(); }));
    document.querySelector("#export-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => { if (exportUrl) URL.revokeObjectURL(exportUrl); exportUrl = ""; });
    copy.addEventListener("click", async () => {
      const budget = currentBudget();
      if (budget === null || results.hidden || !items.length) return;
      const text = renderReviewPlanMarkdown(items, repository, budget, source);
      try {
        if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard unavailable");
        await navigator.clipboard.writeText(text);
        setStatus(`Copied the ${budget} minute ${source === "sample" ? "example " : ""}review plan.`);
      } catch (_) {
        document.querySelector("#export-text").value = text;
        if (exportUrl) URL.revokeObjectURL(exportUrl);
        exportUrl = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
        const download = document.querySelector("#export-download");
        download.href = exportUrl; download.download = "review-plan.md";
        dialog.showModal();
        document.querySelector("#export-text").focus();
        document.querySelector("#export-text").select();
      }
    });
    const initialRepository = repositoryFromSearch(window.location.search);
    const initialBudget = planMinutesFromSearch(window.location.search);
    if (initialBudget) minutes.value = String(initialBudget);
    showSample();
    if (initialRepository) { input.value = initialRepository; scan(); }
  }

  const api = {
    analyzePullRequest, buildReviewPlan, estimateReviewMinutes, fetchPreview,
    normalizeRepository, normalizePlanMinutes, planMinutesFromSearch,
    repositoryFromSearch, renderReviewPlanMarkdown, sampleQueue,
    summarizeCheckRuns, summarizeFiles, safePullUrl,
  };
  if (typeof module !== "undefined") module.exports = api;
  if (typeof window !== "undefined") { window.MaintainerRadarDemo = api; init(); }
})();
