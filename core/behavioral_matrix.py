"""DEFECT.PROBE.LIVE.4/.5 — the behavioral discrimination matrix for one subject.

INDENT.SEMANTICS.1 changes what a case *declares* and appends three cases; it
changes nothing about how a case runs.  Every earlier oracle read the leading
whitespace of every physical line, and for Python that set carries
continuation alignment, string interiors, comment-only and whitespace-only
rows beside the block indentation the subject is about.  The smallest measured
shape::

    def f(a,
          b):
        pass

reads as widths 6 and 4 — a 2-space unit — while its only block step is 4, and
a docstring with a 6-wide interior row does the same.  So each case now names
the language of its *input* — never inferred from the file the function under
test lives in — and carries the reference reading of that input from
:mod:`core.indentation_observation`: tokenize structure for Python, the generic
physical reading, explicitly weaker, for everything else.  The five LIVE.5
cases keep their ids, bytes, expectations, roles and provenance and are
declared Python.  Three fixed preservation cases follow them: the continuation
shape and the docstring shape, both 4space, and one Go sample indented with
tabs, which keeps a reading that only knows Python structure from being
rewarded for answering None on source it cannot structure.

The candidate is still called with the text and nothing else.  The language
travels with the case to the reference path and stops there.

Everything below this paragraph is DEFECT.PROBE.LIVE.5's, unchanged.

DEFECT.PROBE.LIVE.5 appends one case to the matrix this module already builds,
and changes nothing else.  Round-9 black-box evidence measured a candidate that
answers all four LIVE.4 cases and still does not infer the base indentation
unit: it measures the real leading width of each line and then *votes on the
absolute width*, awarding a line four spaces wide to ``4space`` and a line two
spaces wide to ``2space``.  Every LIVE.4 fixture happens to give the right width
family a majority, so the four-case matrix closed for it.

The deterministic diagnostic found the smallest shape where it does not.  One
line at one indentation unit and two at two::

    def level_0():
      if level_1:
        level_2 = 2
        level_3 = 3

Positive indentation widths ``[2, 4, 4]``; the base unit is ``2``; and counting
absolute widths says ``4space`` two votes to one.  So the measured ceiling is::

    base indentation unit != most frequent classified absolute width

and the fifth case closes it.  The expectation is derivable from the bounded
source and from nothing else: within the subject's own classification
vocabulary — ``2space``, ``4space``, ``tab`` — a base unit has to divide every
indentation width in the sample, and ``4`` does not divide ``2``, so an actual
two-space indentation witness leaves ``2space`` as the only value left.  No
style guide, repository convention or user preference is consulted, and
:func:`skew_consistent_units` refuses to build the case at all for a width where
more than one vocabulary value survives — which is why the mirrored ``[4, 8, 8]``
shape is a test control here and never a required production case.

Everything below this paragraph is DEFECT.PROBE.LIVE.4's, unchanged.

DEFECT.PROBE.LIVE.4 — depth-variant behavioral discrimination matrix.

DEFECT.PROBE.LIVE.3 asks two questions of a candidate: did the input the user
complained about start producing the value the user asked for, and did the one
collision partner the same typed fact exposes keep producing what it already
produced.  Round-8 black-box evidence measured a concrete candidate that answers
both correctly and still implements the behavior wrongly::

    ordinary nested 2-space   expected 2space   candidate 2space   PASS
    ordinary nested 4-space   expected 4space   candidate 4space   PASS
    2-space, indented only at depth >= 3   expected 2space   candidate None   FAIL
    4-space, indented only at depth >= 2   expected 4space   candidate None   FAIL

That is a measured ceiling in the oracle, not a hypothesis about one.  The
candidate recognises *absolute* indentation depths — a line indented by exactly
two spaces, a line indented by exactly four — and the subject is the *base
indentation unit*.  A repository does not stop being 2-space because its sample
happens to contain no line indented by exactly two spaces; depths 2, 4, 6, 8 all
belong to the same style.  The two-point oracle cannot see the difference
because both of its cases put a line at exactly one indentation unit in front of
the classifier.

So this phase widens the *oracle*, and only the oracle.  Nothing about probe
execution changes: the same immutable :class:`DefectProbeContract`, the same
static worker, the same single managed sandbox DEFECT.PROBE.LIVE.2 already
creates.  What changes is that the same candidate bytes are asked four bounded
questions instead of two, and the answers are reduced together.

The matrix is deliberately small and deliberately fixed.  It is not property
testing, not fuzzing and not generated coverage: four deterministic cases,
chosen for the one production subject a typed behavioral expectation currently
carries, with stable identifiers and no random values anywhere.  Two of them are
the cases LIVE.3 already ran, byte-for-byte, built by the frozen constructors
that built them before; two are their depth-variant siblings.

Case roles are explicit because they mean different things:

``primary_defect``
    the user's own claim, with the user's own provenance, unchanged.
``defect_generalization``
    the same defect measured across a different valid shape of the same
    subject.  System-derived.  It may fail on the baseline too — that is not a
    second user claim, it is the same behavior family showing itself again.
``preservation``
    behavior the baseline already produced and a fix must not trade away.
``preservation_generalization``
    the same, under the depth-variant shape.

A preservation case keeps LIVE.3's precondition: it is an oracle only where the
baseline already satisfies it, because a counter-case the unpatched repository
already fails proves nothing about a candidate.

Nothing here authors a candidate, ranks a hypothesis, retrieves source, calls a
model, touches the network, walks the repository, widens ``safe_minimal``,
raises a validation budget, or grants any authority.  Matrix evidence is
evidence; ``write_authority``, ``execution_authorized`` and ``approval_ready``
remain exactly where they were.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from core.behavioral_expectation import (
    PROVENANCE_EXPLICIT_USER_FACT,
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
)
from core.candidate_defect_probe import (
    CLOSURE_CHANGED_BUT_UNRESOLVED,
    CLOSURE_FIXED,
    CLOSURE_FIXED_BUT_REGRESSIVE,
    CLOSURE_INCONCLUSIVE,
    CLOSURE_STILL_REPRODUCED,
    CLOSURE_UNAVAILABLE,
    CandidateDefectClosureReceipt,
    evaluate_candidate_defect_closure,
)
from core.defect_probe import (
    EXECUTION_STAGE_PRE_PATCH,
    EXPECTATION_BASIS_TASK_FACT_ADAPTER,
    INPUT_BASIS_TASK_FACT_ADAPTER,
    PROBE_BASIS_TASK_FACT_ADAPTER,
    PROBE_NOT_REPRODUCED,
    PROBE_REPRODUCED,
    DefectProbeContract,
    DefectProbeReceipt,
    ProbeTargetBinding,
    # §6: the same value grammar the primary adapter accepts, imported rather
    # than restated, so the matrix can never be built for a fact the probe it
    # extends would have refused.
    _INDENT_VALUE_RE,
    build_python_function_probe,
    execute_defect_probe,
)
# INDENT.SEMANTICS.1 — the one observation authority.  The matrix only asks it
# to read a case's own fixture under the case's own declared language.
from core.indentation_observation import (
    LANGUAGE_PYTHON,
    STYLE_4SPACE,
    STYLE_TAB,
    SourceIndentationAssessment,
    assess_indentation_observation,
    observe_source_indentation,
)
from core.paired_defect_probe import (
    ORACLE_UNAVAILABLE,
    PAIRED_CHANGED_BUT_UNRESOLVED,
    PAIRED_FIXED,
    PAIRED_FIXED_AND_PRESERVED,
    PAIRED_FIXED_BUT_REGRESSIVE,
    PAIRED_INCONCLUSIVE,
    PAIRED_STILL_REPRODUCED,
    PAIRED_UNAVAILABLE,
    PRESERVATION_PROVENANCE,
    PairedDefectProbeReceipt,
    PreservationCase,
    PreservationCaseResult,
    build_preservation_cases,
    evaluate_paired_defect_closure,
    # §19: the LIVE.3 view of a matrix run is produced by LIVE.3's own
    # resolution rules, imported here rather than re-implemented.  Two copies
    # of "when is a counter-case an oracle at all" could drift into a receipt
    # whose legacy half means something its new half does not.  The per-case
    # rules this module states in its own vocabulary are instead pinned equal
    # to LIVE.3's by test, which proves the agreement rather than assuming it.
    _bound_to_primary,
    _effective_closure_status,
    _oracle_status,
    _resolved_case,
    derive_paired_status,
)


PHASE_ID = "DEFECT.PROBE.LIVE.4"
#: §28.  ``schema_version`` in this repository tags the structural wire shape of
#: a receipt: ``core/content_acquisition.py`` is the precedent, where a receipt
#: whose ``schema_version`` does not match refuses to construct.  Nothing
#: validates or branches on this one, and DEFECT.PROBE.LIVE.5 adds no field a
#: pre-LIVE.5 reader consumed and removes none — it adds an entry to a list that
#: was always variable-length.  So the version is deliberately *not* bumped for
#: a widened oracle, and the phases whose discrimination the matrix carries are
#: named here instead.  A stored LIVE.4 receipt keeps saying exactly what it
#: said: four cases, no skew case, and no claim that LIVE.5 ran.
#:
#: INDENT.SEMANTICS.1 §55 bumps it to ``_v2``, by the same rule that kept
#: ``_v1``: that phase gives *every case record* five fields it never had — the
#: input's declared language and the reference reading's tier, claim strength,
#: fallback reason and value.  Nothing is renamed or removed, so every
#: ``.get()`` reader keeps working, but the serialized case shape grew, and
#: ``core/evidence_verification.py`` is the precedent for saying so with
#: ``_v2``.  A stored ``_v1`` receipt keeps saying exactly what it said: no
#: case in it declared a language, and nothing in it claims this phase ran.
RECEIPT_SCHEMA_VERSION = "behavioral_matrix_live_4_v2"
#: The phases whose bounded discrimination this matrix executes, in order.
#: ``PHASE_ID`` stays the phase that owns the structure; this says what the
#: structure now measures, so a reader can determine from the receipt alone that
#: distribution-skew discrimination was active.
DISCRIMINATION_PHASE_IDS: tuple[str, ...] = (
    "DEFECT.PROBE.LIVE.4",
    "DEFECT.PROBE.LIVE.5",
    "INDENT.SEMANTICS.1",
)

# ── Case roles (§3) ───────────────────────────────────────────────────────────
#: The user's own claim.  Exactly one per matrix.
ROLE_PRIMARY_DEFECT = "primary_defect"
#: The same defect, measured across another valid shape of the same subject.
ROLE_DEFECT_GENERALIZATION = "defect_generalization"
#: Behavior the baseline already had, which a fix must not trade away.
ROLE_PRESERVATION = "preservation"
#: The same, under the depth-variant shape — and, since INDENT.SEMANTICS.1,
#: under the continuation, multi-line string and non-Python shapes.
ROLE_PRESERVATION_GENERALIZATION = "preservation_generalization"
CASE_ROLES: tuple[str, ...] = (
    ROLE_PRIMARY_DEFECT,
    ROLE_DEFECT_GENERALIZATION,
    ROLE_PRESERVATION,
    ROLE_PRESERVATION_GENERALIZATION,
)
#: Roles whose candidate observation must reach the expected value.
DEFECT_ROLES: frozenset[str] = frozenset(
    {ROLE_PRIMARY_DEFECT, ROLE_DEFECT_GENERALIZATION}
)
#: Roles that are an oracle only where the baseline already satisfied them.
PRESERVATION_ROLES: frozenset[str] = frozenset(
    {ROLE_PRESERVATION, ROLE_PRESERVATION_GENERALIZATION}
)

# ── Provenance (§4) ───────────────────────────────────────────────────────────
#: The primary case keeps the user's own provenance, untouched.
MATRIX_PROVENANCE_EXPLICIT_USER = PROVENANCE_EXPLICIT_USER_FACT
#: Derived matrix cases say plainly that the system, not the user, produced
#: them: they follow from the subject's own invariant — that a style is a base
#: unit and not an absolute depth — and from nothing the user said.
MATRIX_PROVENANCE_SUBJECT_INVARIANT = "system_derived_subject_invariant"
#: LIVE.3's provenance for the original preservation case.  Kept for the case
#: LIVE.3 already produced, so a legacy reader sees exactly what it saw.
MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION = PRESERVATION_PROVENANCE
MATRIX_PROVENANCES: tuple[str, ...] = (
    MATRIX_PROVENANCE_EXPLICIT_USER,
    MATRIX_PROVENANCE_SUBJECT_INVARIANT,
    MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION,
)

# ── Per-case baseline vocabulary ──────────────────────────────────────────────
#: The unpatched repository does not produce the case's expected value.
BASELINE_REPRODUCED = "reproduced"
#: The unpatched repository already produces it.
BASELINE_SATISFIED = "satisfied"
BASELINE_INCONCLUSIVE = "inconclusive"
BASELINE_UNAVAILABLE = "unavailable"
BASELINE_STATUSES: tuple[str, ...] = (
    BASELINE_REPRODUCED,
    BASELINE_SATISFIED,
    BASELINE_INCONCLUSIVE,
    BASELINE_UNAVAILABLE,
)

# ── Per-case candidate vocabulary ─────────────────────────────────────────────
CANDIDATE_FIXED = "fixed"
CANDIDATE_STILL_REPRODUCED = "still_reproduced"
CANDIDATE_CHANGED_BUT_UNRESOLVED = "changed_but_unresolved"
CANDIDATE_PRESERVED = "preserved"
CANDIDATE_REGRESSED = "regressed"
CANDIDATE_INCONCLUSIVE = "inconclusive"
CANDIDATE_UNAVAILABLE = "unavailable"
CANDIDATE_STATUSES: tuple[str, ...] = (
    CANDIDATE_FIXED,
    CANDIDATE_STILL_REPRODUCED,
    CANDIDATE_CHANGED_BUT_UNRESOLVED,
    CANDIDATE_PRESERVED,
    CANDIDATE_REGRESSED,
    CANDIDATE_INCONCLUSIVE,
    CANDIDATE_UNAVAILABLE,
)

# ── Matrix result vocabulary (§11) ────────────────────────────────────────────
#: Every required defect case closed and every available preservation case held.
MATRIX_FIXED_AND_PRESERVED = PAIRED_FIXED_AND_PRESERVED
#: A preservation case the baseline already satisfied did not survive.
MATRIX_FIXED_BUT_REGRESSIVE = PAIRED_FIXED_BUT_REGRESSIVE
#: No required defect case closed, and each still produces its baseline value.
MATRIX_STILL_REPRODUCED = PAIRED_STILL_REPRODUCED
#: Some required defect cases closed and at least one did not.  This is the
#: Round-8 ceiling candidate's status, and it is deliberately not ``fixed``.
MATRIX_PARTIALLY_FIXED = "partially_fixed"
#: No required defect case closed, and at least one changed without closing.
MATRIX_UNRESOLVED_FAILURE = "unresolved_matrix_failure"
MATRIX_INCONCLUSIVE = PAIRED_INCONCLUSIVE
MATRIX_UNAVAILABLE = PAIRED_UNAVAILABLE
MATRIX_STATUSES: tuple[str, ...] = (
    MATRIX_FIXED_AND_PRESERVED,
    MATRIX_FIXED_BUT_REGRESSIVE,
    MATRIX_STILL_REPRODUCED,
    MATRIX_PARTIALLY_FIXED,
    MATRIX_UNRESOLVED_FAILURE,
    MATRIX_INCONCLUSIVE,
    MATRIX_UNAVAILABLE,
)
#: The only matrix status that means behavioral closure.  Every reader that
#: must not treat an overfitted candidate as a closed one compares against this.
CLOSING_MATRIX_STATUSES: frozenset[str] = frozenset({MATRIX_FIXED_AND_PRESERVED})

# ── Rejection reasons (§20) ───────────────────────────────────────────────────
REASON_DEFECT_CASE_NOT_CLOSED = "required_defect_case_not_closed"
REASON_PRESERVATION_REGRESSED = "preservation_case_regressed"
REASON_CASE_NO_VERDICT = "matrix_case_reached_no_verdict"
REASON_MATRIX_NOT_EXECUTED = "matrix_was_not_executed"
REASON_CASE_NOT_BOUND = "matrix_case_is_not_bound_to_the_primary_probe"
REASON_SUBJECT_UNSUPPORTED = "subject_has_no_deterministic_behavioral_matrix"
REASON_BASELINE_NOT_SATISFIED = "baseline_did_not_satisfy_the_case"
MATRIX_REJECTION_REASONS: tuple[str, ...] = (
    REASON_DEFECT_CASE_NOT_CLOSED,
    REASON_PRESERVATION_REGRESSED,
    REASON_CASE_NO_VERDICT,
    REASON_MATRIX_NOT_EXECUTED,
    REASON_CASE_NOT_BOUND,
    REASON_SUBJECT_UNSUPPORTED,
    REASON_BASELINE_NOT_SATISFIED,
)


# ── The bounded fixture primitive (§6) ────────────────────────────────────────
#
# ``core.defect_probe._nested_indentation_fixture(width)`` builds the ordinary
# sample at one indentation width and is frozen by
# ``tests/fixtures/defect_fact_live1_frozen_probe_execution.json``.  A
# depth-only sample is the same construction with a different depth sequence, so
# this is that construction with the sequence made explicit rather than a second
# fixture idea: ``indentation_depth_fixture(width)`` reproduces the frozen
# generator byte-for-byte at every width the value grammar accepts, which
# ``tests/test_defect_probe_matrix_live.py`` pins.  Cases A and C keep going
# through the frozen constructors, so their bytes cannot drift at all.
#: The ordinary shape: rise to depth three and come back down.
ORDINARY_DEPTHS: tuple[int, ...] = (0, 1, 2, 3, 3, 2, 1)

#: How deep a depth-only sample may start before the subject adapter gives up.
#: A bound, not a search space: the derivation below stops at the first depth
#: that carries no unit-width evidence, and never explores indentation depth.
MAX_DEPTH_ONLY_START = 4


def indentation_depth_fixture(
    width: int, depths: Sequence[int] = ORDINARY_DEPTHS
) -> str:
    """Deterministic nested text at ``width`` spaces per depth, for ``depths``.

    ``depths`` selects which nesting levels appear at all, which is the whole
    point: a sample whose shallowest indented line sits at depth three has no
    line indented by one unit, and a classifier that recognises absolute depths
    rather than the base unit has nothing to recognise.
    """

    return "".join(
        (" " * (width * depth)) + f"level_{index}\n"
        for index, depth in enumerate(depths)
    )


def depth_only_depths(unit_width: int, collision_widths: Sequence[int]) -> tuple[int, ...]:
    """The shallowest depth-only shape carrying no unit-width evidence.

    ``collision_widths`` are the absolute widths a candidate could be
    recognising instead of the unit — for a typed indentation fact, the two
    widths the fact itself names.  The shape starts at the shallowest depth from
    which neither of its two levels lands on one of them, so the sample can only
    be classified by inferring the *unit*.  Two levels are required: a single
    width is its own base unit, which would make the case unanswerable rather
    than discriminating.

    The result keeps the ordinary fixture's shape — an unindented line, then a
    rise and a fall — so the two families differ in nothing but which nesting
    levels appear.

    ``()`` when no depth within :data:`MAX_DEPTH_ONLY_START` qualifies.  That is
    a truthful "this phase has no depth-variant case for that width", never an
    approximation of one.
    """

    forbidden = {int(value) for value in collision_widths}
    for start in range(2, MAX_DEPTH_ONLY_START + 1):
        if all(unit_width * depth not in forbidden for depth in (start, start + 1)):
            return (0, start, start + 1, start + 1, start)
    return ()


# ── The distribution-skew fixture (DEFECT.PROBE.LIVE.5 §3/§4) ─────────────────
#
# The depth-only family above removes the shallow evidence entirely.  The skew
# family does the opposite: it keeps exactly one line at one indentation unit
# and puts two below it, so direct evidence of the base unit is present and in
# the minority.  One shape, fixed: depth one once, depth two twice.  The
# diagnostic established that 1:2 discriminates, so there is no 1:3 or 1:4
# sibling and nothing here searches for one.
#: Depth one once, depth two twice.  The whole shape.
SKEW_DEPTHS: tuple[int, ...] = (0, 1, 2, 2)

#: §5.  The values this subject's classification vocabulary can return for a
#: space-indented sample.  The skew case's expectation is derived against this
#: closed set and against the fixture's own widths — never against a style
#: guide, a repository convention or anything the user said.
SUBJECT_SPACE_UNITS: tuple[int, ...] = (2, 4)


def indentation_skew_fixture(
    width: int, depths: Sequence[int] = SKEW_DEPTHS
) -> str:
    """Deterministic *parseable* nested Python at ``width`` spaces per depth.

    The same arithmetic as :func:`indentation_depth_fixture` — every depth adds
    exactly ``width`` spaces — with the line bodies made structural so the
    sample is real source rather than a width vector wearing text.  A line whose
    successor sits deeper opens a block; every other line is a statement.  So
    ``SKEW_DEPTHS`` at two spaces is a function holding a branch holding two
    assignments, it parses, and its positive widths are ``[2, 4, 4]``.
    """

    lines: list[str] = []
    for index, depth in enumerate(depths):
        level = int(depth)
        pad = " " * (width * level)
        opens = index + 1 < len(depths) and int(depths[index + 1]) > level
        if opens:
            header = f"def level_{index}():" if level == 0 else f"if level_{index}:"
            lines.append(pad + header)
        else:
            lines.append(f"{pad}level_{index} = {index}")
    return "".join(line + "\n" for line in lines)


def skew_consistent_units(unit_width: int) -> tuple[int, ...]:
    """Which vocabulary units the skew fixture's own widths still admit.

    A base indentation unit has to divide every indentation width in a sample,
    so the widths ``{unit_width, 2 * unit_width}`` admit exactly the members of
    :data:`SUBJECT_SPACE_UNITS` that divide ``unit_width``.  Two spaces admits
    only ``2``, because ``4`` does not divide ``2`` — which is what makes
    ``2space`` the single answer the bounded source itself supports.  Four spaces
    admits both ``2`` and ``4``, because a four-space line is equally consistent
    with a two-space style indented twice, so that shape is genuinely ambiguous
    and :func:`_indentation_matrix_cases` declines to require it.
    """

    if unit_width <= 0:
        return ()
    return tuple(unit for unit in SUBJECT_SPACE_UNITS if unit_width % unit == 0)


# ── Declared input language (INDENT.SEMANTICS.1 §5/§21/§22) ──────────────────
#
# A case's language describes the text the case hands to the function under
# test, never the file that function lives in: ``core/code_dna.py`` is Python,
# and ``_classify_indent`` still classifies Go, TypeScript and HTML for
# ``compute_dna``.  The language reaches the reference reading and nothing else.
#: Every ordinary, depth-only and skew fixture is a Python sample of the
#: subject.  The four ``level_N`` ones tokenize without parsing, which is why
#: the observer is tokenize and not a parser.
INPUT_LANGUAGE_PYTHON = LANGUAGE_PYTHON
INPUT_LANGUAGE_GO = "go"

#: §24 — the measured minimal continuation shape: one row aligned 6 spaces
#: inside brackets and one block step of 4.
CONTINUATION_FIXTURE = "def f(a,\n      b):\n    pass\n"
#: §25 — 4-space block indentation around a docstring whose interior row is 6
#: spaces wide.  It parses; the interior is string content, not a block.
MULTILINE_STRING_FIXTURE = (
    'def f():\n    """Summary.\n      detail\n    """\n    return 1\n'
)
#: §26 — Go indented with tabs.  The generic reading answers ``tab`` and the
#: baseline already does; a reading that knows only Python structure answers
#: ``None``, because braces leave tokenize no block to see.
GO_TAB_FIXTURE = "package main\n\nfunc main() {\n\tif true {\n\t\tprintln(1)\n\t}\n}\n"


def _declared_input_fields(
    input_language: str, reference: SourceIndentationAssessment | None
) -> dict[str, Any]:
    """§29 — what the case's input declared, and how its reference read it.

    Tier and claim strength are reported beside the value and never folded
    into it: a heuristic ``tab`` and a structural ``tab`` are different
    evidence.  No fixture text is repeated here; the case's contract holds it.
    """

    return {
        "input_language": input_language,
        "observation_tier": reference.observation_tier if reference else None,
        "claim_strength": reference.claim_strength if reference else None,
        "fallback_reason": (
            reference.observation.fallback_reason if reference else None
        ),
        "reference_assessment": reference.value if reference else None,
    }


# ── Case and result records ───────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BehavioralMatrixCase:
    """One deterministic case and the bounded contract that runs it."""

    case_id: str
    role: str
    provenance: str
    subject_kind: str
    expected: Any
    contract: DefectProbeContract
    derivation: str
    #: INDENT.SEMANTICS.1 — the language of the text this case hands to the
    #: function under test.  Empty for a case that declares none.
    input_language: str = ""
    #: The reference reading of that text under that language.  Evidence about
    #: the input, carried beside the case; it never reaches the candidate.
    reference: SourceIndentationAssessment | None = None

    def __post_init__(self) -> None:
        if self.role not in CASE_ROLES:
            raise ValueError(f"unsupported matrix case role: {self.role!r}")
        if self.provenance not in MATRIX_PROVENANCES:
            raise ValueError(f"unsupported matrix provenance: {self.provenance!r}")
        if self.role != ROLE_PRIMARY_DEFECT and (
            self.provenance == MATRIX_PROVENANCE_EXPLICIT_USER
        ):
            # §3.  A system-derived case may never be dressed as something the
            # user said; the user said one thing and it is the primary case.
            raise ValueError(
                "only the primary case may carry explicit user provenance"
            )
        if self.reference is not None and (
            self.reference.language != self.input_language
        ):
            # INDENT.SEMANTICS.1 §5 — a reference read under any language but
            # the one the input declares is a reading of some other input.
            raise ValueError("a case reference must read the case's declared language")

    @property
    def is_defect_case(self) -> bool:
        return self.role in DEFECT_ROLES

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "role": self.role,
            "provenance": self.provenance,
            "subject_kind": self.subject_kind,
            "expected": self.expected,
            "derivation": self.derivation,
            **_declared_input_fields(self.input_language, self.reference),
        }


@dataclass(frozen=True, slots=True)
class MatrixCaseResult:
    """Baseline and candidate observations for one matrix case."""

    case_id: str
    role: str
    provenance: str
    subject_kind: str
    expected: Any
    baseline_status: str
    candidate_status: str
    baseline_observed: Any = None
    candidate_observed: Any = None
    baseline_result: str = ""
    candidate_result: str = ""
    reason: str = ""
    #: INDENT.SEMANTICS.1 §29 — carried from the case, unchanged.
    input_language: str = ""
    reference: SourceIndentationAssessment | None = None
    # PATCH.AUTHOR.LIVE.3: bytes from the contract actually executed.
    input_text: str | None = None
    case_probe_fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.role not in CASE_ROLES:
            raise ValueError(f"unsupported matrix case role: {self.role!r}")
        if self.baseline_status not in BASELINE_STATUSES:
            raise ValueError(f"unsupported baseline status: {self.baseline_status!r}")
        if self.candidate_status not in CANDIDATE_STATUSES:
            raise ValueError(f"unsupported candidate status: {self.candidate_status!r}")
        if self.role in DEFECT_ROLES and self.candidate_status in {
            CANDIDATE_PRESERVED,
            CANDIDATE_REGRESSED,
        }:
            raise ValueError("a defect case may not carry a preservation verdict")
        if self.role in PRESERVATION_ROLES and self.candidate_status in {
            CANDIDATE_FIXED,
            CANDIDATE_STILL_REPRODUCED,
            CANDIDATE_CHANGED_BUT_UNRESOLVED,
        }:
            raise ValueError("a preservation case may not carry a defect verdict")

    @property
    def is_preservation_oracle(self) -> bool:
        """§10 — only a case the baseline already satisfied can regress."""

        return self.role in PRESERVATION_ROLES and self.candidate_status in {
            CANDIDATE_PRESERVED,
            CANDIDATE_REGRESSED,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "role": self.role,
            "provenance": self.provenance,
            "subject_kind": self.subject_kind,
            "expected": self.expected,
            "baseline_observed": self.baseline_observed,
            "baseline_result": self.baseline_result,
            "baseline_status": self.baseline_status,
            "candidate_observed": self.candidate_observed,
            "candidate_result": self.candidate_result,
            "candidate_status": self.candidate_status,
            "input_text": self.input_text,
            "case_probe_fingerprint": self.case_probe_fingerprint,
            "reason": self.reason,
            **_declared_input_fields(self.input_language, self.reference),
        }


@dataclass(frozen=True, slots=True)
class BehavioralMatrixReceipt:
    """The LIVE.3 pair as it always read, plus the matrix that supersedes it.

    ``paired`` is a real DEFECT.PROBE.LIVE.3 receipt covering exactly the cases
    LIVE.3 ran, so a reader written before this phase sees what it expects.  Its
    ``paired_status`` and ``defect_closure_status`` are narrowed by the matrix
    where the matrix is stricter — never widened — so no legacy reader can be
    told a candidate closed when the matrix says it did not.
    """

    paired: PairedDefectProbeReceipt
    subject_kind: str
    matrix_status: str
    cases: tuple[MatrixCaseResult, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    timings: dict[str, float] = field(default_factory=dict)
    schema_version: str = RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.matrix_status not in MATRIX_STATUSES:
            raise ValueError(f"unsupported matrix status: {self.matrix_status!r}")

    # ── The LIVE.3 surface, so pipeline and telemetry read unchanged ────────
    @property
    def closure(self) -> CandidateDefectClosureReceipt:
        return self.paired.closure

    @property
    def defect_closure_status(self) -> str:
        return self.paired.defect_closure_status

    @property
    def primary_status(self) -> str:
        return self.paired.primary_status

    @property
    def paired_status(self) -> str:
        return self.paired.paired_status

    @property
    def preservation_oracle_status(self) -> str:
        return self.paired.preservation_oracle_status

    @property
    def matrix_available(self) -> bool:
        return bool(self.cases)

    @property
    def closure_ready(self) -> bool:
        """Evidence-only: the matrix closed.  Not eligibility, not authority."""

        if self.matrix_available:
            return self.matrix_status in CLOSING_MATRIX_STATUSES
        return self.paired.closure_ready

    def case(self, case_id: str) -> MatrixCaseResult | None:
        return next((item for item in self.cases if item.case_id == case_id), None)

    def as_telemetry(self) -> dict[str, Any]:
        payload = self.paired.as_telemetry()
        cases = [item.as_dict() for item in self.cases]
        payload.update(
            {
                "behavioral_matrix_phase_id": PHASE_ID,
                "behavioral_matrix_schema_version": self.schema_version,
                "behavioral_matrix_status": self.matrix_status,
                "behavioral_matrix_subject_kind": self.subject_kind,
                "behavioral_matrix_case_count": len(cases),
                "behavioral_matrix_cases": cases,
                "behavioral_matrix_rejection_reasons": list(self.rejection_reasons),
                "behavioral_matrix_timings": dict(self.timings),
                "behavioral_matrix_authority_effect": "none",
                # §20 — one bounded receipt, so a reader does not have to
                # reassemble the matrix from flat keys to see what was measured.
                "behavioral_matrix": {
                    "phase_id": PHASE_ID,
                    # DEFECT.PROBE.LIVE.5 §27/§28 — additive, inside the one
                    # canonical structure.  No second subtree and no
                    # LIVE.5-specific receipt: a reader asks this list which
                    # bounded discriminations the matrix it is holding ran.
                    "discrimination_phase_ids": list(DISCRIMINATION_PHASE_IDS),
                    "schema_version": self.schema_version,
                    "subject_kind": self.subject_kind,
                    "case_count": len(cases),
                    "cases": cases,
                    "matrix_status": self.matrix_status,
                    "rejection_reasons": list(self.rejection_reasons),
                    "candidate_fingerprint": self.closure.candidate_fingerprint,
                    "probe_fingerprint": self.closure.probe_fingerprint,
                    "authority_effect": "none",
                },
            }
        )
        return payload


# ── The subject adapter (§5) ──────────────────────────────────────────────────

def _indentation_matrix_cases(
    *,
    target: ProbeTargetBinding,
    behavior_fact: BehavioralExpectation,
    primary_contract: DefectProbeContract,
) -> tuple[BehavioralMatrixCase, ...]:
    """The one production subject: eight cases over one indentation fact.

    ``expected_value`` and ``observed_value`` name two widths.  Each contributes
    an ordinary case — the ones LIVE.2 and LIVE.3 already built, reused here
    rather than rebuilt — and one depth-only sibling whose indentation starts
    below no unit-width line, which is the shape the Round-8 candidate could not
    classify.  DEFECT.PROBE.LIVE.5 appends a fifth: the distribution-skew shape
    at the claimed width, which is the shape the Round-9 candidate could not
    classify.  The four LIVE.4 cases keep their identifiers, their contracts and
    their positions; the new one is appended, never inserted.

    INDENT.SEMANTICS.1 declares every one of those a Python input and appends
    three fixed preservation cases after them, the same three for every fact:
    see :func:`_declared_input_cases`.
    """

    expected = _INDENT_VALUE_RE.fullmatch(behavior_fact.expected_value)
    observed = _INDENT_VALUE_RE.fullmatch(behavior_fact.observed_value)
    if expected is None or observed is None:
        return ()
    expected_width = int(expected.group("width"))
    observed_width = int(observed.group("width"))
    if expected_width == observed_width:
        return ()

    # §3/§19 — case C is LIVE.3's preservation case, built by LIVE.3's own
    # adapter.  Reusing it is what keeps the legacy half of the receipt honest:
    # the case a pre-LIVE.4 reader sees is the identical contract, identical
    # fixture bytes and identical case id it would have seen before.
    preservation = build_preservation_cases(target=target, behavior_fact=behavior_fact)
    if len(preservation) != 1:
        return ()
    ordinary_preservation = preservation[0]

    collisions = (expected_width, observed_width)
    deep_defect = depth_only_depths(expected_width, collisions)
    deep_preservation = depth_only_depths(observed_width, collisions)
    if not deep_defect or not deep_preservation:
        return ()
    defect_start = min(depth for depth in deep_defect if depth)
    preservation_start = min(depth for depth in deep_preservation if depth)

    subject = behavior_fact.subject_kind
    cases = [
        BehavioralMatrixCase(
            case_id=f"{subject}.primary.{behavior_fact.expected_value}",
            role=ROLE_PRIMARY_DEFECT,
            provenance=behavior_fact.provenance,
            subject_kind=subject,
            expected=behavior_fact.expected_value,
            contract=primary_contract,
            derivation=(
                "the explicit behavioral claim, probed at the width the user "
                "said the code should produce"
            ),
        ),
        BehavioralMatrixCase(
            case_id=f"{subject}.generalize.{behavior_fact.expected_value}.deep",
            role=ROLE_DEFECT_GENERALIZATION,
            provenance=MATRIX_PROVENANCE_SUBJECT_INVARIANT,
            subject_kind=subject,
            expected=behavior_fact.expected_value,
            contract=_depth_only_contract(
                target=target,
                behavior_fact=behavior_fact,
                width=expected_width,
                depths=deep_defect,
                expected_value=behavior_fact.expected_value,
                role=ROLE_DEFECT_GENERALIZATION,
            ),
            derivation=(
                "subject invariant: a style is a base indentation unit, so the "
                f"same {behavior_fact.expected_value} claim must close for a "
                "sample whose indentation begins only at depth "
                f"{defect_start}"
            ),
        ),
        BehavioralMatrixCase(
            case_id=ordinary_preservation.case_id,
            role=ROLE_PRESERVATION,
            provenance=ordinary_preservation.provenance,
            subject_kind=subject,
            expected=ordinary_preservation.expected,
            contract=ordinary_preservation.contract,
            derivation=ordinary_preservation.derivation,
        ),
        BehavioralMatrixCase(
            case_id=f"{subject}.preserve.{behavior_fact.observed_value}.deep",
            role=ROLE_PRESERVATION_GENERALIZATION,
            provenance=MATRIX_PROVENANCE_SUBJECT_INVARIANT,
            subject_kind=subject,
            expected=behavior_fact.observed_value,
            contract=_depth_only_contract(
                target=target,
                behavior_fact=behavior_fact,
                width=observed_width,
                depths=deep_preservation,
                expected_value=behavior_fact.observed_value,
                role=ROLE_PRESERVATION_GENERALIZATION,
            ),
            derivation=(
                "subject invariant: behavior the baseline already produces for "
                f"{behavior_fact.observed_value} must survive for a sample "
                "whose indentation begins only at depth "
                f"{preservation_start}"
            ),
        ),
    ]

    # DEFECT.PROBE.LIVE.5 §2/§5 — the distribution-skew case, appended last so
    # no historical case moves.  It is required only where the bounded source
    # answers it on its own: the fixture's widths must leave exactly one value
    # of the subject vocabulary standing, which is the claimed width itself.
    # Where more than one survives the shape is ambiguous, and an ambiguous case
    # is omitted rather than decided by preference.
    if skew_consistent_units(expected_width) == (expected_width,):
        cases.append(
            BehavioralMatrixCase(
                case_id=f"{subject}.generalize.{behavior_fact.expected_value}.skew",
                role=ROLE_DEFECT_GENERALIZATION,
                provenance=MATRIX_PROVENANCE_SUBJECT_INVARIANT,
                subject_kind=subject,
                expected=behavior_fact.expected_value,
                contract=_skew_contract(
                    target=target,
                    behavior_fact=behavior_fact,
                    width=expected_width,
                    expected_value=behavior_fact.expected_value,
                ),
                derivation=(
                    "subject invariant: a style is a base indentation unit, not "
                    "the width most of its lines happen to use, so the same "
                    f"{behavior_fact.expected_value} claim must close for a "
                    f"sample carrying one line indented by {expected_width} and "
                    f"two indented by {expected_width * 2}; within the subject "
                    "vocabulary a base unit has to divide every indentation "
                    f"width present, so the {expected_width}-space witness "
                    f"leaves {behavior_fact.expected_value} as the only value "
                    "the sample admits"
                ),
            )
        )

    # INDENT.SEMANTICS.1 §22 — the cases above are built exactly as before and
    # each is a Python sample of the subject; declaring that is what lets the
    # reference path read them by block structure.  Then §24–§28: three fixed
    # cases, appended after every historical one, never inserted between them.
    return tuple(
        [_declared(case, INPUT_LANGUAGE_PYTHON) for case in cases]
        + _declared_input_cases(target=target, behavior_fact=behavior_fact)
    )


def _declared(case: BehavioralMatrixCase, language: str) -> BehavioralMatrixCase:
    """INDENT.SEMANTICS.1 — one case, declaring its input and its reference.

    The reference is read from the case's own fixture under the case's own
    declared language, by the one observation authority.  Nothing about the
    contract changes: same fixture bytes, same expectation, same fingerprint.
    """

    (text,) = case.contract.structured_input["args"]
    return replace(
        case,
        input_language=language,
        reference=assess_indentation_observation(
            observe_source_indentation(text, language=language)
        ),
    )


def _declared_input_cases(
    *,
    target: ProbeTargetBinding,
    behavior_fact: BehavioralExpectation,
) -> list[BehavioralMatrixCase]:
    """INDENT.SEMANTICS.1 §24–§26 — three fixed preservation cases.

    Their fixtures and expected values are constants, not derived from the
    fact, from a candidate or from any reading of them: the continuation shape
    and the docstring shape are 4space because a style is a *block* unit, and
    the Go sample is ``tab`` because that is what the baseline already answers
    and a fix must not trade it away.  The Go case's reference is the generic
    physical reading and says so; it preserves behavior and derives no
    structural expectation of any kind (§30).
    """

    subject = behavior_fact.subject_kind
    requirement = (
        f"not a user requirement: the user's requirement is "
        f"{behavior_fact.expected_value} and it belongs to the primary case"
    )
    specs = (
        (
            f"{subject}.preserve.{STYLE_4SPACE}.continuation",
            MATRIX_PROVENANCE_SUBJECT_INVARIANT,
            STYLE_4SPACE,
            CONTINUATION_FIXTURE,
            INPUT_LANGUAGE_PYTHON,
            (
                "subject invariant: a style is a block indentation unit, so a "
                "Python sample whose only block step is 4 spaces is 4space "
                "however its continuation rows inside brackets are aligned"
            ),
            (
                "the deterministic fixture is valid Python whose only block "
                "step is 4 spaces and whose one continuation row is aligned 6 "
                "spaces inside brackets; alignment inside brackets is not "
                "indentation evidence"
            ),
        ),
        (
            f"{subject}.preserve.{STYLE_4SPACE}.multiline_string",
            MATRIX_PROVENANCE_SUBJECT_INVARIANT,
            STYLE_4SPACE,
            MULTILINE_STRING_FIXTURE,
            INPUT_LANGUAGE_PYTHON,
            (
                "subject invariant: a style is a block indentation unit, so a "
                "Python sample whose only block step is 4 spaces is 4space "
                "whatever widths appear inside its multi-line strings"
            ),
            (
                "the deterministic fixture is valid Python indented 4 spaces "
                "per block around a docstring whose interior row is 6 spaces "
                "wide; text inside a string is not indentation evidence"
            ),
        ),
        (
            f"{subject}.preserve.{STYLE_TAB}.go",
            MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION,
            STYLE_TAB,
            GO_TAB_FIXTURE,
            INPUT_LANGUAGE_GO,
            (
                "compatibility: tab-indented Go is classified tab by the "
                "generic reading the baseline already applies, and a fix must "
                "not trade that away; that reading is heuristic, so the case "
                "preserves behavior and derives no structural expectation"
            ),
            (
                "the deterministic fixture is Go indented with tabs and "
                "declared go, so its reference reading is the generic physical "
                "one and only heuristic; tab is what the unpatched code "
                "already produces"
            ),
        ),
    )
    return [
        _declared(
            BehavioralMatrixCase(
                case_id=case_id,
                role=ROLE_PRESERVATION_GENERALIZATION,
                provenance=provenance,
                subject_kind=subject,
                expected=expected,
                contract=build_python_function_probe(
                    target=target,
                    args=(fixture,),
                    expected=expected,
                    probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
                    input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
                    expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
                    provenance_reference=(
                        f"system-derived {ROLE_PRESERVATION_GENERALIZATION} case "
                        f"for the {subject} subject; {fixture_note}; its "
                        f"expected result {expected} is {requirement}"
                    ),
                    # INDENT.RUNTIME.1 §17 — the same `language` this
                    # comprehension already passes to _declared() below, so
                    # the two can never drift apart.
                    kwargs={"language": language},
                ),
                derivation=derivation,
            ),
            language,
        )
        for (
            case_id,
            provenance,
            expected,
            fixture,
            language,
            derivation,
            fixture_note,
        ) in specs
    ]


def _depth_only_contract(
    *,
    target: ProbeTargetBinding,
    behavior_fact: BehavioralExpectation,
    width: int,
    depths: Sequence[int],
    expected_value: str,
    role: str,
) -> DefectProbeContract:
    """One bounded depth-only contract, built by the frozen probe constructor."""

    return build_python_function_probe(
        target=target,
        args=(indentation_depth_fixture(width, depths),),
        expected=expected_value,
        probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
        input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
        expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
        provenance_reference=(
            f"system-derived {role} case for the {behavior_fact.subject_kind} "
            f"subject; the deterministic fixture uses {width} spaces per depth "
            f"at depths {tuple(depths)}, so no line is indented by exactly one "
            f"unit; its expected result {expected_value} follows from the "
            "subject invariant that a style is a base indentation unit rather "
            "than an absolute depth, and is not a user requirement — the "
            f"user's requirement is {behavior_fact.expected_value} and it "
            "belongs to the primary case"
        ),
        # INDENT.RUNTIME.1 §17 — indentation_depth_fixture is always a
        # Python-shaped sample; _declared() below wraps every case built here
        # with the same INPUT_LANGUAGE_PYTHON.
        kwargs={"language": INPUT_LANGUAGE_PYTHON},
    )


def _skew_contract(
    *,
    target: ProbeTargetBinding,
    behavior_fact: BehavioralExpectation,
    width: int,
    expected_value: str,
) -> DefectProbeContract:
    """One bounded distribution-skew contract, same frozen probe constructor.

    DEFECT.PROBE.LIVE.5 §17/§20 — no new probe primitive, no new fingerprint
    primitive and no second oracle: the same
    :func:`core.defect_probe.build_python_function_probe`, the same bases, the
    same target binding, one different bounded input.
    """

    return build_python_function_probe(
        target=target,
        args=(indentation_skew_fixture(width),),
        expected=expected_value,
        probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
        input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
        expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
        provenance_reference=(
            f"system-derived {ROLE_DEFECT_GENERALIZATION} case for the "
            f"{behavior_fact.subject_kind} subject; the deterministic fixture is "
            f"parseable nested source with one line indented by {width} and two "
            f"by {width * 2}, so the classified width seen most often is not the "
            f"base unit; its expected result {expected_value} follows from the "
            "subject vocabulary itself — a base unit divides every indentation "
            f"width present and only {expected_value} does — and is not a user "
            f"requirement: the user's requirement is "
            f"{behavior_fact.expected_value} and it belongs to the primary case"
        ),
        # INDENT.RUNTIME.1 §17 — indentation_skew_fixture is always a
        # Python-shaped sample; _declared() below wraps this case with the
        # same INPUT_LANGUAGE_PYTHON.
        kwargs={"language": INPUT_LANGUAGE_PYTHON},
    )


#: §5.  Subject → optional deterministic matrix.  A subject absent here has no
#: matrix, which leaves DEFECT.PROBE.LIVE.3's paired semantics exactly as they
#: were and is never a licence to invent cases for it.
_MATRIX_ADAPTERS = {
    SUBJECT_INDENTATION_STYLE: _indentation_matrix_cases,
}


def matrix_subject_supported(subject_kind: Any) -> bool:
    return str(subject_kind or "") in _MATRIX_ADAPTERS


def build_behavioral_matrix(
    *,
    probe_contract: DefectProbeContract | None,
    behavior_fact: BehavioralExpectation | None,
) -> tuple[BehavioralMatrixCase, ...]:
    """The bounded matrix for one typed fact, or nothing at all.

    Empty is the truthful answer for every subject without an adapter, for a
    fact this phase cannot read, and for transport carrying no typed fact.  It
    is never an approximation, and a partially-built matrix is never returned:
    a subject either has all of its required cases or it has none, so a missing
    case can never be mistaken for a case that passed.
    """

    if behavior_fact is None or probe_contract is None:
        return ()
    adapter = _MATRIX_ADAPTERS.get(behavior_fact.subject_kind)
    if adapter is None:
        return ()
    cases = adapter(
        target=probe_contract.target,
        behavior_fact=behavior_fact,
        primary_contract=probe_contract,
    )
    if not cases:
        return ()
    # §22 — every non-primary case must probe the same localized target with a
    # distinct oracle, using DEFECT.PROBE.LIVE.3's own binding rule.  A case
    # that fails it is not demoted to a weaker case; the whole matrix is
    # withdrawn, because a matrix missing one of its required cases is not the
    # matrix this phase reduces.
    if any(
        not _bound_to_primary(
            PreservationCase(
                case_id=case.case_id,
                subject_kind=case.subject_kind,
                expected=case.expected,
                contract=case.contract,
                derivation=case.derivation,
            ),
            probe_contract,
        )
        for case in cases
        if case.role != ROLE_PRIMARY_DEFECT
    ):
        return ()
    if len({case.case_id for case in cases}) != len(cases):
        return ()
    return cases


# ── Per-case resolution ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ProbeObservation:
    """One bounded probe outcome, whatever produced it.

    The primary case's two observations already exist on DEFECT.PROBE.LIVE.2's
    closure receipt, and the companion cases' arrive as
    :class:`DefectProbeReceipt` objects.  Reading both through one small record
    is what lets the primary case be resolved by exactly the same rules as
    every other case without re-running its probe or fabricating a receipt for
    it.
    """

    result: str
    observed: Any = None
    reason: str = ""
    probe_fingerprint: str = ""

    @classmethod
    def of(cls, receipt: DefectProbeReceipt | None) -> "ProbeObservation | None":
        if receipt is None:
            return None
        return cls(
            result=receipt.probe_result,
            observed=receipt.observed,
            reason=receipt.reason,
            probe_fingerprint=receipt.probe_fingerprint,
        )


def _baseline_status(observation: ProbeObservation | None) -> tuple[str, str]:
    if observation is None or not observation.result:
        return BASELINE_UNAVAILABLE, REASON_MATRIX_NOT_EXECUTED
    if observation.result == PROBE_NOT_REPRODUCED:
        return BASELINE_SATISFIED, ""
    if observation.result == PROBE_REPRODUCED:
        return BASELINE_REPRODUCED, ""
    return BASELINE_INCONCLUSIVE, observation.reason or REASON_CASE_NO_VERDICT


def _defect_candidate_status(
    observation: ProbeObservation | None, baseline_observed: Any
) -> tuple[str, str]:
    """§11 — a defect case closes only by producing the expected value."""

    if observation is None or not observation.result:
        return CANDIDATE_UNAVAILABLE, REASON_MATRIX_NOT_EXECUTED
    if observation.result == PROBE_NOT_REPRODUCED:
        return CANDIDATE_FIXED, ""
    if observation.result == PROBE_REPRODUCED:
        if observation.observed == baseline_observed:
            return (
                CANDIDATE_STILL_REPRODUCED,
                "the exact same wrong bounded behavior remains",
            )
        return (
            CANDIDATE_CHANGED_BUT_UNRESOLVED,
            "the candidate changed the observation without reaching the "
            "expected behavior",
        )
    return CANDIDATE_INCONCLUSIVE, observation.reason or REASON_CASE_NO_VERDICT


def _preservation_candidate_status(
    observation: ProbeObservation | None,
) -> tuple[str, str]:
    """§10 — states LIVE.3's rule in this phase's vocabulary.

    ``tests/test_defect_probe_matrix_live.py`` pins it equal to
    ``core.paired_defect_probe._candidate_case_status`` for every probe result,
    so "preserved" and "regressed" cannot come to mean two different things in
    the two halves of the same receipt.
    """

    if observation is None or not observation.result:
        return CANDIDATE_INCONCLUSIVE, REASON_MATRIX_NOT_EXECUTED
    if observation.result == PROBE_NOT_REPRODUCED:
        return CANDIDATE_PRESERVED, ""
    if observation.result == PROBE_REPRODUCED:
        return (
            CANDIDATE_REGRESSED,
            "the candidate lost behavior the baseline already produced",
        )
    return CANDIDATE_INCONCLUSIVE, observation.reason or REASON_CASE_NO_VERDICT


def resolve_matrix_case(
    case: BehavioralMatrixCase,
    baseline: ProbeObservation | None,
    candidate: ProbeObservation | None,
) -> MatrixCaseResult:
    """Close one case over its baseline and its candidate observation."""

    baseline_status, baseline_reason = _baseline_status(baseline)
    baseline_observed = baseline.observed if baseline is not None else None
    baseline_result = baseline.result if baseline is not None else ""

    if case.is_defect_case:
        candidate_status, reason = _defect_candidate_status(candidate, baseline_observed)
    elif baseline_status != BASELINE_SATISFIED:
        # §10 — the baseline does not satisfy this preservation case, so there
        # is nothing here a candidate could have broken.  Refusing the oracle is
        # the only truthful move; counting it would manufacture a regression
        # out of behavior that was already wrong.
        candidate, candidate_status = None, CANDIDATE_UNAVAILABLE
        reason = baseline_reason or REASON_BASELINE_NOT_SATISFIED
    else:
        candidate_status, reason = _preservation_candidate_status(candidate)

    if case.is_defect_case and candidate_status == CANDIDATE_FIXED:
        reason = ""
    # Only carry text when the observation names the immutable contract that
    # was supplied to the worker. No fixture generator or case-id inference.
    input_text = None
    case_probe_fingerprint = ""
    if candidate is not None and candidate.result in {PROBE_REPRODUCED, PROBE_NOT_REPRODUCED}:
        if candidate.probe_fingerprint == case.contract.fingerprint:
            structured = case.contract.structured_input
            args = structured.get("args", []) if isinstance(structured, dict) else []
            kwargs = structured.get("kwargs", {}) if isinstance(structured, dict) else {}
            if (isinstance(args, list) and len(args) == 1 and isinstance(args[0], str)
                    and isinstance(kwargs, dict) and not (set(kwargs) - {"language"})
                    and kwargs.get("language", "") == case.input_language
                    and len(args[0].encode("utf-8")) <= 16_384):
                input_text = args[0]
                case_probe_fingerprint = candidate.probe_fingerprint
    return MatrixCaseResult(
        case_id=case.case_id,
        role=case.role,
        provenance=case.provenance,
        subject_kind=case.subject_kind,
        expected=case.expected,
        baseline_status=baseline_status,
        candidate_status=candidate_status,
        baseline_observed=baseline_observed,
        baseline_result=baseline_result,
        candidate_observed=candidate.observed if candidate is not None else None,
        candidate_result=candidate.result if candidate is not None else "",
        reason=reason,
        input_language=case.input_language,
        reference=case.reference,
        input_text=input_text,
        case_probe_fingerprint=case_probe_fingerprint,
    )


# ── The reduction (§11/§12) ───────────────────────────────────────────────────

def reduce_behavioral_matrix(
    cases: Sequence[MatrixCaseResult],
) -> tuple[str, tuple[str, ...]]:
    """Close the matrix.  Deterministic, fail-closed, in one fixed order.

    1. any preservation case the baseline satisfied and the candidate broke;
    2. no cases at all — nothing was measured;
    3. any required case that reached no verdict;
    4. no defect case closed, and each still produces its baseline value;
    5. no defect case closed, and at least one changed without closing;
    6. some defect cases closed and at least one did not;
    7. every defect case closed and every available preservation case held.

    One passing case never speaks for another.  ``partially_fixed`` exists so
    that a candidate which satisfies the primary claim and fails its own
    subject's invariant cannot be reported as ``fixed`` by rounding.
    """

    reasons: list[str] = []
    if not cases:
        return MATRIX_UNAVAILABLE, (REASON_MATRIX_NOT_EXECUTED,)

    regressed = [item for item in cases if item.candidate_status == CANDIDATE_REGRESSED]
    if regressed:
        return MATRIX_FIXED_BUT_REGRESSIVE, tuple(
            [REASON_PRESERVATION_REGRESSED]
            + [f"{REASON_PRESERVATION_REGRESSED}:{item.case_id}" for item in regressed]
        )

    defects = [item for item in cases if item.role in DEFECT_ROLES]
    undecided = [
        item
        for item in cases
        if item.candidate_status == CANDIDATE_INCONCLUSIVE
        or (item.role in DEFECT_ROLES and item.candidate_status == CANDIDATE_UNAVAILABLE)
    ]
    if not defects or undecided:
        reasons.append(REASON_CASE_NO_VERDICT)
        reasons.extend(f"{REASON_CASE_NO_VERDICT}:{item.case_id}" for item in undecided)
        return MATRIX_INCONCLUSIVE, tuple(reasons)

    open_defects = [item for item in defects if item.candidate_status != CANDIDATE_FIXED]
    if open_defects:
        reasons.append(REASON_DEFECT_CASE_NOT_CLOSED)
        reasons.extend(
            f"{REASON_DEFECT_CASE_NOT_CLOSED}:{item.case_id}" for item in open_defects
        )
        if len(open_defects) != len(defects):
            return MATRIX_PARTIALLY_FIXED, tuple(reasons)
        if any(
            item.candidate_status == CANDIDATE_CHANGED_BUT_UNRESOLVED
            for item in open_defects
        ):
            return MATRIX_UNRESOLVED_FAILURE, tuple(reasons)
        return MATRIX_STILL_REPRODUCED, tuple(reasons)
    return MATRIX_FIXED_AND_PRESERVED, ()


#: §11/§19 — how a matrix status narrows the LIVE.3 fields a pre-LIVE.4 reader
#: already consumes.  Every mapping is at most as permissive as the matrix
#: itself: ``fixed`` is reachable only from ``fixed_and_preserved``.
_MATRIX_TO_PAIRED: dict[str, str] = {
    MATRIX_FIXED_AND_PRESERVED: PAIRED_FIXED_AND_PRESERVED,
    MATRIX_FIXED_BUT_REGRESSIVE: PAIRED_FIXED_BUT_REGRESSIVE,
    MATRIX_PARTIALLY_FIXED: PAIRED_CHANGED_BUT_UNRESOLVED,
    MATRIX_UNRESOLVED_FAILURE: PAIRED_CHANGED_BUT_UNRESOLVED,
    MATRIX_STILL_REPRODUCED: PAIRED_STILL_REPRODUCED,
    MATRIX_INCONCLUSIVE: PAIRED_INCONCLUSIVE,
    MATRIX_UNAVAILABLE: PAIRED_UNAVAILABLE,
}
_MATRIX_TO_CLOSURE: dict[str, str] = {
    MATRIX_FIXED_AND_PRESERVED: CLOSURE_FIXED,
    MATRIX_FIXED_BUT_REGRESSIVE: CLOSURE_FIXED_BUT_REGRESSIVE,
    MATRIX_PARTIALLY_FIXED: CLOSURE_CHANGED_BUT_UNRESOLVED,
    MATRIX_UNRESOLVED_FAILURE: CLOSURE_CHANGED_BUT_UNRESOLVED,
    MATRIX_STILL_REPRODUCED: CLOSURE_STILL_REPRODUCED,
    MATRIX_INCONCLUSIVE: CLOSURE_INCONCLUSIVE,
    MATRIX_UNAVAILABLE: CLOSURE_UNAVAILABLE,
}
_MATRIX_CLOSURE_REASON: dict[str, str] = {
    MATRIX_PARTIALLY_FIXED: (
        "the claimed defect closed and a system-derived case for the same "
        "subject invariant did not"
    ),
    MATRIX_UNRESOLVED_FAILURE: (
        "no bounded case for this subject reached the expected behavior"
    ),
}


# ── Execution ─────────────────────────────────────────────────────────────────

def evaluate_behavioral_closure(
    *,
    repo_path: str | Path,
    candidate_plan: Any,
    probe_contract: DefectProbeContract,
    pre_probe_receipt: DefectProbeReceipt | Mapping[str, Any],
    patch_safety: Mapping[str, Any],
    behavior_fact: BehavioralExpectation | None = None,
    matrix_cases: Sequence[BehavioralMatrixCase] | None = None,
    expected_candidate_fingerprint: str = "",
    sandbox_parent: str | Path | None = None,
) -> PairedDefectProbeReceipt | BehavioralMatrixReceipt:
    """Run the bounded behavioral matrix for one candidate, in one sandbox.

    A subject with no matrix reaches :func:`evaluate_paired_defect_closure`
    unchanged and comes back with a DEFECT.PROBE.LIVE.3 receipt, so every task
    outside the one supported subject keeps exactly the behavior it had.

    With a matrix, the baselines run read-only against the real repository — the
    primary case's baseline is the pre-patch receipt that already reproduced, so
    it is never re-run — and every candidate case runs inside the *one* managed
    sandbox DEFECT.PROBE.LIVE.2 creates, against the same applied bytes, through
    the same static worker.  The added cost is probe executions, never a second
    patch application.
    """

    started = time.perf_counter()
    timings: dict[str, float] = {}
    build_started = time.perf_counter()
    cases = (
        tuple(matrix_cases)
        if matrix_cases is not None
        else build_behavioral_matrix(
            probe_contract=probe_contract, behavior_fact=behavior_fact
        )
    )
    timings["matrix_construction_sec"] = round(time.perf_counter() - build_started, 6)

    if not cases:
        # §18 compatibility — LIVE.3 semantics, unmodified, for every subject
        # this phase has no matrix for.
        return evaluate_paired_defect_closure(
            repo_path=repo_path,
            candidate_plan=candidate_plan,
            probe_contract=probe_contract,
            pre_probe_receipt=pre_probe_receipt,
            patch_safety=patch_safety,
            behavior_fact=behavior_fact,
            expected_candidate_fingerprint=expected_candidate_fingerprint,
            sandbox_parent=sandbox_parent,
        )

    companions = tuple(case for case in cases if case.role != ROLE_PRIMARY_DEFECT)
    safety_ok = isinstance(patch_safety, Mapping) and patch_safety.get("ok") is True

    baselines: dict[str, DefectProbeReceipt] = {}
    if safety_ok:
        baseline_started = time.perf_counter()
        baselines = {
            case.case_id: execute_defect_probe(
                case.contract,
                repo_path=repo_path,
                execution_stage=EXECUTION_STAGE_PRE_PATCH,
            )
            for case in companions
        }
        timings["matrix_baseline_sec"] = round(
            time.perf_counter() - baseline_started, 6
        )

    closure = evaluate_candidate_defect_closure(
        repo_path=repo_path,
        candidate_plan=candidate_plan,
        probe_contract=probe_contract,
        pre_probe_receipt=pre_probe_receipt,
        patch_safety=patch_safety,
        expected_candidate_fingerprint=expected_candidate_fingerprint,
        sandbox_parent=sandbox_parent,
        # §23 — one sandbox.  Every companion contract runs against the bytes
        # the primary post-probe just saw, in the order the matrix declares.
        preservation_probes=tuple(
            (case.case_id, case.contract) for case in companions
        ),
    )
    candidate_receipts = dict(closure.preservation_probe_receipts)
    timings["matrix_candidate_probe_sec"] = float(
        closure.timings.get("preservation_probe_execution_sec", 0.0)
    )

    # §25 — the primary case's two observations already exist on the closure
    # receipt.  DEFECT.PROBE.LIVE.1 took its baseline before any candidate
    # existed, and DEFECT.PROBE.LIVE.2 refused to proceed unless it reproduced,
    # so re-running it would buy a second subprocess and no new fact.
    primary_baseline = ProbeObservation(
        result=closure.pre_probe_result, observed=closure.pre_probe_observed
    )
    primary_candidate = ProbeObservation(
        result=closure.post_probe_result,
        observed=closure.post_probe_observed,
        reason=closure.reason,
        probe_fingerprint=closure.probe_fingerprint,
    )
    reduce_started = time.perf_counter()
    resolved = tuple(
        resolve_matrix_case(
            case,
            (
                primary_baseline
                if case.role == ROLE_PRIMARY_DEFECT
                else ProbeObservation.of(baselines.get(case.case_id))
            ),
            (
                primary_candidate
                if case.role == ROLE_PRIMARY_DEFECT
                else ProbeObservation.of(candidate_receipts.get(case.case_id))
            ),
        )
        for case in cases
    )
    matrix_status, reasons = reduce_behavioral_matrix(resolved)
    timings["matrix_reduction_sec"] = round(time.perf_counter() - reduce_started, 6)
    timings["matrix_total_sec"] = round(time.perf_counter() - started, 6)

    paired = _legacy_paired_receipt(
        cases=cases,
        resolved=resolved,
        closure=closure,
        probe_contract=probe_contract,
        baselines=baselines,
        candidate_receipts=candidate_receipts,
        matrix_status=matrix_status,
    )
    return BehavioralMatrixReceipt(
        paired=paired,
        subject_kind=cases[0].subject_kind,
        matrix_status=matrix_status,
        cases=resolved,
        rejection_reasons=reasons,
        timings=timings,
    )


def _legacy_paired_receipt(
    *,
    cases: Sequence[BehavioralMatrixCase],
    resolved: Sequence[MatrixCaseResult],
    closure: CandidateDefectClosureReceipt,
    probe_contract: DefectProbeContract,
    baselines: Mapping[str, DefectProbeReceipt],
    candidate_receipts: Mapping[str, DefectProbeReceipt],
    matrix_status: str,
) -> PairedDefectProbeReceipt:
    """The DEFECT.PROBE.LIVE.3 view of a matrix run.

    §19 — it covers exactly the cases LIVE.3 ran: the primary case and the one
    ordinary preservation counter-case, resolved by LIVE.3's own rules.  A
    historical receipt is not reinterpreted and a new one does not claim the
    depth-variant cases executed under LIVE.3's vocabulary; they live in the
    matrix block, which is where they were measured.

    The two statuses a legacy reader consumes are then narrowed to the matrix's
    own verdict where the matrix is stricter.  Narrowing only ever removes
    closure: a reader that predates this phase cannot be told the pair closed
    when the matrix says the subject invariant did not.
    """

    legacy_case = next(
        (case for case in cases if case.role == ROLE_PRESERVATION), None
    )
    legacy_results: tuple[PreservationCaseResult, ...] = ()
    if legacy_case is not None:
        baseline = baselines.get(legacy_case.case_id)
        if baseline is not None:
            legacy_results = (
                _resolved_case(
                    PreservationCase(
                        case_id=legacy_case.case_id,
                        subject_kind=legacy_case.subject_kind,
                        expected=legacy_case.expected,
                        contract=legacy_case.contract,
                        derivation=legacy_case.derivation,
                    ),
                    baseline,
                    candidate_receipts.get(legacy_case.case_id),
                ),
            )
    primary_status = closure.defect_closure_status
    paired_status = derive_paired_status(primary_status, legacy_results)
    oracle_status, oracle_reason = (
        _oracle_status(legacy_results)
        if legacy_results
        else (ORACLE_UNAVAILABLE, REASON_MATRIX_NOT_EXECUTED)
    )
    effective, effective_reason = _effective_closure_status(paired_status, primary_status)

    # §11 — the matrix is authoritative.  Where it is stricter than the LIVE.3
    # pair, both legacy statuses take the matrix's verdict; where the pair is
    # already at least as strict, LIVE.3's own wording stands.
    matrix_paired = _MATRIX_TO_PAIRED[matrix_status]
    matrix_closure = _MATRIX_TO_CLOSURE[matrix_status]
    if matrix_paired != paired_status and paired_status in {
        PAIRED_FIXED_AND_PRESERVED,
        PAIRED_FIXED,
    }:
        paired_status = matrix_paired
    if matrix_closure != effective and effective in {CLOSURE_FIXED}:
        effective = matrix_closure
        effective_reason = _MATRIX_CLOSURE_REASON.get(matrix_status, effective_reason)

    return PairedDefectProbeReceipt(
        closure=(
            closure
            if effective == primary_status
            else replace(
                closure,
                defect_closure_status=effective,
                reason=effective_reason or closure.reason,
            )
        ),
        primary_status=primary_status,
        paired_status=paired_status,
        primary_expected=probe_contract.expected,
        preservation_oracle_status=oracle_status,
        preservation_oracle_reason=oracle_reason,
        preservation_cases=legacy_results,
        timings={},
    )


def behavioral_matrix_guardrails() -> dict[str, bool]:
    return {
        "bounded_fixed_case_matrix": True,
        "case_ids_deterministic": True,
        "primary_case_keeps_user_provenance": True,
        "derived_cases_labeled_system_derived": True,
        "depth_variant_cases_omit_unit_width_evidence": True,
        # DEFECT.PROBE.LIVE.5 — one added case, one fixed shape, no search.
        "distribution_skew_case_is_bounded_and_fixed": True,
        "skew_case_expectation_derived_from_bounded_source": True,
        "ambiguous_skew_shape_is_omitted_not_decided": True,
        # INDENT.SEMANTICS.1 — the input declares its language; nothing
        # guesses it, and the candidate never sees it.
        "case_input_language_declared": True,
        "reference_reading_is_language_aware": True,
        "continuation_and_multiline_string_cases_are_fixed": True,
        "non_python_compatibility_case_is_fixed": True,
        "input_language_inferred_from_target_path": False,
        # INDENT.RUNTIME.1 — every case's candidate probe contract now carries
        # kwargs={"language": case.input_language}; see
        # test_every_case_contract_kwargs_language_matches_the_cases_declared_language.
        "candidate_receives_input_language": True,
        "heuristic_reference_labelled_structural": False,
        "preservation_baseline_precondition_required": True,
        "one_candidate_sandbox_for_every_case": True,
        "primary_baseline_reused_not_reprobed": True,
        "matrix_reduction_is_authoritative": True,
        "single_passing_case_can_close_the_matrix": False,
        "randomized_or_generated_cases": False,
        "property_based_testing_added": False,
        "probe_execution_primitive_changed": False,
        "candidate_authoring_changed": False,
        "safe_minimal_changed": False,
        "targeted_validation_budget_changed": False,
        "behavioral_expectation_extraction_changed": False,
        "control_ranking_changed": False,
        "retrieval_changed": False,
        "production_classifier_fixed": False,
        "human_review_eligibility_granted": False,
        "write_authority_granted": False,
        "execution_authorized": False,
        "auto_apply_granted": False,
        "model_called": False,
        "network_called": False,
        "repository_traversal_added": False,
    }


__all__ = [
    "PHASE_ID",
    "RECEIPT_SCHEMA_VERSION",
    "ROLE_PRIMARY_DEFECT",
    "ROLE_DEFECT_GENERALIZATION",
    "ROLE_PRESERVATION",
    "ROLE_PRESERVATION_GENERALIZATION",
    "CASE_ROLES",
    "DEFECT_ROLES",
    "PRESERVATION_ROLES",
    "MATRIX_PROVENANCE_EXPLICIT_USER",
    "MATRIX_PROVENANCE_SUBJECT_INVARIANT",
    "MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION",
    "MATRIX_PROVENANCES",
    "BASELINE_REPRODUCED",
    "BASELINE_SATISFIED",
    "BASELINE_INCONCLUSIVE",
    "BASELINE_UNAVAILABLE",
    "BASELINE_STATUSES",
    "CANDIDATE_FIXED",
    "CANDIDATE_STILL_REPRODUCED",
    "CANDIDATE_CHANGED_BUT_UNRESOLVED",
    "CANDIDATE_PRESERVED",
    "CANDIDATE_REGRESSED",
    "CANDIDATE_INCONCLUSIVE",
    "CANDIDATE_UNAVAILABLE",
    "CANDIDATE_STATUSES",
    "MATRIX_FIXED_AND_PRESERVED",
    "MATRIX_FIXED_BUT_REGRESSIVE",
    "MATRIX_STILL_REPRODUCED",
    "MATRIX_PARTIALLY_FIXED",
    "MATRIX_UNRESOLVED_FAILURE",
    "MATRIX_INCONCLUSIVE",
    "MATRIX_UNAVAILABLE",
    "MATRIX_STATUSES",
    "CLOSING_MATRIX_STATUSES",
    "MATRIX_REJECTION_REASONS",
    "REASON_DEFECT_CASE_NOT_CLOSED",
    "REASON_PRESERVATION_REGRESSED",
    "REASON_CASE_NO_VERDICT",
    "REASON_MATRIX_NOT_EXECUTED",
    "REASON_CASE_NOT_BOUND",
    "REASON_SUBJECT_UNSUPPORTED",
    "ORDINARY_DEPTHS",
    "MAX_DEPTH_ONLY_START",
    "DISCRIMINATION_PHASE_IDS",
    "SKEW_DEPTHS",
    "SUBJECT_SPACE_UNITS",
    "INPUT_LANGUAGE_PYTHON",
    "INPUT_LANGUAGE_GO",
    "CONTINUATION_FIXTURE",
    "MULTILINE_STRING_FIXTURE",
    "GO_TAB_FIXTURE",
    "BehavioralMatrixCase",
    "MatrixCaseResult",
    "BehavioralMatrixReceipt",
    "indentation_depth_fixture",
    "indentation_skew_fixture",
    "depth_only_depths",
    "skew_consistent_units",
    "matrix_subject_supported",
    "build_behavioral_matrix",
    "resolve_matrix_case",
    "reduce_behavioral_matrix",
    "evaluate_behavioral_closure",
    "behavioral_matrix_guardrails",
]
