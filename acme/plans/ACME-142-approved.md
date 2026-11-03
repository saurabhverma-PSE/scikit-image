ACME-142 — Approved Contribution Plan
Status: Approved for implementation by the engineer.

Scope: Synthetic onboarding exercise in a personal fork. Not an upstream scikit-image contribution.

Approved decisions:
- Deprecation window: 0.27 → 0.29.
- Preserve old positional and keyword callers during deprecation.
- Limit changes to threshold_triangle.
- Human review required before merging.
1. Task summary
Standardize the bin-count argument of threshold_triangle from nbins to n_bins. Keep current numeric results and keep existing callers working through a compatibility path. Update tests and the docs this repository uses for a parameter deprecation. Do not weaken validation.
2. AI policy and this exercise
Confirmed policy, in CONTRIBUTING.md under (ai-policy)= (included by doc/source/development/contribute.md). .github/PULL_REQUEST_TEMPLATE.md points at the same section.

The policy applies when a human author wants scikit-image maintainers to review a contribution. It says the human must understand the change; check in before significant LLM use that will be reviewed; not use AI to invent novel algorithms or to decide what to test; not use AI to write PR descriptions or issue/PR comments. Allowed uses include exploring the codebase, mechanical edits, and trivial reviewable changes. If a PR is submitted, the human must declare tool use, write the description by hand, separate AI commits and tag them Assisted-by:, keep AI changes trivial to review, accept copyright responsibility, and answer review questions personally.

Implications here:

This ticket is a local exercise. No upstream PR, issue comment, or maintainer review is in scope. Disclosure, hand-written PR text, and Assisted-by: tags are required only if you later choose to submit the work upstream. This plan does not do that.

The rename uses the existing deprecate_parameter decorator. That is a mechanical API edit, which the policy allows AI to help with. The human still approves the plan and owns the result.

You specified the behaviors to test (section 7). That is the test decision the policy assigns to a human. Implementation after approval may add the scaffolding for those cases. It should not add extra test ideas.

Do not retitle this work as an upstream scikit-image fix.
3. Change classification and risk
Public API rename with a deprecation cycle. Medium risk.

Confirmed: src/skimage/filters/thresholding.py re-exports the _skimage2 function. doc/source/development/deprecations.md requires a cycle for a keyword rename and names deprecate_parameter. pyproject.toml sets filterwarnings = ["error", ...], so an unexpected FutureWarning fails tests. tests/skimage/test_migration.py snapshots the public signature; inspect.signature follows wrapped and records <DEPRECATED> defaults, as it already does for rolling_ball.

No new dependency, security boundary, or CI config change.
4. Repository evidence
Implementation is only src/_skimage2/filters/thresholding.py: threshold_triangle(image, nbins=256) passes nbins to histogram(...). Integer images ignore that count; the body then uses nbins = len(hist). try_all_threshold calls it with the image only.

Other threshold functions and histogram still use nbins. Do not rename them. The ticket names only threshold_triangle.

Pattern to copy: @deprecate_parameter("num_threads", new_name="workers", start_version="0.26", stop_version="0.28") in src/_skimage2/restoration/_rolling_ball.py. Old default is DEPRECATED. The decorator emits FutureWarning, copies the old value onto the new name, and raises ValueError if both names are passed. modify_docstring=True adds the old name under Other Parameters.

Call sites that pass nbins= are test_triangle_float_images in both tests/skimage/filters/test_thresholding.py and tests/skimage2/filters/test_thresholding.py. Both suites run. No in-repo positional nbins call. External callers can still pass the second positional argument.

User-facing docs for this function are its docstring. No gallery page or .pyi signature mentions nbins.
5. Version labels
Evidence:

Both src/skimage/init.py and src/_skimage2/init.py set __version__ = '0.27.0rc2.dev0'. pyproject.toml marks version dynamic, so those strings are the package version.

Every deprecate_parameter start_version / stop_version in src/ is 0.x. .. versionadded:: directives in _skimage2 are 0.x. The deprecation opened on this dev line, threshold_rel in src/_skimage2/feature/blob.py, uses start_version="0.27" and stop_version="0.29". TODO.txt records that removal under Version 0.29. The same file's Version 0.28 entries match decorators whose stop version is 0.28 (rolling_ball, cycle_spin).

doc/source/skips/4-transition-to-v2.rst says the package version becomes 2.0.0 only when skimage2 leaves experimental status. That has not happened: the version is still 0.27.0rc2.dev0.

