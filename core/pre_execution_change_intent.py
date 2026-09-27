"""WORKER.DECL.2B — pre-execution change intent channel.

The same already-scheduled worker invocation emits two sibling structures:
``patch_plan`` and ``change_intent``.  The software does not derive either one
from the other.  That makes intent an independently declared channel, but not
independent evidence: both fields have the same model lineage.

This module is observation-only.  It cannot select or alter a patch plan, grant
path authority, retry a model, run validation, or traverse a repository.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.live_worker_declaration import (
    DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
    DECLARATION_STAGE_PRE_EXECUTION_INTENT,
    WORKER_CLAIM_PARTIAL,
    WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2,
    DeclaredChangeClaim,
    WorkerChangeDeclaration,
)
from core.strict_envelope_emission import (
    PROVIDER_FAMILIES,
    PROVIDER_UNKNOWN,
    STRATEGY_LEGACY_PROMPT,
    TRANSPORT_STRATEGIES,
    StrictEmissionDirective,
)
from core.worker_patch_envelope import (
    INTENT_CHANGE_ADDED,
    INTENT_CHANGE_MODIFIED,
    OPERATION_CREATE_FILE,
    OPERATION_REPLACE_SNIPPET,
    PARSE_STATUSES,
    PRE_EXECUTION_INTENT_STAGE,
    STATUS_VALID,
    WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2,
    PreExecutionChangeIntent,
    WorkerPatchEnvelope,
    parse_strict_worker_patch_envelope_v2,
    worker_patch_envelope_fingerprint,
)


PHASE_ID = "WORKER.DECL.2B"
PRODUCER_KIND = "pre_execution_change_intent_observation"
INTENT_OBSERVATION_SCHEMA_VERSION = "worker_decl_2b_intent_observation_v1"
DURABLE_INTENT_RECEIPT_SCHEMA_VERSION = "worker_decl_2b_durable_intent_receipt_v1"
INTENT_ARTIFACT_NAME = "pre_execution_change_intent.json"

#: Additional opt-in composed with WORKER.DECL.2A.1's strict transport flag.
#: It cannot enroll a legacy call by itself.
ENVIRONMENT_FLAG = "PRE_EXECUTION_CHANGE_INTENT"

STRICT_V2_NOT_REQUESTED = "not_requested"

INTENT_PLAN_AGREED = "agreed"
INTENT_MISSING_PLAN_CHANGE = "intent_missing_plan_change"
PLAN_CHANGE_MISSING_INTENT = "plan_change_missing_intent"
INTENT_PLAN_KIND_MISMATCH = "kind_mismatch"
INTENT_PLAN_MIXED = "mixed"
INTENT_PLAN_UNAVAILABLE = "unavailable"
INTENT_PLAN_AGREEMENTS: tuple[str, ...] = (
    INTENT_PLAN_AGREED,
    INTENT_MISSING_PLAN_CHANGE,
    PLAN_CHANGE_MISSING_INTENT,
    INTENT_PLAN_KIND_MISMATCH,
    INTENT_PLAN_MIXED,
    INTENT_PLAN_UNAVAILABLE,
)

INTENT_OBSERVED_AGREED = "agreed"
INTENDED_NOT_OBSERVED = "intended_not_observed"
OBSERVED_NOT_INTENDED = "observed_not_intended"
INTENDED_KIND_MISMATCH = "intended_kind_mismatch"
INTENT_OBSERVED_MIXED = "mixed"
INTENT_OBSERVED_UNAVAILABLE = "unavailable"
INTENT_OBSERVED_RELATIONS: tuple[str, ...] = (
    INTENT_OBSERVED_AGREED,
    INTENDED_NOT_OBSERVED,
    OBSERVED_NOT_INTENDED,
    INTENDED_KIND_MISMATCH,
    INTENT_OBSERVED_MIXED,
    INTENT_OBSERVED_UNAVAILABLE,
)

MAX_IDENTITY_CHARS = 160
MAX_DIAGNOSTIC_PATHS = 256

PLAN_OPERATION_CHANGE_KINDS: dict[str, str] = {
    OPERATION_CREATE_FILE: INTENT_CHANGE_ADDED,
    OPERATION_REPLACE_SNIPPET: INTENT_CHANGE_MODIFIED,
}


def is_pre_execution_change_intent_enabled(value: Any = None) -> bool:
    """Default off; only an explicit truthy value enables v2 emission."""
    raw = os.getenv(ENVIRONMENT_FLAG) if value is None else value
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


STRICT_V2_PROMPT_BLOCK = "\n".join(
    (
        "",
        "[STRICT PATCH ENVELOPE V2 - OUTPUT TRANSPORT ONLY]",
        "This section changes only the format your answer is transported in.",
        "Return ONLY valid JSON with no Markdown, fences, explanation, preface,",
        "or trailing text. The first character must be `{` and the last `}`.",
        "",
        "Emit exactly one WorkerPatchEnvelope v2 object with exactly three keys:",
        "{",
        '  "schema_version": "' + WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2 + '",',
        '  "patch_plan": [',
        '    {"op": "create_file", "relative_path": "...", "content": "..."},',
        '    {"op": "replace_snippet", "relative_path": "...",',
        '     "target_snippet": "...", "patched_snippet": "..."}',
        "  ],",
        '  "change_intent": {',
        '    "stage": "pre_execution_intent",',
        '    "intended_changes": [',
        '      {"path": "explicit/repository-relative/path",',
        '       "change_kind": "added|modified"}',
        "    ]",
        "  }",
        "}",
        "",
        "change_intent declaratively describes intended repository effects.",
        "It does not replace, add, remove, or authorize patch operations.",
        "Declare every intended path explicitly. Do not infer or copy paths in",
        "software: patch_plan and change_intent are separate model-emitted fields.",
        "No other top-level or nested key is allowed.",
        "Do not add permission, approval, validation, merge, or authority fields.",
        "",
    )
)


def intent_emission_directive(
    directive: StrictEmissionDirective | None,
    value: Any = None,
) -> StrictEmissionDirective | None:
    """Upgrade an enrolled strict request to v2, leaving every off path exact."""
    if not is_pre_execution_change_intent_enabled(value):
        return directive
    if directive is None or not directive.applies:
        return directive
    return StrictEmissionDirective(
        strategy=directive.strategy,
        provider_family=directive.provider_family,
        prompt_suffix=STRICT_V2_PROMPT_BLOCK,
        response_mime_type=directive.response_mime_type,
    )


def _plan_changes(plan: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Project typed operation structure for diagnostics, never for intent."""
    changes: dict[str, str] = {}
    for operation in plan:
        if not isinstance(operation, Mapping):
            continue
        kind = PLAN_OPERATION_CHANGE_KINDS.get(operation.get("op"))
        path = operation.get("relative_path") or operation.get("file")
        if kind is not None and isinstance(path, str):
            # Same execution semantics as the legacy CHECK.LIVE.1 projection:
            # the last operation on a path describes its final planned kind.
            changes[path] = kind
    return changes


