"""INDEX.1D.1 focused tests for the contract-only dual graph boundary."""
from __future__ import annotations

import ast
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from core.dual_graph_lifecycle import (
    ACTIVATION_ARTIFACT_KIND,
    ACTIVATION_STORAGE_ROOT,
    CANONICAL_ARTIFACT_KIND,
    CONTRACT_JSON_NAME,
    CONTRACT_MD_NAME,
    DEFAULT_ACTIVATION_TTL_SECONDS,
    GRAPH_KIND_ACTIVATION,
    GRAPH_KIND_CANONICAL,
    GRAPH_KIND_DIRECT_CONTEXT,
    build_activation_cleanup_plan,
    build_activation_metadata,
    build_canonical_operation_authority,
    build_dual_graph_lifecycle_contract,
    can_release_activation_lease,
    classify_activation_expiry,
    classify_activation_freshness,
    graph_kind_contract,
    recommend_graph_kind,
    render_dual_graph_lifecycle_json,
    render_dual_graph_lifecycle_markdown,
    validate_activation_lease,
    validate_activation_transition,
    validate_canonical_transition,
)
from scripts.create_dual_graph_lifecycle_contract import (
    run_create_dual_graph_lifecycle_contract,
)


ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = ROOT / "core" / "dual_graph_lifecycle.py"
SCRIPT_PATH = ROOT / "scripts" / "create_dual_graph_lifecycle_contract.py"
DESIGN_PATH = ROOT / "docs" / "designs" / "2026-07-27-dual-graph-lifecycle-contract.md"

NOW = "2026-07-27T12:00:00+00:00"
HOUR_71 = "2026-07-24T13:00:01+00:00"
HOUR_72 = "2026-07-24T12:00:00+00:00"


def _record(
    activation_id: str = "act-a",
    *,
    status: str = "active",
    last_used_at: str = HOUR_71,
    repository_root: str = "C:/repo",
    pinned: bool = False,
    lease_expires_at: str | None = None,
    storage_bytes: int = 10,
) -> dict:
    return build_activation_metadata(
        activation_id=activation_id,
        repository_root=repository_root,
        task_id=f"run-{activation_id}",
        created_at="2026-07-20T12:00:00+00:00",
        last_used_at=last_used_at,
        status=status,
        pinned=pinned,
        lease_owner="run-owner" if lease_expires_at else None,
        lease_acquired_at="2026-07-27T11:00:00+00:00" if lease_expires_at else None,
        lease_expires_at=lease_expires_at,
        storage_bytes=storage_bytes,
    )


# Graph-kind contract


def test_stable_graph_kind_identifiers():
    assert GRAPH_KIND_DIRECT_CONTEXT == "direct_context"
    assert GRAPH_KIND_ACTIVATION == "activation_graph"
    assert GRAPH_KIND_CANONICAL == "canonical_incremental_graph"


def test_direct_context_requires_no_graph_or_scan():
    direct = graph_kind_contract(GRAPH_KIND_DIRECT_CONTEXT)
    assert direct["graph_required"] is False
    assert direct["repository_scan_required"] is False
    assert direct["database_write_allowed"] is False


def test_activation_cannot_write_persistent_index_state():
    activation = graph_kind_contract(GRAPH_KIND_ACTIVATION)
    assert activation["database_write_allowed"] is False
    assert activation["manifest_advancement_allowed"] is False
    assert activation["reconciliation_allowed"] is False


def test_canonical_is_only_graph_kind_allowed_to_advance_manifest():
    for kind in (GRAPH_KIND_DIRECT_CONTEXT, GRAPH_KIND_ACTIVATION):
        assert graph_kind_contract(kind)["manifest_advancement_allowed"] is False
    assert (
        graph_kind_contract(GRAPH_KIND_CANONICAL)["manifest_advancement_allowed"]
        == "trusted_completion_only"
    )


def test_activation_pinning_does_not_make_it_canonical():
    metadata = _record(pinned=True)
    assert metadata["graph_kind"] == GRAPH_KIND_ACTIVATION
    assert metadata["canonical_manifest_advanced"] is False
    assert metadata["persistent_code_index_written"] is False
    assert metadata["repository_completeness_claimed"] is False


