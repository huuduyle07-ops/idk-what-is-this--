"""PATCH.MINIMAL.LIVE.2 — bounded local implementation novelty.

``safe_minimal``'s identifier rule was one line of lexical set arithmetic::

    new = identifiers(patched_snippet) - identifiers(target_snippet)
                                       - keywords - language_builtins
    if new: reject

That rule cannot tell these two candidates apart::

    width = 0                     # a temporary that lives and dies inside
    for ch in line:               # the existing function's body
        ...

    import statistics             # a new dependency edge, a new module
    mode = statistics.mode(...)   # surface, a new callable

Both introduce identifiers absent from the original source, so both were
rejected with the same reason.  Round 6 authored a candidate whose whole
novelty was ``lstrip`` / ``mode`` / ``stripped``, and the measured rejection
reason was "introduced identifiers not present in the source" — a true
statement that says nothing about whether the candidate expanded what the
program can reach.

**The distinction this module owns.**

    a lexical identifier being new
        is not evidence that the candidate expands program capability.

    LOCAL BINDING NOVELTY   — a name that is created, used and destroyed
                              inside the body of an *existing* function
    EXTERNAL / STRUCTURAL   — a new import, definition, parameter, global,
    REFERENCE NOVELTY         attribute, member or callable

The first is implementation detail.  The second changes what the program is
made of.  This module reasons from syntax and lexical scope to separate them,
and widens ``safe_minimal`` for the first only.

**What it does not do.**  It does not allow arbitrary novel identifiers; a
novel name is admitted only when the *same* candidate structurally binds it as
a local of the one existing function it edits.  It adds no allowlist of
spellings — there is no ``lstrip`` entry here, and a candidate that calls a
novel member is rejected whether the receiver is a local or not.  Imports,
definitions, signatures, globals, nonlocals and attribute stores keep the
previous conservative treatment, and a candidate that mixes allowed local
novelty with any of them stays rejected.

**Language coverage.**  Python only.  Lexical scope is a language-specific
fact, and inventing Python's rules for every other grammar would be exactly the
unsafe symmetry §4 forbids.  Every other language reports
``language_supported=False`` and keeps the pre-existing behaviour byte for
byte.

**It grants nothing.**  A candidate admitted here is *eligible for candidate
verification* and nothing else — not correct, not verified, not review
eligible, not approval ready and not execution authorised.  DEFECT.PROBE.LIVE.4
and CANDIDATE.VERIFY.LIVE.1 remain the semantic verdict, unchanged and
unbypassable.

The classifier is pure: it parses the two bounded snippets the gate already
holds and reads nothing else.  No repository access, no traversal, no model
call, no network call, no subprocess.

LIVE.3 additionally accepts occurrence-specific immutable result-field proofs
from the authoritative baseline context. Those reads are data access; novel
methods, properties and unproven members keep the conservative rule.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence, TYPE_CHECKING

from core.immutable_result_fields import (
    PROVEN_IMMUTABLE_RESULT_FIELD_READ,
    proven_field_read_nodes,
)

if TYPE_CHECKING:
    from core.authoritative_binding_context import AuthoritativeBindingContext


PHASE_ID = "PATCH.MINIMAL.LIVE.2"
SCHEMA_VERSION = "patch_minimal_live_2_v1"

# ── Novelty classes ─────────────────────────────────────────────────────────
#
# Every novel identifier lands in exactly one of these.  The vocabulary is
# closed: a name this module cannot place is ``unresolved``, which blocks.
NOVELTY_LOCAL_BINDING = "local_binding"
NOVELTY_STRUCTURAL = "structural"
NOVELTY_EXTERNAL_REFERENCE = "external_reference"
NOVELTY_IMPORT = "import"
NOVELTY_SCOPE_DECLARATION = "scope_declaration"
NOVELTY_ATTRIBUTE_STORE = "attribute_store"
NOVELTY_UNRESOLVED = "unresolved"
NOVELTY_CLASSES: tuple[str, ...] = (
    NOVELTY_LOCAL_BINDING,
    NOVELTY_STRUCTURAL,
    NOVELTY_EXTERNAL_REFERENCE,
    NOVELTY_IMPORT,
    NOVELTY_SCOPE_DECLARATION,
    NOVELTY_ATTRIBUTE_STORE,
    NOVELTY_UNRESOLVED,
)

# ── Reasons (§19) ───────────────────────────────────────────────────────────
#
# Semantically separate, and deliberately *not* collapsed back into one
# ``invented_identifier``.  The first is the only one that admits.
REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY = "bounded_local_identifier_novelty"
REASON_NOVEL_EXTERNAL_REFERENCE = "novel_external_reference"
REASON_NOVEL_IMPORT = "novel_import"
REASON_NOVEL_DEFINITION = "novel_definition"
REASON_SIGNATURE_CHANGE = "signature_change"
REASON_NOVEL_SCOPE_DECLARATION = "novel_scope_declaration"
REASON_NOVEL_ATTRIBUTE_STORE = "novel_attribute_store"
REASON_UNRESOLVED_NOVEL_IDENTIFIER = "unresolved_novel_identifier"
REASON_LOCAL_NOVELTY_BUDGET_EXCEEDED = "local_novelty_budget_exceeded"
REASON_MULTIPLE_FUNCTIONS_CHANGED = "multiple_functions_changed"
REASON_UNSUPPORTED_LANGUAGE = "unsupported_language"
REASON_UNSUPPORTED_CANDIDATE_SHAPE = "unsupported_candidate_shape"
REASON_UNPARSED_CANDIDATE = "unparsed_candidate"

#: Deterministic report order.  When a candidate carries several kinds of
#: novelty the first surviving entry is the one an operator is shown, and the
#: ordering is structural severity: what the program is made of, then what it
#: reaches, then how much of it moved.
BLOCKING_REASON_ORDER: tuple[str, ...] = (
    REASON_NOVEL_IMPORT,
    REASON_NOVEL_DEFINITION,
    REASON_SIGNATURE_CHANGE,
    REASON_NOVEL_SCOPE_DECLARATION,
    REASON_NOVEL_ATTRIBUTE_STORE,
    REASON_NOVEL_EXTERNAL_REFERENCE,
    REASON_UNRESOLVED_NOVEL_IDENTIFIER,
    REASON_MULTIPLE_FUNCTIONS_CHANGED,
    REASON_LOCAL_NOVELTY_BUDGET_EXCEEDED,
    REASON_UNSUPPORTED_CANDIDATE_SHAPE,
    REASON_UNPARSED_CANDIDATE,
    REASON_UNSUPPORTED_LANGUAGE,
)

# ── Caps (§12/§13) ──────────────────────────────────────────────────────────
#
# Structural eligibility, then three small deterministic counts.  There is no
# score and no coefficient: a candidate is inside the caps or it is not.
#
# The numbers are measured, not chosen.  Against the live T6 target the
# representative local-only candidates bind 1, 2, 2, 3 and 5 novel locals and
# change 12, 12, 12, 18 and 24 lines; the correct unit-inferring positive
# control is the 3-binding, 18-line one.  ``3`` is therefore the smallest
# binding cap that admits a correct fix, and ``24`` the smallest line cap that
# admits every measured local-only formulation of one.
MAX_NOVEL_LOCAL_BINDINGS = 3
MAX_CHANGED_LINES = 24
#: §25 — one existing function first.  The multi-file feature path is a
#: different contract and is not borrowed here.
MAX_TOUCHED_FUNCTIONS = 1

# ── Candidate shapes ────────────────────────────────────────────────────────
SHAPE_DEFINITION = "definition"
SHAPE_FUNCTION_BODY_FRAGMENT = "function_body_fragment"
SHAPE_UNSUPPORTED = "unsupported"

#: The one language whose lexical scope this module models.
SUPPORTED_LANGUAGE = "python"

#: Aliases the gate may hand us for that language.
_PYTHON_ALIASES = frozenset({"py", "python", "python3"})

_DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LocalBinding:
    """One novel name bound inside the body of one existing function."""

    name: str
    scope: str
    binding_kinds: tuple[str, ...]
    load_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope,
            "binding_kinds": list(self.binding_kinds),
            "load_count": self.load_count,
        }


@dataclass(frozen=True, slots=True)
class NoveltyFinding:
    """One novel identifier this module refuses to call a local binding."""

    name: str
    novelty_class: str
    reason: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.novelty_class not in NOVELTY_CLASSES:
            raise ValueError(f"unsupported novelty class: {self.novelty_class!r}")
        if self.reason not in BLOCKING_REASON_ORDER:
            raise ValueError(f"unsupported novelty reason: {self.reason!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "novelty_class": self.novelty_class,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class NoveltyCaps:
    """The three bounded counts, and whether the candidate is inside them."""

    novel_local_bindings: int = 0
    touched_functions: int = 0
    changed_lines: int = 0

    @property
    def binding_budget_exceeded(self) -> bool:
        return self.novel_local_bindings > MAX_NOVEL_LOCAL_BINDINGS

    @property
    def line_budget_exceeded(self) -> bool:
        return self.changed_lines > MAX_CHANGED_LINES

    @property
    def function_budget_exceeded(self) -> bool:
        return self.touched_functions > MAX_TOUCHED_FUNCTIONS

    @property
    def exceeded(self) -> bool:
        return (
            self.binding_budget_exceeded
            or self.line_budget_exceeded
            or self.function_budget_exceeded
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_novel_local_bindings": MAX_NOVEL_LOCAL_BINDINGS,
            "novel_local_bindings": self.novel_local_bindings,
            "max_touched_functions": MAX_TOUCHED_FUNCTIONS,
            "touched_functions": self.touched_functions,
            "max_changed_lines": MAX_CHANGED_LINES,
            "changed_lines": self.changed_lines,
            "binding_budget_exceeded": self.binding_budget_exceeded,
            "function_budget_exceeded": self.function_budget_exceeded,
            "line_budget_exceeded": self.line_budget_exceeded,
            "exceeded": self.exceeded,
        }


@dataclass(frozen=True, slots=True)
class CandidateNoveltyClassification:
    """What kinds of novelty one candidate carries, and whether the local kind
    alone explains all of it."""

    language: str = ""
    language_supported: bool = False
    candidate_shape: str = SHAPE_UNSUPPORTED
    containing_functions: tuple[str, ...] = ()
    local_bindings: tuple[LocalBinding, ...] = ()
    findings: tuple[NoveltyFinding, ...] = ()
    caps: NoveltyCaps = field(default_factory=NoveltyCaps)
    classification_seconds: float = 0.0
    schema_version: str = SCHEMA_VERSION
    proven_field_read_names: tuple[str, ...] = ()
    field_lookup_seconds: float = 0.0

    # ── the answer ──────────────────────────────────────────────────────────

    @property
    def local_binding_names(self) -> frozenset[str]:
        return frozenset(item.name for item in self.local_bindings)

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        found = {item.reason for item in self.findings}
        if self.caps.binding_budget_exceeded or self.caps.line_budget_exceeded:
            found.add(REASON_LOCAL_NOVELTY_BUDGET_EXCEEDED)
        if self.caps.function_budget_exceeded:
            found.add(REASON_MULTIPLE_FUNCTIONS_CHANGED)
        return tuple(
            reason for reason in BLOCKING_REASON_ORDER if reason in found
        )

    @property
    def bounded_local_novelty_allowed(self) -> bool:
        """Structural eligibility, read as a chain and not as a score.

        novel identifier → is it a local binding? → contained in one existing
        function? → within caps? → is there no structural, dependency, member
        or cross-scope novelty anywhere in the same candidate? → eligible.
        """

        return (
            self.language_supported
            and self.candidate_shape != SHAPE_UNSUPPORTED
            and bool(self.local_bindings)
            and not self.blocking_reasons
        )

    @property
    def primary_reason(self) -> str:
        if self.proven_field_read_names and not self.blocking_reasons:
            return PROVEN_IMMUTABLE_RESULT_FIELD_READ
        if self.bounded_local_novelty_allowed:
            return REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY
        blocking = self.blocking_reasons
        return blocking[0] if blocking else ""

    def admits(self, novel_identifiers: Iterable[str]) -> bool:
        """Whether bounded local novelty explains *every* novel identifier.

        The gate's lexical delta is the authority on what is new.  This says
        only that each of those names is one of the local bindings proven
        above — a candidate whose delta contains anything else is not admitted,
        which is how mixed novelty (§14) stays blocked without a second rule.
        """

        if not self.bounded_local_novelty_allowed and not (
            self.proven_field_read_names and self.language_supported
            and self.candidate_shape != SHAPE_UNSUPPORTED and not self.blocking_reasons
        ):
            return False
        return set(novel_identifiers) <= (set(self.local_binding_names) | set(self.proven_field_read_names))

    def unexplained_identifiers(
        self, novel_identifiers: Iterable[str]
    ) -> tuple[str, ...]:
        """The novel names bounded local novelty does *not* account for.

        When local novelty was not granted at all, nothing is explained: the
        answer is the whole delta, not the part that happens to look local.
        Reporting a subtraction there would suggest a partial grant, and there
        is no such thing.
        """

        names = sorted(set(str(name) for name in novel_identifiers))
        if self.admits(names):
            return ()
        if not self.bounded_local_novelty_allowed:
            return tuple(names)
        return tuple(name for name in names if name not in self.local_binding_names)

    def rejection_reason(self, novel_identifiers: Iterable[str]) -> str:
        """The typed reason a candidate is refused, or ``""`` when admitted.

        A lexical delta can name something no AST node carries — an ``f``
        prefix, a token this module has no rule for.  Such a name is
        deliberately not silently forgiven: it falls through to
        ``unresolved_novel_identifier`` rather than to the allow path.
        """

        if self.admits(novel_identifiers):
            return ""
        blocking = self.blocking_reasons
        if blocking:
            return blocking[0]
        return REASON_UNRESOLVED_NOVEL_IDENTIFIER

    # ── receipts (§18) ──────────────────────────────────────────────────────

    def _class_names(self, novelty_class: str) -> list[str]:
        return sorted(
            {
                item.name
                for item in self.findings
                if item.novelty_class == novelty_class
            }
        )

    def novelty_classification(self) -> dict[str, Any]:
        """The typed evidence, and no AST."""

        def group(novelty_class: str) -> dict[str, Any]:
            names = self._class_names(novelty_class)
            return {"names": names, "count": len(names)}

        result = {
            "local_binding_novelty": {
                "names": sorted(self.local_binding_names),
                "count": len(self.local_bindings),
                "scopes": [item.as_dict() for item in self.local_bindings],
            },
            "structural_novelty": group(NOVELTY_STRUCTURAL),
            "external_reference_novelty": group(NOVELTY_EXTERNAL_REFERENCE),
            "import_novelty": group(NOVELTY_IMPORT),
            "scope_declaration_novelty": group(NOVELTY_SCOPE_DECLARATION),
            "attribute_store_novelty": group(NOVELTY_ATTRIBUTE_STORE),
            "unresolved_novelty": group(NOVELTY_UNRESOLVED),
        }
        if self.proven_field_read_names:
            result[PROVEN_IMMUTABLE_RESULT_FIELD_READ] = {
                "names": list(self.proven_field_read_names),
                "count": len(self.proven_field_read_names),
            }
        return result

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "phase_id": PHASE_ID,
            "schema_version": self.schema_version,
            "language": self.language,
            "language_supported": self.language_supported,
            "candidate_shape": self.candidate_shape,
            "containing_functions": list(self.containing_functions),
            "novelty_classification": self.novelty_classification(),
            "findings": [item.as_dict() for item in self.findings],
            "caps": self.caps.as_dict(),
            "bounded_local_novelty_allowed": self.bounded_local_novelty_allowed,
            "reason": self.primary_reason,
            "blocking_reasons": list(self.blocking_reasons),
        }
        payload["novelty_fingerprint"] = _fingerprint(payload)
        return payload

    def as_telemetry(
        self,
        *,
        candidate_fingerprint: str = "",
        novel_identifiers: Iterable[str] = (),
    ) -> dict[str, Any]:
        """The additive bounded facts this phase writes onto a payload.

        Harness-authored control-plane state: it is never an answer field, and
        ANSWER.GROUND.LIVE.4 leaves it alone.
        """

        receipt = self.as_dict()
        delta = tuple(sorted(set(str(name) for name in novel_identifiers)))
        return {
            "candidate_novelty_novel_identifiers": list(delta),
            "candidate_novelty_unexplained_identifiers": list(
                self.unexplained_identifiers(delta)
            ),
            "candidate_novelty_admitted": self.admits(delta),
            "candidate_novelty_phase_id": PHASE_ID,
            "candidate_novelty_schema_version": self.schema_version,
            "candidate_novelty_language": self.language,
            "candidate_novelty_language_supported": self.language_supported,
            "candidate_novelty_candidate_shape": self.candidate_shape,
            "candidate_novelty_containing_functions": list(
                self.containing_functions
            ),
            "candidate_novelty_classification": receipt["novelty_classification"],
            "candidate_novelty_local_binding_names": sorted(
                self.local_binding_names
            ),
            "candidate_novelty_local_binding_count": len(self.local_bindings),
            "candidate_novelty_findings": receipt["findings"],
            "candidate_novelty_caps": receipt["caps"],
            "bounded_local_novelty_allowed": self.bounded_local_novelty_allowed,
            "candidate_novelty_reason": self.primary_reason,
            "candidate_novelty_blocking_reasons": list(self.blocking_reasons),
            "candidate_novelty_receipt": receipt,
            "candidate_novelty_fingerprint": receipt["novelty_fingerprint"],
            "candidate_novelty_candidate_fingerprint": str(
                candidate_fingerprint or ""
            ),
            "candidate_novelty_classification_seconds": self.classification_seconds,
            "candidate_novelty_model_calls": 0,
            "candidate_novelty_network_calls": 0,
            "candidate_novelty_repository_reads": 0,
            "candidate_novelty_repository_mutations": 0,
            "immutable_result_field_lookup_seconds": self.field_lookup_seconds,
        }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse(snippet: str) -> tuple[ast.Module | None, bool]:
    """``(tree, needed_dedent)`` for one bounded snippet, or ``(None, False)``.

    A snippet that only parses after dedenting is a suite fragment: its first
    statement is indented, so it was lifted out of some enclosing block.
    """

    try:
        return ast.parse(snippet), False
    except SyntaxError:
        pass
    try:
        return ast.parse(textwrap.dedent(snippet)), True
    except SyntaxError:
        return None, False


def _every_line_indented(snippet: str) -> bool:
    """No non-blank line starts at column zero.

    A contiguous region that is entirely indented and contains no ``def`` or
    ``class`` cannot contain module-level code and cannot span two functions,
    which is what makes the fragment shape safe to reason about at all.
    """

    return all(
        (not line.strip()) or line[:1] in (" ", "\t")
        for line in (snippet or "").splitlines()
    )


def _has_definition(tree: ast.AST) -> bool:
    return any(
        isinstance(node, _DEFINITION_NODES) or isinstance(node, ast.Lambda)
        for node in ast.walk(tree)
    )


def _top_level_definitions(tree: ast.Module) -> bool:
    return any(isinstance(node, _DEFINITION_NODES) for node in tree.body)


def _changed_lines(target: str, patched: str) -> int:
    diff = difflib.unified_diff(
        (target or "").splitlines(), (patched or "").splitlines(), lineterm="", n=0
    )
    return sum(
        1
        for line in diff
        if line[:1] in "+-" and line[:3] not in ("+++", "---")
    )


# ---------------------------------------------------------------------------
# Definition index and public shape
# ---------------------------------------------------------------------------


def _definition_index(tree: ast.AST) -> dict[str, ast.AST]:
    """Qualified name → definition node, for every def/class in a tree."""

    index: dict[str, ast.AST] = {}

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _DEFINITION_NODES):
                qualname = f"{prefix}.{child.name}" if prefix else child.name
                index[qualname] = child
                walk(child, qualname)
            else:
                walk(child, prefix)

    walk(tree, "")
    return index


def _public_shape(node: ast.AST) -> str:
    """A deterministic string identity for everything §6 forbids changing."""

    if isinstance(node, _DEF_NODES):
        return _canonical_json(
            {
                "kind": type(node).__name__,
                "name": node.name,
                "args": ast.dump(node.args),
                "returns": ast.dump(node.returns) if node.returns else "",
                "decorators": [ast.dump(item) for item in node.decorator_list],
            }
        )
    if isinstance(node, ast.ClassDef):
        return _canonical_json(
            {
                "kind": "ClassDef",
                "name": node.name,
                "bases": [ast.dump(item) for item in node.bases],
                "keywords": [ast.dump(item) for item in node.keywords],
                "decorators": [ast.dump(item) for item in node.decorator_list],
            }
        )
    return ast.dump(node)


def _body_shape(node: ast.AST) -> str:
    body = getattr(node, "body", [])
    return _canonical_json([ast.dump(item) for item in body])


def _statement_shapes(tree: ast.AST, node_type: type | tuple) -> list[str]:
    return sorted(
        ast.dump(node) for node in ast.walk(tree) if isinstance(node, node_type)
    )


# ---------------------------------------------------------------------------
# Scope model
# ---------------------------------------------------------------------------


class _Scope:
    """One lexical scope and the novel names bound in it."""

    __slots__ = ("key", "parent", "kind", "bindings", "loads", "function_key")

    def __init__(self, key: str, parent: "_Scope | None", kind: str, function_key: str):
        self.key = key
        self.parent = parent
        self.kind = kind
        self.function_key = function_key
        self.bindings: dict[str, set[str]] = {}
        self.loads: dict[str, int] = {}

    def bind(self, name: str, kind: str) -> None:
        self.bindings.setdefault(name, set()).add(kind)

    def resolve(self, name: str) -> "_Scope | None":
        scope: _Scope | None = self
        while scope is not None:
            if name in scope.bindings:
                return scope
            scope = scope.parent
        return None


_COMPREHENSION_NODES = (
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------


def classify_candidate_novelty(
    *,
    target_snippet: str,
    patched_snippet: str,
    language: str,
    allowed_identifiers: Iterable[str],
    target_node_kind: str = "",
    target_node_name: str = "",
    authoritative_binding_context: AuthoritativeBindingContext | None = None,
) -> CandidateNoveltyClassification:
    """Separate local binding novelty from external/structural novelty.

    ``allowed_identifiers`` is the gate's own "already present" set — the
    identifiers of the original snippet plus the language keyword and builtin
    allowlists.  This module never decides what is *new*; it decides what a new
    name structurally *is*.
    """

    started = time.perf_counter()
    lang = str(language or "").lower().strip()
    normalized = SUPPORTED_LANGUAGE if lang in _PYTHON_ALIASES else lang

    if normalized != SUPPORTED_LANGUAGE:
        return CandidateNoveltyClassification(
            language=normalized,
            language_supported=False,
            candidate_shape=SHAPE_UNSUPPORTED,
            findings=(
                NoveltyFinding(
                    name="",
                    novelty_class=NOVELTY_UNRESOLVED,
                    reason=REASON_UNSUPPORTED_LANGUAGE,
                    detail=(
                        "lexical scope is modelled for Python only; every other "
                        "language keeps the previous conservative rule"
                    ),
                ),
            ),
            classification_seconds=round(time.perf_counter() - started, 6),
        )

    allowed = frozenset(str(name) for name in allowed_identifiers)
    target_tree, target_dedented = _parse(target_snippet)
    patched_tree, patched_dedented = _parse(patched_snippet)

    if target_tree is None or patched_tree is None:
        return _blocked(
            normalized,
            SHAPE_UNSUPPORTED,
            REASON_UNPARSED_CANDIDATE,
            "one side of the candidate is not parsable Python",
            started,
            _changed_lines(target_snippet, patched_snippet),
        )

    shape = _candidate_shape(
        target_snippet,
        patched_snippet,
        target_tree,
        patched_tree,
        target_dedented,
        patched_dedented,
        target_node_kind,
    )
    if shape == SHAPE_UNSUPPORTED:
        return _blocked(
            normalized,
            SHAPE_UNSUPPORTED,
            REASON_UNSUPPORTED_CANDIDATE_SHAPE,
            (
                "the candidate is neither a whole definition nor a wholly "
                "indented definition-free body fragment of one existing function"
            ),
            started,
            _changed_lines(target_snippet, patched_snippet),
        )

    findings: list[NoveltyFinding] = []
    if shape == SHAPE_DEFINITION:
        touched, structural = _definition_form_functions(target_tree, patched_tree)
        findings.extend(structural)
        containing = tuple(touched)
    else:
        containing = (str(target_node_name or "").strip() or "<enclosing function>",)

    # §8 — a new import statement is a new dependency edge, full stop.
    if _statement_shapes(patched_tree, (ast.Import, ast.ImportFrom)) != (
        _statement_shapes(target_tree, (ast.Import, ast.ImportFrom))
    ):
        findings.append(
            NoveltyFinding(
                name=_first_import_name(target_tree, patched_tree),
                novelty_class=NOVELTY_IMPORT,
                reason=REASON_NOVEL_IMPORT,
                detail="the candidate adds or changes an import",
            )
        )

    # §15 — a scope declaration is the opposite of bounded local novelty.
    if _statement_shapes(patched_tree, (ast.Global, ast.Nonlocal)) != (
        _statement_shapes(target_tree, (ast.Global, ast.Nonlocal))
    ):
        findings.append(
            NoveltyFinding(
                name=_first_scope_declaration_name(target_tree, patched_tree),
                novelty_class=NOVELTY_SCOPE_DECLARATION,
                reason=REASON_NOVEL_SCOPE_DECLARATION,
                detail="the candidate declares global or nonlocal",
            )
        )

    # §7 — a lambda is an executable definition.
    if len(_statement_shapes(patched_tree, ast.Lambda)) > len(
        _statement_shapes(target_tree, ast.Lambda)
    ):
        findings.append(
            NoveltyFinding(
                name="<lambda>",
                novelty_class=NOVELTY_STRUCTURAL,
                reason=REASON_NOVEL_DEFINITION,
                detail="the candidate introduces a lambda",
            )
        )

    field_started = time.perf_counter()
    field_reads = (
        proven_field_read_nodes(patched_tree, authoritative_binding_context)
        if authoritative_binding_context is not None else frozenset()
    )
    field_seconds = time.perf_counter() - field_started
    scopes, name_findings = _walk_scopes(
        patched_tree, allowed, shape, containing, field_reads
    )
    findings.extend(name_findings)

    bindings = _collect_local_bindings(scopes, shape, containing)
    caps = NoveltyCaps(
        novel_local_bindings=len(bindings),
        touched_functions=len(containing) if shape == SHAPE_DEFINITION else 1,
        changed_lines=_changed_lines(target_snippet, patched_snippet),
    )
    return CandidateNoveltyClassification(
        language=normalized,
        language_supported=True,
        candidate_shape=shape,
        containing_functions=containing,
        local_bindings=bindings,
        findings=tuple(_deduplicate(findings)),
        caps=caps,
        classification_seconds=round(time.perf_counter() - started, 6),
        proven_field_read_names=tuple(sorted({n.attr for n in field_reads})),
        field_lookup_seconds=field_seconds,
    )


def _blocked(
    language: str,
    shape: str,
    reason: str,
    detail: str,
    started: float,
    changed_lines: int,
) -> CandidateNoveltyClassification:
    return CandidateNoveltyClassification(
        language=language,
        language_supported=True,
        candidate_shape=shape,
        findings=(
            NoveltyFinding(
                name="",
                novelty_class=NOVELTY_UNRESOLVED,
                reason=reason,
                detail=detail,
            ),
        ),
        caps=NoveltyCaps(changed_lines=changed_lines),
        classification_seconds=round(time.perf_counter() - started, 6),
    )


def _candidate_shape(
    target_snippet: str,
    patched_snippet: str,
    target_tree: ast.Module,
    patched_tree: ast.Module,
    target_dedented: bool,
    patched_dedented: bool,
    target_node_kind: str,
) -> str:
    """Which of the two shapes this module can reason about, if either."""

    if not target_dedented and not patched_dedented:
        if _top_level_definitions(target_tree) and _top_level_definitions(
            patched_tree
        ):
            return SHAPE_DEFINITION
        # Column-zero statements with no definition are module-level code: a
        # novel name bound there is a module-level binding, not a local.
        return SHAPE_UNSUPPORTED

    if not (target_dedented and patched_dedented):
        # One side is a definition and the other a fragment.  The replacement
        # is not shape-preserving, so decline rather than guess.
        return SHAPE_UNSUPPORTED

    if str(target_node_kind or "").strip().lower() != "function":
        return SHAPE_UNSUPPORTED
    if not (
        _every_line_indented(target_snippet)
        and _every_line_indented(patched_snippet)
    ):
        return SHAPE_UNSUPPORTED
    if _has_definition(target_tree):
        return SHAPE_UNSUPPORTED
    return SHAPE_FUNCTION_BODY_FRAGMENT


def _definition_form_functions(
    target_tree: ast.Module, patched_tree: ast.Module
) -> tuple[list[str], list[NoveltyFinding]]:
    """Touched function qualnames, plus every §6/§7 structural violation."""

    before = _definition_index(target_tree)
    after = _definition_index(patched_tree)
    findings: list[NoveltyFinding] = []

    for name in sorted(set(after) - set(before)):
        findings.append(
            NoveltyFinding(
                name=name,
                novelty_class=NOVELTY_STRUCTURAL,
                reason=REASON_NOVEL_DEFINITION,
                detail="the candidate defines a function or class the source did not",
            )
        )
    for name in sorted(set(before) - set(after)):
        findings.append(
            NoveltyFinding(
                name=name,
                novelty_class=NOVELTY_STRUCTURAL,
                reason=REASON_UNSUPPORTED_CANDIDATE_SHAPE,
                detail="the candidate removes an existing definition",
            )
        )

    touched: list[str] = []
    for name in sorted(set(before) & set(after)):
        if _public_shape(before[name]) != _public_shape(after[name]):
            findings.append(
                NoveltyFinding(
                    name=name,
                    novelty_class=NOVELTY_STRUCTURAL,
                    reason=REASON_SIGNATURE_CHANGE,
                    detail="name, parameters, defaults, annotation, decorators or async-ness changed",
                )
            )
        if isinstance(after[name], _DEF_NODES) and _body_shape(
            before[name]
        ) != _body_shape(after[name]):
            touched.append(name)
    return touched, findings


def _first_import_name(target_tree: ast.AST, patched_tree: ast.AST) -> str:
    before = set(_statement_shapes(target_tree, (ast.Import, ast.ImportFrom)))
    for node in ast.walk(patched_tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and ast.dump(node) not in before:
            if isinstance(node, ast.ImportFrom) and node.module:
                return str(node.module)
            return str(node.names[0].asname or node.names[0].name)
    return ""


def _first_scope_declaration_name(target_tree: ast.AST, patched_tree: ast.AST) -> str:
    before = set(_statement_shapes(target_tree, (ast.Global, ast.Nonlocal)))
    for node in ast.walk(patched_tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)) and ast.dump(node) not in before:
            return str(node.names[0]) if node.names else ""
    return ""


# ---------------------------------------------------------------------------
# The scope walk
# ---------------------------------------------------------------------------


def _walk_scopes(
    patched_tree: ast.Module,
    allowed: frozenset[str],
    shape: str,
    containing: Sequence[str],
    field_reads: frozenset[ast.Attribute] = frozenset(),
) -> tuple[list[_Scope], list[NoveltyFinding]]:
    """Bind, then resolve, every novel name in the patched tree.

    One descent creates the scopes, records which scope every node sits in and
    binds every store target.  A second pass over those recorded pairs resolves
    loads, so a name used before the line that binds it is judged the same way
    as one used after: this is lexical scope, not execution order.

    Returns every scope encountered plus the findings for names that are not
    local bindings of the one existing function being edited.
    """

    if shape == SHAPE_FUNCTION_BODY_FRAGMENT:
        # A dedented body fragment parses as a module, but it is not one: its
        # statements are the suite of an existing function, so its root scope
        # is that function.  Getting this wrong would file every local as a
        # module-level binding.
        function_key = str(containing[0]) if containing else "<enclosing function>"
        root = _Scope(function_key, None, "function", function_key)
    else:
        root = _Scope("<module>", None, "module", "")

    scopes: list[_Scope] = [root]
    findings: list[NoveltyFinding] = []
    placement: list[tuple[ast.AST, _Scope]] = []
    comprehensions = 0

    def novel(name: str) -> bool:
        return bool(name) and name not in allowed

    def bind_target(node: ast.AST, scope: _Scope, kind: str) -> None:
        """Bind the novel ``Name`` stores of one assignment target.

        ``ast.walk`` reaches the elements of a tuple or starred target.  It
        also reaches a subscript's own value and slice, which carry ``Load``
        context and are skipped: ``mapping[key] = value`` mutates an existing
        object and binds nothing (§17).  An attribute store is recorded as
        exactly that and never as a local (§16).
        """

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                if novel(child.id):
                    scope.bind(child.id, kind)
            elif isinstance(child, ast.Attribute) and isinstance(
                child.ctx, (ast.Store, ast.Del)
            ):
                if novel(child.attr):
                    findings.append(
                        NoveltyFinding(
                            name=child.attr,
                            novelty_class=NOVELTY_ATTRIBUTE_STORE,
                            reason=REASON_NOVEL_ATTRIBUTE_STORE,
                            detail="an attribute store is not a local binding",
                        )
                    )

    def descend(node: ast.AST, scope: _Scope) -> None:
        nonlocal comprehensions
        placement.append((node, scope))

        for child in ast.iter_child_nodes(node):
            if isinstance(child, _DEFINITION_NODES):
                qualname = (
                    f"{scope.key}.{child.name}"
                    if scope.kind == "function"
                    else child.name
                )
                is_function = isinstance(child, _DEF_NODES)
                inner = _Scope(
                    qualname,
                    scope,
                    "function" if is_function else "class",
                    qualname if is_function else "",
                )
                scopes.append(inner)
                for name in _arg_names(child):
                    if novel(name):
                        inner.bind(name, "parameter")
                descend(child, inner)
                continue

            if isinstance(child, ast.Lambda):
                inner = _Scope(f"{scope.key}.<lambda>", scope, "function", "")
                scopes.append(inner)
                for name in _arg_names(child):
                    if novel(name):
                        inner.bind(name, "parameter")
                descend(child, inner)
                continue

            if isinstance(child, _COMPREHENSION_NODES):
                comprehensions += 1
                inner = _Scope(
                    f"{scope.key}.<comprehension:{comprehensions}>",
                    scope,
                    "comprehension",
                    scope.function_key,
                )
                scopes.append(inner)
                for generator in child.generators:
                    bind_target(generator.target, inner, "comprehension_target")
                descend(child, inner)
                continue

            if isinstance(child, (ast.For, ast.AsyncFor)):
                bind_target(child.target, scope, "loop_target")
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    bind_target(target, scope, "assignment")
            elif isinstance(child, (ast.AugAssign, ast.AnnAssign)):
                bind_target(child.target, scope, "assignment")
            elif isinstance(child, ast.NamedExpr):
                bind_target(child.target, scope, "walrus")
            elif isinstance(child, ast.withitem) and child.optional_vars is not None:
                bind_target(child.optional_vars, scope, "with_target")
            elif isinstance(child, ast.ExceptHandler) and child.name:
                if novel(child.name):
                    scope.bind(child.name, "except_target")
            elif isinstance(child, (ast.Global, ast.Nonlocal)):
                # §15 — a declared name is written through a scope this
                # candidate does not own.  It is recorded so the receipt never
                # lists it as a local binding; the declaration itself already
                # blocks the widening.
                for name in child.names:
                    if novel(name):
                        scope.bind(name, "scope_declared")

            descend(child, scope)

    descend(patched_tree, root)
    findings.extend(_resolve_names(placement, allowed, shape, containing, field_reads))
    return scopes, findings


def _arg_names(node: ast.AST) -> list[str]:
    args = getattr(node, "args", None)
    if args is None:
        return []
    names: list[str] = []
    for group in (args.posonlyargs, args.args, args.kwonlyargs):
        names.extend(item.arg for item in group)
    for extra in (args.vararg, args.kwarg):
        if extra is not None:
            names.append(extra.arg)
    return names


def _resolve_names(
    placement: Sequence[tuple[ast.AST, "_Scope"]],
    allowed: frozenset[str],
    shape: str,
    containing: Sequence[str],
    field_reads: frozenset[ast.Attribute] = frozenset(),
) -> list[NoveltyFinding]:
    """Classify every novel ``Name`` and ``Attribute`` occurrence.

    A novel name is part of bounded local implementation novelty only when it
    resolves, through the lexical scope chain, to a binding this candidate made
    inside the one existing function it edits (§5).  Everything else is named
    for what it actually is.
    """

    findings: list[NoveltyFinding] = []
    permitted = set(containing)

    for node, scope in placement:
        if isinstance(node, ast.Attribute):
            if node in field_reads:
                continue
            if node.attr in allowed or isinstance(node.ctx, (ast.Store, ast.Del)):
                # A store was already recorded; a load of an existing member
                # name was never novel.
                continue
            findings.append(
                NoveltyFinding(
                    name=node.attr,
                    novelty_class=NOVELTY_EXTERNAL_REFERENCE,
                    reason=REASON_NOVEL_EXTERNAL_REFERENCE,
                    detail=(
                        "a novel member or callable without immutable "
                        "result-field proof is an external surface"
                    ),
                )
            )
            continue

        if isinstance(node, ast.keyword) and node.arg and node.arg not in allowed:
            # A novel keyword-argument name is part of some callee's parameter
            # list, so it is an external surface even though the AST carries it
            # as a bare string rather than as a ``Name``.
            findings.append(
                NoveltyFinding(
                    name=node.arg,
                    novelty_class=NOVELTY_EXTERNAL_REFERENCE,
                    reason=REASON_NOVEL_EXTERNAL_REFERENCE,
                    detail="a novel keyword argument names another callable's parameter",
                )
            )
            continue

        if not isinstance(node, ast.Name) or node.id in allowed:
            continue

        binding_scope = scope.resolve(node.id)
        if binding_scope is None:
            findings.append(
                NoveltyFinding(
                    name=node.id,
                    novelty_class=NOVELTY_UNRESOLVED,
                    reason=REASON_UNRESOLVED_NOVEL_IDENTIFIER,
                    detail="a novel name that the candidate never binds",
                )
            )
            continue
        if binding_scope.kind in ("module", "class"):
            findings.append(
                NoveltyFinding(
                    name=node.id,
                    novelty_class=NOVELTY_STRUCTURAL,
                    reason=REASON_NOVEL_DEFINITION,
                    detail=(
                        "a novel module-level or class-level binding is API or "
                        "config, not a local"
                    ),
                )
            )
            continue
        kinds = binding_scope.bindings.get(node.id, frozenset())
        if "scope_declared" in kinds:
            findings.append(
                NoveltyFinding(
                    name=node.id,
                    novelty_class=NOVELTY_SCOPE_DECLARATION,
                    reason=REASON_NOVEL_SCOPE_DECLARATION,
                    detail="the name is declared global or nonlocal, not local",
                )
            )
            continue
        if "parameter" in kinds:
            findings.append(
                NoveltyFinding(
                    name=node.id,
                    novelty_class=NOVELTY_STRUCTURAL,
                    reason=REASON_SIGNATURE_CHANGE,
                    detail="a novel parameter is public shape, not a local",
                )
            )
            continue
        if shape == SHAPE_DEFINITION and binding_scope.function_key not in permitted:
            findings.append(
                NoveltyFinding(
                    name=node.id,
                    novelty_class=NOVELTY_STRUCTURAL,
                    reason=REASON_MULTIPLE_FUNCTIONS_CHANGED,
                    detail=(
                        "the binding is local to a function this candidate was "
                        "not measured to touch"
                    ),
                )
            )
            continue
        if isinstance(node.ctx, ast.Load):
            binding_scope.loads[node.id] = binding_scope.loads.get(node.id, 0) + 1
    return findings


def _collect_local_bindings(
    scopes: list[_Scope], shape: str, containing: Sequence[str]
) -> tuple[LocalBinding, ...]:
    """Every novel name bound inside the one existing function being edited."""

    permitted = set(containing)
    bindings: dict[str, LocalBinding] = {}
    for scope in scopes:
        if scope.kind not in ("function", "comprehension"):
            continue
        if shape == SHAPE_DEFINITION and scope.function_key not in permitted:
            continue
        for name, kinds in scope.bindings.items():
            if "parameter" in kinds or "scope_declared" in kinds:
                continue
            existing = bindings.get(name)
            merged_kinds = tuple(sorted(kinds))
            loads = scope.loads.get(name, 0)
            if existing is None:
                bindings[name] = LocalBinding(
                    name=name,
                    scope=scope.key,
                    binding_kinds=merged_kinds,
                    load_count=loads,
                )
            else:
                # §38 — a name bound in two nested scopes of the same function
                # is one novel local, reported deterministically at the
                # outermost scope that binds it.
                bindings[name] = LocalBinding(
                    name=name,
                    scope=existing.scope,
                    binding_kinds=tuple(
                        sorted(set(existing.binding_kinds) | set(merged_kinds))
                    ),
                    load_count=existing.load_count + loads,
                )
    return tuple(bindings[name] for name in sorted(bindings))


def _deduplicate(findings: Iterable[NoveltyFinding]) -> list[NoveltyFinding]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[NoveltyFinding] = []
    for item in findings:
        key = (item.name, item.novelty_class, item.reason)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return sorted(unique, key=lambda item: (item.reason, item.name))


def describe_candidate_novelty(
    classification: CandidateNoveltyClassification,
) -> str:
    """One line an operator can act on, that claims nothing extra."""

    if classification.proven_field_read_names and not classification.blocking_reasons:
        return (
            "Proven immutable result-field read: "
            + ", ".join(classification.proven_field_read_names)
            + ". The candidate is eligible for verification; no execution is authorized."
        )
    if classification.bounded_local_novelty_allowed:
        names = ", ".join(sorted(classification.local_binding_names))
        return (
            f"Bounded local implementation novelty: {names} "
            f"{'is' if len(classification.local_bindings) == 1 else 'are'} bound "
            "inside the existing function being edited and never escape it. The "
            "candidate is now eligible for verification; it has not been judged "
            "correct."
        )
    reason = classification.primary_reason or REASON_UNSUPPORTED_CANDIDATE_SHAPE
    return (
        f"Not bounded local implementation novelty: {reason}. The previous "
        "conservative safe_minimal treatment applies."
    )


__all__ = [
    "BLOCKING_REASON_ORDER",
    "MAX_CHANGED_LINES",
    "MAX_NOVEL_LOCAL_BINDINGS",
    "MAX_TOUCHED_FUNCTIONS",
    "NOVELTY_ATTRIBUTE_STORE",
    "NOVELTY_CLASSES",
    "NOVELTY_EXTERNAL_REFERENCE",
    "NOVELTY_IMPORT",
    "NOVELTY_LOCAL_BINDING",
    "NOVELTY_SCOPE_DECLARATION",
    "NOVELTY_STRUCTURAL",
    "NOVELTY_UNRESOLVED",
    "PHASE_ID",
    "REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY",
    "REASON_LOCAL_NOVELTY_BUDGET_EXCEEDED",
    "REASON_MULTIPLE_FUNCTIONS_CHANGED",
    "REASON_NOVEL_ATTRIBUTE_STORE",
    "REASON_NOVEL_DEFINITION",
    "REASON_NOVEL_EXTERNAL_REFERENCE",
    "REASON_NOVEL_IMPORT",
    "REASON_NOVEL_SCOPE_DECLARATION",
    "REASON_SIGNATURE_CHANGE",
    "REASON_UNPARSED_CANDIDATE",
    "REASON_UNRESOLVED_NOVEL_IDENTIFIER",
    "REASON_UNSUPPORTED_CANDIDATE_SHAPE",
    "REASON_UNSUPPORTED_LANGUAGE",
    "SCHEMA_VERSION",
    "SHAPE_DEFINITION",
    "SHAPE_FUNCTION_BODY_FRAGMENT",
    "SHAPE_UNSUPPORTED",
    "SUPPORTED_LANGUAGE",
    "CandidateNoveltyClassification",
    "LocalBinding",
    "NoveltyCaps",
    "NoveltyFinding",
    "classify_candidate_novelty",
    "describe_candidate_novelty",
]
