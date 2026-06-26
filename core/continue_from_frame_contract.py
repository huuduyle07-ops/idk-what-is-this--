"""UX.3 — Continue-from-Frame Contract (report-only).

Defines the contract for "Continue from Frame." A frame is a reusable snapshot
of operator-facing run context. UX.3 specifies what a frame is, what context
can be carried forward, what context must be excluded, what human confirmation
is required, what continuation modes are allowed, and how the UI should present
continuation in the future.

Core principle: UX.3 defines the continuation contract only. It does not
implement actual continuation execution, start a run from history, call models,
apply patches, run validation, run benchmarks, contact network services, launch
workers, mutate the repo, push, merge, or open PRs.

This module is stdlib-only and pure apart from ``write_continue_from_frame_artifacts``
(which writes two report files). All analysis functions are side-effect-free.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "continue_from_frame_contract"

CONTRACT_STATUS_READY       = "ready_for_review"
CONTRACT_STATUS_NEEDS_INPUT = "needs_more_input"
CONTRACT_STATUS_BLOCKED     = "blocked"

JSON_NAME = "continue_from_frame_contract.json"
MD_NAME   = "continue_from_frame_contract.md"

#: Allowed source types for a frame.
ALLOWED_SOURCE_TYPES: tuple[str, ...] = (
    "manual",
    "run_timeline",
    "replay",
    "benchmark_report",
    "commander_report",
    "evidence_pack",
    "unknown",
)

#: Allowed continuation modes (safe, review-only).
ALLOWED_CONTINUATION_MODES: tuple[str, ...] = (
    "ask_about_frame",
    "continue_planning",
    "draft_next_patch_plan",
    "compare_with_current",
    "open_evidence_review",
    "create_commander_contract",
)

#: Forbidden continuation modes (would bypass human review or execute tasks).
FORBIDDEN_CONTINUATION_MODES: tuple[str, ...] = (
    "auto_apply_patch",
    "auto_run_validation",
    "auto_run_benchmark",
    "auto_launch_worker",
    "auto_call_model",
    "auto_merge",
    "auto_push",
    "remote_execute",
)

#: Staleness class definitions.
STALENESS_CLASSES: dict[str, str] = {
    "fresh":          "Current repo state is known to match the frame source.",
    "possibly_stale": "Source exists but current repo match is not confirmed.",
    "stale":          "Source explicitly predates current repo changes.",
    "unknown":        "Insufficient evidence to determine freshness.",
}

GUARDRAIL_NOTE = (
    "Continue-from-Frame Contract is a report-only definition. "
    "UX.3 defines the continuation contract only. It does not implement actual "
    "continuation execution, start a run from history, call models, apply patches, "
    "run validation, run benchmarks, contact network services, launch workers, "
    "mutate the repo, push, merge, or open PRs. "
    "Human review and explicit approval are required before any action."
)

_BOUNDARIES: tuple[str, ...] = (
    "UX.3 defines the continuation contract only.",
    "UX.3 does not implement actual continuation execution.",
    "UX.3 does not start a run from history.",
    "UX.3 does not call models.",
    "UX.3 does not apply patches.",
    "UX.3 does not run validation.",
    "UX.3 does not run benchmarks.",
    "UX.3 does not contact network services.",
    "UX.3 does not launch workers.",
    "UX.3 does not mutate the repo.",
    "UX.3 does not push, merge, or open PRs.",
)

_FRAME_IS_NOT: tuple[str, ...] = (
    "a hidden agent state",
    "a resumable process",
    "a worker checkpoint",
    "an auto-execution token",
    "a permission to mutate files",
    "a permission to apply patches",
    "a permission to skip human review",
)

_REUSABLE_CONTEXT_ITEMS: tuple[str, ...] = (
    "user-facing task summary",
    "current answer summary",
    "patch summary",
    "changed file list",
    "evidence summary",
    "validation result summary",
    "benchmark result summary",
    "known blockers",
    "next recommended operator action",
    "safe artifact references",
)

_EXCLUDED_CONTEXT_ITEMS: tuple[str, ...] = (
    "secrets",
    "API keys",
    "tokens",
    "environment variables",
    "raw credentials",
    "hidden chain-of-thought",
    "unreviewed tool outputs",
    "raw shell/process output unless explicitly summarized",
    "stale patch bodies unless marked review-only",
    "absolute permission to mutate files",
    "auto-approval state",
    "background worker state",
)

_HUMAN_CONFIRMATION_REQUIRED_BEFORE: tuple[str, ...] = (
    "applying a patch",
    "running validation",
    "running benchmark",
    "launching a worker",
    "using external tools",
    "contacting network services",
    "committing",
    "push",
    "merge",
    "opening PRs",
)

_NEXT_UX_STEPS: tuple[str, ...] = (
    "UX.4 — Mixed Mode Intent Router Preview: classify operator intent into instant/commander/ask modes.",
    "UX.5 — Cockpit Panel Layout: implement the read-only operator cockpit defined in UX.1.",
    "UX.6 — Operator Feedback Loop: allow operators to annotate run results for future improvement.",
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _short_id(seed: str) -> str:
    return hashlib.sha1(seed.encode()).hexdigest()[:8]


# ── Frame normalisation ───────────────────────────────────────────────────────

def normalize_frame(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a fully populated frame from a raw dict (pure, no I/O)."""
    frame: dict[str, Any] = dict(raw)
    frame.setdefault("frame_id", _short_id(str(raw)))
    frame.setdefault("created_at", "")
    frame.setdefault("source_type", "unknown")
    frame.setdefault("source_run_id", "")
    frame.setdefault("source_artifacts", [])
    frame.setdefault("title", "Untitled Frame")
    frame.setdefault("task_summary", "")
    frame.setdefault("mode", "unknown")
    frame.setdefault("repo_path", ".")
    frame.setdefault("branch_hint", "")
    frame.setdefault("changed_files_summary", "")
    frame.setdefault("patch_summary", "")
    frame.setdefault("evidence_summary", "")
    frame.setdefault("validation_summary", "")
    frame.setdefault("benchmark_summary", "")
    frame.setdefault("decision_summary", "")
    frame.setdefault("reusable_context", list(_REUSABLE_CONTEXT_ITEMS))
    frame.setdefault("excluded_context", list(_EXCLUDED_CONTEXT_ITEMS))
    frame.setdefault("staleness_risk", "unknown")
    frame.setdefault("safety_flags", [])
    frame.setdefault("required_confirmations", list(_HUMAN_CONFIRMATION_REQUIRED_BEFORE))
    frame.setdefault("allowed_continuation_modes", list(ALLOWED_CONTINUATION_MODES))
    frame.setdefault("forbidden_continuation_modes", list(FORBIDDEN_CONTINUATION_MODES))
    frame.setdefault("next_operator_action", "Review this frame before choosing a continuation mode.")
    return frame


