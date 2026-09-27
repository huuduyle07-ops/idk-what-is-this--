from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Any

from core.patch_basis import (
    PATCH_BASIS_GROUNDED_DEFECT,
    has_legitimate_patch_basis,
    normalize_patch_basis,
)

PatchStyle = Literal["safe_minimal", "balanced", "vibe"]


@dataclass(frozen=True)
class PatchPolicy:
    style: PatchStyle
    allow_new_api: bool
    allow_multifile_patch: bool
    allow_statement_level_patch: bool
    require_exact_target_match: bool
    require_validation_for_apply: bool
    patch_basis: str
    patch_basis_accepted: bool
    auto_apply_allowed: bool
    human_approval_required: bool
    prompt_rules: list[str]


def normalize_patch_style(value: str | None) -> PatchStyle:
    value = (value or "").strip().lower()

    aliases = {
        "safe": "safe_minimal",
        "safe_minimal": "safe_minimal",
        "minimal": "safe_minimal",
        "balanced": "balanced",
        "normal": "balanced",
        "vibe": "vibe",
        "creative": "vibe",
        "vibe_creative": "vibe",
    }

    return aliases.get(value, "safe_minimal")


def build_patch_policy(
    style: str | None,
    *,
    repo_manifest: dict[str, Any] | None = None,
    language: str = "unknown",
    has_validation_command: bool = False,
    patch_confidence: float = 0.0,
    defect_grounded: bool = False,
    patch_basis: str | None = None,
    control_confidence: float = 0.0,
) -> PatchPolicy:
    """Build patch/apply policy from patch facts, never localization rank.

    ``control_confidence`` remains in the call signature so historical callers
    and replay artifacts stay readable.  It is the deprecated CONTROL
    localization value and intentionally grants nothing.  ``patch_confidence``
    is the model patch writer's separate self-assessment. ``patch_basis`` is the
    typed reason a patch may be considered.  ``defect_grounded`` remains as a
    compatibility input for historical callers and projects only to
    ``grounded_defect``; it is not the conceptual policy input for new callers.

    A legitimate basis is still not auto-apply authority.  In particular an
    ``explicit_change_request`` is accepted for patch-safety/human review but
    never enables automatic application here.
    """
    del control_confidence
    patch_style = normalize_patch_style(style)
    repo_manifest = repo_manifest or {}
    effective_patch_basis = normalize_patch_basis(patch_basis)
    if patch_basis is None and defect_grounded:
        effective_patch_basis = PATCH_BASIS_GROUNDED_DEFECT
    patch_basis_accepted = has_legitimate_patch_basis(effective_patch_basis)
    defect_basis = effective_patch_basis == PATCH_BASIS_GROUNDED_DEFECT

    repo_warnings = repo_manifest.get("warnings", [])
    primary_language = repo_manifest.get("primary_language", language)

    if patch_style == "safe_minimal":
        return PatchPolicy(
            style="safe_minimal",
            allow_new_api=False,
            allow_multifile_patch=False,
            allow_statement_level_patch=True,
            require_exact_target_match=True,
            require_validation_for_apply=False,
            patch_basis=effective_patch_basis,
            patch_basis_accepted=patch_basis_accepted,
            auto_apply_allowed=(
                defect_basis
                and patch_confidence >= 0.75
                and primary_language != "unknown"
            ),
            human_approval_required=True,
            prompt_rules=[
                "Use only APIs, fields, functions, and classes already present in the provided context.",
                "Do not introduce new fields, methods, classes, imports, or framework assumptions.",
                "Prefer the smallest single-file edit.",
                "If a safe patch requires missing context, set needs_escalation=true.",
            ],
        )

    if patch_style == "balanced":
        return PatchPolicy(
            style="balanced",
            allow_new_api=False,
            allow_multifile_patch=False,
            allow_statement_level_patch=True,
            require_exact_target_match=True,
            require_validation_for_apply=True,
            patch_basis=effective_patch_basis,
            patch_basis_accepted=patch_basis_accepted,
            auto_apply_allowed=(
                defect_basis
                and patch_confidence >= 0.8
                and primary_language != "unknown"
                and has_validation_command
            ),
            human_approval_required=True,
            prompt_rules=[
                "You may propose a design-level fix, but patch_candidate must stay grounded in existing code.",
                "Do not introduce unknown APIs in patched_snippet unless they are visible in repo context.",
                "If the correct fix requires a new API or new field, return a plan or needs_escalation=true.",
                "Prefer single-file edits unless evidence clearly requires more.",
            ],
        )

    # vibe / creative
    return PatchPolicy(
        style="vibe",
        allow_new_api=True,
        allow_multifile_patch=True,
        allow_statement_level_patch=True,
        require_exact_target_match=True,
        require_validation_for_apply=True,
        patch_basis=effective_patch_basis,
        patch_basis_accepted=patch_basis_accepted,
        auto_apply_allowed=False,
        human_approval_required=True,
        prompt_rules=[
            "You may propose broader changes, new fields, or new helper APIs if they serve the user's goal.",
            "Clearly mark assumptions.",
            "If adding a new API, include all files that must change.",
            "Do not auto-apply creative patches; produce a reviewable patch or plan.",
            "Prefer validation before applying.",
        ],
    )


def policy_to_prompt_block(policy: PatchPolicy) -> str:
    lines = [
        f"PATCH STYLE: {policy.style}",
        f"- allow_new_api: {policy.allow_new_api}",
        f"- allow_multifile_patch: {policy.allow_multifile_patch}",
        f"- patch_basis: {policy.patch_basis}",
        f"- patch_basis_accepted: {policy.patch_basis_accepted}",
        f"- auto_apply_allowed: {policy.auto_apply_allowed}",
        f"- human_approval_required: {policy.human_approval_required}",
        "",
        "Patch style rules:",
    ]
    lines.extend(f"- {rule}" for rule in policy.prompt_rules)
    return "\n".join(lines)
