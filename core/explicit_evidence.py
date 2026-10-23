"""INPUT.1 — deterministic explicit-evidence extraction (pre-semantic).

This module is the first stage of the input-understanding pipeline:

    raw user prompt -> ExplicitEvidence -> Semantic Waiter -> Task Contract

Its single job is to preserve the *literal commitments* a user made, so that a
later semantic interpreter cannot silently delete them.  It deliberately does
not attempt natural-language understanding: everything it reports is a span the
user actually typed.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, selects no execution mode, and grants
no authority of any kind.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from core.behavioral_expectation import (
    MAX_BEHAVIORAL_EXPECTATIONS,
    BehavioralExpectation,
    extract_behavioral_expectations,
)
from core.explicit_design_evidence import DesignEvidence, extract_design_evidence


PHASE_ID = "INPUT.1"

# ── Bounds ────────────────────────────────────────────────────────────────────
#: The raw request itself is never truncated (see ``core.task_contract``); only
#: the derived evidence collections below are bounded.
MAX_SCAN_CHARS = 100_000
MAX_ITEM_CHARS = 240
MAX_NAMED_ENTITIES = 24
MAX_URLS = 16
MAX_FILE_PATHS = 32
MAX_QUOTED_TERMS = 32
MAX_LIST_ITEMS = 64
MAX_COMPARISONS = 8
MAX_COMPARISON_SUBJECTS = 4
MAX_FRAMEWORK_VALUES = 32
MAX_CONSTRAINTS = 32
MAX_REQUESTED_OUTPUTS = 8
#: DEFECT.FACT.LIVE.1 owns this one; it is re-exported here so intake and the
#: typed-fact extractor cannot disagree about how many claims an order carries.
MAX_BEHAVIORAL_EXPECTATION_ITEMS = MAX_BEHAVIORAL_EXPECTATIONS

_HARD_ITEM_SCAN_CAP = 512

# ── Stable vocabularies ───────────────────────────────────────────────────────
#: Framework kinds a user can literally name.
FRAMEWORK_TYPES: tuple[str, ...] = (
    "rubric",
    "framework",
    "criteria",
    "scale",
    "categories",
    "checklist",
)

#: Constraint kinds recoverable from literal marker words.
CONSTRAINT_KINDS: tuple[str, ...] = (
    "requirement",
    "prohibition",
    "restriction",
    "authority_reference",
    "framework_reference",
)

#: Output formats recoverable from literal request cues.
OUTPUT_FORMATS: tuple[str, ...] = (
    "table",
    "json",
    "markdown",
    "bullet_list",
    "report",
    "yaml",
    "csv",
    "diagram",
    "prose",
)

#: Comparison markers a user can literally write.
COMPARISON_MARKERS: tuple[str, ...] = (
    "against",
    "versus",
    "vs",
    "with",
    "to",
    "and",
)


# ── Patterns ──────────────────────────────────────────────────────────────────

_LIST_RE = re.compile(r"^[ \t]*(?:[-*+•]|\d+[.)])[ \t]+(\S.*?)[ \t]*$")

_FRAMEWORK_WORD = r"(rubric|framework|criteria|criterion|scale|categories|checklist|dimensions)"
_FRAMEWORK_CUE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\busing\s+the\s+following\s+" + _FRAMEWORK_WORD, re.I),
    re.compile(r"\busing\s+(?:this|the)\s+" + _FRAMEWORK_WORD, re.I),
    re.compile(r"\baccording\s+to\s+(?:the\s+following|this|the)\s+" + _FRAMEWORK_WORD, re.I),
    re.compile(r"\bwith\s+the\s+following\s+" + _FRAMEWORK_WORD, re.I),
    re.compile(r"\b" + _FRAMEWORK_WORD + r"\s*:", re.I),
)
_FRAMEWORK_TYPE_ALIASES = {"criterion": "criteria", "dimensions": "criteria"}

_ACRONYM_RE = re.compile(r"\b(?:[A-Za-z]\.){2,}[A-Za-z]?\b")
_TITLE_RUN_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[ \-][A-Z][A-Za-z0-9]*){0,3}\b")

_URL_RE = re.compile(r"https?://[^\s<>\"'`)\]]+", re.I)

_PATH_EXT = (
    r"(?:py|pyi|md|rst|txt|json|jsonl|ya?ml|toml|ini|cfg|sh|ps1|bat|js|jsx|ts|tsx"
    r"|rs|go|java|rb|php|c|h|cc|cpp|hpp|cs|sql|html|css|csv|tsv|lock)"
)
_PATH_RE = re.compile(
    r"(?<![\w./\\-])((?:[A-Za-z0-9_.\-]+[/\\])*[A-Za-z0-9_.\-]+\." + _PATH_EXT + r")\b",
    re.I,
)

_QUOTE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\"([^\"\n]{1,240})\""),
    re.compile("“([^”\n]{1,240})”"),
    re.compile(r"`([^`\n]{1,240})`"),
)

_CLAUSE_STOP_RE = re.compile(
    r"(?:[,;:]"
    r"|[.!?](?=\s|$)"
    r"|\n"
    r"|\s+(?:using|according\s+to|with\s+the\s+following|based\s+on|per\s+the|and\s+then)\b"
    r"|\s+(?:as|in)\s+(?:a\s+)?"
    r"(?:table|json|markdown|yaml|csv|report|diagram|bullet|tabular)\b)",
    re.I,
)

_COMPARE_VERB_RE = re.compile(
    r"\b(?:compare|contrast)\s+(?P<left>.+?)\s+(?P<marker>with|to|against|versus|vs\.?|and)\s+(?P<right>.+)",
    re.I,
)
_ANALYZE_AGAINST_RE = re.compile(
    r"\b(?:analyze|analyse|evaluate|benchmark|assess|measure|review|weigh)\s+"
    r"(?P<left>.+?)\s+(?P<marker>against|versus|vs\.?)\s+(?P<right>.+)",
    re.I,
)
_BARE_VS_RE = re.compile(
    r"(?P<left>[A-Za-z0-9][\w .&\-]*?)\s+(?P<marker>vs\.?|versus)\s+(?P<right>.+)",
    re.I,
)
_COMPARISON_RES = (_COMPARE_VERB_RE, _ANALYZE_AGAINST_RE, _BARE_VS_RE)

_CONSTRAINT_MARKER_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:must\s+not|may\s+not|should\s+not|cannot|can\s+not)\b", re.I), "prohibition"),
    (re.compile(r"\b(?:do\s+not|don't|never)\b", re.I), "prohibition"),
    (re.compile(r"\b(?:must|shall|required\s+to)\b", re.I), "requirement"),
    (re.compile(r"\baccording\s+to\b", re.I), "authority_reference"),
    (re.compile(r"\bonly\b", re.I), "restriction"),
)

_OUTPUT_CUE_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:as|in)\s+(?:a\s+)?table\b|\btable\s+format\b|\btabular\b", re.I), "table"),
    (re.compile(r"\b(?:as|in)\s+json\b|\bjson\s+format\b", re.I), "json"),
    (re.compile(r"\b(?:as|in)\s+markdown\b|\bmarkdown\s+format\b", re.I), "markdown"),
    (re.compile(r"\bas\s+(?:a\s+)?bullet(?:ed)?\s+list\b|\bas\s+bullets\b|\bbullet\s+points\b", re.I), "bullet_list"),
    (re.compile(r"\bas\s+(?:a\s+)?report\b|\bwrite\s+(?:a\s+)?report\b", re.I), "report"),
    (re.compile(r"\b(?:as|in)\s+yaml\b", re.I), "yaml"),
    (re.compile(r"\b(?:as|in)\s+csv\b", re.I), "csv"),
    (re.compile(r"\bas\s+(?:a\s+)?diagram\b", re.I), "diagram"),
)

#: Tokens that may never start or end a named-entity run.  These are command
#: verbs and function words, not names.
_RUN_EDGE_STOPWORDS: frozenset[str] = frozenset({
    "a", "about", "add", "against", "an", "analyse", "analyze", "and", "are",
    "as", "assess", "benchmark", "build", "but", "by", "can", "check", "compare",
    "contrast", "could", "create", "delete", "describe", "do", "does", "evaluate",
    "explain", "fix", "for", "from", "give", "how", "if", "implement", "in",
    "into", "is", "it", "make", "measure", "or", "per", "please", "refactor",
    "remove", "review", "should", "show", "summarize", "test", "that", "the",
    "then", "this", "to", "update", "use", "using", "versus", "vs", "weigh",
    "what", "when", "where", "which", "who", "why", "with", "would", "write",
})

_LEADING_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+", re.I)

_TRAILING_FILLER: frozenset[str] = frozenset({
    "please", "thanks", "now", "today", "asap", "ok", "okay", "too", "also",
})

_MIN_ACRONYM_CHARS = 3


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ExplicitComparison:
    """A comparison the user literally wrote (``compare A with B``)."""

    subjects: tuple[str, ...]
    marker: str
    text: str

    def __post_init__(self) -> None:
        if len(self.subjects) < 2:
            raise ValueError("an explicit comparison needs at least two subjects")
        if len(self.subjects) > MAX_COMPARISON_SUBJECTS:
            raise ValueError("explicit comparison subjects exceed the supported bound")

    def as_dict(self) -> dict[str, Any]:
        return {
            "subjects": list(self.subjects),
            "marker": self.marker,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class ExplicitFramework:
    """An evaluation framework / rubric the user literally supplied."""

    type: str
    values: tuple[str, ...]
    ordered: bool
    cue_text: str

    def __post_init__(self) -> None:
        if self.type not in FRAMEWORK_TYPES:
            raise ValueError(f"unsupported framework type: {self.type!r}")
        if not self.values:
            raise ValueError("an explicit framework needs at least one value")
        if len(self.values) > MAX_FRAMEWORK_VALUES:
            raise ValueError("explicit framework values exceed the supported bound")

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "values": list(self.values),
            "ordered": self.ordered,
            "cue_text": self.cue_text,
        }


@dataclass(frozen=True, slots=True)
class ExplicitConstraint:
    """A literal commitment marker (``must`` / ``do not`` / ``only`` / ...)."""

    kind: str
    text: str
    marker: str

    def __post_init__(self) -> None:
        if self.kind not in CONSTRAINT_KINDS:
            raise ValueError(f"unsupported constraint kind: {self.kind!r}")

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "text": self.text, "marker": self.marker}


@dataclass(frozen=True, slots=True)
class ExplicitRequestedOutput:
    """A literally requested output format."""

    format: str
    evidence_text: str

    def __post_init__(self) -> None:
        if self.format not in OUTPUT_FORMATS:
            raise ValueError(f"unsupported output format: {self.format!r}")

    def as_dict(self) -> dict[str, Any]:
        return {"format": self.format, "evidence_text": self.evidence_text}


@dataclass(frozen=True, slots=True)
class ExplicitEvidence:
    """Everything the user literally supplied, before any interpretation."""

    named_entities: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    file_paths: tuple[str, ...] = ()
    quoted_terms: tuple[str, ...] = ()
    list_items: tuple[str, ...] = ()
    comparisons: tuple[ExplicitComparison, ...] = ()
    framework: ExplicitFramework | None = None
    requested_outputs: tuple[ExplicitRequestedOutput, ...] = ()
    constraints: tuple[ExplicitConstraint, ...] = ()
    #: DEFECT.FACT.LIVE.1 — explicit "should be X, is Y" claims, typed once
    #: here so no downstream consumer re-reads the user's sentence for them.
    behavioral_expectations: tuple[BehavioralExpectation, ...] = ()
    truncated_fields: tuple[str, ...] = ()
    #: OOP.INTENT.DESIGN.1 — additive typed literals, owned by this intake pass.
    design_evidence: DesignEvidence = field(default_factory=DesignEvidence)

    def is_empty(self) -> bool:
        return not (
            self.named_entities
            or self.urls
            or self.file_paths
            or self.quoted_terms
            or self.list_items
            or self.comparisons
            or self.framework
            or self.requested_outputs
            or self.constraints
            or self.behavioral_expectations
        )

    def comparison_subjects(self) -> tuple[str, ...]:
        """Every subject named inside an explicit comparison, in order."""
        out: list[str] = []
        seen: set[str] = set()
        for comparison in self.comparisons:
            for subject in comparison.subjects:
                key = subject.casefold()
                if key not in seen:
                    seen.add(key)
                    out.append(subject)
        return tuple(out)

    def as_dict(self) -> dict[str, Any]:
        return {
            "named_entities": list(self.named_entities),
            "urls": list(self.urls),
            "file_paths": list(self.file_paths),
            "quoted_terms": list(self.quoted_terms),
            "list_items": list(self.list_items),
            "comparisons": [item.as_dict() for item in self.comparisons],
            "framework": self.framework.as_dict() if self.framework else None,
            "requested_outputs": [item.as_dict() for item in self.requested_outputs],
            "constraints": [item.as_dict() for item in self.constraints],
            "behavioral_expectations": [
                item.as_dict() for item in self.behavioral_expectations
            ],
            "truncated_fields": list(self.truncated_fields),
            **({"design_evidence": self.design_evidence.as_dict()}
               if not self.design_evidence.is_empty() else {}),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _blank_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Replace ``spans`` with spaces, preserving every offset in ``text``."""
    if not spans:
        return text
    chars = list(text)
    for start, end in spans:
        for index in range(start, min(end, len(chars))):
            chars[index] = " "
    return "".join(chars)


