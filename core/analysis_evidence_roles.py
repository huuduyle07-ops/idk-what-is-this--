"""ANALYSIS.EVIDENCE.LIVE.1 — role-balanced analysis evidence selection.

WAITER.LIVE.1 gave the analysis route a bounded document budget and a fixed
priority order over paths.  The order was: what the user named, then the
documents a repository writes about itself, then its manifests, then a small
list of root-level entry-point names, then any markdown under ``docs/``.  On a
small repository that reads exactly like a careful human.  On a real monorepo it
starves.

The live T5 measurement, against ``deepseek-harness`` (6,126 indexable files,
2,700 of them TypeScript):

    selected 12 files — 11 markdown documents and 1 ``package.json``
    selected 0 implementation source files
    59,674 of the 60,000 character budget spent before any code was reached

Nothing was misconfigured.  ``.ts`` is a supported extension, the files were in
the inventory, and the answer that came back was accurate.  It was accurate
*about the documentation*, because the documentation had consumed the entire
budget before implementation code was ever considered — the repository has no
root-level ``index.ts``, so the fixed entry-point list matched nothing, and the
``docs/`` sweep took every remaining slot.

The fix is allocation, not capacity.  The file cap is still 12, the character
cap is still 60,000, the per-file cap is still 6,000.  What changes is that the
budget is divided across evidence *roles* before it is spent:

    classify every candidate into one deterministic role
        -> derive a small evidence profile from the task's own words
        -> reserve a per-role minimum, interleaved so each role reaches the
           reader before the character budget is exhausted
        -> fill what is left by role rotation

An architecture or implementation question therefore cannot be answered from
documentation alone while supported source exists — and a documentation question
is still answered from documentation, because the profile is read off what the
user asked for rather than off what the repository happens to contain.

The module is pure and stdlib-only apart from two existing policy imports.  It
reads no files, walks nothing, calls no model, contacts no service, builds no
index and grants no authority.  It decides only *which* bounded set of paths the
analysis route should open.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from core.eligibility_policy import (
    is_historical_location,
    is_snapshot_location,
    is_temporary_location,
    is_test_location,
)
from core.source_file_policy import SOURCE_ROLE_BY_EXTENSION, SOURCE_ROLE_CODE


PHASE_ID = "ANALYSIS.EVIDENCE.LIVE.1"
ANALYSIS_EVIDENCE_ROLE_SCHEMA_VERSION = "analysis_evidence_live_1_role_balance_v1"


# ── Evidence roles ────────────────────────────────────────────────────────────
#: Why a file was selected, and what kind of evidence it therefore is.  Roles
#: are the unit the budget is allocated across and the only explanation the
#: selection ever offers.
#:
#: ``requested_path`` and ``requested_subject`` are WAITER.LIVE.1's own names and
#: keep their meaning.  ``implementation_source`` and ``test_example`` are new:
#: before this phase there was no role that could hold code, which is precisely
#: why code could never be reserved.  ``entry_point`` is retained so evidence
#: receipts written before this phase still validate; new selections classify a
#: canonical entry point as ``implementation_source`` and rank it first inside
#: that role, because an entry point *is* implementation source and a monorepo
#: keeps its entry points inside packages rather than at the root.
ROLE_REQUESTED_PATH = "requested_path"
ROLE_IMPLEMENTATION_SOURCE = "implementation_source"
ROLE_PROJECT_DOCUMENT = "project_document"
ROLE_PACKAGE_MANIFEST = "package_manifest"
ROLE_TEST_EXAMPLE = "test_example"
ROLE_REQUESTED_SUBJECT = "requested_subject"
ROLE_ENTRY_POINT = "entry_point"

EVIDENCE_ROLES: tuple[str, ...] = (
    ROLE_REQUESTED_PATH,
    ROLE_IMPLEMENTATION_SOURCE,
    ROLE_PROJECT_DOCUMENT,
    ROLE_PACKAGE_MANIFEST,
    ROLE_TEST_EXAMPLE,
    ROLE_REQUESTED_SUBJECT,
    ROLE_ENTRY_POINT,
)

#: Roles the balancer may reserve budget for.  ``requested_path`` is absent on
#: purpose: an exactly requested file is not balanced against anything, it is
#: taken first (see :func:`plan_analysis_evidence`).  ``entry_point`` is absent
#: because nothing is classified into it any more.
BALANCED_ROLES: tuple[str, ...] = (
    ROLE_IMPLEMENTATION_SOURCE,
    ROLE_PROJECT_DOCUMENT,
    ROLE_PACKAGE_MANIFEST,
    ROLE_TEST_EXAMPLE,
    ROLE_REQUESTED_SUBJECT,
)


# ── Evidence profiles ─────────────────────────────────────────────────────────
#: What shape of evidence the question needs.  Derived from the obligations and
#: subjects INPUT.1 already preserved — the user's own words, split by
#: WAITER.LIVE.1 — by literal marker match.  There is no classifier here, no
#: model call and no score: the same words always yield the same profile.
PROFILE_ARCHITECTURE_IMPLEMENTATION = "architecture_implementation"
PROFILE_IMPLEMENTATION_DETAIL = "implementation_detail"
PROFILE_DOCUMENTATION_EXPLANATION = "documentation_explanation"
PROFILE_DEPENDENCY_CONFIGURATION = "dependency_configuration"
PROFILE_GENERAL_ANALYSIS = "general_analysis"

ANALYSIS_EVIDENCE_PROFILES: tuple[str, ...] = (
    PROFILE_ARCHITECTURE_IMPLEMENTATION,
    PROFILE_IMPLEMENTATION_DETAIL,
    PROFILE_DOCUMENTATION_EXPLANATION,
    PROFILE_DEPENDENCY_CONFIGURATION,
    PROFILE_GENERAL_ANALYSIS,
)

#: Per-role minimum file counts, in the order the profile wants them filled.
#:
#: The numbers are small and they are not percentages of anything.  Each is a
#: floor on representation, not a quota to be met at all costs: a role with
#: nothing available contributes nothing, and a role listed at ``0`` is still
#: allowed to fill leftover budget.  What a positive minimum buys is a place in
#: the *reservation* pass, which runs before the character budget can be spent.
#:
#: ``architecture_implementation`` is the T5 shape and the reason this phase
#: exists: documentation and implementation source are both reserved, because an
#: architecture answer that cites only prose has not read the system it
#: describes.  ``documentation_explanation`` deliberately reserves no source —
#: "summarise the README" is not a request to read the compiler.
_PROFILE_RESERVATIONS: dict[str, tuple[tuple[str, int], ...]] = {
    PROFILE_ARCHITECTURE_IMPLEMENTATION: (
        (ROLE_IMPLEMENTATION_SOURCE, 4),
        (ROLE_PROJECT_DOCUMENT, 3),
        (ROLE_PACKAGE_MANIFEST, 1),
        (ROLE_TEST_EXAMPLE, 0),
        (ROLE_REQUESTED_SUBJECT, 0),
    ),
    PROFILE_IMPLEMENTATION_DETAIL: (
        (ROLE_IMPLEMENTATION_SOURCE, 5),
        (ROLE_PROJECT_DOCUMENT, 1),
        (ROLE_PACKAGE_MANIFEST, 1),
        (ROLE_TEST_EXAMPLE, 0),
        (ROLE_REQUESTED_SUBJECT, 0),
    ),
    PROFILE_DOCUMENTATION_EXPLANATION: (
        (ROLE_PROJECT_DOCUMENT, 4),
        (ROLE_PACKAGE_MANIFEST, 1),
        (ROLE_IMPLEMENTATION_SOURCE, 0),
        (ROLE_REQUESTED_SUBJECT, 0),
        (ROLE_TEST_EXAMPLE, 0),
    ),
    PROFILE_DEPENDENCY_CONFIGURATION: (
        (ROLE_PACKAGE_MANIFEST, 3),
        (ROLE_PROJECT_DOCUMENT, 1),
        (ROLE_IMPLEMENTATION_SOURCE, 0),
        (ROLE_REQUESTED_SUBJECT, 0),
        (ROLE_TEST_EXAMPLE, 0),
    ),
    #: No task words to read.  This is WAITER.LIVE.1's own emphasis — documents
    #: then manifests — kept as the default so a caller that supplies no
    #: obligations sees the behaviour it saw before this phase.
    PROFILE_GENERAL_ANALYSIS: (
        (ROLE_PROJECT_DOCUMENT, 3),
        (ROLE_PACKAGE_MANIFEST, 1),
        (ROLE_IMPLEMENTATION_SOURCE, 0),
        (ROLE_REQUESTED_SUBJECT, 0),
        (ROLE_TEST_EXAMPLE, 0),
    ),
}

if set(_PROFILE_RESERVATIONS) != set(ANALYSIS_EVIDENCE_PROFILES):  # pragma: no cover
    raise RuntimeError("every analysis evidence profile must state its reservations")
for _profile, _rows in _PROFILE_RESERVATIONS.items():  # pragma: no cover
    if tuple(sorted(role for role, _ in _rows)) != tuple(sorted(BALANCED_ROLES)):
        raise RuntimeError(
            f"profile {_profile!r} must state a minimum for every balanced role"
        )


# ── Profile markers ───────────────────────────────────────────────────────────
#: Bounded literal markers, matched case-insensitively against the words the
#: user actually wrote.  Deliberately the same technique WAITER.LIVE.1 already
#: uses to read defect/change/analysis markers off a request: a frozen pattern,
#: a bounded scan, and no interpretation beyond "this word is present".
_MAX_PROFILE_SCAN_CHARS = 4_000

_ARCHITECTURE_RE = re.compile(
    r"\b(?:architecture|architectural|architected|design|designs|designed|"
    r"structure|structures|structured|structural|layout|topology|subsystem|"
    r"subsystems|component|components|layering|layered|"
    r"organi[sz]ation|organi[sz]ed)\b",
    re.I,
)
_IMPLEMENTATION_RE = re.compile(
    r"\b(?:implement|implements|implemented|implementing|implementation|"
    r"internal|internally|internals|mechanism|mechanisms|mechanics|"
    r"under the hood|code path|call path|control flow|data flow|algorithm|"
    r"algorithms|source code|how (?:it|this|that|they|these|those) works?|"
    r"how does\b.{0,60}?\bwork)\b",
    re.I,
)
_DOCUMENTATION_RE = re.compile(
    r"\b(?:readme|documentation|docs|changelog|release notes)\b",
    re.I,
)
_DEPENDENCY_RE = re.compile(
    r"\b(?:dependency|dependencies|devdependencies|peerdependencies|"
    r"package\.json|pyproject|cargo\.toml|go\.mod|requirements\.txt|"
    r"manifest|manifests|scripts?|workspace|workspaces|"
    r"packages? declares?|version constraints?)\b",
    re.I,
)


def derive_evidence_profile(
    *,
    obligations: Iterable[str] = (),
    subjects: Iterable[str] = (),
) -> str:
    """Read the evidence profile off the task's own preserved words.

    Total over the profile vocabulary and order-stable: architecture wins over
    implementation (an architecture question wants both roles), implementation
    wins over documentation (``how does this work internally`` is not a request
    to read prose), documentation wins over dependencies (``summarise the
    README`` stays documentation-centric even when it mentions scripts), and a
    request with none of those markers gets the general profile.

    No model is consulted and nothing is scored.  When the caller supplies no
    task words at all the answer is :data:`PROFILE_GENERAL_ANALYSIS`, which is
    WAITER.LIVE.1's pre-existing emphasis.
    """
    parts: list[str] = []
    for group in (obligations, subjects):
        for value in group or ():
            text = str(value or "").strip()
            if text:
                parts.append(text)
    scanned = " ".join(parts)[:_MAX_PROFILE_SCAN_CHARS]
    if not scanned:
        return PROFILE_GENERAL_ANALYSIS

    if _ARCHITECTURE_RE.search(scanned):
        return PROFILE_ARCHITECTURE_IMPLEMENTATION
    if _IMPLEMENTATION_RE.search(scanned):
        return PROFILE_IMPLEMENTATION_DETAIL
    if _DOCUMENTATION_RE.search(scanned):
        return PROFILE_DOCUMENTATION_EXPLANATION
    if _DEPENDENCY_RE.search(scanned):
        return PROFILE_DEPENDENCY_CONFIGURATION
    return PROFILE_GENERAL_ANALYSIS


def profile_reservations(profile: str) -> tuple[tuple[str, int], ...]:
    """The ``(role, minimum)`` rows for one profile, in fill order."""
    return _PROFILE_RESERVATIONS.get(profile, _PROFILE_RESERVATIONS[PROFILE_GENERAL_ANALYSIS])


def profile_requires_source(profile: str) -> bool:
    """Does this profile reserve implementation source when it exists?"""
    return any(
        role == ROLE_IMPLEMENTATION_SOURCE and minimum > 0
        for role, minimum in profile_reservations(profile)
    )


# ── Path vocabulary ───────────────────────────────────────────────────────────
#: Documents a repository writes about itself, in the order a human would open
#: them.  Matched on the normalized path, and used as the within-role ordering
#: hint rather than as a separate priority pass.
PROJECT_DOCUMENT_NAMES: tuple[str, ...] = (
    "readme.md",
    "readme.rst",
    "readme.txt",
    "readme",
    "architecture.md",
    "design.md",
    "overview.md",
    "setup.md",
    "contributing.md",
    "docs/readme.md",
    "docs/architecture.md",
    "docs/overview.md",
    "docs/design.md",
)

#: Directories whose prose counts as an architecture document.
DOCUMENT_DIRECTORIES: tuple[str, ...] = ("docs/", "doc/", "documentation/")
DOCUMENT_SUFFIXES: tuple[str, ...] = (".md", ".rst", ".adoc", ".txt")

#: What a repository declares itself to be built from.
MANIFEST_NAMES: tuple[str, ...] = (
    "package.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "gemfile",
    "pubspec.yaml",
    "pnpm-workspace.yaml",
    "docker-compose.yml",
    "dockerfile",
    "makefile",
)

#: Where execution starts.  Matched on the *basename* now rather than on a fixed
#: root-relative path, because a workspace keeps ``index.ts`` inside each
#: package and the root-anchored list matched nothing on the repository that
#: produced this phase.  This is an ordering hint inside
#: ``implementation_source``; it is not a separate budget.
ENTRY_POINT_BASENAMES: frozenset[str] = frozenset(
    {
        "main.py",
        "__main__.py",
        "app.py",
        "cli.py",
        "manage.py",
        "index.js",
        "index.ts",
        "index.tsx",
        "main.js",
        "main.ts",
        "server.ts",
        "server.js",
        "server.py",
        "main.go",
        "main.rs",
        "lib.rs",
        "mod.rs",
        "program.cs",
    }
)

#: Never analysis evidence.  Build output and vendored trees describe somebody
#: else's repository.
EXCLUDED_PREFIXES: tuple[str, ...] = (
    "node_modules/",
    "target/",
    "dist/",
    "build/",
    "vendor/",
    ".git/",
    ".agent/",
    "__pycache__/",
    "tmp_tests/",
)

#: The same names, read as path *segments* rather than as root prefixes.  A
#: monorepo puts its build output at ``packages/<name>/dist`` and its vendored
#: copies at ``packages/<name>/node_modules``, neither of which a root-anchored
#: prefix can see.  Derived from :data:`EXCLUDED_PREFIXES` so there is one list
#: to maintain and no second extension/vendor map to drift from it.
#:
#: Nested matches *demote* rather than exclude: generated and vendored code may
#: still be the only code there is, and the invariant this phase owns is that
#: primary implementation source is never displaced by it.
GENERATED_OR_VENDOR_SEGMENTS: frozenset[str] = frozenset(
    prefix.rstrip("/") for prefix in EXCLUDED_PREFIXES
)

#: Tests and examples, differentiated from production source so an architecture
#: question cannot have its implementation reservation filled entirely by spec
#: files.  ``is_test_location`` owns the ``tests/`` directory and ``test_``/
#: ``_test.`` name conventions; the two additions here are the brace-language
#: conventions it does not spell (``foo.test.ts``, ``foo.spec.ts``) and the
#: directories a repository keeps runnable samples in.
_TEST_NAME_MARKERS: tuple[str, ...] = (".test.", ".spec.", "_spec.")
_EXAMPLE_DIRECTORY_SEGMENTS: frozenset[str] = frozenset(
    {
        "example",
        "examples",
        "sample",
        "samples",
        "fixture",
        "fixtures",
        "__fixtures__",
        "__mocks__",
    }
)

#: Subject words too generic to steer a path selection.  Small, static and
#: local: this is a stop list, not a frequency model, and nothing here is
#: weighted, scored or derived from the repository.
_SUBJECT_STOP_WORDS: frozenset[str] = frozenset(
    {
        "about", "against", "also", "analyse", "analyze", "been", "code",
        "codebase", "compare", "comparison", "could", "does", "each",
        "explain", "file", "files", "from", "have", "idea", "ideas", "into",
        "made", "make", "more", "other", "project", "recommend", "repositories",
        "repository", "should", "some", "source", "than", "that", "their",
        "them", "then", "these", "they", "this", "those", "used", "using",
        "what", "when", "where", "which", "with", "would",
    }
)

MIN_SUBJECT_TOKEN_CHARS = 4
MAX_SUBJECT_TOKENS = 12

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _segments(path: str) -> tuple[str, ...]:
    return tuple(part for part in path.split("/") if part)


def _basename(path: str) -> str:
    segments = _segments(path)
    return segments[-1] if segments else ""


def _extension(path: str) -> str:
    """The file's actual final extension, lowercased.

    ``README.ts.md`` is a markdown document.  Reading the role off the real
    extension rather than off a substring of the path is the whole guard against
    that false positive.
    """
    tail = _basename(path)
    if "." not in tail:
        return ""
    return "." + tail.rsplit(".", 1)[-1]


def is_document_path(path: str) -> bool:
    """Prose a repository writes about itself."""
    normalized = path.casefold()
    if normalized.endswith(DOCUMENT_SUFFIXES):
        return True
    return _basename(normalized) in {"readme", "license", "licence", "notice"}


def is_manifest_path(path: str) -> bool:
    return _basename(path.casefold()) in set(MANIFEST_NAMES)


def is_source_path(path: str) -> bool:
    """Is this a supported *code* file, by the canonical extension policy?

    Delegates to ``core.source_file_policy``.  This phase adds no extension map
    of its own, so ``.ts`` classifies as code here for exactly the reason it
    classifies as code everywhere else in the system.
    """
    return SOURCE_ROLE_BY_EXTENSION.get(_extension(path.casefold())) == SOURCE_ROLE_CODE


def is_test_or_example_path(path: str) -> bool:
    normalized = path.casefold()
    if is_test_location(normalized):
        return True
    basename = _basename(normalized)
    if any(marker in basename for marker in _TEST_NAME_MARKERS):
        return True
    return any(part in _EXAMPLE_DIRECTORY_SEGMENTS for part in _segments(normalized)[:-1])


def is_generated_or_vendored_path(path: str) -> bool:
    normalized = path.casefold()
    if any(part in GENERATED_OR_VENDOR_SEGMENTS for part in _segments(normalized)):
        return True
    return is_snapshot_location(normalized) or is_temporary_location(normalized)


def classify_evidence_role(path: str) -> str | None:
    """The single deterministic role one repository path belongs to.

    Returns ``None`` for a path no role claims — data files, lockfiles, images.
    Such a path is still selectable when the user named it exactly, and still
    selectable as ``requested_subject`` when its name carries a subject the user
    asked about; it is never reserved budget of its own.
    """
    normalized = str(path or "").replace("\\", "/").strip("/").casefold()
    if not normalized:
        return None
    if is_manifest_path(normalized):
        return ROLE_PACKAGE_MANIFEST
    if is_document_path(normalized):
        return ROLE_PROJECT_DOCUMENT
    if is_source_path(normalized):
        if is_test_or_example_path(normalized):
            return ROLE_TEST_EXAMPLE
        return ROLE_IMPLEMENTATION_SOURCE
    return None


def subject_tokens(subjects: Iterable[str]) -> tuple[str, ...]:
    """Bounded lexical tokens from the task words INPUT.1 preserved.

    Whole subjects are sentences — ``"this repository (deepseek-harness"`` is one
    of them on the live T5 request — and no path has ever contained one.
    Splitting them into words is what lets a subject reach a source file at all,
    and the bound plus the stop list are what keep it from reaching every source
    file.

    Callers pass subjects *and* obligations, subjects first so the narrower
    signal wins the token budget.  Measured on the live T5 request: subjects
    alone yield ``("deepseek", "harness")``, which reaches UI settings dialogs
    and API plumbing; adding the obligations yields ``agent``, ``loop`` and
    ``extension`` too, which reaches ``packages/core/agent-loop/src/agent.ts`` —
    the code the question was actually about.  The question's own words were
    already preserved and were simply not being used.

    This stays a bounded literal-token overlap, not retrieval ranking: no
    frequency, no weighting, no model, and the same fixed cap either way.
    """
    tokens: list[str] = []
    for subject in subjects or ():
        for raw in _TOKEN_SPLIT_RE.split(str(subject or "").casefold()):
            if len(raw) < MIN_SUBJECT_TOKEN_CHARS or raw in _SUBJECT_STOP_WORDS:
                continue
            if raw in tokens:
                continue
            tokens.append(raw)
            if len(tokens) >= MAX_SUBJECT_TOKENS:
                return tuple(tokens)
    return tuple(tokens)


def _document_rank(path: str) -> int:
    try:
        return PROJECT_DOCUMENT_NAMES.index(path)
    except ValueError:
        pass
    base = len(PROJECT_DOCUMENT_NAMES)
    if path.startswith(DOCUMENT_DIRECTORIES):
        return base
    return base + 1


def _manifest_rank(path: str) -> int:
    basename = _basename(path)
    try:
        return MANIFEST_NAMES.index(basename)
    except ValueError:
        return len(MANIFEST_NAMES)


def _demotion(path: str) -> int:
    """How far back a path goes regardless of which role it serves.

    ``0`` primary, ``1`` secondary — a test, an example, or archived/superseded
    material — and ``2`` generated or vendored.  This is the whole of the
    test/example and generated/vendor policy: nothing is excluded, because a
    sample really can be the clearest description of an API and generated code
    really is sometimes the only code there is.  What the tiers forbid is either
    kind displacing primary material while primary material exists.

    ``is_historical_location`` is the existing demotion rule, reused: a design
    note under ``archived/`` or ``superseded/`` describes a system that was.
    """
    if is_generated_or_vendored_path(path):
        return 2
    if is_test_or_example_path(path) or is_historical_location(path.casefold()):
        return 1
    return 0


#: Markup, stylesheets and build configuration are code by the canonical
#: extension policy and stay code here; they are simply the weakest answer to
#: "how is this implemented".  ``packages/core/agent-loop/tsdown.config.ts``
#: names the right package and says nothing about the loop.
#:
#: An ordering tier, not a reclassification: no extension changes role, and the
#: policy in ``core.source_file_policy`` is untouched.
_STYLE_AND_MARKUP_EXTENSIONS: frozenset[str] = frozenset(
    {".html", ".htm", ".css", ".scss", ".sass"}
)


def _source_tier(path: str) -> int:
    if _extension(path) in _STYLE_AND_MARKUP_EXTENSIONS:
        return 1
    if ".config." in _basename(path):
        return 1
    return 0


def candidate_sort_key(path: str, role: str, tokens: tuple[str, ...]) -> tuple:
    """Stable ordering inside one role.

    Every role starts from the same demotion, then applies its own notion of
    "strongest", then falls back to the shallower path and finally to the
    canonical path.  A role always produces the same tuple shape, and ordering
    only ever happens within a role, so the shapes never meet.

    The role-specific middles:

    ``project_document``
        the order a human opens a repository's own documents — README, then
        architecture, then the rest of ``docs/`` — before subject overlap.
        Explicitness first, exactly as the phase brief orders it.

    ``package_manifest``
        the ecosystem order in :data:`MANIFEST_NAMES`, so the root
        ``package.json`` precedes a sample project's copy.

    ``implementation_source``
        program code before markup and stylesheets, then overlap with the
        subjects the user named, then an entry-point basename, which is how a
        workspace's per-package front doors are found now that a root-anchored
        list finds nothing.

    Nothing here is a frequency, a weight or a probability.  Overlap is a count
    of distinct subject tokens present in the path, which is why this is not
    retrieval ranking and does not reopen it.
    """
    demotion = _demotion(path)
    overlap = -sum(1 for token in tokens if token in path)
    tail = (path.count("/"), path)
    if role == ROLE_PROJECT_DOCUMENT:
        return (demotion, (_document_rank(path), overlap), *tail)
    if role == ROLE_PACKAGE_MANIFEST:
        return (demotion, (_manifest_rank(path), overlap), *tail)
    if role == ROLE_IMPLEMENTATION_SOURCE:
        entry = 0 if _basename(path) in ENTRY_POINT_BASENAMES else 1
        return (demotion, (_source_tier(path), overlap, entry), *tail)
    return (demotion, (overlap,), *tail)


# ── The plan ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AnalysisSelectionPlan:
    """Which paths to read, in which order, and what the roles cost."""

    profile: str
    selections: tuple[tuple[str, str], ...] = ()
    available_by_role: tuple[tuple[str, int], ...] = ()
    required_by_role: tuple[tuple[str, int], ...] = ()
    reserved_by_role: tuple[tuple[str, int], ...] = ()
    selection_reason: str = ""
    schema_version: str = ANALYSIS_EVIDENCE_ROLE_SCHEMA_VERSION

    @property
    def available_roles(self) -> tuple[str, ...]:
        return tuple(role for role, count in self.available_by_role if count)

    def available(self, role: str) -> int:
        return dict(self.available_by_role).get(role, 0)

    def required(self, role: str) -> int:
        return dict(self.required_by_role).get(role, 0)


def _rotate(
    pools: dict[str, list[str]],
    order: Iterable[str],
    *,
    limit: int,
    taken: set[str],
    out: list[tuple[str, str]],
    quotas: dict[str, int] | None = None,
) -> None:
    """Take one file at a time from each role in turn, until nothing is left.

    Rotation is the whole point.  Sorting every candidate globally and reading
    the first twelve is what produced eleven documents and no code: by the time
    the reader reached the character cap it had never seen a source file.  Taking
    turns puts each reserved role in front of the reader early enough to be
    read, under exactly the same total budget.
    """
    roles = [role for role in order if pools.get(role)]
    while roles and len(out) < limit:
        progressed = False
        for role in list(roles):
            if len(out) >= limit:
                return
            if quotas is not None and quotas.get(role, 0) <= 0:
                roles.remove(role)
                continue
            pool = pools.get(role) or []
            while pool and pool[0] in taken:
                pool.pop(0)
            if not pool:
                roles.remove(role)
                continue
            path = pool.pop(0)
            taken.add(path)
            out.append((path, role))
            progressed = True
            if quotas is not None:
                quotas[role] -= 1
        if not progressed:
            return


def plan_analysis_evidence(
    relative_paths: Iterable[str],
    *,
    requested_paths: Iterable[str] = (),
    subjects: Iterable[str] = (),
    obligations: Iterable[str] = (),
    profile: str | None = None,
    max_files: int = 12,
) -> AnalysisSelectionPlan:
    """Choose a bounded, role-balanced set of paths for an analysis answer.

    Deterministic over the same inventory: every ordering input is a constant, a
    literal token match or the canonical path, and no iteration order depends on
    hashing.  The repository is never walked here — ``relative_paths`` is the
    inventory production already built.
    """
    resolved_profile = profile if profile in ANALYSIS_EVIDENCE_PROFILES else PROFILE_GENERAL_ANALYSIS
    reservations = profile_reservations(resolved_profile)

    available: dict[str, str] = {}
    for raw in relative_paths or ():
        normalized = str(raw or "").replace("\\", "/").strip("/").casefold()
        if not normalized or normalized.startswith(EXCLUDED_PREFIXES):
            continue
        available.setdefault(normalized, str(raw).replace("\\", "/").strip("/"))

    selections: list[tuple[str, str]] = []
    taken: set[str] = set()

    # 1. Exactly what the user named, in the order they named it.  Strongest,
    #    first, and never displaced to satisfy a quota.
    for requested in requested_paths or ():
        key = str(requested or "").replace("\\", "/").strip("/").casefold()
        if key in available and key not in taken and len(selections) < max_files:
            taken.add(key)
            selections.append((key, ROLE_REQUESTED_PATH))

    # 2. Classify what is left, once.  Subjects lead the token budget; the
    #    obligations follow, because that is where a question keeps the words
    #    that name what it is about ("agent loop", "tool registration").
    tokens = subject_tokens([*(subjects or ()), *(obligations or ())])
    pools: dict[str, list[str]] = {role: [] for role in BALANCED_ROLES}
    for key in available:
        if key in taken:
            continue
        role = classify_evidence_role(key)
        if role is None:
            if tokens and any(token in key for token in tokens):
                pools[ROLE_REQUESTED_SUBJECT].append(key)
            continue
        pools[role].append(key)

    available_by_role = tuple((role, len(pools[role])) for role in BALANCED_ROLES)
    for role in BALANCED_ROLES:
        pools[role].sort(key=lambda path, _role=role: candidate_sort_key(path, _role, tokens))

    # 3. Reserve a per-role minimum, interleaved, before anything is filled.
    quotas = {
        role: min(minimum, len(pools[role]))
        for role, minimum in reservations
    }
    reserved_before = len(selections)
    _rotate(
        pools,
        (role for role, minimum in reservations if minimum > 0),
        limit=max_files,
        taken=taken,
        out=selections,
        quotas=quotas,
    )
    reserved_counts: dict[str, int] = {}
    for _path, role in selections[reserved_before:]:
        reserved_counts[role] = reserved_counts.get(role, 0) + 1

    # 4. Fill what is left.  Roles the profile asked for go first, still by
    #    rotation, so no single role can take every remaining slot; roles the
    #    profile did not ask for may use budget nobody else claimed, which is
    #    how a three-file repository stays sensible without any quota being met.
    _rotate(
        pools,
        (role for role, minimum in reservations if minimum > 0),
        limit=max_files,
        taken=taken,
        out=selections,
    )
    _rotate(
        pools,
        (role for role, minimum in reservations if minimum == 0),
        limit=max_files,
        taken=taken,
        out=selections,
    )

    ordered = tuple((available[key], role) for key, role in selections[:max_files])
    reserved_summary = ", ".join(
        f"{role}>={minimum}" for role, minimum in reservations if minimum > 0
    )
    reason = (
        f"profile={resolved_profile}; reserved {reserved_summary or 'nothing'}; "
        f"selected {len(ordered)} of {max_files} slot(s) from "
        f"{len(available)} in-scope inventory path(s)"
    )
    return AnalysisSelectionPlan(
        profile=resolved_profile,
        selections=ordered,
        available_by_role=available_by_role,
        required_by_role=tuple((role, minimum) for role, minimum in reservations),
        reserved_by_role=tuple(
            (role, reserved_counts.get(role, 0)) for role, _ in reservations
        ),
        selection_reason=reason,
    )


__all__ = [
    "ANALYSIS_EVIDENCE_PROFILES",
    "ANALYSIS_EVIDENCE_ROLE_SCHEMA_VERSION",
    "BALANCED_ROLES",
    "DOCUMENT_DIRECTORIES",
    "DOCUMENT_SUFFIXES",
    "ENTRY_POINT_BASENAMES",
    "EVIDENCE_ROLES",
    "EXCLUDED_PREFIXES",
    "GENERATED_OR_VENDOR_SEGMENTS",
    "MANIFEST_NAMES",
    "MAX_SUBJECT_TOKENS",
    "MIN_SUBJECT_TOKEN_CHARS",
    "PHASE_ID",
    "PROFILE_ARCHITECTURE_IMPLEMENTATION",
    "PROFILE_DEPENDENCY_CONFIGURATION",
    "PROFILE_DOCUMENTATION_EXPLANATION",
    "PROFILE_GENERAL_ANALYSIS",
    "PROFILE_IMPLEMENTATION_DETAIL",
    "PROJECT_DOCUMENT_NAMES",
    "ROLE_ENTRY_POINT",
    "ROLE_IMPLEMENTATION_SOURCE",
    "ROLE_PACKAGE_MANIFEST",
    "ROLE_PROJECT_DOCUMENT",
    "ROLE_REQUESTED_PATH",
    "ROLE_REQUESTED_SUBJECT",
    "ROLE_TEST_EXAMPLE",
    "AnalysisSelectionPlan",
    "candidate_sort_key",
    "classify_evidence_role",
    "derive_evidence_profile",
    "is_document_path",
    "is_generated_or_vendored_path",
    "is_manifest_path",
    "is_source_path",
    "is_test_or_example_path",
    "plan_analysis_evidence",
    "profile_requires_source",
    "profile_reservations",
    "subject_tokens",
]
