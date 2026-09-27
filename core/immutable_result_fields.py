"""Bounded, baseline-only proof of frozen dataclass result-field reads.

This is annotation/declaration proof, not a Python type checker. Only direct
repository imports of undecorated synchronous functions, returning a named
repository-local frozen dataclass, participate. No module is executed. Source
snapshots and their identities belong to AuthoritativeBindingContext.
"""

from __future__ import annotations

import ast
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.authoritative_binding_context import AuthoritativeBindingContext


PROVEN_IMMUTABLE_RESULT_FIELD_READ = "proven_immutable_result_field_read"
MAX_PROOF_FILES = 16
MAX_SOURCE_BYTES = 262_144
MAX_TOTAL_SOURCE_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class CallableResultFields:
    bound_name: str
    type_name: str
    type_source_path: str
    field_names: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "bound_name": self.bound_name,
            "type_name": self.type_name,
            "type_source_path": self.type_source_path,
            "field_names": list(self.field_names),
        }


@dataclass(frozen=True, slots=True)
class ImmutableResultProof:
    repo_root: str = ""
    source_identities: tuple[tuple[str, str], ...] = ()
    callable_results: tuple[CallableResultFields, ...] = ()
    construction_seconds: float = 0.0

    def is_current(self) -> bool:
        root = Path(self.repo_root)
        try:
            for relative, digest in self.source_identities:
                path = (root / relative).resolve()
                path.relative_to(root)
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    return False
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    return False
        except (OSError, ValueError):
            return False
        return True


