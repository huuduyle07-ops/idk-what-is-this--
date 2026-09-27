# INPUT.1 — Lossless Task Contract & Semantic Waiter Boundary

Date: 2026-08-21
Status: complete
Next: INPUT.2 — Semantic Waiter Model Adapter & Semantic Evaluation

## Decision

A raw prompt must not route directly into execution mode selection.

A dogfood run asked C.A.T.T.U.S to analyze DeepSeek Harness against C.A.T.T.U.S
using a supplied five-value rubric. The request was routed incorrectly, the
comparative nature was lost, C.A.T.T.U.S itself disappeared as one of the two
comparison subjects, the rubric was not preserved as an evaluation framework,
and execution then confidently answered a different task. Every one of those
failures happened before any repository reasoning began.

INPUT.1 inserts a canonical intermediate representation between the prompt and
anything that acts:

```text
User Prompt
    ↓
Deterministic Explicit Extractor
    ↓
Semantic Waiter boundary
    ↓
Lossless Task Contract
    ↓
Deterministic Preservation Gate
    ↓
[future Execution Waiter / mode router]
    ↓
[future Kitchen / execution]
```

INPUT.1 stops before the Execution Waiter. It changes no routing behavior.

The long-term reading is a compiler one:

```text
raw user request = source language
Task Contract    = canonical intermediate representation
Goal Brief       = human-editable projection of that representation
```

Goal Brief stays assistive and optional. INPUT.1 never forces a user to fill
one in.

## Modules

| Module | Responsibility |
| --- | --- |
| `core/explicit_evidence.py` | Literal, pre-semantic extraction of what the user typed |
| `core/task_contract.py` | The canonical contract schema, provenance rules, serialization |
| `core/semantic_waiter.py` | The interpretation boundary: interface + deterministic implementations |
| `core/requirement_preservation.py` | The deterministic gate comparing evidence against interpretation |
| `core/input_understanding.py` | The four-stage pipeline that assembles a contract |

The five modules import nothing outside themselves and `__future__`,
`dataclasses`, `hashlib`, `json`, `re`, and `typing`. Tests enforce that.

## Lossless raw request

```python
task_contract.raw_request.text == original_input
```

`raw_request` is the one field with no bound. Every derived collection is
bounded; the user's own words are not. The record also carries `char_count` and
a `sha256` digest so a later phase can prove the text was not swapped.

## Explicit evidence

The extractor exists to preserve literal commitments so a semantic model cannot
silently delete them. It is not an attempt at natural-language understanding —
every value it reports is a span the user actually typed.

It currently captures:

- named entities (dotted acronyms such as `C.A.T.T.U.S`, CamelCase tokens, and
  multi-word TitleCase runs with leading command verbs stripped);
- URLs, and file paths with recognised extensions (URL spans are blanked first,
  so a URL never masquerades as a path);
- double-quoted, curly-quoted, and backticked terms;
- bullet and numbered list items, in supplied order;
- an evaluation framework / rubric, bound from a literal cue
  (`using the following framework`, `using this rubric`, `criteria:` …) to the
  list that follows it;
- comparisons (`compare A with B`, `analyze A against B`, `A vs B`);
- requested output formats (`as a table`, `in JSON`, `as markdown` …);
- constraints keyed off literal markers: `must`, `must not`, `do not`, `never`,
  `only`, `according to`, and framework references.

## Provenance

Exactly two states, and the distinction is load-bearing:

| State | Meaning |
| --- | --- |
| `explicit` | The user literally supplied this value |
| `inferred` | An interpreter derived this meaning |

An explicit value may not carry a confidence — the record type rejects it. A
probability on a quotation is a category error, and permitting one is how an
inferred value starts looking like something the user said. Deterministic
derivations (task type, execution requirements) are `inferred` with
`confidence=None`; only a genuinely probabilistic interpreter should populate a
number.

## Semantic Waiter boundary

```python
SemanticInterpreter.interpret(
    raw_prompt,
    explicit_evidence,
) -> SemanticInterpretation
```

The waiter takes the order. It never cooks it. `SEMANTIC_WAITER_FORBIDDEN_ACTIONS`
enumerates the boundary: no solving the task, no repository inspection or
indexing, no execution-mode selection, no provider or model selection, no
patching, no validation, no benchmarks, no worker launch, no Dream, no Project
Evolution, no write authority.

INPUT.1 ships two implementations and no model adapter:

- `ExplicitEvidenceInterpreter` — the default. It promotes literal evidence into
  an interpretation and infers only the task classification and the execution
  requirements, by fixed rules. Because it cannot drop what it was given, it
  cannot fail the preservation gate.
- `StaticSemanticInterpreter` — a test double returning a supplied
  interpretation verbatim, used to simulate a lossy model against the gate
  without wiring one.

## Requirement Preservation Gate

The gate compares explicit commitments against the interpretation and fails
closed. It never consults model confidence.

It fails when:

- an explicitly named comparison subject is absent;
- an explicit comparison relationship is not represented;
- the supplied framework, any of its values, or its supplied order is lost;
- an explicit constraint is dropped, rewritten, or has its kind flipped;
- an explicitly requested output format is dropped or changed;
- any value is labelled `explicit` without literal backing in the evidence.

Identity comparison ignores case, whitespace, and separator punctuation, so
`C.A.T.T.U.S` and `CATTUS` are the same subject while a genuinely different
value is not.

```text
explicit requirement lost
    ↓
preservation_status = failed
routing_allowed = false
```

`TaskContract.__post_init__` refuses to construct a contract with
`routing_allowed=True` over a failed gate, so the invariant cannot be bypassed
by a caller that forgets to check.

The canonical case: an interpreter reporting `confidence=0.97` while dropping
one of two explicitly named subjects still fails.

## Goal Brief relationship

Unchanged and untouched. `core/goal_brief.py` and `core/goal_brief_4w1h.py` were
not modified. A short conversational request produces a small valid contract
with `goal_brief_required=false` and no forced fields. Exposing or editing the
contract through the Goal Brief surface is INPUT.3, not this phase.

## What INPUT.1 does not do

No execution, mode dispatch, mode-router change, Instant Run change, Commander
execution, repository scan or index, CTX.SELECT change, patch generation or
application, patch-safety change, validation, benchmark scoring, lesson
behavior change, worker launch, Dream, Project Evolution, model or provider
selection, external API call, network call, database write, or repo mutation.
Human approval authority is unchanged and unweakened.

## Next

INPUT.2 should add a Semantic Waiter model adapter behind the existing
interface, plus semantic evaluation of interpretation quality. The preservation
gate stays deterministic and stays in front of routing: a model adapter is a new
implementation of an interface that is already gated, not a new trust boundary.
