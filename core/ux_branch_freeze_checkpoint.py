"""UX.CLOSE — UX Branch Freeze Checkpoint (report-only).

Reads the phase registry, the phase picker state, the UX.11 Unified Workbench
behavior preservation report, integration-presence evidence, and documentation,
then writes a deterministic JSON + Markdown checkpoint that proves the UX branch
(UX.1 through UX.11) is complete, behavior-preserving, and safe to freeze.

Core principle: UX.CLOSE audits the completed UX branch. It does not choose new
work, execute phases, call models, apply patches, run a validation command, run a
benchmark check, contact network services, launch workers, write to a database,
add a backend or mutation route, change UI behavior, block execution, push,
merge, or open PRs. UX.CLOSE is a report-only checkpoint.

It reuses ``core.phase_picker.pick_phase_candidates`` for authoritative registry
validity and bucket state, and ingests an already-built
``core.unified_workbench_behavior_preservation`` (UX.11) report so the freeze
criteria are proven by the same source-level checks UX.11 already performs.
Nothing here is run; the UX.11 report is consumed as data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.phase_picker import pick_phase_candidates
from core.unified_workbench_behavior_preservation import (
    build_unified_workbench_behavior_preservation_report,
)


# ── Constants ──────────────────────────────────────────────────────────────────

REPORT_KIND = "ux_branch_freeze_checkpoint"

THIS_PHASE_ID = "UX.CLOSE"

REQUIRED_UX_PHASE_IDS: tuple[str, ...] = (
    "UX.1", "UX.2", "UX.3", "UX.4", "UX.5", "UX.6",
    "UX.7", "UX.8", "UX.9", "UX.10", "UX.11",
)

DOC_PHASE_IDS: tuple[str, ...] = REQUIRED_UX_PHASE_IDS + (THIS_PHASE_ID,)

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

#: Integration evidence the checkpoint expects. ``required`` records become
#: blockers when absent; optional records become warnings.
INTEGRATION_CHECK_SPEC: tuple[tuple[str, str, bool], ...] = (
    ("ux10_visual_integration", "UX.10 Unified Workbench visual integration exists", True),
    ("ux11_behavior_preservation_module", "UX.11 behavior preservation check module exists", True),
    ("ux10_visual_integration_test", "UX.10 visual integration test exists", False),
    ("ux11_behavior_preservation_script", "UX.11 behavior preservation report script exists", False),
    ("ux11_behavior_preservation_test", "UX.11 behavior preservation test exists", False),
)

#: Source-level evidence used to confirm the visual integration and the UX.11
#: check exist (relative paths plus the marker that proves the visual work).
VISUAL_INTEGRATION_FILE = "web/templates/index.html"
VISUAL_INTEGRATION_MARKER = "UX.10 unified-workbench"
UX11_MODULE_REL = "core/unified_workbench_behavior_preservation.py"
UX10_VISUAL_TEST_REL = "tests/test_unified_workbench_visual_integration.py"
UX11_SCRIPT_REL = "scripts/create_unified_workbench_behavior_preservation_report.py"
UX11_TEST_REL = "tests/test_unified_workbench_behavior_preservation.py"

#: Each freeze criterion is satisfied only when every supporting UX.11 check id is
#: present and passes. These map the spec's safety bullets onto UX.11 evidence.
FREEZE_CRITERIA: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "no_new_execution_path",
        "The UX branch added no new execution path.",
        (
            "instant_run_not_auto_dispatched",
            "no_fetch_in_workbench",
            "no_hidden_auto_dispatch_marker",
            "single_form_post",
            "workbench_has_no_form_action",
            "mode_chip_js_is_visual_only",
        ),
    ),
    (
        "no_new_mutation_route",
        "UX.10 and UX.11 added no new mutation route.",
        (
            "no_workbench_post_route",
            "no_workbench_mutation_route",
            "legacy_routes_left_intact",
        ),
    ),
    (
        "dangerous_actions_separate_and_human_triggered",
        "Dangerous actions remain separate and human-triggered.",
        (
            "apply_review_outside_workbench",
            "apply_review_human_triggered",
            "advanced_debug_secondary",
        ),
    ),
    (
        "assistive_or_preview_only",
        "Goal Brief / 4W1H / Mode Preview remain assistive or preview-only.",
        (
            "mode_preview_read_only",
            "helpers_help_only",
            "four_w_one_h_no_submit",
            "goal_brief_reachable",
            "mode_preview_has_no_click_handlers",
        ),
    ),
    (
        "apply_review_outside_input_requires_human_action",
        "Apply / Review Patch remains outside the unified input and requires human action.",
        (
            "apply_review_outside_workbench",
            "apply_review_human_triggered",
        ),
    ),
)

#: Work that intentionally stays outside this branch — future polish only.
REMAINING_UX_WORK: tuple[str, ...] = (
    "Live in-browser confirmation of the Unified Workbench flow: the source-level "
    "checks pass, but a human should still click through the cockpit once.",
    "Deeper cockpit visual polish and copy refinement beyond the UX.1-UX.11 scope.",
    "Optional consolidation of preview-only surfaces once operators have used the "
    "Workbench in practice.",
)

DEFAULT_README_REL = "README.md"
DEFAULT_ROADMAP_REL = "docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md"

JSON_NAME = "ux_branch_freeze_checkpoint.json"
MD_NAME = "ux_branch_freeze_checkpoint.md"

STATUS_PASS = "pass"
STATUS_WARN = "pass_with_warnings"
STATUS_BLOCKED = "blocked"

PRESERVATION_STATUS_PASS = "pass"

NEXT_STEP_FREEZE = "freeze_ux_branch"
NEXT_STEP_BY_STATUS: dict[str, str] = {
    STATUS_PASS: NEXT_STEP_FREEZE,
    STATUS_WARN: "resolve_warnings_before_freezing_ux_branch",
    STATUS_BLOCKED: "fix_blockers_before_freezing_ux_branch",
}

#: After UX freezes, the documented top priority is continued security hardening
#: of the remaining audit debt (HARDEN.1 only closed the web auth / CSRF gap).
NEXT_BRANCH_HARDEN = "HARDEN"
NEXT_PHASE_HARDEN_CONTINUE = (
    "HARDEN.2 - Remaining Security Debt (safe validation hardening / "
    "MCP approval enforcement)"
)
NEXT_BRANCH_CANDIDATES: tuple[str, ...] = (
    "HARDEN - continue security hardening of the remaining audit debt "
    "(safe validation hardening, MCP approval enforcement).",
    "Human selects the next branch among the documented candidate branches with "
    "explicit approval.",
)

GUARDRAIL_NOTE = (
    "UX Branch Freeze Checkpoint is report-only: it reads the phase registry, the "
    "phase picker state, the UX.11 behavior preservation report, integration "
    "evidence, and documentation, then verifies the UX branch is complete and safe "
    "to freeze. UX.CLOSE does not choose new work, execute phases, call models, "
    "apply patches, run a validation command, run a benchmark check, contact "
    "network services, launch workers, write to a database, add a backend or "
    "mutation route, change UI behavior, block execution, push, merge, or open PRs. "
    "UX.CLOSE is a report-only checkpoint."
)

UX_CLOSE_BOUNDARIES: tuple[str, ...] = (
    "UX.CLOSE does not choose new work.",
    "UX.CLOSE does not execute phases.",
    "UX.CLOSE does not call models.",
    "UX.CLOSE does not apply patches.",
    "UX.CLOSE does not run validation.",
    "UX.CLOSE does not run benchmarks.",
    "UX.CLOSE does not contact network services.",
    "UX.CLOSE does not launch workers.",
    "UX.CLOSE does not write to a database.",
    "UX.CLOSE does not add a backend or mutation route.",
    "UX.CLOSE does not change UI behavior.",
    "UX.CLOSE does not block execution.",
    "UX.CLOSE does not push, merge, or open PRs.",
    "UX.CLOSE is a report-only checkpoint.",
)


# ── Small helpers ──────────────────────────────────────────────────────────────

def _str(v: Any, default: str = "") -> str:
    return str(v) if v is not None else default


def _norm_path(v: Any) -> str:
    return str(v).replace("\\", "/").strip()


def _md(v: Any) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def _lower(v: bool) -> str:
    return str(bool(v)).lower()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ── UX.CLOSE own guardrails ─────────────────────────────────────────────────────

def _ux_close_guardrails() -> dict[str, bool]:
    """UX.CLOSE's own boundary booleans — it performs none of these actions."""
    return {
        "report_only": True,
        "chooses_work": False,
        "executes_phases": False,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "worker_launch_performed": False,
        "backend_route_added": False,
        "mutation_route_added": False,
        "ui_behavior_changed": False,
        "blocks_execution": False,
        "merge_performed": False,
    }