def build_default_frame(
    *,
    repo_path: str = ".",
    created_at: str = "",
    frame_id: str | None = None,
    title: str = "Default Frame",
    source_type: str = "manual",
) -> dict[str, Any]:
    """Build a default minimal frame (pure, no I/O)."""
    fid = frame_id or _short_id(f"default:{repo_path}:{created_at}")
    return normalize_frame({
        "frame_id": fid,
        "created_at": created_at,
        "source_type": source_type,
        "title": title,
        "repo_path": repo_path,
    })


# ── Staleness classification ──────────────────────────────────────────────────

def classify_frame_staleness(frame: dict[str, Any]) -> dict[str, Any]:
    """Classify frame staleness (pure, no I/O, no git commands)."""
    risk = frame.get("staleness_risk", "unknown")
    valid_classes = set(STALENESS_CLASSES.keys())
    staleness_class = risk if risk in valid_classes else "unknown"
    warning = ""
    if staleness_class == "stale":
        warning = (
            "This frame is stale: the source predates current repo changes. "
            "Review carefully before using any context from this frame."
        )
    elif staleness_class == "possibly_stale":
        warning = (
            "This frame may be stale: current repo match is not confirmed. "
            "Verify the frame source before proceeding."
        )
    elif staleness_class == "unknown":
        warning = "Staleness cannot be determined from available information."
    return {
        "staleness_class": staleness_class,
        "definition": STALENESS_CLASSES[staleness_class],
        "warning": warning,
    }


# ── Context summaries ─────────────────────────────────────────────────────────

def summarize_reusable_context(frame: dict[str, Any]) -> dict[str, Any]:
    """Return a summary of reusable context from a frame (pure, no I/O)."""
    return {
        "included_items": list(_REUSABLE_CONTEXT_ITEMS),
        "task_summary": frame.get("task_summary", ""),
        "patch_summary": frame.get("patch_summary", ""),
        "changed_files_summary": frame.get("changed_files_summary", ""),
        "evidence_summary": frame.get("evidence_summary", ""),
        "validation_summary": frame.get("validation_summary", ""),
        "benchmark_summary": frame.get("benchmark_summary", ""),
        "decision_summary": frame.get("decision_summary", ""),
        "artifact_references": frame.get("source_artifacts", []),
        "next_operator_action": frame.get("next_operator_action", ""),
    }


