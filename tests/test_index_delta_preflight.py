"""INDEX.1E.0 deterministic preflight and guardrail coverage."""

from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.index_completion import (
    AppliedManifestEvidence,
    classify_index_completion,
    may_advance_applied_manifest,
    may_claim_repository_intelligence_current,
)
from core.index_delta_preflight import (
    DEFAULT_BASELINE_JSON,
    DEFAULT_BASELINE_MARKDOWN,
    DEFAULT_PREFLIGHT_JSON,
    DEFAULT_PREFLIGHT_MARKDOWN,
    FAILURE_AUTHORITATIVE_INDEX,
    FAILURE_CATEGORIES,
    FAILURE_INDEX_ADJACENT,
    FAILURE_MIRROR_OR_HARDENING,
    FAILURE_STALE_ROADMAP,
    FAILURE_UNCLASSIFIED,
    GUARDRAIL_KEYS,
    PHASE_STATUS_BLOCKED,
    PHASE_STATUS_COMPLETE,
    PHASE_STATUS_COMPLETE_WITH_WARNINGS,
    PREREQUISITE_NAMES,
    READINESS_BLOCKED_CONTRACT,
    READINESS_BLOCKED_INDEX,
    READINESS_BLOCKED_PREREQUISITE,
    READINESS_BLOCKED_UNCLASSIFIED,
    READINESS_READY,
    READINESS_READY_WITH_WARNINGS,
    RETRIEVAL_SCOPE_PATHS,
    build_index_delta_preflight,
    build_known_failure_baseline,
    classify_readiness,
    default_contract_mismatches,
    default_deferred_integration_requirements,
    default_prerequisite_audit,
    normalize_known_failure_baseline,
    render_index_delta_preflight_markdown,
    render_known_failure_markdown,
    validate_index_delta_preflight,
    write_index_delta_preflight,
)
from core.index_execution import (
    EmbeddingAction,
    EmbeddingCompatibility,
    IndexExecutionPlan,
    build_index_execution_plan,
)
from core.index_manifest import (
    RepositoryDelta,
    RepositoryManifest,
    get_repository_manifest_path,
    inspect_repository_delta,
    load_repository_manifest,
)
from core.repository_identity import (
    build_code_index_scope,
    build_repository_identity,
    is_code_index_scope,
)
from core.repository_identity_state import (
    derive_canonical_identity_permissions,
    initialize_repository_identity_state,
    load_repository_identity_state,
)
from core.repository_inventory import (
    RepositoryInventory,
    create_repository_inventory,
    validate_repository_inventory,
)
from core.retriever import _index_scope_for
from database.code_index import (
    _require_current_files,
    _require_index_scope,
)
import scripts.create_index_delta_preflight as script


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _python_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _call_leaf_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name):
            names.add(function.id)
        elif isinstance(function, ast.Attribute):
            names.add(function.attr)
    return names


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _decorator_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _failure(
    node_id: str,
    *,
    category: str = FAILURE_STALE_ROADMAP,
    intersects: bool = False,
) -> dict:
    return {
        "node_id": node_id,
        "category": category,
        "index_path_intersection": intersects,
        "reason": "The assertion describes an unrelated stale artifact.",
        "evidence": ["tests/example.py:10", "core/indexer.py is not imported"],
    }


def _baseline(
    *failures: dict,
    passed: int = 20,
    skipped: int = 1,
    diagnostic_output: dict | None = None,
) -> dict:
    records = list(failures) or [
        _failure("tests/test_alpha.py::test_old_count"),
        _failure(
            "tests/test_mirror.py::test_missing_trace",
            category=FAILURE_MIRROR_OR_HARDENING,
        ),
    ]
    return build_known_failure_baseline(
        command="python -m pytest -q",
        collection_timestamp="2026-07-28T16:00:00+07:00",
        worktree_state={
            "commit": "a1d3299b69df65137d13f8dbea40044c7fde48fc",
            "dirty": True,
        },
        summary={
            "passed": passed,
            "skipped": skipped,
            "failed": len(records),
        },
        known_failures=records,
        reported_summary={
            "passed": 6261,
            "skipped": 5,
            "failed": 48,
        },
        diagnostic_output=diagnostic_output,
    )


