from __future__ import annotations

from pathlib import Path

import core.router as router
from core import project_map_v2
from core.repo_librarian import build_repo_manifest
from core.retriever import extract_file_text
from core.validator import _is_source_file
from web.patch_helpers import detect_patch_language, detect_repo_language


def test_router_detects_mojo_extension_before_rust_syntax():
    assert router.detect_language("fn main() {}", "main.mojo") == "mojo"


def test_router_keeps_content_only_language_regressions():
    assert router.detect_language("fn main() {}") == "rust"
    assert router.detect_language("from python import Python") == "python"
    assert router.detect_language("function add(a, b) { return a + b }") == "javascript"
    assert router.detect_language("interface Foo { id: number }") == "typescript"
    assert router.detect_language("package main\nfunc main() {}") == "go"
    assert router.detect_language("impl Thing { fn run(&self) {} }") == "rust"


def test_fire_extension_remains_unknown_and_unsupported():
    assert router.detect_language("fn main() {}", "main.🔥") == "rust"
    assert router.detect_language("plain text", "main.🔥") == "unknown"
    assert router.should_use_retriever("main.🔥") is False


def test_mojo_extension_is_retriever_supported_and_source_file():
    assert router.should_use_retriever("main.mojo") is True
    assert _is_source_file(Path("main.mojo")) is True


def test_mojo_file_text_is_retrievable(tmp_path):
    (tmp_path / "main.mojo").write_text("fn main() {}\n", encoding="utf-8")

    assert extract_file_text("main.mojo", repo_path=str(tmp_path)) == "fn main() {}\n"


def test_mojo_only_repo_manifest_is_indexable(tmp_path):
    (tmp_path / "main.mojo").write_text("fn main() {}\n", encoding="utf-8")

    manifest = build_repo_manifest(str(tmp_path))

    assert manifest["ok"] is True
    assert manifest["indexable_count"] == 1
    assert manifest["primary_language"] == "mojo"
    assert manifest["languages"] == {"mojo": 1}
    assert manifest["sample_indexable_files"] == ["main.mojo"]


def test_project_map_counts_mojo_language(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.mojo").write_text("fn main() {}\n", encoding="utf-8")

    record = project_map_v2.build_project_map_v2_record(str(tmp_path))

    assert {"language": "mojo", "count": 1} in record["languages"]


def test_web_patch_helpers_detect_mojo_from_patch_and_repo(tmp_path):
    assert detect_patch_language({"relative_path": "src/main.mojo"}) == "mojo"

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.mojo").write_text("fn main() {}\n", encoding="utf-8")

    assert detect_repo_language(tmp_path) == "mojo"


def test_router_detects_lua_extension_before_python_print_heuristic():
    assert router.detect_language("print('hello')", "main.lua") == "lua"


def test_lua_extension_is_retriever_supported_and_already_source_file(tmp_path):
    (tmp_path / "main.lua").write_text("print('hello')\n", encoding="utf-8")

    assert router.should_use_retriever("main.lua") is True
    assert _is_source_file(Path("main.lua")) is True
    assert extract_file_text("main.lua", repo_path=str(tmp_path)) == "print('hello')\n"


def test_lua_only_repo_manifest_is_indexable(tmp_path):
    (tmp_path / "main.lua").write_text("print('hello')\n", encoding="utf-8")

    manifest = build_repo_manifest(str(tmp_path))

    assert manifest["ok"] is True
    assert manifest["indexable_count"] == 1
    assert manifest["primary_language"] == "lua"
    assert manifest["languages"] == {"lua": 1}
    assert manifest["sample_indexable_files"] == ["main.lua"]


def test_project_map_counts_lua_language(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.lua").write_text("print('hello')\n", encoding="utf-8")

    record = project_map_v2.build_project_map_v2_record(str(tmp_path))

    assert {"language": "lua", "count": 1} in record["languages"]


def test_web_patch_helpers_detect_lua_from_patch_and_repo(tmp_path):
    assert detect_patch_language({"relative_path": "src/main.lua"}) == "lua"

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.lua").write_text("print('hello')\n", encoding="utf-8")

    assert detect_repo_language(tmp_path) == "lua"