def intent_plan_agreement(envelope: WorkerPatchEnvelope | None) -> str:
    """Compare the two model-emitted siblings without enforcing equality."""
    if (
        type(envelope) is not WorkerPatchEnvelope
        or envelope.change_intent is None
    ):
        return INTENT_PLAN_UNAVAILABLE
    intent = {
        item.path: item.change_kind
        for item in envelope.change_intent.intended_changes
    }
    plan = _plan_changes(envelope.patch_plan)
    categories: set[str] = set()
    if set(intent) - set(plan):
        categories.add(INTENT_MISSING_PLAN_CHANGE)
    if set(plan) - set(intent):
        categories.add(PLAN_CHANGE_MISSING_INTENT)
    if any(intent[path] != plan[path] for path in set(intent) & set(plan)):
        categories.add(INTENT_PLAN_KIND_MISMATCH)
    if not categories:
        return INTENT_PLAN_AGREED
    if len(categories) == 1:
        return next(iter(categories))
    return INTENT_PLAN_MIXED


@dataclass(frozen=True, slots=True)
class PreExecutionIntentCapture:
    """Frozen result of parsing one already-received response as v2."""

    provider_family: str
    transport_strategy: str
    strict_v2_status: str
    intent_plan_agreement: str
    envelope: WorkerPatchEnvelope | None = None
    unknown_keys: tuple[str, ...] = ()
    schema_version: str = INTENT_OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.provider_family not in PROVIDER_FAMILIES:
            raise ValueError("unsupported provider family")
        if self.transport_strategy not in TRANSPORT_STRATEGIES:
            raise ValueError("unsupported transport strategy")
        if self.strict_v2_status not in PARSE_STATUSES + (STRICT_V2_NOT_REQUESTED,):
            raise ValueError("unsupported strict v2 status")
        if self.intent_plan_agreement not in INTENT_PLAN_AGREEMENTS:
            raise ValueError("unsupported intent-plan agreement")
        if (self.envelope is None) is (self.strict_v2_status == STATUS_VALID):
            raise ValueError("exactly a valid v2 parse carries an envelope")
        if self.envelope is not None and self.envelope.change_intent is None:
            raise ValueError("a captured v2 envelope must carry native intent")

    @property
    def native_intent_available(self) -> bool:
        return self.envelope is not None

    @property
    def intent(self) -> PreExecutionChangeIntent | None:
        return self.envelope.change_intent if self.envelope is not None else None

    @property
    def intent_fingerprint(self) -> str | None:
        return self.intent.fingerprint if self.intent is not None else None

    @property
    def envelope_fingerprint(self) -> str | None:
        return (
            worker_patch_envelope_fingerprint(self.envelope)
            if self.envelope is not None
            else None
        )

    @property
    def authoritative_effect(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_kind": PRODUCER_KIND,
            "phase_id": PHASE_ID,
            "provider_family": self.provider_family,
            "transport_strategy": self.transport_strategy,
            "strict_v2_status": self.strict_v2_status,
            "native_intent_available": self.native_intent_available,
            "declaration_stage": (
                PRE_EXECUTION_INTENT_STAGE
                if self.native_intent_available
                else None
            ),
            "source_provenance": (
                DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT
                if self.native_intent_available
                else "unavailable"
            ),
            "channel_provenance": (
                "independently_declared_channel"
                if self.native_intent_available
                else "unavailable"
            ),
            "intent_fingerprint": self.intent_fingerprint,
            "envelope_fingerprint": self.envelope_fingerprint,
            "intent_plan_agreement": self.intent_plan_agreement,
            "unknown_keys": list(self.unknown_keys),
            "intent_fidelity_measurable": self.native_intent_available,
            "self_report_fidelity_measurable": False,
            "authoritative_effect": self.authoritative_effect,
            "same_model_channel_is_independent_evidence": False,
        }