# Activation expiry


def test_less_than_72_hours_stays_active():
    result = classify_activation_expiry(last_used_at=HOUR_71, now=NOW)
    assert result.decision == "keep_active"
    assert result.expired is False


@pytest.mark.parametrize(
    "last_used",
    [HOUR_72, "2026-07-24T11:59:59+00:00"],
)
def test_exactly_at_or_beyond_72_hours_expires(last_used):
    result = classify_activation_expiry(last_used_at=last_used, now=NOW)
    assert result.decision == "mark_expired"
    assert result.expired is True


def test_last_used_not_created_at_controls_expiry():
    metadata = build_activation_metadata(
        activation_id="act-reused",
        repository_root="C:/repo",
        task_id="run-reused",
        created_at="2025-01-01T00:00:00+00:00",
        last_used_at=HOUR_71,
        status="active",
    )
    result = classify_activation_expiry(
        last_used_at=metadata["last_used_at"],
        now=NOW,
        ttl_seconds=metadata["ttl_seconds"],
    )
    assert result.decision == "keep_active"


def test_pinned_expired_graph_is_retained():
    result = classify_activation_expiry(
        last_used_at=HOUR_72, now=NOW, pinned=True
    )
    assert result.decision == "keep_pinned"
    assert result.protected is True


def test_valid_lease_protects_graph():
    result = classify_activation_expiry(
        last_used_at=HOUR_72,
        now=NOW,
        lease_expires_at="2026-07-27T12:30:00+00:00",
    )
    assert result.decision == "keep_leased"
    assert result.protected is True


def test_expired_lease_does_not_protect_graph():
    result = classify_activation_expiry(
        last_used_at=HOUR_72,
        now=NOW,
        lease_expires_at="2026-07-27T12:00:00+00:00",
    )
    assert result.decision == "mark_expired"
    assert result.protected is False


@pytest.mark.parametrize(
    "last_used,now",
    [
        ("not-a-time", NOW),
        ("2026-07-27T11:00:00", NOW),
        (HOUR_71, "2026-07-27T12:00:00"),
        ("2026-07-28T12:00:00+00:00", NOW),
    ],
)
def test_invalid_or_naive_timestamps_fail_closed(last_used, now):
    result = classify_activation_expiry(last_used_at=last_used, now=now)
    assert result.decision == "invalid_metadata"
    assert result.automatic_cleanup_allowed is False


def test_default_ttl_is_72_hours():
    assert DEFAULT_ACTIVATION_TTL_SECONDS == 259200


# Cleanup planning


def test_expired_graph_becomes_cleanup_candidate():
    plan = build_activation_cleanup_plan(
        [_record(status="expired", last_used_at=HOUR_72)], now=NOW
    )
    assert plan["cleanup_order"][0]["activation_id"] == "act-a"
    assert plan["records"][0]["classification"] == "cleanup_candidate"


def test_pinned_graph_is_excluded_from_cleanup():
    plan = build_activation_cleanup_plan(
        [_record(status="expired", last_used_at=HOUR_72, pinned=True)], now=NOW
    )
    assert plan["cleanup_order"] == []
    assert plan["records"][0]["classification"] == "blocked_by_pin"


def test_leased_graph_is_excluded_from_cleanup():
    plan = build_activation_cleanup_plan(
        [
            _record(
                status="expired",
                last_used_at=HOUR_72,
                lease_expires_at="2026-07-27T13:00:00+00:00",
            )
        ],
        now=NOW,
    )
    assert plan["cleanup_order"] == []
    assert plan["records"][0]["classification"] == "blocked_by_lease"


def test_canonical_artifact_is_never_selected():
    record = _record(status="expired", last_used_at=HOUR_72)
    record.update(
        artifact_kind=CANONICAL_ARTIFACT_KIND,
        graph_kind=GRAPH_KIND_CANONICAL,
        artifact_path=".agent/repository_intelligence/repo/epoch",
    )
    plan = build_activation_cleanup_plan([record], now=NOW)
    assert plan["cleanup_order"] == []
    assert plan["records"][0]["classification"] == "invalid_or_unmanaged"


