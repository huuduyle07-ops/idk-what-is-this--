"""ROAD.4 — Post-EVAL/CMD Checkpoint Audit (report-only).

Reads the phase registry, the phase picker state, EVAL artifact root
directories, CMD artifact root directories, and project documentation, then
writes a deterministic JSON + Markdown checkpoint audit that verifies the
completed EVAL and CMD arcs: all seven required phases (EVAL.1-3, CMD.1-4)
are registered, complete, report-only, artifact-backed, and documented.

Core principle: ROAD.4 audits the completed EVAL/CMD arcs. ROAD.4 does not
choose new work, execute phases, call models, apply patches, run validation,
run benchmarks, contact network services, launch workers, push, merge, or
open PRs. ROAD.4 is a report-only checkpoint audit.

Reuses ``core.phase_picker.pick_phase_candidates`` for authoritative
registry validity, bucket counts, safe-candidate count, and top
recommendation. The picker classifies metadata only; nothing is run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.phase_picker import pick_phase_candidates


# ── Constants ──────────────────────────────────────────────────────────────────

REPORT_KIND = "post_eval_cmd_checkpoint_audit"

REQUIRED_EVAL_PHASE_IDS: tuple[str, ...] = ("EVAL.1", "EVAL.2", "EVAL.3")
REQUIRED_CMD_PHASE_IDS: tuple[str, ...] = ("CMD.1", "CMD.2", "CMD.3", "CMD.4")
REQUIRED_PHASE_IDS: tuple[str, ...] = REQUIRED_EVAL_PHASE_IDS + REQUIRED_CMD_PHASE_IDS

DOC_PHASE_IDS: tuple[str, ...] = REQUIRED_PHASE_IDS + ("ROAD.4",)

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

EXPECTED_ARTIFACT_ROOTS: tuple[tuple[str, str, bool], ...] = (
    ("eval_benchmark_run_ledger", ".agent/eval/benchmark_run_ledger", True),
    ("eval_benchmark_report_compare", ".agent/eval/benchmark_report_compare", True),
    ("eval_flake_classification_report", ".agent/eval/flake_classification_report", True),
    ("cmd_contracts", ".agent/commander/contracts", True),
    ("cmd_decomposition_previews", ".agent/commander/decomposition_previews", True),
    ("cmd_budget_previews", ".agent/commander/budget_previews", True),
    ("cmd_readiness_reports", ".agent/commander/readiness_reports", True),
)

DEFAULT_README_REL = "README.md"
DEFAULT_ROADMAP_REL = "docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md"

JSON_NAME = "post_eval_cmd_checkpoint_audit.json"
MD_NAME = "post_eval_cmd_checkpoint_audit.md"

STATUS_PASS = "pass"
STATUS_WARN = "pass_with_warnings"
STATUS_BLOCKED = "blocked"

NEXT_STEP_FREEZE = "freeze_eval_cmd_checkpoint"
NEXT_STEP_HARDEN = "start_hardening_branch"

NEXT_STEP_BY_STATUS: dict[str, str] = {
    STATUS_PASS: NEXT_STEP_FREEZE,
    STATUS_WARN: "resolve_warnings_before_next_branch",
    STATUS_BLOCKED: "fix_blockers_before_next_branch",
}

NEXT_BRANCH_HARDEN = "HARDEN"
NEXT_BRANCH_HUMAN_CHOICE = "HUMAN_CHOICE"
NEXT_BRANCH_UX_OR_HARDEN = "UX_OR_HARDEN"
NEXT_PHASE_HARDEN1 = "HARDEN.1 - Web Mutation Auth / CSRF Gate"
NEXT_PHASE_HUMAN_CHOICE = "choose_next_branch_with_human_approval"

GUARDRAIL_NOTE = (
    "Post-EVAL/CMD Checkpoint Audit is report-only: it reads the phase registry, the "
    "phase picker state, EVAL and CMD artifact roots, and documentation, then verifies "
    "the completed EVAL and CMD arcs agree. ROAD.4 does not choose new work, execute "
    "phases, call models, apply patches, run validation, run benchmarks, contact network "
    "services, launch workers, push, merge, or open PRs. ROAD.4 is a report-only checkpoint audit."
)

ROAD4_BOUNDARIES: tuple[str, ...] = (
    "ROAD.4 does not choose new work.",
    "ROAD.4 does not execute phases.",
    "ROAD.4 does not call models.",
    "ROAD.4 does not apply patches.",
    "ROAD.4 does not run validation.",
    "ROAD.4 does not run benchmarks.",
    "ROAD.4 does not contact network services.",
    "ROAD.4 does not launch workers.",
    "ROAD.4 does not push, merge, or open PRs.",
    "ROAD.4 is a report-only checkpoint audit.",
)


# ── External audit parsing ────────────────────────────────────────────────────

def _extract_section_lines(text: str, heading: str) -> list[str]:
    """Return non-empty lines in the first section matching *heading* (case-insensitive)."""
    pattern = re.compile(
        r"(?:^|\n)#+\s+" + re.escape(heading) + r"\s*\n(.*?)(?=\n#+\s|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return []
    body = m.group(1)
    return [ln.strip() for ln in body.splitlines() if ln.strip()]


def parse_external_audit(text: str) -> dict[str, Any]:
    """Parse external audit Markdown text deterministically.

    Pure text extraction: no model calls, no network, no execution.
    Returns a structured summary dict.
    """
    if not isinstance(text, str):
        text = ""

    # Tally line: "Tally ...: N critical · ~M high · ~P medium · ~Q low"
    tally_pat = re.compile(
        r"tally[^\n:]*:\s*(\d+)\s+critical[^\n·*]*[·*]\s*~?(\d+)\s+high[^\n·*]*[·*]"
        r"\s*~?(\d+)\s+medium[^\n·*]*[·*]\s*~?(\d+)\s+low",
        re.IGNORECASE,
    )
    tm = tally_pat.search(text)
    tally_line = tm.group(0).strip() if tm else ""
    critical_count = int(tm.group(1)) if tm else 0
    high_count = int(tm.group(2)) if tm else 0
    medium_count = int(tm.group(3)) if tm else 0
    low_count = int(tm.group(4)) if tm else 0

    # C2 / web auth / CSRF signal
    has_c2 = bool(re.search(r"\bC2\b", text))
    c2_web_auth_csrf_signal = has_c2 and bool(
        re.search(r"CSRF|No auth|unauthenticated\s+RCE|web UI|CONFIRMED CRITICAL", text, re.IGNORECASE)
    )

    # C1 / safe validation signal
    has_c1 = bool(re.search(r"\bC1\b", text))
    c1_safe_validation_signal = has_c1 and bool(
        re.search(r"shell=True|safe.validation|require_safe_validation", text, re.IGNORECASE)
    )

    # C3 / MCP approval flag signal
    has_c3 = bool(re.search(r"\bC3\b", text))
    c3_mcp_approval_signal = has_c3 and bool(
        re.search(r"requires_human_approval|can_run_sub\w+|\bMCP\b", text, re.IGNORECASE)
    )

    exec_summary_bullets = _extract_section_lines(text, "Executive summary")
    recalibrated_priority = _extract_section_lines(text, "Recalibrated priority")
    remediation_roadmap = _extract_section_lines(text, "Remediation roadmap")

    return {
        "tally_line": tally_line,
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "has_critical": critical_count > 0,
        "has_high": high_count > 0,
        "exec_summary_bullets": exec_summary_bullets,
        "recalibrated_priority": recalibrated_priority,
        "remediation_roadmap": remediation_roadmap,
        "c2_web_auth_csrf_signal": c2_web_auth_csrf_signal,
        "c1_safe_validation_signal": c1_safe_validation_signal,
        "c3_mcp_approval_signal": c3_mcp_approval_signal,
    }


def _recommend_next_branch(
    audit_summary: dict[str, Any] | None,
    audit_path: str = "",
) -> tuple[str, str]:
    """Return (recommended_next_branch, recommended_next_phase) from parsed audit summary."""
    if audit_summary is None:
        return NEXT_BRANCH_HUMAN_CHOICE, NEXT_PHASE_HUMAN_CHOICE
    if audit_summary.get("c2_web_auth_csrf_signal") or (
        audit_summary.get("has_critical") and (
            audit_summary.get("c2_web_auth_csrf_signal")
            or audit_summary.get("c1_safe_validation_signal")
            or audit_summary.get("c3_mcp_approval_signal")
        )
    ):
        return NEXT_BRANCH_HARDEN, NEXT_PHASE_HARDEN1
    if audit_summary.get("has_critical") or audit_summary.get("has_high"):
        return NEXT_BRANCH_HARDEN, NEXT_PHASE_HARDEN1
    return NEXT_BRANCH_UX_OR_HARDEN, NEXT_PHASE_HUMAN_CHOICE


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


# ── ROAD.4 own guardrails ──────────────────────────────────────────────────────

def _road4_guardrails() -> dict[str, bool]:
    """ROAD.4's own boundary booleans — it performs none of these actions."""
    return {
        "chooses_work": False,
        "executes_phases": False,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "worker_launch_performed": False,
        "merge_performed": False,
    }


