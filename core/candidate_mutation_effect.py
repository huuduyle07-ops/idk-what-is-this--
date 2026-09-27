"""PATCH.MINIMAL.LIVE.1 — exact no-op candidate rejection.

Round 7 authored a candidate whose ``patched_snippet`` was byte-identical to
its ``target_snippet``::

    target_snippet == patched_snippet

``safe_minimal`` accepted it, and it was right to.  The candidate introduced no
identifier and was structurally tiny, and the existing no-op heuristic in
``patching.patch_gates._looks_like_noop_patch`` looks for an emptied or
degenerate function *body* — not for exact replacement equality.  Shape safety
is shape safety.

So the read-only verification chain caught it instead, correctly and much
later: it built a disposable sandbox, applied the candidate there, re-ran the
defect probe, found the primary defect still reproduced and rejected the
candidate.  Roughly 3.65 s of sandbox and 4.29 s of paired probe were spent
proving that identical bytes do nothing.  The harness was safe.  It was
wasteful, and it was semantically late.

This module owns one cheap deterministic invariant and nothing else:

    a patch candidate that changes zero authoritative bytes
    is not a meaningful patch candidate.

**Exact bytes only.**  Whitespace, indentation, line endings, encoding,
comments, syntax and formatting are deliberately *not* normalized.  A CRLF/LF
delta and a re-indentation are real repository changes owned by byte-preserving
semantics; claiming them here would make this gate a formatting policy, which
it is not.  The comparison is::

    authoritative original bytes == authoritative proposed replacement bytes

**It is not a semantic verdict.**  A no-op candidate says nothing about whether
the model's diagnosis was correct — Round 7 in fact had a correct diagnosis and
an empty implementation delta.  ``candidate_effect`` answers "did the model
propose a change?"; whether a proposed change is the *right* change stays with
CANDIDATE.VERIFY.LIVE.1, unchanged, for every candidate whose bytes differ.

**It grants nothing.**  Rejection can only narrow: ``human_review_eligible``,
``candidate_review_ready`` and ``approval_ready`` are written ``False`` and
never ``True``, and no execution, authority or approval semantics are touched.

The evaluator is pure.  It reads the bounded target/replacement representation
the patch-safety and candidate pipeline already consumes and re-reads nothing:
no repository access, no traversal, no model call, no network call, no
subprocess, no probe and no validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Iterable, Mapping, MutableMapping, Sequence


PHASE_ID = "PATCH.MINIMAL.LIVE.1"
SCHEMA_VERSION = "patch_minimal_live_1_v1"

# ── Candidate effect vocabulary ─────────────────────────────────────────────
#
# Three values, and none of them is an execution result.  Nothing has run when
# this is decided, so "failed" would be a lie in every direction.
CANDIDATE_EFFECT_NOT_APPLICABLE = "not_applicable"
CANDIDATE_EFFECT_NO_OP = "no_op"
CANDIDATE_EFFECT_MUTATING = "mutating"
CANDIDATE_EFFECT_STATUSES: tuple[str, ...] = (
    CANDIDATE_EFFECT_NOT_APPLICABLE,
    CANDIDATE_EFFECT_NO_OP,
    CANDIDATE_EFFECT_MUTATING,
)

#: A payload written before this phase carries no effect measurement at all.
#: It reads back as its own value — never ``mutating`` — and historical
#: artifacts are not rewritten to pretend a gate ran that did not exist.
CANDIDATE_EFFECT_LEGACY_UNMEASURED = "legacy_unmeasured"

# ── Per-operation effect vocabulary ─────────────────────────────────────────
OPERATION_EFFECT_EXACT_NO_OP = "exact_no_op"
OPERATION_EFFECT_MUTATING = "mutating"
#: Both byte sides were not available, so this operation is not *claimed* to be
#: a no-op.  Fail-open is the safe direction here: rejection is the aggressive
#: action, and an unprovable operation must never trigger it.
OPERATION_EFFECT_UNDETERMINED = "undetermined"
OPERATION_EFFECTS: tuple[str, ...] = (
    OPERATION_EFFECT_EXACT_NO_OP,
    OPERATION_EFFECT_MUTATING,
    OPERATION_EFFECT_UNDETERMINED,
)

# ── Closed rejection-reason vocabulary ──────────────────────────────────────
#
# Nothing was executed, so the reason may not borrow execution vocabulary.
REASON_NO_OP_CANDIDATE = "no_op_candidate"
REJECTION_REASONS: tuple[str, ...] = (REASON_NO_OP_CANDIDATE,)

#: ``replace_snippet`` is the one operation shape that carries both byte sides.
_OP_REPLACE_SNIPPET = "replace_snippet"
#: ``create_file`` writes a file the executor has already refused to overwrite,
#: so it changes repository bytes by construction and can never be a no-op.
_OP_CREATE_FILE = "create_file"

#: Plan-operation keys kept verbatim in the debugging copy of a rejected
#: candidate.  The receipt itself carries no source (§18).
_PLAN_KEYS: tuple[str, ...] = (
    "op",
    "relative_path",
    "file",
    "target_snippet",
    "patched_snippet",
    "content",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _operation_bytes(operation: Mapping[str, Any]) -> tuple[bytes | None, bytes | None]:
    """The authoritative original and replacement bytes for one operation.

    Only the bounded representation the candidate pipeline already carries is
    read.  The repository is never consulted: if the harness already holds the
    authoritative bytes, re-reading them would add a traversal for no new fact,
    and if it does not, this gate has nothing to say.
    """

    target = operation.get("target_snippet")
    replacement = operation.get("patched_snippet")
    if not isinstance(target, str) or not isinstance(replacement, str):
        return None, None
    return target.encode("utf-8"), replacement.encode("utf-8")


@dataclass(frozen=True, slots=True)
class OperationEffect:
    """What one authoritative patch operation does to repository bytes."""

    index: int
    op: str
    relative_path: str
    effect: str

    def __post_init__(self) -> None:
        if self.effect not in OPERATION_EFFECTS:
            raise ValueError(f"unsupported operation effect: {self.effect!r}")

    @property
    def exact_no_op(self) -> bool:
        return self.effect == OPERATION_EFFECT_EXACT_NO_OP

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "op": self.op,
            "relative_path": self.relative_path,
            "effect": self.effect,
        }


def classify_operation(index: int, operation: Any) -> OperationEffect:
    """Classify one operation by exact byte equality, and by nothing else."""

    mapping: Mapping[str, Any] = (
        operation if isinstance(operation, Mapping) else {}
    )
    op_type = _text(mapping.get("op"))
    path = _normalized_path(mapping.get("relative_path") or mapping.get("file"))

    if op_type == _OP_CREATE_FILE:
        effect = OPERATION_EFFECT_MUTATING
    else:
        original, replacement = _operation_bytes(mapping)
        if original is None or replacement is None:
            effect = OPERATION_EFFECT_UNDETERMINED
        elif original == replacement:
            effect = OPERATION_EFFECT_EXACT_NO_OP
        else:
            effect = OPERATION_EFFECT_MUTATING

    return OperationEffect(
        index=index,
        op=op_type or _OP_REPLACE_SNIPPET,
        relative_path=path,
        effect=effect,
    )


@dataclass(frozen=True, slots=True)
class CandidateMutationEffect:
    """One closed statement about what an authored candidate changes."""

    status: str = CANDIDATE_EFFECT_NOT_APPLICABLE
    rejection_reason: str = ""
    operations: tuple[OperationEffect, ...] = ()
    candidate_fingerprint: str = ""
    rejected_candidate: tuple[dict[str, Any], ...] = ()
    evaluation_seconds: float = 0.0
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in CANDIDATE_EFFECT_STATUSES:
            raise ValueError(f"unsupported candidate effect: {self.status!r}")
        if self.rejection_reason and self.rejection_reason not in REJECTION_REASONS:
            raise ValueError(f"unsupported rejection reason: {self.rejection_reason!r}")

    # ── the invariant, read three ways ──────────────────────────────────────

    @property
    def exact_no_effect(self) -> bool:
        """Every authoritative operation changes zero bytes."""

        return self.status == CANDIDATE_EFFECT_NO_OP

    @property
    def candidate_authored(self) -> bool:
        return bool(self.operations)

    @property
    def candidate_accepted(self) -> bool:
        """Acceptance *by this gate* only.  It is not review, approval or authority."""

        return self.candidate_authored and not self.exact_no_effect

    # ── counts (§18) ────────────────────────────────────────────────────────

    def _count(self, effect: str) -> int:
        return sum(1 for item in self.operations if item.effect == effect)

    @property
    def exact_no_op_operation_count(self) -> int:
        return self._count(OPERATION_EFFECT_EXACT_NO_OP)

    @property
    def mutating_operation_count(self) -> int:
        return self._count(OPERATION_EFFECT_MUTATING)

    @property
    def undetermined_operation_count(self) -> int:
        return self._count(OPERATION_EFFECT_UNDETERMINED)

    # ── receipts ────────────────────────────────────────────────────────────

    def as_dict(self) -> dict[str, Any]:
        """The receipt.  Deterministic, and free of candidate source bytes."""

        payload = {
            "phase_id": PHASE_ID,
            "schema_version": self.schema_version,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "candidate_fingerprint": self.candidate_fingerprint,
            "candidate_authored": self.candidate_authored,
            "candidate_accepted": self.candidate_accepted,
            "operations": [item.as_dict() for item in self.operations],
            "exact_no_op_operation_count": self.exact_no_op_operation_count,
            "mutating_operation_count": self.mutating_operation_count,
            "undetermined_operation_count": self.undetermined_operation_count,
        }
        payload["effect_fingerprint"] = _fingerprint(payload)
        return payload

    def as_telemetry(self) -> dict[str, Any]:
        """The additive bounded facts this phase writes onto a payload (§18)."""

        receipt = self.as_dict()
        return {
            "candidate_effect_phase_id": PHASE_ID,
            "candidate_effect_schema_version": self.schema_version,
            "candidate_effect_status": self.status,
            "candidate_effect_rejection_reason": self.rejection_reason,
            "candidate_effect_candidate_fingerprint": self.candidate_fingerprint,
            "candidate_effect_authored": self.candidate_authored,
            "candidate_effect_accepted": self.candidate_accepted,
            "candidate_effect_operations": [
                item.as_dict() for item in self.operations
            ],
            "candidate_effect_receipt": receipt,
            "candidate_effect_fingerprint": receipt["effect_fingerprint"],
            "candidate_effect_evaluation_seconds": self.evaluation_seconds,
            "candidate_effect_model_calls": 0,
            "candidate_effect_network_calls": 0,
            "candidate_effect_repository_reads": 0,
            "candidate_effect_repository_mutations": 0,
            "exact_no_op_operation_count": self.exact_no_op_operation_count,
            "mutating_operation_count": self.mutating_operation_count,
            "undetermined_operation_count": self.undetermined_operation_count,
        }

    def as_issue(self) -> dict[str, Any]:
        """The rejection in the payload's canonical structured ``issues`` shape."""

        paths = sorted(
            {item.relative_path for item in self.operations if item.relative_path}
        )
        return {
            "severity": "high",
            "type": "candidate_effect",
            "file": paths[0] if len(paths) == 1 else "",
            "symbol": "",
            "reason": (
                f"Rejected as {REASON_NO_OP_CANDIDATE}: the candidate's "
                f"replacement bytes are identical to its target bytes across "
                f"all {self.exact_no_op_operation_count} operation(s), so it "
                "changes nothing in the repository. Nothing was executed, and "
                "the model's diagnosis was not judged."
            ),
            "fix": (
                "Re-author the candidate so the replacement differs from the "
                "target, or escalate: the described change was never written."
            ),
        }


