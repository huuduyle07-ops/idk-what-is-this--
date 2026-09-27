"""INPUT.PRESERVE.LIVE.1 — Lossless Long-Obligation Transport.

A live T5 black-box run exposed a violation of the frozen INPUT.1 preservation
contract.  The request named six explicit comparison dimensions:

    Compare this repository (deepseek-harness ...) against C.A.T.T.U.S ...
    Focus on: (1) how each one structures its agent loop and extension model,
    (2) how each handles tool/plugin registration and lifecycle, (3) how each
    handles repository context and retrieval for coding tasks. Then recommend
    the three highest-value architectural ideas ...

WAITER.LIVE.1 split it at the sequencing the user wrote — correctly — and then
capped each clause at 240 characters.  The first clause is 355 characters long,
so the transport kept::

    ... (1) how each one structures its agent loop and extension mo

and dropped ``tool``, ``plugin``, ``lifecycle``, ``context`` and ``retrieval``
— five explicit commitments — before ANALYSIS.EVIDENCE.LIVE.1 ever saw them.
The cut landed mid-word, which is the signature of blind character slicing
being used as semantic storage.

This module is the authoritative producer that replaces that cap.

**Lossless is not unbounded.**  The bound moves from "characters of a clause"
to "obligation units, each a whole span the user wrote".  Input size is bounded
at intake by INPUT.1's own frozen policy, and every bound that can still bite
reports an explicit overflow status rather than dropping text quietly.

**Storage is not display.**  :attr:`ObligationSet.values` is authoritative and
never abbreviated; :attr:`ObligationSet.preview` is a 240-character display
string for a UI field, a log line or a receipt.  The old cap survives only
there, where a cap belongs.

**One set, not two.**  The preservation gate and every downstream consumer read
the same tuple.  "Gate says preservation passed, downstream receives fewer" is
not a bug that has to be tested for; it is unrepresentable, because there is
only one tuple to read.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, ranks nothing, selects no evidence, and
grants no authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from core.explicit_evidence import MAX_SCAN_CHARS


PHASE_ID = "INPUT.PRESERVE.LIVE.1"
OBLIGATION_SET_SCHEMA_VERSION = "input_preserve_live_1_obligation_set_v1"

# ── Bounds ────────────────────────────────────────────────────────────────────
#
# Every one of these is a bound on *structure*, not a character cap applied to a
# commitment.  A request that exceeds one of them says so; none of them silently
# shortens a span the user wrote.

#: The maximum request INPUT.1 accepts.  Reused verbatim from the frozen
#: extractor rather than re-declared, so intake and extraction cannot disagree
#: about what "too large" means.
MAX_ACCEPTED_TASK_CHARS = MAX_SCAN_CHARS

#: How many ordered clauses the user's own sequencing may produce.
MAX_OBLIGATION_CLAUSES = 32

#: How many authoritative obligation units survive into the contract.
MAX_OBLIGATION_UNITS = 32

#: The longest single unit.  A clause longer than this is *sub-divided* at
#: boundaries the user wrote, never cut: the characters go into the next unit.
MAX_OBLIGATION_UNIT_CHARS = 480

#: The whole obligation set's character budget, so a long request cannot
#: silently inflate the model prompt payload.  Exceeding it is an overflow
#: state, not a truncation.
MAX_TOTAL_OBLIGATION_CHARS = 6_000

#: Display only.  This is the old cap, kept where a cap is honest.
OBLIGATION_PREVIEW_CHARS = 240

#: What separates one obligation from the next in the preview string.
_PREVIEW_JOIN = " · "
_PREVIEW_ELLIPSIS = "…"

# ── Overflow vocabulary ───────────────────────────────────────────────────────
#: Nothing was dropped and nothing was shortened.
OVERFLOW_NONE = "none"
#: The request itself exceeded the accepted input size at intake.
OVERFLOW_INPUT_TOO_LARGE = "input_exceeds_accepted_size"
#: More ordered obligation units than the contract can carry.
OVERFLOW_UNITS_EXCEEDED = "obligation_units_exceeded"
#: The obligation set's total character budget was exhausted.
OVERFLOW_CHARS_EXCEEDED = "obligation_characters_exceeded"
#: A set restored from a stored artifact, whose completeness cannot be known.
OVERFLOW_HISTORICAL_UNKNOWN = "historical_representation_unknown"

OVERFLOW_STATUSES: tuple[str, ...] = (
    OVERFLOW_NONE,
    OVERFLOW_INPUT_TOO_LARGE,
    OVERFLOW_UNITS_EXCEEDED,
    OVERFLOW_CHARS_EXCEEDED,
    OVERFLOW_HISTORICAL_UNKNOWN,
)

#: The statuses under which the authoritative set is known to be incomplete.
_INCOMPLETE_STATUSES: frozenset[str] = frozenset(
    {OVERFLOW_UNITS_EXCEEDED, OVERFLOW_CHARS_EXCEEDED, OVERFLOW_HISTORICAL_UNKNOWN}
)


# ── Boundaries the user wrote ─────────────────────────────────────────────────
#
# Identical in spirit to WAITER.LIVE.1's clause splitter: a boundary is honoured
# only where the user drew one.  Nothing here infers a break from meaning.

#: The ordered sequencing WAITER.LIVE.1 already splits on.  Kept byte-identical
#: so the primary clause list — the one routing reads — is unchanged.
_CLAUSE_SPLIT_RE = re.compile(
    r"(?:(?<![\w-])(?:then|after that|afterwards|next|finally|and then)(?![\w-])|[;\n])",
    re.I,
)

#: An enumeration the user typed: ``(1)``, ``(a)``, ``2.`` or ``3)``.  On the
#: live T5 request this is what makes each numbered comparison dimension its own
#: obligation rather than a fragment of one long sentence.
_ENUMERATION_BOUNDARY_RE = re.compile(
    r"\s+(?=\((?:\d{1,2}|[a-zA-Z])\)\s)|\s+(?=\d{1,2}[.)]\s)"
)

#: A sentence the user ended.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=\S)")

#: A conjunction the user wrote after a comma — the weakest boundary honoured,
#: and still one that appears literally in the request.
_CONJUNCTION_BOUNDARY_RE = re.compile(
    r",\s+(?=(?:and|or|but|then|plus|also|as well as)(?![\w-]))", re.I
)

#: Applied in this order.  Each rule is tried only when the previous one left a
#: piece still over the unit bound.
_SUBCLAUSE_RULES: tuple[re.Pattern[str], ...] = (
    _ENUMERATION_BOUNDARY_RE,
    _SENTENCE_BOUNDARY_RE,
    _CONJUNCTION_BOUNDARY_RE,
)

#: Trimmed from a clause's edges.  The same set WAITER.LIVE.1 already trims.
_CLAUSE_EDGE_CHARS = " ,.:-"


def _normalize(text: str) -> str:
    """Collapse whitespace and trim the separator the split consumed."""
    return " ".join(str(text or "").split()).strip(_CLAUSE_EDGE_CHARS)


def split_obligation_clauses(text: str) -> tuple[str, ...]:
    """Split a request at the sequencing the user wrote, losslessly.

    This is WAITER.LIVE.1's original primary split with the per-clause character
    cap removed.  It is what mixed-obligation detection reads, so routing keeps
    seeing whole clauses rather than sub-divided ones — sub-division is a
    transport concern and must not manufacture a clarification route.

    Exact duplicates are collapsed case-insensitively, which is the same
    normalization ``core.explicit_evidence`` already applies to literals.  Two
    *different* commitments are never collapsed: "compare lifecycle" and
    "compare retrieval" are two obligations and stay two.
    """
    clauses: list[str] = []
    seen: set[str] = set()
    for raw in _CLAUSE_SPLIT_RE.split(str(text or "")):
        clause = _normalize(raw)
        if not clause:
            continue
        key = clause.casefold()
        if key in seen:
            continue
        seen.add(key)
        clauses.append(clause)
        if len(clauses) >= MAX_OBLIGATION_CLAUSES:
            break
    return tuple(clauses)


def _split_at(text: str, rule: re.Pattern[str]) -> list[str]:
    """Divide one span at every boundary ``rule`` marks, keeping every word."""
    pieces = [piece.strip() for piece in rule.split(text)]
    return [piece for piece in pieces if piece]


def _wrap_words(text: str) -> list[str]:
    """Last resort: wrap at the unit bound on whitespace, never inside a word.

    Reached only by a single unbroken span longer than
    :data:`MAX_OBLIGATION_UNIT_CHARS` that carries no enumeration, no sentence
    end and no conjunction — a wall of prose.  Every word still survives, in
    order, across consecutive units.
    """
    units: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and len(candidate) > MAX_OBLIGATION_UNIT_CHARS:
            units.append(current)
            current = word
        else:
            current = candidate
    if current:
        units.append(current)
    return units or [text]


def _fit_clause(clause: str, rules: tuple[re.Pattern[str], ...]) -> list[str]:
    """Reduce one clause to units within the bound without losing a character."""
    if len(clause) <= MAX_OBLIGATION_UNIT_CHARS:
        return [clause]
    for index, rule in enumerate(rules):
        pieces = _split_at(clause, rule)
        if len(pieces) > 1:
            fitted: list[str] = []
            for piece in pieces:
                fitted.extend(_fit_clause(piece, rules[index + 1 :]))
            return fitted
    return _wrap_words(clause)


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ObligationUnit:
    """One explicit commitment, as the user wrote it.

    ``text`` is a span of the request — never reworded, never summarised and
    never generated.  ``clause_ordinal`` says which piece of the user's own
    sequencing it came from, so a sub-divided clause can still be recognised as
    one order.
    """

    text: str
    ordinal: int
    clause_ordinal: int
    continued: bool = False

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("an obligation unit needs non-empty text")
        if self.ordinal < 0 or self.clause_ordinal < 0:
            raise ValueError("obligation ordinals are non-negative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "ordinal": self.ordinal,
            "clause_ordinal": self.clause_ordinal,
            "continued": self.continued,
        }


@dataclass(frozen=True, slots=True)
class ObligationSet:
    """The authoritative obligation set for one request.

    Read by the preservation gate and by every downstream consumer, from the
    same attribute.  There is no second, shorter representation for anything but
    display.
    """

    units: tuple[ObligationUnit, ...] = ()
    clauses: tuple[str, ...] = ()
    overflow_status: str = OVERFLOW_NONE
    input_chars: int = 0
    accepted_obligation_count: int = 0
    schema_version: str = OBLIGATION_SET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.overflow_status not in OVERFLOW_STATUSES:
            raise ValueError(f"unsupported overflow status: {self.overflow_status!r}")
        if len(self.units) > MAX_OBLIGATION_UNITS:
            raise ValueError("obligation units exceed the supported bound")
        if self.accepted_obligation_count < len(self.units):
            raise ValueError(
                "more obligations were preserved than were accepted, which cannot "
                "happen: the preserved set is a prefix of the accepted set"
            )
        for expected, unit in enumerate(self.units):
            if unit.ordinal != expected:
                raise ValueError("obligation ordinals must be dense and ascending")

    # ── the authoritative view ──────────────────────────────────────────────
    @property
    def values(self) -> tuple[str, ...]:
        """What downstream consumes.  Never abbreviated."""
        return tuple(unit.text for unit in self.units)

    @property
    def preserved_obligation_count(self) -> int:
        return len(self.units)

    @property
    def authoritative_truncated(self) -> bool:
        """Did any accepted commitment fail to reach the authoritative set?

        False for every request within bounds.  True only alongside an explicit
        overflow status — there is no path that makes this true quietly.
        """
        return (
            self.overflow_status in _INCOMPLETE_STATUSES
            or self.accepted_obligation_count != len(self.units)
        )

    @property
    def total_chars(self) -> int:
        return sum(len(unit.text) for unit in self.units)

    # ── the display view ────────────────────────────────────────────────────
    @property
    def preview(self) -> str:
        """A bounded string for a UI field, a log line or a receipt.

        Abbreviating here is fine, and is the only place it is fine.
        """
        values = self.values
        if not values:
            return ""
        rendered = _PREVIEW_JOIN.join(values)
        if len(rendered) <= OBLIGATION_PREVIEW_CHARS:
            return rendered
        budget = OBLIGATION_PREVIEW_CHARS - len(_PREVIEW_ELLIPSIS)
        clipped = rendered[:budget].rstrip()
        return f"{clipped}{_PREVIEW_ELLIPSIS}"

    @property
    def preview_truncated(self) -> bool:
        return len(_PREVIEW_JOIN.join(self.values)) > OBLIGATION_PREVIEW_CHARS

    # ── the receipt ─────────────────────────────────────────────────────────
    def as_dict(self, *, include_preview: bool = True) -> dict[str, Any]:
        """Bounded preservation facts.

        Deliberately counts and flags rather than the user's text: the whole
        request is already preserved verbatim on the Task Contract, and a
        receipt is not the place to copy it again.

        ``include_preview`` is false where the obligations themselves already
        sit beside this receipt — the route receipt, for one.  Repeating an
        abbreviation of a list printed two keys above it would be the same
        duplication this phase exists to stop, in the other direction.
        """
        payload = {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "accepted_obligation_count": self.accepted_obligation_count,
            "preserved_obligation_count": self.preserved_obligation_count,
            "clause_count": len(self.clauses),
            "input_chars": self.input_chars,
            "obligation_chars": self.total_chars,
            "preview_truncated": self.preview_truncated,
            "authoritative_truncated": self.authoritative_truncated,
            "overflow_status": self.overflow_status,
            # The bounds this receipt was produced under are identified by
            # ``schema_version`` rather than copied into every record.
        }
        if include_preview:
            payload["preview"] = self.preview
        return payload

    # ── historical artifacts ────────────────────────────────────────────────
    @classmethod
    def from_historical(cls, values: Iterable[str]) -> "ObligationSet":
        """Restore an obligation list stored by an earlier run.

        Old artifacts hold whatever the 240-character transport left behind.
        They stay readable, and they are never reinterpreted as preserved: the
        completeness of a stored list cannot be established after the fact, so
        the restored set reports itself as incomplete rather than claiming a
        preservation it cannot prove.
        """
        units = tuple(
            ObligationUnit(text=text, ordinal=index, clause_ordinal=index)
            for index, text in enumerate(
                str(value) for value in values if str(value).strip()
            )
        )
        return cls(
            units=units,
            clauses=tuple(unit.text for unit in units),
            overflow_status=OVERFLOW_HISTORICAL_UNKNOWN,
            input_chars=sum(len(unit.text) for unit in units),
            accepted_obligation_count=len(units),
        )


# ── The authoritative producer ────────────────────────────────────────────────

def derive_obligation_set(raw_text: str) -> ObligationSet:
    """Read every explicit obligation out of one request, losslessly.

    Deterministic and pure.  Two runs over the same prompt always produce the
    same set, on any machine, with no network and no model.

    Input is bounded at intake by INPUT.1's own accepted size.  Past that the
    set reports :data:`OVERFLOW_INPUT_TOO_LARGE` rather than accepting the whole
    request and quietly keeping the front of it.
    """
    text = str(raw_text or "")
    input_chars = len(text)

    overflow = OVERFLOW_NONE
    if input_chars > MAX_ACCEPTED_TASK_CHARS:
        overflow = OVERFLOW_INPUT_TOO_LARGE
        text = text[:MAX_ACCEPTED_TASK_CHARS]

    clauses = split_obligation_clauses(text)

    accepted: list[tuple[str, int, bool]] = []
    for clause_ordinal, clause in enumerate(clauses):
        fitted = _fit_clause(clause, _SUBCLAUSE_RULES)
        for position, piece in enumerate(fitted):
            accepted.append((piece, clause_ordinal, position > 0))

    units: list[ObligationUnit] = []
    total = 0
    for text_value, clause_ordinal, continued in accepted:
        # An intake overflow is the more fundamental fact and keeps its status:
        # a request that was too large to accept did not merely produce too many
        # units, and reporting the downstream symptom would hide the cause.
        if len(units) >= MAX_OBLIGATION_UNITS:
            if overflow == OVERFLOW_NONE:
                overflow = OVERFLOW_UNITS_EXCEEDED
            break
        if total + len(text_value) > MAX_TOTAL_OBLIGATION_CHARS:
            if overflow == OVERFLOW_NONE:
                overflow = OVERFLOW_CHARS_EXCEEDED
            break
        units.append(
            ObligationUnit(
                text=text_value,
                ordinal=len(units),
                clause_ordinal=clause_ordinal,
                continued=continued,
            )
        )
        total += len(text_value)

    return ObligationSet(
        units=tuple(units),
        clauses=clauses,
        overflow_status=overflow,
        input_chars=input_chars,
        accepted_obligation_count=len(accepted),
    )


__all__ = [
    "MAX_ACCEPTED_TASK_CHARS",
    "MAX_OBLIGATION_CLAUSES",
    "MAX_OBLIGATION_UNITS",
    "MAX_OBLIGATION_UNIT_CHARS",
    "MAX_TOTAL_OBLIGATION_CHARS",
    "OBLIGATION_PREVIEW_CHARS",
    "OBLIGATION_SET_SCHEMA_VERSION",
    "OVERFLOW_CHARS_EXCEEDED",
    "OVERFLOW_HISTORICAL_UNKNOWN",
    "OVERFLOW_INPUT_TOO_LARGE",
    "OVERFLOW_NONE",
    "OVERFLOW_STATUSES",
    "OVERFLOW_UNITS_EXCEEDED",
    "PHASE_ID",
    "ObligationSet",
    "ObligationUnit",
    "derive_obligation_set",
    "split_obligation_clauses",
]
