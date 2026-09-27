"""RETRIEVE.LIVE.1 - which graph nodes may compete as localization candidates.

Before asking *which candidate should rank highest*, this module answers the
question underneath it:

    which objects are legitimate localization candidates at all?

A program graph serves two jobs that are not the same job.  **Graph
representation** wants call nodes, expression nodes and file nodes, because
dependency and structure are built out of them.  **Localization** wants the
much smaller set of objects a human could open and edit as the likely source of
a task.  Conflating the two is what let a misaligned parser fragment such as
``call::e(\\n`` sit in the same competition as ``core/code_dna.py::
_classify_indent``.

So the boundary here is *eligibility*, never deletion:

    a node may exist in the graph
        and still carry  candidate_eligible = False

Edges are untouched, connectivity is untouched, and no node is removed.

What this module is not
-----------------------

It grants nothing.  Eligibility is not defect grounding, not patch basis and
not write authority; CONTROL.SAFETY.LIVE.1 continues to decide those and a
node's presence here can never widen them.  It is also not a ranking input: no
score, no weight, no confidence, and nothing here is consulted to order two
eligible candidates against each other.

It is deterministic.  It reads no files, calls no model, opens no socket and
walks no directory.  Every verdict is a function of metadata the indexing pass
already produced.

Ordering of the checks matters and is fixed, so one node always yields one
reason: kind first (a structural node is structural whatever its label looks
like), then source binding, then role, then symbol grammar, then span
consistency.

Symbol grammar is language-aware on purpose.  ``name.isascii()`` would reject
``def elevacion()`` and ``def 面積()``, which are legal in Python and in most
grammars this project parses.  The rule instead asks whether each qualified
segment is a valid *identifier* - Python's ``str.isidentifier`` implements the
Unicode UAX-31 identifier rules - after normalising the extra characters a
particular language allows.  That accepts unfamiliar Unicode and still rejects
``e(\\n``, because a raw newline and an open paren are not identifier
characters in any language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.source_file_policy import (
    SOURCE_ROLE_BY_EXTENSION,
    SOURCE_ROLE_CODE,
)


# ---------------------------------------------------------------------------
# Bounded rejection vocabulary
# ---------------------------------------------------------------------------

#: A node that may enter localization candidate competition.
ELIGIBLE = "eligible"

#: The node is real and useful to the graph, but represents structure or
#: bookkeeping rather than a source object someone could open and edit:
#: call nodes, expression nodes, file container nodes, synthetic aggregates.
STRUCTURAL_ONLY = "structural_only"

#: The node does not resolve to a repository source object: no file part, a
#: path that is not canonical repo-relative, an unrecognised extension, or
#: source-span metadata that contradicts itself.
INVALID_SOURCE_BINDING = "invalid_source_binding"

#: The symbol name cannot have come from an identifier in any language this
#: project parses - raw newlines, control characters, unbalanced delimiters,
#: string or comment residue.
MALFORMED_SYMBOL = "malformed_symbol"

#: The node kind is not one this boundary knows how to admit.
UNSUPPORTED_CANDIDATE_KIND = "unsupported_candidate_kind"

#: An implementation symbol claimed from a document, or a document object
#: claimed from source code: the indexing role and the node kind disagree.
SOURCE_ROLE_MISMATCH = "source_role_mismatch"

#: The complete vocabulary.  Reasons are a closed set, never prose.
LOCALIZATION_REJECTION_REASONS: tuple[str, ...] = (
    ELIGIBLE,
    STRUCTURAL_ONLY,
    INVALID_SOURCE_BINDING,
    MALFORMED_SYMBOL,
    UNSUPPORTED_CANDIDATE_KIND,
    SOURCE_ROLE_MISMATCH,
)


# ---------------------------------------------------------------------------
# Node-kind inventory
# ---------------------------------------------------------------------------

#: Kinds that name an implementation object a patch could target.  These are
#: the only kinds allowed to compete as a *primary* defect-localization
#: candidate.
IMPLEMENTATION_KINDS: frozenset[str] = frozenset({
    "function",
    "method",
    "constructor",
    "property",
    "class",
    "struct",
    "union",
    "enum",
    "trait",
    "interface",
    "object",
    "record",
    "type",
    # The graph's generic default when a parser reports no kind: still a
    # source symbol, so it stays admissible rather than silently dropping.
    "symbol",
})

#: Kinds that describe a document rather than code.  They remain eligible
#: navigation/analysis candidates - WAITER.LIVE.1 routes analysis tasks away
#: from defect localization, and documents are valuable evidence there - but
#: they are never primary defect targets.
DOCUMENT_KINDS: frozenset[str] = frozenset({
    "section",
    "heading",
    "document",
    "prose",
})

#: Kinds that exist to carry structure.  Useful in the graph, never a
#: localization candidate.  ``call`` and ``expression`` are the two the graph
#: builder produces in bulk; ``file`` is the container every symbol hangs off.
STRUCTURAL_KINDS: frozenset[str] = frozenset({
    "file",
    "directory",
    "module",
    "package",
    "call",
    "expression",
    "statement",
    "external",
    "dependency",
    "root",
})

#: Synthetic labels the pipeline invents.  ``<top-level>`` is the parser's
#: aggregate for module-level flow: real code, but not a symbol anyone can
#: open by name, and it duplicates its file node.  ``unknown`` is the parser's
#: own failure marker.
SYNTHETIC_SYMBOL_NAMES: frozenset[str] = frozenset({
    "<top-level>",
    "<module>",
    "<anonymous>",
    "unknown",
})

#: Qualified-name separators accepted for every language.  Splitting on these
#: lets ``Outer.inner`` and ``mod::Type`` through as qualified names while each
#: segment is still checked as an identifier.
_UNIVERSAL_QUALIFIERS: tuple[str, ...] = ("::", ".", "#")

#: Extra characters a language allows inside a single identifier segment.
#: Normalised to ``_`` before the identifier test rather than pattern-matched,
#: so Unicode letters elsewhere in the segment are untouched.
_LANGUAGE_IDENTIFIER_EXTRAS: Mapping[str, str] = {
    "javascript": "$",
    "typescript": "$",
    "typescript/javascript": "$",
    "java": "$",
    "kotlin": "$",
    "csharp": "@",
    "c": "~",
    "cpp": "~",
    "rust": "'",
    "php": "$",
}

#: The same allowance keyed by extension, for nodes that carry no language
#: metadata - graph artifacts written before RETRIEVE.LIVE.1, and callers who
#: pass a bare node id.  Without it a legitimate ``app.js::$mount`` from an old
#: artifact would be refused for lack of a language tag.
_EXTENSION_IDENTIFIER_EXTRAS: Mapping[str, str] = {
    ".js": "$", ".jsx": "$", ".mjs": "$", ".cjs": "$",
    ".ts": "$", ".tsx": "$",
    ".java": "$", ".kt": "$", ".kts": "$",
    ".cs": "@",
    ".c": "~", ".h": "~", ".cpp": "~", ".cxx": "~", ".cc": "~",
    ".hpp": "~", ".hxx": "~",
    ".rs": "'",
}


@dataclass(frozen=True)
class LocalizationVerdict:
    """One node's standing in the localization candidate population.

    ``eligible`` answers "may this node enter candidate competition at all".
    ``primary`` answers the narrower question "may it compete as the source
    location of a defect", which only source-backed implementation symbols may
    do.  A document section is eligible and not primary: real, retrievable,
    but not somewhere a code defect lives.
    """

    node_id: str
    node_kind: str
    eligible: bool
    reason: str
    primary: bool = False
    source_file: str | None = None
    symbol: str | None = None
    source_role: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Bounded debugging metadata - identifiers and verdicts, no source."""
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "candidate_eligible": self.eligible,
            "eligibility_reason": self.reason,
            "primary_localization_candidate": self.primary,
            "source_file": self.source_file,
            "source_role": self.source_role,
        }