def test_failure_baseline_is_complete_sorted_and_self_consistent():
    baseline = _baseline(
        _failure("tests/test_z.py::test_z"),
        _failure("tests/test_a.py::test_a"),
    )

    assert [item["node_id"] for item in baseline["known_failures"]] == [
        "tests/test_a.py::test_a",
        "tests/test_z.py::test_z",
    ]
    assert all(item["node_id"] for item in baseline["known_failures"])
    assert all(
        item["category"] in FAILURE_CATEGORIES
        for item in baseline["known_failures"]
    )
    assert all(
        type(item["index_path_intersection"]) is bool
        for item in baseline["known_failures"]
    )
    assert baseline["summary"]["failed"] == len(
        baseline["known_failures"]
    )
    assert baseline["index_intersection_summary"] == {
        "authoritative_index_failures": 0,
        "index_adjacent_failures": 0,
        "unrelated_failures": 2,
        "unclassified_failures": 0,
    }
    assert len(baseline["failure_set_digest"]) == 64
    assert normalize_known_failure_baseline(baseline) == baseline


def test_failure_evidence_order_and_duplicates_do_not_change_baseline():
    first = _failure("tests/test_order.py::test_order")
    first["evidence"] = ["z.py:20", "a.py:10", "z.py:20"]
    second = deepcopy(first)
    second["evidence"].reverse()

    baseline_a = _baseline(first)
    baseline_b = _baseline(second)

    assert baseline_a == baseline_b
    assert baseline_a["known_failures"][0]["evidence"] == [
        "a.py:10",
        "z.py:20",
    ]


def test_diagnostic_output_round_trips_and_normalizes_digest_and_path():
    diagnostic = {
        "path": r".tmp\pytest-output.txt",
        "sha256": "A" * 64,
        "exit_code": 1,
        "duration_seconds": 4.25,
        "collected": 23,
        "warnings": 12,
        "python_version": "3.14.6",
        "pytest_version": "9.1.1",
    }

    baseline = _baseline(diagnostic_output=diagnostic)

    assert baseline["diagnostic_output"] == {
        **diagnostic,
        "path": ".tmp/pytest-output.txt",
        "sha256": "a" * 64,
    }
    assert normalize_known_failure_baseline(baseline) == baseline


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"sha256": "bad"}, "64-character"),
        ({"collected": 22}, "does not match"),
        ({"duration_seconds": float("nan")}, "finite"),
        ({"duration_seconds": float("inf")}, "finite"),
        ({"duration_seconds": float("-inf")}, "finite"),
    ],
)
def test_diagnostic_output_rejects_invalid_or_nonfinite_values(
    mutation,
    match,
):
    diagnostic = {
        "path": ".tmp/pytest-output.txt",
        "sha256": "a" * 64,
        "exit_code": 1,
        "duration_seconds": 4.25,
        "collected": 23,
        "warnings": 12,
        "python_version": "3.14.6",
        "pytest_version": "9.1.1",
    }
    diagnostic.update(mutation)

    with pytest.raises(ValueError, match=match):
        _baseline(diagnostic_output=diagnostic)


def test_duplicate_failure_node_ids_are_rejected():
    duplicate = _failure("tests/test_same.py::test_same")
    with pytest.raises(ValueError, match="duplicate"):
        _baseline(duplicate, deepcopy(duplicate))


def test_machine_readable_prior_node_ids_get_exact_set_comparison():
    current = [
        _failure("tests/test_keep.py::test_keep"),
        _failure("tests/test_added.py::test_added"),
    ]
    baseline = build_known_failure_baseline(
        command="python -m pytest -q",
        collection_timestamp="2026-07-28T16:00:00+07:00",
        worktree_state={"commit": "abc", "dirty": True},
        summary={"passed": 1, "skipped": 0, "failed": 2},
        known_failures=current,
        reported_summary={"passed": 1, "skipped": 0, "failed": 2},
        reported_node_ids=[
            "tests/test_keep.py::test_keep",
            "tests/test_removed.py::test_removed",
        ],
    )

    assert baseline["comparison"]["node_id_comparison"] == "available"
    assert baseline["comparison"]["added_node_ids"] == [
        "tests/test_added.py::test_added"
    ]
    assert baseline["comparison"]["removed_node_ids"] == [
        "tests/test_removed.py::test_removed"
    ]
    assert baseline["comparison"]["changed_node_ids"] == []
    assert baseline["comparison"]["unchanged_node_ids"] == [
        "tests/test_keep.py::test_keep"
    ]
    assert normalize_known_failure_baseline(baseline) == baseline


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (
            lambda value: value.update(category="invented_category"),
            "not stable",
        ),
        (
            lambda value: value.update(index_path_intersection="no"),
            "must be a boolean",
        ),
        (
            lambda value: value.update(reason=""),
            "must be nonblank",
        ),
    ],
)
def test_failure_records_fail_closed_on_invalid_fields(mutation, match):
    failure = _failure("tests/test_bad.py::test_bad")
    mutation(failure)
    with pytest.raises(ValueError, match=match):
        _baseline(failure)


