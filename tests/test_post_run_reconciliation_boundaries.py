"""Static authority-boundary regressions for CHECK.1.

The focused reconciliation suite owns behaviour.  These tests prove that the
implementation has only the machinery needed to compare supplied facts against a
supplied contract.  In particular it has no route to traverse a repository, read
source content, run a validation, apply a patch, call a model, or reach a
semantic verdict about the implementation it reconciles.

Honest *negative* guardrail and authority keys are intentionally permitted as
string literals: ``semantic_goal_review_performed = False`` is a denial, not a
capability.  The stronger boundary is that no field or callable can carry a
semantic verdict and no forbidden authority is constructor settable.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"
_RECONCILIATION_SOURCE = _CORE_ROOT / "post_run_reconciliation.py"
_OBSERVATION_SOURCE = _CORE_ROOT / "post_run_observation.py"

_CHECK_1_SOURCES = (_RECONCILIATION_SOURCE, _OBSERVATION_SOURCE)
_PURE_CORE_SOURCES = (_RECONCILIATION_SOURCE,)

#: CHECK.2 is the one report-only downstream phase allowed to consume a frozen
#: PostRunReconciliation.  It is excluded from the "live wiring" scan only so
#: long as the narrower assertion at the end of this file proves that it reads
#: the contract and cannot re-run CHECK.1, collect facts, or reach any
#: execution, validation or patch runtime.
_DOWNSTREAM_CONTRACT_CONSUMERS = (_CORE_ROOT / "goal_fidelity_review.py",)

#: CHECK.LIVE.1 and CHECK.LIVE.1B are the only *live* consumers allowed to bind
#: to CHECK.1, and only in shadow mode.  These modules produce typed CHECK.1
#: inputs from facts a real execution already holds and invoke the frozen checker
#: once; they are excluded from the "no live wiring" scan only so long as the
#: narrower assertions at the end of this file prove that they reimplement no
#: reconciliation rule, derive no status of their own, and reach no execution,
#: validation, patch or model runtime.
_LIVE_SHADOW_WIRING = (
    _CORE_ROOT / "live_execution_authorization.py",
    _CORE_ROOT / "live_validation_receipt.py",
    _CORE_ROOT / "live_worker_declaration.py",
    _CORE_ROOT / "live_worker_report.py",
    _CORE_ROOT / "post_run_reconciliation_shadow.py",
)

#: The single module permitted to invoke the reconciliation itself.
_SHADOW_ORCHESTRATOR = _CORE_ROOT / "post_run_reconciliation_shadow.py"

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


def _import_statement_modules(tree: ast.Module) -> tuple[str, ...]:
    modules: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return tuple(modules)


def _imported_names(tree: ast.Module, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "") == module:
            names.update(alias.name for alias in node.names)
    return names


def _calls(tree: ast.AST) -> Iterable[tuple[ast.Call, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node, _qualified_name(node.func) or "<dynamic call>"


def _source_trees(sources: tuple[Path, ...] = _CHECK_1_SOURCES):
    for path in sources:
        yield path, _tree(path)


def _function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


# -- Pure, deterministic imports ---------------------------------------------

def test_reconciliation_core_imports_only_pure_helpers_and_a_frozen_path_policy():
    allowed_modules = frozenset(
        {
            "__future__",
            "dataclasses",
            "hashlib",
            "json",
            "typing",
            "core.repository_path_policy",
        }
    )
    violations: list[str] = []
    observed: set[str] = set()
    for path, tree in _source_trees(_PURE_CORE_SOURCES):
        for module in _import_statement_modules(tree):
            observed.add(module)
            if module not in allowed_modules:
                violations.append(f"{path.name}: import {module}")
        for call, name in _calls(tree):
            if name in {"__import__", "importlib.import_module"}:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert observed == allowed_modules
    assert violations == [], violations


def test_the_path_policy_is_reused_for_lexical_shape_only():
    """The one project import must not smuggle in filesystem behaviour."""
    tree = _tree(_RECONCILIATION_SOURCE)
    imported = _imported_names(tree, "core.repository_path_policy")

    assert imported == {
        "MAX_CANONICAL_RELATIVE_PATH_LENGTH",
        "is_safe_repository_relative_path",
    }


def test_the_observation_adapter_imports_only_the_existing_safety_gate():
    allowed_modules = frozenset(
        {
            "__future__",
            "collections.abc",
            "typing",
            "core.patch_safety",
            "core.post_run_reconciliation",
        }
    )
    tree = _tree(_OBSERVATION_SOURCE)
    observed = set(_import_statement_modules(tree))

    assert observed == allowed_modules
    assert _imported_names(tree, "core.patch_safety") == {"evaluate_patch_safety"}


def test_importing_check_1_is_inert():
    """Only definitions and immutable constant construction run at import."""
    allowed_call_names = frozenset({"frozenset"})
    forbidden_top_level = (
        ast.AsyncFor,
        ast.AsyncWith,
        ast.For,
        ast.If,
        ast.Match,
        ast.Try,
        ast.While,
        ast.With,
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for node in tree.body:
            if isinstance(node, forbidden_top_level):
                violations.append(f"{path.name}:{node.lineno}: {type(node).__name__}")
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue
            for call, name in _calls(node):
                if name.rsplit(".", 1)[-1] not in allowed_call_names:
                    violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_check_1_has_no_clock_entropy_environment_or_runtime_imports():
    banned_roots = frozenset(
        {
            "datetime",
            "importlib",
            "locale",
            "platform",
            "random",
            "secrets",
            "time",
            "uuid",
        }
    )
    banned_calls = frozenset(
        {
            "choice",
            "getenv",
            "getrandbits",
            "hash",
            "monotonic",
            "now",
            "perf_counter",
            "randint",
            "random",
            "sample",
            "shuffle",
            "time",
            "time_ns",
            "today",
            "utcnow",
            "uuid1",
            "uuid4",
        }
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            root = module.casefold().split(".", 1)[0]
            if root in banned_roots:
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in banned_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


# -- No authority-bearing runtime --------------------------------------------

def test_check_1_does_not_import_an_authority_stack():
    forbidden_roots = frozenset(
        {
            "aiohttp",
            "anthropic",
            "asyncpg",
            "boto3",
            "database",
            "difflib",
            "fnmatch",
            "ftplib",
            "git",
            "glob",
            "graph",
            "http",
            "httpx",
            "langchain",
            "litellm",
            "multiprocessing",
            "ollama",
            "openai",
            "os",
            "pathlib",
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
            "storage",
            "subprocess",
            "supabase",
            "tempfile",
            "transformers",
            "urllib",
            "web",
            "websockets",
        }
    )
    forbidden_project_prefixes = (
        "agents.",
        "core.bounded_lexical_search",
        "core.context_search_runtime",
        "core.context_selection",
        "core.direct_context_runtime",
        "core.direct_file_reader",
        "core.executor",
        "core.graph",
        "core.index",
        "core.model",
        "core.ollama_client",
        "core.pipeline",
        "core.repo_librarian",
        "core.repository_inventory",
        "core.retriever",
        "core.sandbox_runner",
        "core.self_correct_loop",
        "core.semantic_waiter",
        "core.validation_execution",
        "core.worker_",
        "database.",
        "graph.",
        "patching.",
        "reasoning.",
        "storage.",
        "web.",
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            folded = module.casefold()
            root = folded.split(".", 1)[0]
            if root in forbidden_roots or any(
                folded == prefix.rstrip(".") or folded.startswith(prefix)
                for prefix in forbidden_project_prefixes
            ):
                violations.append(f"{path.name}:{line}: import {module}")

    assert violations == [], violations


def test_check_1_performs_no_traversal_read_execution_network_or_write():
    forbidden_tails = frozenset(
        {
            "call",
            "check_call",
            "check_output",
            "chat",
            "chdir",
            "commit",
            "complete",
            "connect",
            "copy",
            "create_connection",
            "cursor",
            "embed",
            "eval",
            "exec",
            "executemany",
            "execute",
            "fetch",
            "fetchall",
            "fetchone",
            "fdopen",
            "generate",
            "getaddrinfo",
            "glob",
            "iglob",
            "infer",
            "invoke",
            "iterdir",
            "listdir",
            "lstat",
            "makedirs",
            "mkdir",
            "open",
            "popen",
            "post",
            "predict",
            "query",
            "read",
            "read_bytes",
            "readline",
            "readlines",
            "read_text",
            "recv",
            "remove",
            "rename",
            "request",
            "rglob",
            "rmdir",
            "rmtree",
            "rollback",
            "run",
            "scandir",
            "send",
            "socket",
            "spawn",
            "stat",
            "system",
            "touch",
            "unlink",
            "urlopen",
            "walk",
            "write",
            "write_bytes",
            "writelines",
            "write_text",
        }
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden_tails:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_check_1_names_no_patch_apply_validation_run_or_repair_entry_point():
    banned_fragments = (
        "apply_patch",
        "ask_worker",
        "auto_fix",
        "checkout",
        "clean_worktree",
        "git_",
        "merge_branch",
        "repair",
        "reset_repository",
        "retry_validation",
        "revise_note",
        "rerun",
        "rewrite_report",
        "run_tests",
        "run_validation",
        "stage_",
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                folded = node.name.casefold()
                if any(fragment in folded for fragment in banned_fragments):
                    violations.append(f"{path.name}:{node.lineno}: {node.name}")

    assert violations == [], violations


# -- No approximate matching, scoring, or semantic judgement ------------------

def test_check_1_has_no_fuzzy_prefix_or_approximate_path_matching():
    banned_calls = frozenset(
        {
            "SequenceMatcher",
            "casefold",
            "endswith",
            "findall",
            "fnmatch",
            "fullmatch",
            "get_close_matches",
            "lower",
            "match",
            "ratio",
            "search",
            "similarity",
            "startswith",
            "sub",
            "upper",
        }
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in banned_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_the_pure_core_performs_no_numeric_reduction_or_risk_arithmetic():
    banned_reductions = frozenset(
        {
            "Counter",
            "accumulate",
            "fmean",
            "fsum",
            "max",
            "mean",
            "median",
            "min",
            "mode",
            "most_common",
            "prod",
            "quantiles",
            "reduce",
            "sum",
        }
    )
    arithmetic_operators = (
        ast.Add,
        ast.Div,
        ast.FloorDiv,
        ast.MatMult,
        ast.Mod,
        ast.Mult,
        ast.Pow,
        ast.Sub,
    )
    violations: list[str] = []
    for path, tree in _source_trees(_PURE_CORE_SOURCES):
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in banned_reductions:
                violations.append(f"{path.name}:{call.lineno}: {name}")
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, arithmetic_operators):
                violations.append(
                    f"{path.name}:{node.lineno}: {type(node.op).__name__}"
                )

    assert violations == [], violations


def test_no_check_1_field_or_callable_is_score_confidence_or_vote_shaped():
    banned_fragments = (
        "aggregate_confidence",
        "average",
        "confidence",
        "likelihood",
        "majority",
        "mean_",
        "probability",
        "quality",
        "rank",
        "risk_score",
        "score",
        "tally",
        "vote",
        "weight",
        "winner",
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
            if isinstance(node, ast.ClassDef):
                names.extend(
                    statement.target.id
                    for statement in node.body
                    if isinstance(statement, ast.AnnAssign)
                    and isinstance(statement.target, ast.Name)
                )
            if isinstance(node, (ast.Name, ast.arg)):
                names.append(node.id if isinstance(node, ast.Name) else node.arg)
            for name in names:
                folded = name.casefold()
                if any(fragment in folded for fragment in banned_fragments):
                    violations.append(f"{path.name}: {name}")

    assert violations == [], violations


def test_status_and_coverage_vocabularies_contain_no_semantic_verdict():
    from core.post_run_reconciliation import (
        CHANGE_CLASSIFICATIONS,
        RECONCILIATION_STATUSES,
        SEVERITIES,
        VALIDATION_COVERAGE_STATES,
    )

    banned = (
        "correct",
        "goal_satisfied",
        "good",
        "implementation",
        "quality",
        "score",
        "semantically",
        "success",
        "winner",
    )
    for value in (
        *RECONCILIATION_STATUSES,
        *VALIDATION_COVERAGE_STATES,
        *CHANGE_CLASSIFICATIONS,
        *SEVERITIES,
    ):
        assert not any(fragment in value.casefold() for fragment in banned), value


def test_the_result_carries_change_identity_never_diff_or_source_content():
    import dataclasses

    from core.post_run_reconciliation import (
        ChangeFinding,
        ObservedChange,
        PostRunReconciliation,
        ValidationFinding,
    )

    banned_fragments = (
        "body",
        "content",
        "diff",
        "excerpt",
        "hunk",
        "line_text",
        "패치",
        "patch_text",
        "payload",
        "prose",
        "snippet",
        "source_text",
        "stderr",
        "stdout",
        "text_body",
    )
    for owner in (ObservedChange, ChangeFinding, ValidationFinding, PostRunReconciliation):
        for field in dataclasses.fields(owner):
            folded = field.name.casefold()
            assert not any(
                fragment in folded for fragment in banned_fragments
            ), f"{owner.__name__}.{field.name}"


def test_observed_change_exposes_only_bounded_identity_fields():
    import dataclasses

    from core.post_run_reconciliation import ObservedChange

    assert {item.name for item in dataclasses.fields(ObservedChange)} == {
        "path",
        "change_kind",
        "before_sha256",
        "after_sha256",
        "from_path",
    }


def test_the_worker_report_has_no_free_prose_verdict_field():
    import dataclasses

    from core.post_run_reconciliation import WorkerReport

    fields = {item.name for item in dataclasses.fields(WorkerReport)}
    assert fields == {
        "report_id",
        "execution_run_id",
        "declared_status",
        "declared_changes",
        "declared_validation_actions",
        "declared_limitations",
        "declared_unresolved_items",
        "worker_id",
        "schema_version",
    }
    for banned in ("summary", "narrative", "note_text", "conclusion", "verdict"):
        assert banned not in fields


# -- Forbidden authority is not settable -------------------------------------

def test_forbidden_authorities_are_not_constructor_settable():
    import dataclasses
    import inspect

    from core.post_run_reconciliation import (
        PostRunReconciliation,
        reconciliation_authority,
    )

    forbidden_authorities = {
        "semantic_goal_review_authority",
        "implementation_correctness_authority",
        "final_success_authority",
        "merge_authority",
        "patch_authority",
        "write_authority",
        "repository_read_authority",
        "repository_traversal_authority",
        "validation_execution_authority",
        "command_execution_authority",
        "model_selection_authority",
        "provider_selection_authority",
        "final_response_authority",
    }
    result_fields = {item.name for item in dataclasses.fields(PostRunReconciliation)}
    assert forbidden_authorities.isdisjoint(result_fields)

    for property_name in (
        "semantic_goal_review_authority",
        "implementation_correctness_authority",
        "final_success_authority",
    ):
        descriptor = getattr(PostRunReconciliation, property_name)
        assert isinstance(descriptor, property)
        assert descriptor.fset is None
        assert descriptor.fget(object.__new__(PostRunReconciliation)) is False

    check_2 = PostRunReconciliation.check_2_required
    assert isinstance(check_2, property)
    assert check_2.fset is None
    assert check_2.fget(object.__new__(PostRunReconciliation)) is True

    parameters = inspect.signature(reconciliation_authority).parameters
    assert set(parameters) == {"post_run_reconciliation_authority"}
    authority = reconciliation_authority(post_run_reconciliation_authority=True)
    assert authority["human_approval_required"] is True
    assert all(authority[name] is False for name in forbidden_authorities)


def test_the_result_cannot_be_built_without_an_outstanding_semantic_review():
    import dataclasses

    import pytest

    from core.post_run_reconciliation import (
        UNRESOLVED_HUMAN_REVIEW,
        UNRESOLVED_SEMANTIC_GOAL_REVIEW,
    )
    from tests.test_post_run_reconciliation import (
        authorization,
        facts,
        reconcile,
        report,
    )

    result = reconcile(authorization(), report(), facts())
    with pytest.raises(ValueError):
        dataclasses.replace(result, unresolved_requirements=())
    with pytest.raises(ValueError):
        dataclasses.replace(
            result, unresolved_requirements=(UNRESOLVED_SEMANTIC_GOAL_REVIEW,)
        )
    with pytest.raises(ValueError):
        dataclasses.replace(
            result, unresolved_requirements=(UNRESOLVED_HUMAN_REVIEW,)
        )


def test_the_serializer_renders_the_result_and_nothing_else():
    tree = _tree(_RECONCILIATION_SOURCE)
    serializer = _function_node(tree, "render_post_run_reconciliation_json")
    serializer_calls = {name for _call, name in _calls(serializer)}

    assert serializer_calls <= {"TypeError", "json.dumps", "result.as_dict", "type"}
    assert "json.dumps" in serializer_calls
    assert not any(isinstance(node, ast.JoinedStr) for node in ast.walk(serializer))


# -- The observation adapter observes and nothing more ------------------------

def test_the_observation_adapter_declares_it_collected_nothing_itself():
    from core.post_run_observation import observation_guardrails

    guardrails = observation_guardrails()
    assert guardrails["facts_collected_externally"] is True
    assert guardrails["path_safety_gate_reused"] is True
    assert guardrails["human_approval_required"] is True
    for denied in (
        "repository_traversed",
        "repository_read",
        "source_content_read",
        "symlink_resolved",
        "git_invoked",
        "subprocess_invoked",
        "validation_executed",
        "patch_applied",
        "files_modified",
        "worktree_cleaned",
        "repository_reset",
        "network_call_performed",
        "model_called",
    ):
        assert guardrails[denied] is False


def test_facts_built_by_the_adapter_are_always_marked_externally_collected():
    import hashlib

    from core.post_run_observation import build_observed_post_run_facts

    def digest(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    built = build_observed_post_run_facts(
        facts_id="FACTS-1",
        execution_run_id="RUN-1",
        repository_id="REPO-1",
        pre_execution_state_fingerprint=digest("s0"),
        post_execution_state_fingerprint=digest("s0"),
        final_state_fingerprint=digest("s0"),
    )
    assert built.facts_collected_externally is True


def test_the_adapter_cannot_launder_a_gate_blocked_path_into_writable():
    from core.post_run_observation import classify_authorized_paths
    from core.post_run_reconciliation import (
        PATH_AUTHORITY_FORBIDDEN,
        PATH_AUTHORITY_WRITABLE,
    )

    classified = {
        item.path: item
        for item in classify_authorized_paths(
            writable_paths=(
                "core/router.py",
                ".env",
                ".env.local",
                "tests/test_router.py",
                "node_modules/vendor.js",
                ".git/config",
                "benchmarks/cases/case.json",
            )
        )
    }
    assert classified["core/router.py"].authority == PATH_AUTHORITY_WRITABLE
    for laundered, reason in (
        (".env", "env"),
        (".env.local", "env"),
        ("tests/test_router.py", "test"),
        ("node_modules/vendor.js", "protected_dir"),
        (".git/config", "protected_dir"),
        ("benchmarks/cases/case.json", "benchmark_validation"),
    ):
        assert classified[laundered].authority == PATH_AUTHORITY_FORBIDDEN, laundered
        assert classified[laundered].forbidden_reason == reason, laundered


def test_the_adapter_preserves_the_read_versus_execute_versus_write_distinction():
    from core.post_run_observation import classify_authorized_paths
    from core.post_run_reconciliation import (
        PATH_AUTHORITY_SUPPORTING_READ_ONLY,
        PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
    )

    classified = {
        item.path: item
        for item in classify_authorized_paths(
            supporting_read_only_paths=("core/session.py",),
            validation_execute_only_paths=("tests/test_router.py",),
        )
    }
    assert classified["core/session.py"].authority == (
        PATH_AUTHORITY_SUPPORTING_READ_ONLY
    )
    assert classified["tests/test_router.py"].authority == (
        PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY
    )
    assert all(item.write_authorized is False for item in classified.values())


def test_the_adapter_rejects_an_unknown_observed_change_field():
    import pytest

    from core.post_run_observation import observed_changes_from_records

    with pytest.raises(ValueError):
        observed_changes_from_records(
            [
                {
                    "path": "core/router.py",
                    "change_kind": "modified",
                    "before_sha256": "a" * 64,
                    "after_sha256": "b" * 64,
                    "diff_text": "@@ -1 +1 @@",
                }
            ]
        )


def test_the_adapter_rejects_a_path_classified_more_than_once():
    import pytest

    from core.post_run_observation import classify_authorized_paths

    with pytest.raises(ValueError):
        classify_authorized_paths(
            writable_paths=("core/router.py",),
            supporting_read_only_paths=("core/router.py",),
        )


# -- Report-only: no application path may invoke the phase --------------------

_CHECK_1_MODULE_NAMES = frozenset(
    {"post_run_reconciliation", "post_run_observation"}
)

_CHECK_1_ENTRY_POINTS = frozenset(
    {
        "reconcile_post_run",
        "render_post_run_reconciliation_json",
        "classify_authorized_paths",
        "observed_changes_from_records",
        "build_observed_post_run_facts",
    }
)


def _production_python_files() -> Iterable[Path]:
    excluded = {
        path.resolve()
        for path in (
            _CHECK_1_SOURCES + _DOWNSTREAM_CONTRACT_CONSUMERS + _LIVE_SHADOW_WIRING
        )
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


def _is_check_1_import(node: ast.AST) -> bool:
    qualified = {f"core.{name}" for name in _CHECK_1_MODULE_NAMES}
    if isinstance(node, ast.Import):
        return any(
            alias.name in _CHECK_1_MODULE_NAMES or alias.name in qualified
            for alias in node.names
        )
    if not isinstance(node, ast.ImportFrom):
        return False
    module = node.module or ""
    if module in _CHECK_1_MODULE_NAMES or module in qualified:
        return True
    return (module == "core" or (node.level and not module)) and any(
        alias.name in _CHECK_1_MODULE_NAMES for alias in node.names
    )


def test_check_1_is_not_imported_or_called_outside_its_declared_consumers():
    """Only CHECK.2 and the declared live shadow wiring may bind to CHECK.1.

    Everything else in the project — every executor, planner, patch path,
    response builder and route — must still be unable to reach the phase.
    """
    callers: list[str] = []
    for path in _production_python_files():
        tree = _tree(path)
        reasons: set[str] = set()
        for node in ast.walk(tree):
            if _is_check_1_import(node):
                reasons.add(f"import@{node.lineno}")
            if isinstance(node, ast.Call):
                name = _qualified_name(node.func) or ""
                if name.rsplit(".", 1)[-1] in _CHECK_1_ENTRY_POINTS:
                    reasons.add(f"call@{node.lineno}")
                if name == "getattr" and any(
                    isinstance(argument, ast.Constant)
                    and argument.value in _CHECK_1_ENTRY_POINTS
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-call@{node.lineno}")
                if name in {"__import__", "importlib.import_module"} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and (
                        argument.value in _CHECK_1_MODULE_NAMES
                        or argument.value
                        in {f"core.{item}" for item in _CHECK_1_MODULE_NAMES}
                    )
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-import@{node.lineno}")
        if reasons:
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            callers.append(f"{relative}: {', '.join(sorted(reasons))}")

    assert callers == [], callers


def test_check_1_does_not_change_the_existing_checker_or_patch_safety_contracts():
    """CHECK.1 reuses the frozen gate; it must not have rewritten it."""
    from core.patch_safety import evaluate_patch_safety

    verdict = evaluate_patch_safety([".env", "core/router.py"])
    assert verdict["ok"] is False
    categories = {item["path"]: item["category"] for item in verdict["blocked_paths"]}
    assert categories == {".env": "env"}


def test_the_only_downstream_consumer_reads_the_result_and_re_runs_nothing():
    """CHECK.2 may reconcile a frozen PostRunReconciliation, never produce one."""
    forbidden_modules = (
        "agents.ollama_client",
        "core.evidence_analyzer",
        "core.executor",
        "core.patch_safety",
        "core.pipeline",
        "core.post_run_observation",
        "core.repository_inventory",
        "core.self_correct_loop",
        "core.validation_command",
        "core.validation_execution",
        "core.worker_result_review",
        "core.worker_runs",
    )
    forbidden_calls = frozenset(
        {
            "build_observed_post_run_facts",
            "classify_authorized_paths",
            "evaluate_patch_safety",
            "observed_changes_from_records",
            "reconcile_post_run",
        }
    )
    forbidden_contracts = (
        "AuthorizedPath",
        "DeclaredChange",
        "ExecutionAuthorization",
        "ObservedChange",
        "ObservedPostRunFacts",
        "PostRunReconciliationRequest",
        "ValidationReceipt",
        "WorkerReport",
    )

    bound: list[str] = []
    violations: list[str] = []
    for path in _DOWNSTREAM_CONTRACT_CONSUMERS:
        tree = _tree(path)
        source = path.read_text(encoding="utf-8")
        for module, line in _imported_modules(tree):
            if module.startswith("core.post_run_reconciliation"):
                bound.append(f"{path.name}:{line}")
            if module.startswith(forbidden_modules):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")
        for contract_name in forbidden_contracts:
            if contract_name in source:
                violations.append(f"{path.name}: names {contract_name}")

    assert len(_DOWNSTREAM_CONTRACT_CONSUMERS) == 1
    assert bound, "CHECK.2 must bind to the frozen CHECK.1 contract"
    assert violations == [], violations


# -- CHECK.LIVE.1: the live consumer is shadow-only ---------------------------

def test_the_live_shadow_wiring_binds_the_frozen_contract():
    """Every CHECK.LIVE.1 producer consumes the frozen CHECK.1 records."""
    unbound: list[str] = []
    for path in _LIVE_SHADOW_WIRING:
        tree = _tree(path)
        modules = {module for module, _line in _imported_modules(tree)}
        if not any(
            module.startswith("core.post_run_reconciliation")
            or module.startswith("core.post_run_observation")
            for module in modules
        ):
            unbound.append(path.name)
    assert unbound == [], unbound


def test_only_one_live_module_invokes_the_reconciliation():
    """There is exactly one reconciliation policy and one invocation point."""
    invokers: list[str] = []
    for path in _LIVE_SHADOW_WIRING:
        for call, name in _calls(_tree(path)):
            if name.rsplit(".", 1)[-1] == "reconcile_post_run":
                invokers.append(f"{path.name}:{call.lineno}")
    assert len(invokers) == 1, invokers
    assert invokers[0].startswith(_SHADOW_ORCHESTRATOR.name), invokers


def test_the_live_wiring_reimplements_no_reconciliation_rule():
    """A shadow status may only ever be copied from CHECK.1's own result.

    The forbidden shape is a live path deciding for itself — ``if
    forbidden_path: status = "blocked"``.  Every reconciliation status the
    receipt carries must therefore come from an attribute of the CHECK.1
    result, never from a literal or a locally derived value.
    """
    tree = _tree(_SHADOW_ORCHESTRATOR)
    violations: list[str] = []
    for call, name in _calls(tree):
        if name.rsplit(".", 1)[-1] != "ShadowPostRunCheckReceipt":
            continue
        for keyword in call.keywords:
            if keyword.arg != "reconciliation_status":
                continue
            value = keyword.value
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            if isinstance(value, ast.Attribute) and value.attr == "status":
                continue
            violations.append(f"line {call.lineno}: derived reconciliation status")

    # Reconciliation status *names* are imported from the frozen module, never
    # re-declared here: a locally defined status vocabulary would be a second
    # reconciliation policy.
    imported = _imported_names(tree, "core.post_run_reconciliation")
    for constant in (
        "STATUS_BLOCKED",
        "STATUS_INCOMPLETE",
        "STATUS_INCONSISTENT_INPUT",
        "STATUS_RECONCILED",
        "STATUS_RECONCILED_WITH_WARNINGS",
        "STATUS_SUSPICIOUS",
    ):
        assert constant in imported, constant

    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            label = _qualified_name(target) or ""
            if not label.startswith("STATUS_"):
                continue
            violations.append(
                f"line {node.lineno}: reconciliation status redefined locally"
            )

    assert violations == [], violations


def test_the_live_wiring_reaches_no_execution_validation_patch_or_model():
    """The shadow wiring observes; it may not act."""
    forbidden_modules = (
        "agents.",
        "core.executor",
        "core.indexer",
        "core.mirror_tunnel_claim_diff_check",
        "core.mutation_oracle",
        "core.pipeline",
        "core.self_correct_loop",
        "core.validation_execution",
        "core.validator",
        "core.worker_result_review",
        "core.worker_runs",
        "patching",
        "reasoning.",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    )
    forbidden_calls = frozenset(
        {
            "apply_patch_from_json",
            "apply_patch_plan",
            "check_output",
            "clean",
            "getoutput",
            "iterdir",
            "reset",
            "rglob",
            "run_safe_validation_command",
            "run_validation_command",
            "snapshot_repo_files",
            "stash",
            "system",
            "walk",
        }
    )
    violations: list[str] = []
    for path in _LIVE_SHADOW_WIRING + (_CORE_ROOT / "live_change_observation.py",):
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if module.startswith(forbidden_modules):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")
    assert violations == [], violations


def test_the_live_observer_performs_no_repository_traversal():
    """The bounded observer must never grow a repository walk.

    Enumeration needs a module the observer deliberately does not import, so
    the boundary is enforced at the import surface as well as the call surface.
    """
    observer = _CORE_ROOT / "live_change_observation.py"
    tree = _tree(observer)

    assert set(_import_statement_modules(tree)) == {
        "__future__",
        "dataclasses",
        "hashlib",
        "json",
        "pathlib",
        "typing",
        "core.repository_path_policy",
    }

    for _call, name in _calls(tree):
        assert name.rsplit(".", 1)[-1] not in {
            "walk",
            "rglob",
            "glob",
            "iterdir",
            "scandir",
            "listdir",
            "run",
            "Popen",
            "check_output",
            "system",
        }, name


def test_the_live_worker_report_producer_parses_no_prose():
    """A typed worker report is built from structure, never from text."""
    producer = _CORE_ROOT / "live_worker_report.py"
    tree = _tree(producer)
    for module, line in _imported_modules(tree):
        assert not module.startswith("re"), f"{line}: import {module}"
    source = producer.read_text(encoding="utf-8")
    for forbidden in ("re.compile", "re.search", "re.findall", "re.match"):
        assert forbidden not in source, forbidden
    for _call, name in _calls(tree):
        assert name.rsplit(".", 1)[-1] not in {
            "compile",
            "findall",
            "finditer",
            "search",
            "splitlines",
        }, name


def test_the_check_1_public_surface_is_unchanged_by_live_wiring():
    """CHECK.LIVE.1 consumes the frozen contract; it does not widen it."""
    from core.post_run_observation import __all__ as observation_all
    from core.post_run_reconciliation import __all__ as reconciliation_all

    assert set(observation_all) == {
        "PHASE_ID",
        "ADAPTER_KIND",
        "OBSERVED_CHANGE_FIELDS",
        "patch_safety_forbidden_categories",
        "classify_authorized_paths",
        "observed_changes_from_records",
        "build_observed_post_run_facts",
        "observation_guardrails",
    }
    for required in (
        "RECONCILIATION_STATUSES",
        "ExecutionAuthorization",
        "ObservedPostRunFacts",
        "PostRunReconciliationRequest",
        "ValidationReceipt",
        "WorkerReport",
        "reconcile_post_run",
    ):
        assert required in reconciliation_all, required
