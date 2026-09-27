"""Deterministic identifier decomposition for query-derived entry recall.

RETRIEVE.LIVE.2 keeps canonical graph identity and CONTROL ranking untouched.
This module supplies only an auxiliary lexical representation used to decide
which already-eligible source symbols deserve entry into that competition.

The implementation is deliberately local and mechanical: Unicode-aware word
extraction, snake/camel/acronym decomposition, one explicit morphology bridge,
and a small low-information-token policy.  It reads no repository content,
walks no directory, calls no model, opens no socket, and grants no authority.

RETRIEVE.LIVE.4 adds the ordering half of the same boundary.  Which candidates
match is unchanged; how they are ordered before the bounded entry cap now uses
repository-local lexical specificity, derived at use time from the eligible
population itself, so a rare meaningful identifier token is not outvoted by
ordinary prose words that happen to appear in identifiers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
import re
from time import perf_counter
from typing import Iterable, Mapping


EXACT_SYMBOL = "exact_symbol"
EXACT_TAIL = "exact_tail"
IDENTIFIER_TOKEN = "identifier_token"
MULTI_TOKEN_IDENTIFIER = "multi_token_identifier"
BOUNDED_MORPHOLOGY = "bounded_morphology"
UNRESOLVED = "unresolved"

ENTRY_MATCH_KINDS: tuple[str, ...] = (
    EXACT_SYMBOL,
    EXACT_TAIL,
    IDENTIFIER_TOKEN,
    MULTI_TOKEN_IDENTIFIER,
    BOUNDED_MORPHOLOGY,
    UNRESOLVED,
)

# A deliberately small repository-facing policy, not an English stopword
# dictionary.  A lone generic piece cannot enter a population by token overlap;
# it can still resolve an exact symbol/tail, and it can participate alongside a
# meaningful token in a multi-token match (for example ``user_get``).
LOW_INFORMATION_IDENTIFIER_TOKENS: frozenset[str] = frozenset({
    "data",
    "get",
    "item",
    "main",
    "run",
    "set",
    "test",
    "value",
})

_QUERY_STOP_WORDS: frozenset[str] = frozenset({
    "a",
    "an",
    "and",
    "are",
    "as",
    "bug",
    "fix",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "not",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "why",
    "with",
})

# No general stemmer: this is the single observed lexical form needed by the
# production dogfood query.  In particular, arbitrary suffix truncation is
# forbidden (``operation`` must never become ``oper`` or ``opera``).
_BOUNDED_QUERY_MORPHOLOGY: dict[str, str] = {
    "classification": "classify",
    "classified": "classify",
    "indentation": "indent",
}

_CANONICAL_REFERENCE_RE = re.compile(
    r"(?<!\w)(?:[\w./\\-]+::)+[\w.$@#~']+",
    flags=re.UNICODE,
)
_UNICODE_IDENTIFIER_WORD_RE = re.compile(r"[^\W\d]\w*", flags=re.UNICODE)
_IDENTIFIER_SEPARATORS_RE = re.compile(r"(?:::)|[.#/\\]+|_+")


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _trim_identifier_extras(value: str) -> str:
    """Remove language sigils without imposing an ASCII-only grammar."""
    start = 0
    end = len(value)
    while start < end and not (value[start].isalnum() or value[start] == "_"):
        start += 1
    while end > start and not (value[end - 1].isalnum() or value[end - 1] == "_"):
        end -= 1
    return value[start:end]


def _split_camel_acronym(value: str) -> tuple[str, ...]:
    """Split camel/Pascal/acronym transitions using Unicode case properties."""
    if not value:
        return ()

    boundaries = [0]
    for index in range(1, len(value)):
        previous = value[index - 1]
        current = value[index]
        following = value[index + 1] if index + 1 < len(value) else ""

        lower_to_upper = current.isupper() and (
            previous.islower() or previous.isdigit()
        )
        acronym_to_word = (
            previous.isupper()
            and current.isupper()
            and bool(following)
            and following.islower()
        )
        if lower_to_upper or acronym_to_word:
            boundaries.append(index)

    boundaries.append(len(value))
    return tuple(
        value[start:end]
        for start, end in zip(boundaries, boundaries[1:])
        if value[start:end]
    )


def decompose_identifier(identifier: str) -> tuple[str, ...]:
    """Return stable case-folded tokens without mutating ``identifier``.

    Qualification, snake case, leading/trailing underscores, camelCase,
    PascalCase, acronym runs, and legitimate Unicode identifiers are handled.
    The canonical symbol remains separate and is always checked first by the
    entry resolver.
    """
    if not isinstance(identifier, str) or not identifier:
        return ()

    tokens: list[str] = []
    for qualified_part in _IDENTIFIER_SEPARATORS_RE.split(identifier):
        part = _trim_identifier_extras(qualified_part.strip("_"))
        if not part:
            continue
        for piece in _split_camel_acronym(part):
            normalized = piece.casefold()
            if normalized:
                tokens.append(normalized)
    return _dedupe(tokens)


def extract_query_symbol_candidates(query: str, *, limit: int = 12) -> list[str]:
    """Extract a bounded set of likely symbol concepts from natural language.

    Exact canonical ``path::symbol`` references are preserved whole before
    ordinary Unicode identifier-shaped words are considered.  Decomposition is
    deferred so an explicit ``_classify_indent`` or full node ID retains exact
    lookup priority.
    """
    if not isinstance(query, str) or not query or limit <= 0:
        return []

    candidates = list(_CANONICAL_REFERENCE_RE.findall(query))
    candidates.extend(_UNICODE_IDENTIFIER_WORD_RE.findall(query))

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = candidate.strip()
        normalized = value.casefold()
        if len(value) < 2 or normalized in _QUERY_STOP_WORDS or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def _query_token_relations(
    query_candidates: Iterable[str],
) -> tuple[tuple[str, ...], dict[str, str]]:
    exact_tokens: list[str] = []
    morphology: dict[str, str] = {}
    for candidate in query_candidates:
        for token in decompose_identifier(candidate):
            exact_tokens.append(token)
            related = _BOUNDED_QUERY_MORPHOLOGY.get(token)
            if related:
                morphology[token] = related
    return _dedupe(exact_tokens), morphology


@dataclass(frozen=True)
class PreparedIdentifierQuery:
    """Query-side facts computed once before the eligible-node scan."""

    raw_candidates: tuple[str, ...]
    identifier_tokens: tuple[str, ...]
    morphology_relations: tuple[tuple[str, str], ...]

    @property
    def normalized_terms(self) -> tuple[str, ...]:
        """Expose the exact terms plus their bounded morphology targets.

        This is observability over the facts already consumed by
        ``match_identifier_entry``.  It does not feed a second matcher or add
        another normalization policy.
        """
        return _dedupe(
            (*self.identifier_tokens, *(target for _, target in self.morphology_relations))
        )


def prepare_identifier_query(
    query_candidates: Iterable[str],
) -> PreparedIdentifierQuery:
    raw_candidates = _dedupe(
        value.strip() for value in query_candidates if isinstance(value, str)
    )
    exact_tokens, morphology = _query_token_relations(raw_candidates)
    return PreparedIdentifierQuery(
        raw_candidates=raw_candidates,
        identifier_tokens=exact_tokens,
        morphology_relations=tuple(morphology.items()),
    )


@dataclass(frozen=True)
class IdentifierEntryMatch:
    """Lexical entry evidence only; never rank, confidence, or authority."""

    node_id: str
    entry_match_kind: str
    identifier_tokens: tuple[str, ...]
    matched_query_tokens: tuple[str, ...]
    matched_identifier_tokens: tuple[str, ...]
    morphology_relations: tuple[str, ...] = ()
    exact_query: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "entry_match_kind": self.entry_match_kind,
            "identifier_tokens": list(self.identifier_tokens),
            "matched_query_tokens": list(self.matched_query_tokens),
            "matched_identifier_tokens": list(self.matched_identifier_tokens),
            "morphology_relations": list(self.morphology_relations),
            "exact_query": self.exact_query,
        }


def match_identifier_entry(
    node_id: str,
    query_candidates: Iterable[str] | PreparedIdentifierQuery,
) -> IdentifierEntryMatch | None:
    """Match one eligible canonical node against bounded lexical query facts."""
    prepared = (
        query_candidates
        if isinstance(query_candidates, PreparedIdentifierQuery)
        else prepare_identifier_query(query_candidates)
    )
    tail = node_id.rsplit("::", 1)[-1]
    return _match_decomposed(node_id, tail, decompose_identifier(tail), prepared)


def _match_decomposed(
    node_id: str,
    tail: str,
    identifier_tokens: tuple[str, ...],
    prepared: PreparedIdentifierQuery,
) -> IdentifierEntryMatch | None:
    """Match against an already-decomposed tail.

    The population scan decomposes each candidate once and feeds the same
    tokens to both matching and the repository-local frequency map, so
    RETRIEVE.LIVE.4 costs no extra decomposition pass and cannot drift from the
    frozen RETRIEVE.LIVE.2 matching semantics.
    """
    raw_candidates = prepared.raw_candidates
    exact_tokens = prepared.identifier_tokens
    morphology = dict(prepared.morphology_relations)

    exact_query = next((value for value in raw_candidates if value == node_id), None)
    exact_tail_query = next((value for value in raw_candidates if value == tail), None)

    matched_query: list[str] = []
    matched_identifier: list[str] = []
    morphology_relations: list[str] = []

    for query_token in exact_tokens:
        if query_token in identifier_tokens:
            matched_query.append(query_token)
            matched_identifier.append(query_token)
            continue
        related = morphology.get(query_token)
        if related and related in identifier_tokens:
            matched_query.append(query_token)
            matched_identifier.append(related)
            morphology_relations.append(f"{query_token}->{related}")

    matched_query_tokens = _dedupe(matched_query)
    matched_identifier_tokens = _dedupe(matched_identifier)
    meaningful_matches = tuple(
        token
        for token in matched_identifier_tokens
        if token not in LOW_INFORMATION_IDENTIFIER_TOKENS
    )

    if exact_query is not None:
        kind = EXACT_SYMBOL
        exact_value = exact_query
    elif exact_tail_query is not None:
        kind = EXACT_TAIL
        exact_value = exact_tail_query
    elif not meaningful_matches:
        return None
    elif len(matched_query_tokens) >= 2:
        kind = MULTI_TOKEN_IDENTIFIER
        exact_value = None
    elif morphology_relations:
        kind = BOUNDED_MORPHOLOGY
        exact_value = None
    else:
        kind = IDENTIFIER_TOKEN
        exact_value = None

    return IdentifierEntryMatch(
        node_id=node_id,
        entry_match_kind=kind,
        identifier_tokens=identifier_tokens,
        matched_query_tokens=matched_query_tokens,
        matched_identifier_tokens=matched_identifier_tokens,
        morphology_relations=_dedupe(morphology_relations),
        exact_query=exact_value,
    )


@dataclass(frozen=True)
class LexicalSpecificityIndex:
    """Repository-local token specificity over one eligible population.

    Navigation evidence only.  The numbers below say how unusual a token is
    *inside the repository currently being searched*; a token that is rare here
    may be everywhere in the next repository, so nothing global is shipped, no
    corpus is downloaded and no learned weight exists.

    ``token_document_frequency`` is candidate-level: a candidate contributes at
    most one to a token no matter how many times the token repeats inside its
    identifier.  Only the query's own normalized terms are tracked, so the map
    stays bounded by the query rather than by the ~19k-symbol vocabulary.
    """

    candidate_count: int
    token_document_frequency: Mapping[str, int] = field(default_factory=dict)

    def token_idf(self, token: str) -> float:
        """``log(N / (1 + df(token)))`` with an explicit non-negativity floor.

        The logarithm is exactly the measured offline rule.  The floor matters
        only for a token carried by (almost) every candidate, where the raw
        value turns negative and would invert the precision multiplication -
        ranking sprawling identifiers above tight ones in a tiny repository.
        """
        if self.candidate_count <= 0:
            return 0.0
        frequency = self.token_document_frequency.get(token, 0)
        return max(0.0, math.log(self.candidate_count / (1 + frequency)))

    def strongest_match_token(self, match: IdentifierEntryMatch) -> str | None:
        """The matched query token carrying the most repository specificity."""
        if not match.matched_query_tokens:
            return None
        return max(
            match.matched_query_tokens,
            key=lambda token: (self.token_idf(token), token),
        )

    def max_match_specificity(self, match: IdentifierEntryMatch) -> float:
        """Best single matched token, not their sum.

        A sum rewards a long identifier for accumulating several mediocre
        coincidences; the measured rule asks instead how informative this
        candidate's *best* connection to the query is.
        """
        return max(
            (self.token_idf(token) for token in match.matched_query_tokens),
            default=0.0,
        )

    def identifier_precision(self, match: IdentifierEntryMatch) -> float:
        """Share of the candidate identifier the query actually explains.

        Without it a single rare token buried among unrelated identifier tokens
        would win outright, so a wide symbol that merely mentions the concept
        cannot outrank a narrow one that is about it.
        """
        return len(match.matched_query_tokens) / max(1, len(match.identifier_tokens))

    def lexical_specificity_score(self, match: IdentifierEntryMatch) -> float:
        return self.max_match_specificity(match) * self.identifier_precision(match)


def build_lexical_specificity_index(
    candidate_token_sets: Iterable[Iterable[str]],
    *,
    tracked_tokens: Iterable[str],
) -> LexicalSpecificityIndex:
    """Count candidate-level document frequency in one linear pass.

    ``candidate_token_sets`` is the decomposed identifier of every eligible
    candidate, consumed once.  No repository is walked, no file is read and
    nothing is persisted: the map lives for the duration of one query.
    """
    tracked = frozenset(token for token in tracked_tokens if token)
    frequencies: Counter[str] = Counter()
    candidate_count = 0
    for tokens in candidate_token_sets:
        candidate_count += 1
        if tracked:
            frequencies.update(tracked.intersection(tokens))
    return LexicalSpecificityIndex(
        candidate_count=candidate_count,
        token_document_frequency=dict(frequencies),
    )


#: Explicit source references keep their own precedence.  Everything else -
#: multi-token overlap, a single identifier token, a bounded morphology bridge -
#: competes on specificity instead of on a fixed tier, because a hard bottom
#: tier let a rare, meaningful bridge lose to common incidental prose words.
_EXACT_IDENTITY_ORDER = {EXACT_SYMBOL: 0, EXACT_TAIL: 1}
_LEXICAL_IDENTITY_RANK = 2


def entry_match_order_key(
    match: IdentifierEntryMatch,
    specificity: LexicalSpecificityIndex,
) -> tuple[object, ...]:
    """Deterministic pre-cap ordering using entry evidence facts only.

    Four components, smallest first:

    1. explicit identity - a full node id, then an exact tail;
    2. repository-local specificity x identifier precision;
    3. exact token equality ahead of a morphology bridge at equal specificity;
    4. canonical node id, so equal evidence never depends on scan order.
    """
    exact_overlap_count = len(match.matched_query_tokens) - len(
        match.morphology_relations
    )
    return (
        _EXACT_IDENTITY_ORDER.get(match.entry_match_kind, _LEXICAL_IDENTITY_RANK),
        -specificity.lexical_specificity_score(match),
        -exact_overlap_count,
        match.node_id,
    )


def _scan_population(
    eligible_node_ids: Iterable[str],
    prepared_query: PreparedIdentifierQuery,
    matches: list[IdentifierEntryMatch],
) -> Iterable[tuple[str, ...]]:
    """Yield each candidate's decomposed identifier, collecting matches."""
    for node_id in eligible_node_ids:
        tail = node_id.rsplit("::", 1)[-1]
        identifier_tokens = decompose_identifier(tail)
        match = _match_decomposed(node_id, tail, identifier_tokens, prepared_query)
        if match is not None:
            matches.append(match)
        yield identifier_tokens


