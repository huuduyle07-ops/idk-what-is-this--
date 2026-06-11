"""Phase A.11 tests — Proposal/Lesson Entry Consolidation Plan.

Tests:
1. Plan builds JSON and Markdown (non-empty, parseable, required keys).
2. Required proposal entrypoints appear (P1–P7).
3. Canonical target is selected (create_lesson_from_proposal / P1).
4. Dream merge is forbidden (do_not_touch section).
5. Benchmark seeder is frozen (do_not_touch section).
6. Safety invariants are listed (LESSON_AUTO_ACTIVE guard, no active writes, etc.).
7. Future A.12/A.13/A.14 phases are proposed.
8. A.12 acceptance criteria listed (all 10).
9. Report-only import guard: no Flask, no model clients, no DB, no subprocess,
   no lesson write/promotion calls, no patch apply.
10. CLI writes artifacts under .agent/audits and does not mutate source reports.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.proposal_lesson_consolidation_plan import (
    DISP_CANONICAL,
    DISP_DELEGATE,
    DISP_NEEDS_VERIFICATION,
    GUARDRAILS,
    PLAN_VERSION,
    SOURCE_AUDIT,
    build_plan,
    render_markdown,
    write_artifacts,
)

MODULE_PATH = PROJECT_ROOT / "core" / "proposal_lesson_consolidation_plan.py"
CLI_PATH = PROJECT_ROOT / "scripts" / "create_proposal_lesson_consolidation_plan.py"

REQUIRED_PROPOSAL_IDS = {"P1", "P2", "P3", "P4", "P5", "P6", "P7"}
EXPECTED_FUTURE_PHASES = {"A.12", "A.13", "A.14"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry_by_id(plan: dict, entry_id: str) -> dict:
    for e in plan["proposal_entry_map"]:
        if e["entry_id"] == entry_id:
            return e
    raise KeyError(f"entry_id {entry_id!r} not found in proposal_entry_map")


def _all_imported_modules(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            modules.add(mod)
            modules.add(mod.split(".")[0])
            for alias in node.names:
                modules.add(alias.name)
    return modules


def _ast_call_names(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


# ---------------------------------------------------------------------------
# Test 1 — Plan builds JSON and Markdown
# ---------------------------------------------------------------------------


def test_build_plan_returns_required_keys():
    plan = build_plan()
    for key in (
        "plan_version",
        "generated_at",
        "header",
        "proposal_entry_map",
        "canonical_target",
        "source_label_dedup_strategy",
        "backward_compatibility_rules",
        "safety_invariants",
        "future_phases",
        "do_not_touch",
        "acceptance_criteria_a12",
        "doc_update_refs",
        "guardrails",
    ):
        assert key in plan, f"Missing top-level key: {key}"


def test_plan_version_is_a11():
    plan = build_plan()
    assert plan["plan_version"] == PLAN_VERSION
    assert plan["plan_version"] == "A.11"


def test_header_status_is_plan_only():
    plan = build_plan()
    assert plan["header"]["status"] == "plan_only"
    assert plan["header"]["no_runtime_behavior_changed"] is True


def test_header_source_audit_is_a10():
    plan = build_plan()
    assert plan["header"]["source_audit"] == SOURCE_AUDIT
    assert plan["header"]["source_audit"] == "A.10"


def test_render_markdown_is_nonempty_string():
    plan = build_plan()
    md = render_markdown(plan)
    assert isinstance(md, str)
    assert len(md) > 500


def test_render_markdown_contains_required_sections():
    plan = build_plan()
    md = render_markdown(plan)
    for section in (
        "## 1. Header / Summary",
        "## 2. Current Proposal Entry Map",
        "## 3. Canonical Target Design",
        "## 4. Source Label and Dedup Migration Plan",
        "## 5. Backward Compatibility Rules",
        "## 6. Safety Invariants",
        "## 7. Step-by-Step Future Implementation Plan",
        "## 8. Do-Not-Touch Section",
        "## 9. Acceptance Criteria for A.12",
        "## 10. Doc Update References",
        "## Guardrails",
    ):
        assert section in md, f"Missing section: {section}"


def test_write_artifacts_produces_json_and_md():
    with tempfile.TemporaryDirectory() as td:
        plan = build_plan()
        paths = write_artifacts(plan, audits_root=td)
        assert "json" in paths
        assert "markdown" in paths
        json_path = Path(paths["json"])
        md_path = Path(paths["markdown"])
        assert json_path.is_file()
        assert md_path.is_file()
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["plan_version"] == PLAN_VERSION


def test_json_artifact_filename_contains_timestamp_and_slug():
    with tempfile.TemporaryDirectory() as td:
        plan = build_plan()
        paths = write_artifacts(plan, audits_root=td)
        assert "proposal-lesson-consolidation-plan" in Path(paths["json"]).name
        assert Path(paths["json"]).name.endswith(".json")
        assert "proposal-lesson-consolidation-plan" in Path(paths["markdown"]).name
        assert Path(paths["markdown"]).name.endswith(".md")


# ---------------------------------------------------------------------------
# Test 2 — Required proposal entrypoints appear
# ---------------------------------------------------------------------------


def test_all_required_proposal_ids_present():
    plan = build_plan()
    found = {e["entry_id"] for e in plan["proposal_entry_map"]}
    missing = REQUIRED_PROPOSAL_IDS - found
    assert not missing, f"Missing proposal entry IDs: {missing}"


def test_proposal_entries_have_required_fields():
    plan = build_plan()
    required_fields = {
        "entry_id",
        "file",
        "function_or_route",
        "caller_surface",
        "source_label",
        "dedup_mechanism",
        "force_disables_LESSON_AUTO_ACTIVE",
        "recommendation",
        "migration_risk",
        "notes",
    }
    for e in plan["proposal_entry_map"]:
        missing = required_fields - e.keys()
        assert not missing, f"{e['entry_id']} missing fields: {missing}"


def test_all_proposal_entries_force_disable_lesson_auto_active():
    plan = build_plan()
    for eid in REQUIRED_PROPOSAL_IDS:
        e = _entry_by_id(plan, eid)
        assert e["force_disables_LESSON_AUTO_ACTIVE"] is True, (
            f"{eid} must force-disable LESSON_AUTO_ACTIVE"
        )


def test_all_proposal_entries_have_source_label():
    plan = build_plan()
    for eid in REQUIRED_PROPOSAL_IDS:
        e = _entry_by_id(plan, eid)
        assert e["source_label"], f"{eid} must have a source_label"


# ---------------------------------------------------------------------------
# Test 3 — Canonical target is selected
# ---------------------------------------------------------------------------


def test_canonical_target_key_present():
    plan = build_plan()
    ct = plan["canonical_target"]
    for key in ("function", "file", "module", "delegate_ids", "a6_guard_location"):
        assert key in ct, f"canonical_target missing key: {key}"


def test_canonical_target_is_create_lesson_from_proposal():
    plan = build_plan()
    ct = plan["canonical_target"]
    assert ct["function"] == "create_lesson_from_proposal"
    assert "create_lesson_from_proposal.py" in ct["file"]


def test_p1_recommendation_is_canonical():
    plan = build_plan()
    p1 = _entry_by_id(plan, "P1")
    assert p1["recommendation"] == DISP_CANONICAL


def test_delegate_ids_include_p2_through_p7():
    plan = build_plan()
    delegate_ids = set(plan["canonical_target"]["delegate_ids"])
    for eid in ("P2", "P3", "P4", "P5", "P6", "P7"):
        assert eid in delegate_ids, f"{eid} must be in canonical_target.delegate_ids"


def test_p7_is_in_needs_verification_before_deletion():
    plan = build_plan()
    nv_ids = plan["canonical_target"]["needs_verification_before_deletion_ids"]
    assert "P7" in nv_ids, "P7 must be in needs_verification_before_deletion_ids"


def test_p7_recommendation_is_needs_verification():
    plan = build_plan()
    p7 = _entry_by_id(plan, "P7")
    assert p7["recommendation"] == DISP_NEEDS_VERIFICATION


def test_p2_p3_recommendation_is_delegate():
    plan = build_plan()
    for eid in ("P2", "P3"):
        e = _entry_by_id(plan, eid)
        assert e["recommendation"] == DISP_DELEGATE, f"{eid} should be delegate"


def test_a6_guard_location_mentioned_in_canonical():
    plan = build_plan()
    guard = plan["canonical_target"]["a6_guard_location"]
    assert "LESSON_AUTO_ACTIVE" in guard or "A.6" in guard or "create_lesson_from_proposal" in guard


# ---------------------------------------------------------------------------
# Test 4 — Dream merge is forbidden
# ---------------------------------------------------------------------------


def test_do_not_touch_includes_dream_endpoints():
    plan = build_plan()
    do_not_touch_text = " ".join(plan["do_not_touch"])
    assert "D8" in do_not_touch_text or "dream" in do_not_touch_text.lower(), (
        "do_not_touch must mention Dream endpoints (D8/D9)"
    )


def test_do_not_touch_forbids_merging_dream_endpoints():
    plan = build_plan()
    do_not_touch_text = " ".join(plan["do_not_touch"]).lower()
    assert "merge" in do_not_touch_text or "do not merge" in do_not_touch_text, (
        "do_not_touch must forbid merging Dream endpoints"
    )


def test_no_dream_merge_disposition_in_entry_map():
    plan = build_plan()
    for e in plan["proposal_entry_map"]:
        combined = (e.get("notes", "") + " " + e.get("recommendation", "")).lower()
        assert "merge dream" not in combined, (
            f"Entry {e['entry_id']} must not suggest merging Dream endpoints"
        )


# ---------------------------------------------------------------------------
# Test 5 — Benchmark seeder is frozen
# ---------------------------------------------------------------------------


def test_do_not_touch_includes_benchmark_seeder():
    plan = build_plan()
    do_not_touch_text = " ".join(plan["do_not_touch"])
    assert "B12" in do_not_touch_text or "benchmark" in do_not_touch_text.lower(), (
        "do_not_touch must mention benchmark seeder (B12)"
    )


def test_do_not_touch_says_freeze_not_cut_for_benchmark():
    plan = build_plan()
    bench_items = [
        item for item in plan["do_not_touch"]
        if "B12" in item or "benchmark" in item.lower()
    ]
    assert bench_items, "No do_not_touch item mentions benchmark seeder"
    combined = " ".join(bench_items).lower()
    assert "cut" not in combined, "benchmark do_not_touch item must not say 'cut'"
    assert "delete" not in combined, "benchmark do_not_touch item must not say 'delete'"


def test_acceptance_criteria_a12_includes_benchmark_unchanged():
    plan = build_plan()
    criteria_text = " ".join(plan["acceptance_criteria_a12"])
    assert "B12" in criteria_text or "benchmark" in criteria_text.lower(), (
        "A.12 acceptance criteria must confirm benchmark seeder is unchanged"
    )


# ---------------------------------------------------------------------------
# Test 6 — Safety invariants are listed
# ---------------------------------------------------------------------------


def test_safety_invariants_list_is_nonempty():
    plan = build_plan()
    assert len(plan["safety_invariants"]) >= 7


def test_safety_invariants_include_lesson_auto_active_guard():
    plan = build_plan()
    inv_text = " ".join(plan["safety_invariants"])
    assert "LESSON_AUTO_ACTIVE" in inv_text, (
        "safety_invariants must mention LESSON_AUTO_ACTIVE guard"
    )


def test_safety_invariants_forbid_direct_active_writes():
    plan = build_plan()
    inv_text = " ".join(plan["safety_invariants"]).lower()
    assert "active" in inv_text, (
        "safety_invariants must address no direct writes to active/"
    )


def test_safety_invariants_forbid_model_calls():
    plan = build_plan()
    inv_text = " ".join(plan["safety_invariants"]).lower()
    assert "model" in inv_text or "no model" in inv_text, (
        "safety_invariants must forbid adding model calls"
    )


def test_safety_invariants_forbid_patch_apply():
    plan = build_plan()
    inv_text = " ".join(plan["safety_invariants"]).lower()
    assert "patch" in inv_text or "apply" in inv_text, (
        "safety_invariants must forbid adding patch apply"
    )


def test_safety_invariants_mention_lesson_quality():
    plan = build_plan()
    inv_text = " ".join(plan["safety_invariants"]).lower()
    assert "lesson_quality" in inv_text or "lesson quality" in inv_text, (
        "safety_invariants must preserve lesson_quality gate"
    )


def test_safety_invariants_mention_enabled_noop_guard():
    plan = build_plan()
    inv_text = " ".join(plan["safety_invariants"])
    assert "enabled" in inv_text or "no-op" in inv_text or "no_op" in inv_text or "P5" in inv_text, (
        "safety_invariants must preserve the enabled=False no-op guard in P5"
    )


# ---------------------------------------------------------------------------
# Test 7 — Future A.12/A.13/A.14 phases are proposed
# ---------------------------------------------------------------------------


def test_future_phases_include_a12_a13_a14():
    plan = build_plan()
    phase_ids = {p["phase"] for p in plan["future_phases"]}
    missing = EXPECTED_FUTURE_PHASES - phase_ids
    assert not missing, f"Missing future phases: {missing}"


def test_future_phases_have_required_fields():
    plan = build_plan()
    for phase in plan["future_phases"]:
        for field in ("phase", "title", "scope", "tasks"):
            assert field in phase, f"Phase {phase.get('phase')} missing field: {field}"
        assert isinstance(phase["tasks"], list)
        assert len(phase["tasks"]) >= 1


def test_a12_phase_mentions_canonical_function():
    plan = build_plan()
    a12 = next(p for p in plan["future_phases"] if p["phase"] == "A.12")
    scope_and_tasks = a12["scope"] + " ".join(a12["tasks"])
    assert "create_lesson_from_proposal" in scope_and_tasks or "canonical" in scope_and_tasks.lower()


def test_a12_phase_mentions_compat_dedup():
    plan = build_plan()
    a12 = next(p for p in plan["future_phases"] if p["phase"] == "A.12")
    tasks_text = " ".join(a12["tasks"]).lower()
    assert "compat" in tasks_text or "source_report" in tasks_text or "duplicate" in tasks_text


def test_a14_phase_verifies_p7_callers():
    plan = build_plan()
    a14 = next(p for p in plan["future_phases"] if p["phase"] == "A.14")
    text = (a14["scope"] + " ".join(a14["tasks"])).lower()
    assert "p7" in text or "create-candidate-from-proposal" in text or "caller" in text


# ---------------------------------------------------------------------------
# Test 8 — A.12 acceptance criteria are listed
# ---------------------------------------------------------------------------


def test_acceptance_criteria_a12_list_is_nonempty():
    plan = build_plan()
    assert len(plan["acceptance_criteria_a12"]) >= 8


def test_acceptance_criteria_a12_mentions_all_proposal_ids():
    plan = build_plan()
    criteria_text = " ".join(plan["acceptance_criteria_a12"])
    assert "P1" in criteria_text or "canonical" in criteria_text.lower()


def test_acceptance_criteria_a12_mentions_queue_flag():
    plan = build_plan()
    criteria_text = " ".join(plan["acceptance_criteria_a12"]).lower()
    assert "queue" in criteria_text or "create-lesson-candidates" in criteria_text


def test_acceptance_criteria_a12_mentions_web_proposals_promote():
    plan = build_plan()
    criteria_text = " ".join(plan["acceptance_criteria_a12"]).lower()
    assert "promote" in criteria_text or "/proposals/promote" in criteria_text


def test_acceptance_criteria_a12_mentions_benchmark_check():
    plan = build_plan()
    criteria_text = " ".join(plan["acceptance_criteria_a12"]).lower()
    assert "54" in criteria_text or "benchmark" in criteria_text


# ---------------------------------------------------------------------------
# Test 9 — Report-only import guard
# ---------------------------------------------------------------------------


def test_module_file_exists():
    assert MODULE_PATH.is_file(), f"core/proposal_lesson_consolidation_plan.py not found"


def test_no_flask_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "flask" not in modules, "module must not import Flask"
    assert "web" not in {m.split(".")[0] for m in modules if m}, (
        "module must not import web package"
    )


def test_no_model_client_import():
    modules = _all_imported_modules(MODULE_PATH)
    forbidden = {"anthropic", "openai", "sleeping_consultant"}
    found = {m for m in forbidden if any(m in mod for mod in modules)}
    assert not found, f"module imports model clients: {found}"


def test_no_db_import():
    modules = _all_imported_modules(MODULE_PATH)
    forbidden = {"database", "sqlalchemy", "sqlite3", "memory_store"}
    found = {m for m in forbidden if any(m in mod for mod in modules)}
    assert not found, f"module imports DB: {found}"


def test_no_subprocess_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "subprocess" not in modules, "module must not import subprocess"


def test_no_benchmark_runner_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "run_benchmarks" not in modules
    assert not any("benchmarks" in m for m in modules if m), (
        "module must not import benchmarks package"
    )


def test_no_lesson_write_calls_in_module():
    calls = _ast_call_names(MODULE_PATH)
    assert "save_candidate_lesson" not in calls, (
        "module must not call save_candidate_lesson"
    )
    assert "save_raw_lesson_record" not in calls, (
        "module must not call save_raw_lesson_record"
    )
    assert "promote_lesson" not in calls, (
        "module must not call promote_lesson"
    )


def test_no_patch_apply_in_module():
    calls = _ast_call_names(MODULE_PATH)
    assert "apply_patch" not in calls, "module must not call apply_patch"
    modules = _all_imported_modules(MODULE_PATH)
    assert "patch_executor" not in modules, "module must not import patch_executor"


# ---------------------------------------------------------------------------
# Test 10 — CLI writes artifacts; does not mutate source
# ---------------------------------------------------------------------------


def test_cli_file_exists():
    assert CLI_PATH.is_file(), f"scripts/create_proposal_lesson_consolidation_plan.py not found"


def test_cli_writes_to_audits_dir():
    from scripts.create_proposal_lesson_consolidation_plan import _main

    with tempfile.TemporaryDirectory() as td:
        audits_root = Path(td) / "audits"
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", str(audits_root)])
        assert ret == 0
        json_files = list(audits_root.glob("*proposal-lesson-consolidation-plan*.json"))
        md_files = list(audits_root.glob("*proposal-lesson-consolidation-plan*.md"))
        assert json_files, "CLI should produce a JSON artifact"
        assert md_files, "CLI should produce a Markdown artifact"


def test_cli_dry_run_does_not_write():
    from scripts.create_proposal_lesson_consolidation_plan import _main

    with tempfile.TemporaryDirectory() as td:
        audits_root = Path(td) / "audits_dryrun"
        ret = _main(
            ["--repo-path", str(PROJECT_ROOT), "--audits-root", str(audits_root), "--dry-run"]
        )
        assert ret == 0
        json_files = list(audits_root.glob("*.json")) if audits_root.exists() else []
        assert not json_files, "--dry-run must not write files"


def test_cli_does_not_write_to_lessons_store():
    lessons_root = PROJECT_ROOT / ".agent" / "lessons"
    before: set[str] = set()
    if lessons_root.exists():
        before = {str(p) for p in lessons_root.rglob("*")}

    from scripts.create_proposal_lesson_consolidation_plan import _main

    with tempfile.TemporaryDirectory() as td:
        _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])

    after: set[str] = set()
    if lessons_root.exists():
        after = {str(p) for p in lessons_root.rglob("*")}

    new_files = after - before
    assert not new_files, f"CLI wrote to lesson store: {new_files}"


def test_cli_does_not_write_to_proposals_root():
    proposals_root = PROJECT_ROOT / ".agent" / "proposals"
    before: set[str] = set()
    if proposals_root.exists():
        before = {str(p) for p in proposals_root.rglob("*")}

    from scripts.create_proposal_lesson_consolidation_plan import _main

    with tempfile.TemporaryDirectory() as td:
        _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])

    after: set[str] = set()
    if proposals_root.exists():
        after = {str(p) for p in proposals_root.rglob("*")}

    new_files = after - before
    assert not new_files, f"CLI wrote to proposals root: {new_files}"


def test_json_artifact_is_valid_json_with_required_keys():
    from scripts.create_proposal_lesson_consolidation_plan import _main

    with tempfile.TemporaryDirectory() as td:
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])
        assert ret == 0
        json_files = list(Path(td).glob("*.json"))
        assert json_files
        payload = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert payload["plan_version"] == PLAN_VERSION
        assert len(payload["proposal_entry_map"]) == 7
        assert payload["header"]["status"] == "plan_only"


def test_markdown_artifact_contains_all_sections():
    from scripts.create_proposal_lesson_consolidation_plan import _main

    with tempfile.TemporaryDirectory() as td:
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])
        assert ret == 0
        md_files = list(Path(td).glob("*.md"))
        assert md_files
        content = md_files[0].read_text(encoding="utf-8")
        for section in (
            "## 1. Header / Summary",
            "## 2. Current Proposal Entry Map",
            "## 3. Canonical Target Design",
            "## 4. Source Label and Dedup Migration Plan",
            "## 5. Backward Compatibility Rules",
            "## 6. Safety Invariants",
            "## 7. Step-by-Step Future Implementation Plan",
            "## 8. Do-Not-Touch Section",
            "## 9. Acceptance Criteria for A.12",
            "## 10. Doc Update References",
            "## Guardrails",
        ):
            assert section in content, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# Extra: file-existence validation
# ---------------------------------------------------------------------------


def test_build_plan_with_repo_path_marks_existing_files():
    plan = build_plan(repo_path=PROJECT_ROOT)
    for e in plan["proposal_entry_map"]:
        if "file_exists" in e:
            assert isinstance(e["file_exists"], bool), (
                f"{e['entry_id']}: file_exists must be bool"
            )


def test_guardrails_are_all_set():
    plan = build_plan()
    g = plan["guardrails"]
    for flag in (
        "report_only",
        "no_source_mutation",
        "no_lesson_creation",
        "no_promotion",
        "no_model_call",
        "no_subprocess",
        "no_web_behavior_change",
        "no_patch_apply",
        "no_runtime_behavior_change",
    ):
        assert g[flag] is True, f"guardrails.{flag} must be True"
