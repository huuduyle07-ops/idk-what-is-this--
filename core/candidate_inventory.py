"""ACQUIRE.2 — the authorized candidate inventory ACQUIRE.2 consumes.

ACQUIRE.2 does not discover what a repository contains.  Somebody who already
holds traversal authority does that, and hands the answer over:

    canonical / authorized inventory snapshot
        -> CandidateInventory
        -> ACQUIRE.2

and never the other way around.  Nothing here walks a directory tree, opens a
file, refreshes a manifest or reads an ignore file.  If a repository request
arrives with no inventory, the phase fails closed rather than going to look for
one.

**This is a narrow adapter, not a second inventory.**  The field names mirror
:class:`core.file_capabilities.FileCapability` exactly, so a member converts to
the mapping CTX.SELECT's supplied-metadata entry points already accept, and back
again.  ACQUIRE.2 declines to *import* that module because its import graph
reaches ``pathspec``, the ignore-file reader and the repository walker — a
dependency this line of phases has never had and must not acquire in order to
describe candidates.  The compatibility is proved by test instead of by import.

**A member is metadata, never content.**  Size, parser support, read policy,
generated and vendor markers and an optionally declared source class: all of it
established upstream by somebody entitled to establish it.  Nothing here needs
the bytes of a file, an AST, an embedding, a graph or a database.

The module is stdlib-only and pure.  It reads no files, walks no directory,
contacts no service, calls no language system, and grants no authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from core.acquisition_request import (
    ACQUISITION_SOURCE_CLASSES,
    NEVER_REQUESTED_SOURCE_CLASSES,
)
from core.repository_path_policy import is_safe_repository_relative_path


PHASE_ID = "ACQUIRE.2"
CANDIDATE_INVENTORY_SCHEMA_VERSION = "acquire_2_candidate_inventory_v1"

# ── Capability states, mirrored from CTX.SELECT.1 ─────────────────────────────
#: Copied deliberately rather than imported, and asserted equal to the CTX.SELECT
#: vocabularies by test.  A member carrying one of these values converts to a
#: ``FileCapability`` mapping without translation.
PARSER_SUPPORT_STATES: tuple[str, ...] = (
    "supported",
    "partial",
    "unsupported",
    "not_applicable",
)

READ_POLICY_STATES: tuple[str, ...] = (
    "auto_read_allowed",
    "explicit_human_approval_required",
    "hard_no_auto_read",
)

#: Parser support that means "the canonical parser understands this as code".
#: It is a statement about the *kind* of file, not about its relevance and not
#: about whether anything was parsed here — nothing was.
CODE_PARSER_SUPPORT: frozenset[str] = frozenset({"supported", "partial"})

# ── Bounds ────────────────────────────────────────────────────────────────────
#: Generous, because a real repository is large and refusing to describe one
#: would just push the traversal somewhere less careful.  Bounded, because an
#: unbounded input is how six thousand files became one bucket.
MAX_INVENTORY_MEMBERS = 100_000
MAX_IDENTIFIER_LENGTH = 1_024


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def is_acceptable_identifier(value: str) -> bool:
    """Is this a portable repository-relative identifier ACQUIRE.2 will accept?

    The shared canonical policy does the work.  One extra rejection is added on
    top of it: an identifier that begins with a separator is refused outright,
    because the shared helper is lexical and, on a platform whose paths are not
    rooted at ``/``, a leading slash does not read as absolute to it.  ACQUIRE.2
    would rather refuse a path it cannot vouch for than accept one whose meaning
    depends on which machine is asking.

    Membership, not shape, is the real gate — see :meth:`CandidateInventory.member`.
    """
    if not isinstance(value, str) or not value or len(value) > MAX_IDENTIFIER_LENGTH:
        return False
    if value.startswith("/") or value.startswith("\\"):
        return False
    return is_safe_repository_relative_path(value)


@dataclass(frozen=True, slots=True)
class InventoryMember:
    """One member of an already-authorized inventory snapshot.

    Every field is metadata somebody upstream established.  ACQUIRE.2 derives
    none of it, verifies none of it against a filesystem, and adds none of its
    own: what it does not know, it records as unknown.
    """

    identifier: str
    size_bytes: int | None = None
    parser_support: str = "not_applicable"
    read_policy: str = "auto_read_allowed"
    repository_contained: bool = True
    symlink_escape: bool = False
    generated: bool = False
    vendor: bool = False
    #: A source class an authorized inventory builder asserted for this member.
    #: The only route to a class no location or filename can honestly imply —
    #: interface definitions, authoritative architecture description and
    #: registration surfaces among them.
    declared_source_class: str | None = None
    #: Set when this member restates another: a translated README, a rendered
    #: copy.  It names the member it duplicates, and makes this one excludable.
    duplicate_of: str | None = None

    def __post_init__(self) -> None:
        if not is_acceptable_identifier(self.identifier):
            raise ValueError(f"unusable inventory identifier: {self.identifier!r}")
        if self.parser_support not in PARSER_SUPPORT_STATES:
            raise ValueError(f"unknown parser-support state: {self.parser_support!r}")
        if self.read_policy not in READ_POLICY_STATES:
            raise ValueError(f"unknown read-policy state: {self.read_policy!r}")
        if self.size_bytes is not None:
            if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
                raise TypeError("size_bytes must be an integer or None")
            if self.size_bytes < 0:
                raise ValueError("size_bytes must be non-negative or None")
        for name in ("repository_contained", "symlink_escape", "generated", "vendor"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.declared_source_class is not None:
            if self.declared_source_class not in ACQUISITION_SOURCE_CLASSES:
                raise ValueError(
                    f"unsupported declared source class: {self.declared_source_class!r}"
                )
        if self.duplicate_of is not None and not is_acceptable_identifier(self.duplicate_of):
            raise ValueError(f"unusable duplicate identifier: {self.duplicate_of!r}")

    @property
    def size_known(self) -> bool:
        return self.size_bytes is not None

    @property
    def is_code(self) -> bool:
        """Does the canonical parser treat this member as code?

        A statement about the kind of file, established upstream.  It is not a
        claim that the file is relevant, current, correct, or that one byte of
        it has been looked at.
        """
        return self.parser_support in CODE_PARSER_SUPPORT

    @property
    def hard_excluded(self) -> bool:
        return self.read_policy == "hard_no_auto_read"

    @property
    def restates_another_member(self) -> bool:
        return self.duplicate_of is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "size_bytes": self.size_bytes,
            "parser_support": self.parser_support,
            "read_policy": self.read_policy,
            "repository_contained": self.repository_contained,
            "symlink_escape": self.symlink_escape,
            "generated": self.generated,
            "vendor": self.vendor,
            "declared_source_class": self.declared_source_class,
            "duplicate_of": self.duplicate_of,
        }

    def as_capability_mapping(self) -> dict[str, Any]:
        """The same member, in the shape CTX.SELECT's entry points accept.

        ``build_candidate_filename_report`` and ``rank_candidates`` both take
        ``FileCapability`` values *or mappings*, and classify supplied metadata
        without touching a filesystem.  This is the bridge: no translation
        table, no second vocabulary, no import.
        """
        return {
            "path": self.identifier,
            "size_bytes": self.size_bytes,
            "parser_support": self.parser_support,
            "repository_contained": self.repository_contained,
            "symlink_escape": self.symlink_escape,
            "generated": self.generated,
            "vendor": self.vendor,
        }

    @classmethod
    def from_capability_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        declared_source_class: str | None = None,
        duplicate_of: str | None = None,
    ) -> "InventoryMember":
        """Ingest one ``FileCapability.as_dict()`` without importing its module.

        Duck-typed on purpose.  A caller that *does* hold the CTX.SELECT stack
        can hand its records straight over; a caller that does not is not forced
        to acquire ``pathspec`` and a repository walker in order to describe a
        candidate.
        """
        if not isinstance(payload, Mapping):
            raise TypeError("from_capability_mapping requires a mapping")
        identifier = payload.get("path", payload.get("identifier"))
        if not isinstance(identifier, str):
            raise TypeError("a capability mapping must name its path")
        return cls(
            identifier=identifier,
            size_bytes=payload.get("size_bytes"),
            parser_support=str(payload.get("parser_support", "not_applicable")),
            read_policy=str(payload.get("read_policy", "auto_read_allowed")),
            repository_contained=bool(payload.get("repository_contained", True)),
            symlink_escape=bool(payload.get("symlink_escape", False)),
            generated=bool(payload.get("generated", False)),
            vendor=bool(payload.get("vendor", False)),
            declared_source_class=declared_source_class,
            duplicate_of=duplicate_of,
        )


@dataclass(frozen=True, slots=True)
class CandidateInventory:
    """One immutable snapshot of what a repository was already known to contain.

    ACQUIRE.2 treats this as the *whole* truth about membership.  A path that is
    not here does not exist as far as this phase is concerned, however plausible
    it looks and however explicitly the user named it.
    """

    repository_identity: str
    members: tuple[InventoryMember, ...] = ()
    #: The identity of the snapshot itself, as recorded by whoever built it.
    #: Supplied for comparison; ACQUIRE.2 re-derives its own and binds to that.
    declared_fingerprint: str | None = None
    schema_version: str = CANDIDATE_INVENTORY_SCHEMA_VERSION
    _by_identifier: dict[str, InventoryMember] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.repository_identity, str) or not self.repository_identity:
            raise ValueError("an inventory must name the repository it describes")
        if len(self.members) > MAX_INVENTORY_MEMBERS:
            raise ValueError("inventory members exceed the supported bound")
        index: dict[str, InventoryMember] = {}
        for member in self.members:
            if not isinstance(member, InventoryMember):
                raise TypeError("inventory members must be InventoryMember values")
            key = member.identifier.casefold()
            if key in index:
                raise ValueError(
                    f"inventory contains duplicate identifier: {member.identifier!r}"
                )
            index[key] = member
        object.__setattr__(self, "_by_identifier", index)

    def __len__(self) -> int:
        return len(self.members)

    def __contains__(self, identifier: object) -> bool:
        return isinstance(identifier, str) and identifier.casefold() in self._by_identifier

    def member(self, identifier: str) -> InventoryMember | None:
        """The member with this identifier, or ``None``.

        The only door into the candidate pool.  Nothing enters because it
        resembles a valid path; it enters because the authorized snapshot says
        it is there.
        """
        if not isinstance(identifier, str):
            return None
        return self._by_identifier.get(identifier.casefold())

    def identifiers(self) -> tuple[str, ...]:
        return tuple(member.identifier for member in self.members)

    def fingerprint(self) -> str:
        """The snapshot's identity, re-derived rather than believed."""
        return _fingerprint(
            {
                "schema_version": self.schema_version,
                "repository_identity": self.repository_identity,
                "members": [member.as_dict() for member in self.members],
            }
        )

    def declared_fingerprint_matches(self) -> bool:
        """Does the builder's claim about this snapshot survive re-derivation?"""
        if self.declared_fingerprint is None:
            return True
        return self.declared_fingerprint == self.fingerprint()

    def as_capability_mappings(self) -> tuple[dict[str, Any], ...]:
        """Every member in CTX.SELECT's supplied-metadata shape."""
        return tuple(member.as_capability_mapping() for member in self.members)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "repository_identity": self.repository_identity,
            "member_count": len(self.members),
            "fingerprint": self.fingerprint(),
            "declared_fingerprint": self.declared_fingerprint,
            "note": (
                "An inventory snapshot supplied to ACQUIRE.2. It was not built here, "
                "no directory was walked to produce it, and no member's content was "
                "read."
            ),
        }


