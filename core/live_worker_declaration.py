"""CHECK.LIVE.1B — independent typed worker change declaration contract.

This module defines the narrow structured value a future worker-protocol
producer may supply at the live post-run boundary.  It does not create that
value from an execution plan, authorization, observation, diff, or prose.  A
declaration is worker self-report evidence only: it grants no authority and
does not establish an observed fact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.post_run_reconciliation import (
    CHANGE_KINDS,
    CHANGE_RENAMED,
    MAX_DECLARED_CHANGES,
    MAX_DECLARED_VALIDATION_ACTIONS,
    MAX_IDENTIFIER_CHARS,
    MAX_LIMITATIONS,
    MAX_TEXT_CHARS,
    MAX_UNRESOLVED_ITEMS,
    WORKER_CLAIM_PARTIAL,
    WORKER_STATUS_CLAIMS,
    DeclaredValidationAction,
)
from core.repository_path_policy import is_safe_repository_relative_path


PHASE_ID = "CHECK.LIVE.1B"
PRODUCER_KIND = "live_worker_declaration"

WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V1 = (
    "check_live_1b_worker_change_declaration_v1"
)
WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2 = (
    "worker_decl_2b_worker_change_declaration_v2"
)
WORKER_CHANGE_DECLARATION_SCHEMA_VERSION = WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V1
DECLARATION_STAGE_COMPLETED = "completed"
DECLARATION_STAGE_PRE_EXECUTION_INTENT = "pre_execution_intent"

#: Sentinel for a change kind the worker did not independently know.  It is
#: never guessed from another live input.
CHANGE_KIND_UNAVAILABLE_CLAIM = "change_kind_unavailable"

DECLARATION_SOURCE_INDEPENDENT = "independent_worker_declaration"
DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT = "pre_execution_worker_intent"
DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION = (
    "post_execution_worker_declaration"
)
DECLARATION_SOURCE_LEGACY_PLAN_DERIVED = "legacy_plan_derived"
DECLARATION_SOURCE_UNAVAILABLE = "unavailable"

DECLARATION_CHANNEL_INDEPENDENTLY_DECLARED = "independently_declared_channel"
DECLARATION_CHANNEL_UNAVAILABLE = "unavailable"

ALLOWED_DECLARATION_KEYS: tuple[str, ...] = (
    "declaration_id",
    "execution_run_id",
    "worker_id",
    "declaration_stage",
    "declared_status",
    "declared_changes",
    "declared_validation_actions",
    "limitations",
    "unresolved_items",
    "schema_version",
)
ALLOWED_DECLARATION_V2_KEYS: tuple[str, ...] = (
    *ALLOWED_DECLARATION_KEYS,
    "source_provenance",
)
ALLOWED_CHANGE_CLAIM_KEYS: tuple[str, ...] = (
    "path",
    "change_kind",
    "from_path",
)
ALLOWED_VALIDATION_ACTION_KEYS: tuple[str, ...] = (
    "validation_kind",
    "declared_result",
    "validation_id",
)

#: A structured worker declaration is evidence, never a place to smuggle an
#: authorization or approval decision into the live path.
FORBIDDEN_DECLARATION_KEYS: tuple[str, ...] = (
    "write_authority",
    "apply_authority",
    "patch_authority",
    "validation_authority",
    "observed_fact_authority",
    "repository_authority",
    "merge_authority",
    "human_approval",
    "human_approval_required",
    "guardrails",
)


class LiveWorkerDeclarationInputError(ValueError):
    """Raised when structured declaration input violates this contract."""


def _bounded_text(value: object, label: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} contains a control character")


def _bounded_identifier(
    value: object, label: str, *, optional: bool = False
) -> None:
    if value is None and optional:
        return
    _bounded_text(value, label, MAX_IDENTIFIER_CHARS)


def _bounded_path(value: object, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string path")
    if value[:1] in {"/", "\\"} or not is_safe_repository_relative_path(value):
        raise ValueError(f"{label} is not a canonical repository-relative path")


def _bounded_tuple(values: object, maximum: int, label: str) -> None:
    if type(values) is not tuple:
        raise TypeError(f"{label} must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")


@dataclass(frozen=True, slots=True)
class DeclaredChangeClaim:
    """One change kind and path the worker independently claims."""

    path: str
    change_kind: str
    from_path: str | None = None

    def __post_init__(self) -> None:
        _bounded_path(self.path, "declared change claim path")
        if self.change_kind not in (*CHANGE_KINDS, CHANGE_KIND_UNAVAILABLE_CLAIM):
            raise ValueError(
                f"unsupported declared change claim kind: {self.change_kind!r}"
            )
        _bounded_path(
            self.from_path, "declared change claim from path", optional=True
        )
        if self.change_kind == CHANGE_RENAMED and self.from_path is None:
            raise ValueError("a declared rename claim must name its original path")
        if self.change_kind != CHANGE_RENAMED and self.from_path is not None:
            raise ValueError(
                "only a declared rename claim may name an original path"
            )
        if self.from_path is not None and self.from_path == self.path:
            raise ValueError(
                "a declared rename claim must move between distinct paths"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "change_kind": self.change_kind,
            "from_path": self.from_path,
        }


@dataclass(frozen=True, slots=True)
class WorkerChangeDeclaration:
    """A bounded staged worker declaration, carrying no authority.

    A v2 pre-execution value is an independently declared structured channel
    from the same model invocation as the plan.  It is not completion reporting
    and is not independent evidence.
    """

    declaration_id: str
    execution_run_id: str
    worker_id: str | None
    declaration_stage: str
    declared_status: str
    declared_changes: tuple[DeclaredChangeClaim, ...] = ()
    declared_validation_actions: tuple[DeclaredValidationAction, ...] = ()
    limitations: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()
    schema_version: str = WORKER_CHANGE_DECLARATION_SCHEMA_VERSION
    source_provenance: str = DECLARATION_SOURCE_INDEPENDENT

    def __post_init__(self) -> None:
        _bounded_identifier(self.declaration_id, "worker declaration id")
        _bounded_identifier(
            self.execution_run_id, "worker declaration execution run id"
        )
        _bounded_identifier(
            self.worker_id, "worker declaration worker id", optional=True
        )
        if self.schema_version not in {
            WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V1,
            WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2,
        }:
            raise ValueError("unsupported worker change declaration schema version")
        if self.schema_version == WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V1:
            if self.declaration_stage != DECLARATION_STAGE_COMPLETED:
                raise ValueError("v1 worker declaration stage must be completed")
            if self.source_provenance != DECLARATION_SOURCE_INDEPENDENT:
                raise ValueError(
                    "v1 worker declaration provenance must remain its legacy value"
                )
        elif self.declaration_stage == DECLARATION_STAGE_PRE_EXECUTION_INTENT:
            if (
                self.source_provenance
                != DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT
            ):
                raise ValueError(
                    "pre-execution intent requires pre_execution_worker_intent provenance"
                )
            if self.declared_status != WORKER_CLAIM_PARTIAL:
                raise ValueError(
                    "pre-execution intent uses the non-completion partial status adapter"
                )
            if self.declared_validation_actions:
                raise ValueError(
                    "pre-execution intent cannot declare completed validation actions"
                )
        elif self.declaration_stage == DECLARATION_STAGE_COMPLETED:
            if self.source_provenance not in {
                DECLARATION_SOURCE_INDEPENDENT,
                DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            }:
                raise ValueError(
                    "completed declaration requires post-execution provenance"
                )
        else:
            raise ValueError("unsupported worker declaration stage")
        if self.declared_status not in WORKER_STATUS_CLAIMS:
            raise ValueError(
                f"unsupported declared worker status: {self.declared_status!r}"
            )

        _bounded_tuple(
            self.declared_changes, MAX_DECLARED_CHANGES, "declared change claims"
        )
        _bounded_tuple(
            self.declared_validation_actions,
            MAX_DECLARED_VALIDATION_ACTIONS,
            "declared validation actions",
        )
        _bounded_tuple(self.limitations, MAX_LIMITATIONS, "declaration limitations")
        _bounded_tuple(
            self.unresolved_items,
            MAX_UNRESOLVED_ITEMS,
            "declaration unresolved items",
        )
        if not all(type(item) is DeclaredChangeClaim for item in self.declared_changes):
            raise TypeError(
                "declared_changes must contain DeclaredChangeClaim records"
            )
        if not all(
            type(item) is DeclaredValidationAction
            for item in self.declared_validation_actions
        ):
            raise TypeError(
                "declared_validation_actions must contain "
                "DeclaredValidationAction records"
            )
        paths = tuple(item.path for item in self.declared_changes)
        if len(set(paths)) != len(paths):
            raise ValueError("declared change claim paths must be unique")
        action_keys = tuple(item.key for item in self.declared_validation_actions)
        if len(set(action_keys)) != len(action_keys):
            raise ValueError("declared validation actions must be unique")
        for text in (*self.limitations, *self.unresolved_items):
            _bounded_text(text, "worker declaration note", MAX_TEXT_CHARS)

    @property
    def channel_provenance(self) -> str:
        if self.source_provenance in {
            DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        }:
            return DECLARATION_CHANNEL_INDEPENDENTLY_DECLARED
        return DECLARATION_CHANNEL_UNAVAILABLE

    @property
    def intent_fidelity_measurable(self) -> bool:
        return self.source_provenance in {
            DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        }

    @property
    def self_report_fidelity_measurable(self) -> bool:
        return self.source_provenance in {
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        }

    def as_dict(self) -> dict[str, Any]:
        record = {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "declaration_id": self.declaration_id,
            "execution_run_id": self.execution_run_id,
            "worker_id": self.worker_id,
            "declaration_stage": self.declaration_stage,
            "declared_status": self.declared_status,
            "declared_changes": [
                item.as_dict()
                for item in sorted(self.declared_changes, key=lambda item: item.path)
            ],
            "declared_validation_actions": [
                item.as_dict()
                for item in sorted(
                    self.declared_validation_actions, key=lambda item: item.key
                )
            ],
            "limitations": list(self.limitations),
            "unresolved_items": list(self.unresolved_items),
        }
        if self.schema_version == WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2:
            record.update(
                {
                    "source_provenance": self.source_provenance,
                    "channel_provenance": self.channel_provenance,
                    "intent_fidelity_measurable": self.intent_fidelity_measurable,
                    "self_report_fidelity_measurable": (
                        self.self_report_fidelity_measurable
                    ),
                }
            )
        return record


def worker_change_declaration_fingerprint(
    declaration: WorkerChangeDeclaration,
) -> str:
    """Fingerprint one exact declaration over canonical JSON."""
    if type(declaration) is not WorkerChangeDeclaration:
        raise TypeError(
            "worker_change_declaration_fingerprint requires an exact "
            "WorkerChangeDeclaration"
        )
    rendered = json.dumps(
        declaration.as_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _mapping(
    value: Any, label: str, allowed_keys: Sequence[str]
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LiveWorkerDeclarationInputError(f"{label} must be a mapping")
    unknown = sorted(set(value) - set(allowed_keys))
    if unknown:
        raise LiveWorkerDeclarationInputError(
            f"{label} contains unknown keys: {', '.join(unknown)}"
        )
    return value


def _sequence(value: Any, label: str, maximum: int) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise LiveWorkerDeclarationInputError(f"{label} must be a sequence")
    if len(value) > maximum:
        raise LiveWorkerDeclarationInputError(
            f"{label} exceeds the bound of {maximum}"
        )
    return value


def _text_sequence(value: Any, label: str, maximum: int) -> tuple[str, ...]:
    items = _sequence(value, label, maximum)
    values: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise LiveWorkerDeclarationInputError(
                f"{label} entries must be strings"
            )
        values.append(item)
    return tuple(values)


def _change_claim_from_mapping(raw: Any) -> DeclaredChangeClaim:
    payload = _mapping(raw, "declared change claim", ALLOWED_CHANGE_CLAIM_KEYS)
    missing = sorted({"path", "change_kind"} - set(payload))
    if missing:
        raise LiveWorkerDeclarationInputError(
            "declared change claim is missing required keys: "
            + ", ".join(missing)
        )
    return DeclaredChangeClaim(
        path=payload["path"],
        change_kind=payload["change_kind"],
        from_path=payload.get("from_path"),
    )


def _validation_action_from_mapping(raw: Any) -> DeclaredValidationAction:
    payload = _mapping(
        raw, "declared validation action", ALLOWED_VALIDATION_ACTION_KEYS
    )
    missing = sorted({"validation_kind", "declared_result"} - set(payload))
    if missing:
        raise LiveWorkerDeclarationInputError(
            "declared validation action is missing required keys: "
            + ", ".join(missing)
        )
    return DeclaredValidationAction(
        validation_kind=payload["validation_kind"],
        declared_result=payload["declared_result"],
        validation_id=payload.get("validation_id"),
    )


def worker_change_declaration_from_mapping(
    raw: Mapping[str, Any],
) -> WorkerChangeDeclaration:
    """Validate an already-structured mapping without parsing or repairing prose."""
    try:
        if not isinstance(raw, Mapping):
            raise LiveWorkerDeclarationInputError(
                "worker change declaration must be a mapping"
            )
        claimed = sorted(set(raw) & set(FORBIDDEN_DECLARATION_KEYS))
        if claimed:
            raise LiveWorkerDeclarationInputError(
                "worker change declaration claimed authority it does not have: "
                + ", ".join(claimed)
            )
        requested_schema = raw.get(
            "schema_version", WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V1
        )
        allowed_keys = (
            ALLOWED_DECLARATION_V2_KEYS
            if requested_schema == WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2
            else ALLOWED_DECLARATION_KEYS
        )
        payload = _mapping(raw, "worker change declaration", allowed_keys)
        required = {
            "declaration_id",
            "execution_run_id",
            "worker_id",
            "declaration_stage",
            "declared_status",
        }
        missing = sorted(required - set(payload))
        if requested_schema == WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2:
            missing = sorted(set(missing) | ({"source_provenance"} - set(payload)))
        if missing:
            raise LiveWorkerDeclarationInputError(
                "worker change declaration is missing required keys: "
                + ", ".join(missing)
            )

        changes = tuple(
            _change_claim_from_mapping(item)
            for item in _sequence(
                payload.get("declared_changes", ()),
                "declared_changes",
                MAX_DECLARED_CHANGES,
            )
        )
        actions = tuple(
            _validation_action_from_mapping(item)
            for item in _sequence(
                payload.get("declared_validation_actions", ()),
                "declared_validation_actions",
                MAX_DECLARED_VALIDATION_ACTIONS,
            )
        )
        return WorkerChangeDeclaration(
            declaration_id=payload["declaration_id"],
            execution_run_id=payload["execution_run_id"],
            worker_id=payload["worker_id"],
            declaration_stage=payload["declaration_stage"],
            declared_status=payload["declared_status"],
            declared_changes=changes,
            declared_validation_actions=actions,
            limitations=_text_sequence(
                payload.get("limitations", ()), "limitations", MAX_LIMITATIONS
            ),
            unresolved_items=_text_sequence(
                payload.get("unresolved_items", ()),
                "unresolved_items",
                MAX_UNRESOLVED_ITEMS,
            ),
            schema_version=payload.get(
                "schema_version", WORKER_CHANGE_DECLARATION_SCHEMA_VERSION
            ),
            source_provenance=payload.get(
                "source_provenance", DECLARATION_SOURCE_INDEPENDENT
            ),
        )
    except LiveWorkerDeclarationInputError:
        raise
    except (TypeError, ValueError) as error:
        raise LiveWorkerDeclarationInputError(
            f"worker change declaration violated a contract rule: {error}"
        ) from error


def worker_declaration_authority() -> dict[str, bool]:
    """The sole authority of this record is worker self-report evidence."""
    return {
        "write_authority": False,
        "patch_authority": False,
        "validation_authority": False,
        "observed_fact_authority": False,
        "worker_self_report_authority": True,
    }


def worker_declaration_guardrails() -> dict[str, bool]:
    """Every power this contract and strict mapping adapter decline."""
    return {
        "derived_from_patch_plan": False,
        "derived_from_execution_authorization": False,
        "derived_from_observed_facts": False,
        "prose_parsed": False,
        "model_called": False,
        "repository_traversed": False,
        "source_content_read": False,
        "validation_executed": False,
        "patch_applied": False,
        "files_modified": False,
        "network_call_performed": False,
        "authoritative_effect": False,
        "human_approval_required": True,
    }


__all__ = [
    "PHASE_ID",
    "PRODUCER_KIND",
    "WORKER_CHANGE_DECLARATION_SCHEMA_VERSION",
    "WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V1",
    "WORKER_CHANGE_DECLARATION_SCHEMA_VERSION_V2",
    "DECLARATION_STAGE_COMPLETED",
    "DECLARATION_STAGE_PRE_EXECUTION_INTENT",
    "CHANGE_KIND_UNAVAILABLE_CLAIM",
    "DECLARATION_SOURCE_INDEPENDENT",
    "DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT",
    "DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION",
    "DECLARATION_SOURCE_LEGACY_PLAN_DERIVED",
    "DECLARATION_SOURCE_UNAVAILABLE",
    "DECLARATION_CHANNEL_INDEPENDENTLY_DECLARED",
    "DECLARATION_CHANNEL_UNAVAILABLE",
    "ALLOWED_DECLARATION_KEYS",
    "ALLOWED_DECLARATION_V2_KEYS",
    "ALLOWED_CHANGE_CLAIM_KEYS",
    "ALLOWED_VALIDATION_ACTION_KEYS",
    "FORBIDDEN_DECLARATION_KEYS",
    "LiveWorkerDeclarationInputError",
    "DeclaredChangeClaim",
    "WorkerChangeDeclaration",
    "worker_change_declaration_fingerprint",
    "worker_change_declaration_from_mapping",
    "worker_declaration_authority",
    "worker_declaration_guardrails",
]