def summarize_excluded_context(frame: dict[str, Any]) -> dict[str, Any]:
    """Return a summary of excluded context (always excluded for safety)."""
    return {
        "always_excluded": list(_EXCLUDED_CONTEXT_ITEMS),
        "note": (
            "These items are never carried forward to protect operator safety, "
            "prevent secret leakage, and ensure no execution bypasses human review."
        ),
    }


# ── Guardrails ────────────────────────────────────────────────────────────────

def _guardrails(ui_placeholder_added: bool = False) -> dict[str, Any]:
    return {
        "contract_only":                     True,
        "continuation_execution_implemented": False,
        "ui_placeholder_added":              ui_placeholder_added,
        "new_route_added":                   False,
        "mutation_route_added":              False,
        "backend_execution_changed":         False,
        "task_execution_performed":          False,
        "agent_launched":                    False,
        "model_call_performed":              False,
        "patch_applied":                     False,
        "validation_run":                    False,
        "benchmark_run_performed":           False,
        "network_call_performed":            False,
        "database_write_performed":          False,
        "worker_launch_performed":           False,
        "repo_mutation_performed":           False,
        "merge_performed":                   False,
    }


# ── Demo frames ───────────────────────────────────────────────────────────────

def _build_demo_frames() -> list[dict[str, Any]]:
    return [
        normalize_frame({
            "frame_id": "demo-frame-001",
            "created_at": "2026-06-25T10:00:00+00:00",
            "source_type": "run_timeline",
            "source_run_id": "run-abc123",
            "source_artifacts": [".agent/ux/run_timeline_surface/run_timeline_surface.json"],
            "title": "TypeScript Migration — Import Path Fix",
            "task_summary": "Fix broken import paths after moving files to src/.",
            "mode": "instant_run",
            "repo_path": ".",
            "branch_hint": "main",
            "changed_files_summary": "3 files changed: src/index.ts, src/utils/helpers.ts, tsconfig.json",
            "patch_summary": "Updated 3 import paths; no logic changes.",
            "evidence_summary": "Tests passed; no validation errors.",
            "staleness_risk": "possibly_stale",
        }),
        normalize_frame({
            "frame_id": "demo-frame-002",
            "created_at": "2026-06-24T09:00:00+00:00",
            "source_type": "commander_report",
            "source_run_id": "run-xyz789",
            "source_artifacts": [".agent/commander/contracts/contract-xyz789.json"],
            "title": "Auth Middleware Refactor — Commander Run",
            "task_summary": "Replace legacy auth middleware with token-based auth.",
            "mode": "commander_run",
            "repo_path": ".",
            "branch_hint": "feature/auth-refactor",
            "changed_files_summary": "7 files changed across web/ and core/.",
            "patch_summary": "Token validation added; session storage removed.",
            "evidence_summary": "All 4 evidence checks passed.",
            "validation_summary": "Validation: 2 passed, 0 failed.",
            "staleness_risk": "stale",
            "safety_flags": ["branch_hint_unverified", "stale_frame"],
        }),
    ]


# ── Main contract builder ─────────────────────────────────────────────────────

