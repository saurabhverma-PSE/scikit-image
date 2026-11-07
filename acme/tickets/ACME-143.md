
# ACME-143: Improve threshold_triangle migration guidance

## Context

The `threshold_triangle` function is transitioning from the `nbins`
parameter to `n_bins`.

New contributors need clear documentation explaining the preferred
parameter name and the compatibility behavior during migration.

## Requested change

Inspect the existing function documentation and relevant repository
conventions. Propose a minimal documentation improvement that explains:

- `n_bins` is the preferred parameter name.
- Existing `nbins` usage remains supported during the deprecation window.
- The migration should not change threshold computation behavior.

## Acceptance criteria

1. Identify the relevant source and documentation files.
2. Follow existing scikit-image documentation conventions.
3. Preserve backward compatibility.
4. Identify appropriate documentation or test validation.
5. Produce an implementation plan for human review.

## Scope

Planning only for this demonstration. Do not edit implementation,
documentation, or test files without explicit approval.