@pytest.mark.parametrize(
    "mutation",
    [
        {"managed_cleanup_allowed": False},
        {"artifact_kind": "unknown_artifact"},
        {"artifact_path": "../activation_graphs/act-a"},
        {"artifact_path": ".agent/repository_intelligence/act-a"},
        {"path_is_symlink": True},
    ],
)
def test_unmanaged_missing_marker_or_unsafe_path_is_never_selected(mutation):
    record = _record(status="expired", last_used_at=HOUR_72)
    record.update(mutation)
    plan = build_activation_cleanup_plan([record], now=NOW)
    assert plan["cleanup_order"] == []
    assert plan["records"][0]["classification"] == "invalid_or_unmanaged"


def test_cleanup_plan_is_deterministic():
    records = [
        _record("act-z", status="stale"),
        _record("act-a", status="expired", last_used_at=HOUR_72),
    ]
    first = build_activation_cleanup_plan(records, now=NOW)
    second = build_activation_cleanup_plan(records, now=NOW)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_lru_budget_ordering_is_deterministic():
    records = [
        _record("act-new", last_used_at="2026-07-27T11:00:00+00:00"),
        _record("act-old", last_used_at="2026-07-27T09:00:00+00:00"),
        _record("act-mid", last_used_at="2026-07-27T10:00:00+00:00"),
    ]
    plan = build_activation_cleanup_plan(
        records, now=NOW, max_graphs_per_repo=2
    )
    assert [item["activation_id"] for item in plan["cleanup_order"]] == ["act-old"]


def test_storage_budget_uses_lru_after_expired_and_stale():
    records = [
        _record("act-expired", status="expired", last_used_at=HOUR_72, storage_bytes=5),
        _record("act-old", last_used_at="2026-07-27T09:00:00+00:00", storage_bytes=10),
        _record("act-new", last_used_at="2026-07-27T11:00:00+00:00", storage_bytes=10),
    ]
    plan = build_activation_cleanup_plan(
        records, now=NOW, max_graphs_per_repo=20, max_total_bytes=10
    )
    assert [item["activation_id"] for item in plan["cleanup_order"]] == [
        "act-expired",
        "act-old",
    ]


def test_ttl_expired_active_record_sorts_before_stale_record():
    records = [
        _record("act-stale", status="stale"),
        _record("act-ttl-expired", status="active", last_used_at=HOUR_72),
    ]
    plan = build_activation_cleanup_plan(records, now=NOW)
    assert [item["activation_id"] for item in plan["cleanup_order"]] == [
        "act-ttl-expired",
        "act-stale",
    ]


def test_invalid_unbounded_lease_fails_closed_in_cleanup():
    record = _record(status="expired", last_used_at=HOUR_72)
    record["lease"] = {
        "owner": "run-a",
        "acquired_at": "2026-07-01T00:00:00+00:00",
        "expires_at": "2026-08-01T00:00:00+00:00",
    }
    plan = build_activation_cleanup_plan([record], now=NOW)
    assert plan["cleanup_order"] == []
    assert plan["records"][0]["classification"] == "invalid_or_unmanaged"


def test_cleanup_rejects_canonical_root_even_with_activation_marker():
    record = _record(status="expired", last_used_at=HOUR_72)
    record["artifact_path"] = ".agent/repository_intelligence/act-a"
    with pytest.raises(ValueError, match="canonical storage root"):
        build_activation_cleanup_plan(
            [record],
            now=NOW,
            activation_root=".agent/repository_intelligence",
        )
    with pytest.raises(ValueError, match="canonical storage root"):
        build_activation_cleanup_plan(
            [record],
            now=NOW,
            activation_root="C:/repo/.agent/repository_intelligence",
        )


def test_cleanup_planner_performs_no_deletion_and_keeps_roots_separate():
    plan = build_activation_cleanup_plan(
        [_record(status="expired", last_used_at=HOUR_72)], now=NOW
    )
    assert plan["dry_run"] is True
    assert plan["deletion_performed"] is False
    assert plan["activation_root"] == ACTIVATION_STORAGE_ROOT
    assert plan["canonical_root_received_as_candidate"] is False


# Freshness