# ---------------------------------------------------------------------------
# Symbol grammar
# ---------------------------------------------------------------------------

def _split_qualified(name: str) -> list[str]:
    segments = [name]
    for separator in _UNIVERSAL_QUALIFIERS:
        expanded: list[str] = []
        for segment in segments:
            expanded.extend(segment.split(separator))
        segments = expanded
    return segments


def is_wellformed_symbol_name(name: Any, language: str | None = None) -> bool:
    """Is ``name`` shaped like an identifier (or qualified identifier)?

    Language-aware by design: the check is UAX-31 identifier validity per
    qualified segment, not an ASCII or ``[A-Za-z0-9_]`` pattern, so a
    legitimate Unicode identifier passes and extraction residue does not.
    """
    if not isinstance(name, str) or not name:
        return False

    hint = (language or "").lower()
    extras = (
        _LANGUAGE_IDENTIFIER_EXTRAS.get(hint)
        or _EXTENSION_IDENTIFIER_EXTRAS.get(hint)
        or ""
    )
    segments = _split_qualified(name)
    if not segments:
        return False

    for segment in segments:
        if not segment:
            # A leading, trailing or doubled separator is truncation residue,
            # not a qualified name.
            return False
        probe = segment
        for character in extras:
            probe = probe.replace(character, "_")
        if not probe.isidentifier():
            return False
    return True


