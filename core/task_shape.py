"""WAITER.1 — deterministic Task Shape derivation.

The Execution Waiter's first question is not "which workflow?" but "what shape
is this order?".  Shape is descriptive: it says what kind of work the order is,
where its evidence lives, how far it reaches, and how long it runs.  Nothing
here selects a workflow, and nothing here grants anything.

    TaskContract (frozen INPUT.1 product)
        -> TaskShape

The derivation consumes *structured* facts only — the task classification, the
relationships, the execution requirements, and the literal explicit evidence
INPUT.1 already extracted.  It performs no second semantic pass over
``raw_request.text``:

    INPUT says what the order means.
    WAITER determines what capabilities that order requires.

The one place the raw request is touched is
:func:`check_project_evolution_request`, and it is a literal substring identity
check in the spirit of INPUT.1's preservation gate — a claim that the user asked
for an ongoing project-evolution process is checked against the words the user
actually typed.  No meaning is extracted from those words.

Literal backing is necessary and not sufficient.  A caller holding a real span
of the user's prose can still attach an invented label to it, so the same check
also demands that the *declaration itself* be user-authorized: it must come from
a trusted declaration source, it must name the exact preserved request it was
read from, and it must not sit inside a prohibition the user wrote.  "Do not use
Project Evolution; just refactor this architecture" contains the literal words
"Project Evolution" and authorises nothing.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, plans nothing, selects no workflow,
provider or model, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.task_contract import PROVENANCE_EXPLICIT, PROVENANCES, TaskContract


PHASE_ID = "WAITER.1"
TASK_SHAPE_SCHEMA_VERSION = "waiter_1_task_shape_v1"

# ── Task family ───────────────────────────────────────────────────────────────
#: What kind of work the order is.  Every value except ``project_evolution`` is
#: a direct mapping of a frozen ``TaskContract`` task type; the vocabulary is
#: deliberately not a second taxonomy laid over INPUT.1's.
FAMILY_CONVERSATIONAL = "conversational"
FAMILY_EXPLANATORY = "explanatory"
FAMILY_ANALYSIS = "analysis"
FAMILY_COMPARATIVE_ANALYSIS = "comparative_analysis"
FAMILY_RESEARCH = "research"
FAMILY_IMPLEMENTATION = "implementation"
FAMILY_DEBUGGING = "debugging"
FAMILY_REVIEW = "review"
FAMILY_PLANNING = "planning"
#: Reachable only through a verified explicit declaration.  Breadth, difficulty
#: and file count can never promote a task into this family.
FAMILY_PROJECT_EVOLUTION = "project_evolution"
FAMILY_UNKNOWN = "unknown"

TASK_FAMILIES: tuple[str, ...] = (
    FAMILY_CONVERSATIONAL,
    FAMILY_EXPLANATORY,
    FAMILY_ANALYSIS,
    FAMILY_COMPARATIVE_ANALYSIS,
    FAMILY_RESEARCH,
    FAMILY_IMPLEMENTATION,
    FAMILY_DEBUGGING,
    FAMILY_REVIEW,
    FAMILY_PLANNING,
    FAMILY_PROJECT_EVOLUTION,
    FAMILY_UNKNOWN,
)

#: ``TaskContract.task.type`` -> task family.  Total over ``TASK_TYPES``.
_TASK_TYPE_FAMILIES: dict[str, str] = {
    "conversation": FAMILY_CONVERSATIONAL,
    "question": FAMILY_EXPLANATORY,
    "analysis": FAMILY_ANALYSIS,
    "comparative_analysis": FAMILY_COMPARATIVE_ANALYSIS,
    "research": FAMILY_RESEARCH,
    "implementation": FAMILY_IMPLEMENTATION,
    "debugging": FAMILY_DEBUGGING,
    "review": FAMILY_REVIEW,
    "planning": FAMILY_PLANNING,
    "unknown": FAMILY_UNKNOWN,
}

#: Families whose deliverable is the analysis itself.  When such a task needs
#: the repository, the repository *is* the evidence to be surveyed, so it is
#: broad by construction rather than by prompt length.
ANALYSIS_FAMILIES: frozenset[str] = frozenset({
    FAMILY_ANALYSIS,
    FAMILY_COMPARATIVE_ANALYSIS,
    FAMILY_RESEARCH,
    FAMILY_REVIEW,
})

#: Families whose deliverable may be a repository change.
CHANGE_FAMILIES: frozenset[str] = frozenset({
    FAMILY_IMPLEMENTATION,
    FAMILY_DEBUGGING,
})

#: Families whose deliverable is an answer rather than an operation.
ANSWER_FAMILIES: frozenset[str] = frozenset({
    FAMILY_CONVERSATIONAL,
    FAMILY_EXPLANATORY,
    FAMILY_ANALYSIS,
    FAMILY_COMPARATIVE_ANALYSIS,
    FAMILY_RESEARCH,
    FAMILY_REVIEW,
    FAMILY_PLANNING,
})

# ── Interaction shape ─────────────────────────────────────────────────────────
INTERACTION_SINGLE_STAGE = "single_stage"
INTERACTION_MULTI_STAGE = "multi_stage"

INTERACTION_SHAPES: tuple[str, ...] = (
    INTERACTION_SINGLE_STAGE,
    INTERACTION_MULTI_STAGE,
)

# ── Evidence scope ────────────────────────────────────────────────────────────
#: Where the evidence this order needs actually lives.
EVIDENCE_NONE = "none"
EVIDENCE_DIRECT_CONTEXT = "direct_context"
EVIDENCE_BOUNDED_REPOSITORY = "bounded_repository"
EVIDENCE_BROAD_REPOSITORY = "broad_repository"
EVIDENCE_EXTERNAL_INFORMATION = "external_information"
EVIDENCE_MIXED_SOURCES = "mixed_sources"

EVIDENCE_SCOPES: tuple[str, ...] = (
    EVIDENCE_NONE,
    EVIDENCE_DIRECT_CONTEXT,
    EVIDENCE_BOUNDED_REPOSITORY,
    EVIDENCE_BROAD_REPOSITORY,
    EVIDENCE_EXTERNAL_INFORMATION,
    EVIDENCE_MIXED_SOURCES,
)

#: Scopes that require reading the repository at some point downstream.
REPOSITORY_SCOPES: frozenset[str] = frozenset({
    EVIDENCE_BOUNDED_REPOSITORY,
    EVIDENCE_BROAD_REPOSITORY,
    EVIDENCE_MIXED_SOURCES,
})

# ── Change shape ──────────────────────────────────────────────────────────────
CHANGE_NONE = "no_change"
CHANGE_BOUNDED = "bounded_change"
CHANGE_BROAD = "broad_change"

CHANGE_SHAPES: tuple[str, ...] = (CHANGE_NONE, CHANGE_BOUNDED, CHANGE_BROAD)

# ── Analysis shape ────────────────────────────────────────────────────────────
#: Purely descriptive.  ``comparative`` deliberately appears on both CHAT and
#: COMMANDER routes: the noun "compare" never decides a workflow by itself.
ANALYSIS_SIMPLE = "simple"
ANALYSIS_SYNTHESIS = "synthesis"
ANALYSIS_COMPARATIVE = "comparative"
ANALYSIS_INVESTIGATIVE = "investigative"

ANALYSIS_SHAPES: tuple[str, ...] = (
    ANALYSIS_SIMPLE,
    ANALYSIS_SYNTHESIS,
    ANALYSIS_COMPARATIVE,
    ANALYSIS_INVESTIGATIVE,
)

# ── Horizon ───────────────────────────────────────────────────────────────────
HORIZON_IMMEDIATE = "immediate"
HORIZON_BOUNDED_MULTI_STAGE = "bounded_multi_stage"
HORIZON_LONG_RUNNING = "long_running"

HORIZONS: tuple[str, ...] = (
    HORIZON_IMMEDIATE,
    HORIZON_BOUNDED_MULTI_STAGE,
    HORIZON_LONG_RUNNING,
)

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_DECLARATION_CHARS = 400
#: A sha256 hex digest, the identifier INPUT.1 already publishes for a raw
#: request.  Nothing new is manufactured to reference a preserved request.
_SHA256_HEX_CHARS = 64


# ── Explicit project-evolution declaration ────────────────────────────────────
#
# Where a declaration is allowed to have come from.  The vocabulary is bounded
# and split in two on purpose: an untrusted source is *representable* so that a
# caller's honest admission ("I inferred this") can be recorded and refused,
# rather than being unsayable and therefore laundered into a trusted one.

#: The declaration restates evidence INPUT.1 preserved literally.
DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE = "explicit_input_evidence"
#: A human stated the workflow intent for this specific request.
DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT = "human_declared_workflow_intent"

#: The only sources a declaration may be honoured from.
TRUSTED_DECLARATION_SOURCES: tuple[str, ...] = (
    DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE,
    DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
)

#: Sources that may be recorded and may never be honoured.  Every one of them
#: is a way of concluding that an order *feels* long-horizon, and feeling
#: long-horizon is precisely what must not start an ongoing process.
UNTRUSTED_DECLARATION_SOURCES: tuple[str, ...] = (
    "inferred",
    "waiter_inference",
    "model_inference",
    "task_shape_inference",
    "task_complexity",
    "repository_scope",
)

DECLARATION_SOURCES: tuple[str, ...] = (
    TRUSTED_DECLARATION_SOURCES + UNTRUSTED_DECLARATION_SOURCES
)

#: INPUT.1's own kind for a literal prohibition, in ``core.explicit_evidence``.
CONSTRAINT_KIND_PROHIBITION = "prohibition"

# ── Why a project-evolution declaration was not honoured ──────────────────────
#: No declaration was supplied at all.
DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED = (
    "project_evolution_not_explicitly_requested"
)
#: A declaration was supplied from a source that may never authorise one.
DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED = (
    "project_evolution_not_explicitly_authorized"
)
#: The declaration does not name the preserved request it was read from.
DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED = (
    "project_evolution_provenance_unverified"
)
#: The evidence text is not a literal span of the preserved raw request.
DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED = (
    "project_evolution_declaration_not_literally_supported"
)
#: The evidence text is real, and the user wrote it inside a prohibition.
DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NEGATED = (
    "project_evolution_declaration_negated_by_user"
)

PROJECT_EVOLUTION_DISQUALIFIERS: tuple[str, ...] = (
    DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED,
    DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED,
    DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED,
    DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED,
    DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NEGATED,
)


@dataclass(frozen=True, slots=True)
class ProjectEvolutionRequest:
    """A claim that the user asked for an ongoing evolution process.

    INPUT.1's frozen task vocabulary has no value for project-evolution
    lifecycle intent, so WAITER.1 cannot read one off the contract.  Rather
    than infer it — which would make "hard" and "broad" into "ongoing" — the
    declaration is supplied explicitly and then checked, on three axes that a
    careless or hostile caller has to satisfy at once:

    ``evidence_text``
        must be a literal span of the preserved raw request, and must not fall
        inside a prohibition the user wrote.

    ``declared_by``
        must name a trusted declaration source.  Untrusted sources are part of
        the vocabulary so they can be stated and refused; none of them can
        authorise anything.

    ``source_raw_request_sha256``
        must be the fingerprint of the preserved request the evidence was read
        from, so a declaration made about one order cannot be replayed against
        another.

    ``provenance`` may only be ``explicit``.  There is deliberately no inferred
    form of this record: an inferred lifecycle intent is exactly the thing this
    phase must never act on.
    """

    evidence_text: str
    provenance: str = PROVENANCE_EXPLICIT
    declared_by: str = DECLARATION_SOURCE_EXPLICIT_INPUT_EVIDENCE
    source_raw_request_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.provenance not in PROVENANCES:
            raise ValueError(f"unsupported provenance: {self.provenance!r}")
        if self.provenance != PROVENANCE_EXPLICIT:
            raise ValueError(
                "a project-evolution declaration may only be explicit; an inferred "
                "lifecycle intent is not evidence that the user asked for one"
            )
        if self.declared_by not in DECLARATION_SOURCES:
            raise ValueError(
                f"unsupported project-evolution declaration source: {self.declared_by!r}"
            )
        if not self.evidence_text or not self.evidence_text.strip():
            raise ValueError("a project-evolution declaration requires evidence text")
        if len(self.evidence_text) > MAX_DECLARATION_CHARS:
            raise ValueError(
                f"project-evolution evidence exceeds the bound of {MAX_DECLARATION_CHARS}"
            )
        if self.source_raw_request_sha256 is not None and (
            len(self.source_raw_request_sha256) != _SHA256_HEX_CHARS
        ):
            raise ValueError("a source request fingerprint must be a sha256 hex digest")

    @property
    def trusted_source(self) -> bool:
        """Is this declaration allowed to authorise anything at all?"""
        return self.declared_by in TRUSTED_DECLARATION_SOURCES

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_text": self.evidence_text,
            "provenance": self.provenance,
            "declared_by": self.declared_by,
            "trusted_source": self.trusted_source,
            "source_raw_request_sha256": self.source_raw_request_sha256,
        }


@dataclass(frozen=True, slots=True)
class ProjectEvolutionVerification:
    """Whether one declaration may be honoured, and every reason it may not.

    Refusing a declaration is not refusing the order.  The verdict disqualifies
    one workflow; what the order actually needs is decided afterwards, by the
    same rule table that would have run had no declaration been supplied.
    """

    verified: bool
    disqualifiers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for item in self.disqualifiers:
            if item not in PROJECT_EVOLUTION_DISQUALIFIERS:
                raise ValueError(f"unsupported project-evolution disqualifier: {item!r}")
        if self.verified and self.disqualifiers:
            raise ValueError("a verified declaration may not carry disqualifiers")
        if not self.verified and not self.disqualifiers:
            raise ValueError("a refused declaration must state why it was refused")

    def as_dict(self) -> dict[str, Any]:
        return {"verified": self.verified, "disqualifiers": list(self.disqualifiers)}


def _literal_key(value: str) -> str:
    """Casefold and collapse whitespace, changing nothing else.

    This is an identity normaliser, not an interpreter: it lets "the roadmap
    phases" match across a line break without letting it match anything the
    user did not write.
    """
    return " ".join(str(value).split()).casefold()


def _negated_by_the_user(contract: TaskContract, evidence_text: str) -> bool:
    """Did the user write this span inside a prohibition of their own?

    Literal, and scoped the way the words are: a prohibition binds what comes
    after its marker.  "Do not use Project Evolution" negates the span that
    follows ``do not``; "Continue evolving this project ... but do not touch
    database/schema.py" does not, because the span precedes the marker.

    The prohibitions read here are INPUT.1's own literal extraction — marker
    words the user typed — so nothing about meaning is being decided.
    """
    needle = _literal_key(evidence_text)
    if not needle:
        return False
    for constraint in contract.explicit_evidence.constraints:
        if constraint.kind != CONSTRAINT_KIND_PROHIBITION:
            continue
        clause = _literal_key(constraint.text)
        evidence_at = clause.find(needle)
        if evidence_at < 0:
            continue
        marker = _literal_key(constraint.marker)
        if not marker:
            continue
        marker_at = clause.find(marker)
        if 0 <= marker_at <= evidence_at:
            return True
    return False


def check_project_evolution_request(
    contract: TaskContract,
    request: ProjectEvolutionRequest | None,
) -> ProjectEvolutionVerification:
    """May this declaration be honoured?  If not, say every reason why.

    Four independent checks, all of which must pass, evaluated in a fixed order
    so two runs over the same inputs produce the same verdict:

    1. a declaration was supplied at all;
    2. it came from a trusted declaration source;
    3. it names the preserved request it was read from;
    4. its evidence is a literal span of that request, outside any prohibition.

    No meaning is derived from the raw request here.  Checks 3 and 4 are
    substring and fingerprint identities, the same mechanisms INPUT.1's
    preservation gate uses to decide whether an explicit commitment survived.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("check_project_evolution_request requires a TaskContract")
    if request is None:
        return ProjectEvolutionVerification(
            verified=False,
            disqualifiers=(DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_REQUESTED,),
        )
    if not isinstance(request, ProjectEvolutionRequest):
        raise TypeError(
            "check_project_evolution_request requires a ProjectEvolutionRequest or None"
        )

    disqualifiers: list[str] = []

    if not request.trusted_source:
        disqualifiers.append(DISQUALIFIER_PROJECT_EVOLUTION_NOT_EXPLICITLY_AUTHORIZED)
    if request.source_raw_request_sha256 != contract.raw_request.sha256:
        disqualifiers.append(DISQUALIFIER_PROJECT_EVOLUTION_PROVENANCE_UNVERIFIED)

    if _literal_key(request.evidence_text) not in _literal_key(contract.raw_request.text):
        disqualifiers.append(
            DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NOT_LITERALLY_SUPPORTED
        )
    elif _negated_by_the_user(contract, request.evidence_text):
        disqualifiers.append(DISQUALIFIER_PROJECT_EVOLUTION_DECLARATION_NEGATED)

    return ProjectEvolutionVerification(
        verified=not disqualifiers,
        disqualifiers=tuple(disqualifiers),
    )


