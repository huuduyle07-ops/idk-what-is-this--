"""ROAD.3 — Post-MODEL Checkpoint Audit (report-only).

Reads the existing roadmap registry, the registry and picker reports, the generated
model-lab and automation-contract artifacts, and the documentation, then writes a
deterministic checkpoint audit report that verifies the completed roadmap arc all
agrees: the registry is valid, every expected phase is complete, the picker
recommends no further work, every inspected artifact carries no hidden execution
power, and the docs mention every phase.

Core principle: ROAD.3 audits the completed roadmap arc. It does not choose new
work, execute phases, run validation or a benchmark check, call models or
embeddings, contact a network service, run git, apply patches, launch workers,
write to a database, or promote, merge, block, or retrieve lessons. It only reads
existing files and writes an audit report.

ROAD.3 reuses the ROAD.2 picker (``core.phase_picker.pick_phase_candidates``),
which itself reuses the ROAD.1 validator, to derive the authoritative registry
validity, phase counts, completed-phase set, safe-candidate count, and top
recommendation from the registry, then cross-checks the generated reports against
those values. The picker only classifies metadata; nothing is run.

This module is stdlib-only apart from that one in-repo import, and pure apart from
``gather_checkpoint_inputs`` / ``write_checkpoint_audit`` (which read input files
and write the two report artifacts). It never mutates any input.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.phase_picker import pick_phase_candidates  # ROAD.3 reuses the ROAD.2 picker.


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "checkpoint_audit_report"

#: The completed roadmap arc ROAD.3 audits (the eight phases shipped before it).
DEFAULT_EXPECTED_COMPLETE_PHASES: tuple[str, ...] = (
    "ROAD.1",
    "ROAD.2",
    "AUTO.2a",
    "AUTO.2b",
    "AUTO.2c",
    "MODEL.1",
    "MODEL.2",
    "MODEL.3",
)

#: Phase ids whose mention is checked in the README and roadmap documentation
#: (the audited arc plus ROAD.3 itself).
DOC_PHASE_IDS: tuple[str, ...] = DEFAULT_EXPECTED_COMPLETE_PHASES + ("ROAD.3",)

#: Guardrail booleans that, if ``True`` anywhere inside an inspected artifact,
#: indicate hidden execution power and produce a blocker.
GUARDRAIL_EXECUTION_FIELDS: frozenset[str] = frozenset({
    "model_call_performed",
    "model_api_call_performed",
    "llm_call_performed",
    "embedding_call_performed",
    "network_call_performed",
    "database_write_performed",
    "patch_applied",
    "patch_applied_to_real_repo",
    "validation_run",
    "validation_run_by_tool",
    "benchmark_run",
    "benchmark_run_by_tool",
    "worker_launch_performed",
    "merge_performed",
    "push_performed",
    "pr_created",
    "branch_created",
    "github_contacted",
    "telegram_message_sent",
    "n8n_contacted",
    "lesson_promotion_performed",
    "lesson_merge_performed",
    "lesson_block_performed",
    "lesson_retrieval_changed",
    "prompt_injection_changed",
    "live_routing_performed",
    "driver_override_performed",
})

#: (kind, repo-relative path, optional) for every artifact ROAD.3 inspects. Each is
#: optional: a missing one is a warning, never a crash.
INSPECTED_ARTIFACT_SPECS: tuple[tuple[str, str, bool], ...] = (
    ("phase_registry_report", ".agent/roadmap/phase_registry_report.json", True),
    ("phase_picker_report", ".agent/roadmap/phase_picker_report.json", True),
    ("artifact_dataset_report", ".agent/model_lab/artifact_dataset/artifact_dataset_report.json", True),
    (
        "driver_classifier_baseline_report",
        ".agent/model_lab/driver_classifier_baseline/driver_classifier_baseline_report.json",
        True,
    ),
    (
        "lesson_activation_dataset_report",
        ".agent/model_lab/lesson_activation_dataset/lesson_activation_dataset_report.json",
        True,
    ),
    ("telegram_evidence_contract", ".agent/automation_contracts/telegram_evidence_contract.json", True),
    ("github_pr_safety_contract", ".agent/automation_contracts/github_pr_safety_contract.json", True),
    ("n8n_orchestration_dry_run", ".agent/automation_contracts/n8n_orchestration_dry_run.json", True),
)

#: Documentation files scanned for phase mentions, relative to the repo root.
DEFAULT_README_REL = "README.md"
DEFAULT_ROADMAP_REL = "docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-07.md"

#: Report artifact filenames.
JSON_NAME = "checkpoint_audit_report.json"
MD_NAME = "checkpoint_audit_report.md"

#: Verdicts and their recommended next step.
VERDICT_PASS = "pass"
VERDICT_WARN = "warn"
VERDICT_FAIL = "fail"
NEXT_STEP_BY_VERDICT: dict[str, str] = {
    VERDICT_PASS: "freeze_current_roadmap_and_plan_next_map",
    VERDICT_WARN: "review_checkpoint_warnings",
    VERDICT_FAIL: "fix_checkpoint_blockers",
}

CHECKPOINT_AUDIT_GUARDRAIL_NOTE = (
    "Post-MODEL Checkpoint Audit is report-only: it reads the roadmap registry, the "
    "registry and picker reports, the generated model-lab and automation-contract "
    "artifacts, and the docs, then verifies the completed roadmap arc agrees. It does "
    "not choose new work, execute phases, run validation or a benchmark check, call "
    "models or embeddings, contact a network service, run git, apply patches, launch "
    "workers, write to a database, or promote, merge, block, or retrieve lessons. It "
    "only reads existing files and writes an audit report."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _norm_path(value: Any) -> str:
    return str(value).replace("\\", "/").strip()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _lower(value: bool) -> str:
    return str(bool(value)).lower()


# ── Guardrail inspection (recursive, read-only) ─────────────────────────────────

def _iter_guardrail_breaches(node: Any, location: str = "") -> list[tuple[str, str]]:
    """Walk a parsed artifact and return ``(location, field)`` for every guardrail
    field that is literally ``True`` anywhere inside it.

    Recurses through nested dicts and lists, so a breach is found wherever it hides.
    Only a boolean ``True`` counts; falsey or non-boolean values are inert.
    """
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            key_str = str(key)
            child_loc = f"{location}.{key_str}" if location else key_str
            if key_str in GUARDRAIL_EXECUTION_FIELDS and value is True:
                found.append((child_loc, key_str))
            if isinstance(value, (dict, list)):
                found.extend(_iter_guardrail_breaches(value, child_loc))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            child_loc = f"{location}[{index}]"
            if isinstance(item, (dict, list)):
                found.extend(_iter_guardrail_breaches(item, child_loc))
    return found


def _picker_safe_count(artifact: dict[str, Any]) -> int | None:
    counts = artifact.get("bucket_counts")
    if isinstance(counts, dict) and "safe_to_prepare" in counts:
        try:
            return int(counts["safe_to_prepare"])
        except (TypeError, ValueError):
            return None
    safe = artifact.get("safe_to_prepare")
    if isinstance(safe, list):
        return len(safe)
    return None


def _artifact_summary(artifact: dict[str, Any]) -> str:
    parts: list[str] = []
    report_kind = _str(artifact.get("report_kind"))
    if report_kind:
        parts.append(report_kind)
    for key in ("checkpoint_verdict", "overall_verdict", "final_verdict", "verdict"):
        value = _str(artifact.get(key))
        if value:
            parts.append(f"verdict={value}")
            break
    if "is_valid" in artifact:
        parts.append(f"valid={_lower(bool(artifact.get('is_valid')))}")
    if "registry_valid" in artifact:
        parts.append(f"registry_valid={_lower(bool(artifact.get('registry_valid')))}")
    safe = _picker_safe_count(artifact)
    if safe is not None:
        parts.append(f"safe_to_prepare={safe}")
    for key in ("row_count", "phase_count"):
        if key in artifact:
            parts.append(f"{key}={artifact.get(key)}")
    return ", ".join(parts) or "(present)"


def _agreement_warnings(
    kind: str,
    artifact: dict[str, Any],
    path: str,
    *,
    registry_valid: bool,
    safe_to_prepare_count: int,
    top_present: bool,
) -> list[str]:
    """Cross-check a generated report against the authoritative registry-derived
    values. Only fires when the report actually carries the field being compared."""
    out: list[str] = []
    if kind == "phase_registry_report" and "is_valid" in artifact:
        reported = bool(artifact.get("is_valid"))
        if reported != registry_valid:
            out.append(
                f"phase_registry_report ({path}) reports is_valid={_lower(reported)} but the "
                f"registry currently validates as {_lower(registry_valid)} (stale report?)"
            )
    if kind == "phase_picker_report":
        reported_safe = _picker_safe_count(artifact)
        if reported_safe is not None and reported_safe != safe_to_prepare_count:
            out.append(
                f"phase_picker_report ({path}) reports {reported_safe} safe-to-prepare "
                f"candidate(s) but the registry currently yields {safe_to_prepare_count} (stale report?)"
            )
        if "top_recommendation" in artifact:
            reported_top = artifact.get("top_recommendation") is not None
            if reported_top != top_present:
                out.append(
                    f"phase_picker_report ({path}) top_recommendation presence disagrees with the "
                    f"current registry (stale report?)"
                )
    return out


def _inspect_one_artifact(
    record: Any,
    *,
    registry_valid: bool,
    safe_to_prepare_count: int,
    top_present: bool,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Inspect one artifact record. Returns ``(artifact_check, breaches)``."""
    record = record if isinstance(record, dict) else {}
    path = _norm_path(record.get("path"))
    kind = _str(record.get("kind"))
    optional = record.get("optional", True) is not False
    present = bool(record.get("present"))
    artifact = record.get("artifact")
    load_error = _str(record.get("load_error"))
    loaded = present and isinstance(artifact, dict)

    warnings: list[str] = []
    blockers: list[str] = []
    breaches: list[dict[str, str]] = []
    report_kind = ""
    summary = ""
    guardrails_ok = True

    if not present:
        if optional:
            warnings.append(f"optional artifact not present: {path}")
        else:
            blockers.append(f"required artifact not present: {path}")
            guardrails_ok = False
    elif not loaded:
        warnings.append(f"skipped artifact {path}: {load_error or 'artifact is not a JSON object'}")
    else:
        report_kind = _str(artifact.get("report_kind"))
        summary = _artifact_summary(artifact)
        for location, field in _iter_guardrail_breaches(artifact):
            breaches.append({"path": path, "kind": kind, "field": field, "location": location})
            blockers.append(
                f"artifact {path} reports execution power: {field} is true (at {location})"
            )
        guardrails_ok = not breaches
        warnings.extend(
            _agreement_warnings(
                kind,
                artifact,
                path,
                registry_valid=registry_valid,
                safe_to_prepare_count=safe_to_prepare_count,
                top_present=top_present,
            )
        )

    check = {
        "path": path,
        "kind": kind,
        "present": present,
        "loaded": loaded,
        "report_kind": report_kind,
        "summary": summary,
        "guardrails_ok": guardrails_ok,
        "warnings": warnings,
        "blockers": blockers,
    }
    return check, breaches