def capture_pre_execution_change_intent(
    response_text: Any,
    directive: StrictEmissionDirective | None,
    *,
    value: Any = None,
) -> PreExecutionIntentCapture | None:
    """Freeze native intent from the same response, without recovery or retry."""
    if not is_pre_execution_change_intent_enabled(value):
        return None
    family = directive.provider_family if directive else PROVIDER_UNKNOWN
    strategy = directive.strategy if directive else STRATEGY_LEGACY_PROMPT
    if directive is None or not directive.applies:
        return PreExecutionIntentCapture(
            provider_family=family,
            transport_strategy=strategy,
            strict_v2_status=STRICT_V2_NOT_REQUESTED,
            intent_plan_agreement=INTENT_PLAN_UNAVAILABLE,
        )

    parsed = parse_strict_worker_patch_envelope_v2(response_text)
    return PreExecutionIntentCapture(
        provider_family=family,
        transport_strategy=strategy,
        strict_v2_status=parsed.status,
        intent_plan_agreement=intent_plan_agreement(parsed.envelope),
        envelope=parsed.envelope,
        unknown_keys=parsed.unknown_keys,
    )


def safe_capture_pre_execution_change_intent(
    response_text: Any,
    directive: StrictEmissionDirective | None,
    *,
    value: Any = None,
) -> PreExecutionIntentCapture | None:
    """Capture failure is isolated from the authoritative legacy run."""
    try:
        return capture_pre_execution_change_intent(
            response_text, directive, value=value
        )
    except Exception:  # noqa: BLE001 - shadow capture cannot fail the run
        return None


def worker_change_declaration_from_intent_capture(
    capture: PreExecutionIntentCapture,
    *,
    execution_run_id: str,
    worker_id: str | None = None,
) -> WorkerChangeDeclaration | None:
    """Adapt frozen native intent before any objective observation is consulted."""
    if type(capture) is not PreExecutionIntentCapture or capture.intent is None:
        return None
    fingerprint = capture.intent_fingerprint or "unavailable"
    return WorkerChangeDeclaration(
        declaration_id=f"pre-intent-{fingerprint[:32]}",
        execution_run_id=execution_run_id,
        worker_id=worker_id,
        declaration_stage=DECLARATION_STAGE_PRE_EXECUTION_INTENT,
        # Frozen CHECK.1 requires a status.  `partial` is an adapter marker, not
        # a model completion claim; stage/provenance remain attached in live
        # metadata so a mismatch is interpreted as unmaterialized intent.
        declared_status=WORKER_CLAIM_PARTIAL,
        declared_changes=tuple(
            DeclaredChangeClaim(path=item.path, change_kind=item.change_kind)
            for item in capture.intent.intended_changes
        ),
        declared_validation_actions=(),
        limitations=(),
        unresolved_items=(),
        schema_version=WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2,
        source_provenance=DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
    )


