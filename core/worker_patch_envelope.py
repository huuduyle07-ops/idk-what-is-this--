"""WORKER.DECL.2A — strict structured patch response envelope.

WORKER.DECL.1 established that every patch-producing worker response in this
repository is transported as free-form text and recovered by
``core.json_utils.extract_json_block``, which regex-matches fenced blocks and
then scans for balanced braces inside arbitrary prose.  That channel cannot
carry a trustworthy typed field, because "a JSON object appeared somewhere in
the answer" is not a protocol.

This module defines the protocol instead:

    the entire non-whitespace response is exactly one JSON object,
    whose keys are an explicit allow-list,
    whose patch plan reuses the existing operation contract unchanged,
    and every bound of which is finite.

What it deliberately does **not** do
------------------------------------

It parses no prose.  There is no ``re`` import here, no fenced-block reader, no
balanced-brace scanner, no "find the first object" fallback, and no Markdown
cleanup — the boundary suite asserts all of it.  A response that needs any of
those to yield JSON is rejected as ``surrounding_prose_rejected``; the legacy
path may continue to handle it, separately and authoritatively.

It repairs nothing.  A response over a bound is invalid, never truncated: a
silently shortened operation list or snippet would change what a patch means.

It calls no model.  Classification of a rejected response uses only the
standard-library JSON decoder's own report of where a value ended; the decoded
value in that path is discarded and can never become an envelope.

It carries no authority.  The envelope cannot express a write, approval,
validation, routing or merge decision, and authority-shaped keys are rejected
by name rather than ignored as harmless metadata.

It changes no patch semantics.  ``patch_plan`` holds the existing operation
mappings verbatim; this module validates and fingerprints them, and never
rewrites, reorders, normalises or reinterprets one.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from core.repository_path_policy import (
    MAX_CANONICAL_RELATIVE_PATH_LENGTH,
    is_safe_repository_relative_path,
)


PHASE_ID = "WORKER.DECL.2A"
PRODUCER_KIND = "worker_patch_envelope"

WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V1 = "worker_decl_2a_patch_envelope_v1"
WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2 = "worker_decl_2b_patch_envelope_v2"
# Compatibility alias: WORKER.DECL.2A callers and persisted artifacts continue
# to mean v1.  New intent-aware callers must opt into the explicit v2 parser.
WORKER_PATCH_ENVELOPE_SCHEMA_VERSION = WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V1
COMPATIBILITY_RECORD_SCHEMA_VERSION = "worker_decl_2a_response_compatibility_v1"

#: Name of the additive artifact written into the existing replay bundle.
ENVELOPE_ARTIFACT_NAME = "worker_patch_envelope.json"

#: Default-off feature flag.  Enabling it adds measurement only: the legacy
#: patch payload stays authoritative and the applied plan is untouched.
ENVIRONMENT_FLAG = "STRICT_WORKER_PATCH_ENVELOPE_SHADOW"


# ── Bounds ────────────────────────────────────────────────────────────────────

#: Whole-response ceiling.  A response larger than this is rejected before any
#: decode is attempted, so an oversized payload costs one length check.
MAX_ENVELOPE_RESPONSE_CHARS = 1_000_000

#: Operation-count ceiling.  Deliberately equal to CHECK.1's
#: ``MAX_DECLARED_CHANGES``: a plan with more operations than that already
#: cannot be represented as a complete downstream worker report, so accepting
#: one here would only defer the rejection.  The equality is pinned by a test
#: rather than by an import, to keep the worker protocol free of a checker
#: dependency.
MAX_ENVELOPE_OPERATIONS = 256

#: Intent is independently declared by the same response, never derived from
#: the operation list.  Its bound mirrors the existing finite change/operation
#: ceiling without importing a checker contract.
MAX_INTENDED_CHANGES = 256

#: Per-operation payload ceiling, applied to each snippet and file body.
MAX_OPERATION_PAYLOAD_CHARS = 131_072

MAX_PATH_CHARS = MAX_CANONICAL_RELATIVE_PATH_LENGTH

#: How many rejected key names a parse result may name back, and how long each
#: may be.  Key names are model-chosen text, so they are bounded like any other
#: untrusted string and never accompanied by their values.
MAX_REPORTED_UNKNOWN_KEYS = 8
MAX_REPORTED_KEY_CHARS = 160


# ── Vocabularies ──────────────────────────────────────────────────────────────

STATUS_VALID = "valid"
STATUS_INVALID_JSON = "invalid_json"
STATUS_NON_OBJECT = "non_object"
STATUS_UNKNOWN_FIELD = "unknown_field"
STATUS_SCHEMA_INVALID = "schema_invalid"
STATUS_BOUND_EXCEEDED = "bound_exceeded"
STATUS_SURROUNDING_PROSE_REJECTED = "surrounding_prose_rejected"
STATUS_UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"

PARSE_STATUSES: tuple[str, ...] = (
    STATUS_VALID,
    STATUS_INVALID_JSON,
    STATUS_NON_OBJECT,
    STATUS_UNKNOWN_FIELD,
    STATUS_SCHEMA_INVALID,
    STATUS_BOUND_EXCEEDED,
    STATUS_SURROUNDING_PROSE_REJECTED,
    STATUS_UNSUPPORTED_SCHEMA_VERSION,
)

#: Which channel actually supplied a patch plan for this response.  A legacy
#: payload recovered from prose is never labelled strict.
PROVENANCE_STRICT = "strict_worker_patch_envelope"
PROVENANCE_LEGACY = "legacy_extracted_json"
PROVENANCE_NONE = "no_patch_payload"

PROVENANCE_VALUES: tuple[str, ...] = (
    PROVENANCE_STRICT,
    PROVENANCE_LEGACY,
    PROVENANCE_NONE,
)

#: Whether the two parsers saw the same patch plan.  ``not_comparable`` means
#: only one of them produced a plan at all — it is not a disagreement.
AGREEMENT_AGREED = "agreed"
AGREEMENT_MISMATCH = "strict_legacy_semantic_mismatch"
AGREEMENT_NOT_COMPARABLE = "not_comparable"

AGREEMENT_VALUES: tuple[str, ...] = (
    AGREEMENT_AGREED,
    AGREEMENT_MISMATCH,
    AGREEMENT_NOT_COMPARABLE,
)

#: The complete envelope key allow-list.  ``worker_metadata`` is deliberately
#: absent: WORKER.DECL.1 found no genuinely structured worker metadata to carry,
#: and inventing a slot for it would be the very thing this phase exists to
#: avoid.  WORKER.DECL.2B owns the first real added field.
ALLOWED_ENVELOPE_KEYS: tuple[str, ...] = (
    "schema_version",
    "patch_plan",
)

ALLOWED_V2_ENVELOPE_KEYS: tuple[str, ...] = (
    "schema_version",
    "patch_plan",
    "change_intent",
)

PRE_EXECUTION_INTENT_STAGE = "pre_execution_intent"
INTENT_CHANGE_ADDED = "added"
INTENT_CHANGE_MODIFIED = "modified"

# The current executor can create a file or replace a snippet.  It cannot
# express deletion or rename operations, so the intent vocabulary does not
# pretend otherwise.
INTENDED_CHANGE_KINDS: tuple[str, ...] = (
    INTENT_CHANGE_ADDED,
    INTENT_CHANGE_MODIFIED,
)
ALLOWED_CHANGE_INTENT_KEYS: tuple[str, ...] = (
    "stage",
    "intended_changes",
)
ALLOWED_INTENDED_CHANGE_KEYS: tuple[str, ...] = (
    "path",
    "change_kind",
)

#: The existing patch-plan operation vocabulary, mirrored from
#: ``patching.patch_plan_executor.apply_patch_plan``.  It is a table, not an
#: inference: an operation the executor does not define is invalid here too.
OPERATION_CREATE_FILE = "create_file"
OPERATION_REPLACE_SNIPPET = "replace_snippet"

#: Per-operation key allow-lists.  ``file`` is the existing path alias the
#: executor already honours as a fallback, so it stays part of the contract.
ALLOWED_OPERATION_KEYS: dict[str, frozenset[str]] = {
    OPERATION_CREATE_FILE: frozenset({"op", "relative_path", "file", "content"}),
    OPERATION_REPLACE_SNIPPET: frozenset(
        {"op", "relative_path", "file", "target_snippet", "patched_snippet"}
    ),
}

#: Keys that would let a model assert a decision it has no standing to make.
#: They are already outside every allow-list; naming them explicitly makes the
#: refusal deliberate and testable rather than incidental.
FORBIDDEN_AUTHORITY_KEYS: tuple[str, ...] = (
    "write_authority",
    "write_allowed",
    "apply_authority",
    "patch_authority",
    "patch_approved",
    "validation_authority",
    "validation_passed",
    "routing_authority",
    "merge_authority",
    "merge_allowed",
    "human_approval",
    "human_approved",
    "reviewer_approved",
    "secret_authority",
    "authoritative",
    "guardrails",
)


def is_strict_worker_patch_envelope_shadow_enabled(value: str | None = None) -> bool:
    """Read the default-off flag.  Enabling it adds measurement only."""
    raw = os.getenv(ENVIRONMENT_FLAG) if value is None else value
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


# ── The envelope ──────────────────────────────────────────────────────────────

def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def canonical_patch_operation_identity(
    operation: Mapping[str, Any], index: int
) -> dict[str, Any]:
    """Reduce one operation to the facts the existing executor acts on.

    Order is preserved through ``index`` because the executor applies operations
    sequentially and ``replace_snippet`` rewrites only the first occurrence — two
    plans with the same operations in a different order are not the same plan.

    The path alias is resolved the way the executor resolves it
    (``relative_path`` first, then ``file``), so two spellings of one operation
    reduce to one identity.  A path that is not a canonical repository-relative
    spelling is represented by a digest of what was written rather than by the
    text itself, which keeps distinct unusable paths distinct without copying
    model-authored content into a record.
    """
    op_type = operation.get("op")
    declared_path = operation.get("relative_path") or operation.get("file")

    if (
        isinstance(declared_path, str)
        and declared_path[:1] not in {"/", "\\"}
        and is_safe_repository_relative_path(declared_path)
    ):
        path: dict[str, Any] = {"canonical": declared_path}
    else:
        path = {"uncanonical_digest": _digest(declared_path)}

    identity: dict[str, Any] = {
        "index": index,
        "op": op_type if isinstance(op_type, str) else None,
        "path": path,
    }
    if op_type == OPERATION_CREATE_FILE:
        identity["content"] = _digest(operation.get("content"))
    elif op_type == OPERATION_REPLACE_SNIPPET:
        identity["target_snippet"] = _digest(operation.get("target_snippet"))
        identity["patched_snippet"] = _digest(operation.get("patched_snippet"))
    else:
        # An operation the executor does not define contributes its whole shape,
        # so two different unknown operations never collide into one identity.
        identity["unsupported_operation"] = _digest(
            sorted(
                (str(key), _digest(value)) for key, value in operation.items()
            )
        )
    return identity


def canonical_patch_plan_identity(plan: Any) -> str | None:
    """Fingerprint a patch plan by what it would do, not by how it was written.

    Insignificant whitespace and JSON key order cannot change the result;
    operation order, target path, operation type and payload content all can.
    Returns ``None`` when the value is not a patch plan at all, which is
    different from an empty plan.
    """
    if isinstance(plan, (str, bytes)) or not isinstance(plan, Sequence):
        return None
    identities = [
        canonical_patch_operation_identity(operation, index)
        if isinstance(operation, Mapping)
        else {"index": index, "non_object_operation": _digest(operation)}
        for index, operation in enumerate(plan)
    ]
    return _digest({"patch_plan": identities})


@dataclass(frozen=True, slots=True)
class IntendedChange:
    """One repository effect declared before execution.

    This value is a model claim.  A valid path here grants no write authority
    and does not become a patch operation.
    """

    path: str
    change_kind: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str):
            raise TypeError("intended change path must be a string")
        if len(self.path) > MAX_PATH_CHARS:
            raise ValueError("intended change path exceeds its finite bound")
        if self.path[:1] in {"/", "\\"} or not is_safe_repository_relative_path(
            self.path
        ):
            raise ValueError(
                "intended change path must be a canonical repository-relative path"
            )
        if self.change_kind not in INTENDED_CHANGE_KINDS:
            raise ValueError(
                f"unsupported intended change kind: {self.change_kind!r}"
            )

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "change_kind": self.change_kind}


@dataclass(frozen=True, slots=True)
class PreExecutionChangeIntent:
    """Smallest useful immutable pre-execution intent declaration.

    It is structurally separate from ``patch_plan`` even though the same model
    invocation emits both.  That is independent declaration from programmatic
    derivation, not evidential independence.
    """

    stage: str
    intended_changes: tuple[IntendedChange, ...] = ()

    def __post_init__(self) -> None:
        if self.stage != PRE_EXECUTION_INTENT_STAGE:
            raise ValueError("change intent stage must be pre_execution_intent")
        if type(self.intended_changes) is not tuple:
            raise TypeError("intended_changes must be a tuple")
        if len(self.intended_changes) > MAX_INTENDED_CHANGES:
            raise ValueError("intended changes exceed their finite bound")
        if not all(type(item) is IntendedChange for item in self.intended_changes):
            raise TypeError("intended_changes must contain IntendedChange records")
        paths = tuple(item.path for item in self.intended_changes)
        if len(set(paths)) != len(paths):
            raise ValueError("intended change paths must be unique")

    @property
    def fingerprint(self) -> str:
        return _digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "intended_changes": [
                item.as_dict()
                for item in sorted(self.intended_changes, key=lambda item: item.path)
            ],
        }


@dataclass(frozen=True, slots=True)
class WorkerPatchEnvelope:
    """One strictly parsed worker patch response.

    ``patch_plan`` holds the existing operation mappings unchanged — read-only
    views over exactly what the worker sent.  Nothing here is a new patch-plan
    dialect: ``patch_plan_operations()`` hands the very same operations to the
    existing executor.
    """

    schema_version: str
    patch_plan: tuple[Mapping[str, Any], ...] = ()
    change_intent: PreExecutionChangeIntent | None = None

    def __post_init__(self) -> None:
        if self.schema_version not in {
            WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V1,
            WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2,
        }:
            raise ValueError("unsupported worker patch envelope schema version")
        if (
            self.schema_version == WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V1
            and self.change_intent is not None
        ):
            raise ValueError("a v1 worker patch envelope cannot carry change_intent")
        if (
            self.schema_version == WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2
            and type(self.change_intent) is not PreExecutionChangeIntent
        ):
            raise ValueError("a v2 worker patch envelope requires change_intent")
        if type(self.patch_plan) is not tuple:
            raise TypeError("patch_plan must be a tuple of operations")
        if len(self.patch_plan) > MAX_ENVELOPE_OPERATIONS:
            raise ValueError("patch plan exceeds its finite operation bound")
        for operation in self.patch_plan:
            if not isinstance(operation, Mapping):
                raise TypeError("every patch plan operation must be a mapping")

    def patch_plan_operations(self) -> list[dict[str, Any]]:
        """The plan in the shape the existing apply engine already accepts."""
        return [dict(operation) for operation in self.patch_plan]

    @property
    def patch_plan_identity(self) -> str:
        return canonical_patch_plan_identity(self.patch_plan) or _digest(None)

    def as_dict(self) -> dict[str, Any]:
        """A bounded record of the envelope's identity, not of its payload.

        Snippets and file bodies stay out: they are already carried by the
        run's own patch artifacts, and duplicating them into a second artifact
        would widen where model-authored content is written for no measurement
        benefit.
        """
        record = {
            "schema_version": self.schema_version,
            "phase_id": (
                "WORKER.DECL.2B"
                if self.schema_version == WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2
                else PHASE_ID
            ),
            "operation_count": len(self.patch_plan),
            "patch_plan_identity": self.patch_plan_identity,
            "envelope_fingerprint": worker_patch_envelope_fingerprint(self),
        }
        if self.change_intent is not None:
            record.update(
                {
                    "change_intent_stage": self.change_intent.stage,
                    "intended_change_count": len(
                        self.change_intent.intended_changes
                    ),
                    "change_intent_fingerprint": self.change_intent.fingerprint,
                }
            )
        return record


def worker_patch_envelope_fingerprint(envelope: WorkerPatchEnvelope) -> str:
    """Fingerprint the envelope's semantics: schema version plus plan identity.

    No clock, no latency, no provider response id — a replayed response
    fingerprints identically to the original.
    """
    if type(envelope) is not WorkerPatchEnvelope:
        raise TypeError(
            "worker_patch_envelope_fingerprint requires an exact "
            "WorkerPatchEnvelope"
        )
    identity = {
        "schema_version": envelope.schema_version,
        "patch_plan_identity": envelope.patch_plan_identity,
    }
    if envelope.change_intent is not None:
        identity["change_intent_fingerprint"] = envelope.change_intent.fingerprint
    return _digest(identity)


# ── Strict parsing ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class WorkerPatchEnvelopeParse:
    """The outcome of one strict parse.  No score, no confidence."""

    status: str
    envelope: WorkerPatchEnvelope | None = None
    unknown_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in PARSE_STATUSES:
            raise ValueError(f"unsupported parse status: {self.status!r}")
        if (self.envelope is None) is (self.status == STATUS_VALID):
            raise ValueError("exactly a valid parse carries an envelope")

    @property
    def is_valid(self) -> bool:
        return self.status == STATUS_VALID

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "envelope": self.envelope.as_dict() if self.envelope else None,
            "unknown_keys": list(self.unknown_keys),
        }


def _reject(status: str, unknown_keys: Sequence[str] = ()) -> WorkerPatchEnvelopeParse:
    bounded = tuple(
        str(key)[:MAX_REPORTED_KEY_CHARS]
        for key in list(unknown_keys)[:MAX_REPORTED_UNKNOWN_KEYS]
    )
    return WorkerPatchEnvelopeParse(status=status, unknown_keys=bounded)


def _rejection_status_for_undecodable(text: str) -> str:
    """Classify a response the whole-text decode refused, returning a status.

    This helper exists to tell "malformed JSON" apart from "a JSON object with
    something around it" for measurement purposes.  It returns a status string
    and nothing else: no value decoded here is reachable by a caller, so it
    cannot become an envelope by any path.
    """
    if not text.startswith("{"):
        # Text appears where the protocol allows only a single top-level object:
        # a Markdown fence, a preamble, or a response that is prose throughout.
        # Telling those apart would mean scanning the response for an object
        # somewhere inside it, which is precisely the recovery this phase
        # refuses; ``legacy_available`` on the compatibility record already
        # answers "would the legacy extractor have found something here?".
        return STATUS_SURROUNDING_PROSE_REJECTED
    try:
        json.JSONDecoder().raw_decode(text)
    except ValueError:
        return STATUS_INVALID_JSON
    # A complete object was followed by more content: trailing prose, or a
    # second object.  Taking the first one is exactly what this phase refuses.
    return STATUS_SURROUNDING_PROSE_REJECTED


def _operation_bound_exceeded(operation: Mapping[str, Any]) -> bool:
    for key in ("content", "target_snippet", "patched_snippet"):
        value = operation.get(key)
        if isinstance(value, str) and len(value) > MAX_OPERATION_PAYLOAD_CHARS:
            return True
    return False


def _validate_operation(operation: Any) -> str | None:
    """Return a rejection status for one operation, or ``None`` if it is sound."""
    if not isinstance(operation, Mapping):
        return STATUS_SCHEMA_INVALID

    op_type = operation.get("op")
    if not isinstance(op_type, str) or op_type not in ALLOWED_OPERATION_KEYS:
        return STATUS_SCHEMA_INVALID

    keys = {str(key) for key in operation}
    if keys & set(FORBIDDEN_AUTHORITY_KEYS):
        return STATUS_UNKNOWN_FIELD
    if keys - ALLOWED_OPERATION_KEYS[op_type]:
        return STATUS_UNKNOWN_FIELD

    # Resolve the alias exactly as the executor does: ``relative_path`` first,
    # then ``file``, with any falsy value falling through.
    declared_path = operation.get("relative_path") or operation.get("file")
    if not isinstance(declared_path, str):
        return STATUS_SCHEMA_INVALID
    if len(declared_path) > MAX_PATH_CHARS:
        return STATUS_BOUND_EXCEEDED
    # Strict means strict: a path is accepted as written or not at all.  The
    # legacy path may still repair a spelling; this channel never does.  The
    # explicit leading-separator guard is the same one the sibling declaration
    # contract carries: a rooted POSIX path is not reported absolute by the
    # shared lexical policy on Windows, where it has no drive letter.
    if declared_path[:1] in {"/", "\\"} or not is_safe_repository_relative_path(
        declared_path
    ):
        return STATUS_SCHEMA_INVALID

    required = (
        ("content",)
        if op_type == OPERATION_CREATE_FILE
        else ("target_snippet", "patched_snippet")
    )
    for key in required:
        if not isinstance(operation.get(key), str):
            return STATUS_SCHEMA_INVALID

    if _operation_bound_exceeded(operation):
        return STATUS_BOUND_EXCEEDED
    return None


def parse_strict_worker_patch_envelope(
    response_text: Any,
) -> WorkerPatchEnvelopeParse:
    """Parse one response under the strict one-object protocol.

    The entire non-whitespace response must be exactly one JSON object.  There
    is no fence reader, no brace scanner and no first-object search: a response
    that carries an object *somewhere* is rejected, not recovered.
    """
    if not isinstance(response_text, str):
        return _reject(STATUS_INVALID_JSON)
    if len(response_text) > MAX_ENVELOPE_RESPONSE_CHARS:
        return _reject(STATUS_BOUND_EXCEEDED)

    text = response_text.strip()
    if not text:
        return _reject(STATUS_INVALID_JSON)

    try:
        decoded = json.loads(text)
    except ValueError:
        return _reject(_rejection_status_for_undecodable(text))

    if not isinstance(decoded, dict):
        return _reject(STATUS_NON_OBJECT)

    keys = {str(key) for key in decoded}
    claimed_authority = sorted(keys & set(FORBIDDEN_AUTHORITY_KEYS))
    if claimed_authority:
        return _reject(STATUS_UNKNOWN_FIELD, claimed_authority)
    unknown = sorted(keys - set(ALLOWED_ENVELOPE_KEYS))
    if unknown:
        return _reject(STATUS_UNKNOWN_FIELD, unknown)

    missing = sorted(set(ALLOWED_ENVELOPE_KEYS) - keys)
    if missing:
        return _reject(STATUS_SCHEMA_INVALID, missing)

    schema_version = decoded["schema_version"]
    if not isinstance(schema_version, str):
        return _reject(STATUS_SCHEMA_INVALID)
    if schema_version != WORKER_PATCH_ENVELOPE_SCHEMA_VERSION:
        return _reject(STATUS_UNSUPPORTED_SCHEMA_VERSION)

    plan = decoded["patch_plan"]
    if not isinstance(plan, list):
        return _reject(STATUS_SCHEMA_INVALID)
    if len(plan) > MAX_ENVELOPE_OPERATIONS:
        # Rejected whole.  Trimming the tail would silently change the patch.
        return _reject(STATUS_BOUND_EXCEEDED)

    for operation in plan:
        rejection = _validate_operation(operation)
        if rejection is not None:
            return _reject(rejection)

    envelope = WorkerPatchEnvelope(
        schema_version=schema_version,
        patch_plan=tuple(MappingProxyType(dict(operation)) for operation in plan),
    )
    return WorkerPatchEnvelopeParse(status=STATUS_VALID, envelope=envelope)


def _validate_change_intent(
    raw: Any,
) -> tuple[str | None, PreExecutionChangeIntent | None, tuple[str, ...]]:
    """Validate the v2 intent object without consulting its sibling plan."""
    if not isinstance(raw, Mapping):
        return STATUS_SCHEMA_INVALID, None, ()

    keys = {str(key) for key in raw}
    claimed_authority = tuple(sorted(keys & set(FORBIDDEN_AUTHORITY_KEYS)))
    if claimed_authority:
        return STATUS_UNKNOWN_FIELD, None, claimed_authority
    unknown = tuple(sorted(keys - set(ALLOWED_CHANGE_INTENT_KEYS)))
    if unknown:
        return STATUS_UNKNOWN_FIELD, None, unknown
    missing = tuple(sorted(set(ALLOWED_CHANGE_INTENT_KEYS) - keys))
    if missing:
        return STATUS_SCHEMA_INVALID, None, missing

    if raw.get("stage") != PRE_EXECUTION_INTENT_STAGE:
        return STATUS_SCHEMA_INVALID, None, ()
    changes = raw.get("intended_changes")
    if not isinstance(changes, list):
        return STATUS_SCHEMA_INVALID, None, ()
    if len(changes) > MAX_INTENDED_CHANGES:
        return STATUS_BOUND_EXCEEDED, None, ()

    intended: list[IntendedChange] = []
    seen: dict[str, str] = {}
    for raw_change in changes:
        if not isinstance(raw_change, Mapping):
            return STATUS_SCHEMA_INVALID, None, ()
        change_keys = {str(key) for key in raw_change}
        claimed_authority = tuple(
            sorted(change_keys & set(FORBIDDEN_AUTHORITY_KEYS))
        )
        if claimed_authority:
            return STATUS_UNKNOWN_FIELD, None, claimed_authority
        unknown = tuple(sorted(change_keys - set(ALLOWED_INTENDED_CHANGE_KEYS)))
        if unknown:
            return STATUS_UNKNOWN_FIELD, None, unknown
        missing = tuple(sorted(set(ALLOWED_INTENDED_CHANGE_KEYS) - change_keys))
        if missing:
            return STATUS_SCHEMA_INVALID, None, missing

        path = raw_change.get("path")
        kind = raw_change.get("change_kind")
        if not isinstance(path, str) or not isinstance(kind, str):
            return STATUS_SCHEMA_INVALID, None, ()
        if len(path) > MAX_PATH_CHARS:
            return STATUS_BOUND_EXCEEDED, None, ()
        if path[:1] in {"/", "\\"} or not is_safe_repository_relative_path(path):
            return STATUS_SCHEMA_INVALID, None, ()
        if kind not in INTENDED_CHANGE_KINDS:
            return STATUS_SCHEMA_INVALID, None, ()
        # Any duplicate is rejected.  In particular, a duplicate carrying two
        # kinds cannot be normalized into a claim the model never made.
        if path in seen:
            return STATUS_SCHEMA_INVALID, None, ()
        seen[path] = kind
        intended.append(IntendedChange(path=path, change_kind=kind))

    return (
        None,
        PreExecutionChangeIntent(
            stage=PRE_EXECUTION_INTENT_STAGE,
            intended_changes=tuple(intended),
        ),
        (),
    )


def parse_strict_worker_patch_envelope_v2(
    response_text: Any,
) -> WorkerPatchEnvelopeParse:
    """Parse the additive v2 protocol: plan plus pre-execution intent.

    V1 and v2 are deliberately separate entry points.  The v1 parser keeps its
    frozen two-key meaning and remains able to inspect historical artifacts;
    this parser requires the third field and never synthesizes it from the plan.
    """
    if not isinstance(response_text, str):
        return _reject(STATUS_INVALID_JSON)
    if len(response_text) > MAX_ENVELOPE_RESPONSE_CHARS:
        return _reject(STATUS_BOUND_EXCEEDED)

    text = response_text.strip()
    if not text:
        return _reject(STATUS_INVALID_JSON)
    try:
        decoded = json.loads(text)
    except ValueError:
        return _reject(_rejection_status_for_undecodable(text))
    if not isinstance(decoded, dict):
        return _reject(STATUS_NON_OBJECT)

    keys = {str(key) for key in decoded}
    claimed_authority = sorted(keys & set(FORBIDDEN_AUTHORITY_KEYS))
    if claimed_authority:
        return _reject(STATUS_UNKNOWN_FIELD, claimed_authority)
    unknown = sorted(keys - set(ALLOWED_V2_ENVELOPE_KEYS))
    if unknown:
        return _reject(STATUS_UNKNOWN_FIELD, unknown)
    missing = sorted(set(ALLOWED_V2_ENVELOPE_KEYS) - keys)
    if missing:
        return _reject(STATUS_SCHEMA_INVALID, missing)

    schema_version = decoded["schema_version"]
    if not isinstance(schema_version, str):
        return _reject(STATUS_SCHEMA_INVALID)
    if schema_version != WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2:
        return _reject(STATUS_UNSUPPORTED_SCHEMA_VERSION)

    plan = decoded["patch_plan"]
    if not isinstance(plan, list):
        return _reject(STATUS_SCHEMA_INVALID)
    if len(plan) > MAX_ENVELOPE_OPERATIONS:
        return _reject(STATUS_BOUND_EXCEEDED)
    for operation in plan:
        rejection = _validate_operation(operation)
        if rejection is not None:
            return _reject(rejection)

    rejection, intent, intent_keys = _validate_change_intent(
        decoded["change_intent"]
    )
    if rejection is not None:
        return _reject(rejection, intent_keys)
    if intent is None:  # pragma: no cover - guarded by the typed helper result
        return _reject(STATUS_SCHEMA_INVALID)

    envelope = WorkerPatchEnvelope(
        schema_version=schema_version,
        patch_plan=tuple(MappingProxyType(dict(operation)) for operation in plan),
        change_intent=intent,
    )
    return WorkerPatchEnvelopeParse(status=STATUS_VALID, envelope=envelope)


# ── One response, two parsers ─────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class WorkerPatchResponseCompatibility:
    """What the strict and legacy channels each made of one model response.

    This is a measurement, not a decision.  Whatever it records, the legacy
    payload remains the authoritative source of the applied patch plan for the
    whole of WORKER.DECL.2A.
    """

    strict_status: str
    provenance: str
    semantic_agreement: str
    strict_available: bool = False
    legacy_available: bool = False
    strict_patch_plan_identity: str | None = None
    legacy_patch_plan_identity: str | None = None
    envelope_fingerprint: str | None = None
    unknown_keys: tuple[str, ...] = ()
    schema_version: str = COMPATIBILITY_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.strict_status not in PARSE_STATUSES:
            raise ValueError(f"unsupported parse status: {self.strict_status!r}")
        if self.provenance not in PROVENANCE_VALUES:
            raise ValueError(f"unsupported provenance: {self.provenance!r}")
        if self.semantic_agreement not in AGREEMENT_VALUES:
            raise ValueError(f"unsupported agreement: {self.semantic_agreement!r}")
        if self.provenance == PROVENANCE_STRICT and not self.strict_available:
            raise ValueError(
                "only a valid strict parse may claim strict provenance"
            )

    @property
    def authoritative_effect(self) -> bool:
        """The measurement never changes the patch the run applies."""
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "record_kind": PRODUCER_KIND,
            "phase_id": PHASE_ID,
            "strict_status": self.strict_status,
            "strict_available": self.strict_available,
            "legacy_available": self.legacy_available,
            "provenance": self.provenance,
            "semantic_agreement": self.semantic_agreement,
            "strict_patch_plan_identity": self.strict_patch_plan_identity,
            "legacy_patch_plan_identity": self.legacy_patch_plan_identity,
            "envelope_fingerprint": self.envelope_fingerprint,
            "unknown_keys": list(self.unknown_keys),
            "authoritative_effect": self.authoritative_effect,
            "guardrails": worker_patch_envelope_guardrails(),
        }


def _legacy_patch_plan(legacy_payload: Any) -> Any:
    """The patch plan a legacy-extracted payload carries, if it carries one.

    A payload holding only a ``patch_candidate`` counts as carrying no plan:
    converting one into the other is the legacy path's own business, and doing
    it here would be this module reinterpreting a patch.
    """
    if not isinstance(legacy_payload, Mapping):
        return None
    plan = legacy_payload.get("patch_plan")
    return plan if isinstance(plan, list) and plan else None


def compare_strict_and_legacy(
    response_text: Any,
    legacy_payload: Any,
) -> WorkerPatchResponseCompatibility:
    """Measure one already-received response against both parsers.

    The model is not called: ``response_text`` is the response the run already
    has, and ``legacy_payload`` is the result the legacy extractor already
    produced from it.  One response, two parsers, one bounded record.
    """
    parse = parse_strict_worker_patch_envelope(response_text)
    legacy_plan = _legacy_patch_plan(legacy_payload)

    strict_identity = (
        parse.envelope.patch_plan_identity if parse.envelope is not None else None
    )
    legacy_identity = canonical_patch_plan_identity(legacy_plan)

    if parse.is_valid:
        provenance = PROVENANCE_STRICT
    elif legacy_plan is not None:
        provenance = PROVENANCE_LEGACY
    else:
        provenance = PROVENANCE_NONE

    if strict_identity is not None and legacy_identity is not None:
        agreement = (
            AGREEMENT_AGREED
            if strict_identity == legacy_identity
            else AGREEMENT_MISMATCH
        )
    else:
        agreement = AGREEMENT_NOT_COMPARABLE

    return WorkerPatchResponseCompatibility(
        strict_status=parse.status,
        provenance=provenance,
        semantic_agreement=agreement,
        strict_available=parse.is_valid,
        legacy_available=legacy_plan is not None,
        strict_patch_plan_identity=strict_identity,
        legacy_patch_plan_identity=legacy_identity,
        envelope_fingerprint=(
            worker_patch_envelope_fingerprint(parse.envelope)
            if parse.envelope is not None
            else None
        ),
        unknown_keys=parse.unknown_keys,
    )


def safe_compare_strict_and_legacy(
    response_text: Any,
    legacy_payload: Any,
) -> WorkerPatchResponseCompatibility | None:
    """Measure without ever being able to interrupt the run being measured."""
    try:
        return compare_strict_and_legacy(response_text, legacy_payload)
    except Exception:  # noqa: BLE001 - measurement failure is isolated
        return None


# ── Persistence and offline summary ───────────────────────────────────────────

def load_worker_patch_envelope_record(payload: Any) -> dict[str, Any]:
    """Read one persisted record, defaulting anything an older bundle lacks."""
    if not isinstance(payload, Mapping):
        return {
            "schema_version": COMPATIBILITY_RECORD_SCHEMA_VERSION,
            "record_kind": PRODUCER_KIND,
            "phase_id": PHASE_ID,
            "strict_status": None,
            "strict_available": False,
            "legacy_available": False,
            "provenance": None,
            "semantic_agreement": None,
            "strict_patch_plan_identity": None,
            "legacy_patch_plan_identity": None,
            "envelope_fingerprint": None,
            "unknown_keys": [],
            "authoritative_effect": False,
        }
    record = dict(payload)
    record.setdefault("schema_version", COMPATIBILITY_RECORD_SCHEMA_VERSION)
    record.setdefault("record_kind", PRODUCER_KIND)
    record.setdefault("phase_id", PHASE_ID)
    for key in (
        "strict_status",
        "provenance",
        "semantic_agreement",
        "strict_patch_plan_identity",
        "legacy_patch_plan_identity",
        "envelope_fingerprint",
    ):
        record.setdefault(key, None)
    record.setdefault("strict_available", False)
    record.setdefault("legacy_available", False)
    record.setdefault("unknown_keys", [])
    record["authoritative_effect"] = False
    return record


def summarize_worker_patch_envelope_records(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Tally how often current worker output already conforms.

    These are adoption counters.  Nothing here decides whether a patch was
    correct, and no count carries a confidence or a score.
    """
    by_status: dict[str, int] = {}
    by_provenance: dict[str, int] = {}
    strict_valid = 0
    legacy_only = 0
    invalid_both = 0
    mismatches = 0

    for raw in records:
        record = load_worker_patch_envelope_record(raw)
        status = record.get("strict_status")
        if isinstance(status, str):
            by_status[status] = by_status.get(status, 0) + 1
        provenance = record.get("provenance")
        if isinstance(provenance, str):
            by_provenance[provenance] = by_provenance.get(provenance, 0) + 1
        if record.get("strict_available") is True:
            strict_valid += 1
        elif record.get("legacy_available") is True:
            legacy_only += 1
        else:
            invalid_both += 1
        if record.get("semantic_agreement") == AGREEMENT_MISMATCH:
            mismatches += 1

    return {
        "schema_version": COMPATIBILITY_RECORD_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "records": len(records),
        "strict_valid_responses": strict_valid,
        "legacy_only_responses": legacy_only,
        "invalid_both_responses": invalid_both,
        "strict_legacy_mismatches": mismatches,
        "strict_status_counts": dict(sorted(by_status.items())),
        "provenance_counts": dict(sorted(by_provenance.items())),
        "authoritative_effect": False,
    }