def _bindings(tree: ast.AST) -> dict[str, list[ast.AST]]:
    """Lexical writes, including conditional/repeated bindings; no child scopes."""
    result: dict[str, list[ast.AST]] = {}

    def add(name: str, node: ast.AST) -> None:
        result.setdefault(name, []).append(node)

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(node.name, node)
            return
        if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp)):
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                add(alias.asname or alias.name.split(".")[0], node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            add(node.id, node)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            add(node.name, node)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                add(name, node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in tree.body:
        visit(statement)
    return result


def _unique_definition(tree: ast.Module, name: str, kind: type) -> ast.AST | None:
    writes = _bindings(tree).get(name, [])
    if len(writes) == 1 and isinstance(writes[0], kind) and writes[0] in tree.body:
        return writes[0]
    return None


def _simple_annotation(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # A single quoted identifier, never eval or a general expression parser.
        if node.value.isidentifier():
            return node.value
    return ""


def _dataclass_decorator(tree: ast.Module, node: ast.AST) -> bool:
    bindings = _bindings(tree)
    if isinstance(node, ast.Name):
        writes = bindings.get(node.id, [])
        return len(writes) == 1 and isinstance(writes[0], ast.ImportFrom) and (
            writes[0] in tree.body and writes[0].level == 0
            and writes[0].module == "dataclasses"
            and any(a.name == "dataclass" and (a.asname or a.name) == node.id
                    for a in writes[0].names)
        )
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        writes = bindings.get(node.value.id, [])
        return node.attr == "dataclass" and len(writes) == 1 and (
            isinstance(writes[0], ast.Import) and writes[0] in tree.body
            and any(a.name == "dataclasses" and (a.asname or a.name) == node.value.id
                    for a in writes[0].names)
        )
    return False


def _record_fields(tree: ast.Module, record: ast.ClassDef) -> tuple[str, ...]:
    if record.bases or record.keywords or len(record.decorator_list) != 1:
        return ()
    decorator = record.decorator_list[0]
    if not isinstance(decorator, ast.Call) or decorator.args:
        return ()
    if not _dataclass_decorator(tree, decorator.func):
        return ()
    options = {kw.arg: kw.value for kw in decorator.keywords}
    if len(options) != len(decorator.keywords) or set(options) - {"frozen", "slots"}:
        return ()
    if not isinstance(options.get("frozen"), ast.Constant) or options["frozen"].value is not True:
        return ()
    if any(not isinstance(v, ast.Constant) or type(v.value) is not bool
           for v in options.values()):
        return ()
    # No inheritance, custom access hooks, class-body execution, or arbitrary
    # decorators. Ordinary methods/properties may exist but are never fields.
    writes = _bindings(record)
    module_bindings = _bindings(tree)
    if any(name in writes for name in ("__getattr__", "__getattribute__", "__slots__")):
        return ()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            if isinstance(node.value, ast.Name) and node.value.id == record.name:
                return ()
        if isinstance(node, ast.Call) and any(
            isinstance(arg, ast.Name) and arg.id == record.name for arg in node.args
        ) and isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"}:
            return ()
    for statement in record.body:
        if isinstance(statement, ast.FunctionDef) and any(
            not isinstance(d, ast.Name) or d.id != "property" or "property" in module_bindings
            for d in statement.decorator_list
        ):
            return ()
        if not isinstance(statement, (ast.AnnAssign, ast.FunctionDef, ast.Pass)) and not (
            isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            return ()
    fields = []
    for statement in record.body:
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
            continue
        name = statement.target.id
        if name.startswith("__") or len(writes.get(name, [])) != 1:
            continue
        # A literal/no default cannot install a descriptor. Nonliteral defaults
        # are unsupported, even when they might name a harmless constant.
        if statement.value is not None and not isinstance(statement.value, ast.Constant):
            continue
        # Subscripts (ClassVar/InitVar, including aliases) and complex quoted
        # annotations are outside this initial record shape. Plain names must
        # not alias those pseudo-fields either.
        annotation = statement.annotation
        names = [n.id for n in ast.walk(annotation) if isinstance(n, ast.Name)]
        if isinstance(annotation, ast.Constant):
            simple = _simple_annotation(annotation)
            if not simple:
                continue
            names = [simple]
        if any(isinstance(n, (ast.Subscript, ast.Call, ast.Attribute)) for n in ast.walk(annotation)):
            continue
        # Imported aliases can conceal ClassVar/InitVar. Only unshadowed
        # builtin data annotations or directly declared local classes are
        # transparent here; resolving arbitrary field-type aliases is deferred.
        builtin_data = {"str", "bytes", "int", "float", "bool", "object", "tuple", "list", "dict", "set"}
        if any(not (
            n in builtin_data and n not in module_bindings
            or len(module_bindings.get(n, [])) == 1
            and isinstance(module_bindings[n][0], ast.ClassDef)
        ) for n in names):
            continue
        fields.append(name)
    return tuple(sorted(fields))


def build_immutable_result_proof(*, repo_root: Path, target_path: Path,
                                 target_tree: ast.Module, direct_imports: tuple) -> ImmutableResultProof:
    """At most 16 exact files / 1 MiB; one direct type-import hop, no search."""
    from core.authoritative_binding_context import _module_candidates

    started = time.perf_counter()
    # The recognized decorator must not resolve to a repository lookalike.
    if any(p.is_file() for p in (repo_root / "dataclasses.py", repo_root / "dataclasses/__init__.py")):
        return ImmutableResultProof()
    cache: dict[Path, ast.Module | None] = {}
    identities: dict[str, str] = {}
    total_bytes = 0

    def read(path: Path) -> ast.Module | None:
        nonlocal total_bytes
        try:
            path = path.resolve()
            relative = path.relative_to(repo_root).as_posix()
            if path in cache:
                return cache[path]
            if len(cache) >= MAX_PROOF_FILES:
                return None
            cache[path] = None
            size = path.stat().st_size
            if size > MAX_SOURCE_BYTES or total_bytes + size > MAX_TOTAL_SOURCE_BYTES:
                return None
            raw = path.read_bytes()
            if len(raw) > MAX_SOURCE_BYTES or total_bytes + len(raw) > MAX_TOTAL_SOURCE_BYTES:
                return None
            total_bytes += len(raw)
            parsed = ast.parse(raw)
            if any(isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)
                   for n in ast.walk(parsed)):
                return None
            identities[relative] = hashlib.sha256(raw).hexdigest()
            cache[path] = parsed
            return parsed
        except (OSError, ValueError, SyntaxError):
            return None

    results = []
    baseline_bindings = _bindings(target_tree)
    if "*" in baseline_bindings:
        return ImmutableResultProof()
    for binding in direct_imports:
        writes = baseline_bindings.get(binding.bound_name, [])
        if len(writes) != 1 or not isinstance(writes[0], ast.ImportFrom) or writes[0] not in target_tree.body:
            continue
        paths = [p for p in _module_candidates(repo_root, target_path, writes[0]) if p.is_file()]
        if len(paths) != 1:
            continue
        path = repo_root / binding.resolved_module_path
        tree = read(path)
        if tree is None:
            continue
        function = _unique_definition(tree, binding.imported_name, ast.FunctionDef)
        if function is None or function.decorator_list or any(
            isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(function)
        ):
            continue
        type_name = _simple_annotation(function.returns)
        if not type_name:
            continue
        record_tree, record_path = tree, path
        record = _unique_definition(tree, type_name, ast.ClassDef)
        if record is None:
            writes = _bindings(tree).get(type_name, [])
            if len(writes) != 1 or not isinstance(writes[0], ast.ImportFrom) or writes[0] not in tree.body:
                continue
            imp = writes[0]
            aliases = [a for a in imp.names if (a.asname or a.name) == type_name]
            if len(aliases) != 1 or aliases[0].name == "*":
                continue
            paths = [p for p in _module_candidates(repo_root, path, imp) if p.is_file()]
            if len(paths) != 1:
                continue
            record_path = paths[0]
            record_tree = read(record_path)
            if record_tree is None:
                continue
            type_name = aliases[0].name
            record = _unique_definition(record_tree, type_name, ast.ClassDef)
        if record is None:
            continue
        fields = _record_fields(record_tree, record)
        if fields:
            results.append(CallableResultFields(
                binding.bound_name, type_name,
                record_path.relative_to(repo_root).as_posix(), fields,
            ))
    return ImmutableResultProof(
        str(repo_root), tuple(sorted(identities.items())), tuple(results),
        time.perf_counter() - started,
    )


def proven_field_read_nodes(tree: ast.Module, context: AuthoritativeBindingContext) -> frozenset[ast.Attribute]:
    """Occurrence proof, never a spelling allowlist or general dataflow.

    Local results must be assigned exactly once in the supplied straight-line
    function body, before every read, and used only as field receivers. A local
    established outside the supplied fragment is deliberately not inferred.
    """
    proof = context.immutable_result_proof
    if proof is None:
        return frozenset()
    body = tree.body
    if len(body) == 1 and isinstance(body[0], ast.FunctionDef):
        if body[0].name != context.target_symbol.rsplit(".", 1)[-1]:
            return frozenset()
        function = body[0]
        body = function.body
        if function.decorator_list:
            return frozenset()
    elif any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in body):
        return frozenset()
    # Bounded straight-line form. No branch, nested scope, suspension, or
    # comprehension binding can complicate provenance in this slice.
    if any(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Return, ast.Expr, ast.Pass)) for n in body):
        return frozenset()
    nodes = [n for statement in body for n in ast.walk(statement)]
    if any(isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
                          ast.GeneratorExp, ast.NamedExpr, ast.Await, ast.Yield, ast.YieldFrom)) for n in nodes):
        return frozenset()
    parents = {child: n for n in nodes for child in ast.iter_child_nodes(n)}
    writes = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
    eligible = {p.bound_name: p for p in proof.callable_results if (
        context.binding_kind(p.bound_name) == "repository_local_direct_import"
        and p.bound_name not in writes
    )}

    def call_proof(node: ast.AST) -> CallableResultFields | None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return eligible.get(node.func.id)
        return None

    local_results = {}
    for statement in body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        name = statement.targets[0]
        if not isinstance(name, ast.Name) or name.id in context.parameter_names:
            continue
        bindings = [n for n in nodes if isinstance(n, ast.Name) and n.id == name.id
                    and isinstance(n.ctx, (ast.Store, ast.Del))]
        reads = [n for n in nodes if isinstance(n, ast.Name) and n.id == name.id
                 and isinstance(n.ctx, ast.Load)]
        if len(bindings) != 1 or any(
            not isinstance(parents.get(n), ast.Attribute) or parents[n].value is not n
            or n.lineno <= statement.end_lineno for n in reads
        ):
            continue
        origin = call_proof(statement.value)
        if origin is not None:
            local_results[name.id] = origin

    admitted = set()
    for node in nodes:
        if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Load):
            continue
        statement = node
        while statement in parents:
            statement = parents[statement]
        # This slice exports data in return expressions. It does not confer
        # callable authority through a field-to-local alias assignment.
        if not isinstance(statement, ast.Return):
            continue
        parent = parents.get(node)
        if (isinstance(parent, ast.Call) and parent.func is node) or (
            isinstance(parent, (ast.Attribute, ast.Subscript)) and parent.value is node
        ):
            continue
        origin = call_proof(node.value)
        if isinstance(node.value, ast.Name):
            origin = local_results.get(node.value.id)
        if origin is not None and node.attr in origin.field_names:
            admitted.add(node)
    return frozenset(admitted)