def _bounded(values: list[str], limit: int, field: str, truncated: list[str]) -> tuple[str, ...]:
    if len(values) > limit:
        truncated.append(field)
        return tuple(values[:limit])
    return tuple(values)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _first_clause(text: str) -> str:
    match = _CLAUSE_STOP_RE.search(text)
    return text[: match.start()] if match else text


def _strip_trailing_filler(text: str) -> str:
    value = text.strip()
    while True:
        parts = value.split()
        if len(parts) > 1 and parts[-1].casefold().strip(".,;:!?") in _TRAILING_FILLER:
            value = " ".join(parts[:-1]).strip()
            continue
        return value


def _clean_subject(text: str) -> str:
    value = _first_clause(text).strip()
    value = _LEADING_ARTICLE_RE.sub("", value).strip()
    value = _strip_trailing_filler(value)
    value = value.strip(" \t\"'`“”")
    return value[:MAX_ITEM_CHARS].strip()


def _accepts_run(token_count: int, single: str) -> bool:
    if token_count >= 2:
        return True
    if len(single) >= 2 and single.isupper():
        return True
    return any(char.isupper() for char in single[1:])


def _trim_run(run: str) -> str:
    tokens = run.split()
    while tokens and tokens[0].casefold() in _RUN_EDGE_STOPWORDS:
        tokens.pop(0)
    while tokens and tokens[-1].casefold() in _RUN_EDGE_STOPWORDS:
        tokens.pop()
    return " ".join(tokens)