def build_continue_from_frame_contract(
    *,
    repo_path: str = ".",
    frames: list[dict[str, Any]] | None = None,
    created_at: str = "",
    contract_id: str | None = None,
    demo: bool = False,
    ui_placeholder_added: bool = False,
) -> dict[str, Any]:
    """Build the UX.3 Continue-from-Frame Contract report (pure, no I/O)."""
    cid = contract_id or _short_id(f"cfc:{repo_path}:{created_at}")

    if demo:
        resolved_frames = _build_demo_frames()
    elif frames:
        resolved_frames = [normalize_frame(f) for f in frames]
    else:
        resolved_frames = [build_default_frame(repo_path=repo_path, created_at=created_at)]

    # Collect warnings for stale frames
    warnings: list[str] = []
    for f in resolved_frames:
        result = classify_frame_staleness(f)
        if result["warning"]:
            warnings.append(
                f"Frame '{f.get('frame_id')}' ({f.get('title')}): {result['warning']}"
            )

    return {
        "report_kind": REPORT_KIND,
        "contract_id": cid,
        "created_at": created_at,
        "repo_path": repo_path,
        "contract_status": CONTRACT_STATUS_READY,
        "frame_definition": {
            "description": (
                "A frame is a reusable snapshot of operator-facing run context. "
                "It captures what the operator saw and decided during a past run, "
                "expressed as summaries safe for human review."
            ),
            "frame_is": [
                "a snapshot of operator-facing run context",
                "a set of summaries for human review",
                "a safe reference to past artifacts",
            ],
            "frame_is_not": list(_FRAME_IS_NOT),
        },
        "frame_schema": {
            "required_fields": [
                "frame_id", "created_at", "source_type", "source_run_id",
                "source_artifacts", "title", "task_summary", "mode", "repo_path",
                "branch_hint", "changed_files_summary", "patch_summary",
                "evidence_summary", "validation_summary", "benchmark_summary",
                "decision_summary", "reusable_context", "excluded_context",
                "staleness_risk", "safety_flags", "required_confirmations",
                "allowed_continuation_modes", "forbidden_continuation_modes",
                "next_operator_action",
            ],
            "allowed_source_types": list(ALLOWED_SOURCE_TYPES),
            "staleness_values": list(STALENESS_CLASSES.keys()),
        },
        "default_frame": build_default_frame(repo_path=repo_path, created_at=created_at),
        "reusable_context_policy": {
            "description": "Only operator-facing summaries and safe artifact references are reusable.",
            "included_summaries": list(_REUSABLE_CONTEXT_ITEMS),
            "artifact_references": "Safe read-only paths to existing .agent artifacts only.",
            "note": "No execution state, no raw tool output, no credentials are reused.",
        },
        "excluded_context_policy": {
            "description": "These items are always excluded to protect safety and prevent bypass.",
            "always_excluded": list(_EXCLUDED_CONTEXT_ITEMS),
        },
        "allowed_continuation_modes": list(ALLOWED_CONTINUATION_MODES),
        "forbidden_continuation_modes": list(FORBIDDEN_CONTINUATION_MODES),
        "human_confirmation_policy": {
            "description": "Explicit human approval is required before any execution or mutation.",
            "required_before": list(_HUMAN_CONFIRMATION_REQUIRED_BEFORE),
            "silent_resume_forbidden": True,
            "silent_apply_forbidden": True,
        },
        "staleness_policy": {
            "description": "Frames are classified by their currency relative to the repo state.",
            "staleness_classes": STALENESS_CLASSES,
            "note": (
                "UX.3 does not run git commands or shell processes to verify freshness. "
                "This phase only defines the policy."
            ),
        },
        "ui_contract": {
            "continue_button_behavior": "Review-only at first — shows what will be reused and excluded.",
            "required_displays": [
                "what context will be reused",
                "what context will be excluded",
                "staleness warning if applicable",
                "human confirmation prompt",
                "user-chosen continuation mode",
            ],
            "forbidden_behaviors": [
                "silently resume execution",
                "silently apply patch",
                "auto-select continuation mode",
                "bypass staleness warning",
            ],
        },
        "example_frames": resolved_frames,
        "next_ux_steps": list(_NEXT_UX_STEPS),
        "warnings": warnings,
        "blockers": [],
        "guardrails": _guardrails(ui_placeholder_added=ui_placeholder_added),
        "guardrail_note": GUARDRAIL_NOTE,
        "boundaries": list(_BOUNDARIES),
    }


# ── Markdown renderer ─────────────────────────────────────────────────────────