@dataclass(frozen=True, slots=True)
class IntentObservedDiagnostic:
    """Bounded live comparison of frozen intent with objective final changes."""

    relation: str
    intended_and_observed: tuple[str, ...] = ()
    intended_not_observed: tuple[str, ...] = ()
    observed_not_intended: tuple[str, ...] = ()
    intended_kind_mismatch: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.relation not in INTENT_OBSERVED_RELATIONS:
            raise ValueError("unsupported intent-observed relation")
        for paths in (
            self.intended_and_observed,
            self.intended_not_observed,
            self.observed_not_intended,
            self.intended_kind_mismatch,
        ):
            if type(paths) is not tuple or len(paths) > MAX_DIAGNOSTIC_PATHS:
                raise ValueError("intent diagnostic paths exceed their finite bound")

    @property
    def interpretation(self) -> str:
        if self.relation == INTENDED_NOT_OBSERVED:
            return "intended_change_not_materialized"
        if self.relation == OBSERVED_NOT_INTENDED:
            return "observed_change_was_not_intended"
        if self.relation == INTENDED_KIND_MISMATCH:
            return "intended_change_materialized_with_different_kind"
        return self.relation

    def as_dict(self) -> dict[str, Any]:
        return {
            "relation": self.relation,
            "interpretation": self.interpretation,
            "intended_and_observed": list(self.intended_and_observed),
            "intended_not_observed": list(self.intended_not_observed),
            "observed_not_intended": list(self.observed_not_intended),
            "intended_kind_mismatch": list(self.intended_kind_mismatch),
        }


def compare_intent_with_observed_changes(
    intent: PreExecutionChangeIntent | None,
    observed_changes: Sequence[Any],
) -> IntentObservedDiagnostic:
    """Compare frozen intent to typed objective changes without rewriting either."""
    if type(intent) is not PreExecutionChangeIntent:
        return IntentObservedDiagnostic(relation=INTENT_OBSERVED_UNAVAILABLE)
    intended = {item.path: item.change_kind for item in intent.intended_changes}
    observed: dict[str, str] = {}
    for item in observed_changes:
        if isinstance(item, Mapping):
            path = item.get("path")
            kind = item.get("change_kind")
        else:
            path = getattr(item, "path", None)
            kind = getattr(item, "change_kind", None)
        if isinstance(path, str) and isinstance(kind, str):
            observed[path] = kind

    shared = set(intended) & set(observed)
    exact = tuple(sorted(path for path in shared if intended[path] == observed[path]))
    mismatch = tuple(
        sorted(path for path in shared if intended[path] != observed[path])
    )
    missing = tuple(sorted(set(intended) - set(observed)))
    extra = tuple(sorted(set(observed) - set(intended)))
    categories = sum(bool(paths) for paths in (missing, extra, mismatch))
    if categories == 0:
        relation = INTENT_OBSERVED_AGREED
    elif categories > 1:
        relation = INTENT_OBSERVED_MIXED
    elif missing:
        relation = INTENDED_NOT_OBSERVED
    elif extra:
        relation = OBSERVED_NOT_INTENDED
    else:
        relation = INTENDED_KIND_MISMATCH
    return IntentObservedDiagnostic(
        relation=relation,
        intended_and_observed=exact,
        intended_not_observed=missing,
        observed_not_intended=extra,
        intended_kind_mismatch=mismatch,
    )


def build_durable_intent_receipt(
    *,
    case_identity: str,
    run_identity: str,
    capture: PreExecutionIntentCapture | None,
    shadow_receipt: Mapping[str, Any] | None,
    authoritative_outcome: str,
) -> dict[str, Any]:
    """Build the bounded export that survives disposable-repository cleanup."""
    case = str(case_identity or "")[:MAX_IDENTITY_CHARS]
    run = str(run_identity or "")[:MAX_IDENTITY_CHARS]
    shadow = shadow_receipt if isinstance(shadow_receipt, Mapping) else {}
    if capture is None:
        provider = None
        strategy = None
        strict_status = None
        native = False
        intent_fingerprint = None
        envelope_fingerprint = None
        plan_relation = INTENT_PLAN_UNAVAILABLE
    else:
        provider = capture.provider_family
        strategy = capture.transport_strategy
        strict_status = capture.strict_v2_status
        native = capture.native_intent_available
        intent_fingerprint = capture.intent_fingerprint
        envelope_fingerprint = capture.envelope_fingerprint
        plan_relation = capture.intent_plan_agreement
    return {
        "schema_version": DURABLE_INTENT_RECEIPT_SCHEMA_VERSION,
        "record_kind": "durable_pre_execution_change_intent_receipt",
        "phase_id": PHASE_ID,
        "case_identity": case,
        "run_identity": run,
        "provider_family": provider,
        "transport_strategy": strategy,
        "strict_v2_status": strict_status,
        "native_intent_available": native,
        "declaration_stage": shadow.get("declaration_stage"),
        "source_provenance": shadow.get("worker_declaration_source", "unavailable"),
        "intent_fingerprint": intent_fingerprint,
        "envelope_fingerprint": envelope_fingerprint,
        "intent_plan_agreement": plan_relation,
        "intent_observed_relation": shadow.get(
            "intent_observed_relation", INTENT_OBSERVED_UNAVAILABLE
        ),
        "check_1_shadow_status": shadow.get("reconciliation_status"),
        "authoritative_outcome": str(authoritative_outcome or "")[:MAX_IDENTITY_CHARS],
        "authoritative_effect": False,
        "contains_raw_response": False,
        "same_model_channel_is_independent_evidence": False,
    }


