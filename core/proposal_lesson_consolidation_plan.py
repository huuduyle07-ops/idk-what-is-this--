"""Phase A.11 — Proposal/Lesson Entry Consolidation Plan.

Static registry of the consolidation plan for Proposal → Lesson candidate
creation. Plan-only phase: no code consolidation happens here. Report-only:
no lesson writes, no source mutations, no model calls, no Flask imports,
no DB imports, no subprocess calls, no benchmark runner, no patch/apply calls.

Artifacts are written to:
    .agent/audits/<timestamp>_proposal-lesson-consolidation-plan.json
    .agent/audits/<timestamp>_proposal-lesson-consolidation-plan.md
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN_VERSION = "A.11"
SOURCE_AUDIT = "A.10"
SOURCE_AUDIT_FILE = ".agent/audits/20260611_090717_lesson-entry-dedup-audit.json"

# ---------------------------------------------------------------------------
# Disposition constants
# ---------------------------------------------------------------------------
DISP_CANONICAL = "canonical"
DISP_DELEGATE = "delegate"
DISP_FREEZE = "freeze"
DISP_NEEDS_VERIFICATION = "needs_verification"

# ---------------------------------------------------------------------------
# Proposal entry map — the 7 proposal→candidate paths from A.10
# ---------------------------------------------------------------------------

_PROPOSAL_ENTRY_MAP: list[dict[str, Any]] = [
    {
        "entry_id": "P1",
        "file": "scripts/create_lesson_from_proposal.py",
        "function_or_route": "create_lesson_from_proposal",
        "caller_surface": "CLI",
        "source_label": "patch_proposal",
        "dedup_mechanism": "source_report",
        "force_disables_LESSON_AUTO_ACTIVE": True,
        "recommendation": DISP_CANONICAL,
        "migration_risk": (
            "low — most battle-tested path; A.6 guard lives here; P2 and P3 already "
            "delegate to it; no code change to P1 itself required in A.12"
        ),
        "notes": (
            "Chosen as canonical target. A.6 guard (LESSON_AUTO_ACTIVE=False around "
            "save_candidate_lesson) lives in this function. P2 (queue flag) and P3 "
            "(web /proposals/promote) already delegate to it. All other proposal paths "
            "must route through this function in A.12."
        ),
    },
    {
        "entry_id": "P2",
        "file": "scripts/run_patch_proposal_queue.py",
        "function_or_route": "_maybe_create_lesson_candidate (--create-lesson-candidates flag)",
        "caller_surface": "queue_flag",
        "source_label": "patch_proposal",
        "dedup_mechanism": "source_report",
        "force_disables_LESSON_AUTO_ACTIVE": True,
        "recommendation": DISP_DELEGATE,
        "migration_risk": (
            "very low — already delegates to P1; A.12 consolidation is a verification "
            "step; no code change expected unless delegation path is found incomplete"
        ),
        "notes": (
            "Already delegates to create_lesson_from_proposal (P1) with an explicit "
            "find_lesson_by_source_report pre-check before the call. "
            "In A.12: verify delegation chain is complete; no code change expected."
        ),
    },
    {
        "entry_id": "P3",
        "file": "web/app.py",
        "function_or_route": "/proposals/promote",
        "caller_surface": "web_route",
        "source_label": "patch_proposal",
        "dedup_mechanism": "source_report",
        "force_disables_LESSON_AUTO_ACTIVE": True,
        "recommendation": DISP_DELEGATE,
        "migration_risk": (
            "very low — already delegates to P1; keep as-is; no change needed unless "
            "the canonical target is moved to a different module in a later phase"
        ),
        "notes": (
            "Delegates to create_lesson_from_proposal (P1). A.6 guard is inherited. "
            "No changes needed in A.12 unless the canonical target location changes."
        ),
    },
    {
        "entry_id": "P4",
        "file": "scripts/seed_lessons_from_proposals.py",
        "function_or_route": "seed_lessons_from_proposals",
        "caller_surface": "CLI",
        "source_label": "proposal_artifact",
        "dedup_mechanism": "source_key",
        "force_disables_LESSON_AUTO_ACTIVE": True,
        "recommendation": DISP_DELEGATE,
        "migration_risk": (
            "medium — uses different source_label (proposal_artifact) and dedup mechanism "
            "(source_key) from P1; A.12 must bridge to canonical while adding compat dedup "
            "check to prevent cross-path duplicates"
        ),
        "notes": (
            "Source label mismatch (proposal_artifact vs patch_proposal) with P1/P2/P3 "
            "creates the cross-path duplicate risk identified in A.10. "
            "In A.12: route through canonical function; retain source_key dedup as "
            "a pre-check; also add a source_report compat check to detect P1/P2/P3 records."
        ),
    },
    {
        "entry_id": "P5",
        "file": "core/lesson_auto_candidates.py",
        "function_or_route": "maybe_create_lesson_candidate_from_proposal",
        "caller_surface": "core_function",
        "source_label": "proposal_artifact",
        "dedup_mechanism": "source_key",
        "force_disables_LESSON_AUTO_ACTIVE": True,
        "recommendation": DISP_DELEGATE,
        "migration_risk": (
            "medium — same source_label mismatch as P4; is the call target for P6 and P7; "
            "must keep enabled=False no-op guard; must not break P6/P7 callers"
        ),
        "notes": (
            "Delegates to P4 (seed_lessons_from_proposals). "
            "In A.12: this becomes the internal delegation point that calls the canonical "
            "function. The enabled=False no-op guard must be preserved exactly."
        ),
    },
    {
        "entry_id": "P6",
        "file": "scripts/create_lesson_candidate.py",
        "function_or_route": "main --proposal-dir",
        "caller_surface": "CLI",
        "source_label": "proposal_artifact",
        "dedup_mechanism": "source_key",
        "force_disables_LESSON_AUTO_ACTIVE": True,
        "recommendation": DISP_DELEGATE,
        "migration_risk": (
            "low — controlled operator-only trigger; shares file with D11 (--dream-item-dir); "
            "must preserve --dream-item-dir path before any forward-merge of this file"
        ),
        "notes": (
            "Delegates to P5 (maybe_create_lesson_candidate_from_proposal, enabled=True). "
            "In A.12: keep as-is; --proposal-dir continues routing through P5 → canonical. "
            "The --dream-item-dir path (D11) in the same file must not be disturbed."
        ),
    },
    {
        "entry_id": "P7",
        "file": "web/app.py",
        "function_or_route": "/lessons/create-candidate-from-proposal",
        "caller_surface": "web_route",
        "source_label": "proposal_artifact",
        "dedup_mechanism": "source_key",
        "force_disables_LESSON_AUTO_ACTIVE": True,
        "recommendation": DISP_NEEDS_VERIFICATION,
        "migration_risk": (
            "medium-high — external callers unknown; A.10 flagged needs_verification; "
            "route must remain live until A.14 confirms zero callers or provides migration"
        ),
        "notes": (
            "Delegates to P5. A.10 flagged needs_verification due to unknown external callers. "
            "In A.12: keep as-is; do not cut or deprecate. "
            "In A.14: audit all callers (scripts, MCP tools, harnesses, test fixtures) then "
            "decide freeze/deprecate/delete."
        ),
    },
]

# ---------------------------------------------------------------------------
# Canonical target design
# ---------------------------------------------------------------------------

_CANONICAL_TARGET: dict[str, Any] = {
    "function": "create_lesson_from_proposal",
    "file": "scripts/create_lesson_from_proposal.py",
    "module": "scripts.create_lesson_from_proposal",
    "selected_in_phase": "A.11 (this plan)",
    "rationale": (
        "create_lesson_from_proposal is the most battle-tested proposal→lesson path. "
        "It already holds the A.6 LESSON_AUTO_ACTIVE guard at lines ~272-287. "
        "P2 (queue flag) and P3 (web /proposals/promote) already delegate to it, so it "
        "is already behaving as a partial canonical. Making it fully canonical requires "
        "no new module and no code movement, minimising risk. "
        "The scripts/ location is sub-optimal for a canonical function (core/ would be "
        "better for cross-module imports) but changing that location is a separate refactor "
        "with its own risk. Conservative approach: establish delegation first, move to core/ "
        "in a later phase once all paths are confirmed stable."
    ),
    "alternative_considered": (
        "A new core/proposal_lesson_creator.py helper could host the canonical function, "
        "allowing core modules (P5 in lesson_auto_candidates.py) to import it without "
        "depending on the scripts/ package. Deferred: once all paths delegate to the current "
        "canonical, moving it to core/ is a mechanical import change with no logic change "
        "and can be done as a named future phase."
    ),
    "delegate_ids": ["P2", "P3", "P4", "P5", "P6", "P7"],
    "frozen_ids": [],
    "needs_verification_before_deletion_ids": ["P7"],
    "different_input_type_ids": [],
    "a6_guard_location": (
        "scripts/create_lesson_from_proposal.py::create_lesson_from_proposal "
        "(sets LESSON_AUTO_ACTIVE=False around save_candidate_lesson call)"
    ),
}

# ---------------------------------------------------------------------------
# Source label and dedup migration plan
# ---------------------------------------------------------------------------

_SOURCE_LABEL_DEDUP_STRATEGY: dict[str, Any] = {
    "current_split": {
        "group_a": {
            "ids": ["P1", "P2", "P3"],
            "source_label": "patch_proposal",
            "dedup_mechanism": "source_report",
            "dedup_key_format": "str(proposal_dir)",
        },
        "group_b": {
            "ids": ["P4", "P5", "P6", "P7"],
            "source_label": "proposal_artifact",
            "dedup_mechanism": "source_key",
            "dedup_key_format": "proposal_ref:hash",
        },
        "cross_path_duplicate_risk": True,
        "risk_explanation": (
            "A proposal processed via P1/P2/P3 (patch_proposal/source_report) is invisible "
            "to P4/P5/P6/P7 dedup checks (proposal_artifact/source_key) and vice versa. "
            "The same proposal directory can be ingested twice, once by each group."
        ),
    },
    "recommended_strategy": {
        "name": "canonical_proposal_artifact_with_compat_check",
        "canonical_source_label": "proposal_artifact",
        "canonical_dedup_mechanism": "source_key",
        "canonical_dedup_key_format": (
            "Stable source_key derived from the proposal directory path relative to "
            ".agent/proposals/. Format: 'proposal:<run>/<item>' or "
            "'proposal:<proposal_id>' when a stable id is available in item.json."
        ),
        "compatibility_alias": (
            "During duplicate detection in the canonical function, also call "
            "find_lesson_by_source_report('patch_proposal', str(proposal_dir)) in addition "
            "to _existing_source_keys(). If either check returns a match, skip creation. "
            "This prevents re-ingestion when the same proposal was previously written by "
            "the old patch_proposal/source_report path (P1/P2/P3)."
        ),
        "no_mass_migration": True,
        "no_mass_migration_reason": (
            "Existing patch_proposal/source_report records are valid and queryable. "
            "They must not be rewritten or deleted. The compat alias provides transparent "
            "cross-path duplicate detection without touching existing data."
        ),
        "implementation_phase": "A.12",
        "rationale": (
            "source_key is a stronger and more stable dedup identifier than source_report "
            "because it is derived from content identity rather than a directory path string "
            "that may vary across machines or run timestamps. Standardising on proposal_artifact "
            "aligns with the more recent, more complete P4–P7 paths. "
            "The compat alias closes the cross-path duplicate gap identified in A.10 without "
            "requiring a schema migration."
        ),
    },
    "alternative_strategy": {
        "name": "preserve_both_labels_compute_both_keys",
        "description": (
            "Preserve all existing source_label values. In the canonical function, always "
            "compute both a source_key and a source_report from the proposal_dir, then check "
            "both dedup paths before saving. Write the new record with both fields populated."
        ),
        "advantage": (
            "Zero schema change. All existing query paths (find_lesson_by_source_report, "
            "_existing_source_keys) continue to work unchanged."
        ),
        "disadvantage": (
            "Two competing dedup identifiers per record increases cognitive overhead for "
            "future audits and for lesson_store maintainers. The source_label split between "
            "patch_proposal and proposal_artifact persists, making it harder to query all "
            "proposal-derived lessons in a single pass."
        ),
        "recommended": False,
    },
}

# ---------------------------------------------------------------------------
# Backward compatibility rules
# ---------------------------------------------------------------------------

_BACKWARD_COMPAT_RULES: list[str] = [
    "Existing candidate/active/blocked lesson records remain readable without schema migration.",
    "Existing active lessons are not rewritten or reprocessed by consolidation work.",
    "Existing source_report records created by P1/P2/P3 are not deleted; they are "
    "recognized via the compat alias check during future dedup.",
    "Old CLI arguments (--proposal-dir, --create-lesson-candidates, --allow-failed, "
    "--global-candidate) remain accepted without change for at least one phase after A.12.",
    "Web route /proposals/promote (P3) continues to delegate to the canonical function "
    "and is not cut in A.12.",
    "Web route /lessons/create-candidate-from-proposal (P7) remains live until A.14 "
    "verifies zero external callers; it is not cut or deprecated in A.12.",
    "Lesson retrieval continues reading active/ only; no candidate reads are added.",
    "Promote flow remains human-only; no auto-promote path is added by consolidation.",
    "lesson_quality continues to decide blocked vs candidate; "
    "consolidation does not bypass or replace lesson_quality.",
]

# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

_SAFETY_INVARIANTS: list[str] = [
    "LESSON_AUTO_ACTIVE is forced off inside the canonical function (A.6 guard); "
    "all paths delegating to it inherit this guard automatically.",
    "lesson_quality still decides blocked vs candidate; the canonical function must not "
    "override or replace lesson_quality evaluation.",
    "lesson_store routing is not weakened; all writes go through save_candidate_lesson "
    "with proper source, source_report/source_key, and scope arguments.",
    "No proposal path may write directly to active/; all writes land in candidate/ "
    "or blocked/ as determined by lesson_store routing and lesson_quality.",
    "No model call is added to any proposal→lesson path by consolidation work.",
    "No patch apply step is added to any proposal→lesson path by consolidation work.",
    "No validation side effects are added; proposal artifact files are read-only "
    "during lesson candidate creation.",
    "The enabled=False no-op guard in maybe_create_lesson_candidate_from_proposal (P5) "
    "is preserved exactly; operator must pass enabled=True to trigger creation.",
    "The --dream-item-dir path in create_lesson_candidate.py (D11) is not disturbed "
    "by any changes made to the --proposal-dir (P6) path in the same file.",
]

# ---------------------------------------------------------------------------
# Future phases
# ---------------------------------------------------------------------------

_FUTURE_PHASES: list[dict[str, Any]] = [
    {
        "phase": "A.12",
        "title": "Canonical Proposal Candidate Creator",
        "scope": (
            "Make all proposal candidate paths (P1–P7) delegate to one function "
            "(scripts/create_lesson_from_proposal.py::create_lesson_from_proposal). "
            "Keep all old wrappers. Add compatibility duplicate detection so that "
            "records created by the old patch_proposal/source_report path are recognized "
            "by the new proposal_artifact/source_key path and vice versa."
        ),
        "size": "small",
        "prerequisite": "A.11 plan accepted (this document)",
        "tasks": [
            "Characterize current P4/P5 delegation chain: trace seed_lessons_from_proposals "
            "→ save_candidate_lesson and confirm it does not call create_lesson_from_proposal.",
            "Add compat duplicate pre-check in canonical function: call "
            "find_lesson_by_source_report('patch_proposal', str(proposal_dir)) before the "
            "source_key check in the canonical path.",
            "Rewire P4/P5 to delegate to the canonical function while retaining source_key "
            "dedup as a pre-check.",
            "Verify P6 (--proposal-dir) delegation chain through P5 → canonical.",
            "Verify P7 (/lessons/create-candidate-from-proposal) delegation chain through "
            "P5 → canonical.",
            "Keep all old wrappers (P2, P3, P4, P5, P6, P7); do not delete any entrypoint.",
            "Write tests: every proposal entrypoint delegates to canonical.",
            "Write tests: old patch_proposal/source_report duplicate detected.",
            "Write tests: new proposal_artifact/source_key duplicate detected.",
            "Run benchmarks --check and confirm 54 pass / 0 fail.",
        ],
    },
    {
        "phase": "A.13",
        "title": "Proposal Source Key Compatibility Tests",
        "scope": (
            "Pin the cross-path duplicate detection behavior: records created by the old "
            "patch_proposal/source_report path (P1/P2/P3) and records created by the new "
            "proposal_artifact/source_key path (P4/P5/P6/P7) both prevent re-ingestion "
            "from the opposite group."
        ),
        "size": "small",
        "prerequisite": "A.12 complete",
        "tasks": [
            "Write test: a proposal processed by P1 (patch_proposal/source_report) is "
            "not re-created when the same proposal_dir is submitted via P4/P5/P6/P7.",
            "Write test: a proposal processed by P4 (proposal_artifact/source_key) is "
            "not re-created when the same proposal_dir is submitted via P1/P2/P3.",
            "Write test: compat alias correctly recognizes existing source_report records.",
            "Write test: no existing lesson record is deleted or mutated during dedup checks.",
            "Run full pytest and benchmarks --check.",
        ],
    },
    {
        "phase": "A.14",
        "title": "Deprecated Proposal Route Verification",
        "scope": (
            "Verify /lessons/create-candidate-from-proposal (P7) external callers. "
            "Only after zero-caller confirmation decide freeze/deprecate/delete. "
            "Do not delete the route in A.14 itself."
        ),
        "size": "small",
        "prerequisite": "A.12 and A.13 complete",
        "tasks": [
            "Grep all internal scripts, worker harnesses, MCP tool configs, and test "
            "fixtures for the route URL string '/lessons/create-candidate-from-proposal'.",
            "Search git history for commits that reference the route URL.",
            "If no callers found: add a deprecation warning response header to the route; "
            "add a code comment marking it deprecated.",
            "If callers found: document each caller, its owner, and a migration timeline "
            "before deciding any removal.",
            "Do not delete the route in A.14; deletion is a follow-on phase after "
            "a migration window.",
        ],
    },
]

# ---------------------------------------------------------------------------
# Do-not-touch section
# ---------------------------------------------------------------------------

_DO_NOT_TOUCH: list[str] = [
    "Do not merge Dream endpoints D8 (/dream/create-lesson-candidate) and D9 "
    "(/lessons/create-candidate-from-dream). They serve intentionally different "
    "Dream item lifecycle stages (non-ready vs ready_to_apply).",
    "Do not remove or modify scripts/seed_lessons_from_benchmark.py (B12). "
    "It is the only benchmark→lesson path; freeze it (no changes, no deletion) "
    "until a redesign is accepted as a named phase.",
    "Do not touch core/anti_lessons.py or the anti-lesson creation paths (A13).",
    "Do not touch core/lesson_merge.py or the lesson merge creation paths (M14).",
    "Do not change active lesson retrieval logic in core/lesson_retrieval.py.",
    "Do not remove or weaken tool_registry promote_lesson (T15).",
    "Do not change Project Evolution gates (B.4, B.8, B.10).",
    "Do not change Dream candidate creation paths (D8, D9, D10, D11).",
    "Do not auto-promote any lesson; Promote flow remains human-only.",
]

# ---------------------------------------------------------------------------
# Acceptance criteria for A.12
# ---------------------------------------------------------------------------

_ACCEPTANCE_CRITERIA_A12: list[str] = [
    "Every proposal entrypoint (P1–P7) either IS the canonical function or provably "
    "delegates to it through a traceable call chain.",
    "LESSON_AUTO_ACTIVE=true at call time still results in candidate-only output "
    "(A.6 guard inside canonical function forces it off).",
    "A record created via the old patch_proposal/source_report path (P1/P2/P3) is "
    "detected as a duplicate when the same proposal_dir is submitted via P4/P5/P6/P7.",
    "A record created via the new proposal_artifact/source_key path (P4/P5/P6/P7) is "
    "detected as a duplicate when the same proposal_dir is submitted via P1/P2/P3.",
    "The queue flag (--create-lesson-candidates in run_patch_proposal_queue.py) still "
    "produces a candidate lesson.",
    "Web /proposals/promote still produces a candidate lesson.",
    "scripts/create_lesson_candidate.py --proposal-dir still produces a candidate lesson.",
    "Dream paths (D8, D9, D10, D11) are unchanged and their tests still pass.",
    "Benchmark seeder (B12, scripts/seed_lessons_from_benchmark.py) is unchanged.",
    "benchmarks/run_benchmarks.py --check reports 54 pass / 0 fail.",
]

# ---------------------------------------------------------------------------
# A.7 / A.10 doc update references
# ---------------------------------------------------------------------------

_DOC_UPDATE_REFS: dict[str, Any] = {
    "a7_triage_doc": "docs/audits/2026-06-11-architecture-audit-triage.md",
    "a7_section_to_update": (
        "Under 'Accepted Later' → 'Proposal → Lesson Entry Consolidation': "
        "add a reference to the A.11 consolidation plan artifact."
    ),
    "a10_audit_artifact": ".agent/audits/20260611_090717_lesson-entry-dedup-audit.json",
    "a10_update_note": (
        "The A.10 audit artifact is read-only; no content change required. "
        "The A.11 plan artifact references A.10 as source_audit. "
        "Link from A.7 triage doc is sufficient."
    ),
    "update_required": True,
}

# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

GUARDRAILS: dict[str, Any] = {
    "report_only": True,
    "no_source_mutation": True,
    "no_lesson_creation": True,
    "no_promotion": True,
    "no_model_call": True,
    "no_subprocess": True,
    "no_web_behavior_change": True,
    "no_patch_apply": True,
    "no_runtime_behavior_change": True,
    "description": (
        "This module and CLI are strictly plan-only and report-only. "
        "They do not write lessons, mutate source artifacts, promote lessons, call models, "
        "spawn subprocesses, import Flask, import DB, import benchmark runners, or change "
        "any runtime behavior. They write only the plan artifact files under .agent/audits/."
    ),
}

# ---------------------------------------------------------------------------
# Build plan
# ---------------------------------------------------------------------------


def build_plan(repo_path: str | Path | None = None) -> dict[str, Any]:
    """Build the full consolidation plan dict.

    Pass repo_path to enable file-existence checks on proposal entry files.
    When None, file_exists fields are omitted and statuses reflect the static
    registry only.
    """
    rp: Path | None = Path(repo_path).resolve() if repo_path else None

    entries: list[dict[str, Any]] = []
    for entry in _PROPOSAL_ENTRY_MAP:
        e = dict(entry)
        if rp is not None:
            file_rel = e.get("file")
            if file_rel:
                e["file_exists"] = (rp / file_rel).is_file()
        entries.append(e)

    return {
        "plan_version": PLAN_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(rp) if rp else None,
        "header": {
            "plan_name": "A.11 Proposal/Lesson Entry Consolidation Plan",
            "source_audit": SOURCE_AUDIT,
            "source_audit_file": SOURCE_AUDIT_FILE,
            "purpose": (
                "Choose the canonical Proposal → Lesson candidate creation path and define "
                "the consolidation strategy before any code changes. This is a plan-only "
                "artifact produced by A.11; no runtime behavior is changed by generating "
                "this report."
            ),
            "status": "plan_only",
            "no_runtime_behavior_changed": True,
        },
        "proposal_entry_map": entries,
        "canonical_target": _CANONICAL_TARGET,
        "source_label_dedup_strategy": _SOURCE_LABEL_DEDUP_STRATEGY,
        "backward_compatibility_rules": _BACKWARD_COMPAT_RULES,
        "safety_invariants": _SAFETY_INVARIANTS,
        "future_phases": _FUTURE_PHASES,
        "do_not_touch": _DO_NOT_TOUCH,
        "acceptance_criteria_a12": _ACCEPTANCE_CRITERIA_A12,
        "doc_update_refs": _DOC_UPDATE_REFS,
        "guardrails": GUARDRAILS,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_markdown(plan: dict[str, Any]) -> str:
    lines: list[str] = []

    header = plan["header"]
    lines += [
        f"# {header['plan_name']}",
        "",
        f"Generated: {plan['generated_at']}",
        f"Plan version: `{plan['plan_version']}`",
        f"Source audit: `{header['source_audit']}` — `{header['source_audit_file']}`",
        f"Status: **{header['status']}**",
        "",
        f"> {header['purpose']}",
        "",
        "---",
        "",
        "## 1. Header / Summary",
        "",
        f"- **Plan**: {header['plan_name']}",
        f"- **Source audit**: {header['source_audit']} — Proposal/Lesson Entry Dedup Audit",
        f"- **Purpose**: {header['purpose']}",
        f"- **Status**: **{header['status']}**",
        f"- **No runtime behavior changed**: `{header['no_runtime_behavior_changed']}`",
        "",
        "---",
        "",
        "## 2. Current Proposal Entry Map",
        "",
        "| ID | File / Route | Surface | Source Label | Dedup | Force-disable AUTO_ACTIVE | Recommendation | Risk (summary) |",
        "|----|----|----|----|----|----|----|--------|",
    ]

    for e in plan["proposal_entry_map"]:
        exists_note = ""
        if "file_exists" in e and not e["file_exists"]:
            exists_note = " _(missing)_"
        risk_short = e["migration_risk"]
        if len(risk_short) > 55:
            risk_short = risk_short[:52] + "…"
        lines.append(
            f"| {e['entry_id']} "
            f"| `{e['file']}`{exists_note} `{e['function_or_route']}` "
            f"| {e['caller_surface']} "
            f"| `{e['source_label']}` "
            f"| {e['dedup_mechanism']} "
            f"| {e['force_disables_LESSON_AUTO_ACTIVE']} "
            f"| **{e['recommendation']}** "
            f"| {risk_short} |"
        )

    lines += [""]
    for e in plan["proposal_entry_map"]:
        lines += [
            f"### {e['entry_id']} — `{e['function_or_route']}`",
            "",
            f"- **File**: `{e['file']}`",
            f"- **Surface**: {e['caller_surface']}",
            f"- **Source label**: `{e['source_label']}`",
            f"- **Dedup**: {e['dedup_mechanism']}",
            f"- **Force-disable LESSON_AUTO_ACTIVE**: {e['force_disables_LESSON_AUTO_ACTIVE']}",
            f"- **Recommendation**: **{e['recommendation']}**",
            f"- **Migration risk**: {e['migration_risk']}",
            f"- **Notes**: {e['notes']}",
            "",
        ]

    ct = plan["canonical_target"]
    lines += [
        "---",
        "",
        "## 3. Canonical Target Design",
        "",
        f"**Canonical function**: `{ct['function']}` in `{ct['file']}`",
        f"**Module**: `{ct['module']}`",
        f"**Selected in**: {ct['selected_in_phase']}",
        "",
        "### Rationale",
        "",
        ct["rationale"],
        "",
        "### Alternative Considered",
        "",
        ct["alternative_considered"],
        "",
        f"**Delegate paths (must route through canonical in A.12)**: {ct['delegate_ids']}",
        f"**Frozen paths**: {ct['frozen_ids'] if ct['frozen_ids'] else 'none'}",
        f"**Needs verification before deletion**: {ct['needs_verification_before_deletion_ids']}",
        f"**Separate input type (no consolidation)**: {ct['different_input_type_ids'] if ct['different_input_type_ids'] else 'none'}",
        f"**A.6 guard location**: `{ct['a6_guard_location']}`",
        "",
    ]

    strat = plan["source_label_dedup_strategy"]
    rec = strat["recommended_strategy"]
    alt = strat["alternative_strategy"]
    ga = strat["current_split"]["group_a"]
    gb = strat["current_split"]["group_b"]
    lines += [
        "---",
        "",
        "## 4. Source Label and Dedup Migration Plan",
        "",
        "### Current Split",
        "",
        f"- **Group A** ({', '.join(ga['ids'])}): source_label=`{ga['source_label']}`, dedup=`{ga['dedup_mechanism']}`",
        f"- **Group B** ({', '.join(gb['ids'])}): source_label=`{gb['source_label']}`, dedup=`{gb['dedup_mechanism']}`",
        f"- **Cross-path duplicate risk**: **{strat['current_split']['cross_path_duplicate_risk']}**",
        f"- {strat['current_split']['risk_explanation']}",
        "",
        f"### Recommended Strategy: `{rec['name']}`",
        "",
        f"- **Canonical source_label**: `{rec['canonical_source_label']}`",
        f"- **Canonical dedup**: `{rec['canonical_dedup_mechanism']}`",
        f"- **Canonical dedup key format**: {rec['canonical_dedup_key_format']}",
        f"- **Compatibility alias**: {rec['compatibility_alias']}",
        f"- **No mass migration required**: {rec['no_mass_migration']} — {rec['no_mass_migration_reason']}",
        f"- **Implementation phase**: {rec['implementation_phase']}",
        f"- **Rationale**: {rec['rationale']}",
        "",
        f"### Alternative Strategy: `{alt['name']}`",
        "",
        f"- **Description**: {alt['description']}",
        f"- **Advantage**: {alt['advantage']}",
        f"- **Disadvantage**: {alt['disadvantage']}",
        f"- **Recommended**: {alt['recommended']}",
        "",
    ]

    lines += [
        "---",
        "",
        "## 5. Backward Compatibility Rules",
        "",
    ]
    for rule in plan["backward_compatibility_rules"]:
        lines.append(f"- {rule}")
    lines += ["", "---", ""]

    lines += [
        "## 6. Safety Invariants",
        "",
    ]
    for inv in plan["safety_invariants"]:
        lines.append(f"- {inv}")
    lines += ["", "---", ""]

    lines += [
        "## 7. Step-by-Step Future Implementation Plan",
        "",
    ]
    for phase in plan["future_phases"]:
        lines += [
            f"### {phase['phase']} — {phase['title']}",
            "",
            f"**Scope**: {phase['scope']}",
            "",
            f"**Size**: {phase['size']}  |  **Prerequisite**: {phase['prerequisite']}",
            "",
            "**Tasks**:",
            "",
        ]
        for task in phase["tasks"]:
            lines.append(f"- [ ] {task}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 8. Do-Not-Touch Section",
        "",
    ]
    for item in plan["do_not_touch"]:
        lines.append(f"- {item}")
    lines += ["", "---", ""]

    lines += [
        "## 9. Acceptance Criteria for A.12",
        "",
    ]
    for crit in plan["acceptance_criteria_a12"]:
        lines.append(f"- [ ] {crit}")
    lines += ["", "---", ""]

    du = plan["doc_update_refs"]
    lines += [
        "## 10. Doc Update References",
        "",
        f"- **A.7 triage doc**: `{du['a7_triage_doc']}`",
        f"  - {du['a7_section_to_update']}",
        f"- **A.10 audit artifact**: `{du['a10_audit_artifact']}`",
        f"  - {du['a10_update_note']}",
        f"- **Update required**: {du['update_required']}",
        "",
        "---",
        "",
        "## Guardrails",
        "",
        plan["guardrails"]["description"],
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Artifact writing
# ---------------------------------------------------------------------------


def write_artifacts(
    plan: dict[str, Any],
    *,
    audits_root: str | Path,
) -> dict[str, str]:
    """Write JSON and Markdown plan artifacts. Returns {'json': path, 'markdown': path}."""
    root = Path(audits_root)
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_proposal-lesson-consolidation-plan"

    json_path = root / f"{stem}.json"
    json_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path = root / f"{stem}.md"
    md_path.write_text(render_markdown(plan), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}
