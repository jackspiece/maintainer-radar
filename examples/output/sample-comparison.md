# Queue snapshot comparison

Before: 3 PRs. After: 3 PRs.

Newly observed: 1. No longer observed: 1. Changed: 1. Unchanged in compared fields: 1.

- Snapshots may cover different filters, scan limits, hydration, times, configurations, or Radar versions; queue JSON does not record that provenance. Compare equivalent captures where possible.
- Newly observed and no longer observed describe only these snapshots. Absence does not establish that a pull request was closed or merged.
- Score and action differences are saved observations, not proof of code progress or a cause of change. No records are re-scored and no network requests are made.

Compared fields: title, action, risk, reviewability, next_step, checks, flags, signals.

## Newly observed

- [#45 Test empty cache responses](<https://github.com/example/project/pull/45>): review now; risk 0; reviewability 100.

## No longer observed

- [#43 Add universal plugin system](<https://github.com/example/project/pull/43>): ask for CI fix; risk 100; reviewability 0.

## Changed observations

### [#42 Fix parser cache race](<https://github.com/example/project/pull/42>)

| Field | Before | After |
| --- | --- | --- |
| action | ask for CI fix | review now |
| risk | 30 | 0 |
| reviewability | 70 | 100 |
| next_step | Ask the author to get failing checks green before deeper review&#46; | Review now while the PR appears small&#44; active&#44; and low risk&#46; |
| checks | &#123;&#34;failed&#34;&#58; 1&#44; &#34;passed&#34;&#58; 0&#44; &#34;pending&#34;&#58; 0&#44; &#34;skipped&#34;&#58; 0&#44; &#34;total&#34;&#58; 1&#125; | &#123;&#34;failed&#34;&#58; 0&#44; &#34;passed&#34;&#58; 2&#44; &#34;pending&#34;&#58; 0&#44; &#34;skipped&#34;&#58; 0&#44; &#34;total&#34;&#58; 2&#125; |
| flags | &#91;&#34;CI failing&#34;&#44; &#34;incomplete file list&#34;&#93; | &#91;&#34;incomplete file list&#34;&#93; |
| signals | &#91;&#34;mergeable&#34;&#44; &#34;review requested&#34;&#44; &#34;review required&#34;&#44; &#34;test plan present&#34;&#44; &#34;tests changed&#34;&#93; | &#91;&#34;CI passed&#34;&#44; &#34;mergeable&#34;&#44; &#34;review requested&#34;&#44; &#34;review required&#34;&#44; &#34;test plan present&#34;&#44; &#34;tests changed&#34;&#93; |