def evaluate_candidate_mutation_effect(
    candidate_plan: Any,
    *,
    candidate_fingerprint: str = "",
) -> CandidateMutationEffect:
    """Decide what an authored candidate changes, from bytes already in hand.

    ``candidate_fingerprint`` is supplied by the caller from the lifecycle's
    existing primitive rather than recomputed here: this phase deliberately
    introduces no second candidate-identity primitive (§12).
    """

    started = time.perf_counter()
    operations = tuple(
        classify_operation(index, operation)
        for index, operation in enumerate(_iter_operations(candidate_plan))
    )
    if not operations:
        status = CANDIDATE_EFFECT_NOT_APPLICABLE
        reason = ""
    elif all(item.exact_no_op for item in operations):
        status = CANDIDATE_EFFECT_NO_OP
        reason = REASON_NO_OP_CANDIDATE
    else:
        # §4 — a candidate with any real mutation effect keeps every operation
        # the model wrote.  Silently deleting its redundant operations would be
        # a rewrite policy this phase does not have.
        status = CANDIDATE_EFFECT_MUTATING
        reason = ""

    rejected = (
        _debug_copy(candidate_plan) if status == CANDIDATE_EFFECT_NO_OP else ()
    )
    return CandidateMutationEffect(
        status=status,
        rejection_reason=reason,
        operations=operations,
        candidate_fingerprint=str(candidate_fingerprint or ""),
        rejected_candidate=rejected,
        evaluation_seconds=round(time.perf_counter() - started, 6),
    )


