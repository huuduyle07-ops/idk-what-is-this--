"""WAITER.LIVE.1 — bounded repository evidence for the analysis route.

An architecture question needs to read the repository.  It does not need a call
graph, a ranked patch target or an exact replacement snippet, and the field test
proved what happens when it is handed those instead: twenty-six minutes of
indexing, an unrelated test file ranked first, and an answer that echoed the
question back.

So the analysis route acquires a different kind of evidence:

    RepositoryInventory  (already computed, no graph, no index)
        -> deterministic document selection      [here]
        -> bounded excerpts                      [here]
        -> a user-readable answer prompt         [here]

The selection is deliberately dull.  It is a fixed priority order over paths —
what the user named, then the documents a repository writes about itself, then
its manifests, then its canonical entry points — with hard caps on how many
files and how many characters may be read.  There is no ranking model, no
embedding, no scoring and no traversal beyond the inventory that production had
already built before this module was called.

This is not retrieval.  Choosing *better* documents for a large repository is a
separate, known, unsolved problem; this phase's invariant is only that an
analysis question stops becoming a patch-target search.  When the evidence is
thin the prompt says so and asks the answer to declare the gap, which is the
honest failure and the one the previous path could not produce.

ANALYSIS.EVIDENCE.LIVE.1 kept every one of those bounds and replaced the fixed
priority order with a role-balanced one.  The measured reason is recorded in
:mod:`core.analysis_evidence_roles`: on a real monorepo the fixed order spent
the whole 60,000-character budget on markdown before implementation code was
ever considered, so an architecture question was answered from documentation
alone while 2,700 supported TypeScript files sat unread in the same inventory.
The caps did not move.  What moved is that the budget is now divided across
evidence roles — implementation source, project documentation, package
manifests, tests and examples — with a per-role minimum reserved before the
character budget can be spent, and the profile that decides those minimums read
off the words the user actually wrote.

ANALYSIS.MULTIROOT.LIVE.1 added a second repository to that picture and nothing
else.  When an ``analysis_only`` request explicitly names another project root —
"compare this repository against ../C.A.T.T.U.S" — that root is resolved,
validated, given its own identity and its own containment boundary, and read
under the *same* global budget: twelve files and 60,000 characters shared across
both repositories, not doubled.  Everything above still holds per root, and the
selection order between roots is a rotation, so the first repository cannot
spend the whole budget before the second one is considered.  The gate is the
user's own words; a repository nobody asked for stays unreadable.

The module reads files inside the repository roots the request established and
nothing else.  It calls no model, contacts no service, builds no graph, writes
nothing, and grants no authority.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.analysis_multiroot import (
    INVENTORY_BOUNDED_LISTING,
    MULTIROOT_SINGLE_ROOT_LEGACY,
    AnalysisRepositorySubject,
    MultiRootResolution,
    acquire_subject_membership,
    allocate_root_balanced_selections,
    multiroot_receipt,
    resolve_analysis_subjects,
    single_root_legacy_receipt,
)
from core.analysis_evidence_roles import (
    ANALYSIS_EVIDENCE_PROFILES,
    BALANCED_ROLES,
    EVIDENCE_ROLES,
    PROFILE_ARCHITECTURE_IMPLEMENTATION,
    PROFILE_DEPENDENCY_CONFIGURATION,
    PROFILE_DOCUMENTATION_EXPLANATION,
    PROFILE_GENERAL_ANALYSIS,
    PROFILE_IMPLEMENTATION_DETAIL,
    ROLE_ENTRY_POINT,
    ROLE_IMPLEMENTATION_SOURCE,
    ROLE_PACKAGE_MANIFEST,
    ROLE_PROJECT_DOCUMENT,
    ROLE_REQUESTED_PATH,
    ROLE_REQUESTED_SUBJECT,
    ROLE_TEST_EXAMPLE,
    AnalysisSelectionPlan,
    derive_evidence_profile,
    plan_analysis_evidence,
    profile_requires_source,
)


PHASE_ID = "WAITER.LIVE.1"
ROLE_BALANCE_PHASE_ID = "ANALYSIS.EVIDENCE.LIVE.1"
MULTIROOT_PHASE_ID = "ANALYSIS.MULTIROOT.LIVE.1"
ANALYSIS_EVIDENCE_SCHEMA_VERSION = "waiter_live_1_analysis_evidence_v1"

# ── Bounds ────────────────────────────────────────────────────────────────────
#: Small on purpose.  An analysis route that reads the whole repository has
#: simply moved the twenty-six minutes somewhere else.
MAX_EVIDENCE_FILES = 12
MAX_CHARS_PER_FILE = 6_000
MAX_TOTAL_CHARS = 60_000
MAX_INVENTORY_SCAN = 4_000

# ── Evidence roles ────────────────────────────────────────────────────────────
#: The role vocabulary, the path tables and the balancing policy all live in
#: :mod:`core.analysis_evidence_roles` and are re-exported here so every existing
#: importer of this module keeps working unchanged.


@dataclass(frozen=True, slots=True)
class AnalysisEvidenceItem:
    """One bounded excerpt, and why it was read."""

    path: str
    role: str
    text: str
    truncated: bool = False
    # ANALYSIS.MULTIROOT.LIVE.1 — which repository this excerpt came from.  Empty
    # on a single-root run, where "the repository" is unambiguous; carried on
    # every multi-root item, because two repositories can both hold src/index.ts
    # and a citation that says only "src/index.ts" names neither of them.
    repository_id: str = ""
    repository_display: str = ""

    def __post_init__(self) -> None:
        if self.role not in EVIDENCE_ROLES:
            raise ValueError(f"unsupported analysis evidence role: {self.role!r}")

    @property
    def citation(self) -> str:
        """How this file must be named where more than one repository was read.

        ``repository::path`` is not a syntax invented here: it is the
        repository-qualified reference grammar ANSWER.GROUND.LIVE.1 already
        parses, so a citation written this way lands in the right repository's
        symbol universe instead of being attributed by guesswork.
        """
        if self.repository_display:
            return f"{self.repository_display}::{self.path}"
        return self.path

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "role": self.role,
            "chars": len(self.text),
            "truncated": self.truncated,
        }
        if self.repository_id:
            payload["repository_id"] = self.repository_id
            payload["repository_display"] = self.repository_display
        return payload


@dataclass(frozen=True, slots=True)
class AnalysisEvidence:
    """Everything the analysis route actually read, and what it could not.

    ``gaps`` matters as much as ``items``.  An answer bounded by evidence has to
    be able to say what it did not see, and a route that cannot report a gap can
    only hide one.
    """

    items: tuple[AnalysisEvidenceItem, ...] = ()
    gaps: tuple[str, ...] = ()
    inventory_file_count: int = 0
    schema_version: str = ANALYSIS_EVIDENCE_SCHEMA_VERSION
    # ANALYSIS.EVIDENCE.LIVE.1 — how the bounded budget was divided.  Every
    # field is a count, a role name or a sentence built from constants; none is
    # a confidence, a score or a fragment of source.
    profile: str = PROFILE_GENERAL_ANALYSIS
    available_by_role: tuple[tuple[str, int], ...] = ()
    required_by_role: tuple[tuple[str, int], ...] = ()
    unmet_role_requirements: tuple[str, ...] = ()
    selection_reason: str = ""
    # ANALYSIS.MULTIROOT.LIVE.1 — the repository subjects this request was
    # allowed to read, accepted and rejected alike.  Empty on a single-root run.
    repositories: tuple[AnalysisRepositorySubject, ...] = ()
    multi_root: Mapping[str, Any] | None = None

    @property
    def is_empty(self) -> bool:
        return not self.items

    # ── multi-root views ─────────────────────────────────────────────────────
    @property
    def is_multi_root(self) -> bool:
        """Did more than one repository subject reach acquisition?"""
        return len(self.accepted_repositories) > 1

    @property
    def accepted_repositories(self) -> tuple[AnalysisRepositorySubject, ...]:
        return tuple(subject for subject in self.repositories if subject.accepted)

    @property
    def rejected_repositories(self) -> tuple[AnalysisRepositorySubject, ...]:
        return tuple(subject for subject in self.repositories if not subject.accepted)

    def files_by_repository(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            key = item.repository_id or ""
            counts[key] = counts.get(key, 0) + 1
        return counts

    def chars_by_repository(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            key = item.repository_id or ""
            counts[key] = counts.get(key, 0) + len(item.text)
        return counts

    def roles_by_repository(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        for item in self.items:
            bucket = counts.setdefault(item.repository_id or "", {})
            bucket[item.role] = bucket.get(item.role, 0) + 1
        return counts

    def unmet_role_requirements_by_repository(self) -> dict[str, list[str]]:
        """Which roles each accepted repository owed and could not deliver."""
        return {
            subject.repository_id: list(subject.unmet_role_requirements)
            for subject in self.accepted_repositories
        }

    def source_backed_repositories(self) -> tuple[str, ...]:
        """Repositories an implementation source file actually reached."""
        return tuple(
            dict.fromkeys(
                item.repository_id or ""
                for item in self.items
                if item.role == ROLE_IMPLEMENTATION_SOURCE
            )
        )

    def items_for_repository(self, repository_id: str) -> tuple[AnalysisEvidenceItem, ...]:
        return tuple(
            item for item in self.items if (item.repository_id or "") == repository_id
        )

    def paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.items)

    def files_by_role(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.role] = counts.get(item.role, 0) + 1
        return counts

    def chars_by_role(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.role] = counts.get(item.role, 0) + len(item.text)
        return counts

    def role_coverage(self) -> dict[str, dict[str, int]]:
        """Per role: how much existed, how much was owed, how much was read."""
        available = dict(self.available_by_role)
        required = dict(self.required_by_role)
        selected = self.files_by_role()
        chars = self.chars_by_role()
        roles = [role for role in EVIDENCE_ROLES if role in available or role in selected]
        return {
            role: {
                "available": int(available.get(role, 0)),
                "required": int(required.get(role, 0)),
                "selected": int(selected.get(role, 0)),
                "chars": int(chars.get(role, 0)),
            }
            for role in roles
        }

    @property
    def source_backed(self) -> bool:
        """Did implementation source actually reach the reader?"""
        return any(item.role == ROLE_IMPLEMENTATION_SOURCE for item in self.items)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "role_balance_phase_id": ROLE_BALANCE_PHASE_ID,
            "multiroot_phase_id": MULTIROOT_PHASE_ID,
            # ANALYSIS.MULTIROOT.LIVE.1.  A run that never requested a second
            # repository reports single_root_legacy — which is also what a
            # historical artifact carrying no receipt at all means.  Absence is
            # never read as a failed multi-root acquisition.
            "multi_root": dict(self.multi_root or single_root_legacy_receipt()),
            # ANALYSIS.MULTIROOT.LIVE.1 — the role-coverage receipt, made
            # root-aware additively.  The single-root fields below keep their
            # names and their meanings; these four sit beside them.
            "selected_files_by_repository": self.files_by_repository(),
            "selected_chars_by_repository": self.chars_by_repository(),
            "roles_by_repository": self.roles_by_repository(),
            "unmet_role_requirements_by_repository": (
                self.unmet_role_requirements_by_repository()
            ),
            "files_read": [item.as_dict() for item in self.items],
            "file_count": len(self.items),
            "inventory_file_count": self.inventory_file_count,
            "gaps": list(self.gaps),
            "evidence_profile": self.profile,
            "available_roles": [
                role for role, count in self.available_by_role if count
            ],
            "selected_files_by_role": self.files_by_role(),
            "selected_chars_by_role": self.chars_by_role(),
            "role_coverage": self.role_coverage(),
            "unmet_role_requirements": list(self.unmet_role_requirements),
            "selection_reason": self.selection_reason,
            "source_backed": self.source_backed,
            "bounds": {
                "max_files": MAX_EVIDENCE_FILES,
                "max_chars_per_file": MAX_CHARS_PER_FILE,
                "max_total_chars": MAX_TOTAL_CHARS,
            },
            "note": (
                "Bounded, role-balanced repository evidence for the analysis "
                "route. No call graph was built, no patch target was ranked and "
                "no source snippet was required."
            ),
        }


def _normalize(path: str) -> str:
    return str(path or "").replace("\\", "/").strip("/").lower()


def _relative_paths(repo_path: str, inventory: Any) -> list[str]:
    """Repository-relative paths, from the inventory production already built.

    Falls back to one bounded listing only when no inventory was handed over,
    so the common live path adds no traversal at all.
    """
    entries = getattr(inventory, "indexable_entries", None)
    if entries:
        return [
            entry.relative_path.as_posix()
            for entry in list(entries)[:MAX_INVENTORY_SCAN]
        ]

    root = Path(repo_path)
    if not root.is_dir():
        return []
    found: list[str] = []
    for current, directories, files in os.walk(root):
        directories[:] = [
            name
            for name in directories
            if not name.startswith(".")
            and name not in {"node_modules", "target", "dist", "build", "vendor",
                             "__pycache__", "tmp_tests"}
        ]
        for name in files:
            relative = Path(current, name).relative_to(root).as_posix()
            found.append(relative)
            if len(found) >= MAX_INVENTORY_SCAN:
                return found
    return found


#: A file that exists but cannot be read is a gap; a file that resolves outside
#: the root is not evidence at all.  The two outcomes are different and the
#: reader has to be able to tell them apart.
_UNREADABLE = object()


def _read_excerpt(
    root: Path, relative: str, remaining: int
) -> tuple[str, bool] | None | object:
    """Read one bounded excerpt from inside ``root``, or refuse it.

    Containment is checked on the canonical target, per root.  A symlink inside
    an approved repository that points outside it resolves outside and is
    refused; approving the repository never approves what its links reach.
    """
    try:
        target = (root / relative).resolve()
        target.relative_to(root)
    except (OSError, ValueError, RuntimeError):
        return None
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _UNREADABLE
    budget = min(MAX_CHARS_PER_FILE, max(0, remaining))
    excerpt = text[:budget]
    return excerpt, len(excerpt) < len(text)


def _source_gap_sentence(available: int, *, subject: str) -> str:
    """The documentation-only limitation, stated rather than hidden."""
    if available > 0:
        return (
            f"{subject}: this question asked about architecture or "
            f"implementation, and {available} supported implementation source "
            "file(s) exist, but none could be read within the bounded evidence "
            "budget. Treat the documentation as a description of the system, "
            "not as proof of how it is implemented."
        )
    return (
        f"{subject}: this question asked about architecture or implementation, "
        "but no supported implementation source files were found in this "
        "repository's inventory. Any statement about how the code works rests "
        "on documentation alone."
    )


def select_analysis_paths(
    relative_paths: list[str],
    *,
    requested_paths: Iterable[str] = (),
    subjects: Iterable[str] = (),
    obligations: Iterable[str] = (),
    profile: str | None = None,
) -> list[tuple[str, str]]:
    """Pick which files an analysis answer should read, in reading order.

    Returns ``(relative_path, role)`` pairs.  Deterministic over the same
    inventory: every ordering input is a constant, a literal token match or the
    canonical path, and nothing is scored.

    The order is a reading order, not a ranking.  Reserved roles are interleaved
    so that each of them reaches the reader before the character budget can be
    exhausted — which is the difference between reserving implementation source
    and actually acquiring it.
    """
    return list(
        plan_analysis_evidence(
            relative_paths,
            requested_paths=requested_paths,
            subjects=subjects,
            obligations=obligations,
            profile=profile,
            max_files=MAX_EVIDENCE_FILES,
        ).selections
    )


def _unmet_requirements(
    plan: AnalysisSelectionPlan,
    read_by_role: dict[str, int],
) -> tuple[str, ...]:
    """Roles the profile asked for that the read evidence does not carry.

    Conditional on purpose: a role with nothing available is not unmet, it is
    absent, and this route never manufactures evidence to fill a quota.
    """
    unmet: list[str] = []
    for role, minimum in plan.required_by_role:
        if minimum <= 0 or plan.available(role) <= 0:
            continue
        if read_by_role.get(role, 0) <= 0:
            unmet.append(role)
    return tuple(unmet)


def _collect_multiroot_analysis_evidence(
    resolution: MultiRootResolution,
    *,
    primary_inventory: Any,
    requested_paths: Iterable[str],
    subjects: Iterable[str],
    obligations: Iterable[str],
    resolved_profile: str,
) -> AnalysisEvidence:
    """Read bounded evidence from every repository the request may read.

    One budget, divided.  Twelve files and 60,000 characters are the same twelve
    and the same 60,000 they were for one repository; what changes is that the
    roots take turns spending them, so an answer about two systems is not an
    answer about the first one with the second one's name attached.
    """
    requested = list(requested_paths or ())
    subject_values = list(subjects or ())
    obligation_values = list(obligations or ())

    gaps: list[str] = []
    plans: list[tuple[AnalysisRepositorySubject, Any, Path]] = []
    final_subjects: list[AnalysisRepositorySubject] = []

    selection_started = time.perf_counter()
    membership_seconds = 0.0
    for subject in resolution.subjects:
        if not subject.accepted:
            gaps.append(
                f"The repository requested as {subject.requested_root_literal} was "
                f"named as a subject of this request but was not read "
                f"({subject.resolution_status}): {subject.rejection_reason} The "
                "comparison is therefore partial on every dimension that needed it."
            )
            final_subjects.append(subject)
            continue

        if subject.is_primary and primary_inventory is None:
            # The pre-phase fallback, unchanged: one bounded listing when
            # production handed over no inventory.  This phase adds no walk of
            # the primary root — reuse or the existing fallback, never both.
            listing_started = time.perf_counter()
            paths = _relative_paths(subject.canonical_root, None)
            subject = replace(
                subject,
                inventory_status=INVENTORY_BOUNDED_LISTING,
                inventory_file_count=len(paths),
                inventory_seconds=time.perf_counter() - listing_started,
            )
            membership_seconds += subject.inventory_seconds
        else:
            subject, paths = acquire_subject_membership(
                subject,
                inventory=primary_inventory if subject.is_primary else None,
            )
            membership_seconds += subject.inventory_seconds

        if not subject.accepted:
            gaps.append(
                f"{subject.display()} was accepted as a subject of this request "
                f"but produced no readable membership: {subject.rejection_reason}"
            )
            final_subjects.append(subject)
            continue

        plan = plan_analysis_evidence(
            paths,
            requested_paths=requested,
            subjects=subject_values,
            obligations=obligation_values,
            profile=resolved_profile,
            max_files=MAX_EVIDENCE_FILES,
        )
        plans.append((subject, plan, Path(subject.canonical_root)))

    allocation = allocate_root_balanced_selections(
        [(subject.subject_ordinal, plan.selections) for subject, plan, _ in plans],
        max_files=MAX_EVIDENCE_FILES,
        requested_role=ROLE_REQUESTED_PATH,
    )
    # Membership is reported on its own line, so selection time is selection.
    # Folding the secondary walk in here would hide the one cost this phase
    # actually adds, which is the cost most worth being able to see.
    selection_seconds = max(
        0.0, time.perf_counter() - selection_started - membership_seconds
    )

    by_ordinal = {subject.subject_ordinal: (subject, plan, root) for subject, plan, root in plans}
    acquisition_started = time.perf_counter()
    items: list[AnalysisEvidenceItem] = []
    read_by_root: dict[int, dict[str, int]] = {}
    chars_by_root: dict[int, int] = {}
    total = 0
    budget_exhausted = False
    for ordinal, relative, role in allocation:
        entry = by_ordinal.get(ordinal)
        if entry is None:
            continue
        subject, _plan, root = entry
        if total >= MAX_TOTAL_CHARS:
            budget_exhausted = True
            gaps.append(
                "The bounded evidence budget was reached before every selected "
                "document could be read."
            )
            break
        outcome = _read_excerpt(root, relative, MAX_TOTAL_CHARS - total)
        if outcome is None:
            continue
        if outcome is _UNREADABLE:
            gaps.append(f"{subject.display()}:{relative} could not be read.")
            continue
        excerpt, truncated = outcome  # type: ignore[misc]
        total += len(excerpt)
        read_by_root.setdefault(ordinal, {})
        read_by_root[ordinal][role] = read_by_root[ordinal].get(role, 0) + 1
        chars_by_root[ordinal] = chars_by_root.get(ordinal, 0) + len(excerpt)
        items.append(
            AnalysisEvidenceItem(
                path=relative,
                role=role,
                text=excerpt,
                truncated=truncated,
                repository_id=subject.repository_id,
                repository_display=subject.repository_display,
            )
        )
    acquisition_seconds = time.perf_counter() - acquisition_started

    inventory_total = 0
    available_totals: dict[str, int] = {}
    required_by_role: tuple[tuple[str, int], ...] = ()
    unmet_union: list[str] = []
    reasons: list[str] = []
    for subject, plan, _root in plans:
        read = read_by_root.get(subject.subject_ordinal, {})
        unmet = _unmet_requirements(plan, read)
        inventory_total += subject.inventory_file_count
        for role, count in plan.available_by_role:
            available_totals[role] = available_totals.get(role, 0) + count
        # Every root planned under the same profile, so every root owes the same
        # per-role minimums; the first one states them for the whole request.
        required_by_role = required_by_role or plan.required_by_role
        for role in unmet:
            if role not in unmet_union:
                unmet_union.append(role)
        final_subjects.append(
            replace(
                subject,
                evidence_selected=sum(read.values()),
                evidence_chars=chars_by_root.get(subject.subject_ordinal, 0),
                unmet_role_requirements=unmet,
            )
        )
        reasons.append(f"{subject.display()}: {plan.selection_reason}")

        if not read:
            gaps.append(
                f"{subject.display()} was read-scoped for this request but no "
                "file from it fitted the bounded evidence budget."
            )
        elif profile_requires_source(plan.profile) and not read.get(
            ROLE_IMPLEMENTATION_SOURCE, 0
        ):
            gaps.append(
                _source_gap_sentence(
                    plan.available(ROLE_IMPLEMENTATION_SOURCE),
                    subject=subject.display(),
                )
            )

    final_subjects.sort(key=lambda subject: subject.subject_ordinal)
    if not items:
        gaps.append(
            "No project documents, manifests, source files or entry points were "
            "found in the repository inventories of the requested subjects."
        )

    receipt = multiroot_receipt(
        resolution,
        final_subjects,
        files_selected=len(items),
        chars_selected=total,
        budget_exhausted=budget_exhausted,
        max_files=MAX_EVIDENCE_FILES,
        max_chars=MAX_TOTAL_CHARS,
        selection_seconds=selection_seconds,
        acquisition_seconds=acquisition_seconds,
    )
    return AnalysisEvidence(
        items=tuple(items),
        gaps=tuple(dict.fromkeys(gaps)),
        inventory_file_count=inventory_total,
        profile=resolved_profile,
        available_by_role=tuple(
            (role, available_totals.get(role, 0)) for role in BALANCED_ROLES
        ),
        required_by_role=required_by_role,
        unmet_role_requirements=tuple(unmet_union),
        selection_reason="; ".join(reasons),
        repositories=tuple(final_subjects),
        multi_root=receipt,
    )


def collect_analysis_evidence(
    repo_path: str | None,
    *,
    inventory: Any = None,
    requested_paths: Iterable[str] = (),
    subjects: Iterable[str] = (),
    obligations: Iterable[str] = (),
    profile: str | None = None,
    analysis_only: bool = False,
) -> AnalysisEvidence:
    """Read a bounded, role-balanced set of files to answer a question.

    Never indexes, never builds a graph, never ranks a patch target and never
    reads outside the repository roots this request established.  When nothing
    useful is found, the gap is reported rather than papered over — and when an
    architecture or implementation question could only reach documentation, that
    is reported too, because documentation presented as implementation proof is
    the failure this phase exists to stop.

    ``analysis_only`` is the multi-root gate.  Only the analysis workflow may
    read a second repository, and only one the user explicitly named: a
    clarification route, a defect repair and an explicit change all stay inside
    the active project root regardless of what any text mentions.
    """
    resolved_profile = (
        profile
        if profile in ANALYSIS_EVIDENCE_PROFILES
        else derive_evidence_profile(obligations=obligations, subjects=subjects)
    )

    if not repo_path:
        return AnalysisEvidence(
            gaps=("No repository was attached to this request.",),
            profile=resolved_profile,
        )

    root = Path(repo_path)
    try:
        root = root.resolve()
    except OSError:
        return AnalysisEvidence(
            gaps=("The repository path could not be resolved.",),
            profile=resolved_profile,
        )
    if not root.is_dir():
        return AnalysisEvidence(
            gaps=("The repository path is not a directory.",),
            profile=resolved_profile,
        )

    # ANALYSIS.MULTIROOT.LIVE.1 — a second repository enters only when the user
    # named it and only on the analysis route.  Nothing below this branch is
    # reached differently when they did not: a request that names one root takes
    # exactly the path it took before this phase existed.
    if analysis_only:
        resolution = resolve_analysis_subjects(
            str(root),
            obligations=obligations,
            requested_paths=requested_paths,
            subjects=subjects,
        )
        if resolution.multi_root_requested:
            return _collect_multiroot_analysis_evidence(
                resolution,
                primary_inventory=inventory,
                requested_paths=requested_paths,
                subjects=subjects,
                obligations=obligations,
                resolved_profile=resolved_profile,
            )

    relative_paths = _relative_paths(str(root), inventory)
    plan = plan_analysis_evidence(
        relative_paths,
        requested_paths=requested_paths,
        subjects=subjects,
        obligations=obligations,
        profile=resolved_profile,
        max_files=MAX_EVIDENCE_FILES,
    )

    items: list[AnalysisEvidenceItem] = []
    gaps: list[str] = []
    read_by_role: dict[str, int] = {}
    total = 0
    for relative, role in plan.selections:
        if total >= MAX_TOTAL_CHARS:
            gaps.append(
                "The bounded evidence budget was reached before every selected "
                "document could be read."
            )
            break
        outcome = _read_excerpt(root, relative, MAX_TOTAL_CHARS - total)
        if outcome is None:
            continue
        if outcome is _UNREADABLE:
            gaps.append(f"{relative} could not be read.")
            continue
        excerpt, truncated = outcome  # type: ignore[misc]
        total += len(excerpt)
        read_by_role[role] = read_by_role.get(role, 0) + 1
        items.append(
            AnalysisEvidenceItem(
                path=relative,
                role=role,
                text=excerpt,
                truncated=truncated,
            )
        )

    if not items:
        gaps.append(
            "No project documents, manifests, source files or entry points were "
            "found in the repository inventory."
        )
    if len(relative_paths) > len(items):
        gaps.append(
            f"{len(items)} of {len(relative_paths)} inventoried files were read; "
            "the rest were outside this route's bounded document budget."
        )

    # The documentation-only limitation, stated rather than hidden.  A question
    # about architecture or implementation that reached no code has to say so:
    # the previous behaviour presented eleven markdown files as an account of
    # how a system works, and it read as authoritative because nothing in the
    # answer marked the difference.
    source_read = read_by_role.get(ROLE_IMPLEMENTATION_SOURCE, 0)
    if profile_requires_source(plan.profile) and not source_read:
        if plan.available(ROLE_IMPLEMENTATION_SOURCE) > 0:
            gaps.append(
                "This question asked about architecture or implementation, and "
                f"{plan.available(ROLE_IMPLEMENTATION_SOURCE)} supported "
                "implementation source file(s) exist, but none could be read "
                "within the bounded evidence budget. Treat the documentation "
                "below as a description of the system, not as proof of how it "
                "is implemented."
            )
        else:
            gaps.append(
                "This question asked about architecture or implementation, but "
                "no supported implementation source files were found in this "
                "repository's inventory. Any statement about how the code works "
                "rests on documentation alone."
            )

    return AnalysisEvidence(
        items=tuple(items),
        gaps=tuple(gaps),
        inventory_file_count=len(relative_paths),
        profile=plan.profile,
        available_by_role=plan.available_by_role,
        required_by_role=plan.required_by_role,
        unmet_role_requirements=_unmet_requirements(plan, read_by_role),
        selection_reason=plan.selection_reason,
    )


def render_analysis_evidence_block(evidence: AnalysisEvidence) -> str:
    """Render the acquired excerpts as a prompt block.

    Where more than one repository was read, every excerpt names its repository.
    Two projects can both hold ``src/index.ts``; an excerpt labelled only
    ``src/index.ts`` would let a claim about one of them be written from the
    other, which is the specific confusion a comparison cannot survive.
    """
    if evidence.is_empty:
        return "No repository evidence was acquired."
    multi = evidence.is_multi_root
    parts: list[str] = []
    for index, item in enumerate(evidence.items, start=1):
        suffix = " (truncated)" if item.truncated else ""
        header = (
            f"repository={item.repository_display}\n"
            f"file={item.path}\n"
            f"cite={item.citation}\n"
            if multi
            else f"file={item.path}\n"
        )
        parts.append(
            f"--- EVIDENCE [{index}] ---\n"
            f"{header}"
            f"role={item.role}{suffix}\n\n"
            f"{item.text}"
        )
    return "\n\n".join(parts)


def _repositories_block(evidence: AnalysisEvidence) -> str:
    """What each requested repository contributed, and what it could not.

    The T5 answer used to open by declaring the second repository inaccessible.
    When it *was* read, saying so is not decoration: an answer that hedges about
    evidence it actually holds is as wrong as one that invents evidence it does
    not.
    """
    lines: list[str] = []
    files = evidence.files_by_repository()
    chars = evidence.chars_by_repository()
    roles = evidence.roles_by_repository()
    for subject in evidence.repositories:
        if subject.accepted:
            role_summary = ", ".join(
                f"{role}={count}"
                for role, count in sorted(roles.get(subject.repository_id, {}).items())
            )
            lines.append(
                f"- {subject.display()} [{subject.root_role}, read-only]: "
                f"{files.get(subject.repository_id, 0)} file(s), "
                f"{chars.get(subject.repository_id, 0)} chars"
                + (f" ({role_summary})" if role_summary else " (no file read)")
            )
        else:
            lines.append(
                f"- {subject.display()} [requested as "
                f"{subject.requested_root_literal}]: NOT READ — "
                f"{subject.resolution_status}: {subject.rejection_reason}"
            )
    return "\n".join(lines)


def build_analysis_answer_prompt(
    *,
    user_query: str,
    evidence: AnalysisEvidence,
    obligations: Iterable[str] = (),
    repo_path: str | None = None,
    memory_block: str = "",
    history_block: str = "",
    clarification: bool = False,
) -> str:
    """Build the answer prompt for a read-only route.

    Natural language out, deliberately.  There is no patch schema here, no
    ``source_snippet`` requirement and no instruction to return
    ``patch_candidate=null`` — the previous path's habit of answering an
    architecture question with a refusal to patch is the specific thing this
    prompt replaces.

    The answer is still evidence-bounded: it may claim only what the listed
    files support, and it is told to declare a gap rather than fill one in.
    """
    ordered = [str(item) for item in (obligations or ()) if str(item).strip()]
    obligations_block = (
        "\n".join(f"{index}. {item}" for index, item in enumerate(ordered, start=1))
        if ordered
        else "1. " + " ".join(str(user_query or "").split())[:240]
    )
    gaps_block = (
        "\n".join(f"- {gap}" for gap in evidence.gaps)
        if evidence.gaps
        else "- None recorded."
    )
    # Grouped by role, because a flat list buries the distinction the answer is
    # being asked to respect.  The measured T5 answer cited documentation and a
    # manifest and never named one of the six source files acquired beside them;
    # the files were in the prompt, but nothing in the prompt said which of them
    # could settle a question about how the code behaves.
    multi_root = evidence.is_multi_root
    if evidence.items and multi_root:
        # Grouped by repository first, then by role.  A comparison answer needs
        # to be able to see, at a glance, which side of the comparison each
        # acquired file belongs to.
        sections: list[str] = []
        for subject in evidence.accepted_repositories:
            grouped_root: dict[str, list[str]] = {}
            for item in evidence.items_for_repository(subject.repository_id):
                grouped_root.setdefault(item.role, []).append(item.path)
            if not grouped_root:
                sections.append(f"{subject.display()}: no file was read.")
                continue
            body = "\n".join(
                f"  {role} ({len(paths)}):\n"
                + "\n".join(f"  - {subject.display()}::{path}" for path in paths)
                for role in EVIDENCE_ROLES
                if (paths := grouped_root.get(role))
            )
            sections.append(f"{subject.display()}:\n{body}")
        files_block = "\n".join(sections)
    elif evidence.items:
        grouped: dict[str, list[str]] = {}
        for item in evidence.items:
            grouped.setdefault(item.role, []).append(item.path)
        files_block = "\n".join(
            f"{role} ({len(paths)}):\n"
            + "\n".join(f"- {path}" for path in paths)
            for role in EVIDENCE_ROLES
            if (paths := grouped.get(role))
        )
    else:
        files_block = "- No files were read."

    if clarification:
        task_block = """\
