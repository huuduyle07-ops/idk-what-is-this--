from core.index_manifest import RepositoryDelta
from core.index_execution import build_index_execution_plan, EmbeddingAction, EmbeddingCompatibility

def test_compatible_plan_parses_only_added_and_modified():
    delta = RepositoryDelta(
        added=("a.py",),
        modified=("b.py",),
        deleted=("c.py",),
        unchanged=("d.py",),
        hashes_computed=2,
        hashes_reused=1,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.to_parse == ("a.py", "b.py")
    assert plan.to_delete == ("c.py",)
    assert plan.to_reembed == ()
    assert plan.embedding_action is (
        EmbeddingAction.COMPUTE_CHANGED
    )
    assert plan.blocked_reason == ""

def test_zero_delta_reuses_everything():
    delta = RepositoryDelta(
        added=(),
        modified=(),
        deleted=(),
        unchanged=("a.py", "b.py"),
        hashes_computed=0,
        hashes_reused=2,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.to_parse == ()
    assert plan.to_delete == ()
    assert plan.to_reembed == ()
    assert plan.embedding_action is EmbeddingAction.REUSE
    assert plan.source_state_changed is False

def test_missing_trusted_index_forces_full_baseline():
    delta = RepositoryDelta(
        added=(),
        modified=(),
        deleted=(),
        unchanged=("a.py", "b.py"),
        hashes_computed=0,
        hashes_reused=2,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=False,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.force_full_reindex is True
    assert plan.reset_index_scope is True
    assert plan.to_parse == ("a.py", "b.py")
    assert plan.force_reindex_reason == "trusted_index_missing"

def test_same_dimension_drift_reembeds_unchanged_only():
    delta = RepositoryDelta(
        added=(),
        modified=(),
        deleted=(),
        unchanged=("stable.py",),
        hashes_computed=0,
        hashes_reused=1,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.SAME_DIMENSION_DRIFT
        ),
    )

    assert plan.to_parse == ()
    assert plan.to_reembed == ("stable.py",)
    assert plan.embedding_action is (
        EmbeddingAction.REEMBED_UNCHANGED
    )

def test_same_dimension_drift_with_changed_and_unchanged_files():
    delta = RepositoryDelta(
        added=("new.py",),
        modified=("changed.py",),
        deleted=(),
        unchanged=("stable.py",),
        hashes_computed=2,
        hashes_reused=1,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.SAME_DIMENSION_DRIFT
        ),
    )

    assert plan.to_parse == ("changed.py", "new.py")
    assert plan.to_reembed == ("stable.py",)
    assert plan.embedding_action is (
        EmbeddingAction
        .COMPUTE_CHANGED_AND_REEMBED_UNCHANGED
    )

def test_same_dimension_drift_with_only_changed_files():
    delta = RepositoryDelta(
        added=(),
        modified=("changed.py",),
        deleted=(),
        unchanged=(),
        hashes_computed=1,
        hashes_reused=0,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.SAME_DIMENSION_DRIFT
        ),
    )

    assert plan.to_parse == ("changed.py",)
    assert plan.to_reembed == ()
    assert plan.embedding_action is (
        EmbeddingAction.COMPUTE_CHANGED
    )

def test_incompatible_dimension_blocks_execution():
    delta = RepositoryDelta(
        added=("a.py",),
        modified=(),
        deleted=(),
        unchanged=(),
        hashes_computed=1,
        hashes_reused=0,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.INCOMPATIBLE_DIMENSION
        ),
    )

    assert plan.blocked_reason == (
        "embedding_dimension_incompatible"
    )
    assert plan.to_parse == ()
    assert plan.to_delete == ()

def test_database_unavailable_returns_no_executable_work():
    delta = RepositoryDelta(
        added=("a.py",),
        modified=(),
        deleted=("old.py",),
        unchanged=(),
        hashes_computed=1,
        hashes_reused=0,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=False,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.blocked_reason == "database_unavailable"
    assert plan.embedding_action is EmbeddingAction.BLOCKED
    assert plan.to_parse == ()
    assert plan.to_delete == ()
    assert plan.to_reembed == ()

def test_provider_off_parses_changes_without_embedding():
    delta = RepositoryDelta(
        added=("a.py",),
        modified=(),
        deleted=(),
        unchanged=("b.py",),
        hashes_computed=1,
        hashes_reused=1,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=EmbeddingCompatibility.OFF,
    )

    assert plan.to_parse == ("a.py",)
    assert plan.embedding_action is EmbeddingAction.DISABLED
    assert plan.blocked_reason == ""

def test_policy_change_alone_does_not_force_full_reindex():
    delta = RepositoryDelta(
        added=(),
        modified=(),
        deleted=(),
        unchanged=("a.py",),
        hashes_computed=0,
        hashes_reused=1,
        policy_changed=True,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.force_full_reindex is False
    assert plan.to_parse == ()
    assert plan.embedding_action is EmbeddingAction.REUSE

def test_explicit_force_reindexes_all_current_files():
    delta = RepositoryDelta(
        added=("new.py",),
        modified=(),
        deleted=("old.py",),
        unchanged=("stable.py",),
        hashes_computed=1,
        hashes_reused=1,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
        force_full_reindex=True,
    )

    assert plan.force_full_reindex is True
    assert plan.reset_index_scope is True
    assert plan.to_parse == ("new.py", "stable.py")
    assert plan.to_delete == ("old.py",)
    assert plan.force_reindex_reason == "explicit_force_reindex"
    
def test_deleted_only_delta_does_not_parse_files():
    delta = RepositoryDelta(
        added=(),
        modified=(),
        deleted=("old.py",),
        unchanged=("stable.py",),
        hashes_computed=0,
        hashes_reused=1,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.to_parse == ()
    assert plan.to_delete == ("old.py",)
    assert plan.embedding_action is EmbeddingAction.REUSE
    assert plan.source_state_changed is True

def test_plan_outputs_are_deterministically_sorted():
    delta = RepositoryDelta(
        added=("z.py", "a.py"),
        modified=("m.py", "b.py"),
        deleted=("y.py", "c.py"),
        unchanged=("x.py", "d.py"),
        hashes_computed=4,
        hashes_reused=2,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.added == ("a.py", "z.py")
    assert plan.modified == ("b.py", "m.py")
    assert plan.deleted == ("c.py", "y.py")
    assert plan.unchanged == ("d.py", "x.py")
    assert plan.to_parse == (
        "a.py",
        "b.py",
        "m.py",
        "z.py",
    )

def test_added_and_modified_categories_remain_distinct():
    delta = RepositoryDelta(
        added=("same-name-new.py",),
        modified=("same-name-existing.py",),
        deleted=(),
        unchanged=(),
        hashes_computed=2,
        hashes_reused=0,
        policy_changed=False,
    )

    plan = build_index_execution_plan(
        delta,
        trusted_index_exists=True,
        database_available=True,
        embedding_compatibility=(
            EmbeddingCompatibility.COMPATIBLE
        ),
    )

    assert plan.added == ("same-name-new.py",)
    assert plan.modified == ("same-name-existing.py",)
    assert plan.to_parse == (
        "same-name-existing.py",
        "same-name-new.py",
    )