def _iter_operations(candidate_plan: Any) -> Iterable[Mapping[str, Any]]:
    if not isinstance(candidate_plan, Sequence) or isinstance(
        candidate_plan, (str, bytes)
    ):
        return ()
    return [item for item in candidate_plan if isinstance(item, Mapping)]


def _debug_copy(candidate_plan: Any) -> tuple[dict[str, Any], ...]:
    """§10 — the authored bytes stay inspectable, verbatim and unusable."""

    return tuple(
        {key: item[key] for key in _PLAN_KEYS if key in item}
        for item in _iter_operations(candidate_plan)
    )


def reject_exact_no_op_candidate(
    block: MutableMapping[str, Any],
    effect: CandidateMutationEffect,
) -> bool:
    """Apply the rejection to one writer payload.  Returns whether it fired.

    A candidate with real mutation effect leaves this function having changed
    nothing at all — the gate is a guard, not a rewriter.

    For an exact no-op the payload is made unambiguous.  The candidate is
    removed because it is not a patch, and the model's authored bytes are kept
    under a harness-owned debugging key so the output stays explainable without
    being presented as something a human could approve.  Every flag written
    here narrows; none can grant.
    """

    if not isinstance(block, MutableMapping):
        return False
    if effect.status != CANDIDATE_EFFECT_NO_OP:
        return False

    block.update(effect.as_telemetry())
    block["candidate_effect_rejected_candidate"] = [
        dict(item) for item in effect.rejected_candidate
    ]

    # §9 — no usable candidate survives, in either candidate shape.
    block["patch_candidate"] = None
    block["patch_plan"] = None

    # §9/§19 — narrowing only.  These are never set ``True`` from here.
    block["needs_escalation"] = True
    block["human_review_eligible"] = False
    block["candidate_review_ready"] = False
    block["approval_ready"] = False
    block["eligible_for_patch_safety_handoff"] = False
    # §10 — visible for debugging, never "ready to approve or apply".
    block["candidate_visible_for_debugging"] = True

    issues = block.get("issues")
    if not isinstance(issues, list):
        issues = []
    issues.insert(0, effect.as_issue())
    block["issues"] = issues
    return True