@dataclass(frozen=True)
class IdentifierRecallResult:
    """Bounded canonical query-recall facts for one eligible population."""

    raw_query_terms: tuple[str, ...]
    normalized_query_terms: tuple[str, ...]
    morphology_relations: tuple[str, ...]
    matches: tuple[IdentifierEntryMatch, ...]
    candidate_population_count: int
    query_resolution_seconds: float
    specificity: LexicalSpecificityIndex = field(
        default_factory=lambda: LexicalSpecificityIndex(candidate_count=0)
    )

    @property
    def resolved_entry_nodes(self) -> tuple[str, ...]:
        return tuple(match.node_id for match in self.matches)

    def entry_ordering_facts(self) -> list[dict[str, object]]:
        """Per-entry ordering evidence for the bounded returned set only.

        The repository vocabulary is never emitted: this covers the entries
        that survived the cap, and the frequency view below covers the query's
        own terms.
        """
        facts: list[dict[str, object]] = []
        for rank, match in enumerate(self.matches, start=1):
            strongest = self.specificity.strongest_match_token(match)
            facts.append(
                {
                    "node_id": match.node_id,
                    "rank": rank,
                    "entry_match_kind": match.entry_match_kind,
                    "matched_query_tokens": list(match.matched_query_tokens),
                    "strongest_match_token": strongest,
                    "strongest_match_token_df": (
                        self.specificity.token_document_frequency.get(strongest, 0)
                        if strongest is not None
                        else 0
                    ),
                    "max_match_specificity": self.specificity.max_match_specificity(
                        match
                    ),
                    "identifier_precision": self.specificity.identifier_precision(
                        match
                    ),
                    "lexical_specificity_score": (
                        self.specificity.lexical_specificity_score(match)
                    ),
                }
            )
        return facts

    def as_debug_dict(self) -> dict[str, object]:
        """Return bounded navigation telemetry with no ranking or authority."""
        return {
            "raw_query_terms": list(self.raw_query_terms),
            "normalized_query_terms": list(self.normalized_query_terms),
            "resolved_entry_nodes": list(self.resolved_entry_nodes),
            "entry_match_kind": {
                match.node_id: match.entry_match_kind for match in self.matches
            },
            "morphology_relations": list(self.morphology_relations),
            "candidate_population_count": self.candidate_population_count,
            "query_resolution_seconds": self.query_resolution_seconds,
            "query_token_document_frequency": dict(
                self.specificity.token_document_frequency
            ),
            "specificity_candidate_count": self.specificity.candidate_count,
            "entry_ordering": self.entry_ordering_facts(),
        }


