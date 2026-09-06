const assert = require("node:assert/strict");
const demo = require("../docs/assets/demo.js");

for (const value of ["python/cpython", "https://github.com/python/cpython/pulls", "github.com/python/cpython/pull/123", "https://github.com/python/cpython/?tab=readme-ov-file#readme"]) {
  assert.equal(demo.normalizeRepository(value), "python/cpython");
}
for (const value of ["not a repo", "https://example.com/python/cpython", "https://github.com.evil.test/python/cpython", "owner/..", "../repo", "owner/repo/../../secret", "javascript:alert(1)"]) {
  assert.equal(demo.normalizeRepository(value), "");
}
assert.equal(demo.repositoryFromSearch("?repo=python%2Fcpython"), "python/cpython");
assert.equal(demo.repositoryFromSearch("?other=x"), "");
assert.equal(demo.normalizePlanMinutes("45"), 45);
assert.equal(demo.normalizePlanMinutes("0", 30), 30);
assert.equal(demo.normalizePlanMinutes("bad", 0), 0);
assert.equal(demo.normalizePlanMinutes("999999"), 240);
assert.equal(demo.planMinutesFromSearch("?plan=15"), 15);
assert.equal(demo.planMinutesFromSearch("?plan-minutes=45"), 45);
assert.equal(demo.planMinutesFromSearch("?review-plan-minutes=20"), 20);
assert.equal(demo.planMinutesFromSearch("?plan=bad"), 30);
assert.equal(demo.planMinutesFromSearch(""), "");
assert.equal(demo.safePullUrl("javascript:alert(1)"), "");
assert.equal(demo.safePullUrl("https://evil.test/pull/1"), "");
assert.equal(demo.safePullUrl("https://github.com/owner/repo/pull/1"), "https://github.com/owner/repo/pull/1");

const now = new Date("2026-06-01T00:00:00Z");
const base = { number: 42, title: "Fix parser cache race", html_url: "https://github.com/example/project/pull/42", body: "Test plan: local repro and unit tests.", updated_at: now.toISOString(), additions: 42, deletions: 18, changed_files: 2, draft: false };
const files = [{ filename: "src/parser.py" }, { filename: "tests/test_parser.py" }];
const passed = [{ status: "COMPLETED", conclusion: "SUCCESS" }];
const analyze = (pr = {}, options = {}, paths = files) => demo.analyzePullRequest({ ...base, ...pr }, paths, { now, checkRuns: passed, ...options });
const ready = analyze();
assert.equal(ready.action, "review now");
assert.equal(ready.reviewability, 100);
assert.ok(ready.signals.includes("test plan present"));
assert.ok(ready.signals.includes("tests changed"));
assert.equal(ready.checksKnown, true);
const risky = analyze({ number: 43, additions: 2200, deletions: 120, changed_files: 40, body: "Implementation update.", updated_at: "2026-05-10T00:00:00Z" }, { checkRuns: [{ status: "COMPLETED", conclusion: "FAILURE" }] }, [{ filename: "src/plugin/runtime.ts" }]);
assert.equal(risky.action, "ask for CI fix");
assert.equal(risky.reviewability, 17);
for (const flag of ["very large diff", "CI failing", "stale 22 days", "no test plan found", "incomplete file list"]) assert.ok(risky.flags.includes(flag), flag);
assert.ok(!risky.flags.includes("code changed without tests"));
assert.ok(risky.scoreBreakdown.some((entry) => entry.label === "very large diff" && entry.riskDelta === 30));
assert.equal(analyze({ labels: [{ name: "waiting-on-author" }] }).action, "needs author follow-up");
assert.equal(analyze({ labels: ["blocked-upstream"] }).action, "needs author follow-up");
assert.equal(analyze({ labels: ["waiting-for-dependency"] }).action, "needs author follow-up");
assert.equal(analyze({ mergeable: false }).action, "needs author follow-up");
assert.equal(analyze({ mergeable_state: "behind" }).action, "needs author follow-up");
assert.equal(analyze({ draft: true }).action, "wait for author");
assert.equal(analyze({ additions: 2000, changed_files: 30 }).action, "request smaller PR");
assert.equal(analyze({ requested_reviewers: [{ login: "a" }], requested_teams: [{ name: "team" }] }).reviewRequests, 2);
const pending = analyze({ number: 45 }, { checkRuns: [{ status: "IN_PROGRESS", conclusion: null }] });
assert.equal(pending.action, "wait for CI");
assert.equal(analyze({}, { checkRuns: null }).checksKnown, false);
assert.ok(analyze({}, { checkRuns: [] }).flags.includes("no visible checks"));
assert.deepEqual(demo.summarizeCheckRuns([{ status: "IN_PROGRESS", conclusion: null }]), { passed: 0, failed: 0, pending: 1, skipped: 0, total: 1 });

// Ordinary mentions of tests are not evidence. Tests and generated files are not source files.
assert.ok(analyze({ body: "This makes the CI and tests faster." }).flags.includes("no test plan found"));
for (const body of ["## Test plan\npytest", "**Validation:** ran tests", "Tested locally with pytest", "Tests added: regression coverage"]) {
  assert.ok(analyze({ body }).signals.includes("test plan present"), body);
}
assert.deepEqual(demo.summarizeFiles([{ filename: "tests/test_a.py" }, { filename: "generated/test_a.py" }, { filename: "docs/guide.py" }, { filename: "src/a.py" }]), { codeFiles: 1, docFiles: 1, testFiles: 1, generatedFiles: 1, totalFiles: 4 });
assert.ok(!analyze({ body: "" }, {}, [{ filename: "tests/test_parser.py" }]).flags.includes("no test plan found"));
const shallow = { ...base }; delete shallow.body;
assert.ok(!demo.analyzePullRequest(shallow, files, { now }).flags.includes("no test plan found"));
for (const filename of ["package-lock.json", "Dockerfile", "tests/test_parser.py"]) {
  const mixed = analyze({}, {}, [{ filename: "README.md" }, { filename }]);
  assert.ok(!mixed.signals.includes("docs-only shape"), filename);
  assert.equal(demo.estimateReviewMinutes(mixed), 12, filename);
}
const docsOnly = analyze({ changed_files: 1 }, {}, [{ filename: "README.md" }]);
assert.equal(demo.estimateReviewMinutes(docsOnly), 6);

