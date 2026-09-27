"""WAITER.LIVE.1 — live task-shape derivation and change-need separation.

Black-box field tests showed the live runtime sending three unrelated kinds of
order down one road.  "Compare deepseek-harness and C.A.T.T.U.S architecture"
spent twenty-six minutes indexing, ranked an unrelated test file first, and
ended at *cannot safely generate patch because CONTROL did not provide an exact
source snippet* — a sentence that means nothing for a question nobody asked a
patch for.  "Add task priority support" produced a correct five-operation plan
that the defect-grounding gate then had to discard, because a feature request
has no failing test to point at and CONTROL.SAFETY.LIVE.1 rightly refuses to
invent one.

Both failures have the same cause: production had no place to say *what kind of
order this is* before it started looking for something to patch.  This module is
that place.

    raw user task  (+ already-available explicit production facts)
        -> live compatibility adapter          [here]
        -> TaskContract                        [core.input_understanding]
        -> TaskShape                           [core.task_shape,   WAITER.1]
        -> CapabilityRequirements              [core.capability_requirements]
        -> LiveTaskShape                       [here]

Three properties are load-bearing.

**Deterministic.**  Nothing here calls a model, opens a socket, walks a
repository or builds a graph.  The classification reads literal marker words the
user typed and the structured facts INPUT.1 already extracted from them.  Two
runs over the same prompt always produce the same shape, on any machine, with
any repository state and no network.

**A live compatibility adapter, not an authoritative semantic replacement.**
INPUT.2's model-backed Semantic Waiter is not wired into the live runtime, and
INPUT.3's handoff receipt requires evidence of a semantic model call that the
live path cannot produce without adding one.  So the adapter reuses everything
that *is* live-available — INPUT.1's literal evidence extractor, its
deterministic interpreter, its preservation gate, and WAITER.1's shape and
capability derivation — and supplies only the two fields the frozen
deterministic interpreter cannot derive: the task classification and the
execution requirements.  It never re-interprets meaning INPUT already
established, and it is not a second semantic system.

**A shape is not an authority.**  ``change_requested=True`` records that the
user asked for a change.  It does not establish a target, a patch, a path, an
apply permission, a passing validation or a human approval, and it never sets
``defect_established``.  Those remain exactly where CONTROL.SAFETY.LIVE.1,
patch safety, CTX.PATCH/CTX.APPLY and the runtime authorization gates left them.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, indexes nothing, plans nothing, selects
no provider or model, and grants no authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.behavioral_expectation import (
    BehavioralExpectation,
    bind_obligation_ordinals,
    supported_behavior_facts,
)
from core.capability_requirements import (
    CapabilityRequirements,
    derive_capability_requirements,
)
from core.explicit_evidence import ExplicitEvidence
from core.input_understanding import understand_request
from core.obligation_preservation import (
    MAX_OBLIGATION_UNITS,
    ObligationSet,
    derive_obligation_set,
)
from core.semantic_waiter import (
    ExplicitEvidenceInterpreter,
    SemanticInterpretation,
)
from core.task_contract import (
    PROVENANCE_INFERRED,
    ExecutionRequirements,
    TaskClassification,
    TaskContract,
)
from core.task_shape import (
    ANSWER_FAMILIES,
    FAMILY_DEBUGGING,
    FAMILY_IMPLEMENTATION,
    TaskShape,
    derive_task_shape,
)


PHASE_ID = "WAITER.LIVE.1"
LIVE_TASK_SHAPE_SCHEMA_VERSION = "waiter_live_1_task_shape_v1"

#: Stamped on every adapter product.  The label is the promise: these fields
#: exist so a frozen contract can be consumed live, not so a second meaning of
#: the user's words can be manufactured beside INPUT's.
ADAPTER_KIND = "live compatibility adapter"

# ── Live task shapes ──────────────────────────────────────────────────────────
#: Four, and no more.  Each one changes what production may do next; a fifth
#: that did not would be description rather than routing.

#: The deliverable is an answer.  No repository change was requested.
SHAPE_ANALYSIS_ONLY = "analysis_only"
#: The user claims something is currently wrong and asks for it to be repaired.
SHAPE_DEFECT_REPAIR = "defect_repair"
#: The user asks for a change that no pre-existing defect has to justify.
SHAPE_EXPLICIT_CHANGE = "explicit_change"
#: Deterministic classification cannot preserve the user's intent safely.
SHAPE_NEEDS_CLARIFICATION = "needs_clarification"

LIVE_TASK_SHAPES: tuple[str, ...] = (
    SHAPE_ANALYSIS_ONLY,
    SHAPE_DEFECT_REPAIR,
    SHAPE_EXPLICIT_CHANGE,
    SHAPE_NEEDS_CLARIFICATION,
)

#: Shapes whose deliverable may be a repository change.
CHANGE_SHAPES: frozenset[str] = frozenset({SHAPE_DEFECT_REPAIR, SHAPE_EXPLICIT_CHANGE})

# ── Change-need source ────────────────────────────────────────────────────────
#: *Why* a change is needed — never *whether* one may be written.  The vocabulary
#: is bounded and deliberately has no probability in it.

#: No change was requested at all.
CHANGE_NEED_NONE = "none"
#: The user asked for the change.  This establishes the need and nothing else.
CHANGE_NEED_EXPLICIT_USER_REQUEST = "explicit_user_request"
#: Independently executed failure evidence established a defect.  Only
#: CONTROL.SAFETY.LIVE.1 may set this, and only from OPS.VALIDATE.1 facts.
CHANGE_NEED_GROUNDED_DEFECT = "grounded_defect"
#: A change may be needed and nothing has established why yet.
CHANGE_NEED_UNRESOLVED = "unresolved"

CHANGE_NEED_SOURCES: tuple[str, ...] = (
    CHANGE_NEED_NONE,
    CHANGE_NEED_EXPLICIT_USER_REQUEST,
    CHANGE_NEED_GROUNDED_DEFECT,
    CHANGE_NEED_UNRESOLVED,
)

# ── Reason codes ──────────────────────────────────────────────────────────────
REASON_ANALYSIS_NO_CHANGE_REQUESTED = "analysis_no_change_requested"
REASON_DEFECT_CLAIM_PRESENT = "defect_claim_present"
REASON_EXPLICIT_CHANGE_REQUEST = "explicit_change_request"
REASON_MIXED_OBLIGATIONS = "mixed_ordered_obligations"
REASON_NO_DETERMINABLE_OBLIGATION = "no_determinable_obligation"
REASON_PRESERVATION_FAILED = "explicit_requirement_preservation_failed"
REASON_EMPTY_REQUEST = "empty_request"

LIVE_SHAPE_REASONS: tuple[str, ...] = (
    REASON_ANALYSIS_NO_CHANGE_REQUESTED,
    REASON_DEFECT_CLAIM_PRESENT,
    REASON_EXPLICIT_CHANGE_REQUEST,
    REASON_MIXED_OBLIGATIONS,
    REASON_NO_DETERMINABLE_OBLIGATION,
    REASON_PRESERVATION_FAILED,
    REASON_EMPTY_REQUEST,
)

LIVE_SHAPE_REASON_DESCRIPTIONS: dict[str, str] = {
    REASON_ANALYSIS_NO_CHANGE_REQUESTED: (
        "The order asks for an explanation, comparison, review or summary and "
        "requests no repository change."
    ),
    REASON_DEFECT_CLAIM_PRESENT: (
        "The order states that something is currently wrong, or asks for a repair. "
        "The claim selects the defect route; only executed failure evidence can "
        "establish that the claim is true."
    ),
    REASON_EXPLICIT_CHANGE_REQUEST: (
        "The user literally asked for a change. The request establishes why a "
        "change is needed; it establishes nothing about what may be written."
    ),
    REASON_MIXED_OBLIGATIONS: (
        "The order carries an analysis obligation and a change obligation in "
        "separate ordered clauses. Neither half may be dropped, and one live route "
        "cannot execute both."
    ),
    REASON_NO_DETERMINABLE_OBLIGATION: (
        "No analysis subject, defect claim or change request could be read from the "
        "words the user wrote."
    ),
    REASON_PRESERVATION_FAILED: (
        "INPUT.1's preservation gate reports that an explicit commitment did not "
        "survive interpretation, so routing fails closed."
    ),
    REASON_EMPTY_REQUEST: "The request is empty.",
}

# ── Bounds ────────────────────────────────────────────────────────────────────
#: INPUT.PRESERVE.LIVE.1 owns the obligation bound now, and it counts *units*
#: rather than characters.  ``MAX_OBLIGATION_CHARS`` used to cap each clause at
#: 240 characters, which is how the live T5 request lost ``tool``, ``plugin``,
#: ``lifecycle``, ``context`` and ``retrieval`` from a 352-character clause.
#: The 240 survives as :data:`core.obligation_preservation.OBLIGATION_PREVIEW_CHARS`,
#: where it abbreviates a display string and nothing else.
MAX_OBLIGATIONS = MAX_OBLIGATION_UNITS
MAX_MARKERS = 12
MAX_MARKER_SCAN_CHARS = 100_000


# ── Literal marker vocabulary ─────────────────────────────────────────────────
#
# Marker words, in the spirit of ``core.explicit_evidence``: every one of them is
# a span the user actually typed.  Nothing here is natural-language
# understanding, nothing is weighted, and nothing consults a model.  A marker
# that does not appear contributes nothing; a marker that appears contributes
# exactly one fact.

def _word_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    body = "|".join(re.escape(word) for word in words)
    return re.compile(rf"(?<![\w-])(?:{body})(?![\w-])", re.I)


#: A claim that something is *currently wrong*.
DEFECT_CLAIM_MARKERS: tuple[str, ...] = (
    "bug", "bugs", "buggy", "defect", "defects", "regression", "regressions",
    "broken", "breaks", "breaking",
    "crash", "crashes", "crashed", "hangs", "deadlock",
    "traceback", "stack trace", "exception", "exceptions",
    "assertionerror", "typeerror", "nameerror", "syntaxerror",
    "modulenotfounderror", "valueerror", "keyerror", "indexerror",
    "nullreferenceexception", "segfault",
    "error", "errors", "failure", "failures",
    "fail", "fails", "failed", "failing",
    "wrong", "incorrect", "misbehaves", "misbehaving",
    "not working", "doesn't work", "does not work", "isn't working",
    "is not working", "no longer works", "stopped working",
    "should return", "returns the wrong", "off by one",
    # Vietnamese, matching the vocabulary production already recognises.
    "lỗi", "sai", "hỏng", "không chạy", "không hoạt động",
)

#: An imperative to repair.  Separated from the claim markers because "fix" is
#: the one repair verb users write without ever describing the symptom.
DEFECT_REPAIR_MARKERS: tuple[str, ...] = (
    "fix", "fixes", "fixed", "repair", "repairs", "debug", "troubleshoot",
    "sửa", "khắc phục",
)

#: A request to change the code that no pre-existing defect has to justify.
EXPLICIT_CHANGE_MARKERS: tuple[str, ...] = (
    "add", "adds", "implement", "implements", "create", "introduce",
    "refactor", "refactors", "rename", "renames", "migrate", "migration",
    "port", "convert", "rewrite", "restructure",
    "extend", "extends", "remove", "delete", "drop", "replace",
    "wire", "integrate", "enable", "disable",
    "split", "extract", "inline",
    "upgrade", "downgrade", "backport",
    # Vietnamese, matching the vocabulary production already recognises.
    "thêm", "tạo", "tích hợp", "xoá", "xóa", "chuyển",
)

# These verbs also occur as nouns or descriptions ("what would change?",
# "review the update"). Read them as requests only in directive position,
# including ordinary polite requests; their mere presence is not intent.
_DIRECTIVE_CHANGE_MARKERS = (
    "change", "update", "modify", "edit", "adjust",
    "thay đổi", "cập nhật", "điều chỉnh",
)
_DIRECTIVE_PREFIX_RE = re.compile(
    r"(?:^\s*|[.!?;,\n]\s*|\b(?:then|but|and)\s+)"
    r"(?:(?:please|hãy|vui lòng)\s+|"
    r"(?:can|could|would|will)\s+you\s+(?:please\s+)?|"
    r"i\s+(?:want|need)\s+(?:you\s+)?to\s+)?$",
    re.I,
)
_NEGATED_ACTION_PREFIX_RE = re.compile(
    r"\b(?:do\s+not|don['’]t|must\s+not|should\s+not|never|avoid|without|đừng|không)"
    r"\s+(?:[\w'-]+\s+){0,3}$",
    re.I,
)

#: A request whose deliverable is the answer itself.
ANALYSIS_MARKERS: tuple[str, ...] = (
    "explain", "explains", "explanation", "describe", "description",
    "compare", "compares", "comparison", "contrast", "versus", "vs",
    "summarize", "summarise", "summary", "overview",
    "analyze", "analyse", "analysis", "review", "audit", "assess", "evaluate",
    "walk me through", "walk through", "how does", "how do", "how is",
    "what is", "what does", "what are", "why does", "why is", "why do",
    "where is", "where does", "outline", "document how",
    "tell me", "show me how", "understand",
    # Vietnamese.
    "giải thích", "so sánh", "tóm tắt", "phân tích", "tổng quan",
)

_DEFECT_CLAIM_RE = _word_pattern(DEFECT_CLAIM_MARKERS)
_DEFECT_REPAIR_RE = _word_pattern(DEFECT_REPAIR_MARKERS)
_ANALYSIS_RE = _word_pattern(ANALYSIS_MARKERS)

#: The change verbs, refused in call position.  ``add(2, 2) returns 0`` names a
#: function; it does not ask for one to be added, and reading it as a feature
#: request would send the calc.py defect down the wrong road.
_CHANGE_RE = re.compile(
    r"(?<![\w-])(?:"
    + "|".join(
        re.escape(word)
        for word in (*EXPLICIT_CHANGE_MARKERS, *_DIRECTIVE_CHANGE_MARKERS)
    )
    + r")(?![\w-])(?!\s*\()",
    re.I,
)

#: Sequencing the user wrote themselves is split by INPUT.PRESERVE.LIVE.1 now,
#: so production holds exactly one clause splitter rather than two that can
#: drift apart.  See :func:`core.obligation_preservation.split_obligation_clauses`.


@dataclass(frozen=True, slots=True)
class TaskNeedMarkers:
    """The literal marker spans one request contains, in the order written.

    Evidence, not a verdict.  The record exists so a route can be explained by
    quoting the user rather than by citing a score.
    """

    defect_claims: tuple[str, ...] = ()
    defect_repairs: tuple[str, ...] = ()
    explicit_changes: tuple[str, ...] = ()
    analyses: tuple[str, ...] = ()

    @property
    def defect_claim_present(self) -> bool:
        return bool(self.defect_claims or self.defect_repairs)

    @property
    def change_request_present(self) -> bool:
        return bool(self.explicit_changes)

    @property
    def analysis_present(self) -> bool:
        return bool(self.analyses)

    def as_dict(self) -> dict[str, Any]:
        return {
            "defect_claims": list(self.defect_claims),
            "defect_repairs": list(self.defect_repairs),
            "explicit_changes": list(self.explicit_changes),
            "analyses": list(self.analyses),
        }


def _bounded_matches(pattern: re.Pattern[str], text: str) -> tuple[str, ...]:
    seen: list[str] = []
    keys: set[str] = set()
    for match in pattern.finditer(text):
        value = match.group(0)
        key = value.casefold()
        if key in keys:
            continue
        keys.add(key)
        seen.append(value)
        if len(seen) >= MAX_MARKERS:
            break
    return tuple(seen)


def extract_need_markers(text: str) -> TaskNeedMarkers:
    """Read the literal change/defect/analysis markers out of one span."""
    scanned = str(text or "")[:MAX_MARKER_SCAN_CHARS]
    return TaskNeedMarkers(
        defect_claims=_bounded_matches(_DEFECT_CLAIM_RE, scanned),
        defect_repairs=_bounded_matches(_DEFECT_REPAIR_RE, scanned),
        explicit_changes=_change_request_matches(scanned),
        analyses=_bounded_matches(_ANALYSIS_RE, scanned),
    )


def _change_request_matches(text: str) -> tuple[str, ...]:
    """Keep action spans, without turning a prohibition or noun into a request."""
    changes: list[str] = []
    seen: set[str] = set()
    for match in _CHANGE_RE.finditer(text):
        marker = match.group(0)
        key = marker.casefold()
        prefix = text[max(0, match.start() - 200):match.start()]
        if _NEGATED_ACTION_PREFIX_RE.search(prefix):
            continue
        if key in _DIRECTIVE_CHANGE_MARKERS and not _DIRECTIVE_PREFIX_RE.search(prefix):
            continue
        if key not in seen:
            seen.add(key)
            changes.append(marker)
        if len(changes) >= MAX_MARKERS:
            break
    return tuple(changes)


def split_obligations(text: str) -> tuple[str, ...]:
    """The authoritative obligations of one request, in the order written.

    Delegates to INPUT.PRESERVE.LIVE.1.  Nothing is reworded, reordered,
    summarised or cut at a character count: a clause too long for one unit is
    sub-divided at a boundary the user wrote, and every word survives.

    "Compare X, then recommend Y" still keeps both halves and keeps them that
    way round.
    """
    return derive_obligation_set(text).values


def _obligation_kinds(obligations: tuple[str, ...]) -> tuple[frozenset[str], ...]:
    kinds: list[frozenset[str]] = []
    for clause in obligations:
        markers = extract_need_markers(clause)
        found: set[str] = set()
        if markers.defect_claim_present:
            found.add(SHAPE_DEFECT_REPAIR)
        if markers.change_request_present:
            found.add(SHAPE_EXPLICIT_CHANGE)
        if markers.analysis_present:
            found.add(SHAPE_ANALYSIS_ONLY)
        kinds.append(frozenset(found))
    return tuple(kinds)


def has_mixed_obligations(obligations: tuple[str, ...]) -> bool:
    """Does the order carry an answer obligation and a change obligation apart?

    Only *separate* clauses count.  "Fix this bug" states a defect claim and a
    repair imperative in one breath and is one obligation; "explain how
    validation works, then fix the pytest detection bug" is two, and no single
    live route executes both.
    """
    kinds = _obligation_kinds(obligations)
    analysis_at = {
        index
        for index, found in enumerate(kinds)
        if found == {SHAPE_ANALYSIS_ONLY}
    }
    change_at = {
        index
        for index, found in enumerate(kinds)
        if found & {SHAPE_DEFECT_REPAIR, SHAPE_EXPLICIT_CHANGE}
    }
    return bool(analysis_at and change_at and analysis_at != change_at)


# ── The live compatibility adapter ────────────────────────────────────────────

#: ``live task shape -> INPUT.1 task type``.  The live vocabulary is mapped onto
#: INPUT.1's frozen ``TASK_TYPES`` rather than laid beside it, so WAITER.1's
#: existing family table, capability derivation and workflow policy all apply
#: unchanged.
_SHAPE_TASK_TYPES: dict[str, str] = {
    SHAPE_ANALYSIS_ONLY: "analysis",
    SHAPE_DEFECT_REPAIR: "debugging",
    SHAPE_EXPLICIT_CHANGE: "implementation",
    SHAPE_NEEDS_CLARIFICATION: "unknown",
}

#: Answer task types INPUT.1's own deterministic interpreter already decided
#: *from something the user wrote*.  When it has read one of these off the
#: words, the adapter keeps it — a comparison stays a comparison rather than
#: being flattened to "analysis".
#:
#: ``conversation`` is deliberately absent.  INPUT.1 reports it when the request
#: contains no explicit evidence at all, which is exactly the ambiguous case:
#: "Improve the agent." names no subject, no defect and no change, and reading
#: its emptiness as "an analysis was requested" would answer a question nobody
#: asked.  It falls through to ``needs_clarification`` instead.
_PRESERVED_ANSWER_TASK_TYPES: frozenset[str] = frozenset(
    {"comparative_analysis", "question", "review", "research"}
)


def classify_live_shape(
    raw_text: str,
    *,
    interpreted_task_type: str | None = None,
) -> tuple[str, tuple[str, ...], TaskNeedMarkers, ObligationSet]:
    """Deterministically decide which of the four live shapes an order is.

    Returns ``(shape, reasons, markers, obligation_set)``.  The obligation set
    is INPUT.PRESERVE.LIVE.1's authoritative record, derived once here and read
    by the preservation gate and every downstream consumer alike.

    Mixed-obligation detection reads the set's *clauses* — the user's own
    sequencing — never its units.  A long clause that INPUT.PRESERVE sub-divides
    for transport is still one order, and sub-division must not manufacture a
    clarification route.

    Precedence, applied in
    a fixed order so two runs over the same prompt always agree:

    0. an empty request                        -> needs_clarification
    1. an answer obligation and a change
       obligation in separate clauses          -> needs_clarification
    2. a defect claim or a repair imperative   -> defect_repair
    3. an explicit change request              -> explicit_change
    4. an analysis marker, or an answer task
       type INPUT already read off the words   -> analysis_only
    5. anything else                           -> needs_clarification

    Rule 2 sits above rule 3 because "fix this bug" asks for both and the defect
    route is the one that demands evidence before it patches.  Rule 5 is the
    fail-closed default: an order nobody can read is never a patch target.
    """
    text = str(raw_text or "")
    if not text.strip():
        return (
            SHAPE_NEEDS_CLARIFICATION,
            (REASON_EMPTY_REQUEST,),
            TaskNeedMarkers(),
            ObligationSet(),
        )

    obligations = derive_obligation_set(text)
    markers = extract_need_markers(text)

    if has_mixed_obligations(obligations.clauses):
        return (
            SHAPE_NEEDS_CLARIFICATION,
            (REASON_MIXED_OBLIGATIONS,),
            markers,
            obligations,
        )

    if markers.defect_claim_present:
        return SHAPE_DEFECT_REPAIR, (REASON_DEFECT_CLAIM_PRESENT,), markers, obligations

    if markers.change_request_present:
        return (
            SHAPE_EXPLICIT_CHANGE,
            (REASON_EXPLICIT_CHANGE_REQUEST,),
            markers,
            obligations,
        )

    if markers.analysis_present or (
        interpreted_task_type in _PRESERVED_ANSWER_TASK_TYPES
    ):
        return (
            SHAPE_ANALYSIS_ONLY,
            (REASON_ANALYSIS_NO_CHANGE_REQUESTED,),
            markers,
            obligations,
        )

    return (
        SHAPE_NEEDS_CLARIFICATION,
        (REASON_NO_DETERMINABLE_OBLIGATION,),
        markers,
        obligations,
    )


class LiveTaskFieldsInterpreter:
    """A live compatibility adapter over INPUT.1's deterministic interpreter.

    It delegates every field INPUT.1 can already derive — subjects,
    relationships, framework, requested output, constraints — to
    :class:`~core.semantic_waiter.ExplicitEvidenceInterpreter`, and replaces
    exactly two:

    ``task``
        the frozen deterministic interpreter has no rule that yields
        ``implementation`` or ``debugging``, because INPUT.2's model was meant
        to supply those and is not live.  The replacement is derived from
        literal marker words, never from a model.

    ``execution_requirements``
        the frozen rule reads "a repository is involved" off file paths in the
        prose.  Live, production already knows whether a repository is attached
        to the run, and that fact is strictly better than guessing at it.

    This is not a second Semantic Waiter.  It adds no meaning of its own to the
    user's words, and it cannot delete any: INPUT.1's preservation gate runs
    over its output exactly as it runs over the interpreter it wraps.
    """

    def __init__(
        self,
        *,
        repository_available: bool = False,
        external_information_available: bool = False,
    ) -> None:
        self._delegate = ExplicitEvidenceInterpreter()
        self._repository_available = bool(repository_available)
        self._external_information_available = bool(external_information_available)
        self._live_shape: str = SHAPE_NEEDS_CLARIFICATION
        self._reasons: tuple[str, ...] = (REASON_NO_DETERMINABLE_OBLIGATION,)
        self._markers = TaskNeedMarkers()
        self._obligation_set = ObligationSet()

    # ── what the adapter decided, for the caller that asked for it ──────────
    @property
    def live_shape(self) -> str:
        return self._live_shape

    @property
    def reasons(self) -> tuple[str, ...]:
        return self._reasons

    @property
    def markers(self) -> TaskNeedMarkers:
        return self._markers

    @property
    def obligation_set(self) -> ObligationSet:
        """INPUT.PRESERVE.LIVE.1's authoritative record for this request."""
        return self._obligation_set

    @property
    def obligations(self) -> tuple[str, ...]:
        """The authoritative values, read off the one set that exists."""
        return self._obligation_set.values

    def interpret(
        self,
        raw_prompt: str,
        explicit_evidence: ExplicitEvidence,
    ) -> SemanticInterpretation:
        base = self._delegate.interpret(raw_prompt, explicit_evidence)

        shape, reasons, markers, obligations = classify_live_shape(
            raw_prompt,
            interpreted_task_type=base.task.type,
        )
        self._live_shape = shape
        self._reasons = reasons
        self._markers = markers
        self._obligation_set = obligations

        if shape == SHAPE_ANALYSIS_ONLY and base.task.type in _PRESERVED_ANSWER_TASK_TYPES:
            task_type = base.task.type
        else:
            task_type = _SHAPE_TASK_TYPES[shape]

        repository_required = self._repository_available or bool(
            explicit_evidence.file_paths
        )
        external_required = self._external_information_available or bool(
            explicit_evidence.urls
        )

        return SemanticInterpretation(
            task=TaskClassification(type=task_type, provenance=PROVENANCE_INFERRED),
            subjects=base.subjects,
            relationships=base.relationships,
            framework=base.framework,
            requested_output=base.requested_output,
            constraints=base.constraints,
            # DEFECT.FACT.LIVE.1 — carried, never re-derived.  The live adapter
            # replaces two fields the frozen interpreter cannot supply; a typed
            # behavioral claim is not one of them, and re-reading the prompt for
            # it here would be the second semantic system this phase forbids.
            behavioral_expectations=base.behavioral_expectations,
            ambiguities=base.ambiguities,
            missing_information=base.missing_information,
            execution_requirements=ExecutionRequirements(
                multi_stage=base.execution_requirements.multi_stage,
                external_information_required=external_required,
                repository_inspection_required=repository_required,
                local_repository_required=repository_required,
                provenance=PROVENANCE_INFERRED,
            ),
            notes=base.notes,
        )


