---
name: first-contribution
description: Guide a new engineer from an assigned ticket to a safe, reviewable contribution plan before implementation.
---

# First Contribution

Use this workflow when an engineer is preparing a first contribution to this repository.

The goal is to understand enough of the current codebase to propose a safe change without requiring the engineer to learn the entire repository first.

## 1. Understand the task

Read the assigned ticket and identify:

- requested outcome
- acceptance criteria
- explicit constraints
- unclear or missing requirements

Do not assume implementation details that are not stated in the ticket.

## 2. Classify the change

Determine the likely change type and risk.

Consider whether the task affects:

- public APIs
- backward compatibility
- security or data boundaries
- dependencies
- configuration
- tests
- documentation
- CI or deployment behavior

Explain why the change is low, medium, or high risk.

## 3. Inspect the current repository

Before proposing an implementation, inspect the current checkout to discover:

- where the relevant behavior is implemented
- public and internal surfaces affected by the change
- existing repository conventions
- similar implementations or prior patterns
- relevant tests and test structure
- documentation requirements
- validation, linting, and CI expectations

Prefer evidence from the current repository over assumptions or remembered conventions.

Do not inspect unrelated areas without a task-specific reason.

## 4. Analyze compatibility and boundaries

Identify:

- existing callers or interfaces that could be affected
- backward-compatibility requirements
- deprecated or legacy behavior that must be preserved
- repository or contribution policies relevant to the task
- context, code, or dependencies that fall outside the approved scope

If the repository contains conflicting patterns or the safe approach is unclear, surface the conflict rather than choosing silently.

## 5. Propose validation

Define how the change should be checked before implementation.

Include, where relevant:

- focused tests for the changed behavior
- regression or compatibility tests
- broader affected test suites
- formatting or lint checks
- repository-specific validation
- CI checks

Never propose weakening an existing check to make the change pass.

## 6. Produce a contribution plan

Return a concise plan containing:

1. Task summary
2. Change classification and risk
3. Repository evidence discovered
4. Proposed implementation approach
5. Files or surfaces likely to change
6. Compatibility considerations
7. Test and validation plan
8. Documentation or change-management requirements
9. Security or context-boundary considerations
10. Open questions or decisions requiring human judgment

Distinguish confirmed repository facts from recommendations or assumptions.

## 7. Human approval gate

STOP after producing the contribution plan.

Do not modify source code, tests, documentation, configuration, or dependencies until the engineer explicitly approves the plan.

If the engineer requests changes to the plan, revise the plan and stop again for approval.

Implementation begins only after explicit human approval.