# ── Phase-level guardrail check ───────────────────────────────────────────────

def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    """Return names of PHASE_GUARDRAIL_FIELDS that are True in a phase dict."""
    return [f for f in PHASE_GUARDRAIL_FIELDS if phase.get(f) is True]


# ── Arc summary ────────────────────────────────────────────────────────────────

def _build_arc_summary(
    arc_name: str,
    required_ids: tuple[str, ...],
    registry_data: Any,
) -> dict[str, Any]:
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

    for pid in required_ids:
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

    return {
        "arc": arc_name,
        "required_phases": list(required_ids),
        "phase_checks": phase_checks,
        "all_complete": all_complete,
        "all_guardrails_ok": all_guardrails_ok,
    }


# ── Artifact coverage ──────────────────────────────────────────────────────────

def _build_artifact_coverage(artifact_root_records: Any) -> dict[str, Any]:
    records = list(artifact_root_records) if isinstance(artifact_root_records, (list, tuple)) else []
    roots_checked: list[dict[str, Any]] = []
    roots_present: list[str] = []
    roots_missing: list[str] = []
    for rec in records:
        rec = rec if isinstance(rec, dict) else {}
        kind = _str(rec.get("kind"))
        rel = _str(rec.get("rel"))
        optional = rec.get("optional", True) is not False
        present = bool(rec.get("present"))
        roots_checked.append({"kind": kind, "path": rel, "optional": optional, "present": present})
        (roots_present if present else roots_missing).append(rel)
    return {
        "roots_checked": roots_checked,
        "roots_present": roots_present,
        "roots_missing": roots_missing,
        "all_present": not roots_missing,
    }