[TASK]
This request could not be read as a single executable obligation. It may be
ambiguous, or it may carry an analysis obligation and a change obligation that
one run cannot honour together.

Do not choose a change workflow on the user's behalf.
Do not propose or apply an edit. Instead:
- restate every obligation you can see, in the order the user wrote it;
- say plainly which parts you can answer now from the evidence below, and answer
  those;
- ask the smallest set of questions needed to make the remaining part
  executable, naming the specific missing detail (target, file, expected
  behaviour, or which obligation to run first).
Never drop half of a request in order to answer the other half."""
    else:
        task_block = """\
[TASK]
Answer the user's question about this repository. This is an analysis request:
no code change was asked for, and none may be proposed.

- Ground every claim in the evidence below and name the file it came from.
- Where the evidence does not support an answer, say so explicitly and name what
  you would need to read; do not fill the gap with a guess.
- Documentation describes intent; source files show implementation. Where
  implementation_source files were read, name them for claims about how the
  code actually behaves. Where a claim rests only on documentation, say so in
  that sentence rather than presenting the document as proof of the code.
- Compare like with like when the user asked for a comparison, and keep the
  order and the dimensions they asked for.
- Answer in plain prose or markdown. Do not emit JSON, a patch, a diff, or a
  structured patch payload."""

    if multi_root:
        task_block += """

