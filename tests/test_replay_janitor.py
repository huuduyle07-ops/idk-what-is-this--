"""Tests for Phase 13R.4 read-only replay janitor dry-run planning."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.replay_janitor import (
    CONFIRM_TOKEN,
    GUARDRAIL_NOTE,
    ReplayCleanupResult,
    ReplayJanitorPlan,
    _rmtree_contained,
    apply_replay_cleanup,
    format_replay_janitor_markdown,
    plan_replay_cleanup,
)
from core.replay_recorder import create_replay_bundle, write_replay_artifact


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _entry(plan: ReplayJanitorPlan, replay_id: str):
    for item in plan.entries:
        if item.replay_id == replay_id:
            return item
    raise AssertionError(f"missing entry for {replay_id}")


def _make_bundle(repo: Path, run_kind: str, created: datetime):
    return create_replay_bundle(repo, run_kind=run_kind, now=created)


def test_newest_bundles_are_kept_under_max_keep(tmp_path):
    repo = _repo(tmp_path)
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    oldest = _make_bundle(repo, "a", base)
    middle = _make_bundle(repo, "b", base + timedelta(seconds=1))
    newest = _make_bundle(repo, "c", base + timedelta(seconds=2))

    plan = plan_replay_cleanup(repo, max_keep=2, now=base + timedelta(seconds=3))

    assert _entry(plan, newest.replay_id).classification == "keep"
    assert _entry(plan, middle.replay_id).classification == "keep"
    assert _entry(plan, oldest.replay_id).classification == "cleanup_candidate"
    assert plan.keep_count == 2
    assert plan.cleanup_count == 1


def test_old_bundles_become_cleanup_candidates(tmp_path):
    repo = _repo(tmp_path)
    now = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    old = _make_bundle(repo, "old", now - timedelta(days=30))
    recent = _make_bundle(repo, "recent", now - timedelta(hours=1))

    plan = plan_replay_cleanup(repo, max_age_days=7, now=now)

    assert _entry(plan, old.replay_id).classification == "cleanup_candidate"
    assert _entry(plan, old.replay_id).reason == "too_old"
    assert _entry(plan, recent.replay_id).classification == "keep"


def test_pinned_bundles_are_always_kept(tmp_path):
    repo = _repo(tmp_path)
    now = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    old = _make_bundle(repo, "old", now - timedelta(days=30))
    recent = _make_bundle(repo, "recent", now - timedelta(hours=1))

    plan = plan_replay_cleanup(
        repo,
        max_age_days=7,
        max_keep=1,
        pinned_ids=[old.replay_id],
        now=now,
    )

    entry = _entry(plan, old.replay_id)
    assert entry.classification == "keep"
    assert entry.reason == "pinned"
    assert entry.pinned is True
    assert _entry(plan, recent.replay_id).classification == "keep"


def test_unreadable_or_invalid_bundles_reported_safely(tmp_path):
    repo = _repo(tmp_path)
    good = _make_bundle(repo, "good", datetime(2026, 1, 1, tzinfo=timezone.utc))
    root = repo / ".agent" / "replays"
    # A bundle directory with no manifest at all.
    (root / "20260101_000000_nomanifst").mkdir()
    # A bundle directory with a corrupt manifest.
    corrupt_dir = root / "20260102_000000_corrupted"
    corrupt_dir.mkdir()
    (corrupt_dir / "replay_manifest.json").write_text("{not json", encoding="utf-8")

    plan = plan_replay_cleanup(repo, now=datetime(2026, 6, 1, tzinfo=timezone.utc))

    assert _entry(plan, good.replay_id).classification == "keep"
    assert (
        _entry(plan, "20260101_000000_nomanifst").classification
        == "invalid_or_unreadable"
    )
    assert (
        _entry(plan, "20260102_000000_corrupted").classification
        == "invalid_or_unreadable"
    )
    assert plan.invalid_count == 2


def test_include_invalid_marks_invalid_as_cleanup_candidate(tmp_path):
    repo = _repo(tmp_path)
    _make_bundle(repo, "good", datetime(2026, 1, 1, tzinfo=timezone.utc))
    root = repo / ".agent" / "replays"
    (root / "20260101_000000_nomanifst").mkdir()

    plan = plan_replay_cleanup(
        repo,
        include_invalid=True,
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    entry = _entry(plan, "20260101_000000_nomanifst")
    assert entry.classification == "cleanup_candidate"
    assert entry.reason == "invalid_included"


def test_dry_run_does_not_delete_or_mutate_anything(tmp_path):
    repo = _repo(tmp_path)
    bundle = _make_bundle(repo, "a", datetime(2026, 1, 1, tzinfo=timezone.utc))
    write_replay_artifact(bundle, "model_prompt.txt", "prompt\n")
    root = repo / ".agent" / "replays"

    before = {
        path: path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }

    plan_replay_cleanup(repo, max_age_days=0, max_keep=0, include_invalid=True,
                        now=datetime(2026, 6, 1, tzinfo=timezone.utc))

    after = {
        path: path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert bundle.replay_dir.is_dir()


def test_traversal_pinned_id_is_rejected(tmp_path):
    repo = _repo(tmp_path)

    with pytest.raises(ValueError, match="invalid"):
        plan_replay_cleanup(repo, pinned_ids=["../escape"])


def test_missing_replays_dir_returns_empty_plan(tmp_path):
    repo = _repo(tmp_path)

    plan = plan_replay_cleanup(repo)

    assert plan.entries == []
    assert plan.keep_count == 0
    assert plan.cleanup_count == 0
    assert plan.invalid_count == 0


def test_markdown_includes_guardrail_note_and_entries(tmp_path):
    repo = _repo(tmp_path)
    bundle = _make_bundle(repo, "a", datetime(2026, 1, 1, tzinfo=timezone.utc))

    plan = plan_replay_cleanup(repo, now=datetime(2026, 6, 1, tzinfo=timezone.utc))
    markdown = format_replay_janitor_markdown(plan)

    assert "# Replay Janitor Dry-Run" in markdown
    assert GUARDRAIL_NOTE in markdown
    assert bundle.replay_id in markdown
    assert "Dry-run only" in markdown


def test_replay_janitor_ast_guard_minimal_deletion_primitive():
    # 13R.5: the janitor may now delete bundles, but only through the single
    # contained rmtree primitive. Everything else dangerous stays forbidden.
    tree = ast.parse(Path("core/replay_janitor.py").read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "database",
        "docker",
        "google",
        "openai",
        "requests",
        "httpx",
        "subprocess",
    }
    forbidden_calls = {
        "ChatCompletion",
        "Popen",
        "apply_patch_plan",
        "check_call",
        "check_output",
        "commit",
        "execute",
        "executemany",
        "from_env",
        "generate_content",
        "mkdir",
        "remove",
        "removedirs",
        "rmdir",
        "run_benchmark",
        "run_benchmarks",
        "run_deepseek_review",
        "run_gemini_request",
        "run_patch_plan_with_artifacts",
        "run_validation_command",
        "start_overnight_async",
        "system",
        "unlink",
        "write_bytes",
        "write_text",
    }

    assert {name.split(".", 1)[0] for name in imports}.isdisjoint(forbidden_import_roots)
    assert calls.isdisjoint(forbidden_calls)
    # The one allowed deletion primitive is present and confined to a helper.
    assert "rmtree" in calls


# --- Phase 13R.5: apply gate ------------------------------------------------


def test_apply_without_confirmation_deletes_nothing(tmp_path):
    repo = _repo(tmp_path)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    keep = _make_bundle(repo, "keep", base + timedelta(seconds=1))
    drop = _make_bundle(repo, "drop", base)

    result = apply_replay_cleanup(
        repo, max_keep=1, now=base + timedelta(seconds=2)
    )

    assert isinstance(result, ReplayCleanupResult)
    assert result.confirmed is False
    assert result.deleted == []
    assert drop.replay_id in result.blocked
    assert keep.replay_dir.is_dir()
    assert drop.replay_dir.is_dir()


def test_apply_with_confirmation_deletes_only_cleanup_candidates(tmp_path):
    repo = _repo(tmp_path)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    keep = _make_bundle(repo, "keep", base + timedelta(seconds=1))
    drop = _make_bundle(repo, "drop", base)

    result = apply_replay_cleanup(
        repo,
        confirm=CONFIRM_TOKEN,
        max_keep=1,
        now=base + timedelta(seconds=2),
    )

    assert result.confirmed is True
    assert result.deleted == [drop.replay_id]
    assert drop.replay_id not in result.skipped
    assert not drop.replay_dir.exists()
    assert keep.replay_dir.is_dir()
    assert keep.replay_id in result.skipped


def test_apply_never_deletes_pinned(tmp_path):
    repo = _repo(tmp_path)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pinned = _make_bundle(repo, "pinned", base)
    _make_bundle(repo, "newer", base + timedelta(seconds=1))

    result = apply_replay_cleanup(
        repo,
        confirm=CONFIRM_TOKEN,
        max_keep=1,
        pinned_ids=[pinned.replay_id],
        now=base + timedelta(seconds=2),
    )

    assert pinned.replay_id not in result.deleted
    assert pinned.replay_dir.is_dir()


def test_apply_never_deletes_keep_bundles(tmp_path):
    repo = _repo(tmp_path)
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    recent = _make_bundle(repo, "recent", base - timedelta(hours=1))

    result = apply_replay_cleanup(
        repo, confirm=CONFIRM_TOKEN, max_age_days=7, now=base
    )

    assert recent.replay_id not in result.deleted
    assert recent.replay_dir.is_dir()


def test_apply_does_not_delete_invalid_bundles_by_default(tmp_path):
    repo = _repo(tmp_path)
    _make_bundle(repo, "good", datetime(2026, 1, 1, tzinfo=timezone.utc))
    root = repo / ".agent" / "replays"
    invalid_dir = root / "20260101_000000_nomanifst"
    invalid_dir.mkdir()

    result = apply_replay_cleanup(
        repo,
        confirm=CONFIRM_TOKEN,
        max_age_days=0,
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    assert "20260101_000000_nomanifst" not in result.deleted
    assert invalid_dir.is_dir()


def test_apply_containment_guard_blocks_outside_paths(tmp_path):
    repo = _repo(tmp_path)
    root = repo / ".agent" / "replays"
    root.mkdir(parents=True)
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (outside / "keep.txt").write_text("safe", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes"):
        _rmtree_contained(root, outside)

    assert outside.is_dir()
    assert (outside / "keep.txt").is_file()


def test_apply_containment_guard_refuses_replays_root(tmp_path):
    repo = _repo(tmp_path)
    root = repo / ".agent" / "replays"
    root.mkdir(parents=True)

    with pytest.raises(ValueError, match="root"):
        _rmtree_contained(root, root)

    assert root.is_dir()


def test_apply_rejects_traversal_replay_id(tmp_path):
    repo = _repo(tmp_path)

    with pytest.raises(ValueError, match="invalid"):
        apply_replay_cleanup(repo, confirm=CONFIRM_TOKEN, pinned_ids=["../escape"])


def test_apply_is_idempotent(tmp_path):
    repo = _repo(tmp_path)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _make_bundle(repo, "keep", base + timedelta(seconds=1))
    drop = _make_bundle(repo, "drop", base)

    first = apply_replay_cleanup(
        repo, confirm=CONFIRM_TOKEN, max_keep=1, now=base + timedelta(seconds=2)
    )
    second = apply_replay_cleanup(
        repo, confirm=CONFIRM_TOKEN, max_keep=1, now=base + timedelta(seconds=2)
    )

    assert first.deleted == [drop.replay_id]
    assert second.deleted == []
    assert second.errors == []


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names