# ── Documentation / validation / git-history checks ─────────────────────────────

def _build_docs_checks(docs: Any) -> dict[str, Any]:
    docs = list(docs) if isinstance(docs, (list, tuple)) else []
    doc_records: list[dict[str, Any]] = []
    texts: dict[str, tuple[bool, str]] = {}
    for entry in docs:
        entry = entry if isinstance(entry, dict) else {}
        name = _str(entry.get("name"))
        present = bool(entry.get("present", True))
        text = _str(entry.get("text"))
        texts[name] = (present, text)
        doc_records.append({"name": name, "path": _norm_path(entry.get("path")), "present": present})

    def _doc_text(*names: str) -> tuple[str, bool]:
        for name in names:
            if name in texts:
                present, text = texts[name]
                return text, present
        return "", False

    readme_text, _readme_present = _doc_text("README", "readme")
    roadmap_text, _roadmap_present = _doc_text("roadmap", "ROADMAP")
    readme_path = next((d["path"] for d in doc_records if d["name"] in ("README", "readme")), DEFAULT_README_REL)
    roadmap_path = next((d["path"] for d in doc_records if d["name"] in ("roadmap", "ROADMAP")), DEFAULT_ROADMAP_REL)

    mentions: dict[str, dict[str, bool]] = {}
    missing_from_readme: list[str] = []
    missing_from_roadmap: list[str] = []
    missing_everywhere: list[str] = []
    for pid in DOC_PHASE_IDS:
        in_readme = pid in readme_text
        in_roadmap = pid in roadmap_text
        mentioned = in_readme or in_roadmap
        mentions[pid] = {"in_readme": in_readme, "in_roadmap": in_roadmap, "mentioned": mentioned}
        if not in_readme:
            missing_from_readme.append(pid)
        if not in_roadmap:
            missing_from_roadmap.append(pid)
        if not mentioned:
            missing_everywhere.append(pid)

    return {
        "readme_path": readme_path,
        "roadmap_path": roadmap_path,
        "docs": doc_records,
        "checked_phase_ids": list(DOC_PHASE_IDS),
        "mentions": mentions,
        "missing_from_readme": missing_from_readme,
        "missing_from_roadmap": missing_from_roadmap,
        "missing_phase_mentions": missing_everywhere,
    }


