"""Authoritative pre-candidate lexical bindings for ``safe_minimal``.

The patch snippet is not the whole lexical environment of a function.  This
module derives the small missing part from one authoritative Python source
file before candidate application: the target function's parameters and
existing locals, plus direct symbols imported by that module from modules that
can be proven repository-local by bounded path resolution.

It performs no import, module execution, repository walk, index query, model
call, network call, or mutation.  Failure to prove the target, source identity,
or import locality produces no context and preserves the legacy conservative
gate.
"""

from __future__ import annotations

import ast
import hashlib
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from core.immutable_result_fields import ImmutableResultProof, build_immutable_result_proof


PHASE_ID = "PATCH.MINIMAL.LIVE.3"
SCHEMA_VERSION = "patch_minimal_live_3_v1"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalized_relative_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return str(PurePosixPath(text)) if text else ""


def _is_bounded_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and not (
        path.parts and path.parts[0].endswith(":")
    )


def _normalized_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if "::" in text:
        text = text.rsplit("::", 1)[-1]
    return text


@dataclass(frozen=True, slots=True)
class RepositoryLocalDirectImport:
    """One baseline ``from module import name`` binding proven local."""

    bound_name: str
    imported_name: str
    module: str
    resolved_module_path: str

    def as_dict(self) -> dict[str, str]:
        return {
            "bound_name": self.bound_name,
            "imported_name": self.imported_name,
            "module": self.module,
            "resolved_module_path": self.resolved_module_path,
        }


@dataclass(frozen=True, slots=True)
class AuthoritativeBindingContext:
    """The immutable lexical environment owned by one baseline function."""

    source_path: str
    source_sha256: str
    target_symbol: str
    target_source_sha256: str
    target_start_line: int
    target_end_line: int
    parameter_names: tuple[str, ...] = ()
    existing_local_names: tuple[str, ...] = ()
    repository_local_direct_imports: tuple[RepositoryLocalDirectImport, ...] = ()
    immutable_result_proof: ImmutableResultProof | None = None
    construction_seconds: float = 0.0
    schema_version: str = SCHEMA_VERSION

    @property
    def repository_import_names(self) -> frozenset[str]:
        return frozenset(
            binding.bound_name for binding in self.repository_local_direct_imports
        )

    @property
    def known_binding_names(self) -> frozenset[str]:
        return frozenset(self.parameter_names) | frozenset(
            self.existing_local_names
        ) | self.repository_import_names

    def binding_kind(self, name: str) -> str:
        """Return the binding's lexical owner, respecting function shadowing."""

        if name in self.parameter_names:
            return "parameter"
        if name in self.existing_local_names:
            return "existing_local"
        if name in self.repository_import_names:
            return "repository_local_direct_import"
        return ""

    def is_current_for(
        self,
        *,
        authoritative_source: str,
        source_path: str,
        target_symbol: str,
        target_snippet: str,
    ) -> bool:
        """Whether this context still describes the candidate's baseline.

        The whole-file digest prevents reuse after any source replacement.  A
        bounded recorded line span then binds the candidate target snippet to
        the same function rather than merely to similar text elsewhere in the
        file.
        """

        if not isinstance(authoritative_source, str) or not authoritative_source:
            return False
        if _normalized_relative_path(source_path) != self.source_path:
            return False
        if _normalized_symbol(target_symbol) != self.target_symbol:
            return False
        if _sha256(authoritative_source) != self.source_sha256:
            return False
        target_source = _line_span(
            authoritative_source, self.target_start_line, self.target_end_line
        )
        if not target_source or _sha256(target_source) != self.target_source_sha256:
            return False
        return bool(target_snippet) and target_snippet in target_source and (
            self.immutable_result_proof is None or self.immutable_result_proof.is_current()
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": PHASE_ID,
            "schema_version": self.schema_version,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "target_symbol": self.target_symbol,
            "target_source_sha256": self.target_source_sha256,
            "target_start_line": self.target_start_line,
            "target_end_line": self.target_end_line,
            "parameter_names": list(self.parameter_names),
            "existing_local_names": list(self.existing_local_names),
            "repository_local_direct_imports": [
                binding.as_dict()
                for binding in self.repository_local_direct_imports
            ],
            "immutable_result_callable_proofs": [
                item.as_dict() for item in self.immutable_result_proof.callable_results
            ] if self.immutable_result_proof else [],
            "immutable_result_source_identities": list(
                self.immutable_result_proof.source_identities
            ) if self.immutable_result_proof else [],
        }

    def as_telemetry(self, *, current: bool) -> dict[str, Any]:
        return {
            "authoritative_binding_context_phase_id": PHASE_ID,
            "authoritative_binding_context_schema_version": self.schema_version,
            "authoritative_binding_context_current": bool(current),
            "authoritative_binding_context": self.as_dict(),
            "authoritative_binding_context_construction_seconds": (
                self.construction_seconds
            ),
            "authoritative_binding_context_model_calls": 0,
            "authoritative_binding_context_network_calls": 0,
            "authoritative_binding_context_repository_traversals": 0,
            "authoritative_binding_context_repository_mutations": 0,
            "immutable_result_return_type_proof_seconds": (
                self.immutable_result_proof.construction_seconds
                if self.immutable_result_proof else 0.0
            ),
        }