def verify_project_evolution_request(
    contract: TaskContract,
    request: ProjectEvolutionRequest | None,
) -> bool:
    """Is this declaration backed, authorized, bound and un-negated?

    The boolean face of :func:`check_project_evolution_request`, for callers
    that need the verdict rather than the reasons.  Returns ``False`` for a
    missing declaration and for every refusal.
    """
    return check_project_evolution_request(contract, request).verified


# ── Task shape ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class TaskShape:
    """A bounded, deterministic description of one handoff-ready order.

    Descriptive only.  A shape answers "what is this?"; it never answers "what
    may we do about it?".
    """

    task_family: str
    interaction_shape: str
    evidence_scope: str
    change_shape: str
    analysis_shape: str
    horizon: str
    #: True when a comparison relationship survives on the contract, or the
    #: contract itself classifies the task as comparative.
    comparison_present: bool = False
    #: True when the repository must be surveyed rather than merely opened at a
    #: place the order already identifies.
    broad_repository_scope: bool = False
    #: True when a project-evolution declaration was supplied *and* verified
    #: against the preserved raw request.
    explicit_project_evolution: bool = False
    schema_version: str = TASK_SHAPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for value, allowed, label in (
            (self.task_family, TASK_FAMILIES, "task family"),
            (self.interaction_shape, INTERACTION_SHAPES, "interaction shape"),
            (self.evidence_scope, EVIDENCE_SCOPES, "evidence scope"),
            (self.change_shape, CHANGE_SHAPES, "change shape"),
            (self.analysis_shape, ANALYSIS_SHAPES, "analysis shape"),
            (self.horizon, HORIZONS, "horizon"),
        ):
            if value not in allowed:
                raise ValueError(f"unsupported {label}: {value!r}")
        if self.explicit_project_evolution and self.task_family != FAMILY_PROJECT_EVOLUTION:
            raise ValueError(
                "a verified project-evolution declaration must place the task in the "
                "project_evolution family"
            )
        if self.task_family == FAMILY_PROJECT_EVOLUTION and not self.explicit_project_evolution:
            raise ValueError(
                "the project_evolution family is reachable only through a verified "
                "explicit declaration; breadth may never promote a task into it"
            )
        if self.broad_repository_scope and self.evidence_scope not in REPOSITORY_SCOPES:
            raise ValueError(
                "broad repository scope requires an evidence scope that reads the "
                f"repository, not {self.evidence_scope!r}"
            )
        if self.change_shape != CHANGE_NONE and self.evidence_scope not in REPOSITORY_SCOPES:
            raise ValueError(
                "a repository change requires an evidence scope that reads the "
                f"repository, not {self.evidence_scope!r}"
            )

    @property
    def repository_scope(self) -> bool:
        return self.evidence_scope in REPOSITORY_SCOPES

    @property
    def multi_stage(self) -> bool:
        return self.interaction_shape == INTERACTION_MULTI_STAGE

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "task_family": self.task_family,
            "interaction_shape": self.interaction_shape,
            "evidence_scope": self.evidence_scope,
            "change_shape": self.change_shape,
            "analysis_shape": self.analysis_shape,
            "horizon": self.horizon,
            "comparison_present": self.comparison_present,
            "broad_repository_scope": self.broad_repository_scope,
            "explicit_project_evolution": self.explicit_project_evolution,
        }