def test_unchanged_fingerprints_are_fresh():
    result = classify_activation_freshness(
        {"a.py": "1", "b.py": "2"},
        {"a.py": "1", "b.py": "2"},
        changed_file_limit=1,
        changed_ratio_limit=0.5,
    )
    assert result.status == "fresh"
    assert result.reuse_allowed is True


def test_small_bounded_change_is_partial():
    result = classify_activation_freshness(
        {"a.py": "1", "b.py": "2", "c.py": "3"},
        {"a.py": "9", "b.py": "2", "c.py": "3"},
        changed_file_limit=1,
        changed_ratio_limit=0.5,
    )
    assert result.status == "partially_changed"
    assert result.bounded_refresh_recommended is True


def test_large_change_ratio_is_stale():
    result = classify_activation_freshness(
        {"a.py": "1", "b.py": "2"},
        {"a.py": "9", "b.py": "8"},
        changed_file_limit=1,
        changed_ratio_limit=0.5,
    )
    assert result.status == "stale"
    assert result.rebuild_required is True


def test_missing_seed_file_requires_rebuild():
    result = classify_activation_freshness(
        {"seed.py": "1", "other.py": "2"},
        {"other.py": "2"},
        changed_file_limit=1,
        changed_ratio_limit=0.5,
        seed_files=["seed.py"],
    )
    assert result.status == "missing_files"
    assert result.missing_files == ("seed.py",)
    assert result.rebuild_required is True


def test_missing_seed_not_present_in_stored_map_still_requires_rebuild():
    result = classify_activation_freshness(
        {"other.py": "2"},
        {"other.py": "2"},
        changed_file_limit=1,
        changed_ratio_limit=0.5,
        seed_files=["seed.py"],
    )
    assert result.status == "missing_files"
    assert result.missing_files == ("seed.py",)
    assert result.rebuild_required is True


@pytest.mark.parametrize(
    "stored,current",
    [
        (None, {"a.py": "1"}),
        ({}, {}),
        ({"a.py": None}, {"a.py": "1"}),
    ],
)
def test_unknown_fingerprint_state_never_claims_fresh(stored, current):
    result = classify_activation_freshness(
        stored,
        current,
        changed_file_limit=1,
        changed_ratio_limit=0.5,
    )
    assert result.status == "unknown"
    assert result.reuse_allowed is False


# Lifecycle, lease, canonical authority, and recommendation


@pytest.mark.parametrize(
    "current,target,refresh",
    [
        ("planned", "active", False),
        ("active", "stale", False),
        ("stale", "active", True),
        ("expired", "cleanup_candidate", False),
        ("cleanup_candidate", "deleted", False),
    ],
)
def test_valid_activation_transitions_pass(current, target, refresh):
    assert validate_activation_transition(
        current, target, freshness_succeeded=refresh
    ).allowed


@pytest.mark.parametrize(
    "current,target",
    [
        ("active", "planned"),
        ("expired", "active"),
        ("stale", "deleted"),
        ("planned", "deleted"),
    ],
)
def test_invalid_activation_transitions_fail(current, target):
    assert not validate_activation_transition(current, target).allowed


def test_deleted_activation_cannot_revive_same_identity():
    decision = validate_activation_transition("deleted", "active")
    assert decision.allowed is False
    assert decision.new_identity_required is True


def test_blocked_activation_cannot_revive_same_identity():
    decision = validate_activation_transition("blocked", "active")
    assert decision.allowed is False
    assert decision.new_identity_required is True


def test_canonical_current_requires_trusted_completion():
    assert not validate_canonical_transition("building", "current").allowed
    assert validate_canonical_transition(
        "building", "current", trusted_completion=True
    ).allowed
    assert not validate_canonical_transition("refreshing", "current").allowed


def test_initial_and_major_change_transitions_require_confirmation():
    assert not validate_canonical_transition(
        "initial_confirmation_required", "building"
    ).allowed
    assert validate_canonical_transition(
        "initial_confirmation_required", "building", human_confirmation=True
    ).allowed
    assert not validate_canonical_transition(
        "major_change_confirmation_required", "refreshing"
    ).allowed