def test_reported_failure_total_must_match_records():
    with pytest.raises(ValueError, match="record count"):
        build_known_failure_baseline(
            command="python -m pytest -q",
            collection_timestamp="2026-07-28T16:00:00+07:00",
            worktree_state={"commit": "abc", "dirty": True},
            summary={"passed": 1, "skipped": 0, "failed": 2},
            known_failures=[_failure("tests/test_one.py::test_one")],
        )


def test_loaded_baseline_rejects_wrong_schema_phase_and_stale_comparison():
    baseline = _baseline()
    mutations = (
        ("schema_version", 2, "schema_version"),
        ("phase", "INDEX.1E.1", "phase"),
    )
    for field, value, match in mutations:
        changed = deepcopy(baseline)
        changed[field] = value
        with pytest.raises(ValueError, match=match):
            normalize_known_failure_baseline(changed)

    changed = deepcopy(baseline)
    changed["comparison"]["failed_delta"] = 999
    with pytest.raises(ValueError, match="stale comparison"):
        normalize_known_failure_baseline(changed)


def test_authoritative_index_failure_blocks_readiness():
    baseline = _baseline(
        _failure(
            "tests/test_indexer.py::test_replace",
            category=FAILURE_AUTHORITATIVE_INDEX,
            intersects=True,
        )
    )
    decision = classify_readiness(
        baseline=baseline,
        prerequisites=default_prerequisite_audit(),
    )

    assert decision["status"] == READINESS_BLOCKED_INDEX
    assert decision["phase_status"] == PHASE_STATUS_BLOCKED
    assert decision["next_phase_allowed"] is False
    assert decision["index_runtime_failures"] == 1


def test_index_adjacent_failure_also_blocks_readiness():
    baseline = _baseline(
        _failure(
            "tests/test_index_contract.py::test_artifact",
            category=FAILURE_INDEX_ADJACENT,
            intersects=True,
        )
    )
    decision = classify_readiness(
        baseline=baseline,
        prerequisites=default_prerequisite_audit(),
    )
    assert decision["status"] == READINESS_BLOCKED_INDEX
    assert decision["index_adjacent_failures"] == 1
    assert decision["next_phase_allowed"] is False


def test_unclassified_failure_blocks_readiness():
    baseline = _baseline(
        _failure(
            "tests/test_unknown.py::test_unknown",
            category=FAILURE_UNCLASSIFIED,
        )
    )
    decision = classify_readiness(
        baseline=baseline,
        prerequisites=default_prerequisite_audit(),
    )
    assert decision["status"] == READINESS_BLOCKED_UNCLASSIFIED
    assert decision["phase_status"] == PHASE_STATUS_BLOCKED
    assert decision["next_phase_allowed"] is False


def test_missing_prerequisite_and_contract_mismatch_fail_closed():
    baseline = _baseline()
    prerequisites = default_prerequisite_audit()
    prerequisites.pop("manifest")
    missing = classify_readiness(
        baseline=baseline,
        prerequisites=prerequisites,
    )
    mismatch = classify_readiness(
        baseline=baseline,
        prerequisites=default_prerequisite_audit(),
        contract_mismatches=["persistence-disabled claim is contradictory"],
    )

    assert missing["status"] == READINESS_BLOCKED_PREREQUISITE
    assert missing["missing_prerequisites"] == ["manifest"]
    assert missing["next_phase_allowed"] is False
    assert mismatch["status"] == READINESS_BLOCKED_CONTRACT
    assert mismatch["next_phase_allowed"] is False


