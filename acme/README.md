# Acme Engineering — First Contribution POC

## Problem

Acme's new engineers can spend 3–4 weeks making their first clean contribution to a convention-heavy library. Repeated review findings, compatibility mistakes, and inconsistent testing slow onboarding and increase reviewer workload.

This POC demonstrates how Cursor can help engineers plan, implement, review, and validate a safe first contribution while keeping consequential decisions under human control.

## Solution

The workflow combines:

1. **Cursor Rules** — Persistent engineering guardrails in `.cursor/rules/engineering-guardrails.mdc`.
2. **Cursor Skill** — A repeatable first-contribution planning workflow in `.cursor/skills/first-contribution/SKILL.md`.
3. **Cursor Cloud Agents** — Implementation of an explicitly approved plan.
4. **Cursor PR Review Automation** — Automated review of proposed changes and potential defects.
5. **GitHub Actions** — Ruff and focused regression tests.
6. **Acme Engineering Concierge** — A hosted Grok Bot front door for discovering work, checking status, requesting changes, and coordinating approved actions.

## Working Example: ACME-142

The synthetic ticket `acme/tickets/ACME-142.md` requests a backward-compatible parameter rename in scikit-image's `threshold_triangle` API.

The approved plan is recorded in `acme/plans/ACME-142-approved.md`.

- [PR #1](https://github.com/saurabhverma-PSE/scikit-image/pull/1) — Cursor Cloud Agent implementation, regression tests, automated review, and CI.
- [PR #2](https://github.com/saurabhverma-PSE/scikit-image/pull/2) — Experimental deprecation checker, intentionally not included in required CI.
- [PR #3](https://github.com/saurabhverma-PSE/scikit-image/pull/3) — CI workflow improvements, merged into the POC integration branch.

The CI workflow is `.github/workflows/acme-ci.yml`.

## Human Approval and Safety

The first-contribution Skill stops after producing a contribution plan. Implementation requires explicit engineer authorization.

The Concierge also requests authorization before executing consequential repository operations.

GitHub branch protection independently requires an approving review and the `Tests and Ruff` status check before merging into `poc/first-contribution-workflow`.

The POC uses the owner's GitHub identity for Concierge operations; it does not establish a separate service identity or independently auditable Bot authorization record. An eligible second reviewer has not been configured.

## How to Reproduce

1. Open the scikit-image fork in Cursor.
2. Read the ACME-142 ticket and invoke the `first-contribution` Skill to produce a plan.
3. Review the approved plan and PR #1's implementation.
4. Inspect the Cursor automated review and GitHub Actions results.
5. Open Acme Engineering Concierge to ask for ACME-142's status and next steps.
6. Verify that PR #1 remains open and blocked pending human review.

For local validation, use the project's configured Python environment:

```bash
python -m pytest -q tests/skimage/filters/test_thresholding.py tests/skimage2/filters/test_thresholding.py tests/skimage/test_migration.py
```

GitHub Actions also runs Ruff and focused tests on relevant pull requests.

## Live, Synthetic, and Not Implemented

| Component | Status |
|---|---|
| scikit-image repository, code changes, tests, GitHub CI | Live |
| Cursor Cloud Agent implementation and PR review | Live |
| Acme Engineering Concierge | Live, hosted outside this repository |
| ACME-142 ticket and Acme organization | Synthetic |
| Cursor API demonstration | Separate project at `~/Projects/cursor-sa-demo` |
| Production deployment | Not implemented |
| Release/staging approval | Conceptual only |
| Dependency/import boundary enforcement | Not implemented |

## Known Limitations and Next Steps

- CI uses a fixed set of ACME-142 test files rather than selecting tests dynamically.
- The Rule and Skill guide agent behavior but do not technically enforce every repository or data-access boundary.
- Production use would require scoped service credentials, independently attributable approvals, and stronger access controls.
- The experimental checker in PR #2 is not production-ready.
- A real deployment workflow would require environment-specific checks, deployment permissions, and release approval.

The intended production path is: **approved plan → implementation → automated review → tests/CI → independent human review → merge → controlled release**. The POC demonstrates the workflow through the pre-merge approval gate; deployment remains a documented extension.