def test_major_change_blocks_reconciliation_and_manifest_advancement():
    authority = build_canonical_operation_authority(
        status="refreshing",
        identity_confirmed=True,
        successful_persistence=True,
        trusted_completion=True,
        major_change_pending=True,
    )
    assert authority["scope_reconciliation_allowed"] is False
    assert authority["manifest_advancement_allowed"] is False
    assert authority["trusted_architecture_epoch_replacement_allowed"] is False
    assert authority["human_confirmation_required"] is True


def test_trusted_canonical_operation_may_advance_after_persistence():
    authority = build_canonical_operation_authority(
        status="refreshing",
        identity_confirmed=True,
        successful_persistence=True,
        trusted_completion=True,
        major_change_pending=False,
    )
    assert authority["scope_reconciliation_allowed"] is True
    assert authority["manifest_advancement_allowed"] is True


def test_lease_duration_is_bounded_and_expiry_removes_protection():
    active = validate_activation_lease(
        owner="run-a",
        acquired_at="2026-07-27T11:00:00+00:00",
        expires_at="2026-07-27T13:00:00+00:00",
        now=NOW,
    )
    expired = validate_activation_lease(
        owner="run-a",
        acquired_at="2026-07-27T10:00:00+00:00",
        expires_at="2026-07-27T11:00:00+00:00",
        now=NOW,
    )
    too_long = validate_activation_lease(
        owner="run-a",
        acquired_at="2026-07-27T00:00:00+00:00",
        expires_at="2026-07-28T00:00:00+00:00",
        now=NOW,
    )
    assert active.protects_from_cleanup is True
    assert expired.protects_from_cleanup is False
    assert too_long.valid is False


def test_only_matching_owner_may_release_active_lease():
    lease = {
        "owner": "run-a",
        "acquired_at": "2026-07-27T11:00:00+00:00",
        "expires_at": "2026-07-27T13:00:00+00:00",
    }
    assert can_release_activation_lease(lease, owner="run-a", now=NOW)
    assert not can_release_activation_lease(lease, owner="run-b", now=NOW)


def test_recommendations_distinguish_three_context_strategies():
    assert recommend_graph_kind(
        known_files=["a.py"],
        requested_mode="debug",
        scope_breadth="narrow",
        architecture_change=False,
        canonical_status="current",
    ).graph_kind == GRAPH_KIND_DIRECT_CONTEXT
    assert recommend_graph_kind(
        known_files=False,
        requested_mode="debug",
        scope_breadth="bounded",
        architecture_change=False,
        canonical_status="current",
    ).graph_kind == GRAPH_KIND_ACTIVATION
    assert recommend_graph_kind(
        known_files=False,
        requested_mode="Project Evolution",
        scope_breadth="broad",
        architecture_change=True,
        canonical_status="current",
    ).graph_kind == GRAPH_KIND_CANONICAL


def test_narrow_task_can_use_activation_while_major_confirmation_pending():
    result = recommend_graph_kind(
        known_files=False,
        requested_mode="debug",
        scope_breadth="bounded",
        architecture_change=False,
        canonical_status="major_change_confirmation_required",
    )
    assert result.graph_kind == GRAPH_KIND_ACTIVATION
    assert result.canonical_operation_blocked is True


# Artifacts, documentation, purity, and non-mutation guardrails


def test_contract_contains_required_sections_and_future_phases():
    contract = build_dual_graph_lifecycle_contract()
    assert contract["phase"]["phase_id"] == "INDEX.1D.1"
    assert contract["phase"]["contract_only"] is True
    for key in (
        "graph_kinds",
        "activation_graph",
        "canonical_incremental_graph",
        "authority_matrix",
        "command_contract",
        "storage_separation",
        "forbidden_interactions",
        "next_recommended_phases",
    ):
        assert key in contract
    assert any("INDEX.1D.2" in item for item in contract["next_recommended_phases"])
    assert any("INDEX.1F" in item for item in contract["next_recommended_phases"])


def test_authority_matrix_is_explicit_and_test_pinned():
    matrix = build_dual_graph_lifecycle_contract()["authority_matrix"]
    by_capability = {row["capability"]: row for row in matrix}
    assert by_capability["Persistent DB writes"][GRAPH_KIND_ACTIVATION] == "No"
    assert (
        by_capability["Repository completeness claim"][GRAPH_KIND_CANONICAL]
        == "Trusted completion only"
    )
    assert by_capability["TTL cleanup"][GRAPH_KIND_CANONICAL] == "No"