def _build_validation_summary(supplied: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "full_pytest_reported": False,
        "benchmark_check_reported": False,
        "compileall_reported": False,
        "source": "not provided (ROAD.3 does not run validation or benchmarks)",
    }
    if isinstance(supplied, dict):
        for key in ("full_pytest_reported", "benchmark_check_reported", "compileall_reported"):
            if key in supplied:
                summary[key] = bool(supplied.get(key))
        if supplied.get("source"):
            summary["source"] = _str(supplied.get("source"))
    return summary


def _build_git_history_checks(git_history: Any) -> dict[str, Any]:
    note = "git history not checked by ROAD.3 because ROAD.3 does not run git"
    checks: dict[str, Any] = {
        "git_history_checked": False,
        "source": "",
        "warnings": [note],
        "notes": [
            "ROAD.3 records version-control history only from supplied metadata; it never runs git itself."
        ],
    }
    if isinstance(git_history, dict):
        if git_history.get("source"):
            checks["source"] = _str(git_history.get("source"))
        if git_history.get("git_history_checked") is True:
            checks["git_history_checked"] = True
            checks["warnings"] = []
            checks["notes"] = [
                "History metadata was supplied to ROAD.3; ROAD.3 did not run git itself."
            ]
    return checks


def _guardrails() -> dict[str, bool]:
    """ROAD.3's own boundary booleans — it performs none of these actions."""
    return {
        "chooses_work": False,
        "executes_phases": False,
        "model_call_performed": False,
        "embedding_call_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "worker_launch_performed": False,
        "lesson_promotion_performed": False,
        "merge_performed": False,
        "git_command_performed": False,
    }


