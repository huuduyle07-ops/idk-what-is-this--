"""OOP.INTENT.CONTINUE.1: immutable, read-only answer revision and facade.

Callers supply the original stored gap and answer independently at re-entry.
A digest is an identity, not proof: validation reconstructs the entire chain
from the preserved task, exact current source context and stored answer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping

from core.clarification_answer_evidence import (
    AnswerCommitment, AnswerConflict, extract_clarification_answer,
)
from core.explicit_design_evidence import EvidenceSpan
from core.oop_intent_session import bind_human_answer, make_stored_future_design_gap
from core.proposed_design_intent import ProposedDesignIntent, project_proposed_design_intent
from core.repository_identity import derive_repository_id

PHASE_ID = "OOP.INTENT.CONTINUE.1"
SCHEMA_VERSION = "oop_intent_continue_1_v1"


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DesignIntentContinuation:
    status: str
    parent_design_fingerprint: str
    parent_gap_id: str
    task_contract_fingerprint: str
    answer_fingerprint: str
    answer_record_fingerprint: str
    repository_id: str
    source_path: str
    source_fingerprint: str
    class_identity: str
    typed_answer_commitments: tuple[AnswerCommitment, ...]
    resolved_dimensions: tuple[str, ...]
    remaining_dimensions: tuple[str, ...]
    conflicts: tuple[AnswerConflict, ...] = ()
    not_resolved_by_continuation: tuple[EvidenceSpan, ...] = ()
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    provenance: str = field(default="explicit_human", init=False)
    authority: str = field(default="read_only", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.status not in {"clarification_projected", "answer_projection_bounded", "continuation_conflict"}:
            raise ValueError("invalid_continuation_status")
        for name, kind, limit in (
            ("typed_answer_commitments", AnswerCommitment, 96),
            ("resolved_dimensions", str, 7), ("remaining_dimensions", str, 7),
            ("conflicts", AnswerConflict, 64),
            ("not_resolved_by_continuation", EvidenceSpan, 96),
        ):
            items = getattr(self, name)
            if not isinstance(items, tuple) or len(items) > limit or any(not isinstance(x, kind) for x in items):
                raise ValueError("invalid_continuation_bounds")
        for name in ("parent_design_fingerprint", "parent_gap_id", "task_contract_fingerprint",
                     "answer_fingerprint", "answer_record_fingerprint", "source_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("invalid_continuation_fingerprint")
        if set(self.resolved_dimensions) & set(self.remaining_dimensions):
            raise ValueError("invalid_dimension_partition")

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def continuation_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return json.loads(_json({**asdict(self), "continuation_fingerprint": self.fingerprint}))


def continue_design_intent(*, task_contract, base_design, stored_gap, stored_answer,
                           current_context, current_source, repo_path, previous=None,
                           timings: dict | None = None) -> DesignIntentContinuation:
    """Validate an exact original gap, then type its bound answer deterministically.

    No disk access, traversal, session writes, ordinary answer intake or model
    calls. The source buffer must be freshly acquired by the session adapter.
    """
    from time import perf_counter
    from core.oop_intent_detector import detect_missing_future_design_contract

    if not isinstance(base_design, ProposedDesignIntent):
        raise ValueError("base_projection_mismatch")
    baseline = project_proposed_design_intent(task_contract)
    if base_design.as_dict() != baseline.as_dict():
        raise ValueError("base_projection_mismatch")
    if not isinstance(stored_gap, Mapping) or not isinstance(stored_answer, Mapping):
        raise ValueError("stored_binding_required")
    if (not current_context or not isinstance(current_source, bytes)
            or sha256(current_source).hexdigest() != stored_gap.get("source_fingerprint")
            or current_context.source_fingerprint != stored_gap.get("source_fingerprint")):
        raise ValueError("reacquisition_required")
    repository_id = derive_repository_id(repo_path)
    detection = detect_missing_future_design_contract(
        task_contract=task_contract, design_intent=base_design,
        current_context=current_context, current_source=current_source,
        repository_id=repository_id)
    expected_gap = make_stored_future_design_gap(
        detection, task_text=task_contract.raw_request.text, repo_path=repo_path)
    if expected_gap is None or _json(dict(stored_gap)) != _json(expected_gap):
        raise ValueError("parent_gap_binding_mismatch")
    try:
        answer = bind_human_answer(expected_gap, stored_answer.get("text", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError("answer_binding_mismatch") from exc
    if answer.as_dict() != dict(stored_answer):
        raise ValueError("answer_binding_mismatch")
    extraction_start = perf_counter()
    evidence = extract_clarification_answer(answer, expected_gap["subdimensions"], base_design)
    construction_start = perf_counter()
    resolved = tuple(d for d in expected_gap["subdimensions"]
                     if any(item.dimension == d for item in evidence.commitments))
    remaining = tuple(d for d in expected_gap["subdimensions"] if d not in resolved)
    status = ("continuation_conflict" if evidence.conflicts else
              "answer_projection_bounded" if evidence.not_resolved_by_continuation or not resolved else
              "clarification_projected")
    # A conflict cannot resolve anything in the effective design.
    if evidence.conflicts:
        resolved, remaining = (), tuple(expected_gap["subdimensions"])
    result = DesignIntentContinuation(
        status=status, parent_design_fingerprint=base_design.fingerprint,
        parent_gap_id=expected_gap["gap_id"],
        task_contract_fingerprint=base_design.task_contract_fingerprint,
        answer_fingerprint=answer.answer_fingerprint,
        answer_record_fingerprint=_hash(answer.as_dict()),
        repository_id=repository_id, source_path=expected_gap["source_path"],
        source_fingerprint=expected_gap["source_fingerprint"],
        class_identity=expected_gap["class_identity"],
        typed_answer_commitments=evidence.commitments,
        resolved_dimensions=resolved, remaining_dimensions=remaining,
        conflicts=evidence.conflicts,
        not_resolved_by_continuation=evidence.not_resolved_by_continuation)
    if previous is not None:
        payload = previous.as_dict() if isinstance(previous, DesignIntentContinuation) else previous
        if payload != result.as_dict():
            raise ValueError("clarification_conflict")
    if timings is not None:
        timings.update(answer_extraction_seconds=construction_start-extraction_start,
                       continuation_construction_seconds=perf_counter()-construction_start)
    return result


@dataclass(frozen=True, slots=True)
class EffectiveProposedDesignIntent:
    base: ProposedDesignIntent
    continuation: DesignIntentContinuation

    def __post_init__(self):
        if not isinstance(self.base, ProposedDesignIntent) or not isinstance(self.continuation, DesignIntentContinuation):
            raise ValueError("typed_continuation_required")
        if self.base.fingerprint != self.continuation.parent_design_fingerprint:
            raise ValueError("parent_design_mismatch")

    # Only unresolved dimensions change. All structural commitments, their
    # provenance and the base fingerprint remain owned by the original object.
    @property
    def unresolved_dimensions(self):
        resolved = self.continuation.resolved_dimensions if self.continuation.status == "clarification_projected" else ()
        return tuple(item for item in self.base.unresolved_dimensions if item.dimension not in resolved)

    @property
    def status(self):
        return {"continuation_conflict": "conflict", "answer_projection_bounded": "bounded"}.get(self.continuation.status, self.base.status)

    def __getattr__(self, name):
        # Deliberately closed delegation; no arbitrary projection overrides.
        if name in {"relationships", "state_commitments", "behavior_gates", "explicit_absences",
                    "task_contract_fingerprint", "raw_request_fingerprint", "semantic_interpretation_fingerprint",
                    "authority", "write_authority", "repair_scope_authority", "conflicts", "overflow"}:
            return getattr(self.base, name)
        if name in {"execution_authorized", "auto_apply"}:
            return False
        raise AttributeError(name)

    @property
    def fingerprint(self):
        return _hash(self.as_dict())

    def as_dict(self):
        return json.loads(_json({"schema_version": "oop_intent_effective_1_v1", "status": self.status,
                "parent_design_fingerprint": self.base.fingerprint,
                "base": self.base.as_dict(), "continuation": self.continuation.as_dict(),
                "unresolved_dimensions": [item.as_dict() for item in self.unresolved_dimensions],
                "authority": "read_only", "write_authority": False, "execution_authorized": False,
                "auto_apply": False, "repair_scope_authority": False}))


def compose_effective_design(base_design, continuation):
    return EffectiveProposedDesignIntent(base_design, continuation)


def validate_effective_design(*, task_contract, design_intent, current_context,
                              current_source, repo_path, stored_gap, stored_answer):
    if not isinstance(design_intent, EffectiveProposedDesignIntent):
        raise ValueError("typed_continuation_required")
    expected = continue_design_intent(
        task_contract=task_contract, base_design=design_intent.base,
        stored_gap=stored_gap, stored_answer=stored_answer, current_context=current_context,
        current_source=current_source, repo_path=repo_path)
    if design_intent.continuation.as_dict() != expected.as_dict():
        raise ValueError("forged_continuation")
    if design_intent.as_dict() != compose_effective_design(design_intent.base, expected).as_dict():
        raise ValueError("effective_projection_mismatch")
    if expected.status == "continuation_conflict":
        raise ValueError("continuation_conflict")