def test_ready_and_ready_with_warnings_are_the_only_allowed_states():
    baseline = _baseline()
    ready = classify_readiness(
        baseline=baseline,
        prerequisites=default_prerequisite_audit(),
    )
    warned = classify_readiness(
        baseline=baseline,
        prerequisites=default_prerequisite_audit(),
        warnings=["Known unrelated failures remain."],
    )

    assert ready["status"] == READINESS_READY
    assert ready["phase_status"] == PHASE_STATUS_COMPLETE
    assert ready["next_phase_allowed"] is True
    assert warned["status"] == READINESS_READY_WITH_WARNINGS
    assert (
        warned["phase_status"]
        == PHASE_STATUS_COMPLETE_WITH_WARNINGS
    )
    assert warned["next_phase_allowed"] is True


def test_default_preflight_has_one_authoritative_deferred_seam_and_blocks():
    report = build_index_delta_preflight(_baseline())

    assert validate_index_delta_preflight(report) == ()
    assert len(report["integration_seams"]) == 1
    seam = report["integration_seams"][0]
    assert (seam["module"], seam["function"]) == (
        "core.indexer",
        "index_repository",
    )
    assert seam["owns_shared_inventory"] is True
    assert seam["uses_confirmed_identity_permissions"] is True
    assert seam["derives_authority_from_project_tag"] is False
    assert seam["actual_dispatch_deferred"] is True
    assert "observed" in seam["observed_vs_applied"]
    assert "applied" in seam["observed_vs_applied"]
    assert report["readiness"]["status"] == READINESS_BLOCKED_CONTRACT
    assert report["readiness"]["phase_status"] == PHASE_STATUS_BLOCKED
    assert report["readiness"]["next_phase_allowed"] is False
    assert report["blocking_contract_mismatches"] == (
        report["readiness"]["contract_mismatches"]
    )
    assert report["blocking_contract_mismatches"] == sorted(
        default_contract_mismatches()
    )
    assert report["deferred_integration_requirements"] == sorted(
        default_deferred_integration_requirements()
    )
    assert report["integration_contract_gaps"] == sorted(
        default_contract_mismatches()
        + default_deferred_integration_requirements()
    )


def test_validator_rejects_contradictory_ready_decision_and_empty_guardrails():
    report = build_index_delta_preflight(_baseline())
    report["readiness"]["status"] = READINESS_READY
    report["readiness"]["phase_status"] = PHASE_STATUS_COMPLETE
    report["readiness"]["next_phase_allowed"] = True
    report["recommended_next_phase"] = (
        "INDEX.1E.1 — Manifest Load and Delta Plan Dispatch"
    )

    errors = validate_index_delta_preflight(report)

    assert "readiness status contradicts the embedded evidence" in errors
    assert "phase status contradicts the readiness decision" in errors
    assert (
        "next_phase_allowed contradicts the readiness decision" in errors
    )
    assert (
        "recommended next phase contradicts the readiness decision"
        in errors
    )

    report = build_index_delta_preflight(_baseline())
    report["guardrails"] = {}
    assert (
        "guardrail decisions must use the exact key set"
        in validate_index_delta_preflight(report)
    )


def test_validator_rejects_stale_readiness_evidence_fields():
    report = build_index_delta_preflight(_baseline())
    report["readiness"]["contract_mismatches"] = []
    report["readiness"]["warnings"] = []

    errors = validate_index_delta_preflight(report)

    assert (
        "readiness.contract_mismatches contradicts embedded evidence"
        in errors
    )
    assert "readiness.warnings contradicts embedded evidence" in errors


def test_current_run_a_and_b_pin_full_nonincremental_work():
    behavior = build_index_delta_preflight(_baseline())[
        "current_production_behavior"
    ]

    assert behavior["run_a"] == behavior["run_b"]
    assert behavior["run_b"] == {
        "repository_walks": 1,
        "content_reads": 3,
        "parsed_files": 3,
        "graph_parsed_files": 3,
        "embedded_files": 3,
        "replacement_calls": 3,
        "deletion_calls": 0,
        "manifest_loads": 0,
        "manifests_saved": 0,
        "delta_plans_built": 0,
        "reconciliation_calls": 1,
    }


