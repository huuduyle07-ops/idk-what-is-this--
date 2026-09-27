"""CTX.OOP.1C: bounded, read-only interpretation of exact Java class facts.

This module accepts an existing 1A projection and its current source bytes. It
does not discover files, call a provider, construct a patch, or grant authority.
Model observations, when supplied by an already authorized call, are admitted
only against the closed fact references produced here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
import time
from typing import Any, Mapping

from core.class_semantic_context import ClassSemanticContext
from core.task_contract import TaskContract


PHASE_ID = "CTX.OOP.1C"
SCHEMA_VERSION = "ctx_oop_1c_review_v1"
OBSERVATION_KINDS = frozenset({
    "state_ownership", "shared_state_usage", "static_instance_interaction",
    "initialization_semantics", "lifecycle_semantics", "domain_state_overlap",
    "other_bounded_oop_concern",
})
MAX_FACTS = 48
MAX_OBSERVATIONS = 8
MAX_REFS = 8
MAX_GAPS = 1
MAX_REVIEW_BYTES = 16_384
MAX_DESCRIPTION = 500
_MUTATIONS = frozenset({"write", "read_write"})


@dataclass(frozen=True, slots=True)
class OOPStructuralFact:
    kind: str
    description: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OOPSemanticObservation:
    kind: str
    description: str
    evidence_refs: tuple[str, ...]
    material_behavior_difference: bool = False
    intent_question_optional: str = ""
    provenance: str = "deterministic_interpretation"

    def __post_init__(self) -> None:
        if (self.kind not in OBSERVATION_KINDS or not 1 <= len(self.evidence_refs) <= MAX_REFS
                or self.provenance not in {"deterministic_interpretation", "model_interpretation"}):
            raise ValueError("invalid_oop_observation")


@dataclass(frozen=True, slots=True)
class OOPIntentAlternative:
    effect: str
    description: str


@dataclass(frozen=True, slots=True)
class OOPIntentGap:
    dimension: str
    question: str
    alternatives: tuple[OOPIntentAlternative, ...]
    evidence_refs: tuple[str, ...]
    source_fingerprint: str
    task_fingerprint: str
    owner: str = "human"
    status: str = "clarification_required"

    def __post_init__(self) -> None:
        if (self.owner != "human" or self.status != "clarification_required"
                or not 2 <= len(self.alternatives) <= 4
                or len({item.effect for item in self.alternatives}) < 2
                or not 1 <= len(self.evidence_refs) <= MAX_REFS):
            raise ValueError("invalid_oop_intent_gap")


@dataclass(frozen=True, slots=True)
class OOPSemanticReview:
    status: str
    structural_facts: tuple[OOPStructuralFact, ...] = ()
    semantic_observations: tuple[OOPSemanticObservation, ...] = ()
    possible_intent_gaps: tuple[OOPIntentGap, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    task_relevance: str = "informational"
    authority: str = "read_only"
    source_fingerprint: str = ""
    file: str = ""
    class_identity: str = ""
    completeness: str = "unavailable"
    normalization_seconds: float = 0.0
    evidence_binding_seconds: float = 0.0
    gap_admission_seconds: float = 0.0
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.authority != "read_only" or self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid_oop_review_authority")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))


def _ref(kind: str, name: str, start: int, end: int) -> str:
    return f"{kind}:{name}@{start}:{end}"


def _relation_ref(relation: Any) -> str:
    return (f"relation:{relation.kind}:{relation.method_name}@{relation.method_span.start}:"
            f"{relation.method_span.end}:{relation.field_name}@{relation.field_span.start}:"
            f"{relation.field_span.end}:{relation.access}")


def _bounded_text(value: Any, *, optional: bool = False) -> str:
    if not isinstance(value, str) or len(value) > MAX_DESCRIPTION or (not optional and not value.strip()):
        raise ValueError("invalid_oop_observation")
    return value.strip()


def _task_text(contract: TaskContract | None) -> str:
    if contract is None or not contract.routing_allowed or not contract.preservation.passed:
        return ""
    return contract.raw_request.text


def _task_flags(text: str) -> tuple[bool, bool, bool, bool, bool]:
    lower = text.casefold()
    pedagogical = bool(re.search(r"\b(?:practice exercise|simple (?:oop )?exercise|tutorial|learning|learn|homework)\b", lower))
    production = bool(re.search(r"\b(?:production|real(?:istic)? financial|banking application|real account model)\b", lower))
    one_balance = bool(re.search(r"\b(?:one|same|single|current) balance\b|directly to (?:the |account'?s )?balance", lower))
    global_sharing = bool(re.search(r"\b(?:all objects|all instances)\b.*\b(?:share|shared)\b|\bglobal counter\b", lower))
    cross_call = bool(re.search(r"\b(?:persist|survive|retain|remember)\b.{0,35}\b(?:calls?|invocations?)\b", lower))
    return pedagogical, production, one_balance, global_sharing, cross_call


def _normalize_model_observations(
    report: Mapping[str, Any] | None, allowed_refs: frozenset[str],
    *, file: str, class_identity: str, source_fingerprint: str,
) -> tuple[OOPSemanticObservation, ...]:
    if report is None:
        return ()
    if (not isinstance(report, Mapping)
            or set(report) != {"file", "class_identity", "source_fingerprint", "observations"}
            or report["file"] != file or report["class_identity"] != class_identity
            or report["source_fingerprint"] != source_fingerprint):
        raise ValueError("invalid_oop_observation")
    items = report["observations"]
    if not isinstance(items, list) or len(items) > MAX_OBSERVATIONS:
        raise ValueError("invalid_oop_observation")
    normalized = []
    for item in items:
        if not isinstance(item, Mapping) or set(item) - {
            "kind", "evidence_refs", "description", "material_behavior_difference",
            "intent_question_optional",
        } or not {"kind", "evidence_refs", "description", "material_behavior_difference"} <= set(item):
            raise ValueError("invalid_oop_observation")
        refs = item["evidence_refs"]
        if (item["kind"] not in OBSERVATION_KINDS or not isinstance(refs, list)
                or not 1 <= len(refs) <= MAX_REFS or len(refs) != len(set(refs))
                or not all(isinstance(ref, str) and ref in allowed_refs for ref in refs)
                or type(item["material_behavior_difference"]) is not bool):
            raise ValueError("invalid_oop_observation")
        normalized.append(OOPSemanticObservation(
            kind=item["kind"], description=_bounded_text(item["description"]),
            evidence_refs=tuple(refs),
            material_behavior_difference=item["material_behavior_difference"],
            intent_question_optional=_bounded_text(item.get("intent_question_optional", ""), optional=True),
            provenance="model_interpretation",
        ))
    return tuple(normalized)


def _exact_source_facts(
    context: ClassSemanticContext, raw: bytes,
    field_refs: Mapping[str, Any], constructor_refs: Mapping[str, Any],
    cross_call: bool,
) -> tuple[list[OOPStructuralFact], list[OOPSemanticObservation], set[str]]:
    """Add only AST-proven local declarations and explicit constructor writes."""
    facts: list[OOPStructuralFact] = []
    observations: list[OOPSemanticObservation] = []
    refs: set[str] = set()
    try:
        from tree_sitter_language_pack import get_parser
        root = get_parser("java").parse(raw).root_node
    except (ImportError, ValueError, TypeError, AttributeError):
        return facts, observations, refs
    if root.has_error:
        return facts, observations, refs
    target = context.target
    cls = context.class_identity
    if target is None or cls is None:
        return facts, observations, refs
    field_by_name = {field.name: (ref, field) for ref, field in field_refs.items()}
    constructors_by_start = {item.span.start: ref for ref, item in constructor_refs.items()}
    remaining = 16

    def walk(node: Any, callable_ref: str = "", constructor_ref: str = "") -> None:
        nonlocal remaining
        if remaining <= 0 or node.start_byte < cls.span.start or node.end_byte > cls.span.end:
            return
        if node.type in {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration"}:
            if node.start_byte != cls.span.start or node.end_byte != cls.span.end:
                return
        if node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            name = raw[name_node.start_byte:name_node.end_byte].decode("utf-8") if name_node else ""
            callable_ref = _ref("method", name, node.start_byte, node.end_byte)
            constructor_ref = ""
        elif node.type == "constructor_declaration":
            constructor_ref = constructors_by_start.get(node.start_byte, "")
            callable_ref = ""
        elif node.type == "local_variable_declaration" and callable_ref:
            for child in node.named_children:
                if child.type != "variable_declarator" or remaining <= 0:
                    continue
                name_node = child.child_by_field_name("name")
                if name_node is None:
                    continue
                name = raw[name_node.start_byte:name_node.end_byte].decode("utf-8")
                ref = _ref("local", name, child.start_byte, child.end_byte)
                refs.add(ref)
                facts.append(OOPStructuralFact(
                    "state_ownership", f"{name} is method-local state with lexical method scope.",
                    (callable_ref, ref)))
                if cross_call and name not in field_by_name:
                    observations.append(OOPSemanticObservation(
                        "lifecycle_semantics",
                        f"{name} is local to this method and does not itself retain state across calls.",
                        (callable_ref, ref), material_behavior_difference=True))
                remaining -= 1
        elif node.type == "assignment_expression" and constructor_ref:
            left = node.child_by_field_name("left")
            if left is not None and left.type == "field_access":
                obj = left.child_by_field_name("object")
                field_node = left.child_by_field_name("field")
                if obj is not None and obj.type == "this" and field_node is not None:
                    name = raw[field_node.start_byte:field_node.end_byte].decode("utf-8")
                    if name in field_by_name:
                        field_ref, _ = field_by_name[name]
                        refs.add(constructor_ref)
                        facts.append(OOPStructuralFact(
                            "constructor_initialization",
                            f"An explicit constructor assigns {name}.",
                            (constructor_ref, field_ref)))
                        remaining -= 1
        for child in node.named_children:
            walk(child, callable_ref, constructor_ref)

    try:
        walk(root)
    except RecursionError:
        return [], [], set()
    return facts, observations, refs


def review_oop_semantics(
    *, context: ClassSemanticContext | None, current_source: bytes,
    task_contract: TaskContract | None = None,
    model_report: Mapping[str, Any] | None = None,
    repair_intent_owns_ambiguity: bool = False,
) -> OOPSemanticReview:
    """Review one already projected class without a candidate or provider call.

    The optional model report is a typed output of an existing authorized call.
    It can add interpretations, but cannot add facts, refs, or a waiting session.
    """
    if context is None or context.language != "java":
        return OOPSemanticReview("not_supported")
    base = dict(source_fingerprint=context.source_fingerprint, file=context.file,
                class_identity=context.class_identity.qualified_name if context.class_identity else "")
    if not isinstance(current_source, bytes) or hashlib.sha256(current_source).hexdigest() != context.source_fingerprint:
        return OOPSemanticReview("stale", **base)
    if context.status not in {"complete", "bounded"} or context.class_identity is None or context.target is None:
        return OOPSemanticReview("unavailable", **base)
    if "source_bytes" in context.overflow or "serialized_bytes" in context.overflow:
        return OOPSemanticReview("unavailable", **base)

    started = time.perf_counter()
    cls = context.class_identity
    task_text = _task_text(task_contract)
    if ((cls.extends or cls.implements)
            and re.search(r"\b(?:polymorph\w*|overrid\w*|dynamic dispatch)\b",
                          task_text.casefold())):
        return OOPSemanticReview("bounded", source_fingerprint=context.source_fingerprint,
                                 file=context.file, class_identity=cls.qualified_name,
                                 completeness="bounded")
    class_ref = _ref("class", cls.qualified_name, cls.span.start, cls.span.end)
    field_refs = {_ref("field", f.name, f.span.start, f.span.end): f for f in context.fields}
    method_refs = {_ref("method", m.name, m.span.start, m.span.end): m for m in context.methods}
    constructor_refs = {_ref("constructor", c.name, c.span.start, c.span.end): c
                        for c in context.explicit_constructors}
    relation_refs = {_relation_ref(r): r for r in context.relations}
    catalog = frozenset({class_ref, *field_refs, *method_refs, *constructor_refs, *relation_refs})
    fields_by_span = {(f.name, f.span.start, f.span.end): ref for ref, f in field_refs.items()}
    methods_by_span = {(m.name, m.span.start, m.span.end): ref for ref, m in method_refs.items()}
    facts: list[OOPStructuralFact] = []
    observations: list[OOPSemanticObservation] = []
    for ref, field in field_refs.items():
        explanation = ("each object carries separate state" if field.ownership == "instance"
                       else "the class shares this state")
        facts.append(OOPStructuralFact("state_ownership",
                                        f"{field.name} is {field.ownership} state; {explanation}.", (ref,)))
    for ref, relation in relation_refs.items():
        if relation.kind == "field_usage":
            facts.append(OOPStructuralFact("field_usage",
                f"{relation.method_name} {relation.access.replace('_', '/')} accesses {relation.field_name}.",
                (ref,)))
        elif relation.kind == "static_to_instance_field_reference":
            facts.append(OOPStructuralFact("static_instance_interaction",
                f"Static method {relation.method_name} references instance field {relation.field_name}.",
                (ref,)))
            observations.append(OOPSemanticObservation(
                "static_instance_interaction",
                f"The static method and {relation.field_name} have different structural ownership.",
                (ref,)))
    # A 1A relation is a syntactic fact. Group distinct mutating methods by the
    # exact field identity, never by a copied source quote or similar spelling.
    mutation_groups: dict[str, list[tuple[str, Any]]] = {}
    for ref, relation in relation_refs.items():
        if relation.kind != "field_usage" or relation.access not in _MUTATIONS:
            continue
        field_ref = fields_by_span.get((relation.field_name, relation.field_span.start,
                                        relation.field_span.end))
        if field_ref:
            mutation_groups.setdefault(field_ref, []).append((ref, relation))
    text = task_text
    pedagogical, production, one_balance, global_sharing, cross_call = _task_flags(text)
    source_facts, source_observations, source_refs = _exact_source_facts(
        context, current_source, field_refs, constructor_refs, cross_call)
    facts.extend(source_facts)
    observations.extend(source_observations)
    catalog = frozenset(set(catalog) | source_refs)
    review_requested = bool(re.search(r"\b(?:review|check|correct|okay|logic)\b", text.casefold()))
    gap_candidates: list[OOPIntentGap] = []
    task_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    for field_ref, group in mutation_groups.items():
        distinct = {r.method_span.start: (ref, r) for ref, r in group}
        if len(distinct) < 2:
            continue
        group_refs = tuple(ref for ref, _ in sorted(distinct.values(), key=lambda pair: pair[1].method_span.start))[:MAX_REFS]
        field = field_refs[field_ref]
        names = {r.method_name.casefold() for _, r in distinct.values()}
        facts.append(OOPStructuralFact("same_state_mutation",
            f"{', '.join(r.method_name for _, r in sorted(distinct.values(), key=lambda pair: pair[1].method_span.start))} mutate the same {field.ownership} field {field.name}.",
            (field_ref, *group_refs[:MAX_REFS-1])))
        # These names are weak semantic signals. They invite a question about a
        # state model, never a defect claim or a choice of implementation.
        domain_overlap = "saving" in names and bool(names & {"deposit", "withdraw"})
        if domain_overlap:
            refs = (field_ref, *group_refs[:MAX_REFS-1])
            relevant = (review_requested or production or bool(re.search(
                r"\bsaving\b.{0,80}\b(?:interest|balance|state|account|calculate|behavior)\b|"
                r"\b(?:interest|balance|state|account|calculate|behavior)\b.{0,80}\bsaving\b",
                text.casefold())))
            question_needed = relevant and not one_balance and not pedagogical
            observations.append(OOPSemanticObservation(
                "domain_state_overlap",
                f"saving changes {field.name}, the same {field.ownership} state used by "
                + "/".join(sorted(names & {"deposit", "withdraw"})) + ".",
                refs, material_behavior_difference=question_needed,
                intent_question_optional=("Should saving use this same balance, or represent distinct state?"
                                          if question_needed and field.ownership == "instance" else "")))
            if (question_needed and field.ownership == "instance"
                    and not repair_intent_owns_ambiguity):
                gap_candidates.append(OOPIntentGap(
                    "domain_state_overlap", "Should saving use this same balance, or represent distinct state?",
                    (OOPIntentAlternative("shared_balance", "Saving applies to the current account balance."),
                     OOPIntentAlternative("distinct_state", "Savings has separate state or an account object.")),
                    refs, context.source_fingerprint, task_hash))
        else:
            observations.append(OOPSemanticObservation(
                "shared_state_usage", f"Several methods change {field.name}; their effects share state.",
                (field_ref, *group_refs[:MAX_REFS-1])))
    for field_ref, field in field_refs.items():
        if field.ownership != "static" or field_ref not in mutation_groups:
            continue
        if (production or (review_requested and "account" in cls.name.casefold())):
            observations.append(OOPSemanticObservation(
                "state_ownership", f"Every {cls.name} object uses the class-shared {field.name} field.",
                (class_ref, field_ref), material_behavior_difference=not global_sharing,
                intent_question_optional="Is shared state intentional?" if not global_sharing else ""))
            if not global_sharing and not repair_intent_owns_ambiguity:
                gap_candidates.append(OOPIntentGap(
                    "state_ownership", "Should these objects share this state?",
                    (OOPIntentAlternative("shared_state", "All objects share the field."),
                     OOPIntentAlternative("per_instance_state", "Each object carries separate state.")),
                    (class_ref, field_ref), context.source_fingerprint, task_hash))
    normalized_at = time.perf_counter()
    # Fail closed on the whole model contribution if any ID is absent. The
    # catalog is tied to one exact file, class and source fingerprint above.
    model_observations = _normalize_model_observations(
        model_report, catalog, file=context.file,
        class_identity=cls.qualified_name, source_fingerprint=context.source_fingerprint)
    observations.extend(model_observations)
    bound_at = time.perf_counter()
    # One question per dimension. MainApp's deterministic RepairIntent owner
    # suppresses the entire 1C gap adapter, so no duplicate waiting session.
    gaps = tuple(dict((gap.dimension, gap) for gap in gap_candidates).values())[:MAX_GAPS]
    facts = facts[:MAX_FACTS]
    observations = observations[:MAX_OBSERVATIONS]
    review = OOPSemanticReview(
        "clarification_required" if gaps else "informational",
        tuple(facts), tuple(observations), gaps,
        tuple(sorted(catalog)), "clarification_required" if gaps else "informational",
        source_fingerprint=context.source_fingerprint, file=context.file,
        class_identity=cls.qualified_name, completeness=context.status,
        normalization_seconds=round(bound_at-normalized_at, 6),
        evidence_binding_seconds=round(normalized_at-started, 6),
        gap_admission_seconds=round(time.perf_counter()-bound_at, 6),
    )
    if len(review.to_json().encode("utf-8")) > MAX_REVIEW_BYTES:
        return OOPSemanticReview("bounded", source_fingerprint=context.source_fingerprint,
                                 file=context.file, class_identity=cls.qualified_name,
                                 completeness="bounded")
    return review


def render_oop_semantic_review(review: OOPSemanticReview) -> str:
    """Bounded explanatory text; facts and interpretation remain labeled."""
    if review.status not in {"informational", "clarification_required"}:
        return ""
    lines = ["[READ-ONLY OOP SEMANTIC REVIEW]", "Current behavior (structural facts):"]
    lines.extend(f"- {fact.description} [refs: {', '.join(fact.evidence_refs)}]"
                 for fact in review.structural_facts)
    lines.append("Why it may matter (interpretation, not an established defect):")
    lines.extend(f"- {item.description} [refs: {', '.join(item.evidence_refs)}]"
                 for item in review.semantic_observations)
    lines.append("Need clarification: " + ("yes" if review.possible_intent_gaps else "no"))
    lines.extend(f"- {gap.question}" for gap in review.possible_intent_gaps)
    return "\n".join(lines)


def review_acquired_java_evidence(
    *, evidence: Any, repository_root: str, task_contract: TaskContract,
) -> tuple[OOPSemanticReview, ...]:
    """Read exact bytes for already acquired Java items on a review task.

    The existing analysis inventory selected the files. This adapter performs
    zero discovery and at most two exact-file reads. Truncated or text-normalized
    evidence cannot carry a 1A fact and is omitted.
    """
    from pathlib import Path

    from core.class_semantic_context import project_class_semantic_context
    from core.treesitter_parse import structural_definitions

    task = _task_text(task_contract)
    if not re.search(r"\b(?:review|check|correct|okay|logic)\b", task.casefold()):
        return ()
    root = Path(repository_root).resolve()
    results = []
    java_items = [item for item in getattr(evidence, "items", ())
                  if isinstance(getattr(item, "path", None), str)
                  and item.path.lower().endswith(".java") and not getattr(item, "truncated", True)]
    for item in java_items:
        if len(results) >= 2:
            break
        path = getattr(item, "path", "")
        if not isinstance(path, str) or not path.lower().endswith(".java") or getattr(item, "truncated", True):
            continue
        try:
            source_path = (root / path).resolve()
            source_path.relative_to(root)
            raw = source_path.read_bytes()
            if raw.decode("utf-8") != item.text:
                continue
            source = raw.decode("utf-8")
            definitions = structural_definitions(source, "java")["definitions"]
            classes = [d for d in definitions if d["kind"] in {"class", "interface", "enum", "record"}]
            named_path = (path.casefold() in task.casefold()
                          or Path(path).stem.casefold() in task.casefold())
            named_class = any(re.search(r"(?<!\w)" + re.escape(d["name"]) + r"(?!\w)", task)
                              for d in classes)
            if len(java_items) > 1 and not (named_path or named_class):
                continue
            if len(classes) != 1:
                named = [d for d in classes if re.search(r"(?<!\w)" + re.escape(d["name"]) + r"(?!\w)", task)]
                if len(named) != 1:
                    continue
                target = named[0]
            else:
                target = classes[0]
            context = project_class_semantic_context(
                raw=raw, language="java", file=path, target=target,
                expected_source_fingerprint=hashlib.sha256(raw).hexdigest(),
                repository_id=getattr(item, "repository_id", None) or None)
            result = review_oop_semantics(
                context=context, current_source=raw, task_contract=task_contract)
            if result.status in {"informational", "clarification_required"}:
                results.append(result)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, RecursionError):
            continue
    return tuple(results)
