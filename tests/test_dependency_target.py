from pathlib import Path

import pytest

from core.dependency_target import resolve_dependency_target


def test_python_absolute_module_resolves_file(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="pkg/app.py",
        language="python",
        raw_target="pkg.shared",
        repository_files={
            "pkg/app.py",
            "pkg/shared.py",
        },
    )

    assert result.target_file == "pkg/shared.py"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "python_module"


def test_python_relative_module_resolves_file(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="pkg/features/app.py",
        language="python",
        raw_target="from ..shared import value",
        repository_files={
            "pkg/features/app.py",
            "pkg/shared.py",
        },
    )

    assert result.target_file == "pkg/shared.py"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "python_relative_module"


def test_python_from_dot_import_resolves_sibling(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="pkg/app.py",
        language="python",
        raw_target="from . import helpers",
        repository_files={
            "pkg/app.py",
            "pkg/helpers.py",
        },
    )

    assert result.target_file == "pkg/helpers.py"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "python_relative_module"


def test_python_package_resolves_init(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="main.py",
        language="python",
        raw_target="pkg.tools",
        repository_files={
            "main.py",
            "pkg/tools/__init__.py",
        },
    )

    assert result.target_file == "pkg/tools/__init__.py"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "python_module"


def test_python_module_package_ambiguity_is_unresolved(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="main.py",
        language="python",
        raw_target="pkg.tools",
        repository_files={
            "main.py",
            "pkg/tools.py",
            "pkg/tools/__init__.py",
        },
    )

    assert result.target_file is None
    assert result.target_symbol == "pkg.tools"
    assert result.is_internal is False
    assert result.resolution_kind == "ambiguous"


def test_typescript_relative_extensionless_import_resolves(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="./money",
        repository_files={
            "src/app.ts",
            "src/money.ts",
        },
    )

    assert result.target_file == "src/money.ts"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "relative_file"


def test_javascript_explicit_extension_resolves(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.js",
        language="javascript",
        raw_target="./utils.js",
        repository_files={
            "src/app.js",
            "src/utils.js",
        },
    )

    assert result.target_file == "src/utils.js"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "relative_file"


def test_typescript_index_module_resolves(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="./features",
        repository_files={
            "src/app.ts",
            "src/features/index.ts",
        },
    )

    assert result.target_file == "src/features/index.ts"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "relative_file"


def test_typescript_ambiguous_extensions_are_unresolved(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="./money",
        repository_files={
            "src/app.ts",
            "src/money.ts",
            "src/money.js",
        },
    )

    assert result.target_file is None
    assert result.target_symbol == "./money"
    assert result.resolution_kind == "ambiguous"


def test_bare_javascript_package_remains_external(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="react",
        repository_files={"src/app.ts"},
    )

    assert result.target_file is None
    assert result.target_symbol == "react"
    assert result.is_internal is False
    assert result.resolution_kind == "external_or_unresolved"


def test_absolute_target_is_unsafe(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="/outside.ts",
        repository_files={"src/app.ts"},
    )

    assert result.target_file is None
    assert result.target_symbol is None
    assert result.is_internal is False
    assert result.resolution_kind == "unsafe_target"


def test_traversal_target_is_unsafe(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="../../outside",
        repository_files={"src/app.ts"},
    )

    assert result.target_file is None
    assert result.target_symbol is None
    assert result.is_internal is False
    assert result.resolution_kind == "unsafe_target"


def test_windows_separators_normalize_to_posix(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file=r"src\app.ts",
        language="typescript",
        raw_target=r".\utils",
        repository_files={
            r"src\app.ts",
            r"src\utils.ts",
        },
    )

    assert result.target_file == "src/utils.ts"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "relative_file"


def test_invalid_source_file_is_rejected(
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="source_file must be repository-relative",
    ):
        resolve_dependency_target(
            repo_root=tmp_path,
            source_file="../src/app.py",
            language="python",
            raw_target="pkg.shared",
            repository_files={"pkg/shared.py"},
        )


def test_missing_repository_is_rejected(
    tmp_path,
):
    missing_repository = tmp_path / "missing"

    with pytest.raises(
        NotADirectoryError,
        match="Repository root is not a directory",
    ):
        resolve_dependency_target(
            repo_root=missing_repository,
            source_file="src/app.py",
            language="python",
            raw_target="pkg.shared",
            repository_files={"pkg/shared.py"},
        )


def test_repository_files_avoids_filesystem_dependency(
    tmp_path,
    monkeypatch,
):
    def fail_if_candidate_touches_filesystem(
        _path: Path,
    ) -> bool:
        raise AssertionError(
            "candidate resolution must use repository_files"
        )

    monkeypatch.setattr(
        Path,
        "is_file",
        fail_if_candidate_touches_filesystem,
    )

    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="./utils",
        repository_files={
            "src/app.ts",
            "src/utils.ts",
        },
    )

    assert result.target_file == "src/utils.ts"
    assert result.target_symbol is None
    assert result.is_internal is True
    assert result.resolution_kind == "relative_file"

def test_python_relative_import_cannot_escape_package_root(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.py",
        language="python",
        raw_target="from ..outside import value",
        repository_files={
            "src/app.py",
            "outside.py",
        },
    )

    assert result.target_file is None
    assert result.target_symbol is None
    assert result.is_internal is False
    assert result.resolution_kind == "unsafe_target"

def test_python_root_file_relative_import_is_unsafe(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="app.py",
        language="python",
        raw_target="from . import helpers",
        repository_files={
            "app.py",
            "helpers.py",
        },
    )

    assert result.target_file is None
    assert result.target_symbol is None
    assert result.resolution_kind == "unsafe_target"

def test_windows_drive_relative_target_is_unsafe(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target=r"C:outside.ts",
        repository_files={
            "src/app.ts",
        },
    )

    assert result.target_file is None
    assert result.target_symbol is None
    assert result.is_internal is False
    assert result.resolution_kind == "unsafe_target"

def test_node_builtin_specifier_remains_external(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="node:fs",
        repository_files={"src/app.ts"},
    )

    assert result.target_file is None
    assert result.target_symbol == "node:fs"
    assert result.resolution_kind == "external_or_unresolved"

def test_resolution_without_repository_files_uses_bounded_filesystem_checks(
    tmp_path,
):
    source = tmp_path / "src" / "app.ts"
    target = tmp_path / "src" / "utils.ts"

    source.parent.mkdir()
    source.write_text("", encoding="utf-8")
    target.write_text("", encoding="utf-8")

    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="./utils",
    )

    assert result.target_file == "src/utils.ts"
    assert result.is_internal is True

def test_windows_backslash_traversal_is_unsafe(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target=r"..\..\outside",
        repository_files={
            "src/app.ts",
            "outside.ts",
        },
    )

    assert result.target_file is None
    assert result.target_symbol is None
    assert result.is_internal is False
    assert result.resolution_kind == "unsafe_target"

def test_bare_package_does_not_resolve_to_colliding_repo_file(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="react",
        repository_files={
            "src/app.ts",
            "react.ts",
        },
    )

    assert result.target_file is None
    assert result.target_symbol == "react"
    assert result.is_internal is False
    assert result.resolution_kind == "external_or_unresolved"

def test_bare_path_alias_remains_unresolved_without_alias_config(
    tmp_path,
):
    result = resolve_dependency_target(
        repo_root=tmp_path,
        source_file="src/app.ts",
        language="typescript",
        raw_target="src/utils",
        repository_files={
            "src/app.ts",
            "src/utils.ts",
        },
    )

    assert result.target_file is None
    assert result.target_symbol == "src/utils"