The conflicting text is the title of doc/source/release_notes/release_dev.rst: scikit-image 2.7.0rc0. A repo search shows 2.7.0 only in that file. doc/source/development/deprecations.md also names a path that does not exist (doc/release/release_dev.rst); the file that exists is doc/source/release_notes/release_dev.rst, and its API Changes section is where threshold_rel was recorded.

Recommendation, which this plan will follow unless you reject it: decorator start_version="0.27", stop_version="0.29"; docstring versionadded 0.27; release note says 0.27; TODO.txt item under the existing Version 0.29 heading. Do not retitle release_dev.rst and do not write 2.7 into the warning. The warning text is what users see, and it must match __version__ and the other decorators.

Alternatives, only if you reject that:

Use 0.28 / 0.30 on the theory that 0.27.0rc2 is frozen. Evidence against that: __version__ still ends in .dev0, and threshold_rel already starts at 0.27 in this unreleased cycle. There is no Version 0.30 section.

Use 2.7 in the decorator to match the release-note title. That would disagree with __version__, SKIP 4, and every existing decorator.

No further version fact in the tree resolves the 2.7.0rc0 title. Approving this plan accepts 0.27 / 0.29 and leaves the title untouched.
6. Proposed implementation
In src/_skimage2/filters/thresholding.py:

@deprecate_parameter("nbins", new_name="n_bins", start_version="0.27", stop_version="0.29")

def threshold_triangle(image, nbins=DEPRECATED, *, n_bins=256)

Pass n_bins into histogram. Keep the later local length used by the triangle math.

Document n_bins in Parameters, including the existing "ignored for integer arrays" sentence and .. versionadded:: 0.27. Leave nbins to the decorator's Other Parameters section.

nbins stays the second positional parameter so old positional calls warn and still forward the value. n_bins is keyword-only. No change to the skimage re-export, try_all_threshold, histogram, or other threshold_* functions.
7. Validation criteria
Pytest already treats warnings as errors. Assert these cases for both skimage.filters.threshold_triangle and _skimage2.filters.threshold_triangle:

Old keyword: threshold_triangle(image, nbins=N) returns the same value as n_bins=N and emits one FutureWarning whose message names nbins and n_bins.

Old positional: threshold_triangle(image, N) returns that same value and emits one FutureWarning.

New keyword: threshold_triangle(image, n_bins=N) returns that value and emits no warning.

Default: threshold_triangle(image) matches today's default (256) and emits no warning.

Conflict: nbins together with n_bins (keyword plus keyword, and positional plus n_bins=) raises ValueError.

Unchanged numbers, same expectations already in the tests: uniform images 0, 1, 2; uint images 151, 104, 80, 175; float images with the same int_bins count still round to 104 and 151; the flip test still requires unequal pixels under 1e-2. Float tests call n_bins=, not nbins=, so the main path does not warn.

try_all_threshold stays a one-argument call and must not warn.

Signature snapshot in tests/skimage/test_migration.py becomes threshold_triangle(image, nbins=<DEPRECATED>, *, n_bins=256).

Do not add a global filter for this warning. Do not change filterwarnings.

After approval, run tests/skimage/filters/test_thresholding.py, tests/skimage2/filters/test_thresholding.py, and tests/skimage/test_migration.py::test_public_skimage_api with the repo's existing spin test setup if it is already built. Do not install dependencies as part of planning. The docstring example calls threshold_triangle(image) and should stay valid.
8. Files likely to change
src/_skimage2/filters/thresholding.py

tests/skimage/filters/test_thresholding.py

tests/skimage2/filters/test_thresholding.py

tests/skimage/test_migration.py

doc/source/release_notes/release_dev.rst — one API Changes bullet, no invented PR link

TODO.txt — removal note under Version 0.29
9. Compatibility, security, and scope
Default 256 and integer-image behavior stay. Old callers work and warn until 0.29. Both names at once is an error, which is the decorator's existing rule. No security or data-boundary change. No upstream submission.
10. Approval record
Human Gate #1: Approved for implementation by the engineer.

Approved decisions:
- Use start_version="0.27" and stop_version="0.29"; leave the existing release_dev.rst title unchanged.
- Preserve nbins as the second positional parameter during the deprecation window; old positional and keyword calls warn and continue working.
- Make n_bins keyword-only.
- Limit changes to the ACME-142 scope; do not rename other nbins APIs.
- Implement the validation criteria in Section 7 without weakening existing checks.
- Require human review before merging.
Implementation may proceed against this approved plan. No upstream submission is authorized.