def test_persistence_disabled_cannot_claim_trusted_success():
    behavior = build_index_delta_preflight(_baseline())[
        "db_disabled_behavior"
    ]

    assert behavior["processing_can_succeed"] is True
    assert behavior["persistent_canonical_indexing_succeeded"] is False
    assert behavior["completion_status"] == "persistence_disabled"
    assert behavior["trusted_completion"] is False
    assert behavior["manifest_advance_allowed"] is False
    assert behavior["trusted_current_claim_allowed"] is False
    assert behavior["fake_applied_state_claim"] is False


def test_all_index_1d_primitives_are_importable_and_reported_ready():
    prerequisites = default_prerequisite_audit()

    assert set(prerequisites) == set(PREREQUISITE_NAMES)
    assert all(
        item["status"] == "ready"
        for item in prerequisites.values()
    )
    assert RepositoryInventory
    assert create_repository_inventory
    assert validate_repository_inventory
    assert build_repository_identity
    assert initialize_repository_identity_state
    assert derive_canonical_identity_permissions
    assert load_repository_identity_state
    assert RepositoryManifest
    assert get_repository_manifest_path
    assert load_repository_manifest
    assert inspect_repository_delta
    assert RepositoryDelta
    assert IndexExecutionPlan
    assert build_index_execution_plan
    assert classify_index_completion
    assert may_advance_applied_manifest
    assert AppliedManifestEvidence
    assert may_claim_repository_intelligence_current


def test_epoch_writer_and_retriever_scope_mismatch_is_characterized(tmp_path):
    without_tag = build_repository_identity(tmp_path, project_tag=None)
    with_tag = build_repository_identity(
        tmp_path,
        project_tag="semantic-only-label",
    )
    expected = build_code_index_scope(tmp_path)
    epoch_identity = build_repository_identity(
        tmp_path,
        architecture_epoch=1,
    )

    assert without_tag.index_scope == expected
    assert with_tag.index_scope == expected
    assert without_tag.project_tag is None
    assert with_tag.project_tag == "semantic-only-label"
    assert is_code_index_scope(expected)
    assert _require_index_scope(expected) == expected
    assert _index_scope_for(str(tmp_path), None) == expected
    assert epoch_identity.index_scope != expected
    assert (
        _index_scope_for(str(tmp_path), epoch_identity.index_scope)
        == expected
    )
    assert (
        _index_scope_for(str(tmp_path), epoch_identity.index_scope)
        != epoch_identity.index_scope
    )


def test_uninitialized_identity_does_not_grant_authority(tmp_path):
    state = initialize_repository_identity_state(tmp_path)
    permissions = derive_canonical_identity_permissions(state)

    assert state.identity_status == "initial_confirmation_required"
    assert permissions.canonical_build_allowed is False
    assert permissions.canonical_refresh_allowed is False
    assert permissions.reconciliation_allowed is False
    assert permissions.applied_manifest_advance_allowed is False


def test_execution_planner_represents_delta_embedding_and_dimension_cases():
    delta = RepositoryDelta(
        added=("add.py",),
        modified=("mod.py",),
        deleted=("gone.py",),
        unchanged=("same.py",),
        hashes_computed=2,
        hashes_reused=1,
        policy_changed=False,
    )
    normal = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=EmbeddingCompatibility.COMPATIBLE,
    )
    disabled = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=EmbeddingCompatibility.OFF,
    )
    incompatible = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.INCOMPATIBLE_DIMENSION
        ),
    )
    policy_reset = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=EmbeddingCompatibility.COMPATIBLE,
        force_full_reindex=True,
        force_reindex_reason="policy_changed",
    )

    assert normal.to_parse == ("add.py", "mod.py")
    assert normal.to_delete == ("gone.py",)
    assert normal.unchanged == ("same.py",)
    assert disabled.embedding_action is EmbeddingAction.DISABLED
    assert incompatible.embedding_action is EmbeddingAction.BLOCKED
    assert incompatible.blocked_reason == "embedding_dimension_incompatible"
    assert policy_reset.force_full_reindex is True
    assert policy_reset.force_reindex_reason == "policy_changed"


def test_policy_change_requires_an_external_override_today():
    policy_only_delta = RepositoryDelta(
        added=(),
        modified=(),
        deleted=(),
        unchanged=("same.py",),
        hashes_computed=0,
        hashes_reused=1,
        policy_changed=True,
    )
    plan = build_index_execution_plan(
        policy_only_delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=EmbeddingCompatibility.COMPATIBLE,
    )

    assert plan.source_state_changed is False
    assert plan.force_full_reindex is False
    assert not hasattr(plan, "policy_changed")
    assert any(
        value.startswith("planner_policy_change_gap:")
        for value in default_deferred_integration_requirements()
    )


