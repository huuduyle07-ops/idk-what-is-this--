"""ANSWER.GROUND.LIVE.1/.2/.3 — repository-entity truthfulness at display time.

This module answers one deliberately narrow question: may a concrete repository
file, ``file::symbol``, qualified member or bare symbol reference be shown as an
established repository fact?  The answer comes only from evidence the run
already acquired.  There is no repository walk, index query, model repair turn,
network call, ranking decision, or patch-authority decision here.

ANSWER.GROUND.LIVE.1 established the boundary for path-shaped entities.
ANSWER.GROUND.LIVE.2 extends the same boundary — same extraction pass, same
status vocabulary, same evidence sources, same downgrade path, same receipt — to
claims that carry no path at all, because Round-5 showed that

    "The bug is in the PatchGenerator.generate method."

escaped while ``src/generator/formatter.py`` did not.  The symbol universe and
the conservative claim grammar live in ``core.repository_symbol_membership``;
classification, downgrade and receipting stay here so a displayed answer still
passes through exactly one grounding boundary.

ANSWER.GROUND.LIVE.3 changes *what a downgrade does to the text*, and nothing
about what is classified.  Round-6 showed both halves of the same mistake:

  * Remediation deleted the whole containing sentence for one unsupported
    entity, and the sentence splitter treated ``vs.`` as a boundary, so an
    answer reading "(parallel vs. exclusive), and state transitions ..." was
    shipped as "exclusive), and state transitions ...".  True, correctly cited
    prose was destroyed to retract one entity.
  * The path grammar accepted a supported extension as a *prefix* of a longer
    dotted token, so ``args.cmd`` became a fabrication finding about ``args.c``
    and ``settings.plugin`` one about ``settings.pl`` — file claims nobody made.

The invariant this phase adds is that an unsupported entity span is not a
containing sentence.  Remediation now annotates the exact extracted span and
leaves every byte around it — punctuation, citations, bullets, clause structure
— in place, and the path grammar requires a lexical boundary after the
extension.  The epistemic reading is stated in the wording as well: *not
established by the current bounded evidence* is not *proven nonexistent*, and
the answer says so, because this gate never scans the repository and so can
never earn a repository-wide absence claim.

Grounding runs after execution/authorization has reached a terminal outcome.
It therefore edits only the answer that will be displayed or persisted.  It
cannot turn an entity into a patch target or grant any authority.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.repository_symbol_membership import (
    COMMON_REPOSITORY_EXTENSIONS,
    RESOLVED_AMBIGUOUS,
    RESOLVED_EXECUTION_OBSERVED,
    RESOLVED_EXISTING,
    RESOLVED_NOT_A_CLAIM,
    SymbolClaim,
    SymbolMembership,
    declared_symbols,
    extract_symbol_claims,
    member_relations_from_spans,
    parse_symbol_text,
)


PHASE_ID = "ANSWER.GROUND.LIVE.1"
SYMBOL_PHASE_ID = "ANSWER.GROUND.LIVE.2"
LIVE3_PHASE_ID = "ANSWER.GROUND.LIVE.3"
SCHEMA_VERSION = "answer_ground_live_3_v1"

GROUNDED_EXISTING = "grounded_existing"
GROUNDED_EXECUTION_OBSERVED = "grounded_execution_observed"
USER_SUPPLIED_UNVERIFIED = "user_supplied_unverified"
PROPOSED_NEW = "proposed_new"
HYPOTHETICAL = "hypothetical"
UNVERIFIED_MODEL_ASSERTION = "unverified_model_assertion"
#: The single status ANSWER.GROUND.LIVE.2 adds.  A bare symbol that matches
#: several distinct source-backed entities is not guessed at, and stale evidence
#: keeps failing to unverified_model_assertion exactly as it did in LIVE.1.
AMBIGUOUS_SYMBOL = "ambiguous_symbol"

KIND_PATH = "path"
KIND_SYMBOL = "symbol"

MAX_RECEIPT_ENTITIES = 12
MAX_DISPLAY_GAP_ENTITIES = 5
MAX_EXTRACTED_REFERENCES = 128
MAX_PROPOSED_SYMBOLS = 128

#: ANSWER.GROUND.LIVE.3 — alternation order is *constructed*, never inherited
#: from however the extension tuple happens to be spelled.  Longest first (ties
#: broken alphabetically so the string is stable across runs) is what stops
#: ``.json`` from being read as ``.js`` and ``.tsx`` as ``.ts``.
_COMMON_REPOSITORY_EXTENSIONS = "|".join(
    sorted(COMMON_REPOSITORY_EXTENSIONS, key=lambda item: (-len(item), item))
)

#: ANSWER.GROUND.LIVE.3 — an extension must *end* the token it terminates.
#: Without this, ``args.cmd`` matched ``.c``, ``settings.plugin`` matched ``.pl``
#: and ``_pytest.capture.CaptureFixture`` matched ``.c``, each producing a
#: fabrication finding for a file claim nobody made.  The class is ASCII on
#: purpose: it is the exact complement of the ASCII lookbehind that already
#: guards the left edge and of ``_PATH_PART`` itself, and a Unicode ``\w``
#: would additionally *stop finding* ``main.py`` inside non-Latin prose — a
#: false negative, which is the wrong direction for a truthfulness gate.
_EXTENSION_BOUNDARY = r"(?![A-Za-z0-9_])"
_PATH_PART = r"[A-Za-z0-9_@+.-]+"
_SYMBOL_PART = r"[A-Za-z_$@~][A-Za-z0-9_$@~]*"
_ENTITY_RE = re.compile(
    rf"(?<![A-Za-z0-9_./\\-])"
    rf"(?:(?P<repository>[A-Za-z0-9][A-Za-z0-9_.-]{{0,127}})::)?"
    rf"(?P<path>(?:{_PATH_PART}[\\/])*{_PATH_PART}\.(?:{_COMMON_REPOSITORY_EXTENSIONS}))"
    rf"{_EXTENSION_BOUNDARY}"
    rf"(?:::(?P<symbol>{_SYMBOL_PART}(?:(?:::|[.#]){_SYMBOL_PART})*))?"
    rf"(?::(?P<line>[1-9][0-9]*))?",
    re.IGNORECASE,
)
_FENCED_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_MODAL_HYPOTHETICAL_RE = re.compile(r"\b(?:could|would|might)\s+[a-z]{2,}\b")
_HYPOTHETICAL_CUES = (
    "for example",
    "for instance",
    "e.g.",
    "hypothetical",
    "hypothetically",
    "could put",
    "could live",
    "could be",
    "might be",
    "suppose ",
    "imagine ",
    "such as",
)

_SKIP_PAYLOAD_TEXT_KEYS = frozenset(
    {
        # Source/code and acquired execution facts are evidence, not assistant
        # assertions.  Rewriting them would corrupt exact snippets and traces.
        "content",
        "context",
        "diff",
        "diffs",
        "execution_trace",
        "output",
        "patched_snippet",
        "raw",
        "source_snippet",
        "target_snippet",
        "traceback",
        "validation_output",
    }
)

#: Typed fields that carry a symbol assertion outright.  A structured claim is
#: validated as a claim; it does not have to survive free-text extraction first.
_SYMBOL_ASSERTION_KEYS = frozenset(
    {
        "candidate_symbol",
        "class",
        "class_name",
        "diagnosis_location",
        "function",
        "function_name",
        "method",
        "method_name",
        "qualified_symbol",
        "recommended_location",
        "source_reference",
        "symbol",
        "symbol_name",
        "target_node_name",
        "target_symbol",
        "target_symbol_full",
    }
)

#: Sibling keys that say which file a structured symbol belongs to.  Without
#: this, a perfectly good ``{"file": "calc.py", "symbol": "add"}`` would have to
#: be resolved by tail uniqueness alone.
_PATH_CONTEXT_KEYS = (
    "relative_path",
    "target_file",
    "source_file",
    "file",
    "path",
    "filename",
)

#: ANSWER.GROUND.LIVE.4 — model-authored *prose and list* fields.  Every name
#: here is a field the model itself is asked to write, taken from the response
#: schemas in ``core/prompter.py`` (REVIEWER_SCHEMA, PLANNER_SCHEMA,
#: PATCH_RESPONSE_SCHEMA and the per-step schema) and from the reviewer block
#: ``patching/patch_gates.py::reject_schema_drift`` synthesises.  Enum and
#: scalar fields the model also authors — ``severity``, ``type``, ``op``,
#: ``status``, ``target_node_kind``, ``action``, ``confidence``,
#: ``needs_escalation``, ``blocked``, ``id`` — are deliberately absent: they
#: are machine vocabulary, and a truthfulness gate has nothing to say about
#: them.
_ANSWER_PROSE_KEYS = frozenset(
    {
        "analysis",
        "blocker_reason",
        "expected_outcome",
        "explanation",
        "fix",
        "goal",
        "issue",
        "issues",
        "missing_context",
        "note",
        "patch_candidate",
        "patch_plan",
        "raw_answer",
        "reason",
        "recommendation",
        "recommendations",
        "risk",
        "risks",
        "root_cause",
        "subtasks",
        "summary",
        "target",
        "targets",
    }
)

#: ANSWER.GROUND.LIVE.4 — the complete grounding surface.  Nothing outside it
#: is inspected, descended into or rewritten.
#:
#: Round-7 proved the previous default was backwards.  ``_ground_payload_value``
#: walked the whole payload and grounded every string whose immediate key was
#: not blacklisted, so ``candidate_verification_phase_id`` — a harness-authored
#: control-plane fact attached long after the model answered — came back as
#: ``"CANDIDATE.VERIFY.LIVE (not established in the current evidence).1"`` plus
#: evidence-gap prose.  The payload stayed valid JSON and lost its machine
#: meaning.
#:
#: A blacklist cannot fix this: ``core/pipeline.py`` alone names over a hundred
#: control-plane keys, and every future phase adds more.  The boundary is
#: ownership, not spelling.  ANSWER.GROUND owns model-authored repository
#: specificity; it does not own harness-authored control-plane state, so the
#: safe default for an unknown structured field is to leave it exactly as it
#: is.  This mirrors the allowlist ``core/localization_handoff.py::
#: _display_payload`` already applies to the same payload.
#:
#: Ownership is inherited down the subtree.  A key is checked at every level,
#: so a receipt that happens to contain ``summary`` keeps it verbatim: once a
#: field belongs to the harness, everything beneath it does too.
_ANSWER_SURFACE_KEYS = (
    _ANSWER_PROSE_KEYS | _SYMBOL_ASSERTION_KEYS | frozenset(_PATH_CONTEXT_KEYS)
)

#: Product names an answer may discuss without claiming a repository file.
#: Matched as whole spellings against a single-segment reference, never by stem:
#: a stem rule would quietly exempt real files such as path.ts or json.py.
_EXTERNAL_PRODUCT_NAMES = frozenset(
    {
        "alpine.js",
        "angular.js",
        "backbone.js",
        "chart.js",
        "d3.js",
        "ember.js",
        "express.js",
        "next.js",
        "node.js",
        "nuxt.js",
        "react.js",
        "socket.io",
        "svelte.js",
        "three.js",
        "vue.js",
    }
)

#: Python-style frames only.  A frame is promoted to an execution-observed
#: symbol solely when its file is already established repository evidence, so a
#: site-packages frame never becomes a repository symbol.
_TRACEBACK_FRAME_RE = re.compile(
    r'File "(?P<path>[^"\n]{1,400})", line (?P<line>[0-9]{1,9}), in (?P<symbol>[A-Za-z_][A-Za-z0-9_]*)'
)


def _normalize_path(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _path_key(value: object) -> str:
    return _normalize_path(value).casefold()


def _alias_key(value: object) -> str:
    return str(value or "").strip().casefold()


def _canonical_symbol(symbol: object) -> str:
    """One spelling for ``Class.method``, ``Class::method`` and ``Class#method``."""

    return re.sub(r"::|#", ".", str(symbol or "").strip()).casefold()