# ── Phase-level guardrail check ─────────────────────────────────────────────────

def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    """Return names of PHASE_GUARDRAIL_FIELDS that are True in a phase dict."""
    return [f for f in PHASE_GUARDRAIL_FIELDS if phase.get(f) is True]


# ── UX arc summary ───────────────────────────────────────────────────────────────

def _build_ux_arc_summary(registry_data: Any) -> dict[str, Any]:
    root = registry_data if isinstance(registry_data, dict) else {}
    raw_phases = root.get("phases", [])
    phase_map: dict[str, dict[str, Any]] = {}
    if isinstance(raw_phases, list):
        for p in raw_phases:
            if isinstance(p, dict) and p.get("phase_id"):
                phase_map[str(p["phase_id"])] = p

    phase_checks: list[dict[str, Any]] = []
    all_complete = True
    all_guardrails_ok = True

    for pid in REQUIRED_UX_PHASE_IDS:
        phase = phase_map.get(pid)
        present = phase is not None
        complete = present and str(phase.get("status", "")) == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        guardrails_ok = present and not violations
        if not complete:
            all_complete = False
        if not guardrails_ok:
            all_guardrails_ok = False
        phase_checks.append({
            "phase_id": pid,
            "present": present,
            "status": _str(phase.get("status", "")) if present else "(missing)",
            "complete": complete,
            "guardrails_ok": guardrails_ok,
            "guardrail_violations": violations,
        })

    # Is UX.CLOSE itself registered complete?
    this_phase = phase_map.get(THIS_PHASE_ID)
    this_registered = this_phase is not None
    this_complete = this_registered and str(this_phase.get("status", "")) == "complete"

    return {
        "arc": "UX",
        "required_phases": list(REQUIRED_UX_PHASE_IDS),
        "phase_checks": phase_checks,
        "all_complete": all_complete,
        "all_guardrails_ok": all_guardrails_ok,
        "this_phase_id": THIS_PHASE_ID,
        "this_phase_registered": this_registered,
        "this_phase_complete": this_complete,
    }