def test_manifest_delta_requires_indexable_membership_translation(tmp_path):
    (tmp_path / "unit.py").write_text("print('unit')\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    inventory = create_repository_inventory(tmp_path)

    _observed, delta = inspect_repository_delta(
        str(tmp_path),
        inventory=inventory,
    )
    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=EmbeddingCompatibility.COMPATIBLE,
    )
    indexable = {
        item.relative_path.as_posix()
        for item in inventory.indexable_entries
    }

    assert ".gitignore" in delta.added
    assert ".gitignore" in plan.to_parse
    assert ".gitignore" not in indexable
    assert any(
        value.startswith("manifest_indexable_membership_mismatch:")
        for value in default_deferred_integration_requirements()
    )


def test_empty_scope_reconciliation_gap_is_frozen():
    with pytest.raises(ValueError, match="must not be empty"):
        _require_current_files(set())
    assert any(
        value.startswith("empty_repository_deletion_gap:")
        for value in default_contract_mismatches()
    )


def test_web_and_production_boundaries_remain_honestly_characterized():
    report = build_index_delta_preflight(_baseline())
    web = report["web_request_boundary"]
    callers = {
        item["caller"]: item
        for item in report["production_entrypoints"]
    }

    assert web["identity_confirmation_enforced"] is False
    assert web["completion_metadata_reaches_payload"] is False
    assert web["credential_redaction_preserved"] is True
    assert web["shared_inventory"] is True
    assert callers["web.runner.run_agent_web"][
        "manifest_load_behavior"
    ] == "none"
    assert callers["web.runner.run_agent_web"][
        "delta_planner_behavior"
    ] == "not called"
    assert report["retrieval_scope"]["baseline_scope_compatible"] is True
    assert (
        report["retrieval_scope"][
            "architecture_epoch_scope_compatible"
        ]
        is False
    )
    assert report["retrieval_scope"]["compatible"] is False
    assert report["retrieval_scope"]["project_tag_is_authority"] is False
    assert report["retrieval_scope"]["retrieval_paths"] == list(
        RETRIEVAL_SCOPE_PATHS
    )


