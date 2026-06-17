"""AUTO.1e — Sandbox Self-Evolution Evidence Pack (report-only).

Consumes the AUTO.1a/1b/1c/1d sandbox self-evolution artifacts and packages them
into one human-readable review package, so an operator does not have to inspect
four separate files before deciding what to do next.

AUTO.1e packages evidence. AUTO.1e does not execute, approve, apply a patch, run
validation or a benchmark check, call a model, write to the real repo, push,
merge, open a PR, or contact a remote git host / chat service / external
automation. Human approval is required before any real repo change; self-approval
is forbidden.

This module is stdlib-only and pure: it reads already-parsed artifact records
(plain dicts) and returns a deterministic evidence-pack record plus Markdown. It
reads no files and never mutates the source artifacts.
"""
from __future__ import annotations

from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "sandbox_self_evolution_evidence_pack"

#: The four artifact slots, in chain order.
ARTIFACT_KINDS: tuple[str, ...] = ("contract", "dry_run", "patch_evaluation", "graduation_review")

#: The ``report_kind`` each slot must carry to be accepted as valid.
ARTIFACT_REPORT_KINDS: dict[str, str] = {
    "contract": "sandbox_self_evolution_trial",
    "dry_run": "sandbox_self_evolution_dry_run",
    "patch_evaluation": "sandbox_patch_candidate_evaluation",
    "graduation_review": "sandbox_patch_graduation_review",
}

#: Default on-disk filenames (used by the CLI for ``--trial-dir`` discovery).
ARTIFACT_FILENAMES: dict[str, str] = {
    "contract": "self_evolution_trial.json",
    "dry_run": "sandbox_dry_run.json",
    "patch_evaluation": "patch_candidate_evaluation.json",
    "graduation_review": "patch_graduation_review.json",
}

#: Human-readable labels.
ARTIFACT_LABELS: dict[str, str] = {
    "contract": "Contract",
    "dry_run": "Dry run",
    "patch_evaluation": "Patch candidate evaluation",
    "graduation_review": "Graduation review",
}

#: Each artifact stores its verdict under a different key.
ARTIFACT_VERDICT_KEYS: dict[str, str] = {
    "contract": "verdict",
    "dry_run": "dry_run_verdict",
    "patch_evaluation": "verdict",
    "graduation_review": "graduation_verdict",
}

#: Deterministic final verdicts.
FINAL_VERDICTS: tuple[str, ...] = (
    "ready_for_human_review",
    "needs_more_validation",
    "blocked",
    "incomplete_pack",
)

#: Recommended next steps (a human always acts on these).
RECOMMENDED_NEXT_STEPS: tuple[str, ...] = (
    "review_patch_candidate",
    "request_more_validation",
    "reject_candidate",
    "complete_missing_artifacts",
    "keep_report_only",
)

#: Guardrail-boolean fields that, if true in ANY source artifact, hard-block the
#: pack — these mean a report-only / sandbox-only contract was violated.
_HARD_BREACH_FIELDS: tuple[tuple[str, str], ...] = (
    ("self_approval_allowed", "allows self-approval"),
    ("eligible_for_auto_merge", "is eligible for auto-merge"),
    ("real_repo_modified", "reports the real repo was modified"),
    ("patch_applied_to_real_repo", "reports a patch was written to the real repo"),
    ("push_performed", "reports a push was performed"),
    ("merge_performed", "reports a merge was performed"),
    ("model_call_performed", "reports a model call was performed"),
    ("worker_launch_performed", "reports a worker was launched"),
)