# ---------------------------------------------------------------------------
# Source binding
# ---------------------------------------------------------------------------

def _normalize_repo_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def _extension_of(path: str) -> str:
    tail = path.rsplit("/", 1)[-1]
    if "." not in tail:
        return ""
    return "." + tail.rsplit(".", 1)[-1].lower()


def _is_canonical_relative_path(path: str) -> bool:
    if not path or path.startswith("/") or path.endswith("/"):
        return False
    if ":" in path:  # a drive letter or a stray separator
        return False
    parts = path.split("/")
    return all(part and part not in {".", ".."} for part in parts)


def split_node_binding(node_id: str) -> tuple[str | None, str | None]:
    """Split ``path/to/file.py::symbol`` into its file and symbol halves."""
    if not isinstance(node_id, str) or "::" not in node_id:
        return None, None
    raw_file, _, symbol = node_id.partition("::")
    return _normalize_repo_path(raw_file), symbol


def _span_is_consistent(
    metadata: Mapping[str, Any],
    source_context: Mapping[str, Any] | None,
    source_file: str,
) -> bool:
    start = metadata.get("start")
    end = metadata.get("end")
    if start is None and end is None:
        # No span was recorded; the symbol binding alone carries the node.
        return True
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    if isinstance(start, bool) or isinstance(end, bool):
        return False
    if start < 0 or end < start:
        return False

    known_sizes = (source_context or {}).get("file_bytes") or {}
    size = known_sizes.get(source_file)
    if isinstance(size, int) and not isinstance(size, bool) and end > size:
        return False
    return True


# ---------------------------------------------------------------------------
# The boundary
# ---------------------------------------------------------------------------

def classify_localization_candidate(
    node_id: str,
    node_kind: str | None = None,
    *,
    metadata: Mapping[str, Any] | None = None,
    source_context: Mapping[str, Any] | None = None,
) -> LocalizationVerdict:
    """Decide whether ``node_id`` may compete as a localization candidate.

    ``source_context`` is optional already-indexed metadata - today a
    ``file_bytes`` mapping harvested from the graph's own file nodes - used to
    sanity-check spans.  Nothing here reads the repository.
    """
    metadata = metadata or {}
    kind = (node_kind or metadata.get("kind") or "").strip().lower()
    node_id = node_id if isinstance(node_id, str) else ""

    if not node_id:
        return LocalizationVerdict(
            node_id="", node_kind=kind, eligible=False,
            reason=INVALID_SOURCE_BINDING,
        )

    # 1. Kind first: structure is structure whatever the label looks like.
    if not kind:
        return LocalizationVerdict(
            node_id=node_id, node_kind="", eligible=False,
            reason=UNSUPPORTED_CANDIDATE_KIND,
        )
    if kind in STRUCTURAL_KINDS:
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=STRUCTURAL_ONLY,
        )
    if kind not in IMPLEMENTATION_KINDS and kind not in DOCUMENT_KINDS:
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=UNSUPPORTED_CANDIDATE_KIND,
        )

    # 2. A candidate must resolve to a repository source object.
    source_file, symbol = split_node_binding(node_id)
    if not source_file or not symbol:
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=INVALID_SOURCE_BINDING,
        )
    source_file = str(metadata.get("file") or source_file)
    source_file = _normalize_repo_path(source_file)
    if not _is_canonical_relative_path(source_file):
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=INVALID_SOURCE_BINDING, source_file=source_file,
            symbol=symbol,
        )

    role = SOURCE_ROLE_BY_EXTENSION.get(_extension_of(source_file))
    if role is None:
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=INVALID_SOURCE_BINDING, source_file=source_file,
            symbol=symbol,
        )

    # 3. Role and kind must agree.  An implementation symbol parsed out of a
    #    document, or a prose object claimed from source, is a role leak.
    implementation = kind in IMPLEMENTATION_KINDS
    if implementation and role != SOURCE_ROLE_CODE:
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=SOURCE_ROLE_MISMATCH, source_file=source_file,
            symbol=symbol, source_role=role,
        )
    if not implementation and role == SOURCE_ROLE_CODE:
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=SOURCE_ROLE_MISMATCH, source_file=source_file,
            symbol=symbol, source_role=role,
        )

    # 4. Synthetic aggregates are real code but not addressable symbols.
    if symbol in SYNTHETIC_SYMBOL_NAMES:
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=STRUCTURAL_ONLY, source_file=source_file, symbol=symbol,
            source_role=role,
        )

    # 5. Symbol grammar, per language, per the parser's own report.
    language = metadata.get("language") or _extension_of(source_file)
    if not is_wellformed_symbol_name(symbol, language):
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=MALFORMED_SYMBOL, source_file=source_file, symbol=symbol,
            source_role=role,
        )

    # 6. A recorded span must not contradict itself or its file.
    if not _span_is_consistent(metadata, source_context, source_file):
        return LocalizationVerdict(
            node_id=node_id, node_kind=kind, eligible=False,
            reason=INVALID_SOURCE_BINDING, source_file=source_file,
            symbol=symbol, source_role=role,
        )

    return LocalizationVerdict(
        node_id=node_id, node_kind=kind, eligible=True, reason=ELIGIBLE,
        primary=implementation and role == SOURCE_ROLE_CODE,
        source_file=source_file, symbol=symbol, source_role=role,
    )