# ── The live task shape ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LiveTaskShape:
    """What kind of order this is, and why a change (if any) is needed.

    Descriptive.  Every authority-shaped question — may this be patched, may
    this be written, has a defect been established — is answered elsewhere, by
    gates this record cannot reach.
    """

    task_shape: str
    change_requested: bool
    defect_claim_present: bool
    change_need_source: str
    reasons: tuple[str, ...]
    obligations: tuple[str, ...] = ()
    #: DEFECT.FACT.LIVE.1 — the typed behavioral claims this order carries,
    #: each already bound to the preserved obligation unit that holds its span.
    behavioral_expectations: tuple[BehavioralExpectation, ...] = ()
    #: INPUT.PRESERVE.LIVE.1's authoritative record.  ``obligations`` is its
    #: ``values`` and may not disagree with it — see ``__post_init__``.
    obligation_set: ObligationSet = field(default_factory=ObligationSet)
    markers: TaskNeedMarkers = field(default_factory=TaskNeedMarkers)
    contract: TaskContract | None = None
    waiter_task_shape: TaskShape | None = None
    capability_requirements: CapabilityRequirements | None = None
    preservation_passed: bool = True
    adapter_kind: str = ADAPTER_KIND
    schema_version: str = LIVE_TASK_SHAPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.task_shape not in LIVE_TASK_SHAPES:
            raise ValueError(f"unsupported live task shape: {self.task_shape!r}")
        if self.change_need_source not in CHANGE_NEED_SOURCES:
            raise ValueError(
                f"unsupported change-need source: {self.change_need_source!r}"
            )
        if not self.reasons:
            raise ValueError("every live task shape must state at least one reason")
        for reason in self.reasons:
            if reason not in LIVE_SHAPE_REASONS:
                raise ValueError(f"unsupported live shape reason: {reason!r}")
        if len(self.obligations) > MAX_OBLIGATIONS:
            raise ValueError("obligations exceed the supported bound")
        # INPUT.PRESERVE.LIVE.1.  The preservation gate and every downstream
        # consumer read the same set, so a shape that carried a *shorter*
        # obligation tuple than the set it validated cannot be constructed.
        # This is what makes "gate passed, downstream received fewer" a
        # structural impossibility rather than a rule someone has to remember.
        if self.obligations != self.obligation_set.values:
            raise ValueError(
                "the obligations a shape carries must be exactly the authoritative "
                "set the preservation gate inspected"
            )
        if self.preservation_passed and self.obligation_set.authoritative_truncated:
            raise ValueError(
                "preservation may not be reported as passed while an explicit "
                "obligation failed to reach the authoritative contract"
            )
        if self.change_requested != (self.task_shape in CHANGE_SHAPES):
            raise ValueError(
                "change_requested must agree with the task shape: only defect_repair "
                "and explicit_change request a repository change"
            )
        if self.task_shape == SHAPE_DEFECT_REPAIR and not self.defect_claim_present:
            raise ValueError("the defect_repair shape requires a defect claim")
        if self.task_shape == SHAPE_EXPLICIT_CHANGE and self.defect_claim_present:
            raise ValueError(
                "the explicit_change shape exists precisely because no defect was "
                "claimed; a claimed defect belongs to defect_repair"
            )
        if (
            self.task_shape == SHAPE_EXPLICIT_CHANGE
            and self.change_need_source != CHANGE_NEED_EXPLICIT_USER_REQUEST
        ):
            raise ValueError("an explicit change request is its own change-need source")
        if (
            self.task_shape == SHAPE_ANALYSIS_ONLY
            and self.change_need_source != CHANGE_NEED_NONE
        ):
            raise ValueError("an analysis-only order needs no change")
        if self.change_need_source == CHANGE_NEED_GROUNDED_DEFECT:
            raise ValueError(
                "a grounded defect is established by executed failure evidence, "
                "never by task shape"
            )

    @property
    def analysis_only(self) -> bool:
        return self.task_shape == SHAPE_ANALYSIS_ONLY

    @property
    def defect_repair(self) -> bool:
        return self.task_shape == SHAPE_DEFECT_REPAIR

    @property
    def explicit_change(self) -> bool:
        return self.task_shape == SHAPE_EXPLICIT_CHANGE

    @property
    def needs_clarification(self) -> bool:
        return self.task_shape == SHAPE_NEEDS_CLARIFICATION

    @property
    def defect_established(self) -> bool:
        """Always false.  A shape describes a claim, never a verified defect."""
        return False

    def reason_descriptions(self) -> tuple[str, ...]:
        return tuple(LIVE_SHAPE_REASON_DESCRIPTIONS[reason] for reason in self.reasons)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "adapter_kind": self.adapter_kind,
            "task_shape": self.task_shape,
            "change_requested": self.change_requested,
            "defect_claim_present": self.defect_claim_present,
            "defect_established": self.defect_established,
            "change_need_source": self.change_need_source,
            "reasons": [
                {"code": reason, "description": LIVE_SHAPE_REASON_DESCRIPTIONS[reason]}
                for reason in self.reasons
            ],
            "obligations": list(self.obligations),
            "behavioral_expectations": [
                item.as_dict() for item in self.behavioral_expectations
            ],
            "obligation_preservation": self.obligation_set.as_dict(),
            "markers": self.markers.as_dict(),
            "preservation_passed": self.preservation_passed,
            "waiter_task_shape": (
                self.waiter_task_shape.as_dict() if self.waiter_task_shape else None
            ),
            "capability_requirements": (
                self.capability_requirements.as_dict()
                if self.capability_requirements
                else None
            ),
        }