def _symbol_key(path: object, symbol: object) -> str:
    return f"{_path_key(path)}::{_canonical_symbol(symbol)}"


def _binds_symbol(repository: "RepositoryEntityEvidence", path: object, symbol: object) -> bool:
    """Is this exact file/symbol relation established by acquired evidence?

    A real file never validates an invented member and a real class never
    validates a method it does not own: the *relation* has to exist.
    """

    key = _symbol_key(path, symbol)
    return key in repository.source_symbols or key in repository.symbol_members


@dataclass(frozen=True, slots=True)
class EntityReference:
    """One bounded repository-like reference recognized in answer text."""

    raw: str
    path: str
    symbol: str = ""
    repository: str = ""
    line: int | None = None
    start: int = 0
    end: int = 0
    hypothetical: bool = False

    @property
    def identity(self) -> str:
        subject = f"{self.repository}::" if self.repository else ""
        symbol = f"::{self.symbol}" if self.symbol else ""
        line = f":{self.line}" if self.line is not None else ""
        return f"{subject}{self.path}{symbol}{line}"


@dataclass(frozen=True, slots=True)
class RepositoryEntityEvidence:
    """Already-acquired entity membership for one repository subject."""

    repository_id: str
    display_name: str
    aliases: frozenset[str] = frozenset()
    existing_paths: frozenset[str] = frozenset()
    source_symbols: frozenset[str] = frozenset()
    analysis_paths: frozenset[str] = frozenset()
    execution_paths: frozenset[str] = frozenset()
    current: bool = True
    gaps: tuple[str, ...] = ()
    #: ANSWER.GROUND.LIVE.2 — ``path::Owner.member`` relations the already-loaded
    #: metadata establishes, and symbols an execution frame actually named.
    symbol_members: frozenset[str] = frozenset()
    execution_symbols: frozenset[str] = frozenset()
    _membership: SymbolMembership | None = field(
        init=False, repr=False, compare=False, default=None
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "aliases",
            frozenset(_alias_key(item) for item in self.aliases if str(item).strip()),
        )
        for field_name in ("existing_paths", "analysis_paths", "execution_paths"):
            values = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                frozenset(_path_key(item) for item in values if _normalize_path(item)),
            )
        for field_name in ("source_symbols", "symbol_members", "execution_symbols"):
            values = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                frozenset(
                    str(item).strip().casefold() for item in values if str(item).strip()
                ),
            )
        object.__setattr__(
            self,
            "_membership",
            SymbolMembership(
                source_symbols=self.source_symbols,
                member_relations=self.symbol_members,
                execution_symbols=self.execution_symbols,
                known_paths=self.existing_paths
                | self.analysis_paths
                | self.execution_paths,
            ),
        )

    @property
    def membership(self) -> SymbolMembership:
        """The bounded symbol view; never a query, never a traversal."""

        return self._membership or SymbolMembership()

    def matches_alias(self, value: str) -> bool:
        candidate = _alias_key(value)
        return bool(candidate) and candidate in self.aliases