More than one repository was read for this request. Therefore:
- Every repository listed under [REPOSITORIES] as read IS accessible to you.
  Do not open by saying you cannot access it; its files are below.
- Cite files as repository::path, exactly as the cite= line of each evidence
  block spells it. Two repositories may contain the same relative path, and a
  bare path names neither of them.
- A claim about one repository must rest on evidence read from that repository.
  Evidence from one side of a comparison never proves anything about the other.
- A comparative claim of the form "A does X while B does Y" needs evidence for X
  from A and evidence for Y from B. If you hold only one side, say which side is
  missing instead of inferring the other.
- Where a repository was requested but NOT read, say the comparison is partial
  on that dimension and name what was unavailable. Do not construct the missing
  half from the half you have."""

    # Every requested repository, read or refused.  A refused one has to appear
    # here for the same reason a gap does: an answer cannot report a comparison
    # as partial if nothing told it which half is missing.
    repository_block = (
        f"[REPOSITORIES — every subject this request named]\n"
        f"{_repositories_block(evidence)}"
        if evidence.repositories
        else f"[REPOSITORY]\n{repo_path or 'unknown'}"
    )

    return f"""\
You are answering a question about a software repository.

{task_block}

[OBLIGATIONS — preserved in the order the user wrote them]
{obligations_block}

