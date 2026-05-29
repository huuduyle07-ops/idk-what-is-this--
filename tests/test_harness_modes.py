from __future__ import annotations

from core.harness_modes import decide_harness_mode


def test_normal_local_repo_path_returns_normal_patch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="local_windows",
        target_path="app.py",
        source_text="print('hello')",
    )

    assert decision.mode == "normal_patch"
    assert decision.can_generate_patch is True
    assert decision.can_apply_patch is True


def test_outside_repo_path_blocks_generation_and_apply(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="local_linux",
        target_path=str(outside),
        source_text="print('hello')",
    )

    assert decision.mode == "path_outside_repo"
    assert decision.can_generate_patch is False
    assert decision.can_apply_patch is False


def test_codespaces_windows_absolute_path_blocks_with_specific_mode(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="codespaces",
        request_path=r"C:\Users\Admin\project\app.py",
        source_text="print('hello')",
    )

    assert decision.mode == "codespaces_local_path_mismatch"
    assert decision.can_generate_patch is False
    assert decision.can_apply_patch is False
    assert (
        "Codespaces can only patch files inside the Codespaces workspace."
        in decision.warnings
    )


def test_missing_source_blocks_generation_and_apply(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="local_macos",
        target_path="app.py",
        source_text="",
    )

    assert decision.mode == "source_missing"
    assert decision.can_generate_patch is False
    assert decision.can_apply_patch is False


def test_ungrounded_patch_blocks_generation_and_apply(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="local_linux",
        target_path="app.py",
        source_text="print('hello')",
        grounding_failed=True,
    )

    assert decision.mode == "ungrounded_patch_blocked"
    assert decision.can_generate_patch is False
    assert decision.can_apply_patch is False


def test_degraded_context_with_source_allows_generation_and_gate_dependent_apply(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="docker",
        target_path="app.py",
        source_text="print('hello')",
        index_degraded=True,
        patch_gates_passed=True,
    )

    assert decision.mode == "degraded_context"
    assert decision.can_generate_patch is True
    assert decision.can_apply_patch is True
    assert decision.warnings


def test_result_includes_human_readable_reason_warnings_and_evidence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="codespaces",
        request_path=r"C:\Users\Admin\project\app.py",
        source_text="print('hello')",
    )
    data = decision.to_dict()

    assert "Codespaces" in data["reason"]
    assert data["warnings"]
    assert data["evidence"]["runtime_environment"] == "codespaces"
    assert data["evidence"]["request_path"] == r"C:\Users\Admin\project\app.py"
