from __future__ import annotations

from core.harness_modes import decide_harness_mode, format_harness_deny_message


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


def test_codespaces_windows_repo_path_blocks_before_source_missing():
    repo_path = r"C:\Users\Admin\Documents\Code\day 14\AI project\app.py"

    decision = decide_harness_mode(
        repo_root=repo_path,
        runtime_environment="codespaces",
        request_path=repo_path,
        source_text="",
    )

    assert decision.mode == "codespaces_local_path_mismatch"
    assert decision.can_generate_patch is False
    assert decision.can_apply_patch is False
    assert decision.evidence["request_path"] == repo_path
    assert "source_missing" not in decision.reason


def test_codespaces_embedded_windows_repo_path_blocks_before_source_missing():
    repo_path = r"/workspaces/idk-what-is-this--/C:\Users\Admin\project\app.py"

    decision = decide_harness_mode(
        repo_root=repo_path,
        runtime_environment="codespaces",
        request_path=repo_path,
        source_text="",
    )

    assert decision.mode == "codespaces_local_path_mismatch"
    assert decision.evidence["detected_path_environment"] == "local_windows"


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


def test_codespaces_windows_path_formats_hard_deny_message(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    requested_path = r"C:\Users\Administrator\Desktop\ml-data\app.py"

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="codespaces",
        request_path=requested_path,
        source_text="print('hello')",
    )

    message = format_harness_deny_message(decision)

    assert message.startswith("Cannot run: environment/path mismatch.")
    assert "C.A.T.T.U.S is running in: GitHub Codespaces" in message
    assert "Requested path looks like: Local Windows" in message
    assert f"Active repo root:\n{repo.resolve()}" in message
    assert f"Requested path:\n{requested_path}" in message
    assert "GitHub Codespaces cannot access files on your Windows computer." in message
    assert (
        "Open/copy the repo inside /workspaces/... or run C.A.T.T.U.S locally on Windows."
        in message
    )
    assert "Gemini was not called." in message
    assert "C.A.T.T.U.S will not guess" in message
    assert "How to fix:" in message


def test_local_linux_windows_path_formats_environment_mismatch_deny(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    requested_path = r"C:\Users\Admin\project\app.py"

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="local_linux",
        request_path=requested_path,
        source_text="print('hello')",
    )

    message = format_harness_deny_message(decision)

    assert decision.mode == "path_outside_repo"
    assert "Cannot run: environment/path mismatch." in message
    assert "C.A.T.T.U.S is running in: Local Ubuntu/Linux" in message
    assert "Requested path looks like: Local Windows" in message
    assert "Local Ubuntu/Linux cannot access a Local Windows absolute path." in message


def test_path_outside_repo_deny_includes_repo_root_and_requested_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="local_windows",
        target_path=str(outside),
        source_text="print('hello')",
    )

    message = format_harness_deny_message(decision)

    assert "Cannot run:" in message
    assert f"Active repo root:\n{repo.resolve()}" in message
    assert f"Requested path:\n{outside}" in message
    assert "The requested path is outside the active repo root." in message


def test_normal_patch_has_no_hard_deny_message(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    decision = decide_harness_mode(
        repo_root=repo,
        runtime_environment="local_windows",
        target_path="app.py",
        source_text="print('hello')",
    )

    assert decision.mode == "normal_patch"
    assert format_harness_deny_message(decision) == ""