# ── Integration coverage ─────────────────────────────────────────────────────────

def _build_integration_coverage(integration_records: Any) -> dict[str, Any]:
    records = list(integration_records) if isinstance(integration_records, (list, tuple)) else []
    by_id = {}
    for rec in records:
        rec = rec if isinstance(rec, dict) else {}
        by_id[_str(rec.get("check_id"))] = rec

    checks: list[dict[str, Any]] = []
    required_missing: list[str] = []
    optional_missing: list[str] = []
    for check_id, title, required in INTEGRATION_CHECK_SPEC:
        rec = by_id.get(check_id, {})
        present = bool(rec.get("present"))
        evidence = _str(rec.get("evidence"))
        checks.append({
            "check_id": check_id,
            "title": title,
            "required": required,
            "present": present,
            "evidence": evidence,
        })
        if not present:
            (required_missing if required else optional_missing).append(check_id)

    return {
        "checks": checks,
        "required_missing": required_missing,
        "optional_missing": optional_missing,
        "all_required_present": not required_missing,
    }


# ── Behavior preservation summary ────────────────────────────────────────────────

def _flatten_preservation_checks(report: dict[str, Any]) -> dict[str, str]:
    flat: dict[str, str] = {}
    for group in (
        "preservation_checks",
        "route_safety_checks",
        "form_safety_checks",
        "workbench_safety_checks",
    ):
        for check in report.get(group) or []:
            if isinstance(check, dict) and check.get("check_id"):
                flat[str(check["check_id"])] = str(check.get("status", ""))
    return flat


def _build_preservation_summary(behavior_preservation: Any) -> dict[str, Any]:
    present = isinstance(behavior_preservation, dict) and bool(behavior_preservation)
    if not present:
        return {
            "present": False,
            "status": "absent",
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": [],
            "remaining_risks": [],
            "source_report_kind": "",
            "source_report_id": "",
        }
    flat = _flatten_preservation_checks(behavior_preservation)
    failed = sorted(cid for cid, status in flat.items() if status != PRESERVATION_STATUS_PASS)
    passed = sum(1 for status in flat.values() if status == PRESERVATION_STATUS_PASS)
    return {
        "present": True,
        "status": _str(behavior_preservation.get("status")),
        "total_checks": len(flat),
        "passed_checks": passed,
        "failed_checks": failed,
        "remaining_risks": list(behavior_preservation.get("remaining_risks") or []),
        "source_report_kind": _str(behavior_preservation.get("report_kind")),
        "source_report_id": _str(behavior_preservation.get("report_id")),
    }


# ── Freeze criteria ──────────────────────────────────────────────────────────────