{repository_block}

[FILES READ]
{files_block}

[EVIDENCE GAPS]
{gaps_block}

[REPOSITORY EVIDENCE]
{render_analysis_evidence_block(evidence)}

[MEMORY]
{memory_block or "None"}

[RECENT HISTORY]
{history_block or "None"}

[USER]
{user_query}

[RULES]
- No repository change was requested. Do not propose, describe or emit a patch,
  a diff, a patch_candidate or a patch_plan.
- Do not claim anything the evidence above does not support.
- If the evidence is insufficient, answer what you can and state the gap.
- Do not restate the user's request as if it were the answer.
""".strip()


__all__ = [
    "ANALYSIS_EVIDENCE_PROFILES",
    "ANALYSIS_EVIDENCE_SCHEMA_VERSION",
    "BALANCED_ROLES",
    "EVIDENCE_ROLES",
    "MAX_CHARS_PER_FILE",
    "MAX_EVIDENCE_FILES",
    "MAX_TOTAL_CHARS",
    "MULTIROOT_PHASE_ID",
    "MULTIROOT_SINGLE_ROOT_LEGACY",
    "PHASE_ID",
    "PROFILE_ARCHITECTURE_IMPLEMENTATION",
    "PROFILE_DEPENDENCY_CONFIGURATION",
    "PROFILE_DOCUMENTATION_EXPLANATION",
    "PROFILE_GENERAL_ANALYSIS",
    "PROFILE_IMPLEMENTATION_DETAIL",
    "ROLE_BALANCE_PHASE_ID",
    "ROLE_ENTRY_POINT",
    "ROLE_IMPLEMENTATION_SOURCE",
    "ROLE_PACKAGE_MANIFEST",
    "ROLE_PROJECT_DOCUMENT",
    "ROLE_REQUESTED_PATH",
    "ROLE_REQUESTED_SUBJECT",
    "ROLE_TEST_EXAMPLE",
    "AnalysisEvidence",
    "AnalysisEvidenceItem",
    "AnalysisRepositorySubject",
    "build_analysis_answer_prompt",
    "collect_analysis_evidence",
    "derive_evidence_profile",
    "plan_analysis_evidence",
    "render_analysis_evidence_block",
    "resolve_analysis_subjects",
    "select_analysis_paths",
]