EVIDENCE_PACK_GUARDRAIL_NOTE = (
    "Sandbox Self-Evolution Evidence Pack is report-only: it packages the AUTO.1a "
    "/ 1b / 1c / 1d sandbox self-evolution artifacts into one human-readable review "
    "package. It packages evidence; it does not execute, approve, apply a patch, "
    "run validation or a benchmark check, call a model, write to the real repo, "
    "push, merge, open a PR, or contact a remote git host / chat service / external "
    "automation. Human approval is required before any real repo change; "
    "self-approval is forbidden."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def artifact_verdict(kind: str, artifact: Any) -> str | None:
    """Return the verdict string a source artifact carries, or ``None``."""
    if not isinstance(artifact, dict):
        return None
    value = artifact.get(ARTIFACT_VERDICT_KEYS.get(kind, "verdict"))
    return str(value) if value is not None else None


def _se_summary(block: Any) -> dict[str, int]:
    summary = (block or {}).get("summary") or {}
    return {
        "created": _int(summary.get("created")),
        "modified": _int(summary.get("modified")),
        "deleted": _int(summary.get("deleted")),
    }


def _phase_text(contract: Any) -> str:
    phase = (contract or {}).get("phase") or {}
    pid = str(phase.get("id", "")).strip()
    title = str(phase.get("title", "")).strip()
    summary = str(phase.get("summary", "")).strip()
    if not (pid or title or summary):
        return "(unknown)"
    head = " — ".join(part for part in (pid, title) if part) or "(phase)"
    return f"{head}: {summary}" if summary else head


# ── Artifact intake ───────────────────────────────────────────────────────────

def _classify_artifacts(
    artifacts: Any,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Split the provided slots into present / missing / malformed.

    A slot is *present* only when it is a dict whose ``report_kind`` matches the
    expected kind. A provided-but-wrong slot is both missing and malformed; an
    absent slot is simply missing.
    """
    present: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    malformed: list[str] = []
    source = artifacts or {}
    for kind in ARTIFACT_KINDS:
        candidate = source.get(kind)
        if isinstance(candidate, dict) and str(candidate.get("report_kind", "")) == ARTIFACT_REPORT_KINDS[kind]:
            present[kind] = candidate
        else:
            missing.append(kind)
            if candidate is not None:
                malformed.append(kind)
    return present, missing, malformed


def _resolve_trial_id(trial_id: str, present: dict[str, dict[str, Any]]) -> str:
    resolved = str(trial_id or "").strip()
    if resolved:
        return resolved
    for kind in ARTIFACT_KINDS:
        artifact = present.get(kind)
        if artifact and str(artifact.get("trial_id", "")).strip():
            return str(artifact["trial_id"]).strip()
    return ""


# ── Deterministic analysis ────────────────────────────────────────────────────

def _scan_hard_blockers(present: dict[str, dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for kind in ARTIFACT_KINDS:
        artifact = present.get(kind)
        if not artifact:
            continue
        label = ARTIFACT_LABELS[kind].lower()
        for field, phrase in _HARD_BREACH_FIELDS:
            if artifact.get(field) is True:
                blockers.append(f"the {label} artifact {phrase} ({field})")
        if artifact.get("side_effects_sandbox_only") is False:
            blockers.append(f"the {label} artifact reports side effects that were not sandbox-only")
    return blockers


def _validation_skipped_notes(present: dict[str, dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    dry_run = present.get("dry_run")
    if dry_run and (
        str(dry_run.get("validation_status")) == "skipped"
        or str(dry_run.get("dry_run_verdict")) == "validation_skipped"
    ):
        notes.append("validation was skipped in the dry run; more validation is recommended before review")
    patch_eval = present.get("patch_evaluation")
    if patch_eval and (
        str(patch_eval.get("validation_status")) == "skipped"
        or str(patch_eval.get("verdict")) == "validation_skipped"
    ):
        notes.append(
            "validation was skipped in the patch candidate evaluation; more validation is recommended before review"
        )
    graduation = present.get("graduation_review")
    if graduation and str(graduation.get("source_validation_status")) == "skipped":
        notes.append("validation was skipped per the graduation review; more validation is recommended before review")
    return notes


def _decide(present: dict[str, dict[str, Any]], blockers: list[str]) -> tuple[str, str]:
    if blockers:
        return "blocked", "reject_candidate"
    if "graduation_review" in present:
        verdict = artifact_verdict("graduation_review", present["graduation_review"])
        if verdict == "eligible_for_human_review":
            return "ready_for_human_review", "review_patch_candidate"
        if verdict == "needs_more_validation":
            return "needs_more_validation", "request_more_validation"
        if verdict in ("blocked_by_safety", "not_reviewable"):
            return "blocked", "reject_candidate"
        return "incomplete_pack", "complete_missing_artifacts"
    # No graduation review yet -> the pack is incomplete.
    if "patch_evaluation" in present or "dry_run" in present:
        return "incomplete_pack", "complete_missing_artifacts"
    return "incomplete_pack", "keep_report_only"


def _build_risk_summary(
    present: dict[str, dict[str, Any]],
    blockers: list[str],
    patch_se: dict[str, int],
    validation_se: dict[str, int],
) -> dict[str, str]:
    contract = present.get("contract")
    patch_eval = present.get("patch_evaluation")
    dry_run = present.get("dry_run")

    if blockers:
        safety = f"BLOCKED: {len(blockers)} hard safety issue(s) found across the artifacts"
    else:
        safety = f"no hard safety breach detected across {len(present)} present artifact(s)"

    if contract:
        touched = len((patch_eval or {}).get("patch_touched_paths") or [])
        scope = (
            f"automation level {contract.get('automation_level', '(unknown)')}; "
            f"patch touches {touched} file(s)"
        )
    else:
        scope = "unknown (no contract artifact)"

    statuses = []
    if dry_run:
        statuses.append(str(dry_run.get("validation_status", "")))
    if patch_eval:
        statuses.append(str(patch_eval.get("validation_status", "")))
    failed = (patch_eval and str(patch_eval.get("verdict")) == "patch_candidate_failed_validation") or (
        dry_run and str(dry_run.get("dry_run_verdict")) == "dry_run_failed"
    )
    if "skipped" in statuses:
        validation = "validation was skipped in at least one step; more is recommended"
    elif failed:
        validation = "validation failed in at least one step"
    elif statuses and all(status == "ran" for status in statuses):
        validation = "declared validation ran in the sandbox"
    else:
        validation = "validation status unknown or not run"

    if any("sandbox-only" in blocker or "real repo" in blocker for blocker in blockers):
        side_effects = "real repo or non-sandbox effects detected — this blocks graduation"
    else:
        side_effects = (
            "sandbox-only: patch ("
            f"created {patch_se['created']}, modified {patch_se['modified']}, deleted {patch_se['deleted']}), "
            f"validation (created {validation_se['created']}, modified {validation_se['modified']}, "
            f"deleted {validation_se['deleted']})"
        )

    if any(present.get(kind, {}).get("model_call_performed") is True for kind in ARTIFACT_KINDS):
        budget = "a model call was reported — this blocks graduation"
    else:
        budget = "no model call reported; report-only / local budget"

    gate_broken = any(
        present.get(kind, {}).get("self_approval_allowed") is True
        or present.get(kind, {}).get("eligible_for_auto_merge") is True
        for kind in ARTIFACT_KINDS
    )
    human_gate = (
        "BROKEN: self-approval or auto-merge is enabled somewhere"
        if gate_broken
        else "intact: human approval required, no self-approval, no auto-merge"
    )

    return {
        "safety": safety,
        "scope": scope,
        "validation": validation,
        "side_effects": side_effects,
        "budget_or_model_use": budget,
        "human_gate": human_gate,
    }


def _build_human_review_packet(
    present: dict[str, dict[str, Any]],
    final_verdict: str,
    patch_se: dict[str, int],
    validation_se: dict[str, int],
) -> dict[str, Any]:
    contract = present.get("contract")
    patch_eval = present.get("patch_evaluation")
    graduation = present.get("graduation_review")

    touched = list(
        (patch_eval or {}).get("patch_touched_paths")
        or (graduation or {}).get("source_patch_touched_paths")
        or []
    )
    if patch_eval:
        patch_size = (
            f"{_int(patch_eval.get('patch_changed_lines'))} changed lines across "
            f"{_int(patch_eval.get('patch_file_count'))} files"
        )
    else:
        patch_size = "(unknown)"

    validation_status = str(
        (patch_eval or {}).get("validation_status")
        or (present.get("dry_run") or {}).get("validation_status")
        or "(unknown)"
    )

    if graduation:
        graduation_decision = (
            f"{artifact_verdict('graduation_review', graduation)} -> "
            f"{graduation.get('recommended_next_step', '(none)')}"
        )
    else:
        graduation_decision = "(no graduation review)"

    return {
        "phase_or_objective": _phase_text(contract),
        "patch_touched_files": touched,
        "patch_size": patch_size,
        "validation_status": validation_status,
        "sandbox_side_effects": {"patch": patch_se, "validation": validation_se},
        "graduation_decision": graduation_decision,
        "inspect_manually": (
            "Inspect the touched files, the sandbox validation result, and the side effects above, "
            "then confirm the graduation decision before approving any real repo change."
        ),
    }


# ── Record assembly ───────────────────────────────────────────────────────────

def _boundaries() -> dict[str, bool]:
    return {
        "runs_automation": False,
        "applies_patches": False,
        "runs_validation_or_benchmarks": False,
        "calls_models": False,
        "modifies_real_repo": False,
        "pushes_merges_or_opens_pr": False,
        "contacts_remote_or_chat_or_automation": False,
        "allows_self_approval": False,
    }


def build_evidence_pack(
    *,
    artifacts: Any,
    pack_id: str = "",
    created_at: str = "",
    trial_id: str = "",
    artifact_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Package the AUTO.1a/1b/1c/1d artifacts into one evidence-pack record.

    ``artifacts`` maps each slot (``contract`` / ``dry_run`` / ``patch_evaluation``
    / ``graduation_review``) to its parsed record (a dict) or ``None``. This
    function reads only — it never mutates the source artifacts and never runs or
    contacts anything.
    """
    present, missing, malformed = _classify_artifacts(artifacts)
    resolved_trial = _resolve_trial_id(trial_id, present)
    paths = artifact_paths or {}

    blockers = _scan_hard_blockers(present)
    final_verdict, next_step = _decide(present, blockers)

    warnings: list[str] = []
    for kind in malformed:
        warnings.append(
            f"the {ARTIFACT_LABELS[kind].lower()} artifact was missing or malformed and was treated as absent"
        )
    warnings.extend(_validation_skipped_notes(present))
    if missing:
        warnings.append("the evidence pack is incomplete; missing: " + ", ".join(missing))

    patch_eval = present.get("patch_evaluation")
    dry_run = present.get("dry_run")
    patch_se = _se_summary((patch_eval or {}).get("patch_side_effects"))
    validation_se = _se_summary(
        (patch_eval or {}).get("validation_side_effects") or (dry_run or {}).get("side_effects")
    )

    source_artifacts = [
        {
            "kind": kind,
            "label": ARTIFACT_LABELS[kind],
            "report_kind": ARTIFACT_REPORT_KINDS[kind],
            "verdict": artifact_verdict(kind, present[kind]),
            "path": str(paths.get(kind, "")),
        }
        for kind in ARTIFACT_KINDS
        if kind in present
    ]
    source_verdicts = {
        kind: (artifact_verdict(kind, present[kind]) if kind in present else None)
        for kind in ARTIFACT_KINDS
    }
    timeline = [
        {
            "step": index,
            "name": ARTIFACT_LABELS[kind],
            "kind": kind,
            "present": kind in present,
            "verdict": artifact_verdict(kind, present[kind]) if kind in present else None,
        }
        for index, kind in enumerate(ARTIFACT_KINDS, start=1)
    ]

    risk_summary = _build_risk_summary(present, blockers, patch_se, validation_se)
    human_review_packet = _build_human_review_packet(present, final_verdict, patch_se, validation_se)

    summary = {
        "trial_id": resolved_trial,
        "final_verdict": final_verdict,
        "recommended_next_step": next_step,
        "human_review_required": True,
        "artifacts_included": [ARTIFACT_LABELS[kind] for kind in ARTIFACT_KINDS if kind in present],
        "missing_artifacts": list(missing),
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": EVIDENCE_PACK_GUARDRAIL_NOTE,
        "pack_id": str(pack_id or ""),
        "created_at": str(created_at or ""),
        "trial_id": resolved_trial,
        "source_artifacts": source_artifacts,
        "missing_artifacts": list(missing),
        "source_verdicts": source_verdicts,
        "final_verdict": final_verdict,
        "recommended_next_step": next_step,
        "summary": summary,
        "timeline": timeline,
        "risk_summary": risk_summary,
        "human_review_packet": human_review_packet,
        "blockers": blockers,
        "warnings": warnings,
        # ── AUTO.1e guardrail booleans (this tool does none of these) ──
        "human_review_required": True,
        "self_approval_allowed": False,
        "eligible_for_auto_merge": False,
        "real_repo_modified": False,
        "patch_applied_to_real_repo": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "worker_launch_performed": False,
        "boundaries": _boundaries(),
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def render_evidence_pack_markdown(record: dict[str, Any]) -> str:
    """Render the evidence-pack record as one operator-readable report."""
    lines: list[str] = [
        "# Sandbox Self-Evolution Evidence Pack",
        "",
        f"> {record.get('guardrail_note', EVIDENCE_PACK_GUARDRAIL_NOTE)}",
        "",
        "_Report only: this pack bundles the AUTO.1a/1b/1c/1d sandbox artifacts into one "
        "review package. It runs nothing, approves nothing, and changes nothing in the "
        "real repo. Human approval is required before any real repo change._",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]
    lines.append(f"- **Trial id:** `{_md(record.get('trial_id') or '(none)')}`")
    lines.append(f"- **Final verdict:** `{_md(record.get('final_verdict') or '')}`")
    lines.append(f"- **Recommended next step:** `{_md(record.get('recommended_next_step') or '')}`")
    lines.append(f"- **Human review required:** {str(record.get('human_review_required', True)).lower()}")
    included = [a.get("label") for a in record.get("source_artifacts") or []]
    lines.append(f"- **Source artifacts included:** {', '.join(included) if included else 'none'}")
    missing = record.get("missing_artifacts") or []
    lines.append(f"- **Missing artifacts:** {', '.join(missing) if missing else 'none'}")
    lines.append("")

    # Timeline
    lines += ["## Timeline", ""]
    for step in record.get("timeline") or []:
        mark = "present" if step.get("present") else "absent"
        verdict = step.get("verdict") or "—"
        lines.append(f"{step.get('step')}. **{_md(step.get('name'))}** — {mark} (verdict: `{_md(verdict)}`)")
    lines.append("")

    # Verdicts
    lines += ["## Verdicts", "", "| Artifact | Verdict | Notes |", "|---|---|---|"]
    present_kinds = {a.get("kind") for a in record.get("source_artifacts") or []}
    for step in record.get("timeline") or []:
        kind = step.get("kind")
        verdict = step.get("verdict") or "—"
        note = "present" if kind in present_kinds else "missing"
        lines.append(f"| {_md(step.get('name'))} | `{_md(verdict)}` | {note} |")
    lines.append("")

    # Risk Summary
    lines += ["## Risk Summary", ""]
    risk = record.get("risk_summary") or {}
    for key, label in (
        ("safety", "Safety"),
        ("scope", "Scope"),
        ("validation", "Validation"),
        ("side_effects", "Side effects"),
        ("budget_or_model_use", "Budget / model use"),
        ("human_gate", "Human gate"),
    ):
        lines.append(f"- **{label}:** {_md(risk.get(key, ''))}")
    lines.append("")

    # Human Review Packet
    lines += ["## Human Review Packet", ""]
    packet = record.get("human_review_packet") or {}
    lines.append(f"- **Phase / objective:** {_md(packet.get('phase_or_objective', '(unknown)'))}")
    touched = packet.get("patch_touched_files") or []
    lines.append(
        "- **Patch touched files:** " + (", ".join(f"`{_md(path)}`" for path in touched) or "none")
    )
    lines.append(f"- **Patch size:** {_md(packet.get('patch_size', '(unknown)'))}")
    lines.append(f"- **Validation status:** {_md(packet.get('validation_status', '(unknown)'))}")
    side = packet.get("sandbox_side_effects") or {}
    patch_se = side.get("patch") or {}
    validation_se = side.get("validation") or {}
    lines.append(
        "- **Sandbox side effects:** patch ("
        f"created {patch_se.get('created', 0)}, modified {patch_se.get('modified', 0)}, "
        f"deleted {patch_se.get('deleted', 0)}); validation ("
        f"created {validation_se.get('created', 0)}, modified {validation_se.get('modified', 0)}, "
        f"deleted {validation_se.get('deleted', 0)})"
    )
    lines.append(f"- **Graduation decision:** {_md(packet.get('graduation_decision', '(none)'))}")
    lines.append(f"- **Inspect manually:** {_md(packet.get('inspect_manually', ''))}")
    lines.append("")

    # Blockers
    lines += ["## Blockers", ""]
    blockers = record.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    warnings = record.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- This evidence pack does not run automation.",
        "- This evidence pack does not apply patches.",
        "- This evidence pack does not run validation or benchmarks.",
        "- This evidence pack does not call models.",
        "- This evidence pack does not modify the real repo.",
        "- This evidence pack does not push, merge, open PRs, or contact a remote git "
        "host, chat app, or external automation.",
        "- Human approval is required before any real repo change.",
        "",
    ]
    return "\n".join(lines) + "\n"
