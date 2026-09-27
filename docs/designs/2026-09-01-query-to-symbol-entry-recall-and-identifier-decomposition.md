# RETRIEVE.LIVE.2 — Query-to-Symbol Entry Recall & Identifier Decomposition

## Scope

This is a live retrieval-quality fix for entry candidate recall. It does not
change final CONTROL ranking, graph construction, persisted indexing, patch
grounding, validation, execution authorization, or write authority.

The invariant is narrow:

```text
"indent" -> core/code_dna.py::_classify_indent
```

because `indent` is a whole decomposed identifier token, never because it is a
character substring. The implementation of `_classify_indent` remains broken.

## Mechanical trace before the change

The production CONTROL path was:

```text
raw query
  -> reasoning.deep_project_understand.extract_symbol_candidates
  -> reasoning.deep_project_understand.expand_candidates
  -> graph.query.explain_symbol / impact_analysis / trace_path
  -> reasoning.deep_project_understand.deep_project_understand.findings
  -> core.control_engine.select_entry_nodes
  -> core.control_engine.resolve_symbol_to_graph_nodes
  -> exact canonical ID or exact tail equality only
  -> PROJECT_MAP critical-symbol/hotspot direct hits
  -> core.control_engine.fallback_entry_nodes_from_graph when still empty
  -> core.control_engine.control_dfs_v2
  -> core.control_engine.infer_hypotheses
  -> core.control_engine.build_control_result
```

`run_control_structured` is the production consumer of `select_entry_nodes` and
passes its bounded result to `control_dfs_v2`. `run_control` formats that result.
The web and pipeline surfaces consume those CONTROL results through their
existing paths. `web.app` also calls `deep_project_understand` directly for its
inspection endpoints.

`core.retriever._extract_symbol_candidates` is a separate file-context
retrieval helper consumed only by `retrieve_file_context`; it is not in CONTROL
entry selection and was not changed.

The exact reproduced seam, using an eligible in-memory target, was:

```text
extract_symbol_candidates("indent classification")
  -> ["indent", "classification"]

resolve_symbol_to_graph_nodes(graph, "indent")
  -> []

resolve_symbol_to_graph_nodes(graph, "classification")
  -> []

resolve_symbol_to_graph_nodes(graph, "_classify_indent")
  -> ["core/code_dna.py::_classify_indent"]
```

The target therefore did not exist in the query-derived entry set. Ranking
could not recover a candidate it never received.

## New entry-recall path

The production path now adds one bounded stage before project-map fallback:

```text
raw query
  -> extract_symbol_candidates (bounded, Unicode-aware, exact references kept)
  -> resolve_query_to_graph_nodes
       -> eligible_localization_nodes
       -> decompose_identifier on eligible canonical symbol tails
       -> exact/token/bounded-morphology entry facts
       -> deterministic lexical ordering
       -> entry cap
  -> query-derived entry nodes first
  -> existing deep/project-map sources as bounded supplements or fallback
  -> unchanged CONTROL DFS and ranking
```

The result records query candidates, query-derived nodes, bounded match facts,
project-map supplements/fallback and graph fallback separately. It records no
confidence and grants no authority.

## Identifier decomposition

`core.identifier_recall.decompose_identifier` derives a case-folded auxiliary
tuple at retrieval time. The canonical node ID and stored symbol are untouched.

Rules:

- Split `::`, `.`, `#`, path separators and snake underscores.
- Ignore leading/trailing private or language sigils for token exposure.
- Split lower/digit-to-upper camel transitions.
- Split acronym-to-word transitions before the final capital followed by
  lowercase text.
- Use Unicode `isupper`, `islower`, `isalnum` and `casefold`; no ASCII-only
  identifier assumption is introduced.
- Preserve stable first occurrence and remove duplicate auxiliary tokens.

Examples:

```text
_classify_indent             -> classify, indent
length_of_longest_substring  -> length, of, longest, substring
detectDefaultPreflightCommand -> detect, default, preflight, command
HTTPResponseParser           -> http, response, parser
ClassName.method_name        -> class, name, method
__init__                     -> init (while exact __init__ still wins)
module::面積                  -> module, 面積
```