def _line_span(source: str, start_line: int, end_line: int) -> str:
    if start_line < 1 or end_line < start_line:
        return ""
    lines = source.splitlines(keepends=True)
    if end_line > len(lines):
        return ""
    return "".join(lines[start_line - 1 : end_line])


def _definition_index(tree: ast.Module) -> dict[str, ast.AST]:
    index: dict[str, ast.AST] = {}

    def descend(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualname = f"{prefix}.{child.name}" if prefix else child.name
                index[qualname] = child
                descend(child, qualname)
            else:
                descend(child, prefix)

    descend(tree, "")
    return index


def _target_function(tree: ast.Module, target_symbol: str) -> ast.AST | None:
    wanted = _normalized_symbol(target_symbol)
    if not wanted:
        return None
    functions = {
        name: node
        for name, node in _definition_index(tree).items()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    exact = functions.get(wanted)
    if exact is not None:
        return exact
    suffix = [node for name, node in functions.items() if name.rsplit(".", 1)[-1] == wanted]
    return suffix[0] if len(suffix) == 1 else None


def _argument_names(node: ast.AST) -> tuple[str, ...]:
    args = getattr(node, "args", None)
    if args is None:
        return ()
    names: list[str] = []
    for group in (args.posonlyargs, args.args, args.kwonlyargs):
        names.extend(arg.arg for arg in group)
    for extra in (args.vararg, args.kwarg):
        if extra is not None:
            names.append(extra.arg)
    return tuple(sorted(set(names)))


class _FunctionLocalCollector(ast.NodeVisitor):
    """Collect bindings owned by one function without entering child scopes."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.scope_declarations: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.names.add(alias.asname or alias.name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.scope_declarations.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.scope_declarations.update(node.names)

    def _visit_comprehension_scope(
        self,
        *,
        generators: Iterable[ast.comprehension],
        values: Iterable[ast.AST],
    ) -> None:
        # Python 3 comprehension iteration targets live in their own scope.
        # Visit expressions (including a possible named expression), but never
        # misclassify the generator target as a local of the target function.
        for generator in generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for value in values:
            self.visit(value)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_scope(
            generators=node.generators, values=(node.elt,)
        )

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_scope(
            generators=node.generators, values=(node.elt,)
        )

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_scope(
            generators=node.generators, values=(node.elt,)
        )

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_scope(
            generators=node.generators, values=(node.key, node.value)
        )


def _existing_locals(node: ast.AST, parameters: Iterable[str]) -> tuple[str, ...]:
    collector = _FunctionLocalCollector()
    for statement in getattr(node, "body", ()):
        collector.visit(statement)
    return tuple(
        sorted(
            collector.names
            - collector.scope_declarations
            - set(parameters)
        )
    )


def _candidate_function_bindings(
    tree: ast.Module,
    context: AuthoritativeBindingContext,
) -> frozenset[str]:
    target = _target_function(tree, context.target_symbol)
    if target is not None:
        parameters = _argument_names(target)
        return frozenset(parameters) | frozenset(_existing_locals(target, parameters))

    # A body-only candidate parses as module statements after dedenting, but
    # those statements still execute in the authoritative function scope.
    collector = _FunctionLocalCollector()
    for statement in tree.body:
        collector.visit(statement)
    return frozenset(collector.names - collector.scope_declarations)


def resolve_authoritative_candidate_bindings(
    context: AuthoritativeBindingContext,
    *,
    patched_snippet: str,
) -> frozenset[str]:
    """Names this candidate actually resolves to the frozen baseline.

    Existing function locals and parameters win over module bindings.  A new
    candidate local shadows a same-named module import exactly as Python does,
    so that spelling is left to PATCH.MINIMAL.LIVE.2's bounded-local analysis.
    Attribute occurrences are resolved separately by the immutable result-field
    proof; a known binding alone never proves a member.
    """

    try:
        tree = ast.parse(patched_snippet)
    except (SyntaxError, ValueError):
        try:
            tree = ast.parse(textwrap.dedent(patched_snippet))
        except (SyntaxError, ValueError):
            return frozenset()

    candidate_bindings = _candidate_function_bindings(tree, context)
    function_names = frozenset(context.parameter_names) | frozenset(
        context.existing_local_names
    )
    eligible_module_names = context.repository_import_names - candidate_bindings
    eligible_loads = function_names | eligible_module_names
    resolved: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in eligible_loads:
                resolved.add(node.id)
        elif isinstance(node, ast.keyword) and node.arg in function_names:
            # The old gate is spelling-based for keyword names.  Carrying a
            # target-function binding of that exact spelling restores body/full
            # parity without admitting unrelated new keyword surfaces.
            resolved.add(str(node.arg))
    return frozenset(resolved)


def _module_candidates(
    repo_root: Path,
    target_path: Path,
    node: ast.ImportFrom,
) -> tuple[Path, ...]:
    module_parts = tuple(part for part in (node.module or "").split(".") if part)
    if node.level:
        base = target_path.parent
        for _ in range(node.level - 1):
            base = base.parent
    else:
        base = repo_root
    module_base = base.joinpath(*module_parts)
    candidates = (module_base.with_suffix(".py"), module_base / "__init__.py")
    bounded: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(repo_root)
        except (OSError, ValueError):
            continue
        bounded.append(resolved)
    return tuple(bounded)


def _repository_local_imports(
    tree: ast.Module,
    *,
    repo_root: Path,
    target_path: Path,
) -> tuple[RepositoryLocalDirectImport, ...]:
    bindings: list[RepositoryLocalDirectImport] = []
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom):
            continue
        candidates = _module_candidates(repo_root, target_path, statement)
        resolved = next((path for path in candidates if path.is_file()), None)
        if resolved is None:
            continue
        try:
            relative = resolved.relative_to(repo_root).as_posix()
        except ValueError:
            continue
        rendered_module = "." * statement.level + (statement.module or "")
        for alias in statement.names:
            if alias.name == "*":
                continue
            bindings.append(
                RepositoryLocalDirectImport(
                    bound_name=alias.asname or alias.name,
                    imported_name=alias.name,
                    module=rendered_module,
                    resolved_module_path=relative,
                )
            )
    unique = {
        (item.bound_name, item.imported_name, item.module, item.resolved_module_path): item
        for item in bindings
    }
    return tuple(unique[key] for key in sorted(unique))


def build_authoritative_binding_context(
    *,
    repo_root: str | Path,
    source_path: str,
    target_symbol: str,
    authoritative_source: str,
) -> AuthoritativeBindingContext | None:
    """Build a context from one already-acquired pre-candidate source file."""

    started = time.perf_counter()
    if not isinstance(authoritative_source, str) or not authoritative_source:
        return None
    root = Path(repo_root).resolve()
    normalized_path = _normalized_relative_path(source_path)
    if not _is_bounded_relative_path(normalized_path):
        return None
    try:
        target_path = (root / normalized_path).resolve()
        target_path.relative_to(root)
        tree = ast.parse(authoritative_source)
    except (OSError, ValueError, SyntaxError):
        return None
    target = _target_function(tree, target_symbol)
    if target is None:
        return None
    start_line = int(getattr(target, "lineno", 0) or 0)
    end_line = int(getattr(target, "end_lineno", 0) or 0)
    target_source = _line_span(authoritative_source, start_line, end_line)
    if not target_source:
        return None
    parameters = _argument_names(target)
    direct_imports = _repository_local_imports(
        tree, repo_root=root, target_path=target_path
    )
    result_proof = build_immutable_result_proof(
        repo_root=root, target_path=target_path, target_tree=tree,
        direct_imports=direct_imports,
    )
    return AuthoritativeBindingContext(
        source_path=normalized_path,
        source_sha256=_sha256(authoritative_source),
        target_symbol=_normalized_symbol(target_symbol),
        target_source_sha256=_sha256(target_source),
        target_start_line=start_line,
        target_end_line=end_line,
        parameter_names=parameters,
        existing_local_names=_existing_locals(target, parameters),
        repository_local_direct_imports=direct_imports,
        immutable_result_proof=result_proof,
        construction_seconds=round(time.perf_counter() - started, 6),
    )


def load_authoritative_binding_context(
    *,
    repo_root: str | Path,
    source_path: str,
    target_symbol: str,
) -> tuple[AuthoritativeBindingContext | None, str]:
    """Read exactly one named target file, then build its frozen context."""

    root = Path(repo_root).resolve()
    normalized_path = _normalized_relative_path(source_path)
    if not _is_bounded_relative_path(normalized_path):
        return None, ""
    try:
        path = (root / normalized_path).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None, ""
    if not path.is_file():
        return None, ""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, ""
    context = build_authoritative_binding_context(
        repo_root=root,
        source_path=normalized_path,
        target_symbol=target_symbol,
        authoritative_source=source,
    )
    return context, source


__all__ = [
    "PHASE_ID",
    "SCHEMA_VERSION",
    "AuthoritativeBindingContext",
    "RepositoryLocalDirectImport",
    "build_authoritative_binding_context",
    "load_authoritative_binding_context",
    "resolve_authoritative_candidate_bindings",
]
