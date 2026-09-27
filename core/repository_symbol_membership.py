"""ANSWER.GROUND.LIVE.2 — the bounded repository symbol universe and grammar.

ANSWER.GROUND.LIVE.1 answers "may this concrete repository *file* be shown as an
established fact".  It never saw a claim with no path in it, so

    "The bug is in the PatchGenerator.generate method."

escaped intact even though no such symbol exists anywhere in the repository.

This module supplies the two pieces that closes that gap, and nothing else:

    1. a membership view over symbols the run already acquired, and
    2. a deliberately conservative grammar for recognizing when text is
       *asserting* a repository symbol rather than using ordinary words.

It is not a second grounding boundary.  ``core.answer_entity_grounding`` remains
the only place an answer is classified, downgraded or receipted; this module
holds no state, reads no file, calls no model, opens no socket, walks nothing,
and cannot decide anything about authority.

The grammar's bias is explicit: false negatives are preferable to turning every
noun into a repository entity.  A token becomes a claim only when a structured
field says it is one, when its own formatting marks it as code, when its shape
marks it as a symbol, or when the sentence introduces it as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence


PHASE_ID = "ANSWER.GROUND.LIVE.2"

#: Shared with the LIVE.1 path grammar so "settings.py" is recognized as a file
#: name by both halves of one boundary rather than drifting apart.
COMMON_REPOSITORY_EXTENSIONS: tuple[str, ...] = (
    "adoc", "asm", "bash", "bat", "c", "cc", "cfg", "clj", "cljs", "cmake",
    "conf", "cpp", "cs", "css", "csv", "cxx", "dart", "ex", "exs", "fs", "fsx",
    "go", "gradle", "graphql", "h", "hpp", "htm", "html", "hxx", "ini", "java",
    "js", "json", "jsx", "kt", "kts", "lock", "lua", "md", "mjs", "php", "pl",
    "properties", "proto", "ps1", "py", "pyi", "rb", "resx", "rs", "rst",
    "scala", "scss", "sh", "sql", "swift", "toml", "ts", "tsx", "txt", "vue",
    "xml", "yaml", "yml", "zig",
)

#: Hard bounds.  Grounding runs on every displayed answer, so nothing here may
#: scale with repository size at answer time.
MAX_SYMBOL_CLAIMS = 64
MAX_DECLARATION_SCAN_LINES = 4_000
MAX_DECLARATIONS_PER_TEXT = 256
MAX_MEMBER_RELATIONS = 40_000
MAX_SYMBOL_TEXT_LENGTH = 200

#: Resolution outcomes.  Deliberately not statuses: the caller owns the status
#: vocabulary, this module only reports what membership evidence can establish.
RESOLVED_EXISTING = "existing"
RESOLVED_EXECUTION_OBSERVED = "execution_observed"
RESOLVED_AMBIGUOUS = "ambiguous"
RESOLVED_UNKNOWN = "unknown"
RESOLVED_NOT_A_CLAIM = "not_a_claim"

#: Node kinds the parser emits for things that can *own* members.
CLASS_LIKE_KINDS = frozenset(
    {"class", "struct", "union", "enum", "trait", "interface", "object",
     "record", "type"}
)

SYMBOL_SEGMENT = r"[A-Za-z_$@~][A-Za-z0-9_$@~]*"

_EXTENSIONS = frozenset(COMMON_REPOSITORY_EXTENSIONS)
_SEGMENT_RE = re.compile(rf"^{SYMBOL_SEGMENT}$")
_QUALIFIER_SPLIT_RE = re.compile(r"::|[.#]")

#: Namespaces an answer may legitimately discuss without claiming they live in
#: the subject repository.  Only consulted when repository evidence does not
#: already know the name, so a repository class really called ``Path`` still
#: grounds normally.
EXTERNAL_NAMESPACE_ROOTS = frozenset(
    {
        # Python standard library and tooling
        "abc", "argparse", "ast", "asyncio", "base64", "collections",
        "contextlib", "copy", "csv", "dataclasses", "datetime", "decimal",
        "enum", "functools", "glob", "hashlib", "importlib", "inspect", "io",
        "itertools", "json", "logging", "math", "os", "pathlib", "pickle",
        "pip", "pytest", "random", "re", "shutil", "signal", "socket",
        "sqlite3", "string", "subprocess", "sys", "tempfile", "textwrap",
        "threading", "time", "traceback", "types", "typing", "unittest",
        "urllib", "uuid", "warnings", "yaml", "toml", "setuptools",
        # Widely used third-party roots
        "axios", "chai", "click", "django", "docker", "express", "fastapi",
        "flask", "git", "httpx", "jest", "jquery", "lodash", "mocha", "node",
        "npm", "numpy", "np", "pandas", "pd", "pydantic", "react", "requests",
        "scipy", "sklearn", "sqlalchemy", "torch", "vue",
        # Well-known external types written without their module
        "any", "array", "boolean", "component", "date", "dataframe", "decimal",
        "dict", "enum", "exception", "iterable", "json", "list", "logger",
        "map", "mapping", "math", "number", "object", "optional", "path",
        "promise", "regexp", "sequence", "series", "session", "set", "string",
        "tensor", "thread",
    }
)

#: Language builtins.  A bare ``len()`` in an explanation is not an assertion
#: that the repository defines ``len``.
LANGUAGE_BUILTIN_NAMES = frozenset(
    {
        "abs", "all", "any", "bool", "bytes", "callable", "chr", "console",
        "dict", "dir", "divmod", "enumerate", "eval", "exec", "expect",
        "fetch", "filter", "float", "format", "frozenset", "getattr",
        "hasattr", "hash", "hex", "id", "input", "int", "isinstance",
        "issubclass", "iter", "len", "list", "map", "max", "min", "next",
        "object", "open", "ord", "pow", "print", "range", "repr", "require",
        "reversed", "round", "set", "setattr", "slice", "sorted", "str", "sum",
        "super", "tuple", "type", "vars", "zip",
    }
)

#: Ordinary words a cue phrase may sweep up.  Never repository entities.
_PROSE_STOP_WORDS = frozenset(
    {
        "a", "all", "an", "and", "another", "any", "are", "as", "at", "be",
        "been", "below", "both", "but", "by", "call", "calls", "can", "class",
        "classes", "code", "definition", "definitions", "each", "either",
        "every", "file", "files", "for", "from", "function", "functions",
        "has", "have", "here", "how", "if", "in", "instance", "instances",
        "into", "is", "it", "its", "level", "may", "method", "methods",
        "module", "modules", "must", "name", "named", "names", "new", "no",
        "not", "object", "objects", "of", "old", "on", "one", "or", "other",
        "our", "same", "should", "so", "some", "symbol", "symbols", "than",
        "that", "the", "their", "then", "there", "these", "this", "those",
        "to", "two", "up", "use", "used", "uses", "value", "values",
        "variable", "variables", "was", "were", "what", "when", "where",
        "which", "while", "who", "will", "with", "your",
    }
)

_INLINE_CODE_RE = re.compile(r"`([^`\n]{1,200})`")
_QUALIFIED_SYMBOL_RE = re.compile(
    rf"(?<![A-Za-z0-9_$@~.:/\\-])"
    rf"(?P<qualified>{SYMBOL_SEGMENT}(?:(?:\.|::){SYMBOL_SEGMENT}){{1,3}})"
    rf"(?P<call>\(\s*\))?"
    rf"(?![A-Za-z0-9_$@~]|\.[A-Za-z_$@~]|::)"
)
_CALL_FORM_RE = re.compile(rf"(?<![A-Za-z0-9_$@~.])(?P<symbol>{SYMBOL_SEGMENT})\(\s*\)")
_CUE_BEFORE_RE = re.compile(
    rf"\b(?:function|method|class|symbol|helper)\s+(?:named\s+|called\s+)?"
    rf"(?P<symbol>{SYMBOL_SEGMENT})(?![A-Za-z0-9_$@~.])"
)
_CUE_AFTER_RE = re.compile(
    rf"(?<![A-Za-z0-9_$@~.])(?P<symbol>{SYMBOL_SEGMENT})\s+"
    rf"(?:function|method|class|symbol|helper)\b"
)
_CUE_LOCUS_RE = re.compile(
    rf"\b(?:bug|issue|defect|problem|failure|fault|regression)\s+"
    rf"(?:is|lies|sits|resides|occurs|happens)\s+(?:in|inside|within)\s+"
    rf"(?:the\s+)?(?P<symbol>{SYMBOL_SEGMENT})(?![A-Za-z0-9_$@~.])"
)

#: Bounded source declaration grammar.  Applied only to text the run already
#: holds in memory (acquired analysis excerpts, proposed patch content), never
#: to a file this module opened.
_DECLARATION_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?:@\w+\s+)?"
    r"(?:(?:export|public|private|protected|internal|static|final|abstract|"
    r"async|pub|open|override|declare|default)\s+)*"
    r"(?P<keyword>class|interface|struct|enum|trait|record|object|type|def|"
    r"function|func|fn)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
)

#: Brace-language members carry no declaration keyword at all — a TypeScript or
#: Java method is just ``name(args) {``.  Control-flow keywords are excluded so
#: ``if (ready) {`` never becomes a symbol.
_BRACE_METHOD_RE = re.compile(
    r"^(?P<indent>[ \t]+)"
    r"(?:(?:public|private|protected|static|async|override|readonly|abstract|"
    r"get|set)\s+)*"
    r"(?P<name>(?!(?:if|for|while|switch|catch|do|else|try|return|with|using|"
    r"new|typeof|await|throw)\b)[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*\([^)]{0,300}\)\s*(?::[^{;]{0,120})?\{\s*$"
)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_path(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def path_key(value: object) -> str:
    return normalize_path(value).casefold()


def symbol_key(path: object, symbol: object) -> str:
    return f"{path_key(path)}::{str(symbol or '').strip().casefold()}"


def symbol_tail(symbol: object) -> str:
    segments = _QUALIFIER_SPLIT_RE.split(str(symbol or "").strip())
    return segments[-1].casefold() if segments else ""


def module_names_for_path(path: object) -> tuple[str, ...]:
    """Module spellings a source file answers to, without importing anything."""

    normalized = path_key(path)
    if not normalized:
        return ()
    stem = normalized.rsplit("/", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    if not stem:
        return ()
    dotted = normalized
    if "." in dotted.rsplit("/", 1)[-1]:
        dotted = dotted.rsplit(".", 1)[0]
    names = {stem, dotted.replace("/", ".")}
    return tuple(sorted(name for name in names if name))


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

def parse_symbol_text(raw: object) -> tuple[str, str, bool] | None:
    """Split symbol-shaped text into ``(owner, member, call_form)``.

    Returns ``None`` for anything that is not a bare or qualified identifier —
    prose, paths, and ``file.py::symbol`` (which belongs to the LIVE.1 path
    grammar and must stay one entity, not two).
    """

    text = str(raw or "").strip()
    if not text or len(text) > MAX_SYMBOL_TEXT_LENGTH:
        return None

    call_form = False
    if text.endswith("()"):
        text = text[:-2].strip()
        call_form = True
    if not text:
        return None

    # Every segment has to be a whole identifier, which is what rejects prose,
    # paths, calls with arguments and stray punctuation without a second pass.
    segments = _QUALIFIER_SPLIT_RE.split(text)
    if not segments or len(segments) > 4:
        return None
    if any(not _SEGMENT_RE.match(segment) for segment in segments):
        return None
    # ``settings.py`` and ``main.py::main`` are file references.
    if segments[-1].casefold() in _EXTENSIONS:
        return None
    if len(segments) >= 2 and segments[-2].casefold() in _EXTENSIONS:
        return None

    return ".".join(segments[:-1]), segments[-1], call_form


def is_symbol_shaped(name: object) -> bool:
    """Does the token's own form mark it as an identifier rather than a word?"""

    text = str(name or "")
    if not text:
        return False
    if "_" in text or "$" in text:
        return True
    return text[:1].isupper() and any(character.islower() for character in text[1:])