# ── Audit assembly ──────────────────────────────────────────────────────────────

def build_checkpoint_audit(
    *,
    registry_data: Any,
    artifacts: Any = (),
    docs: Any = (),
    expected_complete_phases: Any = None,
    validation_summary: Any = None,
    git_history: Any = None,
    registry_load_error: str = "",
    report_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    registry_path: str = "",
) -> dict[str, Any]:
    """Build the deterministic checkpoint audit report from already-gathered inputs.

    Pure: never reads, writes, runs, or contacts anything, and never mutates its
    inputs. ``registry_data`` is the parsed registry dict (or ``None``); ``artifacts``
    is a list of ``{path, kind, optional, present, artifact, load_error}`` records;
    ``docs`` is a list of ``{name, path, present, text}`` records.
    """
    expected = [
        str(pid)
        for pid in (
            expected_complete_phases
            if expected_complete_phases is not None
            else DEFAULT_EXPECTED_COMPLETE_PHASES
        )
    ]

    # Authoritative registry-derived state (via the ROAD.2 picker / ROAD.1 validator).
    pick = pick_phase_candidates(registry_data)
    registry_valid = bool(pick.get("registry_valid"))
    registry_errors = list(pick.get("errors") or [])
    registry_warnings = list(pick.get("warnings") or [])
    phase_count = int(pick.get("phase_count", 0) or 0)
    buckets = pick.get("buckets") or {}
    safe = list(buckets.get("safe_to_prepare") or [])
    safe_to_prepare_count = len(safe)
    top_recommendation = pick.get("top_recommendation")
    top_present = top_recommendation is not None

    complete_summaries = list(buckets.get("complete_or_history") or [])
    observed_complete_phases = sorted(
        {str(s.get("phase_id", "")).strip() for s in complete_summaries if str(s.get("phase_id", "")).strip()}
    )
    observed_set = set(observed_complete_phases)
    complete_phase_count = len(observed_complete_phases)

    missing_expected_phases = [pid for pid in expected if pid not in observed_set]

    root = registry_data if isinstance(registry_data, dict) else {}
    raw_phases = root.get("phases")
    phase_dicts = [p for p in raw_phases if isinstance(p, dict)] if isinstance(raw_phases, list) else []
    unexpected_incomplete_phases = sorted(
        {
            str(p.get("phase_id", "")).strip()
            for p in phase_dicts
            if str(p.get("status", "")) not in ("complete", "parked", "deferred")
            and str(p.get("phase_id", "")).strip()
        }
    )

    blockers: list[str] = []
    warnings: list[str] = []

    # ── Registry validity ───────────────────────────────────────────────────────
    if registry_load_error:
        blockers.append(f"phase registry could not be read: {registry_load_error}")
    if not registry_valid:
        detail = "; ".join(registry_errors[:5])
        blockers.append("phase registry is invalid" + (f": {detail}" if detail else ""))

    # ── Expected completion ──────────────────────────────────────────────────────
    for pid in missing_expected_phases:
        blockers.append(f"expected phase {pid} is not complete in the registry")

    # ── Picker must recommend nothing ────────────────────────────────────────────
    if safe_to_prepare_count > 0:
        ids = ", ".join(str(s.get("phase_id", "")) for s in safe)
        blockers.append(
            f"phase picker still reports {safe_to_prepare_count} safe-to-prepare candidate(s) "
            f"({ids}); the roadmap arc is not closed"
        )
    if top_present:
        top_id = str(top_recommendation.get("phase_id", "")) if isinstance(top_recommendation, dict) else ""
        blockers.append(f"phase picker still recommends work: {top_id or '(candidate)'}")

    # ── Unexpected pending phases (warning; the arc is not fully frozen) ─────────
    for pid in unexpected_incomplete_phases:
        warnings.append(f"registry phase {pid} is not complete; the roadmap arc is not fully frozen")

    # ── Inspected artifacts ─────────────────────────────────────────────────────
    artifact_records = list(artifacts) if isinstance(artifacts, (list, tuple)) else []
    artifact_checks: list[dict[str, Any]] = []
    all_breaches: list[dict[str, str]] = []
    for record in artifact_records:
        check, breaches = _inspect_one_artifact(
            record,
            registry_valid=registry_valid,
            safe_to_prepare_count=safe_to_prepare_count,
            top_present=top_present,
        )
        artifact_checks.append(check)
        all_breaches.extend(breaches)
        blockers.extend(check["blockers"])
        warnings.extend(check["warnings"])

    guardrail_checks = {
        "inspected_fields": sorted(GUARDRAIL_EXECUTION_FIELDS),
        "artifacts_inspected": sum(1 for c in artifact_checks if c["loaded"]),
        "breaches": all_breaches,
        "all_clear": not all_breaches,
    }

    # ── Documentation ────────────────────────────────────────────────────────────
    docs_checks = _build_docs_checks(docs)
    for pid in docs_checks["missing_phase_mentions"]:
        warnings.append(f"phase {pid} is not mentioned in the README or roadmap documentation")

    # ── Validation + git history (informational; ROAD.3 runs neither) ───────────
    validation_summary_out = _build_validation_summary(validation_summary)
    git_history_checks = _build_git_history_checks(git_history)

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)

    if blockers:
        verdict = VERDICT_FAIL
    elif warnings:
        verdict = VERDICT_WARN
    else:
        verdict = VERDICT_PASS

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": CHECKPOINT_AUDIT_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm_path(repo_path) if repo_path else "",
        "registry_path": _norm_path(registry_path) if registry_path else "",
        "phase_count": phase_count,
        "registry_valid": registry_valid,
        "registry_errors": registry_errors,
        "registry_warnings": registry_warnings,
        "complete_phase_count": complete_phase_count,
        "safe_to_prepare_count": safe_to_prepare_count,
        "top_recommendation": top_recommendation,
        "expected_complete_phases": expected,
        "observed_complete_phases": observed_complete_phases,
        "missing_expected_phases": missing_expected_phases,
        "unexpected_incomplete_phases": unexpected_incomplete_phases,
        "artifact_checks": artifact_checks,
        "guardrail_checks": guardrail_checks,
        "validation_summary": validation_summary_out,
        "docs_checks": docs_checks,
        "git_history_checks": git_history_checks,
        "warnings": warnings,
        "blockers": blockers,
        "checkpoint_verdict": verdict,
        "recommended_next_step": NEXT_STEP_BY_VERDICT[verdict],
        "guardrails": _guardrails(),
    }


