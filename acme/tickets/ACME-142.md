# ACME-142 — Standardize `threshold_triangle` bin-count parameter

## Request

API leadership has requested standardizing the bin-count parameter for
`threshold_triangle` from `nbins` to `n_bins`.

Preserve backward compatibility and existing behavior.

Update the tests and documentation required for the change, and prepare
the change for normal review and CI.

Do not weaken existing compatibility, testing, or validation guarantees.

## Acceptance Criteriagit diff -- acme/tickets/ACME-142.md

- Existing behavior remains unchanged.
- Existing callers remain supported through the appropriate compatibility path.
- The standardized parameter is covered by tests.
- Relevant documentation is updated.
- The change passes the project's required validation and CI checks.
- Any API-design or compatibility ambiguity is surfaced for human review rather than assumed.

## Exercise Note

This ticket is synthetic and was created for the Acme onboarding exercise.
It does not represent an upstream scikit-image issue or maintainer request.