Graph node matching decomposes the symbol tail rather than using path fragments
as implementation-identifier evidence. An exact full graph ID still matches
the canonical identity first, so explicit file-qualified references are not
weakened.

## Query normalization and morphology

Natural-language extraction remains bounded to 12 likely symbol concepts and a
small existing-style stop-word set. It now uses Unicode identifier-shaped words
and preserves an explicit `path::symbol` reference whole before decomposition.

There is no stemmer. One explicit observed family exists:

```text
indentation -> indent
classification -> classify
classified -> classify
```

This supports the actual “2-space indentation is classified as 4-space” query.
The first live capped measurement showed the indentation relation alone was
starved behind six single-token `space`/`classified` test symbols. Adding only
the query's observed classification family makes the target a two-token match,
which the existing entry-evidence policy prefers to single-token ambiguity.
Arbitrary suffix truncation is forbidden: `operation` does not become `oper` or
`opera`.

## Match vocabulary and ordering

The complete vocabulary is:

- `exact_symbol`
- `exact_tail`
- `identifier_token`
- `multi_token_identifier`
- `bounded_morphology`
- `unresolved`

Exact canonical identity and exact tail remain strongest. Multiple meaningful
matched query tokens precede a single token. A morphology-only match follows an
exact token match. Ties use canonical node ID. These are entry facts before the
cap, not final ranking weights; graph centrality, caller count and hotspot score
are not consulted.

Ambiguity is valid. A meaningful query such as `parse` may return multiple
eligible symbols, bounded by the existing entry limit (six in production).

## Low-information tokens and false matches

The small repository-facing low-information set is:

```text
get, set, run, main, data, value, item, test
```

A lone member cannot expand through token membership. It can still resolve an
exact symbol or exact tail, and it can participate when a meaningful query token
also matches the same identifier (`get user` -> `get_user`). This is not a large
English stop-word list.

Matching is token membership only:

```text
cat  -/-> concatenate
run  -/-> runner
```

## Eligibility, structure, and persisted history

`resolve_query_to_graph_nodes` iterates only
`eligible_localization_nodes(graph)`. The order is therefore:

```text
node exists -> RETRIEVE.LIVE.1 eligibility -> decomposition -> query matching
```

Call nodes remain structural-only even if their callee label contains a query
token. Malformed persisted implementation fragments are rejected before token
generation and cannot re-enter. Test-file symbols remain eligible and can match
normally. No node or edge is removed.

## PROJECT_MAP fallback

Query-derived entry nodes are inserted first. Deep/project-map sources can fill
unused bounded slots. If no query-derived node resolves, the established
project-map and graph fallback behavior remains legitimate. Selection metadata
distinguishes:

- `query_derived_entry_nodes`
- `project_map_entry_nodes`
- `project_map_fallback_used`
- `project_map_supplemented`
- `graph_fallback_used`
- `hotspot_only`

A successful identifier-token resolution necessarily makes `hotspot_only`
false.

## Frozen ranking and authority boundaries

Unchanged:

- `relevance_bonus`
- `score_control_node` coefficients
- graph weight alpha/beta/gamma
- context-profile path multipliers
- DFS depth, node and neighbor limits
- hypothesis inference
- CONTROL.SAFETY.LIVE.1
- WAITER.LIVE.1
- PATCH.BASIS.LIVE.1
- OPS.PATCH.1/.2
- OPS.VALIDATE.1/.2
- EXEC.AUTH.LIVE.1
- CTX and patch-safety contracts
- `_classify_indent`

`IdentifierEntryMatch` contains identifiers and bounded match kinds only. It has
no score, confidence, defect-grounding, patch-basis, authorization, write or
apply field. Token overlap is navigation evidence only.

## Persistence, traversal, and external dependencies

Tokens are derived at use time from canonical IDs already loaded in the graph.
There is no persistent token index, schema/version change, database/vector
index, forced repository rebuild, second repository traversal or new content
read. The scan is linear over the RETRIEVE.LIVE.1-eligible population. There are
zero added model calls, embeddings and network calls.