def _clauses(text: str) -> Iterator[str]:
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        for part in re.split(r"(?<=[.!?])(?=\s)", stripped):
            clause = part.strip()
            if clause:
                yield clause


# ── Extractors ────────────────────────────────────────────────────────────────

def _extract_urls(text: str) -> tuple[list[str], list[tuple[int, int]]]:
    values: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in _URL_RE.finditer(text):
        raw = match.group(0)
        trimmed = raw.rstrip(".,;:!?")
        if trimmed:
            values.append(trimmed)
            spans.append((match.start(), match.start() + len(raw)))
    return _dedupe(values), spans


def _extract_named_entities(text: str, url_spans: list[tuple[int, int]]) -> list[str]:
    scannable = _blank_spans(text, url_spans)

    found: list[tuple[int, str]] = []
    acronym_spans: list[tuple[int, int]] = []
    for match in _ACRONYM_RE.finditer(scannable):
        value = match.group(0)
        acronym_spans.append(match.span())
        if len(value) >= _MIN_ACRONYM_CHARS:
            found.append((match.start(), value))

    without_acronyms = _blank_spans(scannable, acronym_spans)
    for match in _TITLE_RUN_RE.finditer(without_acronyms):
        trimmed = _trim_run(match.group(0))
        if not trimmed:
            continue
        tokens = trimmed.split()
        if _accepts_run(len(tokens), tokens[0]):
            found.append((match.start(), trimmed[:MAX_ITEM_CHARS]))

    found.sort(key=lambda item: item[0])
    return _dedupe([value for _, value in found])


