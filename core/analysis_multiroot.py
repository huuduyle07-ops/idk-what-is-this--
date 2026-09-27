"""ANALYSIS.MULTIROOT.LIVE.1 — explicit read-only multi-repository evidence.

The live T5 task asks one question this route could not answer:

    Compare this repository (deepseek-harness) against C.A.T.T.U.S, the Python
    agent harness located at ../C.A.T.T.U.S.

Every earlier phase honoured that request faithfully right up to acquisition and
then stopped, because evidence acquisition is scoped to one project root.  The
answer opened with a disclaimer that the second repository was inaccessible, and
the disclaimer was true: nothing in the system could read it.

This module closes exactly that gap and nothing wider.  A repository outside the
active project root becomes readable when — and only when — the *user* named it
as a subject of the task:

    explicit user request
        -> preserved Task Contract / obligations
        -> requested analysis root literal          [here]
        -> validated, canonicalized project root    [here]
        -> AnalysisReadScope: read yes, write no    [here]

What it deliberately is not
---------------------------
Not a workspace search, not an index federation, not graph merging, not
cross-repository symbol resolution and not a second authorization universe for
writes.  An accepted root grants ``evidence_read_allowed`` and nothing else:
``write_authority``, ``patch_application_authority`` and ``execution_authority``
are static ``False`` properties on the scope type, not fields a caller may set.

Bounds that do not move
-----------------------
The analysis budget stays *global*.  Two roots do not buy twenty-four files or
120,000 characters; they share the same twelve and the same 60,000, allocated
round-robin so the first repository cannot spend the whole budget before the
second one is considered.  The primary root's inventory is reused as-is, and an
accepted additional root costs **at most one** canonical membership traversal —
the same walk, the same ignore policy, the same generated/vendor exclusions.  No
graph is built for it, no index is written, no embedding is generated, no model
is called and no command is executed inside it.

Scope cannot grow from the inside.  A model draft that mentions a third
repository, a README that links to one and an import that points at one all
authorize nothing: root literals are read from the preserved user input and from
nowhere else, before a single provider call has been made.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

from core.analysis_evidence_roles import (
    MANIFEST_NAMES,
    PROJECT_DOCUMENT_NAMES,
    classify_evidence_role,
)


PHASE_ID = "ANALYSIS.MULTIROOT.LIVE.1"
MULTIROOT_SCHEMA_VERSION = "analysis_multiroot_live_1_v1"

# ── Bounds ────────────────────────────────────────────────────────────────────
#: Deliberately small.  This phase covers one comparison — the current root plus
#: at most one explicitly requested additional root.  A third requested root is
#: reported as an explicit overflow, never silently dropped and never silently
#: taken.
MAX_ANALYSIS_ROOTS = 2

#: How much preserved user text is scanned for root literals.  INPUT.PRESERVE
#: already bounds the obligation set well below this; the cap exists so the
#: scanner has a stated bound of its own rather than inheriting one.
MAX_ROOT_LITERAL_SCAN_CHARS = 20_000

#: How many distinct root-shaped literals may be *considered*.  Considering is
#: not accepting: everything past :data:`MAX_ANALYSIS_ROOTS` is rejected with an
#: explicit status, and this second cap only stops a pathological request from
#: producing an unbounded receipt.
MAX_ROOT_LITERAL_CANDIDATES = 8

#: Bound on the literal echoed back in telemetry.
MAX_ROOT_LITERAL_CHARS = 200

#: Ceiling on the relative-path list taken from any one root's inventory, so a
#: very large secondary repository cannot enlarge the selection input.
MAX_ROOT_INVENTORY_PATHS = 4_000


# ── Root roles and subject ordinals ───────────────────────────────────────────
ROOT_ROLE_PRIMARY = "primary"
ROOT_ROLE_ADDITIONAL = "additional"

ROOT_ROLES: tuple[str, ...] = (ROOT_ROLE_PRIMARY, ROOT_ROLE_ADDITIONAL)


# ── Closed root status vocabulary ─────────────────────────────────────────────
#: Statuses are facts about resolution, not confidences.  Every rejected root
#: carries one of these and a sentence built from constants.
ROOT_ACCEPTED = "accepted"
ROOT_NOT_EXPLICITLY_REQUESTED = "not_explicitly_requested"
ROOT_NOT_FOUND = "not_found"
ROOT_NOT_DIRECTORY = "not_directory"
ROOT_NOT_PROJECT_ROOT = "not_project_root"
ROOT_COUNT_EXCEEDED = "root_count_exceeded"
ROOT_CONTAINMENT_INVALID = "containment_invalid"
ROOT_REPOSITORY_IDENTITY_INVALID = "repository_identity_invalid"
ROOT_INVENTORY_UNAVAILABLE = "inventory_unavailable"
ROOT_DUPLICATE_OF_ACCEPTED = "duplicate_of_accepted_root"

ROOT_RESOLUTION_STATUSES: tuple[str, ...] = (
    ROOT_ACCEPTED,
    ROOT_NOT_EXPLICITLY_REQUESTED,
    ROOT_NOT_FOUND,
    ROOT_NOT_DIRECTORY,
    ROOT_NOT_PROJECT_ROOT,
    ROOT_COUNT_EXCEEDED,
    ROOT_CONTAINMENT_INVALID,
    ROOT_REPOSITORY_IDENTITY_INVALID,
    ROOT_INVENTORY_UNAVAILABLE,
    ROOT_DUPLICATE_OF_ACCEPTED,
)

# ── Containment statuses ──────────────────────────────────────────────────────
CONTAINMENT_BOUND = "bound_to_this_root"
CONTAINMENT_NOT_ESTABLISHED = "not_established"

CONTAINMENT_STATUSES: tuple[str, ...] = (
    CONTAINMENT_BOUND,
    CONTAINMENT_NOT_ESTABLISHED,
)

# ── Inventory statuses ────────────────────────────────────────────────────────
INVENTORY_REUSED_REQUEST_SCOPED = "reused_request_scoped"
INVENTORY_TRAVERSED_ONCE = "traversed_once"
INVENTORY_BOUNDED_LISTING = "bounded_listing_fallback"
INVENTORY_IDENTITY_MISMATCH = "repository_identity_mismatch"
INVENTORY_UNAVAILABLE = "unavailable"
INVENTORY_NOT_ATTEMPTED = "not_attempted"

INVENTORY_STATUSES: tuple[str, ...] = (
    INVENTORY_REUSED_REQUEST_SCOPED,
    INVENTORY_TRAVERSED_ONCE,
    INVENTORY_BOUNDED_LISTING,
    INVENTORY_IDENTITY_MISMATCH,
    INVENTORY_UNAVAILABLE,
    INVENTORY_NOT_ATTEMPTED,
)

# ── Root balance statuses ─────────────────────────────────────────────────────
BALANCE_SINGLE_ROOT = "single_root"
BALANCE_BALANCED = "every_accepted_root_represented"
BALANCE_PARTIAL = "accepted_root_without_evidence"
BALANCE_NO_EVIDENCE = "no_evidence_acquired"

#: What a run with no multi-root receipt at all is.  A historical artifact did
#: not fail multi-root; multi-root did not exist when it was written.
MULTIROOT_SINGLE_ROOT_LEGACY = "single_root_legacy"
MULTIROOT_ACTIVE = "multi_root"


# ── Root literal recognition ──────────────────────────────────────────────────
#: A root *candidate* is a path-shaped literal that names somewhere outside the
#: current project root: a ``..`` escape, a POSIX absolute path, a Windows drive
#: path or a home-relative path.  ``..`` is the trigger for candidacy, never the
#: denial criterion — T5 legitimately writes ``../C.A.T.T.U.S`` — and candidacy
#: is not acceptance: every candidate is resolved and validated below.
#:
#: The lookbehind keeps ordinary prose out.  "tool/plugin registration" has a
#: word character before its slash and never becomes a candidate; a sentence
#: that begins "/etc/passwd is..." does, and is then rejected on its merits.
_ROOT_LITERAL_BODY = r"[^\s\"'`,;:()\[\]{}<>|*?]+"
_ROOT_LITERAL_ALTERNATIVES = "|".join(
    (
        r"\.\.(?:[/\\]" + _ROOT_LITERAL_BODY + r")+",
        r"~[/\\]" + _ROOT_LITERAL_BODY,
        r"[A-Za-z]:[/\\]" + _ROOT_LITERAL_BODY,
        r"/(?!/)" + _ROOT_LITERAL_BODY,
    )
)
_ROOT_LITERAL_RE = re.compile(
    r"(?<![\w.\-])(" + _ROOT_LITERAL_ALTERNATIVES + r")"
)

#: Trailing characters a sentence leaves attached to a path.  ``../C.A.T.T.U.S.``
#: at the end of a clause is the repository plus the full stop that ended the
#: sentence, and the repository is what the user named.
_LITERAL_TRAILING = ".,;:!?)]}'\"`/\\"

#: Obviously-not-a-project locations, matched on the literal the user typed with
#: any drive letter removed.  Testing the *literal* rather than the canonical
#: path keeps the verdict identical on every platform: ``/etc/passwd`` is
#: refused on Windows, where it would otherwise canonicalize to ``C:/etc/passwd``
#: and merely not exist, exactly as it is refused on Linux, where it exists and
#: is a file.  This is a small static list, not a filesystem permission system.
_SYSTEM_PATH_PREFIXES: tuple[str, ...] = (
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib32",
    "/lib64",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/srv",
    "/sys",
    "/usr",
    "/windows",
    "/winnt",
    "/program files",
    "/program files (x86)",
    "/programdata",
    "/system32",
    "/system volume information",
    "/$recycle.bin",
)

#: What makes a directory a project root.  Reuses the manifest and document
#: vocabularies ANALYSIS.EVIDENCE already owns so there is one list, plus the
#: version-control marker.  Checked with one shallow directory listing; nothing
#: recursive happens here.
PROJECT_ROOT_MARKERS: frozenset[str] = frozenset(
    {".git", ".hg", ".svn", ".cattusignore"}
    | {name.casefold() for name in MANIFEST_NAMES}
    | {name.casefold() for name in PROJECT_DOCUMENT_NAMES if "/" not in name}
)


def _posix(value: str) -> str:
    return str(value or "").replace("\\", "/")


def _drive_stripped(value: str) -> str:
    """``C:/Windows`` -> ``/windows``; ``/etc/passwd`` -> ``/etc/passwd``."""
    text = _posix(value).casefold()
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        text = text[2:]
    return text or "/"


def is_system_path_literal(literal: str) -> bool:
    """Does this literal name an operating-system location rather than a project?"""
    text = _drive_stripped(literal).rstrip("/")
    if not text:
        return True
    for prefix in _SYSTEM_PATH_PREFIXES:
        if text == prefix or text.startswith(prefix + "/"):
            return True
    return False


def extract_requested_root_literals(
    *sources: Iterable[str] | str | None,
) -> tuple[str, ...]:
    """Root literals the user actually typed, in the order they typed them.

    ``sources`` are the already-frozen explicit-input structures — the preserved
    obligations, ExplicitEvidence's file paths, the task subjects.  Nothing else
    may be passed here: a model draft, a retrieved document and a final answer
    are not authoritative input, and a root the user never named cannot be
    granted by anything downstream of them.

    A literal that names a *file* is not a root.  ``src/index.ts`` and
    ``core/pipeline.py`` are requested paths, which the existing per-root
    selection already prioritises inside whichever repository contains them.
    """
    literals: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if source is None:
            continue
        values: Iterable[str]
        values = (source,) if isinstance(source, str) else source
        for value in values:
            text = str(value or "")[:MAX_ROOT_LITERAL_SCAN_CHARS]
            if not text:
                continue
            for match in _ROOT_LITERAL_RE.finditer(text):
                literal = match.group(1).rstrip(_LITERAL_TRAILING)
                if not literal or literal in {"..", "."}:
                    continue
                literal = literal[:MAX_ROOT_LITERAL_CHARS]
                # A path with a recognised evidence role is a file request, not
                # a repository root.  Same classifier the selection uses, so the
                # two cannot drift apart.
                if classify_evidence_role(_posix(literal).lstrip("./")) is not None:
                    continue
                key = _drive_stripped(literal).rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                literals.append(literal)
                if len(literals) >= MAX_ROOT_LITERAL_CANDIDATES:
                    return tuple(literals)
    return tuple(literals)


# ── Read scope ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AnalysisReadScope:
    """Permission to *read* one repository for analysis evidence. Nothing else.

    The three authority answers are properties, not fields.  A caller cannot
    construct a read scope that writes, patches or executes, and a later phase
    that wants any of those has to establish its own active project scope rather
    than reinterpreting this one.
    """

    repository_id: str
    canonical_root: str

    @property
    def evidence_read_allowed(self) -> bool:
        return True

    @property
    def write_authority(self) -> bool:
        """Always false.  Reading a repository is not permission to change it."""
        return False

    @property
    def patch_application_authority(self) -> bool:
        """Always false.  Applying remains CTX.APPLY's and human approval's."""
        return False

    @property
    def execution_authority(self) -> bool:
        """Always false.  No test, build or repository script runs under this."""
        return False

    @property
    def human_review_eligible(self) -> bool:
        """Always false.  A read scope produces no reviewable operation."""
        return False

    @property
    def approval_ready(self) -> bool:
        """Always false.  There is nothing here to approve."""
        return False

    def contains(self, candidate: str | os.PathLike[str]) -> bool:
        """Is ``candidate`` inside this root once symlinks are resolved?

        Containment is per root.  A relative path belonging to another accepted
        repository must never resolve through this one, and a link inside this
        repository that points outside it escapes nothing: the check runs on the
        canonical target, not on the spelling.
        """
        root = Path(self.canonical_root)
        try:
            target = Path(candidate).resolve()
            target.relative_to(root)
        except (OSError, ValueError, RuntimeError):
            return False
        return True

    def resolve_within(self, relative_path: str) -> Path | None:
        """Canonicalize a repository-relative path, or refuse it."""
        cleaned = _posix(relative_path).strip("/")
        if not cleaned or cleaned.startswith("../") or cleaned == "..":
            return None
        root = Path(self.canonical_root)
        try:
            target = (root / cleaned).resolve()
            target.relative_to(root)
        except (OSError, ValueError, RuntimeError):
            return None
        return target

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "evidence_read_allowed": self.evidence_read_allowed,
            "write_authority": self.write_authority,
            "patch_application_authority": self.patch_application_authority,
            "execution_authority": self.execution_authority,
            "human_review_eligible": self.human_review_eligible,
            "approval_ready": self.approval_ready,
        }


# ── Repository subject ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AnalysisRepositorySubject:
    """One task subject, the repository it resolved to, and what it cost.

    ``canonical_root`` is carried for the acquisition code that needs it and is
    deliberately absent from :meth:`as_dict`: user-facing telemetry in this
    project identifies a repository by display identity, not by an absolute
    filesystem path.
    """

    requested_root_literal: str
    subject_ordinal: int
    root_role: str
    resolution_status: str
    canonical_root: str = ""
    repository_id: str = ""
    repository_display: str = ""
    containment_status: str = CONTAINMENT_NOT_ESTABLISHED
    inventory_status: str = INVENTORY_NOT_ATTEMPTED
    inventory_file_count: int = 0
    traversal_count: int = 0
    validation_listing_count: int = 0
    evidence_selected: int = 0
    evidence_chars: int = 0
    rejection_reason: str = ""
    duplicate_of_ordinal: int | None = None
    read_scope: AnalysisReadScope | None = None
    unmet_role_requirements: tuple[str, ...] = ()
    inventory_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.root_role not in ROOT_ROLES:
            raise ValueError(f"unsupported analysis root role: {self.root_role!r}")
        if self.resolution_status not in ROOT_RESOLUTION_STATUSES:
            raise ValueError(
                f"unsupported analysis root status: {self.resolution_status!r}"
            )
        if self.containment_status not in CONTAINMENT_STATUSES:
            raise ValueError(
                f"unsupported containment status: {self.containment_status!r}"
            )
        if self.inventory_status not in INVENTORY_STATUSES:
            raise ValueError(
                f"unsupported inventory status: {self.inventory_status!r}"
            )
        if self.read_scope is not None and self.resolution_status != ROOT_ACCEPTED:
            raise ValueError("a read scope may exist only on an accepted root")

    @property
    def accepted(self) -> bool:
        return self.resolution_status == ROOT_ACCEPTED

    @property
    def read_scope_granted(self) -> bool:
        return self.accepted and self.read_scope is not None

    @property
    def is_primary(self) -> bool:
        return self.root_role == ROOT_ROLE_PRIMARY

    def display(self) -> str:
        return self.repository_display or self.requested_root_literal or "repository"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "requested_root_literal": self.requested_root_literal[
                :MAX_ROOT_LITERAL_CHARS
            ],
            "repository_id": self.repository_id,
            "repository_display": self.repository_display,
            "root_role": self.root_role,
            "subject_ordinal": self.subject_ordinal,
            "resolution_status": self.resolution_status,
            "read_scope_granted": self.read_scope_granted,
            "containment_status": self.containment_status,
            "inventory_status": self.inventory_status,
            "inventory_file_count": self.inventory_file_count,
            "traversal_count": self.traversal_count,
            "evidence_selected": self.evidence_selected,
            "evidence_chars": self.evidence_chars,
            "unmet_role_requirements": list(self.unmet_role_requirements),
            "rejection_reason": self.rejection_reason,
        }
        if self.duplicate_of_ordinal is not None:
            payload["duplicate_of_subject_ordinal"] = self.duplicate_of_ordinal
        if self.read_scope is not None:
            payload["read_scope"] = self.read_scope.as_dict()
        return payload


@dataclass(frozen=True, slots=True)
class MultiRootResolution:
    """Which repositories this analysis request may read, and which it may not."""

    subjects: tuple[AnalysisRepositorySubject, ...] = ()
    requested_repository_count: int = 0
    root_count_limit: int = MAX_ANALYSIS_ROOTS
    resolution_seconds: float = 0.0
    schema_version: str = MULTIROOT_SCHEMA_VERSION

    @property
    def accepted(self) -> tuple[AnalysisRepositorySubject, ...]:
        return tuple(subject for subject in self.subjects if subject.accepted)

    @property
    def accepted_repository_count(self) -> int:
        return len(self.accepted)

    @property
    def additional_requested(self) -> tuple[AnalysisRepositorySubject, ...]:
        return tuple(
            subject for subject in self.subjects if not subject.is_primary
        )

    @property
    def multi_root_requested(self) -> bool:
        """Did the user name a repository other than the active project root?"""
        return bool(self.additional_requested)

    @property
    def rejected(self) -> tuple[AnalysisRepositorySubject, ...]:
        return tuple(subject for subject in self.subjects if not subject.accepted)


# ── Resolution ────────────────────────────────────────────────────────────────

def _shallow_project_markers(root: Path) -> tuple[str, ...]:
    """One non-recursive listing: what does this directory declare itself to be?

    A directory listing is not a repository traversal.  It reads one level, it
    stops at the first sixteen markers it recognises, and it is counted and
    reported separately from the membership walk.
    """
    found: list[str] = []
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                name = entry.name.casefold()
                if name in PROJECT_ROOT_MARKERS:
                    found.append(name)
                    if len(found) >= 16:
                        break
    except OSError:
        return ()
    return tuple(sorted(found))


def _resolved_candidate(literal: str, primary_root: Path) -> Path:
    """Where a requested literal points, relative to the active project context."""
    candidate = Path(str(literal)).expanduser()
    if not candidate.is_absolute():
        candidate = primary_root / candidate
    try:
        return candidate.resolve()
    except (OSError, RuntimeError):
        return Path(os.path.abspath(str(candidate)))


def _identity_for(canonical_root: str) -> tuple[str, str]:
    from core.repository_identity import derive_repository_id_from_canonical_root

    repository_id = derive_repository_id_from_canonical_root(canonical_root)
    return repository_id, Path(canonical_root).name or repository_id


def _primary_subject(primary_root: str) -> AnalysisRepositorySubject:
    """Root #1 is the active project root, always, and is never re-derived.

    It keeps subject ordinal 0 and it is never given a second inventory: the
    request-scoped one production already built is the one it uses.
    """
    literal = str(primary_root or "")
    try:
        from core.repository_identity import canonicalize_repository_root

        canonical = canonicalize_repository_root(primary_root)
    except (NotADirectoryError, OSError, ValueError):
        return AnalysisRepositorySubject(
            requested_root_literal=literal[:MAX_ROOT_LITERAL_CHARS],
            subject_ordinal=0,
            root_role=ROOT_ROLE_PRIMARY,
            resolution_status=ROOT_NOT_FOUND,
            rejection_reason="The active project root could not be resolved.",
        )
    try:
        repository_id, display = _identity_for(canonical)
    except Exception:
        return AnalysisRepositorySubject(
            requested_root_literal=literal[:MAX_ROOT_LITERAL_CHARS],
            subject_ordinal=0,
            root_role=ROOT_ROLE_PRIMARY,
            resolution_status=ROOT_REPOSITORY_IDENTITY_INVALID,
            rejection_reason="No repository identity could be derived for the "
            "active project root.",
        )
    return AnalysisRepositorySubject(
        requested_root_literal=literal[:MAX_ROOT_LITERAL_CHARS],
        subject_ordinal=0,
        root_role=ROOT_ROLE_PRIMARY,
        resolution_status=ROOT_ACCEPTED,
        canonical_root=canonical,
        repository_id=repository_id,
        repository_display=display,
        containment_status=CONTAINMENT_BOUND,
        read_scope=AnalysisReadScope(
            repository_id=repository_id, canonical_root=canonical
        ),
    )


def _reject(
    literal: str,
    ordinal: int,
    status: str,
    reason: str,
    *,
    duplicate_of: int | None = None,
    validation_listing_count: int = 0,
) -> AnalysisRepositorySubject:
    return AnalysisRepositorySubject(
        requested_root_literal=str(literal)[:MAX_ROOT_LITERAL_CHARS],
        subject_ordinal=ordinal,
        root_role=ROOT_ROLE_ADDITIONAL,
        resolution_status=status,
        rejection_reason=reason,
        duplicate_of_ordinal=duplicate_of,
        validation_listing_count=validation_listing_count,
    )


def resolve_analysis_subjects(
    primary_root: str | None,
    *,
    obligations: Iterable[str] = (),
    requested_paths: Iterable[str] = (),
    subjects: Iterable[str] = (),
    max_roots: int = MAX_ANALYSIS_ROOTS,
) -> MultiRootResolution:
    """Decide which repositories this analysis request may read.

    The active project root is subject 0 and is always a subject.  Additional
    roots come only from the preserved user input passed in ``obligations``,
    ``requested_paths`` and ``subjects`` — every one of them an already-frozen
    explicit-input structure — and each is resolved, validated as a project
    root, given its own identity and its own containment boundary, or refused
    with an explicit status.
    """
    started = time.perf_counter()
    primary = _primary_subject(primary_root or "")
    resolved: list[AnalysisRepositorySubject] = [primary]

    literals = extract_requested_root_literals(obligations, requested_paths, subjects)
    if not literals or not primary.accepted:
        return MultiRootResolution(
            subjects=tuple(resolved),
            requested_repository_count=1 + len(literals),
            root_count_limit=max_roots,
            resolution_seconds=time.perf_counter() - started,
        )

    primary_key = os.path.normcase(os.path.normpath(primary.canonical_root))
    accepted_keys: dict[str, int] = {primary_key: 0}
    accepted_ids: dict[str, int] = {primary.repository_id: 0}
    primary_path = Path(primary.canonical_root)

    for index, literal in enumerate(literals, start=1):
        ordinal = index

        # 6/7. An explicit path is necessary, not sufficient.  Operating-system
        #      locations are refused before the filesystem is touched, so the
        #      /etc/passwd verdict is the same on every platform.
        if is_system_path_literal(literal):
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_NOT_PROJECT_ROOT,
                    "The requested subject names an operating-system location, "
                    "not a project repository.",
                )
            )
            continue

        candidate = _resolved_candidate(literal, primary_path)
        if candidate.parent == candidate:
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_NOT_PROJECT_ROOT,
                    "The requested subject resolves to a filesystem root.",
                )
            )
            continue
        if not candidate.exists():
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_NOT_FOUND,
                    "The requested repository does not exist at the location "
                    "the request named.",
                )
            )
            continue
        if not candidate.is_dir():
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_NOT_DIRECTORY,
                    "The requested subject is a file, not a repository root.",
                )
            )
            continue

        markers = _shallow_project_markers(candidate)
        if not markers:
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_NOT_PROJECT_ROOT,
                    "The requested directory declares no repository marker "
                    "(version control, package manifest or project document).",
                    validation_listing_count=1,
                )
            )
            continue

        try:
            from core.repository_identity import canonicalize_repository_root

            canonical = canonicalize_repository_root(str(candidate))
            repository_id, display = _identity_for(canonical)
        except Exception:
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_REPOSITORY_IDENTITY_INVALID,
                    "No repository identity could be derived for the requested "
                    "subject.",
                    validation_listing_count=1,
                )
            )
            continue

        # 50. Two literals for one repository are one evidence source.  The
        #     provenance of the second request is kept; the traversal is not
        #     repeated and the repository is not counted twice.
        key = os.path.normcase(os.path.normpath(canonical))
        duplicate_of = accepted_keys.get(key, accepted_ids.get(repository_id))
        if duplicate_of is not None:
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_DUPLICATE_OF_ACCEPTED,
                    "The requested subject resolves to a repository this "
                    "request already reads.",
                    duplicate_of=duplicate_of,
                    validation_listing_count=1,
                )
            )
            continue

        if len(accepted_keys) >= max(1, int(max_roots)):
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_COUNT_EXCEEDED,
                    f"This route reads at most {max(1, int(max_roots))} "
                    "repositories in one analysis request.",
                    validation_listing_count=1,
                )
            )
            continue

        scope = AnalysisReadScope(
            repository_id=repository_id, canonical_root=canonical
        )
        if not scope.contains(canonical):
            resolved.append(
                _reject(
                    literal,
                    ordinal,
                    ROOT_CONTAINMENT_INVALID,
                    "No containment boundary could be bound to the requested "
                    "repository root.",
                    validation_listing_count=1,
                )
            )
            continue

        accepted_keys[key] = ordinal
        accepted_ids[repository_id] = ordinal
        resolved.append(
            AnalysisRepositorySubject(
                requested_root_literal=str(literal)[:MAX_ROOT_LITERAL_CHARS],
                subject_ordinal=ordinal,
                root_role=ROOT_ROLE_ADDITIONAL,
                resolution_status=ROOT_ACCEPTED,
                canonical_root=canonical,
                repository_id=repository_id,
                repository_display=display,
                containment_status=CONTAINMENT_BOUND,
                validation_listing_count=1,
                read_scope=scope,
            )
        )

    return MultiRootResolution(
        subjects=tuple(resolved),
        requested_repository_count=1 + len(literals),
        root_count_limit=max_roots,
        resolution_seconds=time.perf_counter() - started,
    )


# ── Membership ────────────────────────────────────────────────────────────────

def _inventory_root(inventory: Any) -> str:
    root = getattr(inventory, "canonical_root", None)
    if not root:
        return ""
    try:
        return os.path.normcase(os.path.normpath(str(Path(str(root)).resolve())))
    except (OSError, RuntimeError):
        return os.path.normcase(os.path.normpath(str(root)))


def inventory_identity_matches(subject: AnalysisRepositorySubject, inventory: Any) -> bool:
    """Does a supplied inventory describe *this* repository?

    An inventory that does not declare a canonical root cannot be checked and is
    accepted as before; one that declares a different root is never merged.
    """
    declared = _inventory_root(inventory)
    if not declared:
        return True
    return declared == os.path.normcase(os.path.normpath(subject.canonical_root))


def _paths_from_inventory(inventory: Any) -> list[str]:
    entries = getattr(inventory, "indexable_entries", None)
    if not entries:
        return []
    return [
        Path(getattr(entry, "relative_path", "")).as_posix()
        for entry in list(entries)[:MAX_ROOT_INVENTORY_PATHS]
    ]


def acquire_subject_membership(
    subject: AnalysisRepositorySubject,
    *,
    inventory: Any = None,
) -> tuple[AnalysisRepositorySubject, list[str]]:
    """Repository membership for one accepted root, at most one walk.

    The primary root reuses whatever production already built and adds zero
    traversals.  An accepted additional root has no such inventory — that is the
    entire reason it was previously unreadable — so it gets exactly one
    canonical membership traversal, through the same walker, the same ignore
    policy and the same generated/vendor exclusions as any other repository.
    No graph is built, no index is written and no embedding is generated.
    """
    if not subject.read_scope_granted:
        return subject, []

    started = time.perf_counter()
    if inventory is not None:
        if not inventory_identity_matches(subject, inventory):
            # 51. Cached evidence claiming another identity is never merged into
            #     this one; the affected root fails conservatively instead.
            return (
                replace(
                    subject,
                    resolution_status=ROOT_REPOSITORY_IDENTITY_INVALID,
                    read_scope=None,
                    containment_status=CONTAINMENT_NOT_ESTABLISHED,
                    inventory_status=INVENTORY_IDENTITY_MISMATCH,
                    rejection_reason="The supplied repository inventory claims a "
                    "different repository identity than the resolved root.",
                    inventory_seconds=time.perf_counter() - started,
                ),
                [],
            )
        paths = _paths_from_inventory(inventory)
        return (
            replace(
                subject,
                inventory_status=INVENTORY_REUSED_REQUEST_SCOPED,
                inventory_file_count=len(paths),
                traversal_count=0,
                inventory_seconds=time.perf_counter() - started,
            ),
            paths,
        )

    try:
        from core.repository_inventory import create_repository_inventory

        built = create_repository_inventory(subject.canonical_root)
    except Exception:
        return (
            replace(
                subject,
                resolution_status=ROOT_INVENTORY_UNAVAILABLE,
                read_scope=None,
                containment_status=CONTAINMENT_NOT_ESTABLISHED,
                inventory_status=INVENTORY_UNAVAILABLE,
                rejection_reason="Repository membership could not be established "
                "for the requested repository.",
                inventory_seconds=time.perf_counter() - started,
            ),
            [],
        )
    paths = _paths_from_inventory(built)
    return (
        replace(
            subject,
            inventory_status=INVENTORY_TRAVERSED_ONCE,
            inventory_file_count=len(paths),
            traversal_count=int(getattr(built, "traversal_count", 1) or 1),
            inventory_seconds=time.perf_counter() - started,
        ),
        paths,
    )


# ── Root-balanced allocation ──────────────────────────────────────────────────

def allocate_root_balanced_selections(
    per_root: Sequence[tuple[int, Sequence[tuple[str, str]]]],
    *,
    max_files: int,
    requested_role: str,
) -> tuple[tuple[int, str, str], ...]:
    """Divide one global file budget across roots, without multiplying it.

    ``per_root`` is ``(subject_ordinal, [(relative_path, role), ...])`` in the
    subject order the preserved task established — never alphabetised, never
    reordered by size.  Each inner sequence is that root's own role-balanced
    reading order, which this function only ever takes a *prefix* of, so the
    within-root role reservation survives being given fewer slots.

    Two rules, in order:

    1. Files the user named exactly are taken first, in every root that has
       them.  Generic balancing never evicts an explicitly requested path.
    2. Everything else is taken one file at a time, rotating between roots.
       Rotation is what makes the floor availability-aware without a quota: a
       root with nothing left simply stops being offered a turn, and its unused
       slots go to the roots that can fill them.
    """
    budget = max(0, int(max_files))
    out: list[tuple[int, str, str]] = []
    pools: list[tuple[int, list[tuple[str, str]]]] = [
        (ordinal, list(selections)) for ordinal, selections in per_root
    ]

    for ordinal, pool in pools:
        remaining: list[tuple[str, str]] = []
        for path, role in pool:
            if role == requested_role and len(out) < budget:
                out.append((ordinal, path, role))
            else:
                remaining.append((path, role))
        pool[:] = remaining

    while len(out) < budget:
        progressed = False
        for ordinal, pool in pools:
            if len(out) >= budget:
                break
            if not pool:
                continue
            path, role = pool.pop(0)
            out.append((ordinal, path, role))
            progressed = True
        if not progressed:
            break
    return tuple(out[:budget])


# ── Receipt ───────────────────────────────────────────────────────────────────

def root_balance_status(
    subjects: Sequence[AnalysisRepositorySubject],
) -> str:
    accepted = [subject for subject in subjects if subject.accepted]
    if not accepted:
        return BALANCE_NO_EVIDENCE
    if not any(subject.evidence_selected for subject in accepted):
        return BALANCE_NO_EVIDENCE
    if len(accepted) == 1:
        return BALANCE_SINGLE_ROOT
    if all(subject.evidence_selected > 0 for subject in accepted):
        return BALANCE_BALANCED
    return BALANCE_PARTIAL


def multiroot_receipt(
    resolution: MultiRootResolution,
    subjects: Sequence[AnalysisRepositorySubject],
    *,
    files_selected: int,
    chars_selected: int,
    budget_exhausted: bool,
    max_files: int,
    max_chars: int,
    selection_seconds: float = 0.0,
    acquisition_seconds: float = 0.0,
) -> dict[str, Any]:
    """Bounded facts about a multi-repository acquisition.

    Counts, statuses and display identities.  No source, no absolute paths, no
    confidence and no authority: nothing in this receipt can widen what the run
    is allowed to do.
    """
    ordered = list(subjects)
    accepted = [subject for subject in ordered if subject.accepted]
    return {
        "schema_version": MULTIROOT_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "status": MULTIROOT_ACTIVE,
        "requested_repository_count": resolution.requested_repository_count,
        "accepted_repository_count": len(accepted),
        "root_count_limit": resolution.root_count_limit,
        "repositories": [subject.as_dict() for subject in ordered],
        "global_files_selected": int(files_selected),
        "global_chars_selected": int(chars_selected),
        "global_bounds": {
            "max_files": int(max_files),
            "max_total_chars": int(max_chars),
            "per_root_multiplication": False,
        },
        "budget_exhausted": bool(budget_exhausted),
        "root_balance_status": root_balance_status(ordered),
        "selected_files_by_repository": {
            subject.repository_id: subject.evidence_selected for subject in accepted
        },
        "selected_chars_by_repository": {
            subject.repository_id: subject.evidence_chars for subject in accepted
        },
        "unmet_role_requirements_by_repository": {
            subject.repository_id: list(subject.unmet_role_requirements)
            for subject in accepted
        },
        "membership_traversals_added": sum(
            subject.traversal_count for subject in ordered
        ),
        "validation_listings": sum(
            subject.validation_listing_count for subject in ordered
        ),
        "authority": {
            "evidence_read_allowed": True,
            "write_authority": False,
            "patch_application_authority": False,
            "execution_authority": False,
            "human_review_eligible": False,
            "approval_ready": False,
        },
        "performance": {
            "root_resolution_seconds": round(resolution.resolution_seconds, 4),
            "membership_seconds_by_repository": {
                subject.repository_id or subject.requested_root_literal: round(
                    subject.inventory_seconds, 4
                )
                for subject in ordered
                if subject.inventory_seconds
            },
            "selection_seconds": round(float(selection_seconds), 4),
            "acquisition_seconds": round(float(acquisition_seconds), 4),
        },
        "note": (
            "Read-only evidence from explicitly requested repository roots. No "
            "index, no program graph, no embedding, no extra model call and no "
            "write, patch or execution authority was created here."
        ),
    }


def single_root_legacy_receipt() -> dict[str, Any]:
    """What a run that never requested a second repository reports."""
    return {
        "schema_version": MULTIROOT_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "status": MULTIROOT_SINGLE_ROOT_LEGACY,
        "requested_repository_count": 1,
        "accepted_repository_count": 1,
    }


__all__ = [
    "BALANCE_BALANCED",
    "BALANCE_NO_EVIDENCE",
    "BALANCE_PARTIAL",
    "BALANCE_SINGLE_ROOT",
    "CONTAINMENT_BOUND",
    "CONTAINMENT_NOT_ESTABLISHED",
    "CONTAINMENT_STATUSES",
    "INVENTORY_BOUNDED_LISTING",
    "INVENTORY_IDENTITY_MISMATCH",
    "INVENTORY_NOT_ATTEMPTED",
    "INVENTORY_REUSED_REQUEST_SCOPED",
    "INVENTORY_STATUSES",
    "INVENTORY_TRAVERSED_ONCE",
    "INVENTORY_UNAVAILABLE",
    "MAX_ANALYSIS_ROOTS",
    "MAX_ROOT_INVENTORY_PATHS",
    "MAX_ROOT_LITERAL_CANDIDATES",
    "MAX_ROOT_LITERAL_CHARS",
    "MAX_ROOT_LITERAL_SCAN_CHARS",
    "MULTIROOT_ACTIVE",
    "MULTIROOT_SCHEMA_VERSION",
    "MULTIROOT_SINGLE_ROOT_LEGACY",
    "PHASE_ID",
    "PROJECT_ROOT_MARKERS",
    "ROOT_ACCEPTED",
    "ROOT_CONTAINMENT_INVALID",
    "ROOT_COUNT_EXCEEDED",
    "ROOT_DUPLICATE_OF_ACCEPTED",
    "ROOT_INVENTORY_UNAVAILABLE",
    "ROOT_NOT_DIRECTORY",
    "ROOT_NOT_EXPLICITLY_REQUESTED",
    "ROOT_NOT_FOUND",
    "ROOT_NOT_PROJECT_ROOT",
    "ROOT_REPOSITORY_IDENTITY_INVALID",
    "ROOT_RESOLUTION_STATUSES",
    "ROOT_ROLES",
    "ROOT_ROLE_ADDITIONAL",
    "ROOT_ROLE_PRIMARY",
    "AnalysisReadScope",
    "AnalysisRepositorySubject",
    "MultiRootResolution",
    "acquire_subject_membership",
    "allocate_root_balanced_selections",
    "extract_requested_root_literals",
    "inventory_identity_matches",
    "is_system_path_literal",
    "multiroot_receipt",
    "resolve_analysis_subjects",
    "root_balance_status",
    "single_root_legacy_receipt",
]
