"""CTX.APPLY.0 direct-context patch-safety attachment.

This module is deliberately an in-memory, fail-closed boundary between the
typed CTX.PATCH.1 proposal and the existing path safety gate.  It does not
generate a patch, write a file, run validation, issue approval, or wire a new
apply path.  The result is evidence for a future, explicit human decision.

Only a typed ``DirectPatchCandidateGateResult``, original immutable direct-read
receipts, a supplied immutable inventory, supplied file capabilities, and
supplied targeted current identities are accepted.  That narrow input surface
prevents a serialized or filename-only record from becoming an implicit write
request.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import islice
from typing import Any

from core.direct_context_runtime import compute_repository_inventory_identity
from core.direct_patch_candidate_gate import (
    ChangeIntention,
    DirectPatchCandidateGateResult,
    PatchCandidateEvaluation,
    TargetRange,
    ValidationCandidate,
)
from core.direct_read_receipt import (
    DirectReadFileIdentity,
    DirectReadRangeReceipt,
    DirectReadReceipt,
    verify_direct_read_receipt,
)
from core.file_capabilities import FileCapability
from core.patch_safety import evaluate_patch_safety
from core.proposed_patch_set import (
    MAX_PROPOSED_SOURCE_FILES,
    MAX_PROPOSED_TOTAL_FILES,
    MAX_PROPOSED_VALIDATION_FILES,
    ProposedPatchSet,
)
from core.repository_identity import derive_repository_id_from_canonical_root
from core.repository_inventory import RepositoryInventory
from core.repository_path_policy import is_safe_repository_relative_path


PHASE_ID = "CTX.APPLY.0"
ATTACHMENT_KIND = "direct_context_patch_safety"
CTX_PATCH_PHASE_ID = "CTX.PATCH.1"

ATTACHMENT_STATUSES = (
    "attached",
    "attached_with_review",
    "partially_attached",
    "reread_required",
    "human_file_selection_required",
    "policy_blocked",
    "security_blocked",
    "invalid_evidence",
)

MAX_RECEIPTS = 8
MAX_RANGES_PER_TARGET = 8
MAX_REVIEW_POINTS = 32
MAX_TEXT = 360

_ATTACHABLE_STATES = frozenset(
    {
        "eligible",
        "eligible_with_review",
        # CTX.PATCH.1 intentionally exposes these as proposable review states.
        # CTX.APPLY.0 preserves the source state and only attaches them with an
        # explicit review requirement; it never silently upgrades them.
        "validation_gap",
        "high_blast_radius_review",
    }
)
_REVIEW_STATES = frozenset(
    {"eligible_with_review", "validation_gap", "high_blast_radius_review"}
)
_ATTACHABLE_PLAN_STATUSES = frozenset({"ready", "ready_with_review"})
_BLOCKED_STATES = frozenset(
    {
        "insufficient_evidence",
        "reread_required",
        "read_only_context",
        "generated_source_redirect",
        "sensitive_blocked",
        "outside_scope",
        "forbidden",
    }
)
_AUTHORITY_FIELDS = frozenset(
    {
        "write_authority",
        "patch_authority",
        "patch_generation_authority",
        "patch_application_authority",
        "patch_apply_authority",
        "apply_authority",
        "execution_authority",
    }
)
_FORBIDDEN_INTENTION_TERMS = frozenset(
    {"diff", "patch", "command", "apply", "write", "filesystem"}
)
_SENSITIVE_INTENTION_PATTERNS = (
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?key|secret(?:[_-]?(?:key|token|value))?"
        r"|password|passwd|credential(?:s)?|authorization|auth[_-]?token"
        r"|private[_-]?key|client[_-]?secret|token)\b\s*(?:=|:)\s*"
        r"(?:['\"][^'\"]{1,}|[^\s]{8,})"
    ),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:xox[baprs]-|gh[pousr]_|github_pat_|sk-)[A-Za-z0-9_-]{12,}"),
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
)
_SAFE_REVIEW_CODE = re.compile(r"[a-z0-9_:-]{1,120}\Z")
_REPOSITORY_CONTEXT_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "operation_id",
        "repository_root",
        "repository_id",
        "inventory_identity",
        "inventory",
        "current_file_identities",
        "file_capabilities",
        "attachment_created_at",
        "human_approval_required",
    }
)


class _RecordMapping(Mapping[str, Any]):
    """Immutable-record mapping facade used by other CTX result objects."""

    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - abstract helper
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


@dataclass(frozen=True, slots=True)
class AttachmentTarget(_RecordMapping):
    """A reviewable implementation target, never a writable target."""

    path: str
    candidate_state: str
    patchability_score: int
    blast_radius: str
    receipt_freshness: str
    target_ranges: tuple[TargetRange, ...]
    receipt_fingerprint: str
    file_identity_fingerprint: str
    change_summary: str
    expected_behavior_change: str
    must_preserve: tuple[str, ...]
    change_intention_fingerprint: str
    review_required: bool

    def __post_init__(self) -> None:
        if not is_safe_repository_relative_path(self.path):
            raise ValueError("attachment target path must be canonical and repository-relative")
        if self.candidate_state not in _ATTACHABLE_STATES:
            raise ValueError("attachment target has a non-attachable candidate state")
        if type(self.patchability_score) is not int or not 0 <= self.patchability_score <= 100:
            raise ValueError("patchability score must be bounded")
        if self.blast_radius not in {"low", "medium", "high", "critical", "unknown"}:
            raise ValueError("attachment target has an unknown blast radius")
        if self.receipt_freshness != "fresh":
            raise ValueError("only fresh receipt evidence may attach")
        if not isinstance(self.target_ranges, tuple) or not self.target_ranges:
            raise ValueError("attached targets require bounded target ranges")
        if len(self.target_ranges) > MAX_RANGES_PER_TARGET:
            raise ValueError("attachment target has too many ranges")
        if not all(isinstance(item, TargetRange) for item in self.target_ranges):
            raise ValueError("attachment target ranges must be typed")
        if self.target_ranges != tuple(sorted(set(self.target_ranges))):
            raise ValueError("target ranges must be deterministic")
        if not _is_sha256_fingerprint(self.receipt_fingerprint):
            raise ValueError("receipt fingerprint is required")
        if not _is_sha256_fingerprint(self.file_identity_fingerprint):
            raise ValueError("file identity fingerprint is required")
        if not _is_sha256_fingerprint(self.change_intention_fingerprint):
            raise ValueError("change intention fingerprint is required")
        if type(self.review_required) is not bool:
            raise ValueError("attachment review requirement must be boolean")
        try:
            summary = _safe_text(self.change_summary, label="change_summary")
            expected = _safe_text(
                self.expected_behavior_change,
                label="expected_behavior_change",
            )
            preserve = tuple(
                sorted(
                    {
                        _safe_text(item, label="must_preserve", maximum=180)
                        for item in self.must_preserve
                    }
                )
            )
        except _InvalidEvidence as exc:
            raise ValueError(str(exc)) from None
        if len(preserve) > 16:
            raise ValueError("attachment preservation scope is too large")
        object.__setattr__(self, "change_summary", summary)
        object.__setattr__(self, "expected_behavior_change", expected)
        object.__setattr__(self, "must_preserve", preserve)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "candidate_state": self.candidate_state,
            "patchability_score": self.patchability_score,
            "blast_radius": self.blast_radius,
            "receipt_freshness": self.receipt_freshness,
            "target_ranges": [item.as_dict() for item in self.target_ranges],
            "receipt_fingerprint": self.receipt_fingerprint,
            "file_identity_fingerprint": self.file_identity_fingerprint,
            "change_summary": self.change_summary,
            "expected_behavior_change": self.expected_behavior_change,
            "must_preserve": list(self.must_preserve),
            "change_intention_fingerprint": self.change_intention_fingerprint,
            "review_required": self.review_required,
            "eligible_for_patch_safety_review": True,
            "write_authority": False,
            "patch_generation_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
        }


@dataclass(frozen=True, slots=True)
class ValidationEvidence(_RecordMapping):
    """Fresh validation-file evidence that is explicitly non-writable."""

    path: str
    receipt_freshness: str
    receipt_fingerprint: str
    file_identity_fingerprint: str
    validation_status: str
    validation_plan_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        if not is_safe_repository_relative_path(self.path):
            raise ValueError("validation evidence path must be canonical")
        if self.receipt_freshness != "fresh":
            raise ValueError("validation evidence must have a fresh receipt")
        if self.validation_status not in {"mapped", "gap"}:
            raise ValueError("validation evidence has an unknown status")

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "receipt_freshness": self.receipt_freshness,
            "receipt_fingerprint": self.receipt_fingerprint,
            "file_identity_fingerprint": self.file_identity_fingerprint,
            "validation_status": self.validation_status,
            "validation_plan_kinds": list(self.validation_plan_kinds),
            "validation_only": True,
            "approved_test_modification_target": None,
            "write_authority": False,
            "patch_generation_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
        }


@dataclass(frozen=True, slots=True)
class ValidationPlanItem(_RecordMapping):
    """A bounded, non-executable validation mapping for one source target."""

    source_path: str
    validation_status: str
    kind: str | None
    target_path: str | None
    target_fingerprint: str | None
    confidence: str | None
    test_modification_requires_separate_policy: bool

    def __post_init__(self) -> None:
        if not is_safe_repository_relative_path(self.source_path):
            raise ValueError("validation plan source path must be canonical")
        if type(self.test_modification_requires_separate_policy) is not bool:
            raise ValueError("validation plan test-modification policy must be boolean")
        if self.validation_status not in {"mapped", "gap"}:
            raise ValueError("validation plan status is invalid")
        if self.validation_status == "gap":
            if any(
                value is not None
                for value in (
                    self.kind,
                    self.target_path,
                    self.target_fingerprint,
                    self.confidence,
                )
            ):
                raise ValueError("validation gap cannot include a validation target")
            return
        if self.kind is None or self.confidence not in {"high", "medium", "low", "unknown"}:
            raise ValueError("mapped validation requires kind and confidence")
        if self.target_path is not None and not is_safe_repository_relative_path(self.target_path):
            raise ValueError("validation plan target path must be canonical")
        if not _is_sha256_fingerprint(self.target_fingerprint):
            raise ValueError("validation plan target fingerprint is required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "validation_status": self.validation_status,
            "kind": self.kind,
            "target_path": self.target_path,
            "target_fingerprint": self.target_fingerprint,
            "confidence": self.confidence,
            "test_modification_requires_separate_policy": (
                self.test_modification_requires_separate_policy
            ),
            "validation_only": True,
            "approved_test_modification_target": None,
            "executed": False,
            "write_authority": False,
            "patch_generation_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
        }


@dataclass(frozen=True, slots=True)
class BlockedAttachmentCandidate(_RecordMapping):
    """One explicit no-attachment outcome; candidates are never dropped."""

    path: str
    candidate_group: str
    candidate_state: str
    decision: str
    reason_code: str
    receipt_freshness: str

    def __post_init__(self) -> None:
        if self.candidate_group not in {"implementation", "validation"}:
            raise ValueError("unknown blocked-candidate group")
        if self.decision not in {
            "candidate_removed",
            "reread_required",
            "security_blocked",
            "attachment_blocked",
            "policy_blocked",
            "invalid_evidence",
            "additional_context_required",
        }:
            raise ValueError("unknown blocked-candidate decision")

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "candidate_group": self.candidate_group,
            "candidate_state": self.candidate_state,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "receipt_freshness": self.receipt_freshness,
            "content_redacted": True,
            "write_authority": False,
            "patch_generation_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
        }


@dataclass(frozen=True, slots=True)
class PatchSafetyAttachment(_RecordMapping):
    """Bounded handoff artifact for the existing safety and review workflow."""

    status: str
    task_id: str
    operation_id: str
    repository_root: str
    repository_id: str
    inventory_identity: str
    proposed_patch_set_identity: str
    attachment_created_at: str
    attachment_fingerprint: str
    implementation_targets: tuple[AttachmentTarget, ...]
    validation_evidence: tuple[ValidationEvidence, ...]
    validation_plan: tuple[ValidationPlanItem, ...]
    blocked_candidates: tuple[BlockedAttachmentCandidate, ...]
    human_review_points: tuple[str, ...]
    errors: tuple[str, ...] = ()
    targeted_identity_checks: int = 0

    def __post_init__(self) -> None:
        if self.status not in ATTACHMENT_STATUSES:
            raise ValueError("unknown attachment status")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.task_id,
                self.operation_id,
                self.repository_root,
                self.repository_id,
                self.inventory_identity,
                self.proposed_patch_set_identity,
                self.attachment_created_at,
                self.attachment_fingerprint,
            )
        ):
            raise ValueError("attachment identity fields must be nonblank")
        paths = [item.path for item in self.implementation_targets]
        paths.extend(item.path for item in self.validation_evidence)
        paths.extend(item.path for item in self.blocked_candidates if item.path)
        if len(paths) != len({path.casefold() for path in paths}):
            raise ValueError("attachment candidates must retain unique canonical paths")
        if len(self.implementation_targets) > MAX_PROPOSED_SOURCE_FILES:
            raise ValueError("attachment source-target limit exceeded")
        if len(self.validation_evidence) > MAX_PROPOSED_VALIDATION_FILES:
            raise ValueError("attachment validation-evidence limit exceeded")
        if len(self.implementation_targets) + len(self.validation_evidence) > MAX_PROPOSED_TOTAL_FILES:
            raise ValueError("attachment total-reference limit exceeded")
        if len(self.validation_plan) > MAX_PROPOSED_VALIDATION_FILES:
            raise ValueError("attachment validation-plan limit exceeded")
        if tuple(sorted(set(self.human_review_points))) != self.human_review_points:
            raise ValueError("review points must be deterministic")
        if tuple(sorted(set(self.errors))) != self.errors:
            raise ValueError("attachment errors must be deterministic")
        if self.targeted_identity_checks < 0:
            raise ValueError("targeted identity checks cannot be negative")

    @property
    def eligible_for_patch_safety_review(self) -> bool:
        return bool(self.implementation_targets)

    def as_dict(self) -> dict[str, Any]:
        targets = [item.as_dict() for item in self.implementation_targets]
        exact_files = [item.path for item in self.implementation_targets]
        return {
            "phase_id": PHASE_ID,
            "attachment_kind": ATTACHMENT_KIND,
            "status": self.status,
            "attachment_status": self.status,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "repository_root": self.repository_root,
            "repository_id": self.repository_id,
            "inventory_identity": self.inventory_identity,
            "proposed_patch_set_identity": self.proposed_patch_set_identity,
            "attachment_created_at": self.attachment_created_at,
            "attachment_fingerprint": self.attachment_fingerprint,
            "implementation_targets": targets,
            "allowed_proposed_targets": exact_files,
            "validation_evidence": [item.as_dict() for item in self.validation_evidence],
            "validation_plan": [item.as_dict() for item in self.validation_plan],
            "blocked_candidates": [item.as_dict() for item in self.blocked_candidates],
            "human_review_points": list(self.human_review_points),
            "human_review_request": {
                "approval_action": "approve_patch_apply",
                "target_type": "patch",
                "target_id": self.attachment_fingerprint,
                "task_id": self.task_id,
                "repository_id": self.repository_id,
                "exact_target_files": exact_files,
                "target_change_intentions": [
                    {
                        "path": item["path"],
                        "target_ranges": item["target_ranges"],
                        "change_summary": item["change_summary"],
                        "expected_behavior_change": item[
                            "expected_behavior_change"
                        ],
                        "change_intention_fingerprint": item[
                            "change_intention_fingerprint"
                        ],
                    }
                    for item in targets
                ],
                "risk_level": _review_risk_level(
                    self.implementation_targets
                ),
                "receipt_freshness": [
                    {"path": item["path"], "status": item["receipt_freshness"]}
                    for item in targets
                ],
                "validation_plan": [item.as_dict() for item in self.validation_plan],
                "fresh_validation_evidence": [
                    {
                        "path": item.path,
                        "status": item.validation_status,
                        "kinds": list(item.validation_plan_kinds),
                    }
                    for item in self.validation_evidence
                ],
                "approval_options": [
                    "approve_exact_candidate_set",
                    "approve_with_file_removals",
                    "reject",
                    "request_reread",
                    "request_more_context",
                ],
                "generic_repository_wide_approval_sufficient": False,
                "approval_record_created": False,
                "human_approval_required": True,
            },
            "future_pre_generation_revalidation": {
                "required": True,
                "required_checks": [
                    "current_file_identity_equals_attached_file_identity",
                    "receipt_identity_remains_fresh",
                    "exact_target_set_matches_attachment",
                    "existing_patch_safety_rechecked",
                    "explicit_human_approval_rechecked",
                ],
                "changed_file_invalidates_attachment": True,
                "attachment_is_write_permission": False,
            },
            "eligible_for_patch_safety_review": self.eligible_for_patch_safety_review,
            "write_authority": False,
            "patch_generation_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
            "patch_safety_required": True,
            "patch_safety_bypassed": False,
            "approval_enforcement_installed": False,
            "errors": list(self.errors),
            "targeted_identity_checks": self.targeted_identity_checks,
            "repository_traversals": 0,
            "production_content_reads": 0,
            "filesystem_writes": 0,
            "patches_generated": 0,
            "patches_applied": 0,
            "validation_commands_executed": 0,
            "indexing_operations": 0,
            "database_operations": 0,
            "graph_operations": 0,
            "model_calls": 0,
            "api_calls": 0,
            "raw_file_content_included": False,
            "security_redacted": True,
        }


@dataclass(frozen=True, slots=True)
class _RepositoryContext:
    task_id: str
    operation_id: str
    repository_root: str
    repository_id: str
    inventory_identity: str
    inventory: RepositoryInventory
    current_file_identities: Mapping[str, Any]
    capabilities: tuple[FileCapability, ...]
    attachment_created_at: str


class _InvalidEvidence(ValueError):
    """Deliberately short, serialization-safe structural failure."""


def _record(value: Any, *, label: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        rendered = as_dict()
        if isinstance(rendered, Mapping):
            return rendered
    raise _InvalidEvidence(f"{label}_must_be_a_record")


def _sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _is_sha256_fingerprint(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        return False
    return all(character in "0123456789abcdef" for character in value[7:])


def _safe_text(value: Any, *, label: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise _InvalidEvidence(f"{label}_must_be_text")
    text = " ".join(value.split())
    if not text or len(text) > maximum or not text.isprintable():
        raise _InvalidEvidence(f"{label}_is_unbounded")
    lowered = text.casefold()
    if any(term in lowered for term in _FORBIDDEN_INTENTION_TERMS):
        raise _InvalidEvidence(f"{label}_contains_execution_language")
    if any(pattern.search(text) for pattern in _SENSITIVE_INTENTION_PATTERNS):
        raise _InvalidEvidence(f"{label}_may_contain_sensitive_content")
    return text


def _strict_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise _InvalidEvidence(f"{label}_is_not_canonical")
    if not is_safe_repository_relative_path(value):
        raise _InvalidEvidence(f"{label}_is_not_repository_relative")
    return value


def _timestamp(value: Any) -> str:
    if value is None or value == "":
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not isinstance(value, str) or len(value) > 80 or not value.strip():
        raise _InvalidEvidence("attachment_created_at_is_invalid")
    return value


def _nonblank_context_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 512:
        raise _InvalidEvidence(f"{label}_is_invalid")
    return value


def _authority_is_safe(value: Any) -> bool:
    record = _record(value, label="authority_record")
    if record.get("human_approval_required", True) is not True:
        return False
    return all(record.get(field, False) is False for field in _AUTHORITY_FIELDS)


def _coerce_capabilities(value: Any, inventory_paths: set[str]) -> tuple[FileCapability, ...]:
    if isinstance(value, Mapping):
        raw = tuple(value.items())
    elif isinstance(value, (str, bytes)) or value is None:
        raise _InvalidEvidence("file_capabilities_are_required")
    else:
        raw = tuple(islice(iter(value), MAX_PROPOSED_TOTAL_FILES + 1))
    if len(raw) > MAX_PROPOSED_TOTAL_FILES:
        raise _InvalidEvidence("file_capabilities_exceed_limit")
    result: list[FileCapability] = []
    seen: set[str] = set()
    for raw_item in raw:
        supplied_key: str | None = None
        item = raw_item
        if isinstance(value, Mapping):
            supplied_key, item = raw_item
        if not isinstance(item, FileCapability):
            raise _InvalidEvidence("file_capabilities_must_be_typed")
        if not all(
            type(flag) is bool
            for flag in (
                item.direct_read_allowed,
                item.repository_contained,
                item.symlink_escape,
                item.generated,
                item.vendor,
            )
        ):
            raise _InvalidEvidence("file_capability_boolean_fields_are_invalid")
        path = _strict_path(item.path, label="capability_path")
        if supplied_key is not None and supplied_key != path:
            raise _InvalidEvidence("capability_path_key_mismatch")
        if path not in inventory_paths:
            raise _InvalidEvidence("capability_path_not_in_inventory")
        if path.casefold() in seen:
            raise _InvalidEvidence("duplicate_capability_path")
        seen.add(path.casefold())
        result.append(item)
    return tuple(sorted(result, key=lambda item: item.path))


def _coerce_context(value: Any) -> _RepositoryContext:
    raw = _record(value, label="repository_context")
    if set(raw) - _REPOSITORY_CONTEXT_FIELDS:
        raise _InvalidEvidence("repository_context_has_unknown_fields")
    schema_version = raw.get("schema_version", 1)
    if type(schema_version) is not int or schema_version != 1:
        raise _InvalidEvidence("repository_context_schema_version_is_invalid")
    if raw.get("human_approval_required", True) is not True:
        raise _InvalidEvidence("repository_context_human_approval_bypassed")
    inventory = raw.get("inventory")
    if not isinstance(inventory, RepositoryInventory):
        raise _InvalidEvidence("repository_context_requires_inventory")
    task_id = _nonblank_context_string(raw.get("task_id"), label="task_id")
    operation_id = _nonblank_context_string(raw.get("operation_id"), label="operation_id")
    repository_root = _nonblank_context_string(
        raw.get("repository_root"), label="repository_root"
    )
    repository_id = _nonblank_context_string(raw.get("repository_id"), label="repository_id")
    inventory_identity = _nonblank_context_string(
        raw.get("inventory_identity"), label="inventory_identity"
    )
    if repository_root != inventory.canonical_root:
        raise _InvalidEvidence("repository_root_mismatch")
    expected_repository_id = derive_repository_id_from_canonical_root(repository_root)
    if repository_id != expected_repository_id:
        raise _InvalidEvidence("repository_id_mismatch")
    expected_inventory_identity = compute_repository_inventory_identity(inventory)
    if inventory_identity != expected_inventory_identity:
        raise _InvalidEvidence("inventory_identity_mismatch")
    current = raw.get("current_file_identities")
    if not isinstance(current, Mapping):
        raise _InvalidEvidence("current_file_identities_are_required")
    inventory_paths = {entry.relative_path.as_posix() for entry in inventory.entries}
    current_keys: set[str] = set()
    for path in current:
        canonical = _strict_path(path, label="current_identity_path")
        if canonical not in inventory_paths:
            raise _InvalidEvidence("current_identity_path_not_in_inventory")
        if canonical.casefold() in current_keys:
            raise _InvalidEvidence("duplicate_current_identity_path")
        current_keys.add(canonical.casefold())
    capabilities = _coerce_capabilities(raw.get("file_capabilities"), inventory_paths)
    return _RepositoryContext(
        task_id=task_id,
        operation_id=operation_id,
        repository_root=repository_root,
        repository_id=repository_id,
        inventory_identity=inventory_identity,
        inventory=inventory,
        current_file_identities=current,
        capabilities=capabilities,
        attachment_created_at=_timestamp(raw.get("attachment_created_at")),
    )


def _coerce_patch_result(value: Any, context: _RepositoryContext) -> DirectPatchCandidateGateResult:
    if not isinstance(value, DirectPatchCandidateGateResult):
        # A bare ProposedPatchSet cannot bind task/operation/receipt provenance;
        # the similarly named CTX.SELECT ProposedPatchSet is deliberately not an
        # accepted substitute either.
        raise _InvalidEvidence("ctx_patch_result_must_be_typed")
    if not isinstance(value.proposed_patch_set, ProposedPatchSet):
        raise _InvalidEvidence("ctx_patch_result_has_invalid_proposal")
    if type(value.files_read) is not int or not 0 <= value.files_read <= MAX_RECEIPTS:
        raise _InvalidEvidence("ctx_patch_files_read_is_invalid")
    if value.task_id != context.task_id:
        raise _InvalidEvidence("task_id_mismatch")
    if value.operation_id != context.operation_id:
        raise _InvalidEvidence("operation_id_mismatch")
    if value.inventory_identity != context.inventory_identity:
        raise _InvalidEvidence("patch_result_inventory_identity_mismatch")
    if not _authority_is_safe(value) or not _authority_is_safe(value.proposed_patch_set):
        raise _InvalidEvidence("ctx_patch_authority_escalation")
    plan = value.proposed_patch_set
    if not all(
        isinstance(group, tuple)
        for group in (
            plan.implementation_candidates,
            plan.validation_candidates,
            plan.supporting_context,
            plan.blocked_candidates,
            value.evaluations,
        )
    ):
        raise _InvalidEvidence("ctx_patch_result_must_use_immutable_candidate_groups")
    proposed = tuple(plan.implementation_candidates) + tuple(plan.validation_candidates)
    if not all(isinstance(item, PatchCandidateEvaluation) for item in proposed):
        raise _InvalidEvidence("ctx_patch_candidates_must_be_typed")
    if not all(isinstance(item, PatchCandidateEvaluation) for item in value.evaluations):
        raise _InvalidEvidence("ctx_patch_evaluations_must_be_typed")
    by_path: dict[str, PatchCandidateEvaluation] = {}
    for evaluation in value.evaluations:
        if evaluation.path in by_path:
            raise _InvalidEvidence("duplicate_ctx_patch_evaluation_path")
        by_path[evaluation.path] = evaluation
    for candidate in proposed:
        if by_path.get(candidate.path) != candidate:
            raise _InvalidEvidence("proposed_candidate_not_backed_by_gate_evaluation")
    return value


def _coerce_receipts(value: Any, context: _RepositoryContext) -> dict[str, DirectReadReceipt]:
    if isinstance(value, (str, bytes, Mapping)) or value is None:
        raise _InvalidEvidence("read_receipts_must_be_typed_iterable")
    raw = tuple(islice(iter(value), MAX_RECEIPTS + 1))
    if len(raw) > MAX_RECEIPTS:
        raise _InvalidEvidence("read_receipts_exceed_limit")
    inventory_paths = {entry.relative_path.as_posix() for entry in context.inventory.entries}
    result: dict[str, DirectReadReceipt] = {}
    for receipt in raw:
        if not isinstance(receipt, DirectReadReceipt):
            raise _InvalidEvidence("read_receipts_must_be_typed")
        if (
            not isinstance(receipt.file_identity, DirectReadFileIdentity)
            or not isinstance(receipt.ranges, tuple)
            or not all(isinstance(item, DirectReadRangeReceipt) for item in receipt.ranges)
            or not isinstance(receipt.truncation_reasons, tuple)
        ):
            raise _InvalidEvidence("read_receipt_must_use_immutable_typed_fields")
        path = _strict_path(receipt.path, label="receipt_path")
        if path not in inventory_paths:
            raise _InvalidEvidence("receipt_path_not_in_inventory")
        if path.casefold() in {item.casefold() for item in result}:
            raise _InvalidEvidence("duplicate_receipt_path")
        if (
            receipt.task_id != context.task_id
            or receipt.operation_id != context.operation_id
            or receipt.inventory_identity != context.inventory_identity
        ):
            raise _InvalidEvidence("receipt_scope_mismatch")
        if not _authority_is_safe(receipt):
            raise _InvalidEvidence("receipt_authority_escalation")
        if len(receipt.ranges) > MAX_RANGES_PER_TARGET:
            raise _InvalidEvidence("receipt_ranges_exceed_limit")
        result[path] = receipt
    return result


def _ranges_are_bounded(intention: ChangeIntention, receipt: DirectReadReceipt) -> bool:
    ranges = intention.target_ranges
    if not ranges or len(ranges) > MAX_RANGES_PER_TARGET:
        return False
    if ranges != tuple(sorted(set(ranges))):
        return False
    previous_end = 0
    for target in ranges:
        if target.start_line <= previous_end:
            return False
        previous_end = target.end_line
        if not any(
            available.start_line <= target.start_line
            and available.end_line >= target.end_line
            for available in receipt.ranges
        ):
            return False
    return True


def _intention_summary(
    value: Any, receipt: DirectReadReceipt
) -> tuple[str, str, tuple[str, ...], str, tuple[TargetRange, ...]]:
    if not isinstance(value, ChangeIntention):
        raise _InvalidEvidence("bounded_change_intention_required")
    if (
        not isinstance(value.target_ranges, tuple)
        or not all(isinstance(item, TargetRange) for item in value.target_ranges)
        or not isinstance(value.must_preserve, tuple)
    ):
        raise _InvalidEvidence("change_intention_must_use_immutable_typed_fields")
    if not _ranges_are_bounded(value, receipt):
        raise _InvalidEvidence("receipt_does_not_cover_target_ranges")
    preserve = tuple(
        sorted(
            {
                _safe_text(item, label="must_preserve", maximum=180)
                for item in value.must_preserve
            }
        )
    )
    summary = _safe_text(value.summary, label="change_summary")
    expected = _safe_text(
        value.expected_behavior_change,
        label="expected_behavior_change",
    )
    fingerprint = _sha256(
        {
            "summary": summary,
            "expected_behavior_change": expected,
            "must_preserve": list(preserve),
            "target_ranges": [item.as_dict() for item in value.target_ranges],
        }
    )
    return (
        "Bounded declared change intention (redacted).",
        "Declared behavior change is bound to the review fingerprint.",
        (),
        fingerprint,
        value.target_ranges,
    )


def _validation_plan_for_candidate(
    candidate: PatchCandidateEvaluation,
) -> tuple[ValidationPlanItem, ...]:
    if candidate.validation_status == "gap":
        return (
            ValidationPlanItem(
                source_path=candidate.path,
                validation_status="gap",
                kind=None,
                target_path=None,
                target_fingerprint=None,
                confidence=None,
                test_modification_requires_separate_policy=True,
            ),
        )
    if candidate.validation_status != "mapped" or not candidate.validation_candidates:
        raise _InvalidEvidence("candidate_validation_mapping_is_invalid")
    if not isinstance(candidate.validation_candidates, tuple):
        raise _InvalidEvidence("candidate_validation_mapping_must_be_immutable")
    if len(candidate.validation_candidates) > MAX_PROPOSED_VALIDATION_FILES:
        raise _InvalidEvidence("candidate_validation_mapping_exceeds_limit")
    items: list[ValidationPlanItem] = []
    seen: set[tuple[str, str]] = set()
    for validation in candidate.validation_candidates:
        if not isinstance(validation, ValidationCandidate):
            raise _InvalidEvidence("candidate_validation_mapping_must_be_typed")
        key = (validation.kind, validation.target)
        if key in seen:
            raise _InvalidEvidence("duplicate_candidate_validation_mapping")
        seen.add(key)
        target_path = (
            validation.target
            if validation.target == validation.target.strip()
            and not any(character.isspace() for character in validation.target)
            and is_safe_repository_relative_path(validation.target)
            else None
        )
        items.append(
            ValidationPlanItem(
                source_path=candidate.path,
                validation_status="mapped",
                kind=validation.kind,
                target_path=target_path,
                target_fingerprint=_sha256(
                    {"kind": validation.kind, "target": validation.target}
                ),
                confidence=validation.confidence,
                test_modification_requires_separate_policy=(
                    validation.test_modification_requires_separate_policy
                ),
            )
        )
    return tuple(items)


def _capability_map(value: _RepositoryContext) -> dict[str, FileCapability]:
    return {item.path: item for item in value.capabilities}


def _candidate_review_points(candidate: PatchCandidateEvaluation, capability: FileCapability) -> set[str]:
    review: set[str] = set()
    if candidate.candidate_state in _REVIEW_STATES:
        review.add(candidate.candidate_state)
    if candidate.blast_radius in {"medium", "high", "critical", "unknown"}:
        review.add(f"blast_radius_{candidate.blast_radius}")
    if candidate.validation_status == "gap":
        review.add("validation_gap")
    if capability.editability == "editable_with_review":
        review.add("editability_requires_review")
    if capability.parser_support in {"partial", "unsupported"}:
        review.add("parser_support_limited")
    if capability.understanding_confidence == "raw_text_only":
        review.add("raw_text_only_understanding")
    if candidate.role.casefold() == "configuration":
        review.add("configuration_candidate")
    return review


def _review_risk_level(targets: tuple[AttachmentTarget, ...]) -> str:
    levels = {"low": 0, "medium": 1, "high": 2, "critical": 3, "unknown": 4}
    if not targets:
        return "unknown"
    return max(targets, key=lambda item: levels.get(item.blast_radius, 4)).blast_radius


def _capability_block(candidate: PatchCandidateEvaluation, capability: FileCapability) -> tuple[str, str] | None:
    if not capability.repository_contained:
        return "attachment_blocked", "capability_not_repository_contained"
    if capability.symlink_escape:
        return "security_blocked", "symlink_alias_blocked"
    if capability.generated or capability.vendor:
        return "attachment_blocked", "generated_or_vendor_target"
    if capability.editability in {"sensitive_requires_approval", "forbidden", "opaque"}:
        return "security_blocked", "sensitive_or_forbidden_target"
    if capability.editability in {"outside_scope", "read_only"}:
        return "attachment_blocked", "non_editable_target"
    if candidate.candidate_state == "generated_source_redirect":
        return "attachment_blocked", "generated_source_requires_separate_read_and_proposal"
    if candidate.candidate_state == "sensitive_blocked":
        return "security_blocked", "candidate_sensitive_blocked"
    if candidate.candidate_state in {"read_only_context", "outside_scope", "forbidden"}:
        return "attachment_blocked", "candidate_state_not_attachable"
    if candidate.candidate_state not in _ATTACHABLE_STATES:
        return "attachment_blocked", "candidate_state_not_attachable"
    return None


def _receipt_fingerprints(receipt: DirectReadReceipt) -> tuple[str, str]:
    rendered = receipt.as_dict()
    identity = rendered["file_identity"]
    return _sha256(rendered), _sha256(identity)


def _invoke_policy(policy: Any, paths: tuple[str, ...], root: str) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Run the existing gate (and optional narrowing policy) without trusting it blindly."""

    policies = [evaluate_patch_safety]
    if policy is not None and policy is not evaluate_patch_safety:
        if not callable(policy):
            return {}, "existing_patch_policy_is_invalid"
        policies.append(policy)
    blocked: dict[str, dict[str, Any]] = {}
    for check in policies:
        try:
            outcome = check(paths, project_root=root)
        except TypeError:
            # Compatibility for a stricter injected policy that intentionally
            # accepts only the target sequence.  It can narrow, never widen,
            # because the real existing gate has already run above.
            try:
                outcome = check(paths)
            except Exception:
                return {}, "existing_patch_policy_failed"
        except Exception:
            return {}, "existing_patch_policy_failed"
        if not isinstance(outcome, Mapping) or type(outcome.get("ok")) is not bool:
            return {}, "existing_patch_policy_response_invalid"
        raw_blocked = outcome.get("blocked_paths")
        if not isinstance(raw_blocked, list):
            return {}, "existing_patch_policy_response_invalid"
        if outcome["ok"] is False and not raw_blocked:
            return {}, "existing_patch_policy_denied_without_targets"
        for item in raw_blocked:
            if not isinstance(item, Mapping):
                return {}, "existing_patch_policy_response_invalid"
            raw_path = item.get("path")
            if raw_path not in paths:
                return {}, "existing_patch_policy_returned_unknown_path"
            blocked[str(raw_path)] = dict(item)
    return blocked, None


