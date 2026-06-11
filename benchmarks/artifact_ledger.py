"""Phase 12.9a - Generated Artifact Ledger.

Separates the files changed during a benchmark run into clear categories so a
report no longer conflates the intended patch with runtime/validation output:

* ``patched_files``        - files the patch intentionally changed
                             (i.e. listed in ``expected_changed_files``).
* ``generated_artifacts``  - files created/modified by validation or runtime
                             output, either explicitly listed in the case config
                             via ``allowed_generated_files`` or recognized as a
                             narrow benchmark build artifact.
* ``unexpected_mutations`` - changed files that are neither patched nor allowed
                             generated artifacts (and are not forbidden).

Strictness rules (do NOT loosen):
* ``allowed_generated_files`` must never override ``forbidden_changed_files``.
  A file in both lists is excluded from ``generated_artifacts`` so it cannot be
  laundered; the existing forbidden-file failure path still fires.
* ``allowed_generated_files`` remains exact-path only. Built-in generated
  artifact rules must stay narrow and must not hide source-root edits.

The classifier is pure and deterministic: every output list is sorted, and the
same inputs always produce the same output.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence


_GENERATED_BUILD_DIRS = {"bin", "obj"}


def _as_set(value: Any) -> set[str]:
    if not value:
        return set()
    return {str(v) for v in value}


def _normalized_parts(path: str | Path) -> list[str]:
    text = str(path).replace("\\", "/")
    return [part for part in text.split("/") if part and part != "."]


def is_generated_artifact_path(path: str | Path) -> bool:
    """Return True for benchmark build-output paths that are not source edits.

    .NET validation can create many files under ``bin`` and ``obj`` (assembly
    info, MSBuild editorconfig/cache files, dll/pdb/exe outputs). Those folders
    are generated build output inside benchmark case repos; source-root files
    such as ``Program.cs`` or ``src/App.AssemblyInfo.cs`` must remain visible.
    """
    parts = _normalized_parts(path)
    return any(part in _GENERATED_BUILD_DIRS for part in parts[:-1])


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
    generated_by_rule = {
        path for path in changed
        if is_generated_artifact_path(path)
    }

    patched = changed & expected
    # A generated artifact is an allowed file that actually changed, minus
    # anything forbidden (override guard) or already counted as a patch target.
    generated = (
        (changed & allowed_generated) | generated_by_rule
    ) - forbidden - expected
    # Unexpected = changed minus every accounted-for category (incl. forbidden,
    # which is reported separately via touched_forbidden_files).
    unexpected = changed - expected - allowed_generated - generated_by_rule - forbidden

    return {
        "patched_files": sorted(patched),
        "generated_artifacts": sorted(generated),
        "unexpected_mutations": sorted(unexpected),
    }
