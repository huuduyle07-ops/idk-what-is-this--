from __future__ import annotations

from pathlib import Path

from web.patch_helpers import (
    backup_key_for_path,
    detect_patch_language,
    detect_repo_language,
    patch_plan_files,
)


def test_detect_repo_language_prefers_repo_markers(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"demo\"\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")

    assert detect_repo_language(tmp_path) == "rust"


def test_detect_repo_language_handles_known_project_types(tmp_path):
    cases = [
        ("go.mod", "go"),
        ("package.json", "javascript"),
        ("src/app.py", "python"),
        ("src/App.csproj", "csharp"),
        ("src/main.cpp", "cpp"),
    ]

    for file_name, expected in cases:
        repo = tmp_path / expected
        path = repo / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

        assert detect_repo_language(repo) == expected


def test_detect_repo_language_returns_unknown_for_unrecognized_repo(tmp_path):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    assert detect_repo_language(tmp_path) == "unknown"


def test_patch_plan_files_preserves_existing_target_extraction_behavior():
    plan = [
        {"relative_path": "src/a.py", "file": "fallback.py"},
        {"file": "src/b.py"},
        {"relative_path": ""},
        "not-an-op",
        {"op": "noop"},
    ]

    assert patch_plan_files(plan) == ["src/a.py", "src/b.py", "", ""]


def test_detect_patch_language_uses_target_extension():
    assert detect_patch_language({"relative_path": "src/app.py"}) == "python"
    assert detect_patch_language({"file": "src/main.rs"}) == "rust"
    assert detect_patch_language({"relative_path": "README.unknown"}) == "unknown"


def test_backup_key_for_path_matches_legacy_naming():
    assert backup_key_for_path("src/app.py") == "src_app.py"
    assert backup_key_for_path("src\\app.py") == "src_app.py"