def _build_freeze_criteria(preservation_flat: dict[str, str]) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = []
    for criterion_id, title, supporting in FREEZE_CRITERIA:
        failing: list[str] = []
        missing: list[str] = []
        for cid in supporting:
            status = preservation_flat.get(cid)
            if status is None:
                missing.append(cid)
            elif status != PRESERVATION_STATUS_PASS:
                failing.append(cid)
        satisfied = not failing and not missing
        if satisfied:
            evidence = f"all {len(supporting)} supporting UX.11 checks pass"
        else:
            parts = []
            if failing:
                parts.append("failing: " + ", ".join(failing))
            if missing:
                parts.append("missing: " + ", ".join(missing))
            evidence = "; ".join(parts)
        criteria.append({
            "criterion_id": criterion_id,
            "title": title,
            "satisfied": satisfied,
            "supporting_checks": list(supporting),
            "evidence": evidence,
        })
    return criteria


# ── Documentation coverage ───────────────────────────────────────────────────────

def _build_documentation_coverage(docs: Any) -> dict[str, Any]:
    docs = list(docs) if isinstance(docs, (list, tuple)) else []
    texts: dict[str, str] = {}
    doc_records: list[dict[str, Any]] = []
    for entry in docs:
        entry = entry if isinstance(entry, dict) else {}
        name = _str(entry.get("name"))
        present = bool(entry.get("present", True))
        text = _str(entry.get("text"))
        texts[name] = text
        doc_records.append({"name": name, "path": _norm_path(entry.get("path", "")), "present": present})

    readme_text = texts.get("README") or texts.get("readme") or ""
    roadmap_text = texts.get("roadmap") or texts.get("ROADMAP") or ""
    readme_path = next(
        (d["path"] for d in doc_records if d["name"] in ("README", "readme")), DEFAULT_README_REL
    )
    roadmap_path = next(
        (d["path"] for d in doc_records if d["name"] in ("roadmap", "ROADMAP")), DEFAULT_ROADMAP_REL
    )

    mentions: dict[str, dict[str, bool]] = {}
    missing_everywhere: list[str] = []
    for pid in DOC_PHASE_IDS:
        in_readme = pid in readme_text
        in_roadmap = pid in roadmap_text
        mentioned = in_readme or in_roadmap
        mentions[pid] = {"in_readme": in_readme, "in_roadmap": in_roadmap, "mentioned": mentioned}
        if not mentioned:
            missing_everywhere.append(pid)

    return {
        "readme_path": readme_path,
        "roadmap_path": roadmap_path,
        "docs": doc_records,
        "checked_phase_ids": list(DOC_PHASE_IDS),
        "mentions": mentions,
        "missing_phase_mentions": missing_everywhere,
    }


# ── Pure checkpoint builder ──────────────────────────────────────────────────────

