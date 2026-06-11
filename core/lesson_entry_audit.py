"""Phase A.10 — Proposal/Lesson Entry Dedup Audit.

Static registry of every lesson candidate creation entry point. Report-only:
no lesson writes, no source mutations, no model calls, no Flask imports, no DB
imports, no subprocess calls, no benchmark runner, no patch/apply calls.

The registry is a plain Python list of dicts. File/route/function existence
checks are done with Path.is_file() only — read-only, fail-soft (a missing
file changes current_status to needs_verification rather than crashing).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_VERSION = "A.10"

# ---------------------------------------------------------------------------
# Category + surface constants
# ---------------------------------------------------------------------------
CAT_PROPOSAL = "proposal_to_candidate"
CAT_DREAM = "dream_to_candidate"
CAT_BENCHMARK = "benchmark_to_candidate"
CAT_ANTI = "anti_lesson"
CAT_MERGE = "merge"
CAT_OTHER = "other"

SURF_CLI = "CLI"
SURF_WEB = "web_route"
SURF_QUEUE = "queue_flag"
SURF_CORE = "core_function"
SURF_TOOL = "tool_registry"

DEDUP_SOURCE_REPORT = "source_report"
DEDUP_SOURCE_KEY = "source_key"
DEDUP_DUPLICATE_DETECTOR = "duplicate_detector"
DEDUP_NONE = "none"

STATUS_SAFE = "safe"
STATUS_DUPLICATE_RISK = "duplicate_risk"
STATUS_FROZEN = "frozen"
STATUS_NEEDS_VERIFICATION = "needs_verification"

WRITE_SAVE_CANDIDATE = "lesson_store.save_candidate_lesson"
WRITE_SAVE_RAW = "lesson_store.save_raw_lesson_record"

BUCKET_CANDIDATE = "candidate"
BUCKET_BLOCKED = "blocked"
BUCKET_ACTIVE_POSSIBLE = "active_possible"

# ---------------------------------------------------------------------------
# Static entrypoint registry
# Validate file existence with _check_file_exists(); do NOT read file content
# here (that is done optionally in the validation pass).
# ---------------------------------------------------------------------------

_ENTRYPOINTS: list[dict[str, Any]] = [
    # ------------------------------------------------------------------
    # Proposal → candidate
    # ------------------------------------------------------------------
    {
        "entry_id": "P1",
        "category": CAT_PROPOSAL,
        "public_surface": SURF_CLI,
        "file": "scripts/create_lesson_from_proposal.py",
        "function_or_route": "create_lesson_from_proposal",
        "source_label": "patch_proposal",
        "dedup_mechanism": DEDUP_SOURCE_REPORT,
        "dedup_notes": "find_lesson_by_source_report(patch_proposal, str(proposal_dir)) inside lesson_store; no pre-check in CLI entry",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "notes": "A.6: forces LESSON_AUTO_ACTIVE=False around save_candidate_lesson",
    },
    {
        "entry_id": "P2",
        "category": CAT_PROPOSAL,
        "public_surface": SURF_QUEUE,
        "file": "scripts/run_patch_proposal_queue.py",
        "function_or_route": "_maybe_create_lesson_candidate (--create-lesson-candidates flag)",
        "source_label": "patch_proposal",
        "dedup_mechanism": DEDUP_SOURCE_REPORT,
        "dedup_notes": "explicit find_lesson_by_source_report(patch_proposal, str(item_dir)) before calling create_lesson_from_proposal",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "notes": "delegates to create_lesson_from_proposal which holds the A.6 guard",
    },
    {
        "entry_id": "P3",
        "category": CAT_PROPOSAL,
        "public_surface": SURF_WEB,
        "file": "web/app.py",
        "function_or_route": "/proposals/promote",
        "source_label": "patch_proposal",
        "dedup_mechanism": DEDUP_SOURCE_REPORT,
        "dedup_notes": "delegates to create_lesson_from_proposal; same source_report dedup as P1",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "notes": "A.6 guard inherited from create_lesson_from_proposal",
    },
    {
        "entry_id": "P4",
        "category": CAT_PROPOSAL,
        "public_surface": SURF_CLI,
        "file": "scripts/seed_lessons_from_proposals.py",
        "function_or_route": "seed_lessons_from_proposals",
        "source_label": "proposal_artifact",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "_existing_source_keys() pre-check before save; source_key=proposal_ref:hash",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_DUPLICATE_RISK,
        "a6_guard": True,
        "notes": "source_label differs from P1/P2/P3 (proposal_artifact vs patch_proposal); cross-path dedup gap",
    },
    {
        "entry_id": "P5",
        "category": CAT_PROPOSAL,
        "public_surface": SURF_CORE,
        "file": "core/lesson_auto_candidates.py",
        "function_or_route": "maybe_create_lesson_candidate_from_proposal",
        "source_label": "proposal_artifact",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "delegates to seed_lessons_from_proposals; same source_key dedup as P4",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "notes": "exact no-op unless enabled=True; used by P6 and P7",
    },
    {
        "entry_id": "P6",
        "category": CAT_PROPOSAL,
        "public_surface": SURF_CLI,
        "file": "scripts/create_lesson_candidate.py",
        "function_or_route": "main --proposal-dir",
        "source_label": "proposal_artifact",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "delegates to P5 (maybe_create_lesson_candidate_from_proposal, enabled=True)",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "notes": "controlled operator trigger; shares source_label/dedup with P4/P5",
    },
    {
        "entry_id": "P7",
        "category": CAT_PROPOSAL,
        "public_surface": SURF_WEB,
        "file": "web/app.py",
        "function_or_route": "/lessons/create-candidate-from-proposal",
        "source_label": "proposal_artifact",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "delegates to P5 (maybe_create_lesson_candidate_from_proposal, enabled=True)",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_NEEDS_VERIFICATION,
        "a6_guard": True,
        "notes": "external callers unknown; verify before cutting; cross-path risk with P1/P2/P3",
    },
    # ------------------------------------------------------------------
    # Dream → candidate
    # ------------------------------------------------------------------
    {
        "entry_id": "D8",
        "category": CAT_DREAM,
        "public_surface": SURF_WEB,
        "file": "web/app.py",
        "function_or_route": "/dream/create-lesson-candidate",
        "source_label": "dream",
        "dedup_mechanism": DEDUP_SOURCE_REPORT,
        "dedup_notes": "source_report=f'{date}/{run}'; no source_key; accepts any Dream item status, not only ready_to_apply",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_DUPLICATE_RISK,
        "a6_guard": True,
        "notes": "simple/non-ready path; source_label 'dream' differs from D9/D10/D11 'dream_artifact'; source_report dedup is weaker; may need source_key dedup added",
        "do_not_merge_with_ready_path": True,
    },
    {
        "entry_id": "D9",
        "category": CAT_DREAM,
        "public_surface": SURF_WEB,
        "file": "web/app.py",
        "function_or_route": "/lessons/create-candidate-from-dream",
        "source_label": "dream_artifact",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "delegates to D10; _existing_source_keys() pre-check; source_key=dream:ref:patch_hash:…",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "notes": "ready_to_apply path only; requires patch_revalidation_pass{N}.json artifact",
        "do_not_merge_with_ready_path": False,
    },
    {
        "entry_id": "D10",
        "category": CAT_DREAM,
        "public_surface": SURF_CORE,
        "file": "core/lesson_auto_candidates.py",
        "function_or_route": "maybe_create_lesson_candidate_from_dream_item",
        "source_label": "dream_artifact",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "_existing_source_keys() pre-check; source_key derived from patch_plan hash or changed_files hash",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "do_not_merge_with_ready_path": False,
        "notes": "exact no-op unless enabled=True; used by D9 and D11",
    },
    {
        "entry_id": "D11",
        "category": CAT_DREAM,
        "public_surface": SURF_CLI,
        "file": "scripts/create_lesson_candidate.py",
        "function_or_route": "main --dream-item-dir",
        "source_label": "dream_artifact",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "delegates to D10 (maybe_create_lesson_candidate_from_dream_item, enabled=True)",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": True,
        "do_not_merge_with_ready_path": False,
        "notes": "shares file with P6 (create_lesson_candidate.py); preserve --dream-item-dir before any forward-merge",
    },
    # ------------------------------------------------------------------
    # Benchmark → candidate
    # ------------------------------------------------------------------
    {
        "entry_id": "B12",
        "category": CAT_BENCHMARK,
        "public_surface": SURF_CLI,
        "file": "scripts/seed_lessons_from_benchmark.py",
        "function_or_route": "seed_lessons_from_report",
        "source_label": "benchmark_report",
        "dedup_mechanism": DEDUP_SOURCE_KEY,
        "dedup_notes": "_existing_source_keys() pre-check; source_key=report_name:case_name:hash",
        "force_disables_LESSON_AUTO_ACTIVE": "true",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_FROZEN,
        "a6_guard": True,
        "notes": "only benchmark→lesson path; freeze until a redesign of the benchmark lesson area is accepted",
    },
    # ------------------------------------------------------------------
    # Anti-lesson creation
    # ------------------------------------------------------------------
    {
        "entry_id": "A13",
        "category": CAT_ANTI,
        "public_surface": SURF_CORE,
        "file": "core/anti_lessons.py",
        "function_or_route": "create_anti_lesson (web /lessons/anti/create)",
        "source_label": "n/a (kind=anti_lesson)",
        "dedup_mechanism": DEDUP_DUPLICATE_DETECTOR,
        "dedup_notes": "find_anti_lesson_duplicates is advisory; does not block creation; human supplies all fields",
        "force_disables_LESSON_AUTO_ACTIVE": "not_applicable",
        "writes_via": WRITE_SAVE_CANDIDATE,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": False,
        "notes": "manual-only path; no auto-creation; advisory dedup via lesson_duplicates",
    },
    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------
    {
        "entry_id": "M14",
        "category": CAT_MERGE,
        "public_surface": SURF_CORE,
        "file": "core/lesson_merge.py",
        "function_or_route": "create_merge (web /lessons/merge/create)",
        "source_label": "n/a (merged)",
        "dedup_mechanism": DEDUP_DUPLICATE_DETECTOR,
        "dedup_notes": "duplicate detection via lesson_duplicates; explicit operator action",
        "force_disables_LESSON_AUTO_ACTIVE": "not_applicable",
        "writes_via": WRITE_SAVE_RAW,
        "expected_output_bucket": BUCKET_CANDIDATE,
        "current_status": STATUS_SAFE,
        "a6_guard": False,
        "notes": "merge creates new candidate; source lessons are archived; uses save_raw_lesson_record",
    },
    # ------------------------------------------------------------------
    # Promotion (not candidate creation)
    # ------------------------------------------------------------------
    {
        "entry_id": "T15",
        "category": CAT_OTHER,
        "public_surface": SURF_TOOL,
        "file": "core/tool_registry.py",
        "function_or_route": "promote_lesson",
        "source_label": "n/a (promotion, not creation)",
        "dedup_mechanism": DEDUP_NONE,
        "dedup_notes": "promotion of existing candidate; not candidate creation",
        "force_disables_LESSON_AUTO_ACTIVE": "not_applicable",
        "writes_via": "lesson_store.promote_lesson",
        "expected_output_bucket": "active_possible",
        "current_status": STATUS_SAFE,
        "a6_guard": False,
        "notes": "marks existing candidate as active; not a candidate-creation path; included for completeness",
    },
]

# ---------------------------------------------------------------------------
# File/route existence validation (fail-soft)
# ---------------------------------------------------------------------------
_FILE_KEYED_ENTRIES = {"P1", "P2", "P4", "P6", "D11", "B12", "A13", "M14", "T15"}


def _validate_entry_file(entry: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    """Return a shallow copy of entry with current_status updated if file missing."""
    result = dict(entry)
    file_rel = entry.get("file")
    if not file_rel:
        return result
    full = repo_path / file_rel
    if not full.is_file():
        if result["current_status"] not in {STATUS_DUPLICATE_RISK, STATUS_FROZEN}:
            result["current_status"] = STATUS_NEEDS_VERIFICATION
        result["file_exists"] = False
    else:
        result["file_exists"] = True
    return result


# ---------------------------------------------------------------------------
# Duplicate risk analysis
# ---------------------------------------------------------------------------

def _proposal_duplicate_risk_entries(entries: list[dict[str, Any]]) -> list[str]:
    source_report_ids = [
        e["entry_id"]
        for e in entries
        if e["category"] == CAT_PROPOSAL and e["dedup_mechanism"] == DEDUP_SOURCE_REPORT
    ]
    source_key_ids = [
        e["entry_id"]
        for e in entries
        if e["category"] == CAT_PROPOSAL and e["dedup_mechanism"] == DEDUP_SOURCE_KEY
    ]
    if source_report_ids and source_key_ids:
        return source_report_ids + source_key_ids
    return []


def _dream_split_entries(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    non_ready = [
        e["entry_id"]
        for e in entries
        if e["category"] == CAT_DREAM and e.get("do_not_merge_with_ready_path") is True
    ]
    ready = [
        e["entry_id"]
        for e in entries
        if e["category"] == CAT_DREAM and e.get("do_not_merge_with_ready_path") is False
    ]
    return {"non_ready_path_ids": non_ready, "ready_to_apply_path_ids": ready}


def _compute_duplicate_risk_count(entries: list[dict[str, Any]]) -> int:
    return sum(1 for e in entries if e["current_status"] == STATUS_DUPLICATE_RISK)


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------

def _safety_checks(entries: list[dict[str, Any]]) -> dict[str, Any]:
    force_disable_ids = [
        e["entry_id"] for e in entries if e.get("force_disables_LESSON_AUTO_ACTIVE") == "true"
    ]
    lesson_store_routing_ids = [
        e["entry_id"]
        for e in entries
        if e.get("writes_via") in {WRITE_SAVE_CANDIDATE, WRITE_SAVE_RAW}
    ]
    can_write_blocked_ids = [
        e["entry_id"]
        for e in entries
        if e.get("expected_output_bucket") in {BUCKET_CANDIDATE, BUCKET_BLOCKED}
        and e.get("writes_via") in {WRITE_SAVE_CANDIDATE, WRITE_SAVE_RAW}
        and e["category"] not in {CAT_OTHER}
    ]
    can_write_active_ids = [
        e["entry_id"]
        for e in entries
        if e.get("expected_output_bucket") == BUCKET_ACTIVE_POSSIBLE
    ]
    candidate_only_ids = [
        e["entry_id"]
        for e in entries
        if e.get("a6_guard") is True and e["category"] == CAT_PROPOSAL
    ]
    return {
        "force_disable_LESSON_AUTO_ACTIVE": force_disable_ids,
        "rely_on_lesson_store_routing": lesson_store_routing_ids,
        "can_write_blocked": can_write_blocked_ids,
        "can_write_active_if_auto_active_enabled": can_write_active_ids,
        "proposal_candidate_only_after_A6": candidate_only_ids,
        "a6_note": (
            "After A.6, all proposal-created lessons (P1–P7) force LESSON_AUTO_ACTIVE=False "
            "so they land in candidate/ regardless of global flag state."
        ),
    }


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: list[dict[str, str]] = [
    {
        "disposition": "accepted_later",
        "topic": "Unify proposal→candidate creation function",
        "detail": (
            "P1/P2/P3 use source='patch_proposal' + source_report dedup; "
            "P4/P5/P6/P7 use source='proposal_artifact' + source_key dedup. "
            "Merge these into a single internal function so all proposal paths share "
            "one source label and one dedup strategy."
        ),
    },
    {
        "disposition": "accepted_later",
        "topic": "Unify source label and source_key strategy across all proposal paths",
        "detail": (
            "Once the creation function is unified, standardise on source_key dedup "
            "for all proposal paths. The source_report mechanism in P1/P2/P3 is "
            "weaker because it does not cross-check the proposal_artifact records."
        ),
    },
    {
        "disposition": "accepted_later",
        "topic": "Add source_key dedup to the simple Dream endpoint (D8)",
        "detail": (
            "D8 (/dream/create-lesson-candidate) currently deduplicates only by "
            "source_report (date/run). Add a source_key based on item identity so "
            "repeated submissions of the same Dream item are detected. "
            "Do not merge D8 into D9 — they serve different item states."
        ),
    },
    {
        "disposition": "accepted_later",
        "topic": "Merge create_lesson_candidate.py forward only after preserving --dream-item-dir",
        "detail": (
            "scripts/create_lesson_candidate.py bundles both --proposal-dir and "
            "--dream-item-dir. Any forward-merge or consolidation must preserve "
            "the --dream-item-dir path. Verify no external callers depend on the "
            "current argument interface before changing."
        ),
    },
    {
        "disposition": "do_not_merge",
        "topic": "Dual Dream endpoints (D8 and D9)",
        "detail": (
            "D8 (/dream/create-lesson-candidate) accepts any Dream item status "
            "(non-ready path). D9 (/lessons/create-candidate-from-dream) requires "
            "a ready_to_apply revalidation artifact. These serve intentionally "
            "different stages of the Dream lifecycle. Do not merge them."
        ),
    },
    {
        "disposition": "freeze",
        "topic": "seed_lessons_from_benchmark.py (B12)",
        "detail": (
            "B12 is the only benchmark→lesson path. It is safe and well-gated. "
            "Freeze it (no changes, no deletion) until a redesign of the benchmark "
            "lesson area is accepted as a named phase."
        ),
    },
    {
        "disposition": "needs_verification",
        "topic": "/lessons/create-candidate-from-proposal external callers (P7)",
        "detail": (
            "P7 is a web route. Before cutting or consolidating, verify that no "
            "external callers (scripts, integrations, MCP tools, worker harnesses) "
            "depend on this specific endpoint URL. If callers exist, coordinate a "
            "migration path before removing."
        ),
    },
]

# ---------------------------------------------------------------------------
# Guardrail declaration
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
    "description": (
        "This module and CLI are strictly report-only. They do not write lessons, "
        "mutate source artifacts, promote lessons, call models, spawn subprocesses, "
        "import Flask, import DB, import benchmark runners, or change any runtime "
        "behavior. They write only the audit artifact files under .agent/audits/."
    ),
}

# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------

def build_report(repo_path: str | Path | None = None) -> dict[str, Any]:
    """Build the full audit report dict.

    Pass repo_path to enable file-existence validation. When None, all
    file_exists fields are omitted and current_status reflects the static
    registry only.
    """
    rp: Path | None = Path(repo_path).resolve() if repo_path else None

    entries: list[dict[str, Any]] = []
    for entry in _ENTRYPOINTS:
        if rp is not None:
            entries.append(_validate_entry_file(entry, rp))
        else:
            entries.append(dict(entry))

    by_category: dict[str, int] = {}
    for e in entries:
        by_category[e["category"]] = by_category.get(e["category"], 0) + 1

    dup_risk_count = _compute_duplicate_risk_count(entries)
    proposal_dup_entries = _proposal_duplicate_risk_entries(entries)
    dream_split = _dream_split_entries(entries)

    summary: dict[str, Any] = {
        "total_entrypoints": len(entries),
        "proposal_to_candidate": by_category.get(CAT_PROPOSAL, 0),
        "dream_to_candidate": by_category.get(CAT_DREAM, 0),
        "benchmark_to_candidate": by_category.get(CAT_BENCHMARK, 0),
        "anti_lesson": by_category.get(CAT_ANTI, 0),
        "merge": by_category.get(CAT_MERGE, 0),
        "other": by_category.get(CAT_OTHER, 0),
        "duplicate_risk_count": dup_risk_count,
        "candidate_only_safety_status": (
            "After A.6, all proposal paths (P1–P7) force LESSON_AUTO_ACTIVE=False. "
            "Proposal-created lessons land in candidate/ regardless of global flag."
        ),
    }

    duplicate_risk_analysis: dict[str, Any] = {
        "proposal_path_split": {
            "source_report_dedup_ids": [
                e["entry_id"]
                for e in entries
                if e["category"] == CAT_PROPOSAL
                and e["dedup_mechanism"] == DEDUP_SOURCE_REPORT
            ],
            "source_key_dedup_ids": [
                e["entry_id"]
                for e in entries
                if e["category"] == CAT_PROPOSAL
                and e["dedup_mechanism"] == DEDUP_SOURCE_KEY
            ],
            "cross_path_duplicates_possible": len(proposal_dup_entries) > 0,
            "explanation": (
                "P1/P2/P3 write source='patch_proposal' and dedup by source_report. "
                "P4/P5/P6/P7 write source='proposal_artifact' and dedup by source_key. "
                "These two dedup mechanisms do not cross-check each other, so the same "
                "proposal can be ingested by both groups creating duplicate records."
            ),
        },
        "dream_path_split": {
            "non_ready_path_ids": dream_split["non_ready_path_ids"],
            "ready_to_apply_path_ids": dream_split["ready_to_apply_path_ids"],
            "intentionally_separate": True,
            "do_not_merge": True,
            "explanation": (
                "D8 (/dream/create-lesson-candidate) is the simple path for any Dream "
                "item regardless of status. D9/D10/D11 are the ready_to_apply path that "
                "require a patch_revalidation_pass{N}.json artifact. These serve "
                "different lifecycle stages. Merging them would break the non-ready path."
            ),
            "d8_dedup_gap": (
                "D8 currently deduplicates only by source_report (date/run granularity). "
                "Multiple items in the same run can be ingested without cross-item dedup."
            ),
        },
        "benchmark_seeder": {
            "entry_id": "B12",
            "disposition": "freeze",
            "explanation": (
                "B12 is the only benchmark→lesson path. It is self-contained with "
                "source_key dedup. Freeze it rather than cutting."
            ),
        },
    }

    return {
        "audit_version": AUDIT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(rp) if rp else None,
        "summary": summary,
        "entrypoints": entries,
        "duplicate_risk_analysis": duplicate_risk_analysis,
        "safety_checks": _safety_checks(entries),
        "recommendations": _RECOMMENDATIONS,
        "guardrails": GUARDRAILS,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _status_badge(status: str) -> str:
    badges = {
        STATUS_SAFE: "safe",
        STATUS_DUPLICATE_RISK: "**duplicate_risk**",
        STATUS_FROZEN: "frozen",
        STATUS_NEEDS_VERIFICATION: "_needs_verification_",
    }
    return badges.get(status, status)


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines: list[str] = [
        f"# Lesson Entry Dedup Audit — {AUDIT_VERSION}",
        "",
        f"Generated: {report['generated_at']}",
        f"Repo path: `{report.get('repo_path') or 'not set'}`",
        "",
        "## Summary",
        "",
        f"- Total entrypoints: {summary['total_entrypoints']}",
        f"- Proposal → candidate: {summary['proposal_to_candidate']}",
        f"- Dream → candidate: {summary['dream_to_candidate']}",
        f"- Benchmark → candidate: {summary['benchmark_to_candidate']}",
        f"- Anti-lesson: {summary['anti_lesson']}",
        f"- Merge: {summary['merge']}",
        f"- Other: {summary['other']}",
        f"- **Duplicate-risk count: {summary['duplicate_risk_count']}**",
        f"- Candidate-only safety: {summary['candidate_only_safety_status']}",
        "",
        "## Entrypoint Table",
        "",
        "| ID | Category | Surface | File/Route | Source Label | Dedup | Force-disable AUTO_ACTIVE | Writes Via | Bucket | Status |",
        "|----|---------|---------|-----------|-----------|----|-----|----|----|----|",
    ]
    for e in report["entrypoints"]:
        exists_note = ""
        if "file_exists" in e and not e["file_exists"]:
            exists_note = " _(file missing)_"
        lines.append(
            f"| {e['entry_id']} "
            f"| {e['category']} "
            f"| {e['public_surface']} "
            f"| `{e['file']}`{exists_note} `{e['function_or_route']}` "
            f"| `{e['source_label']}` "
            f"| {e['dedup_mechanism']} "
            f"| {e['force_disables_LESSON_AUTO_ACTIVE']} "
            f"| {e['writes_via']} "
            f"| {e['expected_output_bucket']} "
            f"| {_status_badge(e['current_status'])} |"
        )

    lines += [
        "",
        "## Duplicate Risk Analysis",
        "",
    ]
    dra = report["duplicate_risk_analysis"]
    pp = dra["proposal_path_split"]
    lines += [
        "### Proposal Path Split",
        "",
        f"- source_report dedup (patch_proposal): {pp['source_report_dedup_ids']}",
        f"- source_key dedup (proposal_artifact): {pp['source_key_dedup_ids']}",
        f"- Cross-path duplicates possible: **{pp['cross_path_duplicates_possible']}**",
        f"- {pp['explanation']}",
        "",
        "### Dream Path Split",
        "",
    ]
    dp = dra["dream_path_split"]
    lines += [
        f"- Non-ready path (D8): {dp['non_ready_path_ids']}",
        f"- Ready-to-apply path: {dp['ready_to_apply_path_ids']}",
        f"- Intentionally separate: {dp['intentionally_separate']}",
        f"- Do NOT merge: {dp['do_not_merge']}",
        f"- {dp['explanation']}",
        f"- D8 dedup gap: {dp['d8_dedup_gap']}",
        "",
        "### Benchmark Seeder",
        "",
        f"- {dra['benchmark_seeder']['entry_id']}: {dra['benchmark_seeder']['disposition']}",
        f"- {dra['benchmark_seeder']['explanation']}",
    ]

    sc = report["safety_checks"]
    lines += [
        "",
        "## Safety Checks",
        "",
        f"- Force-disable LESSON_AUTO_ACTIVE: {sc['force_disable_LESSON_AUTO_ACTIVE']}",
        f"- Rely on lesson_store routing: {sc['rely_on_lesson_store_routing']}",
        f"- Can write blocked: {sc['can_write_blocked']}",
        f"- Can write active (if auto_active on): {sc['can_write_active_if_auto_active_enabled']}",
        f"- Proposal candidate-only (after A.6): {sc['proposal_candidate_only_after_A6']}",
        f"- A.6 note: {sc['a6_note']}",
        "",
        "## Recommendations",
        "",
    ]
    for rec in report["recommendations"]:
        lines += [
            f"### [{rec['disposition'].upper()}] {rec['topic']}",
            "",
            rec["detail"],
            "",
        ]

    lines += [
        "## Guardrails",
        "",
        report["guardrails"]["description"],
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Artifact writing
# ---------------------------------------------------------------------------

def write_artifacts(
    report: dict[str, Any],
    *,
    audits_root: str | Path,
) -> dict[str, str]:
    """Write JSON and Markdown audit artifacts. Returns {'json': path, 'markdown': path}."""
    root = Path(audits_root)
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_lesson-entry-dedup-audit"

    json_path = root / f"{stem}.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path = root / f"{stem}.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}
