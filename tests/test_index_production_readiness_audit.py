"""INDEX.1E.1 characterization of shadow planning versus production truth.

Characterizes what ``core.indexer.index_repository`` actually does across
four consecutive runs (cold, no-change, one-file-modified, one-file-deleted)
against a small temporary repository, with the database, embeddings, and
graph parse layer replaced by counting fakes.

These tests document CURRENT production behavior, including inefficiency.
If production indexing later becomes incremental, the "full rework" numbers
asserted here are EXPECTED to change and the assertions should be updated
to the new (smaller) values — that is the point of a characterization test.

No real database, no real embedding provider, and no network. Tests seed only
fixture-owned applied manifests, then prove production loads but never advances
them while the existing full-processing path remains authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import pytest

import core.index_manifest as index_manifest_module
import core.index_execution as index_execution_module
import core.repo_librarian as repo_librarian_module
from core import indexer as indexer_module
from core import repository_identity
from core.repository_inventory import create_repository_inventory
from core.repository_identity_state import (
    DECISION_SAME_PROJECT,
    apply_human_identity_decision,
    initialize_repository_identity_state,
)


@dataclass
class RunCounters:
    files_read: int = 0
    files_parsed: int = 0
    graph_files_parsed: int = 0
    embeddings_generated: int = 0
    db_replacements: int = 0
    db_deletions: int = 0
    reconciliation_calls: int = 0
    repository_walks: int = 0
    dna_builds: int = 0
    graph_builds: int = 0
    manifest_loads: int = 0
    manifest_saves: int = 0
    delta_inspections: int = 0
    plans_built: int = 0
    replaced_files: list = field(default_factory=list)

    def reset(self) -> None:
        for name in vars(self):
            value = getattr(self, name)
            if isinstance(value, int):
                setattr(self, name, 0)
            elif isinstance(value, list):
                value.clear()


class _FakeEmbedding:
    def tolist(self):
        return [0.0, 1.0]


def _fake_parse(text: str, _language: str) -> dict:
    first_line = text.splitlines()[0] if text.splitlines() else "empty"
    return {
        "symbols": [{
            "kind": "function",
            "name": first_line.strip("# ") or "unit",
            "content": text,
            "execution_flow": "",
            "calls": [],
        }],
        "imports": [],
        "calls": [],
    }


def _write_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "audit_repo"
    repo.mkdir()
    (repo / "alpha.py").write_text("# alpha\nprint('a')\n", encoding="utf-8")
    (repo / "beta.py").write_text("# beta\nprint('b')\n", encoding="utf-8")
    (repo / "gamma.py").write_text("# gamma\nprint('c')\n", encoding="utf-8")
    return repo


def _confirmed_identity(repo: Path):
    confirmation = apply_human_identity_decision(
        initialize_repository_identity_state(repo),
        DECISION_SAME_PROJECT,
        confirmed_at="2026-07-28T06:00:00+00:00",
        confirmed_by="human",
        reason="Confirm identity for production shadow characterization.",
        confirmed_project_tag="audit-repo",
    )
    assert confirmation.valid, confirmation.errors
    return confirmation.state


def _seed_applied_manifest(repo: Path, identity_state) -> Path:
    inventory = create_repository_inventory(repo)
    manifest, _delta = index_manifest_module.inspect_repository_delta(
        str(repo),
        inventory=inventory,
        indexable_only=True,
        repository_id=identity_state.repository_id,
        architecture_epoch=identity_state.architecture_epoch,
        index_scope=identity_state.active_index_scope,
        embedding_signature=(
            index_manifest_module
            .build_current_index_embedding_signature()
        ),
    )
    return index_manifest_module.save_repository_manifest(
        str(repo),
        manifest,
    )


def _set_manifest_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        index_manifest_module,
        "AGENT_DIR",
        tmp_path / "manifest-artifacts",
    )


def _instrument(monkeypatch, tmp_path: Path) -> RunCounters:
    counters = RunCounters()
    _set_manifest_root(monkeypatch, tmp_path)

    real_extract = indexer_module.extract_file_text

    def counting_extract(file_path, repo_path=None, query=None):
        counters.files_read += 1
        return real_extract(file_path, repo_path=repo_path, query=query)

    def counting_parse(text, language):
        counters.files_parsed += 1
        return _fake_parse(text, language)

    def counting_graph_parse(text, language):
        counters.graph_files_parsed += 1
        return _fake_parse(text, language)

    def counting_embedding(_text):
        counters.embeddings_generated += 1
        return _FakeEmbedding()

    def counting_replace(*, file_path, index_scope, code_units, dependencies):
        counters.db_replacements += 1
        counters.replaced_files.append(file_path)
        return len(code_units)

    def counting_delete(*, file_path, index_scope):
        counters.db_deletions += 1
        return True

    def counting_reconcile(**_kwargs):
        counters.reconciliation_calls += 1
        return {"dependencies_deleted": 0, "code_units_deleted": 0}

    real_walk = repo_librarian_module._walk_policy_files

    def counting_walk(repo_path):
        counters.repository_walks += 1
        yield from real_walk(repo_path)

    def counting_dna(_repo_path, *, inventory=None):
        assert inventory is not None
        counters.dna_builds += 1
        return {
            "indent": "4space",
            "naming": "snake",
            "max_line_pref": 100,
        }

    real_graph_build = indexer_module.build_graph_from_repo

    def counting_graph_build(
        repo_path,
        *,
        inventory=None,
        repo_entries=None,
        repository_files=None,
    ):
        assert inventory is not None
        counters.graph_builds += 1
        return real_graph_build(
            repo_path,
            inventory=inventory,
            repo_entries=repo_entries,
            repository_files=repository_files,
        )

    real_manifest_load = (
        index_manifest_module.load_repository_manifest_result
    )

    def counting_manifest_load(repo_path, **kwargs):
        counters.manifest_loads += 1
        return real_manifest_load(repo_path, **kwargs)

    def counting_manifest_save(repo_path, manifest):
        counters.manifest_saves += 1
        raise AssertionError(
            "characterization must not persist a manifest"
        )

    real_delta = index_manifest_module.inspect_repository_delta

    def counting_delta(repo_path, **kwargs):
        counters.delta_inspections += 1
        return real_delta(repo_path, **kwargs)

    real_plan = index_execution_module.build_index_execution_plan

    def counting_plan(delta, **kwargs):
        counters.plans_built += 1
        return real_plan(delta, **kwargs)

    monkeypatch.setenv("INDEX_USE_EMBEDDINGS", "true")
    monkeypatch.setenv("BENCHMARK_SKIP_PHANTOM", "true")

    monkeypatch.setattr(indexer_module, "extract_file_text", counting_extract)
    monkeypatch.setattr(
        indexer_module, "parse_code_with_treesitter", counting_parse
    )
    monkeypatch.setattr(
        "graph.builder.parse_code_with_treesitter", counting_graph_parse
    )
    monkeypatch.setattr(indexer_module, "get_embedding", counting_embedding)
    monkeypatch.setattr(
        indexer_module, "code_index_db_enabled", lambda: True
    )
    monkeypatch.setattr(indexer_module, "init_db", lambda: None)
    monkeypatch.setattr(
        indexer_module, "replace_code_index_for_file", counting_replace
    )
    monkeypatch.setattr(
        "database.memory.delete_code_index_for_file",
        counting_delete,
    )
    monkeypatch.setattr(
        indexer_module, "reconcile_code_index_scope", counting_reconcile
    )
    monkeypatch.setattr(
        repo_librarian_module, "_walk_policy_files", counting_walk
    )
    monkeypatch.setattr(indexer_module, "compute_dna", counting_dna)
    monkeypatch.setattr(
        indexer_module,
        "save_dna",
        lambda _repo, _dna: tmp_path / "code_dna.json",
    )
    monkeypatch.setattr(
        indexer_module, "build_graph_from_repo", counting_graph_build
    )
    monkeypatch.setattr(
        indexer_module, "build_project_map",
        lambda _summaries, graph=None, repo_path=None, inventory=None: "map",
    )
    monkeypatch.setattr(
        indexer_module, "write_project_map",
        lambda _repo, _content: str(tmp_path / "project_map.md"),
    )
    monkeypatch.setattr(
        index_manifest_module,
        "load_repository_manifest_result",
        counting_manifest_load,
    )
    monkeypatch.setattr(
        index_manifest_module,
        "save_repository_manifest",
        counting_manifest_save,
    )
    monkeypatch.setattr(
        index_manifest_module,
        "inspect_repository_delta",
        counting_delta,
    )
    monkeypatch.setattr(
        index_execution_module,
        "build_index_execution_plan",
        counting_plan,
    )
    return counters


def _assert_full_rework(counters: RunCounters, expected_files: int) -> None:
    assert counters.files_read == expected_files
    assert counters.files_parsed == expected_files
    assert counters.graph_files_parsed == expected_files
    assert counters.embeddings_generated == expected_files
    assert counters.db_replacements == expected_files
    assert counters.db_deletions == 0
    assert counters.reconciliation_calls == 1
    assert counters.repository_walks == 1
    assert counters.dna_builds == 1
    assert counters.graph_builds == 1
    assert counters.manifest_loads == 1
    assert counters.manifest_saves == 0
    assert counters.delta_inspections == 1
    assert counters.plans_built == 1


def test_run_a_cold_baseline_processes_every_file(tmp_path, monkeypatch):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    counters = _instrument(monkeypatch, tmp_path)
    manifest_path = index_manifest_module.get_repository_manifest_path(
        str(repo)
    )
    assert not manifest_path.exists()

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    assert set(result) == {
        "repo_path",
        "project_tag",
        "index_scope",
        "files_processed",
        "symbols_stored",
        "code_index_reconciliation",
        "completion",
        "delta_shadow",
        "delta_execution",
        "project_map",
        "phantom_limb",
        "traversal_diagnostics",
    }
    assert set(result) - {"completion"} == {
        "repo_path",
        "project_tag",
        "index_scope",
        "files_processed",
        "symbols_stored",
        "code_index_reconciliation",
        "delta_shadow",
        "delta_execution",
        "project_map",
        "phantom_limb",
        "traversal_diagnostics",
    }
    assert result["files_processed"] == 3
    assert isinstance(result["completion"], dict)
    assert result["traversal_diagnostics"]["repository_walks"] == 1
    assert (
        result["traversal_diagnostics"]["inventory_reuse"]["manifest"]
        is True
    )
    _assert_full_rework(counters, expected_files=3)
    assert sorted(counters.replaced_files) == [
        "alpha.py", "beta.py", "gamma.py",
    ]
    shadow = result["delta_shadow"]
    assert shadow["mode"] == "shadow_only"
    assert shadow["authoritative"] is False
    assert shadow["status"] == "cold_build"
    assert shadow["manifest"] == {
        "load_status": "missing",
        "load_reason": "manifest_missing",
        "previous_applied_present": False,
        "artifact_present": False,
        "legacy_binding": False,
        "observed_built": True,
        "policy_changed": False,
        "previous_records_excluded": 0,
        "embedding_signature_status": "cold_build_no_existing_vectors",
        "baseline_kind": "cold_build",
    }
    assert shadow["delta"]["counts"] == {
        "added": 3,
        "modified": 0,
        "deleted": 0,
        "unchanged": 0,
    }
    assert shadow["delta"]["added"] == [
        "alpha.py",
        "beta.py",
        "gamma.py",
    ]
    assert shadow["plan"]["parse_actions"] == 3
    assert shadow["plan"]["embedding_actions"] == 3
    assert shadow["plan"]["replacement_actions"] == 3
    assert shadow["plan"]["deleted_file_actions"] == 0
    assert shadow["production_execution"]["actual"][
        "parsed_files"
    ] == 3
    assert shadow["production_execution"]["actual"][
        "embedded_files"
    ] == 3
    assert shadow["production_execution"]["actual"][
        "replacement_attempts"
    ] == 3
    assert shadow["production_execution"]["comparison"] == {
        "available": True,
        "matches_shadow_recommendation": True,
        "expected_shadow_only_mismatch": False,
        "unexpected_production_divergence": False,
        "operational_failure_observed": False,
        "shadow_plan_remains_valid": True,
        "deletion": {
            "planned_files": 0,
            "actual_direct_file_deletions": 0,
            "reconciliation_performed": True,
            "actual_code_units_deleted": 0,
            "actual_dependencies_deleted": 0,
            "strategy_matches": True,
            "path_parity_available": True,
        },
    }
    assert shadow["production_execution"]["still_full_processing"] is True
    assert shadow["production_execution"]["plan_controls_execution"] is False
    assert shadow["production_execution"]["manifest_saved"] is False
    assert not manifest_path.exists()


def test_run_b_no_change_skips_authoritative_work(tmp_path, monkeypatch):
    """A verified applied state authorizes only the zero-delta fast path."""
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, identity_state)
    before = manifest_path.read_bytes()
    counters = _instrument(monkeypatch, tmp_path)

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    assert counters.files_read == 0
    assert counters.files_parsed == 0
    assert counters.embeddings_generated == 0
    assert counters.db_replacements == 0
    assert counters.db_deletions == 0
    assert counters.reconciliation_calls == 0
    assert counters.repository_walks == 1
    shadow = result["delta_shadow"]
    assert shadow["manifest"]["load_status"] == "loaded"
    assert shadow["manifest"]["previous_applied_present"] is True
    assert shadow["manifest"]["observed_built"] is True
    assert shadow["delta"]["counts"] == {
        "added": 0,
        "modified": 0,
        "deleted": 0,
        "unchanged": 3,
    }
    assert shadow["plan"]["parse_actions"] == 0
    assert shadow["plan"]["embedding_actions"] == 0
    assert shadow["plan"]["replacement_actions"] == 0
    assert shadow["plan"]["deleted_file_actions"] == 0
    assert shadow["plan"]["unchanged_noop_recommendations"] == 3
    actual = shadow["production_execution"]["actual"]
    assert actual["parsed_files"] == 0
    assert actual["embedded_files"] == 0
    assert actual["replacement_attempts"] == 0
    execution = result["delta_execution"]
    assert execution["fast_path_taken"] is True
    assert execution["actual_work"] == {
        "content_reads": 0,
        "authoritative_index_parses": 0,
        "auxiliary_parses": 0,
        "parsed_files": 0,
        "embedded_files": 0,
        "replacement_calls": 0,
        "deletion_calls": 0,
        "reconciliation_calls": 0,
    }
    assert result["completion"]["persistence_required"] is False
    assert result["completion"]["persistence_attempted"] is False
    assert result["completion"]["persistence_ok"] is True
    assert result["completion"]["trusted_completion"] is True
    assert result["completion"]["current_claim_basis"] == (
        "verified_existing_applied_manifest"
    )
    assert execution["manifest_advanced"] is False
    assert manifest_path.read_bytes() == before


def test_run_c_single_modification_reworks_every_file(
    tmp_path, monkeypatch
):
    """CURRENT behavior: touching one file re-embeds and re-replaces all
    files, not just the modified one."""
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, identity_state)
    before = manifest_path.read_bytes()
    counters = _instrument(monkeypatch, tmp_path)

    (repo / "beta.py").write_text(
        "# beta v2\nprint('b2')\n", encoding="utf-8"
    )
    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    _assert_full_rework(counters, expected_files=3)
    assert counters.replaced_files.count("beta.py") == 1
    assert counters.replaced_files.count("alpha.py") == 1
    shadow = result["delta_shadow"]
    assert shadow["delta"]["counts"] == {
        "added": 0,
        "modified": 1,
        "deleted": 0,
        "unchanged": 2,
    }
    assert shadow["delta"]["modified"] == ["beta.py"]
    assert shadow["plan"]["parse_files"] == ["beta.py"]
    assert shadow["plan"]["embedding_files"] == ["beta.py"]
    assert shadow["plan"]["replacement_files"] == ["beta.py"]
    assert shadow["plan"]["unchanged_noop_files"] == [
        "alpha.py",
        "gamma.py",
    ]
    assert shadow["production_execution"]["comparison"][
        "expected_shadow_only_mismatch"
    ] is True
    assert shadow["production_execution"]["actual"][
        "replacement_attempts"
    ] == 3
    assert manifest_path.read_bytes() == before


def test_run_d_single_deletion_reworks_survivors_without_file_delete(
    tmp_path, monkeypatch
):
    """CURRENT behavior: deleting one file triggers full rework of the
    surviving files; the deletion itself is handled only by end-of-run
    scope reconciliation, never by delete_code_index_for_file."""
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, identity_state)
    before = manifest_path.read_bytes()
    counters = _instrument(monkeypatch, tmp_path)
    reconcile_args = []

    def capturing_reconcile(**kwargs):
        counters.reconciliation_calls += 1
        reconcile_args.append(kwargs)
        return {"dependencies_deleted": 0, "code_units_deleted": 0}

    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        capturing_reconcile,
    )

    (repo / "gamma.py").unlink()
    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    _assert_full_rework(counters, expected_files=2)
    assert counters.db_deletions == 0
    assert reconcile_args == [{
        "index_scope": identity_state.active_index_scope,
        "current_files": {"alpha.py", "beta.py"},
    }]
    assert "gamma.py" not in counters.replaced_files
    shadow = result["delta_shadow"]
    assert shadow["delta"]["counts"] == {
        "added": 0,
        "modified": 0,
        "deleted": 1,
        "unchanged": 2,
    }
    assert shadow["delta"]["deleted"] == ["gamma.py"]
    assert shadow["plan"]["parse_actions"] == 0
    assert shadow["plan"]["replacement_actions"] == 0
    assert shadow["plan"]["deleted_files"] == ["gamma.py"]
    assert shadow["production_execution"]["actual"][
        "direct_file_deletions"
    ] == 0
    assert shadow["production_execution"]["actual"][
        "reconciliation_performed"
    ] is True
    assert shadow["production_execution"]["comparison"][
        "expected_shadow_only_mismatch"
    ] is True
    assert manifest_path.read_bytes() == before


def test_mid_run_replacement_failure_is_explicit_and_latches_abort(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, identity_state)
    manifest_before = manifest_path.read_bytes()
    counters = _instrument(monkeypatch, tmp_path)
    (repo / "alpha.py").write_text("# alpha changed\n", encoding="utf-8")
    database_url = (
        "postgresql://index-user:index-password@"
        "db.example.test/cattus?token=index-token"
    )

    def fail_on_beta(
        *,
        file_path,
        index_scope,
        code_units,
        dependencies,
    ):
        del index_scope, dependencies
        counters.db_replacements += 1
        counters.replaced_files.append(file_path)
        if file_path == "beta.py":
            raise RuntimeError(
                f"replacement failed using {database_url}"
            )
        return len(code_units)

    monkeypatch.setattr(
        indexer_module,
        "replace_code_index_for_file",
        fail_on_beta,
    )

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )
    captured = capsys.readouterr()
    completion = result["completion"]
    outcomes = {
        item["file_path"]: item
        for item in completion["file_outcomes"]
    }
    rendered = json.dumps(completion, sort_keys=True)

    assert counters.files_read == 3
    assert counters.files_parsed == 3
    assert counters.embeddings_generated == 2
    assert counters.replaced_files == ["alpha.py", "beta.py"]
    assert counters.reconciliation_calls == 0
    assert completion["status"] == "persistence_failed"
    assert completion["failure_stage"] == "replacement"
    assert completion["failed_files"] == ["beta.py"]
    assert completion["persistence_aborted_after_failure"] is True
    assert completion["unattempted_required_files"] == ["gamma.py"]
    assert outcomes["alpha.py"]["persistence_status"] == "persisted"
    assert (
        outcomes["beta.py"]["persistence_status"]
        == "replacement_failed"
    )
    assert outcomes["gamma.py"]["persistence_status"] == "pending"
    assert result["code_index_reconciliation"] == {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": "file_replacement_failed",
    }
    assert database_url not in rendered
    assert "index-user" not in rendered
    assert "index-password" not in rendered
    assert "index-token" not in rendered
    assert database_url not in captured.out
    assert "index-user" not in captured.out
    assert "index-password" not in captured.out
    assert "index-token" not in captured.out
    assert manifest_path.read_bytes() == manifest_before


def test_mid_run_embedding_failure_has_independent_failure_stage(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, identity_state)
    manifest_before = manifest_path.read_bytes()
    counters = _instrument(monkeypatch, tmp_path)
    (repo / "alpha.py").write_text("# alpha changed\n", encoding="utf-8")
    embedding_calls: list[str] = []

    def fail_second_embedding(text):
        embedding_calls.append(text)
        counters.embeddings_generated += 1
        if "# beta" in text:
            raise RuntimeError("embedding provider unavailable")
        return _FakeEmbedding()

    monkeypatch.setattr(
        indexer_module,
        "get_embedding",
        fail_second_embedding,
    )

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )
    completion = result["completion"]

    assert len(embedding_calls) == 2
    assert counters.replaced_files == ["alpha.py"]
    assert counters.reconciliation_calls == 0
    assert completion["status"] == "persistence_failed"
    assert completion["failure_stage"] == "embedding"
    assert completion["failed_files"] == ["beta.py"]
    assert completion["unattempted_required_files"] == ["gamma.py"]
    assert manifest_path.read_bytes() == manifest_before


def test_reconciliation_failure_never_advances_applied_manifest(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, identity_state)
    manifest_before = manifest_path.read_bytes()
    counters = _instrument(monkeypatch, tmp_path)
    (repo / "alpha.py").write_text("# alpha changed\n", encoding="utf-8")

    def fail_reconciliation(**_kwargs):
        counters.reconciliation_calls += 1
        raise RuntimeError("reconciliation fixture failure")

    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        fail_reconciliation,
    )

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    assert result["completion"]["status"] == "reconciliation_failed"
    assert result["completion"]["manifest_advance_allowed"] is False
    assert result["delta_shadow"]["production_execution"][
        "manifest_saved"
    ] is False
    assert manifest_path.read_bytes() == manifest_before


def test_persistence_disabled_never_advances_applied_manifest(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, identity_state)
    manifest_before = manifest_path.read_bytes()
    _instrument(monkeypatch, tmp_path)
    monkeypatch.setattr(
        indexer_module,
        "code_index_db_enabled",
        lambda: False,
    )

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    assert result["completion"]["status"] == "persistence_disabled"
    assert result["completion"]["manifest_advance_allowed"] is False
    assert (
        result["delta_shadow"]["production_execution"][
            "persistence_enabled"
        ]
        is False
    )
    assert manifest_path.read_bytes() == manifest_before


def test_identity_blocked_run_never_advances_applied_manifest(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    confirmed = _confirmed_identity(repo)
    blocked = initialize_repository_identity_state(repo)
    _set_manifest_root(monkeypatch, tmp_path)
    manifest_path = _seed_applied_manifest(repo, confirmed)
    manifest_before = manifest_path.read_bytes()
    _instrument(monkeypatch, tmp_path)

    result = indexer_module.index_repository(
        str(repo),
        identity_state=blocked,
    )

    assert result["completion"]["status"] == "identity_blocked"
    assert result["completion"]["manifest_advance_allowed"] is False
    assert result["delta_shadow"]["plan"]["status"] == "identity_blocked"
    assert result["delta_shadow"]["authoritative"] is False
    assert manifest_path.read_bytes() == manifest_before


@pytest.mark.parametrize(
    ("rejection_attempt", "expected_files_read"),
    (
        pytest.param(1, 2, id="pre-read-revalidation"),
        pytest.param(2, 3, id="post-read-revalidation"),
    ),
)
def test_post_inventory_unsafe_entry_is_a_processing_failure(
    tmp_path,
    monkeypatch,
    rejection_attempt,
    expected_files_read,
):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    counters = _instrument(monkeypatch, tmp_path)
    inventory = create_repository_inventory(repo)
    real_is_safe_path = indexer_module.is_safe_path
    beta_safety_checks = 0

    def reject_beta_after_inventory(file_path, allowed_roots=None):
        nonlocal beta_safety_checks
        if Path(file_path).name == "beta.py":
            beta_safety_checks += 1
            if beta_safety_checks == rejection_attempt:
                return False
        return real_is_safe_path(
            file_path,
            allowed_roots=allowed_roots,
        )

    monkeypatch.setattr(
        indexer_module,
        "is_safe_path",
        reject_beta_after_inventory,
    )

    result = indexer_module.index_repository(
        str(repo),
        inventory=inventory,
        identity_state=identity_state,
    )

    assert counters.repository_walks == 1
    assert result["files_processed"] == 2
    assert counters.files_read == expected_files_read
    assert counters.files_parsed == 2
    assert counters.db_replacements == 2
    assert counters.reconciliation_calls == 0
    assert result["code_index_reconciliation"] == {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": "processing_failed",
    }

    completion = result["completion"]
    outcomes = {
        item["file_path"]: item
        for item in completion["file_outcomes"]
    }
    assert completion["status"] == "processing_failed"
    assert completion["failed_files"] == ["beta.py"]
    assert completion["trusted_completion"] is False
    assert completion["manifest_advance_allowed"] is False
    assert outcomes["beta.py"]["processing_status"] == "parse_failed"
    assert outcomes["beta.py"]["error_category"] == (
        "inventory_entry_unsafe"
    )
    assert (
        result["delta_shadow"]["production_execution"]["actual"][
            "reconciliation_performed"
        ]
        is False
    )


def test_invalid_manifest_does_not_interrupt_full_production_work(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    counters = _instrument(monkeypatch, tmp_path)
    manifest_path = index_manifest_module.get_repository_manifest_path(repo)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(b"{broken manifest")
    manifest_before = manifest_path.read_bytes()

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    assert result["files_processed"] == 3
    assert counters.files_read == 3
    assert counters.files_parsed == 3
    assert counters.embeddings_generated == 3
    assert counters.db_replacements == 3
    assert counters.reconciliation_calls == 1
    assert counters.manifest_loads == 1
    assert counters.delta_inspections == 1
    assert counters.plans_built == 0

    shadow = result["delta_shadow"]
    assert shadow["status"] == "manifest_invalid"
    assert shadow["manifest"]["load_status"] == "invalid"
    assert shadow["manifest"]["load_reason"] == "manifest_json_invalid"
    assert shadow["manifest"]["observed_built"] is True
    assert shadow["delta"]["available"] is False
    assert shadow["plan"]["status"] == "planner_unavailable"
    assert shadow["plan"]["future_executable_candidate"] is False
    assert shadow["production_execution"]["actual"]["parsed_files"] == 3
    assert shadow["production_execution"]["actual"]["embedded_files"] == 3
    assert (
        shadow["production_execution"]["actual"][
            "replacement_attempts"
        ]
        == 3
    )
    assert (
        shadow["production_execution"]["comparison"]["available"]
        is False
    )
    assert manifest_path.read_bytes() == manifest_before


def test_database_initialization_failure_downgrades_shadow_and_continues(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    identity_state = _confirmed_identity(repo)
    counters = _instrument(monkeypatch, tmp_path)

    def fail_initialization():
        raise RuntimeError("database initialization fixture failed")

    monkeypatch.setattr(
        indexer_module,
        "init_db",
        fail_initialization,
    )

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
    )

    assert result["files_processed"] == 3
    assert counters.files_read == 3
    assert counters.files_parsed == 3
    assert counters.embeddings_generated == 0
    assert counters.db_replacements == 0
    assert counters.reconciliation_calls == 0
    completion = result["completion"]
    assert completion["status"] == "persistence_failed"
    assert completion["failure_stage"] == "initialization"
    assert completion["manifest_advance_allowed"] is False

    shadow = result["delta_shadow"]
    assert shadow["status"] == "planner_unavailable"
    assert shadow["manifest"]["load_status"] == "missing"
    assert shadow["manifest"]["observed_built"] is True
    assert shadow["delta"]["available"] is True
    assert shadow["plan"]["status"] == "planner_unavailable"
    assert shadow["plan"]["runtime_blocked_reason"] == (
        "database_initialization_failed"
    )
    assert shadow["plan"]["future_executable_candidate"] is False
    assert (
        shadow["production_execution"]["database_available"]
        is False
    )
    assert (
        shadow["production_execution"]["comparison"][
            "operational_failure_observed"
        ]
        is True
    )
    assert (
        shadow["production_execution"]["comparison"][
            "unexpected_production_divergence"
        ]
        is True
    )
    assert "database_initialization_failed" in shadow["warnings"]


def test_code_dna_write_failure_is_explicit_auxiliary_warning(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    _instrument(monkeypatch, tmp_path)
    confirmation = apply_human_identity_decision(
        initialize_repository_identity_state(repo),
        DECISION_SAME_PROJECT,
        confirmed_at="2026-07-28T06:00:00+00:00",
        confirmed_by="human",
        reason="Confirm identity for auxiliary-output evidence.",
        confirmed_project_tag="audit-repo",
    )
    assert confirmation.valid, confirmation.errors
    identity_state = confirmation.state
    monkeypatch.setattr(
        repository_identity,
        "build_code_index_scope",
        lambda _repo_path: identity_state.active_index_scope,
    )
    monkeypatch.setattr(
        indexer_module,
        "save_dna",
        lambda _repo, _dna: None,
    )

    result = indexer_module.index_repository(
        str(repo),
        identity_state=identity_state,
        completion_run_id="dna-warning-run",
        observed_state_id="dna-warning-state",
    )
    completion_block = result["completion"]
    auxiliary = {
        item["component"]: item
        for item in completion_block["auxiliary_outcomes"]
    }

    assert completion_block["status"] == "complete_with_warnings"
    assert completion_block["trusted_completion"] is True
    assert completion_block["manifest_advance_allowed"] is True
    assert completion_block["trusted_current_claim_allowed"] is False
    assert auxiliary["code_dna"] == {
        "component": "code_dna",
        "authority": "auxiliary_output",
        "attempted": True,
        "ok": False,
        "error_category": "code_dna_write_failed",
        "error_message": "Code DNA output was not written",
    }
