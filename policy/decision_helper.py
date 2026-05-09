from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Any

PatchStyle = Literal["safe_minimal", "balanced", "vibe"]


@dataclass(frozen=True)
class PatchPolicy:
    style: PatchStyle
    allow_new_api: bool
    allow_multifile_patch: bool
    allow_statement_level_patch: bool
    require_exact_target_match: bool
    require_validation_for_apply: bool
    auto_apply_allowed: bool
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
    control_confidence: float = 0.0,
) -> PatchPolicy:
    patch_style = normalize_patch_style(style)
    repo_manifest = repo_manifest or {}

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
            auto_apply_allowed=(
                control_confidence >= 0.75
                and primary_language != "unknown"
            ),
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
            auto_apply_allowed=(
                control_confidence >= 0.8
                and primary_language != "unknown"
                and has_validation_command
            ),
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
        auto_apply_allowed=False,
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
        f"- auto_apply_allowed: {policy.auto_apply_allowed}",
        "",
        "Patch style rules:",
    ]
    lines.extend(f"- {rule}" for rule in policy.prompt_rules)
    return "\n".join(lines)