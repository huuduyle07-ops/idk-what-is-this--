"""Static authority-boundary regressions for ACQUIRE.3.

These tests deliberately inspect syntax instead of invoking ACQUIRE.3.  The
focused acquisition tests own bounded reads against temporary repositories;
this file proves that the implementation has no broader machinery and that no
live production path has wired the report-only phase into the application.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"
_CONTRACT_SOURCE = _CORE_ROOT / "content_acquisition.py"
_RUNTIME_SOURCE = _CORE_ROOT / "evidence_content_acquisition.py"
_ACQUIRE_3_SOURCES = (_CONTRACT_SOURCE, _RUNTIME_SOURCE)

#: Downstream report-only phases that consume ACQUIRE.3 *records*.  A phase that
#: reads a frozen contract is not a live production path, and each of these is
#: proved unwired by its own boundary suite; the assertion that matters for them
#: is the narrower one below — they bind to the contract and can never re-run the
#: read runtime.
_DOWNSTREAM_CONTRACT_CONSUMERS = (
    _CORE_ROOT / "evidence_verification.py",
    _CORE_ROOT / "evidence_analyzer.py",
    _CORE_ROOT / "evidence_promotion_gate.py",
    _CORE_ROOT / "evidence_analyzer_adapter.py",
)

_SKIPPED_PRODUCTION_PARTS = frozenset(
    {
        ".agent",
        ".agents",
        ".git",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "tests",
        ".tmp",
        ".pytest_cache",
        "tmp_tests",
        "venv",
    }
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _imported_modules(tree: ast.AST) -> Iterable[tuple[str, int]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module, node.lineno
            for alias in node.names:
                qualified = f"{module}.{alias.name}" if module else alias.name
                yield qualified, node.lineno


def _calls(tree: ast.AST) -> Iterable[tuple[ast.Call, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node, _qualified_name(node.func) or "<dynamic call>"


def _source_trees() -> Iterable[tuple[Path, ast.Module]]:
    for path in _ACQUIRE_3_SOURCES:
        yield path, _tree(path)


def test_acquire_3_does_not_import_forbidden_authority_stacks() -> None:
    forbidden_roots = frozenset(
        {
            "aiohttp",
            "anthropic",
            "asyncpg",
            "boto3",
            "ftplib",
            "google.generativeai",
            "http",
            "httpx",
            "langchain",
            "litellm",
            "multiprocessing",
            "ollama",
            "openai",
            "pathspec",
            "psycopg",
            "psycopg2",
            "pymongo",
            "redis",
            "requests",
            "shutil",
            "smtplib",
            "socket",
            "sqlalchemy",
            "sqlite3",
            "subprocess",
            "supabase",
            "tempfile",
            "transformers",
            "urllib",
            "websockets",
        }
    )
    forbidden_core_prefixes = (
        "core.context_selection",
        "core.direct_file_reader",
        "core.file_candidate_selector",
        "core.graph",
        "core.index",
        "core.model",
        "core.ollama_client",
        "core.repo_librarian",
        "core.repository_inventory",
        "core.retriever",
        "core.semantic_waiter_client",
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            root = module.casefold()
            if any(
                root == prefix or root.startswith(f"{prefix}.")
                for prefix in forbidden_roots
            ) or any(
                root == prefix or root.startswith(f"{prefix}.")
                for prefix in forbidden_core_prefixes
            ):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name in {"__import__", "importlib.import_module"}:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_acquire_3_contains_no_repository_enumeration() -> None:
    exact_traversal_calls = frozenset(
        {
            "glob.glob",
            "glob.iglob",
            "os.fwalk",
            "os.listdir",
            "os.scandir",
            "os.walk",
        }
    )
    traversal_method_names = frozenset(
        {"fwalk", "glob", "iglob", "iterdir", "listdir", "rglob", "scandir", "walk"}
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            if name in exact_traversal_calls or tail in traversal_method_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_acquire_3_contains_no_network_model_database_or_selector_calls() -> None:
    authority_call_names = frozenset(
        {
            "chat",
            "commit",
            "completion",
            "completions",
            "connect",
            "create_connection",
            "cursor",
            "embed",
            "embeddings",
            "execute",
            "executemany",
            "generate",
            "invoke",
            "predict",
            "rollback",
            "urlopen",
        }
    )
    selector_call_names = frozenset(
        {
            "build_candidate_filename_report",
            "derive_candidate_eligibility",
            "execute_context_selection",
            "rank_candidates",
            "select_candidates",
        }
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            if tail in authority_call_names or tail in selector_call_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_acquire_3_contains_no_filesystem_mutation() -> None:
    exact_mutations = frozenset(
        {
            "os.chmod",
            "os.chown",
            "os.fchmod",
            "os.fchown",
            "os.link",
            "os.lchown",
            "os.makedirs",
            "os.mkdir",
            "os.remove",
            "os.removedirs",
            "os.rename",
            "os.renames",
            "os.replace",
            "os.rmdir",
            "os.symlink",
            "os.truncate",
            "os.unlink",
            "os.utime",
            "shutil.copy",
            "shutil.copy2",
            "shutil.copyfile",
            "shutil.copytree",
            "shutil.copymode",
            "shutil.copystat",
            "shutil.move",
            "shutil.rmtree",
        }
    )
    mutation_method_names = frozenset(
        {
            "chmod",
            "hardlink_to",
            "link_to",
            "mkdir",
            "rename",
            "rmdir",
            "symlink_to",
            "touch",
            "truncate",
            "unlink",
            "write",
            "write_bytes",
            "write_text",
            "writelines",
        }
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            path_replace_shape = tail == "replace" and len(call.args) < 2
            if (
                name in exact_mutations
                or tail in mutation_method_names
                or path_replace_shape
            ):
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_file_open_modes_are_statically_read_only_and_descriptor_bounded() -> None:
    trees = {path: tree for path, tree in _source_trees()}
    all_open_calls: list[tuple[Path, ast.Call, str]] = []
    forbidden_flag_names = frozenset(
        {
            "os.O_APPEND",
            "os.O_CREAT",
            "os.O_EXCL",
            "os.O_RDWR",
            "os.O_TMPFILE",
            "os.O_TRUNC",
            "os.O_WRONLY",
        }
    )

    for path, tree in trees.items():
        attributes = {
            _qualified_name(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        assert not forbidden_flag_names & attributes, path.name
        for call, name in _calls(tree):
            if name == "os.open" or name == "os.fdopen" or name == "io.open" or (
                name == "open" or name.endswith(".open")
            ):
                all_open_calls.append((path, call, name))

    assert [(path.name, name) for path, _call, name in all_open_calls] == [
        ("evidence_content_acquisition.py", "os.open")
    ]

    runtime_tree = trees[_RUNTIME_SOURCE]
    functions = {
        node.name: node
        for node in runtime_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    boundary = functions["_open_readonly"]
    assert len(boundary.body) == 6

    initialize, *extend_flags, return_open = boundary.body
    assert isinstance(initialize, ast.Assign)
    assert [_qualified_name(target) for target in initialize.targets] == ["flags"]
    assert _qualified_name(initialize.value) == "os.O_RDONLY"

    observed_optional_flags: set[str] = set()
    for statement in extend_flags:
        assert isinstance(statement, ast.AugAssign)
        assert _qualified_name(statement.target) == "flags"
        assert isinstance(statement.op, ast.BitOr)
        assert isinstance(statement.value, ast.Call)
        assert _qualified_name(statement.value.func) == "getattr"
        assert len(statement.value.args) == 3
        owner, flag, fallback = statement.value.args
        assert _qualified_name(owner) == "os"
        assert isinstance(flag, ast.Constant) and isinstance(flag.value, str)
        assert isinstance(fallback, ast.Constant) and fallback.value == 0
        observed_optional_flags.add(flag.value)
    assert observed_optional_flags == {
        "O_BINARY",
        "O_CLOEXEC",
        "O_NOFOLLOW",
        "O_NONBLOCK",
    }

    assert isinstance(return_open, ast.Return)
    assert isinstance(return_open.value, ast.Call)
    assert _qualified_name(return_open.value.func) == "os.open"
    assert [_qualified_name(argument) for argument in return_open.value.args] == [
        "path",
        "flags",
    ]
    assert return_open.value.keywords == []

    descriptor_read = functions["_descriptor_read"]
    assert len(descriptor_read.body) == 1
    read_return = descriptor_read.body[0]
    assert isinstance(read_return, ast.Return)
    assert isinstance(read_return.value, ast.Call)
    assert _qualified_name(read_return.value.func) == "os.read"
    assert [_qualified_name(argument) for argument in read_return.value.args] == [
        "descriptor",
        "count",
    ]

    exact_read = functions["_read_exact"]
    bounded_calls = [
        call
        for call, name in _calls(exact_read)
        if name == "_descriptor_read"
    ]
    assert len(bounded_calls) == 1
    requested = bounded_calls[0].args[1]
    assert isinstance(requested, ast.Call)
    assert _qualified_name(requested.func) == "min"
    assert [_qualified_name(argument) for argument in requested.args] == [
        "_READ_CHUNK_BYTES",
        "remaining",
    ]


def _production_python_files() -> Iterable[Path]:
    excluded = {
        path.resolve()
        for path in _ACQUIRE_3_SOURCES + _DOWNSTREAM_CONTRACT_CONSUMERS
    }
    for path in sorted(_REPOSITORY_ROOT.rglob("*.py")):
        relative = path.relative_to(_REPOSITORY_ROOT)
        if set(relative.parts) & _SKIPPED_PRODUCTION_PARTS or any(
            part.startswith(".tmp") or part.startswith("pytest-")
            for part in relative.parts
        ):
            continue
        if path.resolve() in excluded:
            continue
        yield path


def _is_acquire_3_import(node: ast.AST) -> bool:
    module_names = {"content_acquisition", "evidence_content_acquisition"}
    if isinstance(node, ast.Import):
        return any(
            alias.name in module_names
            or alias.name in {f"core.{name}" for name in module_names}
            for alias in node.names
        )
    if not isinstance(node, ast.ImportFrom):
        return False
    module = node.module or ""
    if module in module_names or module in {f"core.{name}" for name in module_names}:
        return True
    return (module == "core" or (node.level and not module)) and any(
        alias.name in module_names for alias in node.names
    )


def test_acquire_3_is_not_imported_or_called_by_a_live_production_path() -> None:
    callers: list[str] = []
    for path in _production_python_files():
        tree = _tree(path)
        reasons: set[str] = set()
        for node in ast.walk(tree):
            if _is_acquire_3_import(node):
                reasons.add(f"import@{node.lineno}")
            if isinstance(node, ast.Call):
                name = _qualified_name(node.func) or ""
                if name.rsplit(".", 1)[-1] == "acquire_selected_content":
                    reasons.add(f"call@{node.lineno}")
                if name == "getattr" and any(
                    isinstance(argument, ast.Constant)
                    and argument.value == "acquire_selected_content"
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-call@{node.lineno}")
                if name in {"__import__", "importlib.import_module"} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and argument.value
                    in {
                        "content_acquisition",
                        "core.content_acquisition",
                        "core.evidence_content_acquisition",
                        "evidence_content_acquisition",
                    }
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-import@{node.lineno}")
        if reasons:
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            callers.append(f"{relative}: {', '.join(sorted(reasons))}")

    assert callers == [], callers


def test_downstream_consumers_bind_to_the_contract_and_cannot_re_run_the_read() -> None:
    """EVIDENCE.1 reads ACQUIRE.3's records, never ACQUIRE.3's filesystem path."""
    violations: list[str] = []
    bound: list[str] = []
    for path in _DOWNSTREAM_CONTRACT_CONSUMERS:
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if module.startswith("core.content_acquisition"):
                bound.append(f"{path.name}:{line}")
            if module.startswith("core.evidence_content_acquisition"):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] == "acquire_selected_content":
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert bound, "a downstream consumer must bind to the ACQUIRE.3 contract"
    assert violations == [], violations
