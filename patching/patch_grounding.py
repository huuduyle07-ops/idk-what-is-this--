"""Phase 12.9 — Quote-only patch grounding.

A patch_candidate's ``target_snippet`` must appear *verbatim* in real source
text — the target file on disk, or retrieved source context — before it is
accepted as a candidate. The patch writer can hallucinate target snippets that
do not exist in the source (e.g. proposing ``for i, customer in enumerate(...)``
against a file that actually contains ``df_report = df.iloc[1:11]``). The
apply-time gate would refuse such a patch, but the *generated patch result*
would still present the hallucinated snippet as a candidate, which is
misleading.

This module makes candidates quote-grounded *before* they are accepted:

* :func:`source_snippet_exists` / :func:`validate_patch_candidate_grounding`
  are re-exported from :mod:`core.validator` — the single, centralized,
  exact-substring grounding primitives (no fuzzy matching).
* :func:`enforce_patch_candidate_grounding` applies the rejection consequences
  to a patch-result block: it marks an ungrounded candidate invalid, nulls
  ``patch_plan``, lowers confidence (and control confidence), and records the
  human-readable warning.

Valid exact snippets are preserved untouched.
"""
from __future__ import annotations

from typing import Any

from core.validator import (
    UNGROUNDED_PATCH_CANDIDATE_WARNING as UNGROUNDED_WARNING,
    GroundingResult,
    source_snippet_exists,
    validate_patch_candidate_grounding,
)

__all__ = [
    "UNGROUNDED_WARNING",
    "GroundingResult",
    "source_snippet_exists",
    "validate_patch_candidate_grounding",
    "enforce_patch_candidate_grounding",
]


def _ungrounded_issue(candidate: dict) -> dict:
    """A structured issue mirroring the repo's existing policy-issue shape."""
    return {
        "severity": "high",
        "type": "policy",
        "file": candidate.get("relative_path") or candidate.get("file") or "",
        "symbol": candidate.get("target_node_name") or "",
        "reason": UNGROUNDED_WARNING,
        "fix": (
            "Copy target_snippet byte-exactly from the real source file or the "
            "retrieved source context, or drop the patch."
        ),
    }


def enforce_patch_candidate_grounding(
    block: dict,
    source_text_or_files: Any,
) -> GroundingResult:
    """Quote-ground ``block['patch_candidate']`` against real source, in place.

    ``block`` is a patch-result dict (the structured ``json_block``):
    ``patch_candidate``, ``patch_plan``, ``confidence``, ``issues``, ...

    On success the block is left untouched (valid candidates are preserved).

    On failure the candidate is scrubbed so a hallucinated snippet can never
    surface as a valid patch:
      * the candidate is marked invalid (``rejected`` / ``reject_reason``),
      * ``patch_plan`` is set to ``None``,
      * ``confidence`` (and ``control_confidence`` if present) is lowered to 0,
      * ``needs_escalation`` is set, and
      * the human-readable :data:`UNGROUNDED_WARNING` is recorded as both an
        issue and a warning.

    Returns the :class:`GroundingResult` for the candidate.
    """
    if not isinstance(block, dict):
        return GroundingResult(True, "no patch result block to ground")

    candidate = block.get("patch_candidate")
    if not isinstance(candidate, dict):
        # Nothing to ground (e.g. a patch_plan result, handled elsewhere).
        return GroundingResult(True, "no patch_candidate present")

    result = validate_patch_candidate_grounding(candidate, source_text_or_files)
    if result.is_grounded:
        return result

    # Ungrounded → reject. Prefer exact quote grounding over semantic guessing,
    # so we never invent or fuzzy-match a replacement here.
    candidate["rejected"] = True
    candidate.setdefault("reject_reason", UNGROUNDED_WARNING)

    block["patch_plan"] = None
    block["confidence"] = 0.0
    if "control_confidence" in block:
        block["control_confidence"] = 0.0
    block["needs_escalation"] = True

    issues = block.setdefault("issues", [])
    if not any(
        isinstance(i, dict) and i.get("reason") == UNGROUNDED_WARNING for i in issues
    ):
        issues.insert(0, _ungrounded_issue(candidate))

    warnings = block.setdefault("warnings", [])
    if UNGROUNDED_WARNING not in warnings:
        warnings.append(UNGROUNDED_WARNING)

    return result