def _attachment_identity(result: DirectPatchCandidateGateResult) -> str:
    plan = result.proposed_patch_set
    payload = {
        "phase_id": CTX_PATCH_PHASE_ID,
        "task_id": result.task_id,
        "operation_id": result.operation_id,
        "inventory_identity": result.inventory_identity,
        # Hash the complete bounded typed proposal rather than only its paths.
        # Path, state, intended ranges, behavior, risk, validation mapping, and
        # supporting/blocked classifications therefore cannot share an identity.
        "proposed_patch_set": plan.as_dict(),
        "evaluations": [item.as_dict() for item in result.evaluations],
    }
    return _sha256(payload)


def _make_attachment(
    *,
    status: str,
    context: _RepositoryContext | None,
    proposal_identity: str,
    implementation_targets: Iterable[AttachmentTarget] = (),
    validation_evidence: Iterable[ValidationEvidence] = (),
    validation_plan: Iterable[ValidationPlanItem] = (),
    blocked_candidates: Iterable[BlockedAttachmentCandidate] = (),
    review_points: Iterable[str] = (),
    errors: Iterable[str] = (),
    targeted_identity_checks: int = 0,
) -> PatchSafetyAttachment:
    targets = tuple(sorted(implementation_targets, key=lambda item: item.path))
    validations = tuple(sorted(validation_evidence, key=lambda item: item.path))
    plan_items = tuple(
        sorted(
            validation_plan,
            key=lambda item: (
                item.source_path,
                item.validation_status,
                item.kind or "",
                item.target_fingerprint or "",
            ),
        )
    )
    blocked = tuple(sorted(blocked_candidates, key=lambda item: (item.path, item.candidate_group)))
    review = tuple(sorted(set(review_points)))[:MAX_REVIEW_POINTS]
    safe_errors = tuple(sorted(set(errors)))
    created_at = (
        context.attachment_created_at
        if context is not None
        else datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    identity = {
        "phase_id": PHASE_ID,
        "status": status,
        "task_id": context.task_id if context else "<invalid-task>",
        "operation_id": context.operation_id if context else "<invalid-operation>",
        "repository_root": context.repository_root if context else "<invalid-root>",
        "repository_id": context.repository_id if context else "<invalid-repository>",
        "inventory_identity": context.inventory_identity if context else "<invalid-inventory>",
        "proposed_patch_set_identity": proposal_identity,
        "attachment_created_at": created_at,
        "implementation_targets": [item.as_dict() for item in targets],
        "validation_evidence": [item.as_dict() for item in validations],
        "validation_plan": [item.as_dict() for item in plan_items],
        "blocked_candidates": [item.as_dict() for item in blocked],
        "review_points": list(review),
        "errors": list(safe_errors),
    }
    return PatchSafetyAttachment(
        status=status,
        task_id=identity["task_id"],
        operation_id=identity["operation_id"],
        repository_root=identity["repository_root"],
        repository_id=identity["repository_id"],
        inventory_identity=identity["inventory_identity"],
        proposed_patch_set_identity=proposal_identity,
        attachment_created_at=created_at,
        attachment_fingerprint=_sha256(identity),
        implementation_targets=targets,
        validation_evidence=validations,
        validation_plan=plan_items,
        blocked_candidates=blocked,
        human_review_points=review,
        errors=safe_errors,
        targeted_identity_checks=targeted_identity_checks,
    )


def _status_for_empty_plan(plan: ProposedPatchSet) -> str:
    if plan.status == "human_file_selection_required":
        return "human_file_selection_required"
    if plan.status == "reread_required":
        return "reread_required"
    if plan.status == "blocked":
        return "policy_blocked"
    return "invalid_evidence"


def attach_direct_context_to_patch_safety(
    *,
    proposed_patch_set: DirectPatchCandidateGateResult,
    read_receipts: Iterable[DirectReadReceipt],
    repository_context: Mapping[str, Any],
    existing_patch_policy: Any = None,
) -> PatchSafetyAttachment:
    """Attach a CTX.PATCH.1 proposal to existing patch safety for human review.

    The caller supplies all identity observations.  In particular, this helper
    never discovers files, stats paths, opens content, creates an approval, or
    executes a patch.  A later generation/application step must repeat its own
    target identity, existing safety, and human-approval checks.
    """

    context: _RepositoryContext | None = None
    proposal_identity = "sha256:invalid"
    try:
        context = _coerce_context(repository_context)
        patch_result = _coerce_patch_result(proposed_patch_set, context)
        proposal_identity = _attachment_identity(patch_result)
        receipts = _coerce_receipts(read_receipts, context)
        if patch_result.files_read != len(receipts):
            raise _InvalidEvidence("ctx_patch_read_receipt_count_mismatch")
        plan = patch_result.proposed_patch_set
        if (
            len(plan.implementation_candidates) > MAX_PROPOSED_SOURCE_FILES
            or len(plan.validation_candidates) > MAX_PROPOSED_VALIDATION_FILES
            or len(plan.implementation_candidates) + len(plan.validation_candidates)
            > MAX_PROPOSED_TOTAL_FILES
        ):
            raise _InvalidEvidence("proposed_patch_set_exceeds_limits")
        all_candidates = tuple(plan.implementation_candidates) + tuple(plan.validation_candidates)
        if not all(isinstance(item, PatchCandidateEvaluation) for item in all_candidates):
            raise _InvalidEvidence("ctx_patch_candidates_must_be_typed")
        paths = [item.path for item in all_candidates]
        if any(_strict_path(path, label="candidate_path") != path for path in paths):
            raise _InvalidEvidence("candidate_path_is_not_canonical")
        if len(paths) != len({path.casefold() for path in paths}):
            raise _InvalidEvidence("duplicate_candidate_path")
        inventory_paths = {entry.relative_path.as_posix() for entry in context.inventory.entries}
        if any(path not in inventory_paths for path in paths):
            raise _InvalidEvidence("candidate_path_not_in_inventory")
    except _InvalidEvidence as exc:
        return _make_attachment(
            status="invalid_evidence",
            context=context,
            proposal_identity=proposal_identity,
            errors=(str(exc),),
        )

    if plan.status not in _ATTACHABLE_PLAN_STATUSES:
        terminal_candidates = (
            tuple(plan.implementation_candidates) + tuple(plan.validation_candidates)
        )
        if terminal_candidates:
            return _make_attachment(
                status="invalid_evidence",
                context=context,
                proposal_identity=proposal_identity,
                blocked_candidates=(
                    BlockedAttachmentCandidate(
                        path=item.path,
                        candidate_group=(
                            "implementation"
                            if item in plan.implementation_candidates
                            else "validation"
                        ),
                        candidate_state=item.candidate_state,
                        decision="invalid_evidence",
                        reason_code="terminal_patch_set_status_has_candidates",
                        receipt_freshness=item.receipt_freshness,
                    )
                    for item in terminal_candidates
                ),
                errors=("terminal_patch_set_status_has_candidates",),
            )

    if not plan.implementation_candidates:
        status = _status_for_empty_plan(plan)
        review = (
            "additional_context_required"
            if plan.status == "insufficient_evidence"
            else "no_implementation_candidate_attached"
        )
        return _make_attachment(
            status=status,
            context=context,
            proposal_identity=proposal_identity,
            review_points=(review,),
        )

    implementation_paths = tuple(item.path for item in plan.implementation_candidates)
    policy_blocks, policy_error = _invoke_policy(
        existing_patch_policy, implementation_paths, context.repository_root
    )
    if policy_error:
        return _make_attachment(
            status="policy_blocked",
            context=context,
            proposal_identity=proposal_identity,
            blocked_candidates=(
                BlockedAttachmentCandidate(
                    path=item.path,
                    candidate_group="implementation",
                    candidate_state=item.candidate_state,
                    decision="policy_blocked",
                    reason_code=policy_error,
                    receipt_freshness="unverifiable",
                )
                for item in plan.implementation_candidates
            ),
            errors=(policy_error,),
        )

    capabilities = _capability_map(context)
    targets: list[AttachmentTarget] = []
    validations: list[ValidationEvidence] = []
    validation_plan: list[ValidationPlanItem] = []
    blocked: list[BlockedAttachmentCandidate] = []
    review_points: set[str] = set()
    identity_checks = 0

    def block(
        candidate: PatchCandidateEvaluation,
        group: str,
        decision: str,
        reason: str,
        freshness: str = "unverifiable",
    ) -> None:
        blocked.append(
            BlockedAttachmentCandidate(
                path=candidate.path,
                candidate_group=group,
                candidate_state=candidate.candidate_state,
                decision=decision,
                reason_code=reason,
                receipt_freshness=freshness,
            )
        )

    for group, candidates in (
        ("implementation", plan.implementation_candidates),
        ("validation", plan.validation_candidates),
    ):
        for candidate in candidates:
            capability = capabilities.get(candidate.path)
            if capability is None:
                block(candidate, group, "invalid_evidence", "candidate_capability_missing")
                continue
            receipt = receipts.get(candidate.path)
            if receipt is None:
                block(candidate, group, "invalid_evidence", "candidate_receipt_missing")
                continue
            if candidate.path != receipt.path:
                # Exact spelling, not a case-folded alias, is the security boundary.
                block(candidate, group, "invalid_evidence", "candidate_receipt_path_mismatch")
                continue
            if candidate.path not in context.current_file_identities:
                block(candidate, group, "attachment_blocked", "current_identity_missing")
                continue
            identity_checks += 1
            freshness = verify_direct_read_receipt(
                receipt, context.current_file_identities[candidate.path]
            )
            if freshness.status == "changed":
                block(candidate, group, "reread_required", "receipt_changed", freshness.status)
                continue
            if freshness.status == "deleted":
                block(candidate, group, "candidate_removed", "receipt_target_deleted", freshness.status)
                continue
            if freshness.status == "replaced":
                block(candidate, group, "security_blocked", "receipt_target_replaced", freshness.status)
                continue
            if freshness.status != "fresh":
                block(candidate, group, "attachment_blocked", "receipt_unverifiable", freshness.status)
                continue
            blocked_by_capability = _capability_block(candidate, capability)
            if blocked_by_capability is not None:
                decision, reason = blocked_by_capability
                block(candidate, group, decision, reason, freshness.status)
                continue
            receipt_fingerprint, file_identity_fingerprint = _receipt_fingerprints(receipt)
            if group == "validation":
                kinds = tuple(sorted({item.kind for item in candidate.validation_candidates}))
                validations.append(
                    ValidationEvidence(
                        path=candidate.path,
                        receipt_freshness=freshness.status,
                        receipt_fingerprint=receipt_fingerprint,
                        file_identity_fingerprint=file_identity_fingerprint,
                        validation_status=candidate.validation_status,
                        validation_plan_kinds=kinds,
                    )
                )
                if candidate.validation_status == "gap":
                    review_points.add("validation_gap")
                continue
            if candidate.path in policy_blocks:
                block(candidate, group, "policy_blocked", "existing_patch_safety_blocked", freshness.status)
                continue
            try:
                summary, expected, preserve, intention_fingerprint, ranges = _intention_summary(
                    candidate.change_intention, receipt
                )
                candidate_validation_plan = _validation_plan_for_candidate(candidate)
            except _InvalidEvidence as exc:
                block(candidate, group, "invalid_evidence", str(exc), freshness.status)
                continue
            if (
                len(validation_plan) + len(candidate_validation_plan)
                > MAX_PROPOSED_VALIDATION_FILES
            ):
                block(
                    candidate,
                    group,
                    "invalid_evidence",
                    "attachment_validation_plan_exceeds_limit",
                    freshness.status,
                )
                continue
            candidate_review = _candidate_review_points(candidate, capability)
            targets.append(
                AttachmentTarget(
                    path=candidate.path,
                    candidate_state=candidate.candidate_state,
                    patchability_score=candidate.patchability_score,
                    blast_radius=candidate.blast_radius,
                    receipt_freshness=freshness.status,
                    target_ranges=ranges,
                    receipt_fingerprint=receipt_fingerprint,
                    file_identity_fingerprint=file_identity_fingerprint,
                    change_summary=summary,
                    expected_behavior_change=expected,
                    must_preserve=preserve,
                    change_intention_fingerprint=intention_fingerprint,
                    review_required=bool(candidate_review),
                )
            )
            validation_plan.extend(candidate_validation_plan)
            review_points.update(candidate_review)

    if len(targets) > 1:
        review_points.add("multiple_implementation_files")
    if blocked and targets:
        status = "partially_attached"
    elif targets and review_points:
        status = "attached_with_review"
    elif targets:
        status = "attached"
    else:
        decisions = {item.decision for item in blocked}
        if "security_blocked" in decisions:
            status = "security_blocked"
        elif "reread_required" in decisions:
            status = "reread_required"
        elif "policy_blocked" in decisions:
            status = "policy_blocked"
        else:
            status = "invalid_evidence"
    return _make_attachment(
        status=status,
        context=context,
        proposal_identity=proposal_identity,
        implementation_targets=targets,
        validation_evidence=validations,
        validation_plan=validation_plan,
        blocked_candidates=blocked,
        review_points=review_points,
        targeted_identity_checks=identity_checks,
    )


# Stable aliases for orchestration callers that use attachment-oriented wording.
build_direct_context_patch_safety_attachment = attach_direct_context_to_patch_safety
attach_direct_context_patch_safety = attach_direct_context_to_patch_safety