## Verification

Focused regressions cover decomposition, exact lookup, token and multi-token
entry, bounded morphology, ambiguity/caps, low-information handling, substring
false positives, Unicode, malformed and structural exclusion, calc, flat
pytest, test symbols, fallback behavior, frozen ranking, frozen authority, and
the still-broken dogfood target.

## Final live repository measurement

The final deterministic retrieval-half run used the unchanged graph builder and
CONTROL DFS/ranking path. It performed no model, network, validation, patch or
write operation.

```text
graph nodes                         27,723
graph edges                        580,920
eligible localization candidates   18,736
query concepts                     space, indentation, classified
entry limit                        6
query-derived entries              6
PROJECT_MAP fallback used          false
graph fallback used                false
hotspot-only                       false

_classify_indent entry member      true
entry match kind                   multi_token_identifier
matched query terms                indentation, classified
morphology                         indentation->indent,
                                   classified->classify
final CONTROL rank                 1
final CONTROL score                14.0113
relevance_bonus                    0
```

The top six unchanged-ranking results were:

1. `core/code_dna.py::_classify_indent` — 14.0113
2. `tests/test_localization_candidate_population.py::test_classify_indent_defect_remains_reproducible` — 2.002
3. `tests/test_localization_candidate_population.py::test_classify_indent_is_an_eligible_primary_candidate` — 2.002
4. `tests/test_query_symbol_entry_recall.py::test_classify_indent_remains_intentionally_broken_and_untouched` — 2.002
5. `tests/test_dream_taxonomy.py::test_legacy_reference_study_alias_with_space_is_accepted` — 2.002
6. `tests/test_localization_candidate_population.py::test_classify_indent_source_is_untouched_by_this_phase` — 2.0

Timing:

```text
existing graph build               43.066186 s
eligibility view                    0.205775 s
query extraction                    0.000024 s
candidate token matching            0.378191 s
entry selection total               0.518284 s
unchanged CONTROL DFS/ranking        3.871551 s
retrieval after graph               4.768050 s
```

The target's relevance bonus remains zero because this phase intentionally did
not change `relevance_bonus`. Its rank changed only because the implementation
symbol now enters the pool and carries its pre-existing graph/risk evidence.

Focused product smokes build and retrieve real tiny graphs: `calc.py::add`
remains the first query-derived add entry, and
`solution.py::length_of_longest_substring` remains in the flat-pytest
query-derived set. `_classify_indent` still returns `4space` for the pinned
nested two-space fixture.

For this target, RETRIEVE.LIVE.3 is not needed: membership is fixed and the
unchanged final rank is already #1. General ambiguous-query ranking remains a
possible separate evidence-led phase, but this result does not justify tuning
weights or traversal now.

## Test results

- Phase-specific product/resolver suite: 30 passed.
- Focused retrieval/CONTROL compatibility rerun: 110 passed.
- Frozen-boundary group spanning RETRIEVE.LIVE.1, CONTROL.SAFETY, WAITER,
  PATCH.BASIS, OPS.PATCH, OPS.VALIDATE, EXEC.AUTH, patch safety and registry:
  766 passed.
- Registry validator: valid, 150 phases, INDEX count 10, no errors.
- Phase picker: valid; RETRIEVE.LIVE.2 is complete history.
- Benchmark check: 54 passed, 0 errors.
- `compileall` and `git diff --check`: passed (line-ending warnings only).
- Full repository suite: 9,132 passed, 14 skipped, 52 failed.

The 52 broad-suite failures are outside this phase's files and focused
behavior. They consist primarily of historical phase-picker tests expecting an
older proposed phase/top recommendation, approval/hardening report tests whose
required `.agent` source artifacts are absent, mirror report tests with absent
historical artifacts, and one pre-existing context-selection contract failure
that names `core/direct_context_patch_attachment.py` importing
`core.file_capabilities`. No RETRIEVE.LIVE.2 test, resolver boundary, ranking
pin, registry test, product smoke, or frozen authority suite failed.