# ── Deterministic derivation ──────────────────────────────────────────────────

def _has_comparison(contract: TaskContract, family: str) -> bool:
    """Does a comparison survive as a structured fact?

    Read from the interpreted relationships and the task classification, never
    from the word "compare" appearing somewhere in the prose.
    """
    if family == FAMILY_COMPARATIVE_ANALYSIS:
        return True
    return any(item.type == "comparison" for item in contract.relationships)


def _has_direct_context(contract: TaskContract) -> bool:
    """Did the user hand over the material the answer works on?

    Quoted spans, list items and a supplied framework are content.  A named
    entity is a name, a URL is a pointer somewhere else, and neither is
    evidence the order carries with it.
    """
    evidence = contract.explicit_evidence
    return bool(evidence.quoted_terms or evidence.list_items or evidence.framework)


def _evidence_scope(
    *,
    repository_required: bool,
    external_required: bool,
    broad_repository: bool,
    direct_context: bool,
) -> str:
    if repository_required and external_required:
        return EVIDENCE_MIXED_SOURCES
    if repository_required:
        return EVIDENCE_BROAD_REPOSITORY if broad_repository else EVIDENCE_BOUNDED_REPOSITORY
    if external_required:
        return EVIDENCE_EXTERNAL_INFORMATION
    if direct_context:
        return EVIDENCE_DIRECT_CONTEXT
    return EVIDENCE_NONE