# ── Documentation coverage ────────────────────────────────────────────────────

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


# ── Pure audit builder ─────────────────────────────────────────────────────────

def build_post_eval_cmd_checkpoint_audit(
    *,
    registry_data: Any,
    artifact_root_records: Any = (),
    docs: Any = (),
    registry_load_error: str = "",
    report_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    registry_path: str = "",
    external_audit_text: str | None = None,
    external_audit_path: str = "",
    external_audit_load_error: str = "",
) -> dict[str, Any]:
    """Build the ROAD.4 audit report from pre-gathered inputs.

    Pure: never reads files, writes files, runs commands, or contacts anything.
    ``registry_data`` is the parsed registry dict (or None on load failure);
    ``artifact_root_records`` is a list of {kind, rel, optional, present} dicts
    for directories (not JSON files); ``docs`` is a list of {name, path,
    present, text} dicts.
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

    eval_arc = _build_arc_summary("EVAL", REQUIRED_EVAL_PHASE_IDS, registry_data)
    cmd_arc = _build_arc_summary("CMD", REQUIRED_CMD_PHASE_IDS, registry_data)

    all_checks = eval_arc["phase_checks"] + cmd_arc["phase_checks"]
    for check in all_checks:
        pid = check["phase_id"]
        if not check["present"]:
            blockers.append(f"required phase {pid} is not present in the registry")
        elif not check["complete"]:
            blockers.append(f"required phase {pid} is not complete (status: {check['status']})")
        for field in check.get("guardrail_violations") or []:
            blockers.append(f"phase {pid} has {field}=true; report-only arc violated")

    if safe_to_prepare_count > 0:
        ids = ", ".join(_str(s.get("phase_id")) for s in safe)
        warnings.append(
            f"phase picker reports {safe_to_prepare_count} safe-to-prepare candidate(s) ({ids}); "
            "expected all EVAL/CMD work complete"
        )
    if top_recommendation is not None:
        top_id = _str(top_recommendation.get("phase_id")) if isinstance(top_recommendation, dict) else ""
        warnings.append(f"phase picker still recommends work: {top_id or '(candidate)'}")

    artifact_coverage = _build_artifact_coverage(artifact_root_records)
    for rel in artifact_coverage["roots_missing"]:
        warnings.append(f"expected artifact root not present: {rel}")

    doc_coverage = _build_documentation_coverage(docs)
    for pid in doc_coverage["missing_phase_mentions"]:
        warnings.append(f"phase {pid} is not mentioned in the README or roadmap documentation")

    validation_story = {
        "validation_run": False,
        "note": (
            "ROAD.4 does not run validation commands. The validation commands stored in "
            "the registry for each phase were run externally by the human operator. "
            "No validation results are generated or interpreted by ROAD.4."
        ),
    }

    phase_violations = [
        {"phase_id": c["phase_id"], "field": f}
        for c in all_checks
        for f in (c.get("guardrail_violations") or [])
    ]
    guardrail_summary = {
        "road4_guardrails": _road4_guardrails(),
        "phase_guardrail_fields_checked": list(PHASE_GUARDRAIL_FIELDS),
        "phase_guardrail_violations": phase_violations,
        "all_clear": not phase_violations,
    }

    # ── External audit ────────────────────────────────────────────────────────
    ext_audit_path_norm = _norm_path(external_audit_path) if external_audit_path else ""
    ext_audit_provided = bool(external_audit_path)
    ext_audit_summary: dict[str, Any] | None = None

    if ext_audit_provided:
        if external_audit_load_error or external_audit_text is None:
            warnings.append(
                f"external audit file not found or unreadable: {ext_audit_path_norm or external_audit_path}"
            )
        else:
            ext_audit_summary = parse_external_audit(external_audit_text)

    # Critical/high findings snapshot and recalibrated priority
    critical_findings_snapshot: list[str] = []
    recalibrated_risk_priority: list[str] = []
    security_debt_carryover: list[str] = []
    if ext_audit_summary is not None:
        if ext_audit_summary.get("c2_web_auth_csrf_signal"):
            critical_findings_snapshot.append("C2 - Web UI no auth/CSRF - confirmed critical RCE")
        if ext_audit_summary.get("c1_safe_validation_signal"):
            critical_findings_snapshot.append("C1 - shell=True validation - real, downgraded to high")
        if ext_audit_summary.get("c3_mcp_approval_signal"):
            critical_findings_snapshot.append("C3 - MCP approval flag never enforced - real, high")
        recalibrated_risk_priority = list(ext_audit_summary.get("recalibrated_priority") or [])
        security_debt_carryover = [
            f"critical: {ext_audit_summary['critical_count']}",
            f"high: {ext_audit_summary['high_count']}",
            f"medium: {ext_audit_summary['medium_count']}",
            f"low: {ext_audit_summary['low_count']}",
        ]

    # Next branch / phase recommendation
    rec_branch, rec_phase = _recommend_next_branch(ext_audit_summary, external_audit_path)

    open_questions: list[str] = []
    if artifact_coverage["roots_missing"]:
        open_questions.append(
            "Some expected artifact root directories are absent. "
            "Were all EVAL/CMD phases run and artifacts written before this audit?"
        )
    if doc_coverage["missing_phase_mentions"]:
        open_questions.append(
            "Some phases are not mentioned in the README or roadmap. "
            "Should documentation be updated before freezing this checkpoint?"
        )

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)

    if blockers:
        status = STATUS_BLOCKED
        reason = f"{len(blockers)} blocker(s) prevent checkpoint passage"
    elif warnings:
        status = STATUS_WARN
        reason = f"{len(warnings)} warning(s) noted; checkpoint passes with warnings"
    else:
        status = STATUS_PASS
        reason = "all EVAL/CMD phases complete, report-only, artifact-backed, and documented"

    # Resolve recommended_next_step (may be upgraded to hardening if audit signals critical)
    if status == STATUS_PASS and rec_branch == NEXT_BRANCH_HARDEN:
        recommended_next_step = NEXT_STEP_HARDEN
    else:
        recommended_next_step = NEXT_STEP_BY_STATUS[status]

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": _str(report_id),
        "created_at": _str(created_at),
        "repo_path": _norm_path(repo_path) if repo_path else "",
        "registry_path": _norm_path(registry_path) if registry_path else "",
        "external_audit_path": ext_audit_path_norm,
        "audit_status": status,
        "audit_reason": reason,
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
        "eval_arc_summary": eval_arc,
        "cmd_arc_summary": cmd_arc,
        "artifact_coverage": artifact_coverage,
        "documentation_coverage": doc_coverage,
        "validation_story": validation_story,
        "external_audit_summary": ext_audit_summary if ext_audit_summary is not None else {},
        "critical_findings_snapshot": critical_findings_snapshot,
        "recalibrated_risk_priority": recalibrated_risk_priority,
        "security_debt_carryover": security_debt_carryover,
        "guardrail_summary": guardrail_summary,
        "open_questions": open_questions,
        "recommended_next_branch": rec_branch,
        "recommended_next_phase": rec_phase,
        "recommended_next_step": recommended_next_step,
        "warnings": warnings,
        "blockers": blockers,
        "boundaries": list(ROAD4_BOUNDARIES),
    }


# ── Markdown renderer ──────────────────────────────────────────────────────────

def render_post_eval_cmd_checkpoint_audit_markdown(report: dict[str, Any]) -> str:
    """Render the ROAD.4 audit as operator-readable Markdown."""
    lines: list[str] = [
        "# Post-EVAL/CMD Checkpoint Audit",
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
        f"- **Audit status:** `{_md(report.get('audit_status') or '(none)')}`",
        f"- **Audit reason:** {_md(report.get('audit_reason') or '(none)')}",
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

    def _arc_section(header: str, arc: dict[str, Any]) -> None:
        lines.extend([f"## {header}", ""])
        lines.append(f"- **All complete:** {_lower(bool(arc.get('all_complete')))}")
        lines.append(f"- **All guardrails ok:** {_lower(bool(arc.get('all_guardrails_ok')))}")
        checks = arc.get("phase_checks") or []
        if checks:
            lines.extend([
                "",
                "| Phase | Present | Status | Complete | Guardrails OK | Violations |",
                "| --- | --- | --- | --- | --- | --- |",
            ])
            for c in checks:
                viols = ", ".join(c.get("guardrail_violations") or []) or "(none)"
                lines.append(
                    f"| {_md(c.get('phase_id'))} | {_lower(bool(c.get('present')))} | "
                    f"{_md(c.get('status'))} | {_lower(bool(c.get('complete')))} | "
                    f"{_lower(bool(c.get('guardrails_ok')))} | {_md(viols)} |"
                )
        lines.append("")

    _arc_section("EVAL Arc Summary", report.get("eval_arc_summary") or {})
    _arc_section("CMD Arc Summary", report.get("cmd_arc_summary") or {})

    lines += ["## Artifact Coverage", ""]
    art = report.get("artifact_coverage") or {}
    lines.append(f"- **All present:** {_lower(bool(art.get('all_present')))}")
    lines.append(f"- **Missing:** {', '.join(art.get('roots_missing') or []) or '(none)'}")
    roots = art.get("roots_checked") or []
    if roots:
        lines += ["", "| Kind | Path | Optional | Present |", "| --- | --- | --- | --- |"]
        for r in roots:
            lines.append(
                f"| {_md(r.get('kind'))} | `{_md(r.get('path'))}` | "
                f"{_lower(bool(r.get('optional')))} | {_lower(bool(r.get('present')))} |"
            )
    lines.append("")

    lines += ["## Documentation Coverage", ""]
    doc = report.get("documentation_coverage") or {}
    lines.append(f"- **README:** `{_md(doc.get('readme_path') or '(none)')}`")
    lines.append(f"- **Roadmap:** `{_md(doc.get('roadmap_path') or '(none)')}`")
    missing_docs = doc.get("missing_phase_mentions") or []
    lines.append(f"- **Phases missing from docs:** {', '.join(missing_docs) or '(none)'}")
    mentions = doc.get("mentions") or {}
    if mentions:
        lines += ["", "| Phase | In README | In roadmap |", "| --- | --- | --- |"]
        for pid in doc.get("checked_phase_ids") or []:
            entry = mentions.get(pid) or {}
            lines.append(
                f"| {_md(pid)} | {_lower(bool(entry.get('in_readme')))} | "
                f"{_lower(bool(entry.get('in_roadmap')))} |"
            )
    lines.append("")

    lines += ["## Validation Story", ""]
    vs = report.get("validation_story") or {}
    lines.append(f"- **Validation run:** {_lower(bool(vs.get('validation_run')))}")
    lines.append(f"- {_md(vs.get('note') or '(none)')}")
    lines.append("")

    lines += ["## External Audit Summary", ""]
    ext_path = report.get("external_audit_path") or "(none)"
    lines.append(f"- **External audit path:** `{_md(ext_path)}`")
    ea = report.get("external_audit_summary") or {}
    if ea:
        lines.append(f"- **Tally:** {_md(ea.get('tally_line') or '(not found)')}")
        lines.append(f"- **Critical count:** {ea.get('critical_count', 0)}")
        lines.append(f"- **High count:** {ea.get('high_count', 0)}")
        lines.append(f"- **C2 / web auth / CSRF signal:** {_lower(bool(ea.get('c2_web_auth_csrf_signal')))}")
        lines.append(f"- **C1 / safe validation signal:** {_lower(bool(ea.get('c1_safe_validation_signal')))}")
        lines.append(f"- **C3 / MCP approval signal:** {_lower(bool(ea.get('c3_mcp_approval_signal')))}")
        bullets = ea.get("exec_summary_bullets") or []
        if bullets:
            lines += ["", "**Executive summary:**", ""]
            lines += [f"- {_md(b)}" for b in bullets[:5]]
    else:
        lines.append("- _(no external audit provided or file not found)_")
    lines.append("")

    lines += ["## Critical Findings Snapshot", ""]
    cfs = report.get("critical_findings_snapshot") or []
    if cfs:
        for f in cfs:
            lines.append(f"- {_md(f)}")
    else:
        lines.append("_None — no external audit or no confirmed critical findings._")
    lines.append("")

    lines += ["## Recalibrated Risk Priority", ""]
    rrp = report.get("recalibrated_risk_priority") or []
    if rrp:
        for item in rrp:
            lines.append(f"- {_md(item)}")
    else:
        lines.append("_Not available — see external audit for details._")
    lines.append("")

    lines += ["## Security Debt Carryover", ""]
    sdc = report.get("security_debt_carryover") or []
    if sdc:
        for item in sdc:
            lines.append(f"- {_md(item)}")
    else:
        lines.append("_Not available — provide external audit to populate._")
    lines.append("")

    lines += ["## Recommended Next Branch", ""]
    lines.append(f"- **Branch:** `{_md(report.get('recommended_next_branch') or '(none)')}`")
    lines.append(f"- **Phase:** `{_md(report.get('recommended_next_phase') or '(none)')}`")
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
        lines.append("- No required phase reports any execution power.")
    road4_g = gs.get("road4_guardrails") or {}
    if road4_g:
        lines += ["", "**ROAD.4 own guardrails (all false):**", ""]
        for k, v in sorted(road4_g.items()):
            lines.append(f"- `{_md(k)}`: {_lower(bool(v))}")
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
        lines.append("_None — the EVAL and CMD arcs are complete._")
    lines.append("")

    lines += ["## Boundaries", ""]
    for b in (report.get("boundaries") or list(ROAD4_BOUNDARIES)):
        lines.append(f"- {_md(b)}")
    lines.append("")

    return "\n".join(lines) + "\n"


# ── Input gathering (read-only) ───────────────────────────────────────────────

def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read or parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def gather_post_eval_cmd_checkpoint_inputs(
    repo_path: str | Path,
    registry_path: str | Path,
    *,
    external_audit_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read registry, artifact root dirs, docs, and optional external audit.

    Pure read-only: never writes, runs commands, or contacts anything.
    """
    repo = Path(repo_path)
    registry_data, registry_load_error = _load_json_object(Path(registry_path))

    artifact_root_records: list[dict[str, Any]] = []
    for kind, rel, optional in EXPECTED_ARTIFACT_ROOTS:
        target = repo / rel
        artifact_root_records.append({
            "kind": kind,
            "rel": rel,
            "optional": optional,
            "present": target.is_dir(),
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

    ext_audit_text: str | None = None
    ext_audit_load_error = ""
    ext_audit_path_str = str(external_audit_path) if external_audit_path else ""
    if external_audit_path:
        target = Path(external_audit_path)
        try:
            ext_audit_text = target.read_text(encoding="utf-8")
        except OSError as exc:
            ext_audit_load_error = f"could not read external audit {_norm_path(target)}: {exc}"

    return {
        "registry_data": registry_data,
        "registry_load_error": registry_load_error,
        "artifact_root_records": artifact_root_records,
        "docs": docs,
        "external_audit_text": ext_audit_text,
        "external_audit_path": ext_audit_path_str,
        "external_audit_load_error": ext_audit_load_error,
    }


# ── Report writing ─────────────────────────────────────────────────────────────

def write_post_eval_cmd_checkpoint_audit(
    repo_path: str | Path,
    registry_path: str | Path,
    output_dir: str | Path,
    *,
    report_id: str = "",
    created_at: str = "",
    external_audit_path: str | Path | None = None,
) -> dict[str, Any]:
    """Gather inputs, build the audit, and write JSON + Markdown artifacts.

    Returns ``{ok, json_path, md_path, report}``. Nothing outside ``output_dir``
    is written and nothing is run or contacted.
    """
    inputs = gather_post_eval_cmd_checkpoint_inputs(
        repo_path, registry_path, external_audit_path=external_audit_path
    )
    report = build_post_eval_cmd_checkpoint_audit(
        registry_data=inputs["registry_data"],
        registry_load_error=inputs["registry_load_error"],
        artifact_root_records=inputs["artifact_root_records"],
        docs=inputs["docs"],
        external_audit_text=inputs["external_audit_text"],
        external_audit_path=inputs["external_audit_path"],
        external_audit_load_error=inputs["external_audit_load_error"],
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
    md_path.write_text(render_post_eval_cmd_checkpoint_audit_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