def is_localization_candidate(
    node_id: str,
    node_kind: str | None = None,
    *,
    metadata: Mapping[str, Any] | None = None,
    source_context: Mapping[str, Any] | None = None,
) -> bool:
    """Boolean form of :func:`classify_localization_candidate`."""
    return classify_localization_candidate(
        node_id,
        node_kind,
        metadata=metadata,
        source_context=source_context,
    ).eligible


# ---------------------------------------------------------------------------
# Graph-level application
# ---------------------------------------------------------------------------

def build_source_context(graph: Any) -> dict[str, Any]:
    """Harvest span-checking context from the graph's own file nodes.

    No repository read and no second traversal: the sizes were recorded when
    the file was already open during indexing.
    """
    file_bytes: dict[str, int] = {}
    for node_id, node in (getattr(graph, "nodes", None) or {}).items():
        if (getattr(node, "type", "") or "").lower() != "file":
            continue
        size = (getattr(node, "metadata", None) or {}).get("source_bytes")
        if isinstance(size, int) and not isinstance(size, bool):
            file_bytes[_normalize_repo_path(node_id)] = size
    return {"file_bytes": file_bytes}


def iter_graph_verdicts(
    graph: Any,
    *,
    source_context: Mapping[str, Any] | None = None,
) -> Iterable[LocalizationVerdict]:
    context = source_context if source_context is not None else build_source_context(graph)
    for node_id, node in (getattr(graph, "nodes", None) or {}).items():
        yield classify_localization_candidate(
            node_id,
            getattr(node, "type", ""),
            metadata=getattr(node, "metadata", None),
            source_context=context,
        )


def localization_population_metrics(graph: Any) -> dict[str, Any]:
    """Deterministic counts of the candidate population.  No quality score."""
    nodes_by_kind: dict[str, int] = {}
    rejected_by_reason: dict[str, int] = {}
    total = 0
    eligible = 0
    primary = 0

    context = build_source_context(graph)
    for verdict in iter_graph_verdicts(graph, source_context=context):
        total += 1
        nodes_by_kind[verdict.node_kind] = nodes_by_kind.get(verdict.node_kind, 0) + 1
        if verdict.eligible:
            eligible += 1
            if verdict.primary:
                primary += 1
        else:
            rejected_by_reason[verdict.reason] = (
                rejected_by_reason.get(verdict.reason, 0) + 1
            )

    return {
        "total_graph_nodes": total,
        "nodes_by_kind": dict(sorted(nodes_by_kind.items())),
        "eligible_localization_candidates": eligible,
        "primary_localization_candidates": primary,
        "rejected_candidates": total - eligible,
        "rejected_by_reason": dict(sorted(rejected_by_reason.items())),
    }
