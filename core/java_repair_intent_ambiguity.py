"""Small Java syntax projection for compiler-located state ownership questions.

Only declarations and identifiers in the fingerprinted source are inspected.  A
compiler diagnostic is required for every reported ambiguity.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


_STATIC_INSTANCE = re.compile(
    r"^non-static variable ([A-Za-z_$][\w$]*) cannot be referenced from a static context$"
)


@dataclass(frozen=True, slots=True)
class JavaDeclaration:
    file: str
    name: str
    owner: str
    kind: str
    lexical_scope: str
    source_fingerprint: str
    start_byte: int
    end_byte: int
    is_static: bool = False


@dataclass(frozen=True, slots=True)
class JavaOwnershipEvidence:
    kind: str
    diagnostic_owner: str
    diagnostic_ordinal: int
    declaration: JavaDeclaration


def _text(raw: bytes, node: Any) -> str:
    return raw[node.start_byte:node.end_byte].decode("utf-8")


def _class_of(node: Any) -> Any | None:
    current = node.parent
    while current is not None:
        if current.type == "class_declaration":
            return current
        current = current.parent
    return None


def _static(node: Any, raw: bytes) -> bool:
    modifiers = next((item for item in node.children if item.type == "modifiers"), None)
    return bool(modifiers and any(item.type == "static" for item in modifiers.children))


def _at_diagnostic(root: Any, raw: bytes, line: int, col: int) -> Any | None:
    # javac columns count Unicode characters; Tree-sitter columns count UTF-8
    # bytes.  Translate within this exact source line before querying the AST.
    lines = raw.splitlines(keepends=True)
    if not 1 <= line <= len(lines) or col < 1:
        return None
    decoded = lines[line - 1].decode("utf-8")
    if col > len(decoded):
        return None
    byte_col = len(decoded[:col - 1].encode("utf-8"))
    point = (line - 1, byte_col)
    node = root.descendant_for_point_range(point, point)
    return node if node.type == "identifier" and node.start_point == point else None


def project_java_ownership_evidence(*, raw: bytes, file: str,
                                    source_fingerprint: str,
                                    scope: Mapping[str, Any]) -> tuple[JavaOwnershipEvidence, ...]:
    """Project only exact measured methods, local declarations and class fields."""
    try:
        from tree_sitter_language_pack import get_parser

        root = get_parser("java").parse(raw).root_node
        if root.has_error:
            return ()
        nodes: list[Any] = []
        def visit(node: Any) -> None:
            if node.type in {"method_declaration", "field_declaration", "local_variable_declaration"}:
                nodes.append(node)
            for child in node.named_children:
                visit(child)
        visit(root)
        methods: dict[str, Any] = {}
        for member in scope.get("members") or ():
            if member.get("file") != file:
                continue
            name = member.get("symbol")
            span = member.get("span") or {}
            matches = [node for node in nodes if node.type == "method_declaration"
                       and _text(raw, node.child_by_field_name("name")) == name
                       and node.start_point.row + 1 == span.get("start_line")
                       and node.end_point.row + 1 == span.get("end_line")
                       and _text(raw, node).replace("\r\n", "\n").replace("\r", "\n")
                           == member.get("source_snippet")]
            if len(matches) != 1 or name in methods:
                return ()
            methods[name] = matches[0]
        if not methods:
            return ()
        declarations: list[tuple[JavaDeclaration, Any]] = []
        for node in nodes:
            if node.type not in {"field_declaration", "local_variable_declaration"}:
                continue
            owner_node = _class_of(node)
            if owner_node is None:
                continue
            method = next((method for method in methods.values()
                           if method.start_byte <= node.start_byte < node.end_byte <= method.end_byte), None)
            if node.type == "local_variable_declaration" and method is None:
                continue
            # V1 proves method-body locals only. A declaration in a nested
            # block has a narrower lifetime that this projection does not model.
            if (node.type == "local_variable_declaration"
                    and node.parent != method.child_by_field_name("body")):
                continue
            if node.type == "field_declaration" and method is not None:
                continue
            owner = _text(raw, method.child_by_field_name("name")) if method else _text(
                raw, owner_node.child_by_field_name("name"))
            lexical_node = (method.child_by_field_name("body") if method else
                            owner_node.child_by_field_name("body"))
            for declarator in node.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name_node = declarator.child_by_field_name("name")
                if name_node is None or name_node.type != "identifier":
                    continue
                declarations.append((JavaDeclaration(
                    file, _text(raw, name_node), owner,
                    "local" if method else "field",
                    ("method_body" if method else "class_body") +
                    f":{lexical_node.start_byte}:{lexical_node.end_byte}",
                    source_fingerprint, name_node.start_byte, name_node.end_byte,
                    _static(node, raw) if method is None else False,
                ), owner_node))
        evidence: list[JavaOwnershipEvidence] = []
        for member in scope.get("members") or ():
            owner = member.get("symbol")
            method = methods.get(owner)
            if method is None:
                continue
            method_class = _class_of(method)
            for ordinal, diagnostic in enumerate(member.get("diagnostics") or (), 1):
                if (diagnostic.get("file") != file or diagnostic.get("kind") != "compiler_error"
                        or diagnostic.get("severity") != "error"):
                    continue
                line, col = diagnostic.get("line"), diagnostic.get("col")
                if not isinstance(line, int) or not isinstance(col, int):
                    continue
                identifier = _at_diagnostic(root, raw, line, col)
                if identifier is None or not (method.start_byte <= identifier.start_byte < method.end_byte):
                    continue
                name = _text(raw, identifier)
                same_class = [(declaration, cls) for declaration, cls in declarations
                              if declaration.name == name and cls == method_class]
                message = diagnostic.get("message")
                if message == "cannot find symbol":
                    # An existing class field is visible here; the same spelling
                    # in another method does not establish a cross-local defect.
                    if any(item.kind == "field" for item, _ in same_class):
                        continue
                    locals_elsewhere = [item for item, _ in same_class
                                        if item.kind == "local" and item.owner != owner]
                    if len(locals_elsewhere) == 1:
                        evidence.append(JavaOwnershipEvidence(
                            "cross_member_local_reference", owner, ordinal, locals_elsewhere[0]))
                elif (match := _STATIC_INSTANCE.fullmatch(str(message or ""))) and match[1] == name:
                    if not _static(method, raw):
                        continue
                    fields = [item for item, _ in same_class
                              if item.kind == "field" and not item.is_static]
                    if len(fields) == 1:
                        evidence.append(JavaOwnershipEvidence(
                            "static_instance_state_ambiguity", owner, ordinal, fields[0]))
        return tuple(evidence)
    except (ImportError, UnicodeError, AttributeError, TypeError, ValueError):
        return ()