const plan = demo.buildReviewPlan([ready, risky, pending], 15);
assert.deepEqual(plan.planned.map((entry) => entry.item.number), [42]);
assert.deepEqual(plan.deferred.map((entry) => entry.item.number), [43]);
assert.deepEqual(plan.waiting.map((entry) => entry.item.number), [45]);
assert.equal(plan.plannedMinutes, 12);
assert.equal(plan.remainingMinutes, 3);
assert.equal(demo.buildReviewPlan([ready], 1).overBudgetMinutes, 11);
assert.throws(() => demo.buildReviewPlan([ready], 0), /1 or greater/);
const sample = demo.sampleQueue();
assert.equal(sample.length, 5);
assert.deepEqual(sample, demo.sampleQueue());
assert.ok(sample.every((item) => !item.url));
assert.equal(sample.filter((item) => item.action === "review now").length, 2);
assert.equal(demo.buildReviewPlan(sample, 15).plannedMinutes, 11);
assert.equal(demo.buildReviewPlan(sample, 30).plannedMinutes, 23);
const brief = demo.renderReviewPlanMarkdown(sample, "", 15, "sample");
assert.ok(brief.includes("fictional pull requests"));
assert.ok(brief.includes("Time available: 15 minutes. Estimated work: 11 minutes."));
assert.ok(!brief.includes("Next 60 minutes"));
assert.ok(brief.includes("Leave for later"));
assert.ok(brief.includes("Waiting on someone else or CI"));
assert.ok(!brief.includes("https://github.com/example"));
assert.ok(demo.renderReviewPlanMarkdown([ready], "example/project", 1).includes("exceed this budget by 11"));
assert.ok(demo.renderReviewPlanMarkdown([{ ...ready, url: "javascript:alert(1)" }], "example/project", 30).includes("#42 Fix parser cache race"));
assert.ok(!demo.renderReviewPlanMarkdown([{ ...ready, url: "javascript:alert(1)" }], "example/project", 30).includes("javascript:"));

// Exercise network failure boundaries without making real API requests.
async function networkChecks() {
  const originalFetch = global.fetch;
  const controller = new AbortController();
  const detail = { ...base, head: { sha: "abc" } };
  const reply = (data, status = 200, remaining = "59") => ({ ok: status === 200, status, headers: { get: () => remaining }, json: async () => data });
  try {
    const calls = [];
    global.fetch = async (url, options) => {
      calls.push(url); assert.equal(options.signal, controller.signal);
      if (url.includes("pulls?")) return reply([{ number: 42 }]);
      if (url.includes("/files?")) return reply(files);
      if (url.includes("check-runs")) return reply({ total_count: 1, check_runs: passed });
      if (url.includes("/status?")) return reply({ total_count: 0, statuses: [] });
      return reply(detail);
    };
    let progress;
    const result = await demo.fetchPreview("example/project", { signal: controller.signal, onProgress: (...args) => { progress = args; } });
    assert.equal(result.items.length, 1); assert.deepEqual(result.warnings, []); assert.deepEqual(progress, [1, 1]); assert.equal(calls.length, 5);

    global.fetch = async (url) => {
      if (url.includes("pulls?")) return reply([{ number: 42 }, { number: 43 }]);
      if (url.includes("/43")) return reply({}, 500);
      if (url.includes("/files?")) return reply(files);
      if (url.includes("check-runs")) return reply({}, 403);
      if (url.includes("/status?")) return reply({ total_count: 0, statuses: [] });
      return reply(detail);
    };
    const partial = await demo.fetchPreview("example/project");
    assert.equal(partial.items.length, 1); assert.equal(partial.requested, 2);
    assert.equal(partial.items[0].checksKnown, false);
    assert.ok(partial.warnings.some((warning) => warning.includes("#43 wasn't analyzed")));
    assert.ok(partial.warnings.some((warning) => warning.includes("CI data for #42")));

    global.fetch = async (url) => {
      if (url.includes("pulls?")) return reply([{ number: 42 }]);
      if (url.includes("/files?")) return reply(files);
      return reply({ ...detail, changed_files: 105 });
    };
    await assert.rejects(() => demo.fetchPreview("example/project"), /100-file preview limit/);
    global.fetch = async () => reply({}, 403, "0");
    await assert.rejects(() => demo.fetchPreview("example/project"), /request limit/);
    global.fetch = async () => reply({}, 404);
    await assert.rejects(() => demo.fetchPreview("example/project"), /couldn't find/);
    global.fetch = async () => reply([]);
    assert.deepEqual(await demo.fetchPreview("example/project"), { items: [], warnings: [], requested: 0 });
    controller.abort();
    await assert.rejects(() => demo.fetchPreview("example/project", { signal: controller.signal }), { name: "AbortError" });
  } finally { global.fetch = originalFetch; }
}
networkChecks().then(() => console.log("Demo checks passed: scoring, sample, plans, links, partial scans, and errors.")).catch((error) => { console.error(error); process.exitCode = 1; });
