"""Phase 12.9a - Generated Artifact Ledger.

Separates the files changed during a benchmark run into clear categories so a
report no longer conflates the intended patch with runtime/validation output:

* ``patched_files``        - files the patch intentionally changed
                             (i.e. listed in ``expected_changed_files``).
* ``generated_artifacts``  - files created/modified by validation or runtime
                             output AND explicitly allowed by the case config
                             via ``allowed_generated_files``.
* ``unexpected_mutations`` - changed files that are neither patched nor allowed
                             generated artifacts (and are not forbidden).

Strictness rules (do NOT loosen):
* ``allowed_generated_files`` must never override ``forbidden_changed_files``.
  A file in both lists is excluded from ``generated_artifacts`` so it cannot be
  laundered; the existing forbidden-file failure path still fires.
* Exact file paths only. No glob/pattern expansion in v1.

The classifier is pure and deterministic: every output list is sorted, and the
same inputs always produce the same output.
"""
from __future__ import annotations

from typing import Any, Sequence


def _as_set(value: Any) -> set[str]:
    if not value:
        return set()
    return {str(v) for v in value}


def classify_changed_files(
    case: dict[str, Any],
    changed_files: Sequence[str],
) -> dict[str, list[str]]:
    """Classify ``changed_files`` into the artifact-ledger categories.

    Returns a dict with sorted ``patched_files``, ``generated_artifacts`` and
    ``unexpected_mutations`` lists. Forbidden files are intentionally excluded
    from every bucket here - they keep their dedicated
    ``forbidden_changed_files`` category and failure signal elsewhere - so
    ``allowed_generated_files`` can never reclassify a forbidden change as
    benign.
    """
    changed = _as_set(changed_files)
    expected = _as_set(case.get("expected_changed_files"))
    forbidden = _as_set(case.get("forbidden_changed_files"))
    allowed_generated = _as_set(case.get("allowed_generated_files"))

    patched = changed & expected
    # A generated artifact is an allowed file that actually changed, minus
    # anything forbidden (override guard) or already counted as a patch target.
    generated = (changed & allowed_generated) - forbidden - expected
    # Unexpected = changed minus every accounted-for category (incl. forbidden,
    # which is reported separately via touched_forbidden_files).
    unexpected = changed - expected - allowed_generated - forbidden

    return {
        "patched_files": sorted(patched),
        "generated_artifacts": sorted(generated),
        "unexpected_mutations": sorted(unexpected),
    }