def inventory_from_capability_mappings(
    repository_identity: str,
    payloads: tuple[Mapping[str, Any], ...],
    *,
    declared_source_classes: Mapping[str, str] | None = None,
    duplicates: Mapping[str, str] | None = None,
    declared_fingerprint: str | None = None,
) -> CandidateInventory:
    """Build one inventory from supplied CTX.SELECT-shaped capability mappings.

    The bridge in the inbound direction, so a caller already holding
    ``FileCapability`` records does not have to restate them by hand.  Members
    whose identifier ACQUIRE.2 will not vouch for are refused, not silently
    dropped: an inventory that half-arrives is worse than one that does not.
    """
    declared = dict(declared_source_classes or {})
    restates = dict(duplicates or {})
    members = tuple(
        InventoryMember.from_capability_mapping(
            payload,
            declared_source_class=declared.get(str(payload.get("path", ""))),
            duplicate_of=restates.get(str(payload.get("path", ""))),
        )
        for payload in payloads
    )
    return CandidateInventory(
        repository_identity=repository_identity,
        members=members,
        declared_fingerprint=declared_fingerprint,
    )


__all__ = [
    "CANDIDATE_INVENTORY_SCHEMA_VERSION",
    "CODE_PARSER_SUPPORT",
    "MAX_IDENTIFIER_LENGTH",
    "MAX_INVENTORY_MEMBERS",
    "NEVER_REQUESTED_SOURCE_CLASSES",
    "PARSER_SUPPORT_STATES",
    "PHASE_ID",
    "READ_POLICY_STATES",
    "CandidateInventory",
    "InventoryMember",
    "inventory_from_capability_mappings",
    "is_acceptable_identifier",
]