def resolve_identifier_candidates(
    eligible_node_ids: Iterable[str],
    query_candidates: Iterable[str],
    *,
    limit: int = 6,
) -> IdentifierRecallResult:
    """Resolve prepared concepts once over an already-eligible population.

    Candidate eligibility remains the caller's boundary.  This function owns
    identifier preparation, matching, lexical ordering, and the entry cap so
    focused fixtures and production CONTROL cannot grow separate resolution
    semantics.
    """
    started = perf_counter()
    prepared_query = prepare_identifier_query(query_candidates)
    matches: list[IdentifierEntryMatch] = []
    specificity = LexicalSpecificityIndex(candidate_count=0)

    if limit > 0 and prepared_query.raw_candidates:
        # One pass decomposes each candidate once, matches it, and feeds the
        # same tokens to the frequency map.  Ordering is therefore linear in the
        # eligible population plus the matched set, never matches x population.
        specificity = build_lexical_specificity_index(
            _scan_population(eligible_node_ids, prepared_query, matches),
            tracked_tokens=prepared_query.normalized_terms,
        )
        matches.sort(key=lambda match: entry_match_order_key(match, specificity))
        matches = matches[:limit]

    morphology_relations = tuple(
        f"{source}->{target}"
        for source, target in prepared_query.morphology_relations
    )
    return IdentifierRecallResult(
        raw_query_terms=prepared_query.raw_candidates,
        normalized_query_terms=prepared_query.normalized_terms,
        morphology_relations=morphology_relations,
        matches=tuple(matches),
        candidate_population_count=specificity.candidate_count,
        query_resolution_seconds=perf_counter() - started,
        specificity=specificity,
    )


def resolve_identifier_recall(
    query: str,
    eligible_node_ids: Iterable[str],
    *,
    query_term_limit: int = 12,
    entry_limit: int = 6,
) -> IdentifierRecallResult:
    """Canonical raw-query entry resolver used by production CONTROL."""
    query_candidates = extract_query_symbol_candidates(query, limit=query_term_limit)
    return resolve_identifier_candidates(
        eligible_node_ids,
        query_candidates,
        limit=entry_limit,
    )