def _change_need_source(shape: str) -> str:
    if shape == SHAPE_ANALYSIS_ONLY:
        return CHANGE_NEED_NONE
    if shape == SHAPE_EXPLICIT_CHANGE:
        return CHANGE_NEED_EXPLICIT_USER_REQUEST
    # A defect claim is a claim.  It becomes ``grounded_defect`` only where
    # CONTROL.SAFETY.LIVE.1 binds executed failure evidence to exact source,
    # and stays unresolved everywhere else — including for a claim that turns
    # out to be false.
    return CHANGE_NEED_UNRESOLVED


def derive_live_task_shape(
    raw_text: str,
    *,
    repository_available: bool = False,
    external_information_available: bool = False,
) -> LiveTaskShape:
    """Describe one live order deterministically, before any repository work.

    The whole derivation is literal-marker matching plus INPUT.1's own
    extraction and preservation gate, so it is safe to run first — before
    indexing, before preflight validation and before CONTROL localization,
    which is the point.  It costs no model call, no network call and no
    repository traversal.

    A preservation failure fails closed to ``needs_clarification`` rather than
    to a patch route: an order whose explicit commitments did not survive is the
    last thing that should be allowed to select a target.
    """
    interpreter = LiveTaskFieldsInterpreter(
        repository_available=repository_available,
        external_information_available=external_information_available,
    )
    contract = understand_request(str(raw_text or ""), interpreter=interpreter)

    shape = interpreter.live_shape
    reasons = interpreter.reasons
    obligation_set = interpreter.obligation_set
    # INPUT.PRESERVE.LIVE.1 folds into the same fail-closed verdict INPUT.1
    # already had.  An order whose explicit obligations did not all reach the
    # authoritative contract is exactly as unroutable as one whose subjects
    # did not, and for the same reason.
    preserved = contract.preservation.passed and not (
        obligation_set.authoritative_truncated
    )
    if not preserved:
        shape = SHAPE_NEEDS_CLARIFICATION
        reasons = (REASON_PRESERVATION_FAILED,)

    waiter_shape: TaskShape | None = None
    capabilities: CapabilityRequirements | None = None
    if preserved:
        waiter_shape = derive_task_shape(contract)
        capabilities = derive_capability_requirements(waiter_shape, contract)

    markers = interpreter.markers
    # DEFECT.FACT.LIVE.1.  A typed claim ships only while the preserved text it
    # quotes still says what it says, and it names the obligation unit that
    # carries it.  Extraction and preservation cannot silently diverge because
    # the fact is checked against the very set the preservation gate inspected.
    behavior_facts = bind_obligation_ordinals(
        supported_behavior_facts(
            contract.behavioral_expectations,
            obligation_set.values or (contract.raw_request.text,),
        ),
        obligation_set.values,
    )
    return LiveTaskShape(
        task_shape=shape,
        change_requested=shape in CHANGE_SHAPES,
        defect_claim_present=(
            shape == SHAPE_DEFECT_REPAIR and markers.defect_claim_present
        ),
        change_need_source=_change_need_source(shape),
        reasons=reasons,
        obligations=obligation_set.values,
        behavioral_expectations=behavior_facts,
        obligation_set=obligation_set,
        markers=markers,
        contract=contract,
        waiter_task_shape=waiter_shape,
        capability_requirements=capabilities,
        preservation_passed=preserved,
    )


