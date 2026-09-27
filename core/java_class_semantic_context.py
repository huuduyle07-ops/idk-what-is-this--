"""Java tree-sitter adapter for CTX.OOP.1A's exact-buffer projection."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from core.class_semantic_context import (
    MAX_CONSTRUCTORS, MAX_FIELDS, MAX_METHODS, MAX_RELATIONS,
    CallableSemantic, ClassIdentity, ClassRelation, ClassSemanticContext,
    FieldSemantic, ParameterSemantic, SourceSpan, TargetIdentity,
)


_CLASSES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}
_CALLABLES = {"method_declaration", "constructor_declaration"}


def _text(raw: bytes, node: Any | None) -> str:
    return raw[node.start_byte:node.end_byte].decode("utf-8") if node is not None else ""


def _span(node: Any) -> SourceSpan:
    return SourceSpan(node.start_byte, node.end_byte,
                      node.start_point.row + 1, node.end_point.row + 1)


def _hash(raw: bytes, node: Any) -> str:
    return hashlib.sha256(raw[node.start_byte:node.end_byte]).hexdigest()


def _modifiers(node: Any) -> set[str]:
    modifiers = next((child for child in node.children if child.type == "modifiers"), None)
    return {child.type for child in modifiers.children} if modifiers is not None else set()


def _visibility(modifiers: set[str]) -> str:
    return next((item for item in ("public", "protected", "private") if item in modifiers), "package")


def _name(node: Any, raw: bytes) -> str:
    return _text(raw, node.child_by_field_name("name"))


def _class_ancestors(node: Any) -> list[Any]:
    ancestors = []
    current = node
    while current is not None:
        if current.type in _CLASSES:
            ancestors.append(current)
        current = current.parent
    return ancestors


def _parameters(node: Any, raw: bytes) -> tuple[ParameterSemantic, ...]:
    params = node.child_by_field_name("parameters")
    if params is None:
        return ()
    result = []
    for child in params.named_children:
        if child.type not in {"formal_parameter", "spread_parameter", "receiver_parameter"}:
            continue
        declared_type = _text(raw, child.child_by_field_name("type"))
        name = _text(raw, child.child_by_field_name("name"))
        if not name:
            name = _text(raw, child.named_children[-1]) if child.named_children else ""
        if not declared_type:
            declared_type = _text(raw, child)
        result.append(ParameterSemantic(name, declared_type))
    return tuple(result)


def _callable(node: Any, raw: bytes) -> CallableSemantic:
    modifiers = _modifiers(node)
    constructor = node.type == "constructor_declaration"
    return CallableSemantic(
        name=_name(node, raw), parameters=_parameters(node, raw),
        return_type=None if constructor else _text(raw, node.child_by_field_name("type")),
        visibility=_visibility(modifiers),
        ownership="static" if "static" in modifiers else "instance",
        is_final="final" in modifiers, is_abstract="abstract" in modifiers,
        span=_span(node),
    )


def _field_nodes(body: Any) -> list[Any]:
    return [child for child in body.named_children if child.type == "field_declaration"]


def _fields(body: Any, raw: bytes) -> list[FieldSemantic]:
    fields = []
    for declaration in _field_nodes(body):
        modifiers = _modifiers(declaration)
        declared_type = _text(raw, declaration.child_by_field_name("type"))
        for declarator in declaration.named_children:
            if declarator.type != "variable_declarator":
                continue
            name = _text(raw, declarator.child_by_field_name("name"))
            if name:
                fields.append(FieldSemantic(
                    name=name, declared_type=declared_type,
                    ownership="static" if "static" in modifiers else "instance",
                    visibility=_visibility(modifiers), is_final="final" in modifiers,
                    span=_span(declaration), declaration_fingerprint=_hash(raw, declaration),
                ))
    return fields


def _local_names(method: Any, raw: bytes) -> set[str]:
    names = {parameter.name for parameter in _parameters(method, raw)}
    body = method.child_by_field_name("body")
    if body is None:
        return names

    def walk(node: Any) -> None:
        if node.type in _CLASSES:
            return
        if node.type in {"local_variable_declaration", "enhanced_for_statement", "catch_formal_parameter"}:
            for child in node.named_children:
                if child.type == "variable_declarator":
                    names.add(_text(raw, child.child_by_field_name("name")))
                elif node.type == "catch_formal_parameter" and child.type == "identifier":
                    names.add(_text(raw, child))
        for child in node.named_children:
            walk(child)

    walk(body)
    return names


def _field_usage(method: Any, raw: bytes, field_names: set[str]) -> dict[str, str]:
    """Conservative syntax facts; ambiguous shadowed bare names are omitted."""
    body = method.child_by_field_name("body")
    if body is None:
        return {}
    shadowed = _local_names(method, raw)
    usage: dict[str, set[str]] = {}

    def access(node: Any) -> str:
        current = node
        while current is not None and current != body:
            parent = current.parent
            if parent is None:
                break
            if parent.type == "update_expression":
                return "read_write"
            if parent.type == "assignment_expression" and parent.child_by_field_name("left") == current:
                operator = raw[current.end_byte:parent.child_by_field_name("right").start_byte].strip()
                return "write" if operator == b"=" else "read_write"
            current = parent
        return "read"

    def add(name: str, node: Any) -> None:
        if name in field_names:
            usage.setdefault(name, set()).add(access(node))

    def walk(node: Any) -> None:
        if node.type in _CLASSES:
            return
        if node.type == "field_access":
            obj = node.child_by_field_name("object")
            field = node.child_by_field_name("field")
            if obj is not None and obj.type == "this" and field is not None:
                add(_text(raw, field), node)
            # A field on an unrelated receiver is not a field of this class.
            return
        if node.type == "identifier":
            name = _text(raw, node)
            parent = node.parent
            if (name in field_names and name not in shadowed and parent is not None
                    and not (parent.type == "variable_declarator" and parent.child_by_field_name("name") == node)
                    and not (parent.type == "method_invocation" and parent.child_by_field_name("name") == node)
                    and parent.type not in {"class_literal", "method_reference"}):
                add(name, node)
        for child in node.named_children:
            walk(child)

    walk(body)
    result = {}
    for name, modes in usage.items():
        result[name] = "read_write" if "read_write" in modes or modes == {"read", "write"} else next(iter(modes))
    return result


def project_java_class_semantic_context(
    *, raw: bytes, target: Mapping[str, Any], language: str, file: str,
    repository_id: str | None, source_fingerprint: str,
) -> ClassSemanticContext:
    base = dict(language=language, file=file, repository_id=repository_id,
                source_fingerprint=source_fingerprint)
    try:
        from tree_sitter_language_pack import get_parser

        root = get_parser("java").parse(raw).root_node
        if root.has_error:
            return ClassSemanticContext(**base, status="unavailable")
    except (ImportError, TypeError, ValueError, AttributeError):
        return ClassSemanticContext(**base, status="unavailable")

    try:
        kind, name = target["kind"], target["name"]
        start, end = target["start"], target["end"]
    except (KeyError, TypeError):
        return ClassSemanticContext(**base, status="unavailable")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
        return ClassSemanticContext(**base, status="unavailable")
    matches = []

    def find(node: Any) -> None:
        expected_kind = "function" if node.type in _CALLABLES else {
            "class_declaration": "class", "interface_declaration": "interface",
            "enum_declaration": "enum", "record_declaration": "record",
        }.get(node.type)
        exact_snippet = isinstance(target.get("content"), str) and target["content"] == _text(raw, node)
        if (expected_kind == kind and node.start_byte == start and node.end_byte == end
                and (_name(node, raw) == name or exact_snippet)):
            matches.append(node)
        for child in node.named_children:
            find(child)

    find(root)
    if len(matches) != 1:
        return ClassSemanticContext(**base, status="unavailable")
    target_node = matches[0]
    ancestors = _class_ancestors(target_node)
    if not ancestors or (target_node.type in _CALLABLES and (
            target_node.parent.type not in {"class_body", "interface_body", "enum_body"}
            or target_node.parent.parent != ancestors[0])):
        return ClassSemanticContext(**base, status="unavailable")
    cls = ancestors[0]
    body = cls.child_by_field_name("body")
    if body is None:
        return ClassSemanticContext(**base, status="unavailable")
    qualified = ".".join(_name(item, raw) for item in reversed(ancestors))
    modifiers = _modifiers(cls)
    superclass = cls.child_by_field_name("superclass")
    interfaces = cls.child_by_field_name("interfaces")
    inheritance = tuple(_text(raw, child) for child in interfaces.named_children[0].named_children) if (
        interfaces is not None and interfaces.named_children and interfaces.named_children[0].type == "type_list"
    ) else tuple(_text(raw, child) for child in interfaces.named_children) if interfaces is not None else ()
    identity = ClassIdentity(
        name=_name(cls, raw), qualified_name=qualified,
        kind={"class_declaration": "class", "interface_declaration": "interface",
              "enum_declaration": "enum", "record_declaration": "record"}[cls.type],
        span=_span(cls), declaration_fingerprint=_hash(raw, cls),
        visibility=_visibility(modifiers), is_static="static" in modifiers,
        is_final="final" in modifiers, is_abstract="abstract" in modifiers,
        extends=_text(raw, superclass.named_children[0]) if superclass is not None and superclass.named_children else None,
        implements=inheritance,
    )
    target_identity = TargetIdentity(name=_name(target_node, raw), kind=kind,
                                     span=_span(target_node), owner=qualified)
    fields = _fields(body, raw)
    method_nodes = [child for child in body.named_children if child.type == "method_declaration"]
    constructor_nodes = [child for child in body.named_children if child.type == "constructor_declaration"]
    overflow = []
    if len(fields) > MAX_FIELDS:
        overflow.append("fields")
    if len(method_nodes) > MAX_METHODS:
        overflow.append("methods")
    if len(constructor_nodes) > MAX_CONSTRUCTORS:
        overflow.append("constructors")
    fields = fields[:MAX_FIELDS]
    method_nodes = method_nodes[:MAX_METHODS]
    constructor_nodes = constructor_nodes[:MAX_CONSTRUCTORS]
    relations = []
    for method in method_nodes:
        usage = _field_usage(method, raw, {field.name for field in fields})
        for field in fields:
            if field.name not in usage:
                continue
            relation = ClassRelation("field_usage", _name(method, raw), _span(method),
                                     field.name, field.span, usage[field.name])
            relations.append(relation)
            if "static" in _modifiers(method) and field.ownership == "instance":
                relations.append(ClassRelation("static_to_instance_field_reference",
                                               relation.method_name, relation.method_span,
                                               field.name, field.span, relation.access))
    if len(relations) > MAX_RELATIONS:
        overflow.append("relations")
    return ClassSemanticContext(
        **base, status="bounded" if overflow else "complete",
        class_identity=identity, target=target_identity,
        fields=tuple(fields), methods=tuple(_callable(node, raw) for node in method_nodes),
        explicit_constructors=tuple(_callable(node, raw) for node in constructor_nodes),
        relations=tuple(relations[:MAX_RELATIONS]), overflow=tuple(overflow),
    )