def worker_patch_envelope_guardrails() -> dict[str, bool]:
    """Every power this contract and its strict parser decline."""
    return {
        "strict_one_object_protocol": True,
        "prose_parsed": False,
        "fenced_block_extracted": False,
        "balanced_brace_scanned": False,
        "first_object_selected": False,
        "regular_expression_used": False,
        "markdown_repaired": False,
        "output_truncated": False,
        "model_called": False,
        "model_repair_requested": False,
        "provider_sdk_imported": False,
        "network_call_performed": False,
        "repository_traversed": False,
        "source_content_read": False,
        "validation_executed": False,
        "patch_applied": False,
        "patch_semantics_changed": False,
        "patch_selection_changed": False,
        "files_modified": False,
        "authoritative_effect": False,
        "human_approval_required": True,
    }


__all__ = [
    "PHASE_ID",
    "PRODUCER_KIND",
    "WORKER_PATCH_ENVELOPE_SCHEMA_VERSION",
    "WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V1",
    "WORKER_PATCH_ENVELOPE_SCHEMA_VERSION_V2",
    "COMPATIBILITY_RECORD_SCHEMA_VERSION",
    "ENVELOPE_ARTIFACT_NAME",
    "ENVIRONMENT_FLAG",
    "MAX_ENVELOPE_RESPONSE_CHARS",
    "MAX_ENVELOPE_OPERATIONS",
    "MAX_INTENDED_CHANGES",
    "MAX_OPERATION_PAYLOAD_CHARS",
    "MAX_PATH_CHARS",
    "PARSE_STATUSES",
    "STATUS_VALID",
    "STATUS_INVALID_JSON",
    "STATUS_NON_OBJECT",
    "STATUS_UNKNOWN_FIELD",
    "STATUS_SCHEMA_INVALID",
    "STATUS_BOUND_EXCEEDED",
    "STATUS_SURROUNDING_PROSE_REJECTED",
    "STATUS_UNSUPPORTED_SCHEMA_VERSION",
    "PROVENANCE_VALUES",
    "PROVENANCE_STRICT",
    "PROVENANCE_LEGACY",
    "PROVENANCE_NONE",
    "AGREEMENT_VALUES",
    "AGREEMENT_AGREED",
    "AGREEMENT_MISMATCH",
    "AGREEMENT_NOT_COMPARABLE",
    "ALLOWED_ENVELOPE_KEYS",
    "ALLOWED_V2_ENVELOPE_KEYS",
    "ALLOWED_CHANGE_INTENT_KEYS",
    "ALLOWED_INTENDED_CHANGE_KEYS",
    "ALLOWED_OPERATION_KEYS",
    "FORBIDDEN_AUTHORITY_KEYS",
    "OPERATION_CREATE_FILE",
    "OPERATION_REPLACE_SNIPPET",
    "PRE_EXECUTION_INTENT_STAGE",
    "INTENDED_CHANGE_KINDS",
    "INTENT_CHANGE_ADDED",
    "INTENT_CHANGE_MODIFIED",
    "IntendedChange",
    "PreExecutionChangeIntent",
    "WorkerPatchEnvelope",
    "WorkerPatchEnvelopeParse",
    "WorkerPatchResponseCompatibility",
    "is_strict_worker_patch_envelope_shadow_enabled",
    "canonical_patch_operation_identity",
    "canonical_patch_plan_identity",
    "worker_patch_envelope_fingerprint",
    "parse_strict_worker_patch_envelope",
    "parse_strict_worker_patch_envelope_v2",
    "compare_strict_and_legacy",
    "safe_compare_strict_and_legacy",
    "load_worker_patch_envelope_record",
    "summarize_worker_patch_envelope_records",
    "worker_patch_envelope_guardrails",
]
