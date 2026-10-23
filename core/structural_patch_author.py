"""PATCH.AUTHOR.STRUCTURAL.1: one read-only author, immutable multi-target draft.

The facade reacquires named ADMIT paths before prompting and after the response.
The pure normalizer/validator accept caller-supplied fresh evidence. No existing
repair-author semantics, materialization, execution, session, or Apply adapter.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from hashlib import sha256
import json
import math
from threading import Lock
from time import perf_counter
from typing import Protocol

from core.structural_scope_admission import (
    AdmissionError, AdmittedStructuralAuthoringScope, PathWitness,
    acquire_structural_admission_evidence, validate_admitted_structural_authoring_scope,
)
from core.structural_implementation_plan import DeclarationBinding
from core.structural_java import StructuralJavaError, parse_operation, check_contracts

PHASE_ID = "PATCH.AUTHOR.STRUCTURAL.1"
SCHEMA_VERSION = "patch_author_structural_1_v1"
MAX_OUTPUT_BYTES = 96_000
MAX_CONTEXT_BYTES = 128_000
MAX_OPERATIONS = 64
OPERATION_KINDS = frozenset({"insert_member", "remove_declaration", "draft_new_file", "insert_nested_class"})
ESCALATIONS = frozenset({"missing_context", "admitted_scope_insufficient", "semantic_clarification_required",
    "unsupported_structural_operation", "author_output_invalid", "other_bounded_reason"})
TIMING_FIELDS = ("fresh_admission_validation_seconds", "author_context_projection_seconds",
    "provider_latency_seconds", "candidate_normalization_seconds", "java_structural_parsing_seconds",
    "admitted_scope_containment_seconds", "candidate_fingerprint_seconds", "total_deterministic_seconds")
AUTHORITY_KEYS = frozenset({"write_authority", "filesystem_write_authority", "execution_authorized",
    "apply_authority", "apply", "auto_apply", "filesystem_file_creation_authority", "file_creation_authority"})
BOUNDARY = ("Return a candidate proposal only. No filesystem writes, commands, tools, compilation, "
    "execution or Apply. Every operation and definition must come from AUTHORABLE STRUCTURE. "
    "READ-ONLY SUPPORT is context only, including any shown class body. Do not recover unused "
    "ceiling targets, add helpers, tests, policies, imports/infrastructure, or renegotiate the plan. "
    "Removal supplies only the exact declaration identity; never source or a broader span. "
    "Escalate or abstain when these exact boundaries are insufficient.")


class StructuralAuthorError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise StructuralAuthorError(code, reason)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _immutable(value):
    if value is None or type(value) in {str, int, bool, float}:
        return
    if type(value) is tuple:
        for item in value:
            _immutable(item)
    elif is_dataclass(value) and value.__dataclass_params__.frozen:
        for f in fields(value):
            _immutable(getattr(value, f.name))
    else:
        _fail("author_output_invalid", "mutable candidate/evidence field")


def _authorities(value):
    if type(value) is dict:
        for key, item in value.items():
            if key in AUTHORITY_KEYS and item is not False:
                _fail("author_output_authority_escalation", key)
            _authorities(item)
    elif type(value) in {list, tuple}:
        for item in value:
            _authorities(item)


def _closed(value, keys, code="author_output_invalid"):
    if type(value) is not dict or set(value) != set(keys):
        _fail(code, "closed response vocabulary required")


def _fresh(scope, inputs, measured):
    tick = perf_counter()
    try:
        checked = validate_admitted_structural_authoring_scope(scope, **inputs)
    except AdmissionError as exc:
        _fail(exc.code, exc.reason)
    finally:
        measured["fresh_admission_validation_seconds"] += perf_counter() - tick
    if any(o.operation not in OPERATION_KINDS for o in checked.permitted_structural_operations):
        _fail("unsupported_structural_operation", "ADMIT operation outside structural author V1")
    return checked


@dataclass(frozen=True, slots=True)
class StructuralCandidateOperation:
    operation: str
    physical_target: str
    owner: str
    definition_ids: tuple[str, ...]
    source_text: str | None
    existing_declaration: DeclarationBinding | None
    removal_intent: bool

    def __post_init__(self):
        _immutable(self)


@dataclass(frozen=True, slots=True)
class StructuralPatchCandidate:
    admission_fingerprint: str
    implementation_plan_fingerprint: str
    task_fingerprint: str
    effective_design_fingerprint: str
    p1_fingerprint: str
    approval_receipt_fingerprint: str
    approved_ceiling_fingerprint: str
    repository_id: str
    repository_evidence_fingerprint: str
    source_bindings: tuple[tuple[str, str, str, str], ...]
    new_path_absence_witnesses: tuple[PathWitness, ...]
    operations: tuple[StructuralCandidateOperation, ...]
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    status: str = field(default="structural_patch_candidate", init=False)
    authority: str = field(default="candidate_only", init=False)
    write_authority: bool = field(default=False, init=False)
    filesystem_write_authority: bool = field(default=False, init=False)
    filesystem_file_creation_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    repair_scope_delta: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    patch: str = field(default="", init=False)

    def __post_init__(self):
        _immutable(self)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "candidate_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


@dataclass(frozen=True, slots=True)
class StructuralAuthorContext:
    context_json: str
    authority: str = field(default="candidate_only", init=False)
    write_authority: bool = field(default=False, init=False)

    @property
    def payload(self):
        return json.loads(self.context_json)


def _context(scope, inputs, measured):
    tick = perf_counter()
    snippets = []
    for context, raw in ((inputs["current_context"], inputs["current_source"]), *inputs.get("related_contexts", ())):
        if any((o.physical_target, o.owner) == (context.file, context.class_identity.name)
               for o in scope.existing_file_authoring_targets) or any(
                r.declaration.file == context.file and r.declaration.owner == context.class_identity.name
                for r in scope.read_only_supporting_targets):
            span = context.class_identity.span
            snippets.append({"path": context.file, "owner": context.class_identity.name,
                "source_fingerprint": context.source_fingerprint,
                "exact_source_context": raw[span.start:span.end].decode("utf-8"),
                "authority": "read_only_context; edit only enumerated operations"})
    payload = {"boundary": BOUNDARY, "original_task_meaning": inputs["task_contract"].as_dict()["raw_request"]["text"],
        "admission_fingerprint": scope.fingerprint, "semantic_commitments": scope.semantic_commitments,
        "implementation_decisions": [asdict(d) for d in scope.implementation_decisions],
        "semantic_contracts": {"savings_credit_guard": scope.savings_credit_guard,
            "inherited_balance_access": scope.inherited_balance_access, "base_saving_action": scope.base_saving_action,
            "common_savings_contract": scope.common_savings_contract},
        "[READ-ONLY SUPPORT]": {"declarations": [asdict(r) for r in scope.read_only_supporting_targets],
            "source_context": snippets},
        "[AUTHORABLE STRUCTURE]": {"operations": [asdict(o) for o in scope.permitted_structural_operations],
            "definition_allowances": [asdict(a) for a in scope.definition_allowances],
            "exact_new_file_targets": [asdict(t) for t in scope.new_file_creation_targets]},
        "output_schema": {"candidate": "null or {operations: [operation]}", "confidence": "finite number 0..1",
            "needs_escalation": "boolean", "escalation_reason": "null or bounded reason",
            "operation": {"operation": sorted(OPERATION_KINDS), "physical_target": "exact admitted path",
                "owner": "exact admitted owner", "definition_ids": "exact admitted IDs",
                "source_text": "Java declaration(s)/new file, null for removal",
                "existing_declaration": "exact admitted identity for removal, otherwise null",
                "removal_intent": "true only for removal"},
            "escalation": {"code": sorted(ESCALATIONS), "message": "bounded text",
                           "requested_capabilities": "bounded strings; no authority"}}}
    encoded = _json(payload)
    if len(encoded.encode("utf-8")) > MAX_CONTEXT_BYTES:
        _fail("missing_context", "author context exceeds V1 bound")
    measured["author_context_projection_seconds"] += perf_counter() - tick
    return StructuralAuthorContext(encoded)


@dataclass(frozen=True, slots=True)
class StructuralEscalation:
    code: str
    message: str
    requested_capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuralAuthoringResult:
    status: str
    candidate: StructuralPatchCandidate | None
    reason: str
    confidence: float | None
    escalation: StructuralEscalation | None
    author_calls: int
    model_calls: int
    authority: str = field(default="candidate_only", init=False)
    write_authority: bool = field(default=False, init=False)
    filesystem_write_authority: bool = field(default=False, init=False)
    filesystem_file_creation_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    patch: str = field(default="", init=False)
    repair_scope_delta: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)


def _envelope(output):
    try:
        if type(output) is str:
            if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
                _fail("author_output_invalid", "output bound")
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        _fail("author_output_invalid", "duplicate JSON key")
                    result[key] = value
                return result
            output = json.loads(output, object_pairs_hook=unique)
        if len(_json(output).encode("utf-8")) > MAX_OUTPUT_BYTES:
            _fail("author_output_invalid", "output bound")
    except (ValueError, TypeError, RecursionError) as exc:
        if isinstance(exc, StructuralAuthorError):
            raise
        _fail("author_output_invalid", "invalid bounded JSON")
    _authorities(output)
    _closed(output, {"candidate", "confidence", "needs_escalation", "escalation_reason"})
    confidence = output["confidence"]
    if type(confidence) not in {int, float} or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        _fail("author_output_invalid", "confidence must be finite 0..1")
    if type(output["needs_escalation"]) is not bool:
        _fail("author_output_invalid", "typed escalation flag")
    reason = output["escalation_reason"]
    if output["needs_escalation"]:
        if output["candidate"] is not None:
            _fail("author_output_invalid", "candidate plus escalation quarantined")
        _closed(reason, {"code", "message", "requested_capabilities"})
        if (type(reason["code"]) is not str or reason["code"] not in ESCALATIONS or type(reason["message"]) is not str
                or not 0 < len(reason["message"]) <= 512 or type(reason["requested_capabilities"]) is not list
                or len(reason["requested_capabilities"]) > 8
                or any(type(x) is not str or not 0 < len(x) <= 128 for x in reason["requested_capabilities"])):
            _fail("author_output_invalid", "bounded escalation required")
        return output, StructuralEscalation(reason["code"], reason["message"], tuple(reason["requested_capabilities"]))
    if reason is not None:
        _fail("author_output_invalid", "unexpected escalation reason")
    return output, None


def _candidate(scope, payload, measured):
    tick = perf_counter()
    _closed(payload, {"operations"})
    rows = payload["operations"]
    if type(rows) is not list or len(rows) > MAX_OPERATIONS:
        _fail("author_output_invalid", "bounded operations required")
    measured["candidate_normalization_seconds"] += perf_counter() - tick
    tick = perf_counter()
    expected = {(o.operation, o.physical_target, o.owner, o.definition_ids): o
                for o in scope.permitted_structural_operations}
    generated, seen, parsed = [], set(), []
    for row in rows:
        _closed(row, {"operation", "physical_target", "owner", "definition_ids", "source_text",
                      "existing_declaration", "removal_intent"}, "author_output_outside_admitted_scope")
        if (type(row["operation"]) is not str or row["operation"] not in OPERATION_KINDS
                or type(row["physical_target"]) is not str or type(row["owner"]) is not str
                or type(row["definition_ids"]) is not list
                or any(type(x) is not str for x in row["definition_ids"])):
            _fail("author_output_outside_admitted_scope", "exact operation identity required")
        ids = tuple(sorted(row["definition_ids"]))
        key = (row["operation"], row["physical_target"], row["owner"], ids)
        if key not in expected or key in seen or len(set(ids)) != len(ids):
            _fail("author_output_outside_admitted_scope", "unadmitted/duplicate operation")
        seen.add(key)
        operation = expected[key]
        remove = operation.operation == "remove_declaration"
        if (row["removal_intent"] is not remove or (remove and (row["source_text"] is not None
                or row["existing_declaration"] != json.loads(_json(asdict(operation.existing_declaration)))))
                or (not remove and row["existing_declaration"] is not None)):
            _fail("author_output_outside_admitted_scope", "removal identity/intention differs")
        source = row["source_text"]
        if not remove:
            if type(source) is not str or not source.strip():
                _fail("author_output_invalid", "generated Java source required")
            # Normalize transport newlines only; never regenerate existing bytes.
            source = source.replace("\r\n", "\n").replace("\r", "\n")
            package = next((t.package_name for t in scope.new_file_creation_targets
                            if t.physical_target == operation.physical_target), "")
            definitions = [a.definition for a in scope.definition_allowances if a.definition.identity in ids]
            parsed.append(parse_operation(operation, source, definitions, package_name=package, timings=measured,
                referenced_definitions=[a.definition for a in scope.definition_allowances]))
        generated.append(StructuralCandidateOperation(operation.operation, operation.physical_target,
            operation.owner, ids, source, operation.existing_declaration, remove))
    if seen != set(expected):
        _fail("author_output_incomplete", "all required admitted operations must be present atomically")
    check_contracts(parsed, scope)
    measured["admitted_scope_containment_seconds"] += max(0.0,
        perf_counter() - tick - measured["java_structural_parsing_seconds"])
    tick = perf_counter()
    candidate = StructuralPatchCandidate(scope.fingerprint, scope.implementation_plan_fingerprint,
        scope.task_fingerprint, scope.effective_design_fingerprint, scope.p1_fingerprint,
        scope.approval_receipt_fingerprint, scope.approved_ceiling_fingerprint, scope.repository_id,
        scope.repository_evidence_fingerprint, scope.source_bindings,
        tuple(t.absence_witness for t in scope.new_file_creation_targets),
        tuple(sorted(generated, key=lambda o: _json(asdict(o)))))
    candidate.fingerprint
    measured["candidate_fingerprint_seconds"] += perf_counter() - tick
    return candidate


def _normalize(scope, output, measured, *, calls=0, model_calls=0):
    tick = perf_counter()
    envelope, escalation = _envelope(output)
    measured["candidate_normalization_seconds"] += perf_counter() - tick
    if escalation:
        return StructuralAuthoringResult(escalation.code, None, escalation.message,
                                        envelope["confidence"], escalation, calls, model_calls)
    if envelope["candidate"] is None:
        return StructuralAuthoringResult("author_abstained", None, "typed abstention",
                                        envelope["confidence"], None, calls, model_calls)
    candidate = _candidate(scope, envelope["candidate"], measured)
    return StructuralAuthoringResult(candidate.status, candidate, "validated structural containment",
                                    envelope["confidence"], None, calls, model_calls)


def normalize_structural_author_output(*, admitted_scope, author_output, timings=None, **fresh_inputs):
    """Pure synthetic seam. Fresh lineage/evidence must be acquired by caller."""
    measured = {} if timings is None else timings
    measured.update({k: 0.0 for k in TIMING_FIELDS})
    start = perf_counter()
    try:
        checked = _fresh(admitted_scope, fresh_inputs, measured)
        return _normalize(checked, author_output, measured)
    except (StructuralAuthorError, StructuralJavaError) as exc:
        return StructuralAuthoringResult(exc.code, None, exc.reason, None, None, 0, 0)
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError):
        return StructuralAuthoringResult("author_output_invalid", None, "invalid typed output", None, None, 0, 0)
    finally:
        measured["total_deterministic_seconds"] = perf_counter() - start


def validate_structural_patch_candidate(candidate, *, admitted_scope, **fresh_inputs):
    """Pure future-consumer gate reconstructs candidate, admission and authority.

    Callers must reacquire exact path/source evidence immediately before using it.
    Historical candidate labels/fingerprints never lock paths or grant authority.
    """
    payload = candidate.as_dict() if type(candidate) is StructuralPatchCandidate else candidate
    if type(payload) is not dict:
        _fail("author_output_invalid", "closed candidate required")
    _authorities(payload)
    try:
        result = normalize_structural_author_output(admitted_scope=admitted_scope,
            author_output={"candidate": {"operations": payload.get("operations")}, "confidence": 1.0,
                           "needs_escalation": False, "escalation_reason": None}, **fresh_inputs)
        if result.candidate is None:
            _fail(result.status, result.reason)
        if _json(payload) != _json(result.candidate.as_dict()):
            _fail("candidate_stale", "candidate lineage, authority or fingerprint differs")
    except (ValueError, TypeError, RecursionError) as exc:
        if isinstance(exc, StructuralAuthorError):
            raise
        _fail("author_output_invalid", "invalid candidate JSON")
    return result.candidate


class ReadOnlyStructuralAuthor(Protocol):
    def author(self, context: StructuralAuthorContext) -> dict: ...


class StructuralAuthorInvocation:
    """One-shot call budget for one admitted operation; also safe across threads.

    Caller retains this object for the attempt. There is no retry/reset API or
    persistent session mutation. Live adapters mark model_backed=True explicitly.
    """
    def __init__(self, *, model_backed=False):
        if type(model_backed) is not bool:
            _fail("author_call_not_authorized", "typed provider provenance required")
        self._model_backed = model_backed
        self._used = False
        self._lock = Lock()

    def _claim(self):
        with self._lock:
            if self._used:
                _fail("second_author_call_forbidden")
            self._used = True

    def run(self, *, admitted_scope, repository_root, author: ReadOnlyStructuralAuthor,
            author_call_authorized=False, timings=None, **fresh_lineage_inputs):
        measured = {} if timings is None else timings
        measured.update({k: 0.0 for k in TIMING_FIELDS})
        start = perf_counter()
        calls = 0
        try:
            self._claim()
            # Never accept a caller's old path witness in this I/O facade.
            if "repository_evidence" in fresh_lineage_inputs:
                _fail("structural_author_scope_stale", "facade must reacquire path evidence")
            evidence = acquire_structural_admission_evidence(fresh_lineage_inputs["plan"],
                repository_root=repository_root, **fresh_lineage_inputs_without_plan(fresh_lineage_inputs))
            inputs = dict(fresh_lineage_inputs, repository_evidence=evidence)
            checked = _fresh(admitted_scope, inputs, measured)
            if author_call_authorized is not True:
                _fail("author_call_not_authorized")
            if author is None or not callable(getattr(author, "author", None)):
                _fail("author_provider_unavailable")
            context = _context(checked, inputs, measured)
            tick = perf_counter()
            calls = 1
            try:
                output = author.author(context)
            except Exception:
                _fail("author_provider_failure")
            finally:
                measured["provider_latency_seconds"] += perf_counter() - tick
            evidence = acquire_structural_admission_evidence(fresh_lineage_inputs["plan"],
                repository_root=repository_root, **fresh_lineage_inputs_without_plan(fresh_lineage_inputs))
            checked = _fresh(admitted_scope, dict(fresh_lineage_inputs, repository_evidence=evidence), measured)
            return _normalize(checked, output, measured, calls=calls,
                              model_calls=calls if self._model_backed else 0)
        except (StructuralAuthorError, StructuralJavaError, AdmissionError) as exc:
            return StructuralAuthoringResult(exc.code, None, exc.reason, None, None, calls,
                                            calls if self._model_backed else 0)
        except (ValueError, TypeError, AttributeError, KeyError, RecursionError):
            return StructuralAuthoringResult("author_output_invalid", None, "invalid typed input/output", None, None,
                                            calls, calls if self._model_backed else 0)
        finally:
            measured["total_deterministic_seconds"] = max(0.0,
                perf_counter() - start - measured["provider_latency_seconds"])


def fresh_lineage_inputs_without_plan(inputs):
    return {k: v for k, v in inputs.items() if k != "plan"}