def test_guardrails_record_no_production_behavior_change():
    report = build_index_delta_preflight(_baseline())
    registry = json.loads(
        (PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(
            encoding="utf-8"
        )
    )
    phase = next(
        item
        for item in registry["phases"]
        if item["phase_id"] == "INDEX.1E.0"
    )
    allowed = set(phase["allowed_files"])
    forbidden = set(phase["forbidden_files"])
    phase_code = {
        "core/index_delta_preflight.py",
        "scripts/create_index_delta_preflight.py",
        "tests/test_index_delta_preflight.py",
    }
    protected_production = {
        "core/indexer.py",
        "core/index_manifest.py",
        "core/index_execution.py",
        "core/index_completion.py",
        "core/repository_identity.py",
        "core/repository_identity_state.py",
        "core/repository_inventory.py",
        "core/retriever.py",
    }

    assert set(report["guardrails"]) == set(GUARDRAIL_KEYS)
    assert all(value is False for value in report["guardrails"].values())
    assert phase_code <= allowed
    assert protected_production <= forbidden
    assert allowed.isdisjoint(protected_production)
    assert not any(path.startswith("database/") for path in allowed)
    assert not any(path.startswith("graph/") for path in allowed)
    assert not any(path.startswith("web/") for path in allowed)
    assert not any(path.startswith("benchmarks/") for path in allowed)

    helper = PROJECT_ROOT / "core" / "index_delta_preflight.py"
    generator = PROJECT_ROOT / "scripts" / "create_index_delta_preflight.py"
    helper_imports = _python_imports(helper)
    generator_imports = _python_imports(generator)
    prohibited_import_prefixes = (
        "core.indexer",
        "core.index_manifest",
        "core.index_execution",
        "core.index_completion",
        "core.retriever",
        "database",
        "graph",
        "web",
        "subprocess",
        "threading",
        "concurrent",
        "requests",
        "openai",
    )
    assert not any(
        imported.startswith(prohibited_import_prefixes)
        for imported in helper_imports | generator_imports
    )
    assert "core.index_delta_preflight" in generator_imports

    prohibited_calls = {
        "index_repository",
        "load_repository_manifest",
        "save_repository_manifest",
        "inspect_repository_delta",
        "build_index_execution_plan",
        "replace_file_index",
        "delete_file_index",
        "reconcile_repository_index",
        "embed_code",
    }
    assert _call_leaf_names(helper).isdisjoint(prohibited_calls)
    assert _call_leaf_names(generator).isdisjoint(prohibited_calls)

    production_entrypoints = (
        PROJECT_ROOT / "core" / "indexer.py",
        PROJECT_ROOT / "core" / "retriever.py",
        PROJECT_ROOT / "main.py",
        PROJECT_ROOT / "cli" / "interactive.py",
        PROJECT_ROOT / "web" / "runner.py",
    )
    assert all(
        "index_delta_preflight"
        not in path.read_text(encoding="utf-8")
        for path in production_entrypoints
    )

    test_tree = ast.parse(
        Path(__file__).read_text(encoding="utf-8"),
        filename=__file__,
    )
    weakening_decorators = {
        _decorator_name(decorator)
        for node in ast.walk(test_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for decorator in node.decorator_list
    }
    assert "pytest.mark.skip" not in weakening_decorators
    assert "pytest.mark.xfail" not in weakening_decorators
    assert report["recommended_next_phase"].startswith("BLOCKED")


def test_renderers_and_writes_are_deterministic(tmp_path):
    baseline = _baseline()
    report_a = build_index_delta_preflight(baseline)
    report_b = build_index_delta_preflight(deepcopy(baseline))

    assert report_a == report_b
    assert render_known_failure_markdown(baseline) == (
        render_known_failure_markdown(deepcopy(baseline))
    )
    assert render_index_delta_preflight_markdown(report_a) == (
        render_index_delta_preflight_markdown(report_b)
    )

    first = write_index_delta_preflight(
        repo_root=tmp_path,
        baseline=baseline,
    )
    first_json = Path(first["preflight_json_path"]).read_bytes()
    second = write_index_delta_preflight(
        repo_root=tmp_path,
        baseline=deepcopy(baseline),
    )
    second_json = Path(second["preflight_json_path"]).read_bytes()

    assert first_json == second_json
    assert json.loads(first_json)["readiness"]["next_phase_allowed"] is False
    assert Path(first["baseline_json_path"]).is_file()
    assert Path(first["baseline_markdown_path"]).is_file()
    assert Path(first["preflight_markdown_path"]).is_file()


def test_canonical_artifacts_are_normalized_and_byte_reproducible(tmp_path):
    baseline_path = PROJECT_ROOT / DEFAULT_BASELINE_JSON
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    assert normalize_known_failure_baseline(baseline) == baseline
    result = write_index_delta_preflight(
        repo_root=tmp_path,
        baseline=baseline,
    )
    artifact_pairs = (
        (
            PROJECT_ROOT / DEFAULT_BASELINE_JSON,
            Path(result["baseline_json_path"]),
        ),
        (
            PROJECT_ROOT / DEFAULT_PREFLIGHT_JSON,
            Path(result["preflight_json_path"]),
        ),
        (
            PROJECT_ROOT / DEFAULT_BASELINE_MARKDOWN,
            Path(result["baseline_markdown_path"]),
        ),
        (
            PROJECT_ROOT / DEFAULT_PREFLIGHT_MARKDOWN,
            Path(result["preflight_markdown_path"]),
        ),
    )

    for canonical, regenerated in artifact_pairs:
        assert canonical.read_bytes() == regenerated.read_bytes()


def test_script_reads_captured_baseline_and_writes_artifacts(tmp_path):
    source = tmp_path / "captured-baseline.json"
    source.write_text(
        json.dumps(_baseline(), indent=2),
        encoding="utf-8",
    )

    result = script.run_create_index_delta_preflight(
        repo_root=tmp_path,
        baseline_path=source,
    )

    assert (
        result["report"]["readiness"]["phase_status"]
        == PHASE_STATUS_BLOCKED
    )
    assert Path(result["baseline_json_path"]).is_file()
    assert Path(result["preflight_json_path"]).is_file()