def build_ux_branch_freeze_checkpoint(
    *,
    registry_data: Any,
    behavior_preservation: Any = None,
    integration_records: Any = (),
    docs: Any = (),
    registry_load_error: str = "",
    report_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    registry_path: str = "",
) -> dict[str, Any]:
    """Build the UX.CLOSE checkpoint from pre-gathered inputs.

    Pure: never reads files, writes files, runs commands, or contacts anything.
    ``registry_data`` is the parsed registry dict (or None on load failure);
    ``behavior_preservation`` is an already-built UX.11 report dict (or None);
    ``integration_records`` is a list of {check_id, present, evidence} dicts;
    ``docs`` is a list of {name, path, present, text} dicts.
    """
    pick = pick_phase_candidates(registry_data)
    registry_valid = bool(pick.get("registry_valid"))
    registry_errors = list(pick.get("errors") or [])
    registry_warnings = list(pick.get("warnings") or [])
    phase_count = int(pick.get("phase_count", 0) or 0)
    buckets = pick.get("buckets") or {}
    safe = list(buckets.get("safe_to_prepare") or [])
    safe_to_prepare_count = len(safe)
    top_recommendation = pick.get("top_recommendation")

    blockers: list[str] = []
    warnings: list[str] = []

    if registry_load_error:
        blockers.append(f"phase registry could not be read: {registry_load_error}")
    if not registry_valid:
        detail = "; ".join(registry_errors[:5])
        blockers.append("phase registry is invalid" + (f": {detail}" if detail else ""))

    ux_arc = _build_ux_arc_summary(registry_data)
    for check in ux_arc["phase_checks"]:
        pid = check["phase_id"]
        if not check["present"]:
            blockers.append(f"required UX phase {pid} is not present in the registry")
        elif not check["complete"]:
            blockers.append(f"required UX phase {pid} is not complete (status: {check['status']})")
        for field in check.get("guardrail_violations") or []:
            blockers.append(f"UX phase {pid} has {field}=true; report-only branch violated")

    if not ux_arc["this_phase_registered"]:
        warnings.append(f"{THIS_PHASE_ID} is not yet registered in the phase registry")
    elif not ux_arc["this_phase_complete"]:
        warnings.append(f"{THIS_PHASE_ID} is registered but not marked complete")

    # Integration existence.
    integration_coverage = _build_integration_coverage(integration_records)
    for check_id in integration_coverage["required_missing"]:
        blockers.append(f"required UX integration evidence missing: {check_id}")
    for check_id in integration_coverage["optional_missing"]:
        warnings.append(f"optional UX integration evidence missing: {check_id}")

    # Behavior preservation (UX.11) summary + freeze criteria.
    preservation_summary = _build_preservation_summary(behavior_preservation)
    preservation_flat = (
        _flatten_preservation_checks(behavior_preservation)
        if isinstance(behavior_preservation, dict)
        else {}
    )
    if not preservation_summary["present"]:
        blockers.append(
            "UX.11 behavior preservation report is unavailable; cannot prove the UX "
            "branch preserved behavior"
        )
    elif preservation_summary["status"] != PRESERVATION_STATUS_PASS:
        failed = ", ".join(preservation_summary["failed_checks"]) or "(unknown)"
        blockers.append(
            f"UX.11 behavior preservation status is {preservation_summary['status']!r} "
            f"(failed checks: {failed})"
        )
    elif preservation_summary["failed_checks"]:
        # Trust the per-check evidence over the report's self-declared status: any
        # failing UX.11 check blocks the freeze even if the top-level status claims
        # pass. This covers the UX.11 checks that no freeze criterion maps onto.
        failed = ", ".join(preservation_summary["failed_checks"])
        blockers.append(
            f"UX.11 reports failing behavior-preservation checks despite status "
            f"{preservation_summary['status']!r}: {failed}"
        )

    freeze_criteria = _build_freeze_criteria(preservation_flat)
    for criterion in freeze_criteria:
        if not criterion["satisfied"]:
            blockers.append(
                f"freeze criterion not satisfied: {criterion['criterion_id']} "
                f"({criterion['evidence']})"
            )

    # Picker leftovers.
    if safe_to_prepare_count > 0:
        ids = ", ".join(_str(s.get("phase_id")) for s in safe)
        warnings.append(
            f"phase picker reports {safe_to_prepare_count} safe-to-prepare candidate(s) "
            f"({ids}); expected the UX branch to be complete"
        )
    if top_recommendation is not None:
        top_id = _str(top_recommendation.get("phase_id")) if isinstance(top_recommendation, dict) else ""
        warnings.append(f"phase picker still recommends work: {top_id or '(candidate)'}")

    # Documentation coverage.
    doc_coverage = _build_documentation_coverage(docs)
    for pid in doc_coverage["missing_phase_mentions"]:
        warnings.append(f"phase {pid} is not mentioned in the README or roadmap documentation")

    validation_story = {
        "validation_run": False,
        "note": (
            "UX.CLOSE does not run validation commands. The validation commands stored "
            "in the registry for each phase were run externally by the human operator. "
            "No validation results are generated or interpreted by UX.CLOSE."
        ),
    }

    # Remaining UX work = static future-polish list plus any UX.11 remaining risks.
    remaining_ux_work: list[str] = list(REMAINING_UX_WORK)
    for risk in preservation_summary["remaining_risks"]:
        note = _str(risk.get("note")) if isinstance(risk, dict) else _str(risk)
        if note:
            remaining_ux_work.append(note)
    remaining_ux_work = _dedupe(remaining_ux_work)

    phase_violations = [
        {"phase_id": c["phase_id"], "field": f}
        for c in ux_arc["phase_checks"]
        for f in (c.get("guardrail_violations") or [])
    ]
    guardrail_summary = {
        "ux_close_guardrails": _ux_close_guardrails(),
        "phase_guardrail_fields_checked": list(PHASE_GUARDRAIL_FIELDS),
        "phase_guardrail_violations": phase_violations,
        "all_clear": not phase_violations,
    }

    open_questions: list[str] = []
    if integration_coverage["optional_missing"]:
        open_questions.append(
            "Some optional UX integration evidence is absent. Were the visual "
            "integration test and the UX.11 report script kept in the tree?"
        )
    if doc_coverage["missing_phase_mentions"]:
        open_questions.append(
            "Some UX phases are not mentioned in the README or roadmap. Should "
            "documentation be updated before freezing this checkpoint?"
        )
    if preservation_summary["present"] and preservation_summary["remaining_risks"]:
        open_questions.append(
            "UX.11 still flags a manual confirmation risk. Has a human clicked "
            "through the live Workbench flow at least once?"
        )

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)

    if blockers:
        status = STATUS_BLOCKED
        reason = f"{len(blockers)} blocker(s) prevent freezing the UX branch"
    elif warnings:
        status = STATUS_WARN
        reason = f"{len(warnings)} warning(s) noted; the UX branch freezes with warnings"
    else:
        status = STATUS_PASS
        reason = (
            "UX.1 through UX.11 are complete, behavior-preserving, report-only, and "
            "the UX branch is safe to freeze"
        )

    recommended_next_step = NEXT_STEP_BY_STATUS[status]

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": _str(report_id),
        "created_at": _str(created_at),
        "repo_path": _norm_path(repo_path) if repo_path else "",
        "registry_path": _norm_path(registry_path) if registry_path else "",
        "checkpoint_status": status,
        "checkpoint_reason": reason,
        "registry_summary": {
            "registry_valid": registry_valid,
            "phase_count": phase_count,
            "errors": registry_errors,
            "warnings": registry_warnings,
        },
        "phase_picker_summary": {
            "safe_to_prepare_count": safe_to_prepare_count,
            "top_recommendation": top_recommendation,
            "all_work_complete": safe_to_prepare_count == 0 and top_recommendation is None,
        },
        "ux_arc_summary": ux_arc,
        "integration_coverage": integration_coverage,
        "behavior_preservation_summary": preservation_summary,
        "freeze_criteria": freeze_criteria,
        "all_freeze_criteria_satisfied": all(c["satisfied"] for c in freeze_criteria),
        "remaining_ux_work": remaining_ux_work,
        "documentation_coverage": doc_coverage,
        "validation_story": validation_story,
        "guardrail_summary": guardrail_summary,
        "open_questions": open_questions,
        "recommended_next_branch": NEXT_BRANCH_HARDEN,
        "recommended_next_phase": NEXT_PHASE_HARDEN_CONTINUE,
        "next_branch_candidates": list(NEXT_BRANCH_CANDIDATES),
        "recommended_next_step": recommended_next_step,
        "warnings": warnings,
        "blockers": blockers,
        "boundaries": list(UX_CLOSE_BOUNDARIES),
    }


