"""CTX.OOP.1B: bounded, factual, read-only Java author context.

Selection consumes only CTX.OOP.1A's projection and an exact target. It does
not read files, discover symbols, call a model, or confer edit authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Mapping

from core.class_semantic_context import ClassSemanticContext


MAX_FIELDS = 12
MAX_METHODS = 16
MAX_CONSTRUCTORS = 4
MAX_RELATIONS = 24
MAX_PROMPT_BYTES = 3_072
_OMITTED = "[additional relevant class context omitted by bound]"


def project_oop_author_source(
    *, source: str, file: str, symbol: str, source_snippet: str,
    raw: bytes | None = None,
) -> tuple[ClassSemanticContext | None, tuple[str, str, int, int] | None]:
    """Bind an existing exact Java authoring buffer to one structural target."""
    if not source or not file.lower().endswith(".java") or not source_snippet:
        return None, None
    from core.class_semantic_context import project_class_semantic_context
    from core.treesitter_parse import structural_definitions

    source_raw = raw if raw is not None else source.encode("utf-8")
    try:
        exact_source = source_raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, None
    matches = [item for item in structural_definitions(exact_source, "java")["definitions"]
               if item["name"] == symbol and item["content"].replace("\r\n", "\n").replace("\r", "\n").strip()
               == source_snippet.strip()]
    if len(matches) != 1:
        return None, None
    target = matches[0]
    projection = project_class_semantic_context(
        raw=source_raw, language="java", file=file, target=target,
        expected_source_fingerprint=hashlib.sha256(source_raw).hexdigest())
    return projection, (target["kind"], target["name"], target["start"], target["end"])


@dataclass(frozen=True, slots=True)
class OopReasoningAttachment:
    status: str
    prompt: str = ""
    authority: str = "read_only"
    class_identity: str = ""
    source_fingerprint: str = ""
    selected_field_ids: tuple[str, ...] = ()
    selected_method_ids: tuple[str, ...] = ()
    selected_constructor_ids: tuple[str, ...] = ()
    selected_relation_ids: tuple[str, ...] = ()
    completeness: str = "unavailable"
    freshness_seconds: float = 0.0
    selection_seconds: float = 0.0
    formatting_seconds: float = 0.0
    total_seconds: float = 0.0

    def receipt(self) -> dict[str, Any]:
        return {"status": self.status, "authority": self.authority,
                "class_identity": self.class_identity,
                "source_fingerprint": self.source_fingerprint,
                "selected_field_ids": list(self.selected_field_ids),
                "selected_method_ids": list(self.selected_method_ids),
                "selected_constructor_ids": list(self.selected_constructor_ids),
                "selected_relation_ids": list(self.selected_relation_ids),
                "completeness": self.completeness,
                "prompt_bytes": len(self.prompt.encode("utf-8"))}


def _id(item: Any) -> str:
    return f"{item.name}@{item.span.start}:{item.span.end}"


def _relation_id(item: Any) -> str:
    return (f"{item.kind}:{item.method_name}@{item.method_span.start}:"
            f"{item.field_name}@{item.field_span.start}:{item.access}")


def _signature(item: Any) -> str:
    params = ", ".join(f"{p.declared_type} {p.name}".strip() for p in item.parameters)
    return f"{item.visibility} {item.ownership} {item.return_type + ' ' if item.return_type else ''}{item.name}({params})"


def _line(label: str, value: Any) -> str:
    # Source-derived names/types are untrusted data, never free-form instructions.
    return label + " " + json.dumps(value, ensure_ascii=True, sort_keys=True)


def build_oop_reasoning_context(
    *, context: ClassSemanticContext | None, current_source: bytes,
    target: Mapping[str, Any], repair_scope: Any = None,
    max_prompt_bytes: int = MAX_PROMPT_BYTES,
) -> OopReasoningAttachment:
    started = time.perf_counter()
    if context is None or context.language != "java":
        return OopReasoningAttachment("not_supported")
    fingerprint = hashlib.sha256(current_source).hexdigest()
    fresh_at = time.perf_counter()
    freshness = fresh_at - started
    base = dict(class_identity=(context.class_identity.qualified_name if context.class_identity else ""),
                source_fingerprint=context.source_fingerprint,
                freshness_seconds=round(freshness, 6))
    if context.source_fingerprint != fingerprint:
        return OopReasoningAttachment("stale", **base)
    if context.status not in {"complete", "bounded"} or not context.class_identity or not context.target:
        return OopReasoningAttachment("unavailable", **base)
    if (target.get("name") != context.target.name or target.get("kind") != context.target.kind
            or target.get("start") != context.target.span.start
            or target.get("end") != context.target.span.end):
        return OopReasoningAttachment("unavailable", **base)

    def source_order(item: Any) -> tuple[int, str]:
        return item.span.start, _id(item)

    fields = sorted(context.fields, key=source_order)
    methods = sorted(context.methods, key=source_order)
    constructors = sorted(context.explicit_constructors, key=source_order)
    relations = sorted(context.relations,
                       key=lambda r: (r.method_span.start, r.field_span.start, _relation_id(r)))
    target_method = next((m for m in methods if m.span.start == context.target.span.start
                          and m.span.end == context.target.span.end), None)
    target_constructor = next((c for c in constructors if c.span.start == context.target.span.start
                               and c.span.end == context.target.span.end), None)
    class_target = context.target.kind in {"class", "interface", "enum", "record"}
    repair_members = getattr(repair_scope, "members", ())
    measured = getattr(repair_scope, "measured", None)
    if measured is not None:
        repair_members = getattr(measured, "members", ())
    repair_spans = {(m.start_line, m.end_line, m.symbol) for m in repair_members
                    if getattr(m, "file", None) == context.file}
    repair_methods = [m for m in methods if (m.span.start_line, m.span.end_line, m.name) in repair_spans]

    target_relations = [r for r in relations if target_method and r.method_span.start == target_method.span.start]
    direct_names = {r.field_name for r in target_relations}
    repair_names = {r.field_name for r in relations for m in repair_methods
                    if r.method_span.start == m.span.start}
    relevant_names = {f.name for f in fields} if class_target else direct_names | repair_names
    field_tiers = ([fields] if class_target else
                   [[f for f in fields if f.name in direct_names],
                    [f for f in fields if f.name in repair_names and f.name not in direct_names]])
    sibling_methods = [m for m in methods if m is not target_method and m not in repair_methods
                       and any(r.method_span.start == m.span.start and r.field_name in relevant_names
                               for r in relations)]
    method_tiers = ([methods] if class_target else
                    [[target_method] if target_method else [], repair_methods, sibling_methods])
    selected_fields: list[Any] = []
    selected_methods: list[Any] = []
    bounded = context.status == "bounded"

    def collect(tiers: list[list[Any]], limit: int, output: list[Any]) -> None:
        nonlocal bounded
        seen: set[str] = set()
        for tier in tiers:
            for item in tier:
                identity = _id(item)
                if identity in seen:
                    continue
                seen.add(identity)
                if len(output) >= limit:
                    bounded = True
                else:
                    output.append(item)

    collect(field_tiers, MAX_FIELDS, selected_fields)
    collect(method_tiers, MAX_METHODS, selected_methods)
    selected_constructors = constructors[:MAX_CONSTRUCTORS] if (class_target or relevant_names or target_constructor) else []
    if len(constructors) > len(selected_constructors) and (class_target or relevant_names or target_constructor):
        bounded = True
    field_ids = {f.span.start for f in selected_fields}
    method_ids = {m.span.start for m in selected_methods}
    relevant_relations = [r for r in relations if r.field_span.start in field_ids
                          and r.method_span.start in method_ids]
    relevant_relations.sort(key=lambda r: (0 if target_method and r.method_span.start == target_method.span.start else 1,
                                           0 if r.kind == "static_to_instance_field_reference" else 1,
                                           r.method_span.start, r.field_span.start, _relation_id(r)))
    selected_relations = relevant_relations[:MAX_RELATIONS]
    if len(relevant_relations) > len(selected_relations):
        bounded = True
    selected_at = time.perf_counter()

    cls = context.class_identity
    header = ["[READ-ONLY CLASS CONTEXT]",
              "Structural context only. Presence here does not authorize editing these members.",
              "Edit scope is defined by PATCH TARGET and the authoring scope elsewhere.",
              _line("Class:", {"name": cls.qualified_name, "kind": cls.kind,
                               "visibility": cls.visibility, "static": cls.is_static,
                               "final": cls.is_final, "abstract": cls.is_abstract,
                               "extends": cls.extends, "implements": cls.implements})]
    target_callable = target_method or target_constructor
    if target_callable:
        header.append(_line("Target:", {"id": _id(target_callable), "signature": _signature(target_callable)}))
    else:
        header.append(_line("Target:", {"name": context.target.name, "kind": context.target.kind}))
    prioritized: list[tuple[int, int, str, str, str]] = []
    for f in selected_fields:
        prioritized.append((1 if class_target or f.name in direct_names else 4,
                            f.span.start, "field", _id(f),
                            _line("Field:", {"id": _id(f), "declaration":
                                            f"{f.visibility} {f.ownership} {f.declared_type} {f.name}"})))
    repair_ids = {m.span.start for m in repair_methods}
    for m in selected_methods:
        if m is not target_method:
            prioritized.append((3 if class_target or m.span.start in repair_ids else 5,
                                m.span.start, "method", _id(m),
                                _line("Method:", {"id": _id(m), "signature": _signature(m)})))
    for r in selected_relations:
        priority = (2 if target_method and r.method_span.start == target_method.span.start else
                    4 if r.method_span.start in repair_ids else 5)
        prioritized.append((priority, r.method_span.start, "relation", _relation_id(r),
                            _line("Relation:", {"id": _relation_id(r), "kind": r.kind,
                                                "method": r.method_name, "field": r.field_name,
                                                "access": r.access})))
    for c in selected_constructors:
        if c is not target_constructor:
            prioritized.append((6, c.span.start, "constructor", _id(c),
                                _line("Constructor:", {"id": _id(c), "signature": _signature(c)})))
    prioritized.sort(key=lambda item: (item[0], item[1], item[3]))
    cap = min(max(0, max_prompt_bytes), MAX_PROMPT_BYTES)
    rendered = "\n".join(header)
    chosen: dict[str, list[str]] = {kind: [] for kind in ("field", "method", "relation", "constructor")}
    reserve = len(("\n" + _OMITTED).encode("utf-8"))
    for _, _, kind, identity, line in prioritized:
        if len((rendered + "\n" + line).encode("utf-8")) + reserve > cap:
            bounded = True
            continue
        rendered += "\n" + line
        chosen[kind].append(identity)
    if bounded and len((rendered + "\n" + _OMITTED).encode("utf-8")) <= cap:
        rendered += "\n" + _OMITTED
    if len(rendered.encode("utf-8")) > cap:
        return OopReasoningAttachment("bounded", completeness="bounded", **base)
    ended = time.perf_counter()
    return OopReasoningAttachment(
        "attached", prompt=rendered, completeness="bounded" if bounded else "complete",
        selected_field_ids=tuple(chosen["field"]),
        selected_method_ids=tuple([_id(target_method)] if target_method else []) + tuple(chosen["method"]),
        selected_constructor_ids=tuple([_id(target_constructor)] if target_constructor else []) + tuple(chosen["constructor"]),
        selected_relation_ids=tuple(chosen["relation"]),
        selection_seconds=round(selected_at - fresh_at, 6),
        formatting_seconds=round(ended - selected_at, 6),
        total_seconds=round(ended - started, 6), **base)