def _analysis_shape(
    *,
    family: str,
    comparison: bool,
    multi_stage: bool,
    evidence_scope: str,
    broad_repository: bool,
) -> str:
    if comparison:
        return ANALYSIS_COMPARATIVE
    if family == FAMILY_DEBUGGING and (multi_stage or broad_repository):
        return ANALYSIS_INVESTIGATIVE
    if family in ANALYSIS_FAMILIES and broad_repository:
        return ANALYSIS_INVESTIGATIVE
    if evidence_scope == EVIDENCE_MIXED_SOURCES or multi_stage:
        return ANALYSIS_SYNTHESIS
    return ANALYSIS_SIMPLE


def _change_shape(*, family: str, evidence_scope: str, broad_repository: bool) -> str:
    if family not in CHANGE_FAMILIES or evidence_scope not in REPOSITORY_SCOPES:
        return CHANGE_NONE
    return CHANGE_BROAD if broad_repository else CHANGE_BOUNDED


def derive_task_shape(
    contract: TaskContract,
    *,
    project_evolution_request: ProjectEvolutionRequest | None = None,
) -> TaskShape:
    """Describe one handoff-ready order, deterministically.

    Every input is a structured fact already established by INPUT: the task
    classification, the surviving relationships, the recorded execution
    requirements, and INPUT.1's literal explicit evidence.  Two runs over the
    same contract always produce the same shape.

    ``project_evolution_request`` is optional and defaults to absent.  Supplying
    one does not make it true: it is verified against the preserved raw request
    before it is honoured.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("derive_task_shape requires a TaskContract")

    requirements = contract.execution_requirements
    multi_stage = bool(requirements.multi_stage)
    repository_required = bool(
        requirements.repository_inspection_required or requirements.local_repository_required
    )
    external_required = bool(requirements.external_information_required)

    evolution_verified = verify_project_evolution_request(contract, project_evolution_request)
    mapped_family = _TASK_TYPE_FAMILIES.get(contract.task.type, FAMILY_UNKNOWN)
    family = FAMILY_PROJECT_EVOLUTION if evolution_verified else mapped_family

    comparison = _has_comparison(contract, mapped_family)

    # Breadth is a property of the work, not of the prompt.  A repository read
    # is broad when the order already needs coordinating across stages, or when
    # the deliverable is an analysis of the repository itself — in which case
    # the code must be surveyed before anything can be said about it.  It is
    # also broad for a declared ongoing evolution process.
    broad_repository = repository_required and (
        multi_stage or mapped_family in ANALYSIS_FAMILIES or evolution_verified
    )

    evidence_scope = _evidence_scope(
        repository_required=repository_required,
        external_required=external_required,
        broad_repository=broad_repository,
        direct_context=_has_direct_context(contract),
    )
    change_shape = _change_shape(
        family=mapped_family,
        evidence_scope=evidence_scope,
        broad_repository=broad_repository,
    )
    analysis_shape = _analysis_shape(
        family=mapped_family,
        comparison=comparison,
        multi_stage=multi_stage,
        evidence_scope=evidence_scope,
        broad_repository=broad_repository,
    )

    if evolution_verified:
        horizon = HORIZON_LONG_RUNNING
    elif multi_stage:
        horizon = HORIZON_BOUNDED_MULTI_STAGE
    else:
        horizon = HORIZON_IMMEDIATE

    return TaskShape(
        task_family=family,
        interaction_shape=(
            INTERACTION_MULTI_STAGE if multi_stage else INTERACTION_SINGLE_STAGE
        ),
        evidence_scope=evidence_scope,
        change_shape=change_shape,
        analysis_shape=analysis_shape,
        horizon=horizon,
        comparison_present=comparison,
        broad_repository_scope=broad_repository,
        explicit_project_evolution=evolution_verified,
    )
