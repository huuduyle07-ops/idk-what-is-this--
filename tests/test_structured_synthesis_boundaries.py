"""Static authority-boundary regressions for SYNTHESIS.1.

The focused synthesis suite owns composition behaviour.  These tests prove
that the implementation has only the machinery needed to place frozen CLAIM.1
records into preserved INPUT.1 slots.  In particular it has no route to assess
a claim, inspect evidence or source content, read a repository, call a model,
make a decision, select a winner, compute a score, or emit RESPONSE.1 prose.

Honest negative guardrail and authority *keys* are intentionally permitted as
string literals.  The stronger boundary is that no field or callable can carry
winner/score/confidence/vote data and no forbidden authority is constructor
settable.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"
_SYNTHESIS_SOURCE = _CORE_ROOT / "structured_synthesis.py"

_SYNTHESIS_1_SOURCES = (_SYNTHESIS_SOURCE,)

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


def _calls(tree: ast.AST) -> Iterable[tuple[ast.Call, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node, _qualified_name(node.func) or "<dynamic call>"


def _source_trees(sources: tuple[Path, ...] = _SYNTHESIS_1_SOURCES):
    for path in sources:
        yield path, _tree(path)


def _class_node(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"missing class {name}")


def _function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


# -- Pure, deterministic imports ---------------------------------------------

def test_synthesis_1_imports_only_pure_helpers_and_frozen_contracts() -> None:
    allowed_modules = frozenset(
        {
            "__future__",
            "dataclasses",
            "hashlib",
            "json",
            "typing",
            "core.claim_assessment",
            "core.task_contract",
        }
    )
    violations: list[str] = []
    observed: set[str] = set()
    for path, tree in _source_trees():
        for module in _import_statement_modules(tree):
            observed.add(module)
            if module not in allowed_modules:
                violations.append(f"{path.name}: import {module}")
        for call, name in _calls(tree):
            if name in {"__import__", "importlib.import_module"}:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert observed == allowed_modules
    assert violations == [], violations


def test_importing_synthesis_1_is_inert() -> None:
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
                violations.append(
                    f"{path.name}:{node.lineno}: {type(node).__name__}"
                )
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


def test_synthesis_1_has_no_clock_entropy_environment_or_runtime_imports() -> None:
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

def test_synthesis_1_does_not_import_authority_stacks() -> None:
    forbidden_roots = frozenset(
        {
            "aiohttp",
            "anthropic",
            "asyncpg",
            "boto3",
            "database",
            "ftplib",
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
        "core.acquisition_",
        "core.bounded_lexical_search",
        "core.candidate_",
        "core.content_acquisition",
        "core.context_search_runtime",
        "core.context_selection",
        "core.direct_context_runtime",
        "core.direct_file_reader",
        "core.eligibility_policy",
        "core.evidence_",
        "core.file_candidate_selector",
        "core.graph",
        "core.index",
        "core.model",
        "core.ollama_client",
        "core.repo_librarian",
        "core.repository_inventory",
        "core.retriever",
        "core.semantic_waiter",
        "core.validation_execution",
        "database.",
        "graph.",
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


def test_synthesis_1_performs_no_filesystem_traversal_network_db_or_execution() -> None:
    forbidden_tails = frozenset(
        {
            "check_call",
            "check_output",
            "chat",
            "close",
            "commit",
            "complete",
            "connect",
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
            "flush",
            "fstat",
            "fwalk",
            "generate",
            "getaddrinfo",
            "glob",
            "iglob",
            "infer",
            "insert",
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
            "request",
            "retrieve",
            "rglob",
            "rmdir",
            "rollback",
            "run",
            "scandir",
            "search",
            "seek",
            "send",
            "socket",
            "spawn",
            "stat",
            "system",
            "unlink",
            "urlopen",
            "walk",
            "write",
            "write_bytes",
            "writelines",
            "write_text",
        }
    )
    forbidden_exact = frozenset(
        {
            "os.rename",
            "os.replace",
            "Path.rename",
            "Path.replace",
            "shutil.move",
            "shutil.rmtree",
        }
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name in forbidden_exact or name.rsplit(".", 1)[-1] in forbidden_tails:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_synthesis_1_binds_to_claim_records_but_cannot_assess_or_reverify() -> None:
    forbidden_calls = frozenset(
        {
            "acquire_selected_content",
            "adjudicate",
            "analyze",
            "assess_claim",
            "assess_evidence_set",
            "bounded_payload_view",
            "derive_candidate_eligibility",
            "execute_context_selection",
            "rank_candidates",
            "select_candidates",
            "verify_acquired_source",
            "verify_with_bounded_repair",
        }
    )
    forbidden_contracts = (
        "AcquiredSourcePayload",
        "BoundedPayloadView",
        "EvidenceSetAssessment",
        "EvidenceVerificationRequest",
        "EvidenceVerificationResult",
        "StaticEvidenceAnalyzer",
        "VerifiedEvidence",
    )
    bound: list[str] = []
    violations: list[str] = []
    for path, tree in _source_trees():
        source = path.read_text(encoding="utf-8")
        for module, line in _imported_modules(tree):
            if module.startswith("core.claim_assessment"):
                bound.append(f"{path.name}:{line}")
            if module.startswith(
                (
                    "core.acquisition_",
                    "core.candidate_",
                    "core.content_acquisition",
                    "core.evidence_",
                )
            ):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")
        for contract_name in forbidden_contracts:
            if contract_name in source:
                violations.append(f"{path.name}: names {contract_name}")

    assert bound, "SYNTHESIS.1 must consume the frozen CLAIM.1 contract"
    assert violations == [], violations


# -- No winner, scoring, confidence, voting, or inferred decision -------------

def test_no_synthesis_1_field_or_callable_is_winner_score_or_vote_shaped() -> None:
    banned_fragments = (
        "aggregate_confidence",
        "average",
        "confidence",
        "likelihood",
        "majority",
        "mean_",
        "outweigh",
        "outrank",
        "probability",
        "rank",
        "score",
        "strength",
        "stronger",
        "tally",
        "vote",
        "weight",
        "winner",
        "winning",
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
            for name in names:
                folded = name.casefold()
                if any(fragment in folded for fragment in banned_fragments):
                    violations.append(f"{path.name}: {name}")

            # A local tally has just as much decision power as a public field.
            # String guardrail denials are not Names and remain intentionally
            # outside this scan.
            if isinstance(node, (ast.Name, ast.arg)):
                identifier = node.id if isinstance(node, ast.Name) else node.arg
                folded = identifier.casefold()
                local_decision_fragments = (
                    "confidence",
                    "majority",
                    "score",
                    "status_count",
                    "support_count",
                    "tally",
                    "total_points",
                    "vote",
                    "weight",
                    "winner",
                    "wins",
                )
                if any(
                    fragment in folded for fragment in local_decision_fragments
                ):
                    violations.append(f"{path.name}:{node.lineno}: {identifier}")

    assert violations == [], violations


def _is_set_operand(node: ast.AST) -> bool:
    if isinstance(node, (ast.Set, ast.SetComp)):
        return True
    if isinstance(node, ast.Call):
        return (_qualified_name(node.func) or "").rsplit(".", 1)[-1] in {
            "frozenset",
            "set",
        }
    if isinstance(node, ast.Name):
        return node.id in {
            "actual_set",
            "bound_propositions",
            "expected_set",
            "expected_propositions",
            "represented",
        }
    return False


def test_synthesis_1_has_no_numeric_reduction_or_decision_arithmetic() -> None:
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
    numeric_operators = (
        ast.Add,
        ast.Div,
        ast.FloorDiv,
        ast.MatMult,
        ast.Mod,
        ast.Mult,
        ast.Pow,
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in banned_reductions:
                violations.append(f"{path.name}:{call.lineno}: {name}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp):
                continue
            if isinstance(node.op, numeric_operators):
                violations.append(
                    f"{path.name}:{node.lineno}: {type(node.op).__name__}"
                )
            if isinstance(node.op, ast.Sub) and not (
                _is_set_operand(node.left) and _is_set_operand(node.right)
            ):
                violations.append(
                    f"{path.name}:{node.lineno}: non-set subtraction"
                )

    assert violations == [], violations


def test_synthesis_status_vocabularies_contain_no_decision_outcome() -> None:
    from core.structured_synthesis import SLOT_STATUSES, SYNTHESIS_STATUSES

    banned = (
        "better",
        "confidence",
        "favorable",
        "loser",
        "recommendation_ready",
        "score",
        "strong",
        "true",
        "vote",
        "weak",
        "winner",
    )
    for value in (*SYNTHESIS_STATUSES, *SLOT_STATUSES):
        assert not any(fragment in value.casefold() for fragment in banned), value


# -- Bounded references, authority, and RESPONSE.1 exclusion ------------------

def test_structured_claim_references_have_no_source_or_generated_prose_field() -> None:
    import dataclasses

    from core.structured_synthesis import (
        BASIS_ANALYZER_ASSESSED,
        STATUS_SUPPORTED,
        ClaimAssessmentReference,
        SynthesisSlotResult,
    )

    reference_fields = {
        item.name for item in dataclasses.fields(ClaimAssessmentReference)
    }
    assert reference_fields == {
        "assessment_fingerprint",
        "proposition_id",
        "proposition_sha256",
        "assessment_status",
        "semantic_basis",
        "missing_requirements",
        "inconsistencies",
    }
    reference = ClaimAssessmentReference(
        assessment_fingerprint="a" * 64,
        proposition_id="P-1",
        proposition_sha256="b" * 64,
        assessment_status=STATUS_SUPPORTED,
        semantic_basis=BASIS_ANALYZER_ASSESSED,
    )
    assert set(reference.as_dict()) == reference_fields

    slot_fields = {item.name for item in dataclasses.fields(SynthesisSlotResult)}
    banned_fragments = (
        "answer_text",
        "citation",
        "content",
        "document",
        "excerpt",
        "explanation",
        "html",
        "markdown",
        "narrative",
        "paragraph",
        "path",
        "payload",
        "proposition_text",
        "prose",
        "recommendation_text",
        "response_text",
        "snippet",
        "source",
        "url",
    )
    for owner, field_names in (
        ("ClaimAssessmentReference", reference_fields),
        ("SynthesisSlotResult", slot_fields),
    ):
        for field_name in field_names:
            assert not any(
                fragment in field_name.casefold() for fragment in banned_fragments
            ), f"{owner}.{field_name}"


def test_forbidden_authorities_and_decision_result_are_not_settable() -> None:
    import dataclasses
    import inspect

    from core.structured_synthesis import (
        BINDING_EXPLICIT_TASK_CONTRACT,
        DECISION_COMPARATIVE_SELECTION,
        DecisionRequirement,
        StructuredSynthesis,
        synthesis_authority,
    )

    forbidden_authorities = {
        "decision_authority",
        "evidence_acquisition_authority",
        "evidence_verification_authority",
        "execution_authority",
        "final_claim_authority",
        "final_response_authority",
        "model_selection_authority",
        "network_authority",
        "patch_authority",
        "provider_selection_authority",
        "recommendation_authority",
        "repository_read_authority",
        "write_authority",
    }
    synthesis_fields = {item.name for item in dataclasses.fields(StructuredSynthesis)}
    assert forbidden_authorities.isdisjoint(synthesis_fields)
    for property_name in (
        "decision_authority",
        "final_claim_authority",
        "final_response_authority",
        "recommendation_authority",
    ):
        descriptor = getattr(StructuredSynthesis, property_name)
        assert isinstance(descriptor, property)
        assert descriptor.fset is None
        assert descriptor.fget(object.__new__(StructuredSynthesis)) is False

    parameters = inspect.signature(synthesis_authority).parameters
    assert set(parameters) == {"structured_synthesis_authority"}
    authority = synthesis_authority(structured_synthesis_authority=True)
    assert authority["structured_synthesis_authority"] is True
    assert authority["human_approval_required"] is True
    assert all(authority[name] is False for name in forbidden_authorities)

    decision_fields = {item.name for item in dataclasses.fields(DecisionRequirement)}
    assert "decision_performed" not in decision_fields
    assert isinstance(DecisionRequirement.decision_performed, property)
    requirement = DecisionRequirement(
        requested=True,
        type=DECISION_COMPARATIVE_SELECTION,
        provenance=BINDING_EXPLICIT_TASK_CONTRACT,
    )
    assert requirement.decision_performed is False


def test_synthesis_1_has_no_response_phase_or_prose_renderer() -> None:
    tree = _tree(_SYNTHESIS_SOURCE)
    violations: list[str] = []
    for module, line in _imported_modules(tree):
        folded = module.casefold()
        if "response" in folded or "renderer" in folded:
            violations.append(f"{_SYNTHESIS_SOURCE.name}:{line}: import {module}")
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            folded = node.name.casefold()
            if "response" in folded and node.name != "final_response_authority":
                violations.append(f"{_SYNTHESIS_SOURCE.name}:{node.lineno}: {node.name}")
            if any(
                fragment in folded
                for fragment in (
                    "compose_response",
                    "final_answer",
                    "generate_prose",
                    "generate_response",
                    "render_answer",
                    "render_final",
                    "response_phase",
                )
            ):
                violations.append(f"{_SYNTHESIS_SOURCE.name}:{node.lineno}: {node.name}")

    serializer = _function_node(tree, "render_structured_synthesis_json")
    serializer_calls = {
        name for _call, name in _calls(serializer)
    }
    assert serializer_calls <= {"TypeError", "json.dumps", "result.as_dict", "type"}
    assert "json.dumps" in serializer_calls
    assert not any(isinstance(node, ast.JoinedStr) for node in ast.walk(serializer))
    assert violations == [], violations


# -- Report-only: no application path may invoke the phase --------------------

_SYNTHESIS_1_MODULE_NAMES = frozenset({"structured_synthesis"})

_SYNTHESIS_1_ENTRY_POINTS = frozenset(
    {"compose_structured_synthesis", "render_structured_synthesis_json"}
)


def _production_python_files() -> Iterable[Path]:
    excluded = {path.resolve() for path in _SYNTHESIS_1_SOURCES}
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


def _is_synthesis_1_import(node: ast.AST) -> bool:
    qualified = {f"core.{name}" for name in _SYNTHESIS_1_MODULE_NAMES}
    if isinstance(node, ast.Import):
        return any(
            alias.name in _SYNTHESIS_1_MODULE_NAMES or alias.name in qualified
            for alias in node.names
        )
    if not isinstance(node, ast.ImportFrom):
        return False
    module = node.module or ""
    if module in _SYNTHESIS_1_MODULE_NAMES or module in qualified:
        return True
    return (module == "core" or (node.level and not module)) and any(
        alias.name in _SYNTHESIS_1_MODULE_NAMES for alias in node.names
    )


def test_synthesis_1_is_not_imported_or_called_by_a_live_production_path() -> None:
    callers: list[str] = []
    for path in _production_python_files():
        tree = _tree(path)
        reasons: set[str] = set()
        for node in ast.walk(tree):
            if _is_synthesis_1_import(node):
                reasons.add(f"import@{node.lineno}")
            if isinstance(node, ast.Call):
                name = _qualified_name(node.func) or ""
                if name.rsplit(".", 1)[-1] in _SYNTHESIS_1_ENTRY_POINTS:
                    reasons.add(f"call@{node.lineno}")
                if name == "getattr" and any(
                    isinstance(argument, ast.Constant)
                    and argument.value in _SYNTHESIS_1_ENTRY_POINTS
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-call@{node.lineno}")
                if name in {"__import__", "importlib.import_module"} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and (
                        argument.value in _SYNTHESIS_1_MODULE_NAMES
                        or argument.value
                        in {
                            f"core.{item}" for item in _SYNTHESIS_1_MODULE_NAMES
                        }
                    )
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-import@{node.lineno}")
        if reasons:
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            callers.append(f"{relative}: {', '.join(sorted(reasons))}")

    assert callers == [], callers