def render_continue_from_frame_markdown(contract: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Continue-from-Frame Contract")
    lines.append(f"\n**Contract ID:** {contract.get('contract_id')}  ")
    lines.append(f"**Created:** {contract.get('created_at')}  ")
    lines.append(f"**Contract Status:** {contract.get('contract_status')}  ")
    lines.append(f"**Repo:** {contract.get('repo_path')}\n")

    lines.append("## Summary")
    lines.append(
        "UX.3 defines the contract for continuing from a prior run frame. "
        "A frame is a reusable snapshot of operator-facing run context. "
        "This contract specifies what a frame is, what context can be carried forward, "
        "what must be excluded, what human confirmation is required, and what "
        "continuation modes are allowed. No continuation execution is implemented.\n"
    )

    lines.append("## Frame Definition")
    fd = contract.get("frame_definition", {})
    lines.append(fd.get("description", ""))
    lines.append("\n**A frame IS:**")
    for item in fd.get("frame_is", []):
        lines.append(f"- {item}")
    lines.append("\n**A frame IS NOT:**")
    for item in fd.get("frame_is_not", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Frame Schema")
    schema = contract.get("frame_schema", {})
    lines.append("**Required fields:**")
    fields = schema.get("required_fields", [])
    lines.append(", ".join(f"`{f}`" for f in fields))
    lines.append("\n**Allowed source types:** " + ", ".join(schema.get("allowed_source_types", [])))
    lines.append("**Staleness values:** " + ", ".join(schema.get("staleness_values", [])))
    lines.append("")

    lines.append("## Reusable Context Policy")
    rcp = contract.get("reusable_context_policy", {})
    lines.append(rcp.get("description", ""))
    lines.append("\n**Included summaries:**")
    for item in rcp.get("included_summaries", []):
        lines.append(f"- {item}")
    lines.append(f"\n**Artifact references:** {rcp.get('artifact_references', '')}")
    lines.append(f"\n_{rcp.get('note', '')}_\n")

    lines.append("## Excluded Context Policy")
    ecp = contract.get("excluded_context_policy", {})
    lines.append(ecp.get("description", ""))
    lines.append("\n**Always excluded:**")
    for item in ecp.get("always_excluded", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Allowed Continuation Modes")
    for mode in contract.get("allowed_continuation_modes", []):
        lines.append(f"- `{mode}`")
    lines.append("")

    lines.append("## Forbidden Continuation Modes")
    for mode in contract.get("forbidden_continuation_modes", []):
        lines.append(f"- `{mode}`")
    lines.append("")

    lines.append("## Human Confirmation Policy")
    hcp = contract.get("human_confirmation_policy", {})
    lines.append(hcp.get("description", ""))
    lines.append("\n**Required before:**")
    for action in hcp.get("required_before", []):
        lines.append(f"- {action}")
    lines.append("")

    lines.append("## Staleness Policy")
    sp = contract.get("staleness_policy", {})
    lines.append(sp.get("description", ""))
    lines.append("")
    for cls, defn in sp.get("staleness_classes", {}).items():
        lines.append(f"- **{cls}**: {defn}")
    lines.append(f"\n_{sp.get('note', '')}_\n")

    lines.append("## UI Contract")
    uc = contract.get("ui_contract", {})
    lines.append(f"**Continue button behavior:** {uc.get('continue_button_behavior', '')}")
    lines.append("\n**Required displays:**")
    for item in uc.get("required_displays", []):
        lines.append(f"- {item}")
    lines.append("\n**Forbidden behaviors:**")
    for item in uc.get("forbidden_behaviors", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Example Frames")
    frames = contract.get("example_frames", [])
    if frames:
        for f in frames:
            lines.append(f"### {f.get('title', f.get('frame_id'))}")
            lines.append(f"- **Frame ID:** `{f.get('frame_id')}`")
            lines.append(f"- **Source Type:** {f.get('source_type')}")
            lines.append(f"- **Staleness:** {f.get('staleness_risk')}")
            lines.append(f"- **Task Summary:** {f.get('task_summary')}")
            lines.append(f"- **Patch Summary:** {f.get('patch_summary')}")
            lines.append("")
    else:
        lines.append("_No example frames._")
        lines.append("")

    lines.append("## Next UX Steps")
    for step in contract.get("next_ux_steps", []):
        lines.append(f"- {step}")
    lines.append("")

    lines.append("## Warnings")
    warnings = contract.get("warnings", [])
    lines.append("\n".join(f"- {w}" for w in warnings) if warnings else "_None._")
    lines.append("")

    lines.append("## Blockers")
    blockers = contract.get("blockers", [])
    lines.append("\n".join(f"- {b}" for b in blockers) if blockers else "_None._")
    lines.append("")

    lines.append("## Guardrails")
    gs = contract.get("guardrails", {})
    for k, v in gs.items():
        lines.append(f"- `{k}` = `{v}`")
    lines.append("")

    lines.append("## Boundaries")
    for b in contract.get("boundaries", []):
        lines.append(f"- {b}")
    lines.append("")
    lines.append(f"> {contract.get('guardrail_note', '')}")

    return "\n".join(lines)


# ── I/O writer ────────────────────────────────────────────────────────────────

def write_continue_from_frame_artifacts(
    contract: dict[str, Any],
    output_root: str,
) -> dict[str, Any]:
    """Write JSON + Markdown artifacts. Returns {ok, json_path, md_path}."""
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / JSON_NAME
    mp = out / MD_NAME
    jp.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    mp.write_text(render_continue_from_frame_markdown(contract), encoding="utf-8")
    return {"ok": True, "json_path": str(jp), "md_path": str(mp)}