def candidate_effect_status_of_payload(block: Any) -> str:
    """What a payload's stored effect measurement says, legacy included."""

    if not isinstance(block, Mapping):
        return CANDIDATE_EFFECT_LEGACY_UNMEASURED
    status = _text(block.get("candidate_effect_status"))
    if status in CANDIDATE_EFFECT_STATUSES:
        return status
    return CANDIDATE_EFFECT_LEGACY_UNMEASURED


def payload_rejected_as_exact_no_op(block: Any) -> bool:
    return candidate_effect_status_of_payload(block) == CANDIDATE_EFFECT_NO_OP


def describe_candidate_mutation_effect(effect: CandidateMutationEffect) -> str:
    """One line an operator can act on, that claims nothing extra."""

    if effect.status == CANDIDATE_EFFECT_NOT_APPLICABLE:
        return "No candidate was authored, so there was no mutation effect to measure."
    if effect.status == CANDIDATE_EFFECT_MUTATING:
        return (
            f"Exact candidate effect: mutating "
            f"({effect.mutating_operation_count} of {len(effect.operations)} "
            "operation(s) change bytes)."
        )
    return (
        "Exact candidate effect: no_op — the replacement bytes are identical to "
        "the target bytes in every operation, so the model proposed no "
        "repository change. This is a statement about mutation effect only; the "
        "diagnosis behind it was not judged here, and nothing was executed."
    )


__all__ = [
    "CANDIDATE_EFFECT_LEGACY_UNMEASURED",
    "CANDIDATE_EFFECT_MUTATING",
    "CANDIDATE_EFFECT_NOT_APPLICABLE",
    "CANDIDATE_EFFECT_NO_OP",
    "CANDIDATE_EFFECT_STATUSES",
    "OPERATION_EFFECTS",
    "OPERATION_EFFECT_EXACT_NO_OP",
    "OPERATION_EFFECT_MUTATING",
    "OPERATION_EFFECT_UNDETERMINED",
    "PHASE_ID",
    "REASON_NO_OP_CANDIDATE",
    "REJECTION_REASONS",
    "SCHEMA_VERSION",
    "CandidateMutationEffect",
    "OperationEffect",
    "candidate_effect_status_of_payload",
    "classify_operation",
    "describe_candidate_mutation_effect",
    "evaluate_candidate_mutation_effect",
    "payload_rejected_as_exact_no_op",
    "reject_exact_no_op_candidate",
]
