# ANSWER.GROUND.LIVE.2 — Bare Symbol & Qualified Member Claim Grounding

**Status:** implemented
**Prerequisite:** ANSWER.GROUND.LIVE.1
**Track:** CHECK

## The gap this closes

Round-5 proved ANSWER.GROUND.LIVE.1 catches fabricated *path-shaped* entities:
`src/generator/formatter.py` was classified `unverified_model_assertion` and the
user-visible answer stopped presenting it as a repository location.

The same run let fabricated **symbol-only** assertions through:

```
structured output   "symbol": "CodeGenerator.format_patch"
prose               "The bug is in the PatchGenerator.generate method."
```

Neither string contains a path, so `_ENTITY_RE` never saw them.  Neither symbol
exists.  The answer presented both as established repository specificity.

This phase extends the *same* boundary so a concrete assistant-asserted
repository symbol needs membership evidence too.

## What is deliberately not built

Not semantic fact checking, not a verifier model, not CHECK.2, not a second
retrieval system, not symbol localization, not query expansion, not
hallucination scoring, not confidence thresholding, not an NLP entity
recognizer.  Zero model calls, zero network calls, zero repository traversal,
zero graph or index rebuild.  Retrieval, ranking, identifier recall, validation,
patch basis and execution authority are untouched, and `_classify_indent` is not
fixed.

## Shape of the change

`core/answer_entity_grounding.py` remains the single grounding boundary: one
extraction pass, one status vocabulary, one downgrade path, one receipt.  The
symbol *universe* and the symbol *claim grammar* — both pure, stateless and
free of I/O — live in a small helper, `core/repository_symbol_membership.py`,
because they are a membership view rather than a second checker.  Nothing
constructs a parallel grounding pipeline.

```
answer text / structured payload
        |
        v
  path references            (LIVE.1, unchanged grammar)
  symbol claims              (LIVE.2, new bounded grammar; path spans masked)
        |
        v
  RepositoryEntityEvidence   inventory + graph symbols + member relations
                             + CONTROL evidence + analysis-acquired declarations
                             + execution-observed frames
        |
        v
  one status per entity  ->  one downgrade  ->  one receipt
```

## Symbol evidence sources (no new acquisition)

| Source | Contributes |
| --- | --- |
| RETRIEVE.LIVE.1 eligible graph symbols | `path::name` identities, node spans |
| already-loaded node metadata spans | `path::Owner.member` relations by span containment |
| CONTROL entry nodes / hypotheses / patch intent | `path::name` identities |
| AnalysisEvidence excerpts (already in memory) | declared `path::name` and `path::Owner.member` |
| validation / preflight output tracebacks | `path::frame` execution-observed symbols |
| `create_file` / `patched_snippet` text already in the payload | proposed-new symbol names |

Class membership comes from a linear sweep over spans the graph already
recorded — no reparse, no file read, no graph rebuild.

## Claim grammar (conservative by construction)

Fenced code blocks are excluded, as in LIVE.1.  Spans already claimed by the
path grammar are masked so `file.py::Class.method` stays one entity.

Recognized:

* structured symbol fields (`symbol`, `target_symbol`, `target_node_name`,
  `function`, `method`, `class`, `candidate_symbol`, `diagnosis_location`, …)
  with sibling path context (`relative_path`, `file`, `target_file`, …)
* inline code spans whose whole content is symbol-shaped
* qualified prose forms `Owner.member`, `Owner::member`, `module.symbol`
* call form `name()`
* cue forms: `function|method|class|symbol X`, `X function|method|class`,
  `the bug is in X`

A qualified form is a repository claim only when its leftmost segment is
already known to repository evidence, or is CamelCase-shaped and not a
well-known external namespace root.  `pytest.main`, `pathlib.Path` and
`requests.Session` are therefore never rejected as missing repository symbols.

An unknown bare token is a repository claim only when its own form marks it as
a symbol (underscore, CamelCase, call parentheses, or code formatting) and it
is not a language builtin.  "The bug is in production." stays prose.

## Resolution

| Claim | Requirement |
| --- | --- |
| `path::name` | `path::name` in source evidence |
| `path::Owner.member` | that exact relation exists; a real file never grounds an invented member |
| `Owner.member` | the exact owner/member relation exists; a real class never grounds a fake method, and a real method never grounds the wrong owner |
| `module.symbol` | module resolves to a source-backed path holding that symbol |
| bare `name` | exactly one source-backed symbol carries that tail, else `ambiguous_symbol` |

A typed symbol field is *scoped* by its sibling path: `{"file": "calc.py",
"symbol": "main"}` is a claim about `calc.py`, and it fails even though `main`
exists one file over.  Prose inside the same object is only *contextualized* by
that path — it breaks an ambiguity tie and never turns a symbol that genuinely
lives elsewhere into a fabrication.  A file named in the claim's own sentence
does the same job for free text.  Nothing else may narrow an ambiguity:
grounding is not retrieval and never picks a winner.

A claim introduced by a modal — "a system could expose `Formatter.render()`" —
is hypothetical; the modal has to sit to the *left* of the entity, so "the
repository uses `Formatter.render()` here" still needs evidence.

## Status vocabulary

`grounded_existing`, `grounded_execution_observed`, `user_supplied_unverified`,
`proposed_new`, `hypothetical`, `unverified_model_assertion` are unchanged.
`ambiguous_symbol` is the single addition; stale evidence keeps failing to
`unverified_model_assertion` exactly as in LIVE.1.

## Downgrade

Unsupported specificity is removed from its sentence or field and replaced by
an explicit evidence-gap statement naming the entity under unverified framing.
No substitute symbol is ever invented, no retrieval state is mutated, no
authority is granted or withdrawn.