# ── Markdown rendering ──────────────────────────────────────────────────────────

def render_checkpoint_audit_markdown(report: dict[str, Any]) -> str:
    """Render a checkpoint audit record as one operator-readable Markdown document."""
    verdict = _str(report.get("checkpoint_verdict"))
    lines: list[str] = [
        "# Post-MODEL Checkpoint Audit",
        "",
        f"> {report.get('guardrail_note', CHECKPOINT_AUDIT_GUARDRAIL_NOTE)}",
        "",
        "_Report only: ROAD.3 audits the completed roadmap arc by reading existing files. "
        "It chooses no work, runs nothing, contacts nothing, and changes no runtime behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Registry path:** `{_md(report.get('registry_path') or '(none)')}`",
        f"- **Checkpoint verdict:** `{_md(verdict or '(none)')}`",
        f"- **Recommended next step:** `{_md(report.get('recommended_next_step') or '(none)')}`",
        f"- **Registry valid:** {_lower(bool(report.get('registry_valid')))}",
        f"- **Phase count:** {report.get('phase_count', 0)}",
        f"- **Complete phase count:** {report.get('complete_phase_count', 0)}",
        f"- **Safe-to-prepare count:** {report.get('safe_to_prepare_count', 0)}",
        f"- **Top recommendation:** {_top_text(report.get('top_recommendation'))}",
        "",
    ]

    # Phase registry check
    lines += ["## Phase Registry Check", ""]
    lines.append(f"- **Registry valid:** {_lower(bool(report.get('registry_valid')))}")
    lines.append(f"- **Expected complete phases:** {', '.join(report.get('expected_complete_phases') or []) or '(none)'}")
    lines.append(f"- **Observed complete phases:** {', '.join(report.get('observed_complete_phases') or []) or '(none)'}")
    lines.append(f"- **Missing expected phases:** {', '.join(report.get('missing_expected_phases') or []) or '(none)'}")
    lines.append(f"- **Unexpected incomplete phases:** {', '.join(report.get('unexpected_incomplete_phases') or []) or '(none)'}")
    registry_errors = report.get("registry_errors") or []
    if registry_errors:
        lines += ["", "**Registry errors:**", ""]
        lines += [f"- {_md(error)}" for error in registry_errors]
    lines.append("")

    # Phase picker check
    lines += ["## Phase Picker Check", ""]
    lines.append(f"- **Safe-to-prepare count:** {report.get('safe_to_prepare_count', 0)}")
    lines.append(f"- **Top recommendation:** {_top_text(report.get('top_recommendation'))}")
    lines.append(
        "- **Recommends no further work:** "
        f"{_lower(report.get('safe_to_prepare_count', 0) == 0 and report.get('top_recommendation') is None)}"
    )
    lines.append("")

    # Artifact checks
    lines += ["## Artifact Checks", ""]
    checks = report.get("artifact_checks") or []
    if checks:
        lines += [
            "| Path | Kind | Present | Loaded | Guardrails OK | Summary |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for check in checks:
            lines.append(
                f"| `{_md(check.get('path'))}` | {_md(check.get('kind'))} | "
                f"{_lower(bool(check.get('present')))} | {_lower(bool(check.get('loaded')))} | "
                f"{_lower(bool(check.get('guardrails_ok')))} | {_md(check.get('summary') or '(n/a)')} |"
            )
    else:
        lines.append("_None inspected._")
    lines.append("")

    # Guardrail checks
    lines += ["## Guardrail Checks", ""]
    guardrail_checks = report.get("guardrail_checks") or {}
    lines.append(f"- **Artifacts inspected:** {guardrail_checks.get('artifacts_inspected', 0)}")
    lines.append(f"- **All clear:** {_lower(bool(guardrail_checks.get('all_clear')))}")
    breaches = guardrail_checks.get("breaches") or []
    if breaches:
        lines += ["", "**Execution-power breaches:**", ""]
        for breach in breaches:
            lines.append(
                f"- `{_md(breach.get('field'))}` is true at `{_md(breach.get('location'))}` "
                f"in `{_md(breach.get('path'))}`"
            )
    else:
        lines.append("- No inspected artifact reports any hidden execution power.")
    lines.append("")

    # Validation summary
    lines += ["## Validation Summary", ""]
    validation = report.get("validation_summary") or {}
    lines.append(f"- **Full test suite reported:** {_lower(bool(validation.get('full_pytest_reported')))}")
    lines.append(f"- **Benchmark check reported:** {_lower(bool(validation.get('benchmark_check_reported')))}")
    lines.append(f"- **Compile-all reported:** {_lower(bool(validation.get('compileall_reported')))}")
    lines.append(f"- **Source:** {_md(validation.get('source') or '(none)')}")
    lines.append("")

    # Documentation checks
    lines += ["## Documentation Checks", ""]
    docs_checks = report.get("docs_checks") or {}
    lines.append(f"- **README:** `{_md(docs_checks.get('readme_path') or '(none)')}`")
    lines.append(f"- **Roadmap:** `{_md(docs_checks.get('roadmap_path') or '(none)')}`")
    missing_docs = docs_checks.get("missing_phase_mentions") or []
    lines.append(f"- **Phases missing from docs:** {', '.join(missing_docs) or '(none)'}")
    mentions = docs_checks.get("mentions") or {}
    if mentions:
        lines += ["", "| Phase | In README | In roadmap |", "| --- | --- | --- |"]
        for pid in docs_checks.get("checked_phase_ids") or []:
            entry = mentions.get(pid) or {}
            lines.append(
                f"| {_md(pid)} | {_lower(bool(entry.get('in_readme')))} | {_lower(bool(entry.get('in_roadmap')))} |"
            )
    lines.append("")

    # Git history check
    lines += ["## Git History Check", ""]
    git_checks = report.get("git_history_checks") or {}
    lines.append(f"- **Git history checked:** {_lower(bool(git_checks.get('git_history_checked')))}")
    lines.append(f"- **Source:** {_md(git_checks.get('source') or '(none)')}")
    for note in git_checks.get("warnings") or []:
        lines.append(f"- {_md(note)}")
    for note in git_checks.get("notes") or []:
        lines.append(f"- {_md(note)}")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Blockers
    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None — the completed roadmap arc agrees._")
    lines.append("")

    # Recommended next step
    lines += ["## Recommended Next Step", ""]
    lines.append(f"- `{_md(report.get('recommended_next_step') or '(none)')}`")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- ROAD.3 does not choose new work.",
        "- ROAD.3 does not execute phases.",
        "- ROAD.3 does not run validation or benchmarks.",
        "- ROAD.3 does not call models or embeddings.",
        "- ROAD.3 does not contact network services.",
        "- ROAD.3 does not run git commands.",
        "- ROAD.3 does not apply patches.",
        "- ROAD.3 does not launch workers.",
        "- ROAD.3 does not promote, merge, block, or retrieve lessons.",
        "- ROAD.3 is a checkpoint audit only.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _top_text(top: Any) -> str:
    if isinstance(top, dict):
        return f"{_md(top.get('phase_id', ''))} ({_md(top.get('recommended_next_step', ''))})"
    return "(none)"


# ── Input gathering (read-only) ─────────────────────────────────────────────────

def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Return ``(parsed_dict, error)``; error is non-empty when the file is unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read or parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def gather_checkpoint_inputs(repo_path: str | Path, registry_path: str | Path) -> dict[str, Any]:
    """Read the registry, inspected artifacts, and docs from disk, tolerating
    missing files (recorded as not present) and malformed JSON (recorded as a load
    error). Pure read-only: never writes, runs, or contacts anything.
    """
    repo = Path(repo_path)
    registry_data, registry_load_error = _load_json_object(Path(registry_path))

    artifacts: list[dict[str, Any]] = []
    for kind, rel, optional in INSPECTED_ARTIFACT_SPECS:
        target = repo / rel
        present = target.is_file()
        artifact: dict[str, Any] | None = None
        load_error = ""
        if present:
            artifact, load_error = _load_json_object(target)
        artifacts.append(
            {
                "path": rel,
                "kind": kind,
                "optional": optional,
                "present": present,
                "artifact": artifact,
                "load_error": load_error,
            }
        )

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
        "artifacts": artifacts,
        "docs": docs,
    }


# ── Report writing ──────────────────────────────────────────────────────────────

def write_checkpoint_audit(
    repo_path: str | Path,
    registry_path: str | Path,
    output_dir: str | Path,
    *,
    expected_complete_phases: Any = None,
    validation_summary: Any = None,
    git_history: Any = None,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Gather inputs, build the checkpoint audit, and write the JSON + Markdown
    artifacts. Returns ``{ok, json_path, md_path, report}``. Inputs are read only;
    nothing outside ``output_dir`` is written and nothing is run or contacted.
    """
    inputs = gather_checkpoint_inputs(repo_path, registry_path)
    report = build_checkpoint_audit(
        registry_data=inputs["registry_data"],
        registry_load_error=inputs["registry_load_error"],
        artifacts=inputs["artifacts"],
        docs=inputs["docs"],
        expected_complete_phases=expected_complete_phases,
        validation_summary=validation_summary,
        git_history=git_history,
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
    md_path.write_text(render_checkpoint_audit_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