@dataclass(frozen=True, slots=True)
class EntityFinding:
    reference: str
    path: str
    symbol: str
    repository_id: str | None
    status: str
    kind: str = KIND_PATH

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity": self.reference,
            "path": self.path,
            "symbol": self.symbol or None,
            "repository_id": self.repository_id,
            "status": self.status,
            "kind": self.kind,
        }


@dataclass(slots=True)
class _GroundingAccumulator:
    findings: dict[tuple[str, str, str | None], EntityFinding] = field(default_factory=dict)
    extraction_seconds: float = 0.0
    membership_check_seconds: float = 0.0

    def add(self, finding: EntityFinding) -> None:
        key = (finding.reference.casefold(), finding.status, finding.repository_id)
        self.findings.setdefault(key, finding)


def _masked_spans(text: str) -> tuple[tuple[int, int], ...]:
    return tuple((match.start(), match.end()) for match in _FENCED_BLOCK_RE.finditer(text))


def _inside_spans(position: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """Return simple punctuation/newline bounds without splitting path dots."""

    left = 0
    for match in re.finditer(r"(?:^|\n|[!?\.]\s+)", text[:start]):
        left = match.end()
    right_match = re.search(r"(?:[!?\.](?=\s|$)|\n|$)", text[end:])
    right = end + (right_match.end() if right_match else len(text[end:]))
    return left, right


def _is_hypothetical_context(text: str, start: int, end: int) -> bool:
    left, right = _sentence_bounds(text, start, end)
    sentence = text[left:right].casefold()
    if any(cue in sentence for cue in _HYPOTHETICAL_CUES):
        return True
    # "A system could expose Formatter.render()" is illustration; "the repository
    # uses Formatter.render() here" is a claim.  The modal has to introduce the
    # entity, so only the text to its left counts.
    return bool(_MODAL_HYPOTHETICAL_RE.search(text[left:start].casefold()))


def extract_repository_entities(text: object) -> tuple[EntityReference, ...]:
    """Recognize only well-formed file and ``file::symbol`` references.

    Fenced code is deliberately ignored: a path in a shell/code/pseudocode
    example is not, by shape alone, an assertion that the path exists.
    """

    value = str(text or "")
    spans = _masked_spans(value)
    references: list[EntityReference] = []
    for match in _ENTITY_RE.finditer(value):
        if _inside_spans(match.start(), spans):
            continue
        raw_line = match.group("line")
        references.append(
            EntityReference(
                raw=match.group(0),
                repository=match.group("repository") or "",
                path=_normalize_path(match.group("path")),
                symbol=match.group("symbol") or "",
                line=int(raw_line) if raw_line else None,
                start=match.start(),
                end=match.end(),
                hypothetical=_is_hypothetical_context(value, match.start(), match.end()),
            )
        )
        if len(references) >= MAX_EXTRACTED_REFERENCES:
            break
    return tuple(references)


def _reference_key(reference: EntityReference) -> tuple[str, str, str]:
    return (
        _alias_key(reference.repository),
        _path_key(reference.path),
        reference.symbol.strip().casefold(),
    )


def _repository_for_reference(
    reference: EntityReference,
    repositories: Sequence[RepositoryEntityEvidence],
) -> RepositoryEntityEvidence | None:
    if reference.repository:
        matches = [repo for repo in repositories if repo.matches_alias(reference.repository)]
        return matches[0] if len(matches) == 1 else None

    if len(repositories) == 1:
        return repositories[0]

    path = _path_key(reference.path)
    matches = [
        repo
        for repo in repositories
        if (
            path in repo.existing_paths
            or path in repo.analysis_paths
            or path in repo.execution_paths
            or (reference.symbol and _binds_symbol(repo, reference.path, reference.symbol))
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _classify_reference(
    reference: EntityReference,
    repositories: Sequence[RepositoryEntityEvidence],
    *,
    user_reference_keys: frozenset[tuple[str, str, str]],
    proposed_new_paths: frozenset[str],
) -> EntityFinding:
    repo = _repository_for_reference(reference, repositories)
    repo_id = repo.repository_id if repo is not None else None

    if reference.hypothetical:
        status = HYPOTHETICAL
    elif not reference.symbol and _path_key(reference.path) in proposed_new_paths:
        status = PROPOSED_NEW
    elif repo is not None and repo.current:
        path = _path_key(reference.path)
        if reference.symbol:
            status = (
                GROUNDED_EXISTING
                if _binds_symbol(repo, reference.path, reference.symbol)
                else UNVERIFIED_MODEL_ASSERTION
            )
        elif reference.line is not None and path in repo.execution_paths:
            status = GROUNDED_EXECUTION_OBSERVED
        elif path in repo.existing_paths or path in repo.analysis_paths:
            status = GROUNDED_EXISTING
        elif path in repo.execution_paths:
            status = GROUNDED_EXECUTION_OBSERVED
        else:
            status = UNVERIFIED_MODEL_ASSERTION
    else:
        status = UNVERIFIED_MODEL_ASSERTION

    if status == UNVERIFIED_MODEL_ASSERTION:
        exact_key = _reference_key(reference)
        unqualified_key = ("", exact_key[1], exact_key[2])
        if exact_key in user_reference_keys or unqualified_key in user_reference_keys:
            status = USER_SUPPLIED_UNVERIFIED

    return EntityFinding(
        reference=reference.identity,
        path=reference.path,
        symbol=reference.symbol,
        repository_id=repo_id,
        status=status,
        kind=KIND_PATH,
    )


def _is_external_product_reference(
    reference: EntityReference,
    repositories: Sequence[RepositoryEntityEvidence],
) -> bool:
    """Is this a well-known external product name rather than a repository file?

    "Node.js" is spelled ``<stem>.<extension>`` by accident, so the path grammar
    reads it as a file and an answer that merely mentions it loses the sentence.
    The guard is deliberately literal — whole spellings, not stems — because
    ``path.ts``, ``types.ts`` and ``json.py`` are ordinary repository files and
    must keep failing closed when they are absent.

    Repository evidence still wins.  A repository that really contains the file
    grounds it as usual, and any signal that the reference means a file — a
    directory, a repository prefix, a symbol suffix or a line number — takes it
    back out of the guard.
    """

    if reference.repository or reference.symbol or reference.line is not None:
        return False
    if "/" in reference.path:
        return False
    key = _path_key(reference.path)
    if key not in _EXTERNAL_PRODUCT_NAMES:
        return False
    return not any(
        key in repository.existing_paths
        or key in repository.analysis_paths
        or key in repository.execution_paths
        for repository in repositories
    )


def _symbol_claim_key(claim: SymbolClaim) -> tuple[str, str, str]:
    return (
        _alias_key(claim.repository),
        _path_key(claim.path),
        _canonical_symbol(claim.qualified),
    )


def _repository_for_symbol_claim(
    claim: SymbolClaim,
    repositories: Sequence[RepositoryEntityEvidence],
    *,
    context_path: str,
) -> RepositoryEntityEvidence | None:
    """Never let one repository's membership establish another's symbol."""

    if claim.repository:
        matches = [repo for repo in repositories if repo.matches_alias(claim.repository)]
        return matches[0] if len(matches) == 1 else None
    if len(repositories) == 1:
        return repositories[0]
    matches = [
        repo
        for repo in repositories
        if repo.membership.resolve(claim, context_path=context_path)
        in {RESOLVED_EXISTING, RESOLVED_EXECUTION_OBSERVED}
    ]
    return matches[0] if len(matches) == 1 else None


def _classify_symbol_claim(
    claim: SymbolClaim,
    repositories: Sequence[RepositoryEntityEvidence],
    *,
    user_symbol_keys: frozenset[tuple[str, str, str]],
    proposed_new_symbols: frozenset[str],
    hypothetical: bool,
    context_paths: Sequence[str] = (),
) -> EntityFinding | None:
    """Classify one symbol claim, or return ``None`` when it is not one.

    Ordinary prose, language builtins and external APIs are not repository
    claims at all: they produce no finding, no downgrade and no receipt entry.
    """

    context_path = _path_key(claim.path)
    repo = _repository_for_symbol_claim(claim, repositories, context_path=context_path)
    membership = repo.membership if repo is not None else SymbolMembership()
    if not membership.is_repository_claim(claim):
        return None

    repo_id = repo.repository_id if repo is not None else None
    outcome = (
        membership.resolve(claim, context_path=context_path)
        if repo is not None and repo.current
        else RESOLVED_NOT_A_CLAIM
    )
    if outcome == RESOLVED_NOT_A_CLAIM and repo is not None and repo.current:
        return None

    if outcome == RESOLVED_AMBIGUOUS and not context_path:
        # A file named in the same sentence (or a sibling structured field) may
        # make the identity exact.  Nothing else may: grounding is not retrieval
        # and never picks a winner among equally plausible symbols.
        for candidate in context_paths:
            if repo is not None and membership.resolves_within(claim, candidate):
                outcome = RESOLVED_EXISTING
                context_path = _path_key(candidate)
                break

    if hypothetical:
        status = HYPOTHETICAL
    elif outcome == RESOLVED_EXISTING:
        status = GROUNDED_EXISTING
    elif outcome == RESOLVED_EXECUTION_OBSERVED:
        status = GROUNDED_EXECUTION_OBSERVED
    elif _canonical_symbol(claim.qualified) in proposed_new_symbols or (
        _canonical_symbol(claim.member) in proposed_new_symbols and claim.owner == ""
    ):
        status = PROPOSED_NEW
    elif outcome == RESOLVED_AMBIGUOUS:
        status = AMBIGUOUS_SYMBOL
    else:
        status = UNVERIFIED_MODEL_ASSERTION

    if status == UNVERIFIED_MODEL_ASSERTION:
        exact_key = _symbol_claim_key(claim)
        unqualified_key = ("", "", exact_key[2])
        if exact_key in user_symbol_keys or unqualified_key in user_symbol_keys:
            status = USER_SUPPLIED_UNVERIFIED

    return EntityFinding(
        reference=claim.identity,
        path=_normalize_path(claim.path),
        symbol=claim.qualified,
        repository_id=repo_id,
        status=status,
        kind=KIND_SYMBOL,
    )


#: ANSWER.GROUND.LIVE.3 — the entity-local downgrade wording.  It retracts the
#: *claim* and nothing else: the entity text, its punctuation and every byte
#: around it survive, and neither form asserts repository-wide absence, which
#: this gate never reads enough of the repository to know.
_UNVERIFIED_MARKER = " (not established in the current evidence)"
_AMBIGUOUS_MARKER = " (not uniquely identified in the current evidence)"

#: Delimiter pairs an entity span may sit *directly* inside.  When it does, the
#: annotation is placed after the closing delimiter, so a marker never lands
#: inside an inline-code span or a markdown link destination.
_ENCLOSING_DELIMITERS: tuple[tuple[str, str], ...] = (
    ("`", "`"),
    ("(", ")"),
    ("[", "]"),
    ('"', '"'),
)


def _annotation_marker(status: str) -> str:
    return _AMBIGUOUS_MARKER if status == AMBIGUOUS_SYMBOL else _UNVERIFIED_MARKER


def _annotation_point(value: str, start: int, end: int) -> int:
    """Where the marker for the span ``[start, end)`` may safely be inserted.

    ``[the loop](docs/loop.md)`` must not become ``[the loop](docs/loop.md (…))``
    and ```main.py``` must not become ```main.py (…)```: an annotation inside a
    code span or a link destination is markdown damage, not a downgrade.
    """

    if start > 0 and end < len(value):
        opening = value[start - 1]
        closing = value[end]
        if (opening, closing) in _ENCLOSING_DELIMITERS:
            return end + 1
    return end


def _annotate_unsupported_spans(
    value: str,
    unsupported: Sequence[tuple[int, int, EntityFinding]],
) -> str:
    """Mark each unsupported entity in place, changing nothing around it.

    This is the whole of ANSWER.GROUND.LIVE.3's remediation.  It inserts and
    never deletes, so text before the entity, text after it, punctuation,
    citations and clause structure are preserved byte for byte.  Ownership of
    an overlapping span is settled by reading order, longest span first, so a
    path and a symbol grammar that could both claim one span produce exactly
    one annotation; both findings are still reported.  Insertions are applied
    right to left, which keeps every remaining offset valid.
    """

    accepted: list[tuple[int, int]] = []
    insertions: list[tuple[int, str]] = []
    for start, end, finding in sorted(
        unsupported, key=lambda item: (item[0], -(item[1] - item[0]))
    ):
        if any(start < other_end and other_start < end for other_start, other_end in accepted):
            continue
        accepted.append((start, end))
        insertions.append(
            (_annotation_point(value, start, end), _annotation_marker(finding.status))
        )

    annotated = value
    for point, marker in sorted(insertions, reverse=True):
        annotated = annotated[:point] + marker + annotated[point:]
    return annotated


def _repository_label(
    finding: EntityFinding,
    repositories: Sequence[RepositoryEntityEvidence],
) -> str:
    for repository in repositories:
        if repository.repository_id == finding.repository_id:
            return repository.display_name
    return "the relevant repository"


def _render_entities(
    findings: Sequence[EntityFinding],
    repositories: Sequence[RepositoryEntityEvidence],
) -> tuple[str, str]:
    bounded = list(findings[:MAX_DISPLAY_GAP_ENTITIES])
    rendered = ", ".join(f'"{item.reference}"' for item in bounded)
    if len(findings) > len(bounded):
        rendered += f", and {len(findings) - len(bounded)} more"
    label = (
        _repository_label(bounded[0], repositories)
        if bounded
        else "the relevant repository"
    )
    return rendered, label


def _unsupported_statement(
    findings: Sequence[EntityFinding],
    repositories: Sequence[RepositoryEntityEvidence],
) -> str:
    rendered, label = _render_entities(findings, repositories)
    plural = len(findings) != 1
    if findings and all(item.status == USER_SUPPLIED_UNVERIFIED for item in findings):
        return (
            f"Repository evidence gap: I could not establish that {rendered} exists in "
            f"{label} from the evidence this run acquired; the user's referent is "
            f"retained only as unverified."
        )
    # ANSWER.GROUND.LIVE.3 — the closing clause is the epistemic boundary, not
    # politeness.  This gate reads only what the run already acquired, so it can
    # report that a claim is unestablished and must never imply the stronger
    # fact that the repository lacks the entity.
    return (
        f"Repository evidence gap: the model named {rendered}, but the reference"
        f"{'s are' if plural else ' is'} not established in the current evidence "
        f"for {label}, so I am not treating "
        f"{'them' if plural else 'it'} as a real source location. This check reads "
        f"only the evidence this run acquired, so that is an evidence limit and not "
        f"a finding about whether {label} contains "
        f"{'them' if plural else 'it'}."
    )


def _ambiguous_statement(
    findings: Sequence[EntityFinding],
    repositories: Sequence[RepositoryEntityEvidence],
) -> str:
    rendered, label = _render_entities(findings, repositories)
    return (
        f"Repository evidence gap: {rendered} "
        f"{'match' if len(findings) != 1 else 'matches'} more than one source-backed "
        f"symbol in {label} with no file or module context, so I am not treating "
        f"{'them' if len(findings) != 1 else 'it'} as one specific repository entity."
    )


def _evidence_gap_statement(
    findings: Sequence[EntityFinding],
    repositories: Sequence[RepositoryEntityEvidence],
) -> str:
    ambiguous = [item for item in findings if item.status == AMBIGUOUS_SYMBOL]
    unsupported = [item for item in findings if item.status != AMBIGUOUS_SYMBOL]
    parts = []
    if unsupported:
        parts.append(_unsupported_statement(unsupported, repositories))
    if ambiguous:
        parts.append(_ambiguous_statement(ambiguous, repositories))
    return " ".join(parts)


def _extract_symbol_claims_outside_paths(
    value: str,
    references: Sequence[EntityReference],
    *,
    structured_field: str = "",
    context_path: str = "",
) -> tuple[SymbolClaim, ...]:
    """Symbol claims that the path grammar has not already claimed.

    A typed symbol field is one claim outright; free text is scanned with the
    conservative grammar, with fenced code and every path span masked so
    ``file.py::Class.method`` stays a single entity.
    """

    if structured_field:
        parsed = parse_symbol_text(value.strip())
        if parsed is not None:
            owner, member, call_form = parsed
            return (
                SymbolClaim(
                    raw=value.strip(),
                    owner=owner,
                    member=member,
                    path=context_path,
                    start=0,
                    end=len(value),
                    code_formatted=True,
                    call_form=call_form,
                    structured_field=structured_field,
                ),
            )
    excluded = list(_masked_spans(value))
    excluded.extend((reference.start, reference.end) for reference in references)
    # Prose inside an object that names a file is *contextualized* by it, not
    # scoped to it: the sibling path only breaks ties.  Binding every sentence
    # to it would report a symbol that genuinely lives one file over as absent.
    return extract_symbol_claims(value, exclude_spans=excluded)


def ground_answer_text(
    text: object,
    repositories: Sequence[RepositoryEntityEvidence],
    *,
    user_input: str = "",
    proposed_new_paths: Iterable[str] = (),
    proposed_new_symbols: Iterable[str] = (),
    accumulator: _GroundingAccumulator | None = None,
    structured_field: str = "",
    context_path: str = "",
) -> tuple[str, tuple[EntityFinding, ...]]:
    """Ground one answer string and deterministically downgrade unsupported facts."""

    value = str(text or "")
    acc = accumulator or _GroundingAccumulator()
    extraction_started = time.perf_counter()
    references = extract_repository_entities(value)
    user_references = extract_repository_entities(user_input)
    claims = _extract_symbol_claims_outside_paths(
        value,
        references,
        structured_field=structured_field,
        context_path=context_path,
    )
    user_claims = _extract_symbol_claims_outside_paths(
        str(user_input or ""), user_references
    )
    acc.extraction_seconds += time.perf_counter() - extraction_started
    user_keys = frozenset(_reference_key(item) for item in user_references)
    user_symbol_keys = frozenset(_symbol_claim_key(item) for item in user_claims)
    proposed = frozenset(_path_key(item) for item in proposed_new_paths if _normalize_path(item))
    proposed_symbols = frozenset(
        _canonical_symbol(item) for item in proposed_new_symbols if str(item).strip()
    )

    membership_started = time.perf_counter()
    classified: list[tuple[int, int, EntityFinding]] = []
    for reference in references:
        if _is_external_product_reference(reference, repositories):
            continue
        finding = _classify_reference(
            reference,
            repositories,
            user_reference_keys=user_keys,
            proposed_new_paths=proposed,
        )
        acc.add(finding)
        classified.append((reference.start, reference.end, finding))

    grounded_paths = [
        (start, end, finding.path)
        for start, end, finding in classified
        if finding.status in {GROUNDED_EXISTING, GROUNDED_EXECUTION_OBSERVED}
    ]
    for claim in claims:
        finding = _classify_symbol_claim(
            claim,
            repositories,
            user_symbol_keys=user_symbol_keys,
            proposed_new_symbols=proposed_symbols,
            hypothetical=(
                not structured_field
                and _is_hypothetical_context(value, claim.start, claim.end)
            ),
            context_paths=(
                _sentence_local_paths(value, claim, grounded_paths)
                + ((context_path,) if context_path else ())
            ),
        )
        if finding is None:
            continue
        acc.add(finding)
        classified.append((claim.start, claim.end, finding))
    acc.membership_check_seconds += time.perf_counter() - membership_started

    unsupported = [
        (start, end, finding)
        for start, end, finding in classified
        if finding.status
        in {USER_SUPPLIED_UNVERIFIED, UNVERIFIED_MODEL_ASSERTION, AMBIGUOUS_SYMBOL}
    ]
    findings = tuple(finding for _, _, finding in classified)
    if not unsupported:
        return value, findings

    # ANSWER.GROUND.LIVE.3 — the unit of remediation is the extracted entity
    # span, never the sentence that happens to contain it.  Sentence bounds are
    # still computed above for hypothetical-cue context and for ambiguity
    # resolution; they no longer decide what survives.
    annotated = _annotate_unsupported_spans(value, unsupported)
    gap = _evidence_gap_statement([finding for _, _, finding in unsupported], repositories)
    body = annotated.rstrip()
    return (f"{body}\n\n{gap}" if body else gap, findings)


def _sentence_local_paths(
    value: str,
    claim: SymbolClaim,
    grounded_paths: Sequence[tuple[int, int, str]],
) -> tuple[str, ...]:
    """Grounded file references sharing the claim's sentence, in reading order."""

    if not grounded_paths:
        return ()
    left, right = _sentence_bounds(value, claim.start, claim.end)
    return tuple(
        path
        for start, end, path in grounded_paths
        if path and left <= start and end <= right
    )


def _collect_symbol_values(control: Mapping[str, Any]) -> set[str]:
    symbols: set[str] = set()

    def _take(value: object) -> None:
        text = str(value or "").strip()
        if "::" in text:
            symbols.add(text.casefold())

    for value in control.get("entry_nodes") or ():
        _take(value)
    resolution = control.get("entry_resolution") or {}
    if isinstance(resolution, Mapping):
        for key in ("resolved_entry_nodes", "query_derived_entry_nodes"):
            for value in resolution.get(key) or ():
                _take(value)
    for key in ("top_hypothesis", "grounded_hypothesis", "decision"):
        item = control.get(key)
        if isinstance(item, Mapping):
            _take(item.get("symbol"))
    for key in ("hypotheses", "evidence", "related_snippets"):
        for item in control.get(key) or ():
            if isinstance(item, Mapping):
                _take(item.get("symbol"))
    intent = control.get("patch_intent") or {}
    if isinstance(intent, Mapping):
        _take(intent.get("target_symbol_full"))
        path = intent.get("relative_path") or intent.get("file") or intent.get("target_file")
        symbol = intent.get("target_node_name") or intent.get("target_symbol")
        if path and symbol and intent.get("source_snippet"):
            symbols.add(_symbol_key(path, symbol))
    return symbols


def _collect_paths_from_control(control: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    source_paths: set[str] = set()
    execution_paths: set[str] = set()
    for symbol in _collect_symbol_values(control):
        path, separator, _ = symbol.partition("::")
        if separator and path:
            source_paths.add(path)
    intent = control.get("patch_intent") or {}
    if isinstance(intent, Mapping) and intent.get("source_snippet"):
        for key in ("relative_path", "file", "target_file"):
            if intent.get(key):
                source_paths.add(_path_key(intent[key]))
    for item in control.get("related_snippets") or ():
        if isinstance(item, Mapping) and item.get("snippet") and item.get("file"):
            source_paths.add(_path_key(item["file"]))
    preflight = control.get("preflight_validation") or {}
    if isinstance(preflight, Mapping):
        for location in preflight.get("locations") or ():
            if isinstance(location, Mapping) and location.get("file"):
                execution_paths.add(_path_key(location["file"]))
    return source_paths, execution_paths


def _proposed_new_paths(block: Mapping[str, Any] | None) -> frozenset[str]:
    paths: set[str] = set()
    if not isinstance(block, Mapping):
        return frozenset()
    for operation in block.get("patch_plan") or ():
        if not isinstance(operation, Mapping) or operation.get("op") != "create_file":
            continue
        path = operation.get("relative_path") or operation.get("file")
        if path:
            paths.add(_path_key(path))
    return frozenset(paths)


def _proposed_new_symbols(
    block: Mapping[str, Any] | None,
    repositories: Sequence[RepositoryEntityEvidence] = (),
) -> frozenset[str]:
    """Symbols an unapplied plan proposes to introduce.

    A candidate plan that declares ``class PriorityFilter`` in a new file, or a
    new method inside a class the repository really has, is not fabricating an
    existing entity — so the answer may name it, as a proposal.  Reading a
    declaration out of text the payload already carries is not a repository
    read, and passing candidate validation still does not make the symbol an
    existing repository fact.

    A replacement snippet may only propose members of an *existing* owner.
    Otherwise an invented ``patched_snippet`` could launder an invented class
    and its invented method into "proposed" and escape the downgrade.
    """

    if not isinstance(block, Mapping):
        return frozenset()

    known_owners = {
        owner
        for repository in repositories
        for owner in repository.membership.known_owner_names
    }
    proposed: set[str] = set()

    def _absorb(text: object, *, anchored_only: bool) -> None:
        for owner, name in declared_symbols(text):
            if len(proposed) >= MAX_PROPOSED_SYMBOLS:
                return
            if anchored_only:
                if not owner or _canonical_symbol(owner) not in known_owners:
                    continue
                proposed.add(_canonical_symbol(f"{owner}.{name}"))
                continue
            proposed.add(_canonical_symbol(name))
            if owner:
                proposed.add(_canonical_symbol(f"{owner}.{name}"))

    for operation in block.get("patch_plan") or ():
        if not isinstance(operation, Mapping):
            continue
        if operation.get("op") == "create_file":
            _absorb(operation.get("content"), anchored_only=False)
        else:
            _absorb(operation.get("patched_snippet"), anchored_only=True)
    candidate = block.get("patch_candidate")
    if isinstance(candidate, Mapping):
        _absorb(candidate.get("patched_snippet"), anchored_only=True)
    return frozenset(item for item in proposed if item)


def _state_repository_evidence(state: Any) -> tuple[RepositoryEntityEvidence, ...]:
    repo_path = getattr(state, "repo_path", None)
    if not repo_path:
        return ()
    try:
        canonical_root = str(Path(repo_path).resolve())
    except OSError:
        canonical_root = os.path.abspath(str(repo_path))

    try:
        from core.repository_identity import derive_repository_id_from_canonical_root

        repository_id = derive_repository_id_from_canonical_root(canonical_root)
    except Exception:
        repository_id = f"repository:{Path(canonical_root).name.casefold()}"

    aliases = {
        Path(canonical_root).name,
        getattr(state, "project_tag", "") or "",
        repository_id,
    }
    existing_paths: set[str] = set()
    source_symbols: set[str] = set()
    symbol_members: set[str] = set()
    execution_symbols: set[str] = set()
    analysis_paths: set[str] = set()
    execution_paths: set[str] = set()
    gaps: list[str] = []

    inventory = getattr(state, "repository_inventory", None)
    if inventory is not None:
        try:
            inventory_root = str(Path(inventory.canonical_root).resolve())
        except (AttributeError, OSError):
            inventory_root = ""
        if os.path.normcase(inventory_root) == os.path.normcase(canonical_root):
            for entry in getattr(inventory, "entries", ()) or ():
                existing_paths.add(_path_key(getattr(entry, "relative_path", "")))
        else:
            gaps.append("repository inventory identity mismatch")

    evidence = getattr(state, "analysis_evidence", None)
    for item in getattr(evidence, "items", ()) or ():
        # ANALYSIS.MULTIROOT.LIVE.1 — an excerpt read from another repository
        # belongs to that repository's universe, not this one.  Folding both
        # into one record is exactly how "C.A.T.T.U.S uses Foo.run" would come
        # to be grounded by a file that only exists in deepseek-harness.
        item_repository = str(getattr(item, "repository_id", "") or "")
        if item_repository and item_repository != repository_id:
            continue
        path = getattr(item, "path", "")
        if path:
            analysis_paths.add(_path_key(path))
            existing_paths.add(_path_key(path))
            # WAITER.LIVE.1 already read this excerpt into memory.  An analysis
            # answer that cites a TypeScript symbol it acquired should not have
            # to route through ProgramGraph to stay precise.
            for owner, name in declared_symbols(getattr(item, "text", "")):
                source_symbols.add(_symbol_key(path, name))
                if owner:
                    symbol_members.add(_symbol_key(path, f"{owner}.{name}"))
    for gap in getattr(evidence, "gaps", ()) or ():
        if str(gap).strip():
            gaps.append(str(gap).strip())

    graph = getattr(state, "repository_graph", None)
    if graph is not None:
        try:
            nodes = getattr(graph, "nodes", {}) or {}
            cached_view = getattr(graph, "_localization_eligibility_view", None)
            if (
                isinstance(cached_view, tuple)
                and len(cached_view) == 2
                and cached_view[0] == len(nodes)
                and isinstance(cached_view[1], Mapping)
            ):
                verdicts = cached_view[1].values()
            else:
                from core.localization_candidate import iter_graph_verdicts

                verdicts = iter_graph_verdicts(graph)

            spans: list[tuple[str, str, str, int, int]] = []
            for verdict in verdicts:
                if verdict.eligible and verdict.source_file and verdict.symbol:
                    existing_paths.add(_path_key(verdict.source_file))
                    source_symbols.add(_symbol_key(verdict.source_file, verdict.symbol))
                    # ANSWER.GROUND.LIVE.2 — class membership comes from spans
                    # the graph already recorded during indexing.  No reparse,
                    # no file read, no rebuild, no second traversal.
                    metadata = getattr(nodes.get(verdict.node_id), "metadata", None) or {}
                    start = metadata.get("start")
                    end = metadata.get("end")
                    if isinstance(start, int) and isinstance(end, int):
                        spans.append(
                            (
                                verdict.source_file,
                                verdict.symbol,
                                verdict.node_kind,
                                start,
                                end,
                            )
                        )
            symbol_members.update(member_relations_from_spans(spans))
        except Exception:
            gaps.append("loaded graph evidence could not be qualified")

    control = getattr(state, "control_result", None)
    if isinstance(control, Mapping):
        control_root = control.get("repo_path") or canonical_root
        try:
            control_root = str(Path(str(control_root)).resolve())
        except OSError:
            control_root = os.path.abspath(str(control_root))
        if os.path.normcase(control_root) == os.path.normcase(canonical_root):
            source_symbols.update(_collect_symbol_values(control))
            control_sources, control_execution = _collect_paths_from_control(control)
            existing_paths.update(control_sources)
            execution_paths.update(control_execution)
        else:
            gaps.append("CONTROL evidence repository identity mismatch")

    # Raw validation text is allowed to confirm only paths that the current
    # source/inventory evidence already knows.  This keeps site-packages/system
    # traceback paths outside the repository subject while retaining main.py:2.
    validation_texts = [str(getattr(state, "validation_output", "") or "")]
    if isinstance(control, Mapping):
        preflight = control.get("preflight_validation") or {}
        if isinstance(preflight, Mapping):
            validation_texts.append(str(preflight.get("output") or ""))
    for validation_text in validation_texts:
        for reference in extract_repository_entities(validation_text):
            if _path_key(reference.path) in existing_paths:
                execution_paths.add(_path_key(reference.path))
        # A traceback frame names a file and the function that was running in
        # it.  That is a fact about execution, so it may ground a symbol — but
        # only for a file the repository evidence already knows, which is what
        # keeps external library frames out of the repository symbol universe.
        for frame in _TRACEBACK_FRAME_RE.finditer(validation_text):
            frame_path = _path_key(frame.group("path"))
            if frame_path and frame_path in existing_paths:
                execution_paths.add(frame_path)
                execution_symbols.add(_symbol_key(frame_path, frame.group("symbol")))

    explicitly_current = getattr(state, "answer_grounding_evidence_current", None)
    current = explicitly_current is not False
    if not current:
        gaps.append("repository evidence was marked stale or mismatched")

    return (
        RepositoryEntityEvidence(
            repository_id=repository_id,
            display_name=Path(canonical_root).name or repository_id,
            aliases=frozenset(aliases),
            existing_paths=frozenset(existing_paths),
            source_symbols=frozenset(source_symbols),
            analysis_paths=frozenset(analysis_paths),
            execution_paths=frozenset(execution_paths),
            current=current,
            gaps=tuple(dict.fromkeys(gaps)),
            symbol_members=frozenset(symbol_members),
            execution_symbols=frozenset(execution_symbols),
        ),
        *_additional_analysis_repositories(evidence, repository_id),
    )


def _additional_analysis_repositories(
    evidence: Any, primary_repository_id: str
) -> tuple[RepositoryEntityEvidence, ...]:
    """One membership record per *additional* repository an analysis run read.

    ANSWER.GROUND.LIVE.2 keeps repository symbol universes separate, and
    ANALYSIS.MULTIROOT.LIVE.1 is the first phase that produces more than one of
    them.  Each additional repository is grounded strictly by what was actually
    acquired from it: no inventory is carried across, so a path that exists in
    the second repository but was never read stays unverified rather than
    borrowing the first repository's confirmation.
    """
    subjects = getattr(evidence, "repositories", ()) or ()
    records: list[RepositoryEntityEvidence] = []
    for subject in subjects:
        repository_id = str(getattr(subject, "repository_id", "") or "")
        if not getattr(subject, "accepted", False) or not repository_id:
            continue
        if repository_id == primary_repository_id:
            continue
        paths: set[str] = set()
        symbols: set[str] = set()
        members: set[str] = set()
        for item in getattr(evidence, "items", ()) or ():
            if str(getattr(item, "repository_id", "") or "") != repository_id:
                continue
            path = getattr(item, "path", "")
            if not path:
                continue
            paths.add(_path_key(path))
            for owner, name in declared_symbols(getattr(item, "text", "")):
                symbols.add(_symbol_key(path, name))
                if owner:
                    members.add(_symbol_key(path, f"{owner}.{name}"))
        display = str(getattr(subject, "repository_display", "") or repository_id)
        records.append(
            RepositoryEntityEvidence(
                repository_id=repository_id,
                display_name=display,
                aliases=frozenset(
                    value
                    for value in (
                        display,
                        repository_id,
                        Path(
                            str(getattr(subject, "requested_root_literal", ""))
                        ).name,
                    )
                    if value
                ),
                existing_paths=frozenset(paths),
                source_symbols=frozenset(symbols),
                analysis_paths=frozenset(paths),
                symbol_members=frozenset(members),
                current=True,
                gaps=(
                    "read-only analysis evidence; only acquired files are "
                    "confirmed for this repository",
                ),
            )
        )
    return tuple(records)


def _mapping_path_context(value: Mapping[str, Any], inherited: str) -> str:
    """Which file a structured object is talking about, if it says so."""

    for key in _PATH_CONTEXT_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, str) and _normalize_path(candidate):
            return _normalize_path(candidate)
    return inherited


def _ground_payload_value(
    value: Any,
    repositories: Sequence[RepositoryEntityEvidence],
    *,
    user_input: str,
    proposed_new_paths: frozenset[str],
    proposed_new_symbols: frozenset[str],
    accumulator: _GroundingAccumulator,
    parent_key: str = "",
    context_path: str = "",
) -> Any:
    if isinstance(value, str):
        if parent_key in _SKIP_PAYLOAD_TEXT_KEYS:
            return value
        grounded, _ = ground_answer_text(
            value,
            repositories,
            user_input=user_input,
            proposed_new_paths=proposed_new_paths,
            proposed_new_symbols=proposed_new_symbols,
            accumulator=accumulator,
            structured_field=(
                parent_key if parent_key in _SYMBOL_ASSERTION_KEYS else ""
            ),
            context_path=context_path,
        )
        return grounded
    if isinstance(value, list):
        return [
            _ground_payload_value(
                item,
                repositories,
                user_input=user_input,
                proposed_new_paths=proposed_new_paths,
                proposed_new_symbols=proposed_new_symbols,
                accumulator=accumulator,
                parent_key=parent_key,
                context_path=context_path,
            )
            for item in value
        ]
    if isinstance(value, dict):
        # ANSWER.GROUND.LIVE.4 — the ownership boundary.  A field is grounded
        # only when the model authored it.  Everything else is returned by
        # identity, which is what keeps a harness receipt's phase id, digest,
        # enum, provenance and authority flag byte-for-byte intact.  Sibling
        # path context is still read from the whole mapping, because reading a
        # field is not rewriting it.
        nested_context = _mapping_path_context(value, context_path)
        return {
            key: (
                _ground_payload_value(
                    item,
                    repositories,
                    user_input=user_input,
                    proposed_new_paths=proposed_new_paths,
                    proposed_new_symbols=proposed_new_symbols,
                    accumulator=accumulator,
                    parent_key=str(key),
                    context_path=nested_context,
                )
                if key in _ANSWER_SURFACE_KEYS
                else item
            )
            for key, item in value.items()
            if key != "answer_entity_grounding"
        }
    return value


def _receipt(
    accumulator: _GroundingAccumulator,
    repositories: Sequence[RepositoryEntityEvidence],
    *,
    total_seconds: float,
) -> dict[str, Any]:
    findings = list(accumulator.findings.values())
    grounded = [
        item
        for item in findings
        if item.status in {GROUNDED_EXISTING, GROUNDED_EXECUTION_OBSERVED}
    ]
    unverified = [
        item
        for item in findings
        if item.status in {USER_SUPPLIED_UNVERIFIED, UNVERIFIED_MODEL_ASSERTION}
    ]
    ambiguous = [item for item in findings if item.status == AMBIGUOUS_SYMBOL]
    asserted = [item for item in findings if item.status not in {HYPOTHETICAL, PROPOSED_NEW}]
    symbols = [item for item in asserted if item.kind == KIND_SYMBOL]
    paths = [item for item in asserted if item.kind == KIND_PATH]
    downgraded = unverified + ambiguous
    gaps = list(
        dict.fromkeys(gap for repository in repositories for gap in repository.gaps)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "phase_ids": [PHASE_ID, SYMBOL_PHASE_ID, LIVE3_PHASE_ID],
        "asserted_entity_count": len(asserted),
        "grounded_entity_count": len(grounded),
        "unverified_entity_count": len(unverified),
        # ANSWER.GROUND.LIVE.2 — bounded symbol facts alongside the path facts
        # LIVE.1 already reported.  Counts and identities only: no source text,
        # no confidence, no score.
        "asserted_path_count": len(paths),
        "asserted_symbol_count": len(symbols),
        "grounded_symbol_count": len(
            [item for item in symbols if item.status in
             {GROUNDED_EXISTING, GROUNDED_EXECUTION_OBSERVED}]
        ),
        "unverified_symbol_count": len(
            [item for item in symbols if item.status in
             {USER_SUPPLIED_UNVERIFIED, UNVERIFIED_MODEL_ASSERTION}]
        ),
        "ambiguous_symbol_count": len(ambiguous),
        "action": "downgraded_unsupported_specificity" if downgraded else "unchanged",
        # ANSWER.GROUND.LIVE.3 — two bounded facts about *how* a downgrade was
        # applied.  Not a score, not a confidence, and no authority meaning.
        "remediation_scope": "entity_span",
        "surrounding_text_preserved": True,
        "unverified_entities": [
            item.as_dict() for item in downgraded[:MAX_RECEIPT_ENTITIES]
        ],
        "entity_statuses": [
            item.as_dict() for item in findings[:MAX_RECEIPT_ENTITIES]
        ],
        "receipt_truncated": len(findings) > MAX_RECEIPT_ENTITIES,
        "evidence_gaps": gaps[:MAX_RECEIPT_ENTITIES],
        "timing_seconds": {
            "extraction": round(accumulator.extraction_seconds, 6),
            "membership_check": round(accumulator.membership_check_seconds, 6),
            "total": round(total_seconds, 6),
        },
        "authority_effect": "none",
        "retrieval_effect": "none",
    }


def ground_answer_for_display(
    state: Any,
    answer: str,
    json_block: Mapping[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any] | None, dict[str, Any]]:
    """Return grounded display text/payload without touching operational state."""

    started = time.perf_counter()
    repositories = _state_repository_evidence(state)
    proposed = _proposed_new_paths(json_block)
    proposed_symbols = _proposed_new_symbols(json_block, repositories)
    accumulator = _GroundingAccumulator()
    user_input = str(getattr(state, "user_input", "") or "")

    if isinstance(json_block, Mapping):
        display_block = _ground_payload_value(
            copy.deepcopy(dict(json_block)),
            repositories,
            user_input=user_input,
            proposed_new_paths=proposed,
            proposed_new_symbols=proposed_symbols,
            accumulator=accumulator,
        )
        receipt = _receipt(
            accumulator,
            repositories,
            total_seconds=time.perf_counter() - started,
        )
        display_block["answer_entity_grounding"] = receipt
        rendered = json.dumps(display_block, indent=2, ensure_ascii=False)
        return rendered, rendered, display_block, receipt

    grounded, _ = ground_answer_text(
        answer,
        repositories,
        user_input=user_input,
        proposed_new_paths=proposed,
        proposed_new_symbols=proposed_symbols,
        accumulator=accumulator,
    )
    receipt = _receipt(
        accumulator,
        repositories,
        total_seconds=time.perf_counter() - started,
    )
    return grounded, grounded, None, receipt


def ground_state_answer(state: Any) -> dict[str, Any]:
    """Apply the display-only boundary to one terminal runtime state."""

    final, human, block, receipt = ground_answer_for_display(
        state,
        str(getattr(state, "human_answer", "") or getattr(state, "final_answer", "") or ""),
        getattr(state, "json_block", None),
    )
    state.final_answer = final
    state.human_answer = human
    if block is not None:
        # This happens only after execution has terminated.  The operational
        # payload is replaced with its safe display/persistence copy so no raw
        # alternate field can leak into CLI, web, DB, logs, or artifacts.
        state.json_block = block
    state.answer_entity_grounding = receipt
    return receipt


__all__ = [
    "AMBIGUOUS_SYMBOL",
    "GROUNDED_EXECUTION_OBSERVED",
    "GROUNDED_EXISTING",
    "HYPOTHETICAL",
    "KIND_PATH",
    "KIND_SYMBOL",
    "LIVE3_PHASE_ID",
    "MAX_RECEIPT_ENTITIES",
    "PHASE_ID",
    "PROPOSED_NEW",
    "RepositoryEntityEvidence",
    "SYMBOL_PHASE_ID",
    "UNVERIFIED_MODEL_ASSERTION",
    "USER_SUPPLIED_UNVERIFIED",
    "extract_repository_entities",
    "ground_answer_for_display",
    "ground_answer_text",
    "ground_state_answer",
]