def test_command_contract_avoids_ambiguous_index_command():
    command_contract = build_dual_graph_lifecycle_contract()["command_contract"]
    commands = [item["command"] for item in command_contract["commands"]]
    assert command_contract["future_interface_only"] is True
    assert "cattus index" not in commands
    assert all(
        item["graph_kind"] in {GRAPH_KIND_ACTIVATION, GRAPH_KIND_CANONICAL}
        for item in command_contract["commands"]
    )


def test_json_and_markdown_rendering_are_deterministic():
    contract = build_dual_graph_lifecycle_contract()
    assert render_dual_graph_lifecycle_json(contract) == render_dual_graph_lifecycle_json(
        build_dual_graph_lifecycle_contract()
    )
    assert render_dual_graph_lifecycle_markdown(
        contract
    ) == render_dual_graph_lifecycle_markdown(build_dual_graph_lifecycle_contract())


def test_artifact_builder_writes_fixed_deterministic_names(tmp_path):
    first = run_create_dual_graph_lifecycle_contract(output_root=str(tmp_path))
    first_json = Path(first["json_path"]).read_text(encoding="utf-8")
    first_md = Path(first["md_path"]).read_text(encoding="utf-8")
    second = run_create_dual_graph_lifecycle_contract(output_root=str(tmp_path))
    assert Path(first["json_path"]).name == CONTRACT_JSON_NAME
    assert Path(first["md_path"]).name == CONTRACT_MD_NAME
    assert first_json == Path(second["json_path"]).read_text(encoding="utf-8")
    assert first_md == Path(second["md_path"]).read_text(encoding="utf-8")
    assert json.loads(first_json)["artifact_kind"] == "cattus_dual_graph_lifecycle_contract"


def test_design_document_locks_contract_only_boundary():
    text = DESIGN_PATH.read_text(encoding="utf-8")
    assert "Activation Graph" in text
    assert "Canonical Incremental Graph" in text
    assert "72 hours" in text
    assert "No production graph execution is authorized" in text
    assert "INDEX.1D.2" in text
    assert "INDEX.1F" in text


def test_input_records_are_not_mutated():
    records = [
        _record("act-a", status="expired", last_used_at=HOUR_72),
        _record("act-b", status="stale"),
    ]
    before = copy.deepcopy(records)
    build_activation_cleanup_plan(records, now=NOW)
    assert records == before


def test_core_module_imports_only_stdlib():
    source = CORE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "json",
        "pathlib",
        "typing",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".", 1)[0] in allowed for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".", 1)[0] in allowed


def test_core_has_no_db_graph_builder_indexer_model_or_api_import():
    source = CORE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden_roots = {
        "database",
        "graph",
        "core.indexer",
        "core.index_manifest",
        "core.repository_identity",
        "openai",
        "anthropic",
        "requests",
        "httpx",
        "subprocess",
        "socket",
        "docker",
    }
    assert not any(
        name == forbidden or name.startswith(f"{forbidden}.")
        for name in imported
        for forbidden in forbidden_roots
    )


def test_core_has_no_filesystem_delete_call():
    source = CORE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_methods = {
        "unlink",
        "rmdir",
        "remove",
        "removedirs",
        "rmtree",
        "delete",
    }
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert forbidden_methods.isdisjoint(calls)


def test_core_has_no_subprocess_network_or_runtime_execution_calls():
    combined = (
        CORE_PATH.read_text(encoding="utf-8")
        + "\n"
        + SCRIPT_PATH.read_text(encoding="utf-8")
    ).casefold()
    for token in (
        "subprocess.",
        "requests.",
        "httpx.",
        "socket.",
        "index_repository(",
        "run_benchmarks(",
        "run_validation(",
        "apply_patch(",
        "docker ",
    ):
        assert token not in combined


def test_unused_datetime_object_comparison_remains_timezone_aware():
    result = classify_activation_expiry(
        last_used_at=datetime(2026, 7, 27, 11, tzinfo=timezone.utc),
        now=datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
    )
    assert result.decision == "keep_active"