def is_owner_shaped(name: object) -> bool:
    """Is the leftmost qualifier segment shaped like a type rather than a module?"""

    text = str(name or "")
    return bool(text) and text[:1].isupper() and any(c.islower() for c in text[1:])


@dataclass(frozen=True, slots=True)
class SymbolClaim:
    """One bounded symbol-shaped reference recognized in an answer."""

    raw: str
    owner: str
    member: str
    path: str = ""
    repository: str = ""
    start: int = 0
    end: int = 0
    code_formatted: bool = False
    call_form: bool = False
    structured_field: str = ""

    @property
    def qualified(self) -> str:
        return f"{self.owner}.{self.member}" if self.owner else self.member

    @property
    def identity(self) -> str:
        subject = f"{self.repository}::" if self.repository else ""
        location = f"{normalize_path(self.path)}::" if self.path else ""
        return f"{subject}{location}{self.qualified}"


def _overlaps(span: tuple[int, int], spans: Sequence[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in spans)


def extract_symbol_claims(
    text: object,
    *,
    exclude_spans: Sequence[tuple[int, int]] = (),
) -> tuple[SymbolClaim, ...]:
    """Recognize only strongly symbol-shaped repository references in prose.

    ``exclude_spans`` carries the spans the LIVE.1 path grammar already claimed
    (and any fenced code), so ``file.py::Class.method`` is never split into a
    path entity plus a phantom symbol entity.
    """

    value = str(text or "")
    if not value:
        return ()

    claimed: list[tuple[int, int]] = [
        (int(start), int(end)) for start, end in exclude_spans
    ]
    claims: list[SymbolClaim] = []

    def _record(
        span: tuple[int, int],
        raw: str,
        *,
        code_formatted: bool = False,
        cued: bool = False,
    ) -> None:
        if len(claims) >= MAX_SYMBOL_CLAIMS or _overlaps(span, claimed):
            return
        parsed = parse_symbol_text(raw)
        if parsed is None:
            return
        owner, member, call_form = parsed
        if cued and not owner and member.casefold() in _PROSE_STOP_WORDS:
            return
        claimed.append(span)
        claims.append(
            SymbolClaim(
                raw=raw,
                owner=owner,
                member=member,
                start=span[0],
                end=span[1],
                code_formatted=code_formatted,
                call_form=call_form,
            )
        )

    # 1. Inline code is the strongest formatting signal an answer can give.
    for match in _INLINE_CODE_RE.finditer(value):
        _record(match.span(), match.group(1).strip(), code_formatted=True)

    # 2. Qualified forms: Owner.member, Owner::member, module.symbol.
    for match in _QUALIFIED_SYMBOL_RE.finditer(value):
        _record(match.span(), match.group(0).strip())

    # 3. Explicit call formatting.
    for match in _CALL_FORM_RE.finditer(value):
        _record(match.span(), match.group(0).strip(), cued=True)

    # 4. Sentence cues that introduce a token as a repository entity.
    for pattern in (_CUE_BEFORE_RE, _CUE_AFTER_RE, _CUE_LOCUS_RE):
        for match in pattern.finditer(value):
            _record(match.span("symbol"), match.group("symbol"), cued=True)

    claims.sort(key=lambda claim: (claim.start, claim.end))
    return tuple(claims[:MAX_SYMBOL_CLAIMS])


# ---------------------------------------------------------------------------
# Declarations already held in memory
# ---------------------------------------------------------------------------

def declared_symbols(text: object) -> tuple[tuple[str, str], ...]:
    """Bounded ``(owner, name)`` declarations visible in text already in memory.

    Used for acquired analysis excerpts and for proposed patch content.  It
    opens nothing; the string was handed to it.  Ownership is decided by the
    declaration's own indentation, which is enough for the member relations an
    answer actually cites and admits no repository read.
    """

    value = str(text or "")
    if not value:
        return ()

    declarations: list[tuple[str, str]] = []
    owners: list[tuple[int, str]] = []
    for line_number, line in enumerate(value.splitlines()):
        if line_number >= MAX_DECLARATION_SCAN_LINES:
            break
        if len(declarations) >= MAX_DECLARATIONS_PER_TEXT:
            break
        match = _DECLARATION_RE.match(line)
        keyword = match.group("keyword").casefold() if match is not None else ""
        if match is None:
            match = _BRACE_METHOD_RE.match(line)
        if match is None:
            continue
        column = len(match.group("indent").expandtabs(4))
        while owners and owners[-1][0] >= column:
            owners.pop()
        name = match.group("name")
        owner = owners[-1][1] if owners else ""
        declarations.append((owner, name))
        if keyword in CLASS_LIKE_KINDS:
            owners.append((column, name))
    return tuple(declarations)


def member_relations_from_spans(
    entries: Iterable[tuple[str, str, str, int, int]],
) -> frozenset[str]:
    """Derive ``path::Owner.member`` from spans the graph already recorded.

    ``entries`` are ``(path, symbol, kind, start, end)`` tuples taken from
    already-loaded node metadata.  A linear sweep per file replaces any pairwise
    containment test, and nothing is reparsed, reread or rebuilt.
    """

    by_file: dict[str, list[tuple[int, int, str, str]]] = {}
    for path, symbol, kind, start, end in entries:
        if not symbol or not isinstance(start, int) or not isinstance(end, int):
            continue
        if isinstance(start, bool) or isinstance(end, bool) or end < start:
            continue
        by_file.setdefault(path_key(path), []).append(
            (start, end, str(symbol), str(kind or "").casefold())
        )

    relations: set[str] = set()
    for file_path, items in by_file.items():
        if not any(kind in CLASS_LIKE_KINDS for _, _, _, kind in items):
            continue
        items.sort(key=lambda item: (item[0], -item[1]))
        stack: list[tuple[int, int, str]] = []
        for start, end, symbol, kind in items:
            while stack and stack[-1][1] <= start:
                stack.pop()
            if stack:
                innermost = stack[-1][2]
                relations.add(f"{file_path}::{innermost}.{symbol}".casefold())
                chain = ".".join(owner for _, _, owner in stack)
                relations.add(f"{file_path}::{chain}.{symbol}".casefold())
                if len(relations) >= MAX_MEMBER_RELATIONS:
                    return frozenset(relations)
            if kind in CLASS_LIKE_KINDS:
                stack.append((start, end, symbol))
    return frozenset(relations)


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SymbolMembership:
    """A bounded membership view over symbols the run already established.

    Everything here is a lookup over evidence collected elsewhere.  There is no
    traversal, no query, no ranking and no notion of confidence: a symbol either
    binds to acquired repository evidence or it does not.
    """

    source_symbols: frozenset[str] = frozenset()
    member_relations: frozenset[str] = frozenset()
    execution_symbols: frozenset[str] = frozenset()
    known_paths: frozenset[str] = frozenset()

    _tails: dict[str, frozenset[str]] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )
    _execution_tails: dict[str, frozenset[str]] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )
    _member_pairs: frozenset[str] = field(
        init=False, repr=False, compare=False, default=frozenset()
    )
    _modules: dict[str, frozenset[str]] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )
    _known_names: frozenset[str] = field(
        init=False, repr=False, compare=False, default=frozenset()
    )

    def __post_init__(self) -> None:
        tails: dict[str, set[str]] = {}
        for identity in self.source_symbols:
            file_part, separator, symbol = identity.partition("::")
            if not separator or not symbol:
                continue
            tails.setdefault(symbol_tail(symbol), set()).add(f"{file_part}::{symbol}")
        execution_tails: dict[str, set[str]] = {}
        for identity in self.execution_symbols:
            file_part, separator, symbol = identity.partition("::")
            if not separator or not symbol:
                continue
            execution_tails.setdefault(symbol_tail(symbol), set()).add(identity)

        pairs: set[str] = set()
        for relation in self.member_relations:
            _, separator, qualified = relation.partition("::")
            if separator and "." in qualified:
                pairs.add(qualified)
        # A dotted symbol recorded directly (``file.py::Class.method``) is the
        # same kind of relation and must resolve identically.
        for identity in self.source_symbols:
            _, separator, symbol = identity.partition("::")
            if separator and "." in symbol:
                pairs.add(symbol)

        modules: dict[str, set[str]] = {}
        for file_path in set(self.known_paths) | {
            identity.partition("::")[0] for identity in self.source_symbols
        }:
            if not file_path:
                continue
            for name in module_names_for_path(file_path):
                modules.setdefault(name, set()).add(file_path)

        known = set(tails) | set(modules)
        for pair in pairs:
            known.add(pair.split(".", 1)[0].casefold())

        object.__setattr__(
            self, "_tails", {key: frozenset(value) for key, value in tails.items()}
        )
        object.__setattr__(
            self,
            "_execution_tails",
            {key: frozenset(value) for key, value in execution_tails.items()},
        )
        object.__setattr__(self, "_member_pairs", frozenset(pairs))
        object.__setattr__(
            self, "_modules", {key: frozenset(value) for key, value in modules.items()}
        )
        object.__setattr__(self, "_known_names", frozenset(known))

    # -- introspection used by the boundary and its tests --------------------

    @property
    def member_pairs(self) -> frozenset[str]:
        return self._member_pairs

    @property
    def known_owner_names(self) -> frozenset[str]:
        """Names repository evidence already knows: symbols, modules, owners."""

        return self._known_names

    def knows_path(self, path: object) -> bool:
        return path_key(path) in self.known_paths

    def is_repository_claim(self, claim: SymbolClaim) -> bool:
        """Is this reference asserting a symbol *in the subject repository*?

        External APIs are not repository claims, and ordinary prose caught by a
        cue is not either.  Repository evidence wins over both heuristics: a
        repository class genuinely named ``Path`` is still a repository claim.
        """

        if claim.structured_field:
            return True
        if claim.owner:
            root = claim.owner.split(".", 1)[0]
            if root.casefold() in self._known_names:
                return True
            if root.casefold() in EXTERNAL_NAMESPACE_ROOTS:
                return False
            return is_owner_shaped(root)
        if claim.member.casefold() in self._tails:
            return True
        if claim.member.casefold() in LANGUAGE_BUILTIN_NAMES:
            return False
        return claim.code_formatted or claim.call_form or is_symbol_shaped(claim.member)

    # -- resolution ----------------------------------------------------------

    def resolve(self, claim: SymbolClaim, *, context_path: str = "") -> str:
        """Report only what membership evidence establishes about one claim."""

        member = claim.member.casefold()
        owner = claim.owner.casefold()
        location = path_key(claim.path or context_path)

        if location:
            if owner:
                if f"{location}::{owner}.{member}" in self.member_relations:
                    return RESOLVED_EXISTING
                if f"{location}::{owner}.{member}" in self.source_symbols:
                    return RESOLVED_EXISTING
                if owner in module_names_for_path(location) and (
                    f"{location}::{member}" in self.source_symbols
                ):
                    return RESOLVED_EXISTING
                return (
                    RESOLVED_UNKNOWN
                    if self.is_repository_claim(claim)
                    else RESOLVED_NOT_A_CLAIM
                )
            if f"{location}::{member}" in self.source_symbols:
                return RESOLVED_EXISTING
            if f"{location}::{member}" in self.execution_symbols:
                return RESOLVED_EXECUTION_OBSERVED
            if not self.is_repository_claim(claim):
                return RESOLVED_NOT_A_CLAIM
            return RESOLVED_UNKNOWN

        if owner:
            if f"{owner}.{member}" in self._member_pairs:
                return RESOLVED_EXISTING
            candidates = self._modules.get(owner) or frozenset()
            hits = [
                candidate
                for candidate in candidates
                if f"{candidate}::{member}" in self.source_symbols
            ]
            if len(hits) == 1:
                return RESOLVED_EXISTING
            if len(hits) > 1:
                return RESOLVED_AMBIGUOUS
            if not self.is_repository_claim(claim):
                return RESOLVED_NOT_A_CLAIM
            return RESOLVED_UNKNOWN

        identities = self._tails.get(member) or frozenset()
        if len(identities) == 1:
            return RESOLVED_EXISTING
        if len(identities) > 1:
            return RESOLVED_AMBIGUOUS
        observed = self._execution_tails.get(member) or frozenset()
        if len(observed) == 1:
            return RESOLVED_EXECUTION_OBSERVED
        if len(observed) > 1:
            return RESOLVED_AMBIGUOUS
        if not self.is_repository_claim(claim):
            return RESOLVED_NOT_A_CLAIM
        return RESOLVED_UNKNOWN

    def resolves_within(self, claim: SymbolClaim, path: object) -> bool:
        """Does a nearby grounded file make this claim's identity exact?"""

        location = path_key(path)
        if not location:
            return False
        member = claim.member.casefold()
        owner = claim.owner.casefold()
        if owner:
            return (
                f"{location}::{owner}.{member}" in self.member_relations
                or f"{location}::{owner}.{member}" in self.source_symbols
            )
        return f"{location}::{member}" in self.source_symbols


__all__ = [
    "CLASS_LIKE_KINDS",
    "COMMON_REPOSITORY_EXTENSIONS",
    "EXTERNAL_NAMESPACE_ROOTS",
    "LANGUAGE_BUILTIN_NAMES",
    "MAX_SYMBOL_CLAIMS",
    "PHASE_ID",
    "RESOLVED_AMBIGUOUS",
    "RESOLVED_EXECUTION_OBSERVED",
    "RESOLVED_EXISTING",
    "RESOLVED_NOT_A_CLAIM",
    "RESOLVED_UNKNOWN",
    "SymbolClaim",
    "SymbolMembership",
    "declared_symbols",
    "extract_symbol_claims",
    "is_owner_shaped",
    "is_symbol_shaped",
    "member_relations_from_spans",
    "module_names_for_path",
    "normalize_path",
    "parse_symbol_text",
    "path_key",
    "symbol_key",
    "symbol_tail",
]