# ── Markdown renderer ────────────────────────────────────────────────────────────

def render_ux_branch_freeze_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render the UX.CLOSE checkpoint as operator-readable Markdown."""
    lines: list[str] = [
        "# UX Branch Freeze Checkpoint",
        "",
        f"> {report.get('guardrail_note', GUARDRAIL_NOTE)}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Registry path:** `{_md(report.get('registry_path') or '(none)')}`",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status') or '(none)')}`",
        f"- **Checkpoint reason:** {_md(report.get('checkpoint_reason') or '(none)')}",
        f"- **Recommended next step:** `{_md(report.get('recommended_next_step') or '(none)')}`",
        "",
    ]

    lines += ["## Registry Summary", ""]
    reg = report.get("registry_summary") or {}
    lines.append(f"- **Registry valid:** {_lower(bool(reg.get('registry_valid')))}")
    lines.append(f"- **Phase count:** {reg.get('phase_count', 0)}")
    errors = reg.get("errors") or []
    if errors:
        lines += ["", "**Registry errors:**", ""]
        lines += [f"- {_md(e)}" for e in errors]
    lines.append("")

    lines += ["## Phase Picker Summary", ""]
    picker = report.get("phase_picker_summary") or {}
    lines.append(f"- **Safe-to-prepare count:** {picker.get('safe_to_prepare_count', 0)}")
    top = picker.get("top_recommendation")
    if isinstance(top, dict):
        top_text = f"{_md(top.get('phase_id', ''))} ({_md(top.get('title', ''))})"
    else:
        top_text = "(none)"
    lines.append(f"- **Top recommendation:** {top_text}")
    lines.append(f"- **All work complete:** {_lower(bool(picker.get('all_work_complete')))}")
    lines.append("")

    lines += ["## UX Arc Summary", ""]
    arc = report.get("ux_arc_summary") or {}
    lines.append(f"- **All complete:** {_lower(bool(arc.get('all_complete')))}")
    lines.append(f"- **All guardrails ok:** {_lower(bool(arc.get('all_guardrails_ok')))}")
    lines.append(f"- **{_md(arc.get('this_phase_id', THIS_PHASE_ID))} registered:** "
                 f"{_lower(bool(arc.get('this_phase_registered')))}")
    lines.append(f"- **{_md(arc.get('this_phase_id', THIS_PHASE_ID))} complete:** "
                 f"{_lower(bool(arc.get('this_phase_complete')))}")
    checks = arc.get("phase_checks") or []
    if checks:
        lines += [
            "",
            "| Phase | Present | Status | Complete | Guardrails OK | Violations |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for c in checks:
            viols = ", ".join(c.get("guardrail_violations") or []) or "(none)"
            lines.append(
                f"| {_md(c.get('phase_id'))} | {_lower(bool(c.get('present')))} | "
                f"{_md(c.get('status'))} | {_lower(bool(c.get('complete')))} | "
                f"{_lower(bool(c.get('guardrails_ok')))} | {_md(viols)} |"
            )
    lines.append("")

    lines += ["## Integration Coverage", ""]
    integ = report.get("integration_coverage") or {}
    lines.append(f"- **All required present:** {_lower(bool(integ.get('all_required_present')))}")
    icks = integ.get("checks") or []
    if icks:
        lines += ["", "| Check | Required | Present | Evidence |", "| --- | --- | --- | --- |"]
        for c in icks:
            lines.append(
                f"| {_md(c.get('title'))} | {_lower(bool(c.get('required')))} | "
                f"{_lower(bool(c.get('present')))} | {_md(c.get('evidence') or '(none)')} |"
            )
    lines.append("")

    lines += ["## Behavior Preservation Summary", ""]
    bp = report.get("behavior_preservation_summary") or {}
    lines.append(f"- **Present:** {_lower(bool(bp.get('present')))}")
    lines.append(f"- **Status:** `{_md(bp.get('status') or '(none)')}`")
    lines.append(f"- **Checks passed:** {bp.get('passed_checks', 0)} / {bp.get('total_checks', 0)}")
    failed = bp.get("failed_checks") or []
    lines.append(f"- **Failed checks:** {', '.join(failed) or '(none)'}")
    lines.append("")

    lines += ["## Freeze Criteria", ""]
    crits = report.get("freeze_criteria") or []
    if crits:
        lines += ["| Criterion | Satisfied | Evidence |", "| --- | --- | --- |"]
        for c in crits:
            lines.append(
                f"| {_md(c.get('title'))} | {_lower(bool(c.get('satisfied')))} | "
                f"{_md(c.get('evidence') or '')} |"
            )
    else:
        lines.append("_None._")
    lines.append(f"\n- **All freeze criteria satisfied:** "
                 f"{_lower(bool(report.get('all_freeze_criteria_satisfied')))}")
    lines.append("")

    lines += ["## Remaining UX Work (Future Polish)", ""]
    rem = report.get("remaining_ux_work") or []
    if rem:
        for item in rem:
            lines.append(f"- {_md(item)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Documentation Coverage", ""]
    doc = report.get("documentation_coverage") or {}
    lines.append(f"- **README:** `{_md(doc.get('readme_path') or '(none)')}`")
    lines.append(f"- **Roadmap:** `{_md(doc.get('roadmap_path') or '(none)')}`")
    missing_docs = doc.get("missing_phase_mentions") or []
    lines.append(f"- **Phases missing from docs:** {', '.join(missing_docs) or '(none)'}")
    lines.append("")

    lines += ["## Validation Story", ""]
    vs = report.get("validation_story") or {}
    lines.append(f"- **Validation run:** {_lower(bool(vs.get('validation_run')))}")
    lines.append(f"- {_md(vs.get('note') or '(none)')}")
    lines.append("")

    lines += ["## Guardrail Summary", ""]
    gs = report.get("guardrail_summary") or {}
    lines.append(f"- **All clear:** {_lower(bool(gs.get('all_clear')))}")
    viols = gs.get("phase_guardrail_violations") or []
    if viols:
        lines += ["", "**Phase guardrail violations:**", ""]
        for v in viols:
            lines.append(f"- `{_md(v.get('field'))}` is true in phase `{_md(v.get('phase_id'))}`")
    else:
        lines.append("- No required UX phase reports any execution power.")
    ux_g = gs.get("ux_close_guardrails") or {}
    if ux_g:
        lines += ["", "**UX.CLOSE own guardrails:**", ""]
        for k, v in sorted(ux_g.items()):
            lines.append(f"- `{_md(k)}`: {_lower(bool(v))}")
    lines.append("")

    lines += ["## Recommended Next Branch", ""]
    lines.append(f"- **Branch:** `{_md(report.get('recommended_next_branch') or '(none)')}`")
    lines.append(f"- **Phase:** `{_md(report.get('recommended_next_phase') or '(none)')}`")
    cands = report.get("next_branch_candidates") or []
    if cands:
        lines += ["", "**Candidates:**", ""]
        for c in cands:
            lines.append(f"- {_md(c)}")
    lines.append("")

    lines += ["## Open Questions", ""]
    oq = report.get("open_questions") or []
    if oq:
        for q in oq:
            lines.append(f"- {_md(q)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Recommended Next Step", ""]
    lines.append(f"- `{_md(report.get('recommended_next_step') or '(none)')}`")
    lines.append("")

    lines += ["## Warnings", ""]
    wlist = report.get("warnings") or []
    if wlist:
        for w in wlist:
            lines.append(f"- {_md(w)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Blockers", ""]
    blist = report.get("blockers") or []
    if blist:
        for b in blist:
            lines.append(f"- {_md(b)}")
    else:
        lines.append("_None — the UX branch is complete and safe to freeze._")
    lines.append("")

    lines += ["## Boundaries", ""]
    for b in (report.get("boundaries") or list(UX_CLOSE_BOUNDARIES)):
        lines.append(f"- {_md(b)}")
    lines.append("")

    return "\n".join(lines) + "\n"


# ── Input gathering (read-only) ──────────────────────────────────────────────────

def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read or parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def _marker_present(path: Path, marker: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"{_norm_path(path)} not found"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"could not read {_norm_path(path)}: {exc}"
    if marker in text:
        return True, f"marker {marker!r} found in {_norm_path(path)}"
    return False, f"marker {marker!r} absent from {_norm_path(path)}"


def gather_ux_branch_freeze_checkpoint_inputs(
    repo_path: str | Path,
    registry_path: str | Path,
    *,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Read registry, integration evidence, the UX.11 report, and docs.

    Pure read-only: never writes, runs commands, or contacts anything. The UX.11
    report is built from local source text via the UX.11 builder, which itself
    only reads files.
    """
    repo = Path(repo_path)
    registry_data, registry_load_error = _load_json_object(Path(registry_path))

    # UX.11 behavior preservation report (read-only build from source text).
    behavior_preservation = build_unified_workbench_behavior_preservation_report(
        repo_path=str(repo),
        report_id=report_id or None,
        created_at=created_at or None,
    )

    # Integration evidence records.
    marker_ok, marker_evidence = _marker_present(
        repo / VISUAL_INTEGRATION_FILE, VISUAL_INTEGRATION_MARKER
    )
    file_records = (
        ("ux11_behavior_preservation_module", UX11_MODULE_REL),
        ("ux10_visual_integration_test", UX10_VISUAL_TEST_REL),
        ("ux11_behavior_preservation_script", UX11_SCRIPT_REL),
        ("ux11_behavior_preservation_test", UX11_TEST_REL),
    )
    integration_records: list[dict[str, Any]] = [
        {
            "check_id": "ux10_visual_integration",
            "present": marker_ok,
            "evidence": marker_evidence,
        }
    ]
    for check_id, rel in file_records:
        present = (repo / rel).is_file()
        integration_records.append({
            "check_id": check_id,
            "present": present,
            "evidence": f"{rel} {'exists' if present else 'is missing'}",
        })

    docs: list[dict[str, Any]] = []
    for name, rel in (("README", DEFAULT_README_REL), ("roadmap", DEFAULT_ROADMAP_REL)):
        target = repo / rel
        present = target.is_file()
        text = ""
        if present:
            try:
                text = target.read_text(encoding="utf-8")
            except OSError:
                present = False
        docs.append({"name": name, "path": rel, "present": present, "text": text})

    return {
        "registry_data": registry_data,
        "registry_load_error": registry_load_error,
        "behavior_preservation": behavior_preservation,
        "integration_records": integration_records,
        "docs": docs,
    }


# ── Report writing ───────────────────────────────────────────────────────────────

def write_ux_branch_freeze_checkpoint(
    repo_path: str | Path,
    registry_path: str | Path,
    output_dir: str | Path,
    *,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Gather inputs, build the checkpoint, and write JSON + Markdown artifacts.

    Returns ``{ok, json_path, md_path, report}``. Nothing outside ``output_dir``
    is written and nothing is run or contacted.
    """
    inputs = gather_ux_branch_freeze_checkpoint_inputs(
        repo_path, registry_path, report_id=report_id, created_at=created_at
    )
    report = build_ux_branch_freeze_checkpoint(
        registry_data=inputs["registry_data"],
        registry_load_error=inputs["registry_load_error"],
        behavior_preservation=inputs["behavior_preservation"],
        integration_records=inputs["integration_records"],
        docs=inputs["docs"],
        report_id=report_id,
        created_at=created_at,
        repo_path=str(repo_path),
        registry_path=str(registry_path),
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_ux_branch_freeze_checkpoint_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