def persist_durable_intent_receipt(path: str | Path, receipt: Mapping[str, Any]) -> None:
    """Persist one bounded receipt; callers choose an established durable root."""
    Path(path).write_text(
        json.dumps(dict(receipt), indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def load_durable_intent_receipt(path: str | Path) -> dict[str, Any]:
    """Read a receipt without treating absent historical artifacts as errors."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def summarize_durable_intent_receipts(
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Read-only counts over bounded dogfood fields; no score or decision."""
    fields = (
        "source_provenance",
        "strict_v2_status",
        "intent_plan_agreement",
        "intent_observed_relation",
        "check_1_shadow_status",
        "transport_strategy",
        "provider_family",
    )
    counts: dict[str, dict[str, int]] = {field: {} for field in fields}
    for receipt in receipts:
        for field in fields:
            value = receipt.get(field) if isinstance(receipt, Mapping) else None
            if isinstance(value, str) and value:
                bucket = counts[field]
                bucket[value] = bucket.get(value, 0) + 1
    return {
        "schema_version": DURABLE_INTENT_RECEIPT_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "records": len(receipts),
        "counts": {
            field: dict(sorted(bucket.items()))
            for field, bucket in counts.items()
        },
        "counts_decide_nothing": True,
        "authoritative_effect": False,
    }


def pre_execution_change_intent_guardrails() -> dict[str, bool]:
    return {
        "same_model_invocation": True,
        "independently_declared_channel": True,
        "independent_evidence": False,
        "derived_from_patch_plan": False,
        "derived_from_observation": False,
        "prose_parsed": False,
        "model_call_added": False,
        "network_call_added": False,
        "retry_added": False,
        "validation_executed": False,
        "repository_traversed": False,
        "patch_plan_modified": False,
        "path_authority_granted": False,
        "checker_promoted": False,
        "check_2_invoked": False,
        "authoritative_effect": False,
        "temp_repository_retained": False,
    }


__all__ = [
    "PHASE_ID",
    "PRODUCER_KIND",
    "INTENT_OBSERVATION_SCHEMA_VERSION",
    "DURABLE_INTENT_RECEIPT_SCHEMA_VERSION",
    "INTENT_ARTIFACT_NAME",
    "ENVIRONMENT_FLAG",
    "STRICT_V2_NOT_REQUESTED",
    "STRICT_V2_PROMPT_BLOCK",
    "INTENT_PLAN_AGREEMENTS",
    "INTENT_PLAN_AGREED",
    "INTENT_MISSING_PLAN_CHANGE",
    "PLAN_CHANGE_MISSING_INTENT",
    "INTENT_PLAN_KIND_MISMATCH",
    "INTENT_PLAN_MIXED",
    "INTENT_PLAN_UNAVAILABLE",
    "INTENT_OBSERVED_RELATIONS",
    "INTENT_OBSERVED_AGREED",
    "INTENDED_NOT_OBSERVED",
    "OBSERVED_NOT_INTENDED",
    "INTENDED_KIND_MISMATCH",
    "INTENT_OBSERVED_MIXED",
    "INTENT_OBSERVED_UNAVAILABLE",
    "PLAN_OPERATION_CHANGE_KINDS",
    "is_pre_execution_change_intent_enabled",
    "intent_emission_directive",
    "intent_plan_agreement",
    "PreExecutionIntentCapture",
    "capture_pre_execution_change_intent",
    "safe_capture_pre_execution_change_intent",
    "worker_change_declaration_from_intent_capture",
    "IntentObservedDiagnostic",
    "compare_intent_with_observed_changes",
    "build_durable_intent_receipt",
    "persist_durable_intent_receipt",
    "load_durable_intent_receipt",
    "summarize_durable_intent_receipts",
    "pre_execution_change_intent_guardrails",
]