def _extract_file_paths(text: str, url_spans: list[tuple[int, int]]) -> list[str]:
    scannable = _blank_spans(text, url_spans)
    return _dedupe([match.group(1) for match in _PATH_RE.finditer(scannable)])


def _extract_quoted_terms(text: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for pattern in _QUOTE_RES:
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            if value:
                found.append((match.start(), value[:MAX_ITEM_CHARS]))
    found.sort(key=lambda item: item[0])
    return _dedupe([value for _, value in found])


def _extract_list_items(text: str) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []
    offset = 0
    for line in text.split("\n"):
        match = _LIST_RE.match(line)
        if match:
            value = match.group(1).strip()[:MAX_ITEM_CHARS]
            if value:
                items.append((offset, value))
                if len(items) >= _HARD_ITEM_SCAN_CAP:
                    break
        offset += len(line) + 1
    return items


def _find_framework_cue(text: str) -> tuple[int, int, str, str] | None:
    best: tuple[int, int, str, str] | None = None
    for pattern in _FRAMEWORK_CUE_RES:
        match = pattern.search(text)
        if match is None:
            continue
        word = match.group(1).casefold()
        kind = _FRAMEWORK_TYPE_ALIASES.get(word, word)
        if kind not in FRAMEWORK_TYPES:
            continue
        candidate = (match.start(), match.end(), kind, match.group(0))
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best


def _extract_framework(
    text: str,
    list_items: list[tuple[int, str]],
) -> tuple[ExplicitFramework | None, bool]:
    cue = _find_framework_cue(text)
    if cue is None:
        return None, False

    _, cue_end, kind, cue_text = cue
    values = [value for offset, value in list_items if offset > cue_end]
    if not values:
        return None, False

    truncated = len(values) > MAX_FRAMEWORK_VALUES
    return (
        ExplicitFramework(
            type=kind,
            values=tuple(values[:MAX_FRAMEWORK_VALUES]),
            ordered=True,
            cue_text=cue_text,
        ),
        truncated,
    )


def _extract_comparisons(text: str) -> list[ExplicitComparison]:
    found: list[ExplicitComparison] = []
    seen: set[tuple[str, ...]] = set()
    for pattern in _COMPARISON_RES:
        for match in pattern.finditer(text):
            left = _clean_subject(match.group("left"))
            right = _clean_subject(match.group("right"))
            if not left or not right:
                continue
            if left.casefold() in _RUN_EDGE_STOPWORDS or right.casefold() in _RUN_EDGE_STOPWORDS:
                continue
            if left.casefold() == right.casefold():
                continue
            key = tuple(sorted((left.casefold(), right.casefold())))
            if key in seen:
                continue
            seen.add(key)
            marker = match.group("marker").casefold().rstrip(".")
            found.append(
                ExplicitComparison(
                    subjects=(left, right),
                    marker=marker,
                    text=_first_clause(match.group(0)).strip()[:MAX_ITEM_CHARS],
                )
            )
    return found


def _extract_constraints(text: str) -> list[ExplicitConstraint]:
    found: list[ExplicitConstraint] = []
    seen: set[tuple[str, str]] = set()
    for clause in _clauses(text):
        cleaned = clause.rstrip(".!?").strip()
        if not cleaned:
            continue

        framework_cue = _find_framework_cue(clause)
        matched: tuple[str, str] | None = None
        for pattern, kind in _CONSTRAINT_MARKER_RES:
            marker_match = pattern.search(clause)
            if marker_match is not None:
                matched = (kind, marker_match.group(0).casefold())
                break
        if matched is None and framework_cue is not None:
            matched = ("framework_reference", framework_cue[3].casefold())
        if matched is None:
            continue

        kind, marker = matched
        key = (kind, cleaned.casefold())
        if key in seen:
            continue
        seen.add(key)
        found.append(
            ExplicitConstraint(kind=kind, text=cleaned[:MAX_ITEM_CHARS], marker=marker)
        )
    return found


def _extract_requested_outputs(text: str) -> list[ExplicitRequestedOutput]:
    found: list[tuple[int, ExplicitRequestedOutput]] = []
    seen: set[str] = set()
    for pattern, fmt in _OUTPUT_CUE_RES:
        match = pattern.search(text)
        if match is None or fmt in seen:
            continue
        seen.add(fmt)
        found.append(
            (match.start(), ExplicitRequestedOutput(format=fmt, evidence_text=match.group(0)))
        )
    found.sort(key=lambda item: item[0])
    return [item for _, item in found]


# ── Public entry point ────────────────────────────────────────────────────────

def extract_explicit_evidence(raw_text: str) -> ExplicitEvidence:
    """Extract every literal commitment found in ``raw_text``.

    Deterministic and pure: identical input always yields identical evidence.
    Nothing here interprets meaning — a value appears only when the user typed
    it.
    """
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")

    truncated: list[str] = []
    text = raw_text
    if len(text) > MAX_SCAN_CHARS:
        text = text[:MAX_SCAN_CHARS]
        truncated.append("scanned_text")

    urls, url_spans = _extract_urls(text)
    named_entities = _extract_named_entities(text, url_spans)
    file_paths = _extract_file_paths(text, url_spans)
    quoted_terms = _extract_quoted_terms(text)

    scanned_items = _extract_list_items(text)
    framework, framework_truncated = _extract_framework(text, scanned_items)
    if framework_truncated:
        truncated.append("framework_values")

    comparisons = _extract_comparisons(text)
    if len(comparisons) > MAX_COMPARISONS:
        truncated.append("comparisons")
        comparisons = comparisons[:MAX_COMPARISONS]

    constraints = _extract_constraints(text)
    if len(constraints) > MAX_CONSTRAINTS:
        truncated.append("constraints")
        constraints = constraints[:MAX_CONSTRAINTS]

    requested_outputs = _extract_requested_outputs(text)[:MAX_REQUESTED_OUTPUTS]

    # DEFECT.FACT.LIVE.1.  Extraction happens exactly here, in the one pass that
    # already reads the order literally; every later consumer reads the typed
    # record rather than the prose it came from.
    behavioral_expectations, behavior_truncated = extract_behavioral_expectations(text)
    if behavior_truncated:
        truncated.append("behavioral_expectations")

    return ExplicitEvidence(
        named_entities=_bounded(named_entities, MAX_NAMED_ENTITIES, "named_entities", truncated),
        urls=_bounded(urls, MAX_URLS, "urls", truncated),
        file_paths=_bounded(file_paths, MAX_FILE_PATHS, "file_paths", truncated),
        quoted_terms=_bounded(quoted_terms, MAX_QUOTED_TERMS, "quoted_terms", truncated),
        list_items=_bounded(
            [value for _, value in scanned_items], MAX_LIST_ITEMS, "list_items", truncated
        ),
        comparisons=tuple(comparisons),
        framework=framework,
        requested_outputs=tuple(requested_outputs),
        constraints=tuple(constraints),
        behavioral_expectations=behavioral_expectations,
        truncated_fields=tuple(dict.fromkeys(truncated)),
        design_evidence=extract_design_evidence(raw_text),
    )