def live_shape_from_waiter_family(family: str) -> str:
    """Map a WAITER.1 task family onto the live vocabulary.

    Used to prove the two vocabularies agree rather than to route: ``debugging``
    is defect repair, ``implementation`` is an explicit change, an answer family
    is analysis, and anything else fails closed.
    """
    if family == FAMILY_DEBUGGING:
        return SHAPE_DEFECT_REPAIR
    if family == FAMILY_IMPLEMENTATION:
        return SHAPE_EXPLICIT_CHANGE
    if family in ANSWER_FAMILIES:
        return SHAPE_ANALYSIS_ONLY
    return SHAPE_NEEDS_CLARIFICATION


__all__ = [
    "ADAPTER_KIND",
    "ANALYSIS_MARKERS",
    "CHANGE_NEED_EXPLICIT_USER_REQUEST",
    "CHANGE_NEED_GROUNDED_DEFECT",
    "CHANGE_NEED_NONE",
    "CHANGE_NEED_SOURCES",
    "CHANGE_NEED_UNRESOLVED",
    "CHANGE_SHAPES",
    "DEFECT_CLAIM_MARKERS",
    "DEFECT_REPAIR_MARKERS",
    "EXPLICIT_CHANGE_MARKERS",
    "LIVE_SHAPE_REASONS",
    "LIVE_SHAPE_REASON_DESCRIPTIONS",
    "LIVE_TASK_SHAPES",
    "LIVE_TASK_SHAPE_SCHEMA_VERSION",
    "LiveTaskFieldsInterpreter",
    "LiveTaskShape",
    "PHASE_ID",
    "REASON_ANALYSIS_NO_CHANGE_REQUESTED",
    "REASON_DEFECT_CLAIM_PRESENT",
    "REASON_EMPTY_REQUEST",
    "REASON_EXPLICIT_CHANGE_REQUEST",
    "REASON_MIXED_OBLIGATIONS",
    "REASON_NO_DETERMINABLE_OBLIGATION",
    "REASON_PRESERVATION_FAILED",
    "SHAPE_ANALYSIS_ONLY",
    "SHAPE_DEFECT_REPAIR",
    "SHAPE_EXPLICIT_CHANGE",
    "SHAPE_NEEDS_CLARIFICATION",
    "TaskNeedMarkers",
    "classify_live_shape",
    "derive_live_task_shape",
    "extract_need_markers",
    "has_mixed_obligations",
    "live_shape_from_waiter_family",
    "split_obligations",
]
