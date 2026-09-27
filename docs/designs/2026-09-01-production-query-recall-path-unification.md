# RETRIEVE.LIVE.3 — Production Query-Recall Path Unification

## Scope

This phase is a live integration hardening of RETRIEVE.LIVE.2. It changes no
matching rule, entry ordering, cap, ranking coefficient, graph construction,
candidate eligibility, validation behavior, patch basis, or authority.

The invariant is:

```text
same raw query + same eligible graph population
  -> same query-derived candidate identities
```

through both a focused resolver fixture and the production
`run_control_structured` prefix.

## Side-by-side trace and first divergence

The RETRIEVE.LIVE.2 deterministic closure used:

```text
"2-space indentation is classified as 4-space"
  -> raw terms: space, indentation, classified
  -> bounded relations: indentation->indent, classified->classify
  -> core/code_dna.py::_classify_indent
```

The retained final-product artifact at `.agent/debug_last_control_prompt.txt`
contains a different, longer raw user prompt beginning:

```text
"When I point the agent at a repository that uses 2-space indentation ..."
```

Therefore the first recorded state difference is the raw query itself, before
extraction. The current source did not contain a same-input divergence between
the focused matcher and `select_entry_nodes`: both already reached
`match_identifier_entry`. What it lacked was one API that owned the complete
raw-query resolution path and telemetry showing the internal normalized facts.
The old receipt exposed `query_candidates` (raw extracted terms) but not the
bounded morphology targets, so seeing `indentation` without `indent` did not
prove that morphology had failed.

RETRIEVE.LIVE.3 does not widen semantics to make different prompts equivalent.
It enforces and tests equivalence when the input facts are actually the same.

## One canonical resolver

`core.identifier_recall.resolve_identifier_recall` now owns:

```text
raw query
  -> extract_query_symbol_candidates
  -> prepare_identifier_query
  -> identifier decomposition
  -> existing bounded morphology
  -> match_identifier_entry
  -> existing lexical entry ordering
  -> existing entry cap
```

The caller supplies the already-eligible node IDs. Production CONTROL supplies
`eligible_localization_nodes(graph)` and calls the primitive once.

The compatibility functions `resolve_query_to_graph_nodes` and
`resolve_symbol_to_graph_nodes` delegate to the same core resolver. The latter
no longer maintains an independent exact-tail scan. Exact canonical identity
and exact tail remain strongest because the unchanged RETRIEVE.LIVE.2 matcher
still defines those facts.

`reasoning.deep_project_understand` retains its compatibility inspection role
but owns no morphology and is not the production query-entry authority.

## Live query-fact receipt

The production `entry_resolution` now exposes these bounded facts:

- `raw_query_terms`
- `normalized_query_terms`
- `resolved_entry_nodes`
- `entry_match_kind`
- `morphology_relations`
- `fallback_used`
- `query_resolution_seconds`

It also retains the RETRIEVE.LIVE.2 compatibility fields. Normalized terms are
the exact prepared tokens plus the targets of the existing bounded relations;
they are observability over facts already consumed by the matcher, not a second
normalizer.

For the pinned symptom query the production prefix reports:

```text
raw_query_terms          space, indentation, classified
normalized_query_terms   space, indentation, classified, indent, classify
resolved_entry_nodes     core/code_dna.py::_classify_indent
entry_match_kind         multi_token_identifier
morphology_relations     indentation->indent, classified->classify
fallback_used            false
hotspot_only             false
```

PROJECT_MAP can still supplement unused slots. It is fallback only when
canonical recall resolves no entry; a successful canonical result remains at
the front and cannot be overwritten.

## Frozen boundaries

Unchanged:

- `_BOUNDED_QUERY_MORPHOLOGY` and every RETRIEVE.LIVE.2 matching rule
- low-information-token suppression
- exact/token/multi-token/morphology ordering
- entry and query-term limits
- `relevance_bonus`, CONTROL scoring and graph weights
- candidate eligibility and graph construction
- PROJECT_MAP and graph fallback eligibility
- CONTROL safety, WAITER, PATCH.BASIS, OPS.PATCH, OPS.VALIDATE and EXEC.AUTH
- `_classify_indent`

The canonical resolver reads no repository content, traverses no directory,
rebuilds no graph, calls no model, opens no network connection, and performs
one pass over the supplied eligible population. Query facts remain navigation
evidence only.

## Regression boundary

The phase-specific tests exercise the real `run_control_structured` prefix with
no model call and prove:

- focused/canonical and production query-derived identity parity;
- the actual pinned symptom wording;
- visible `indentation->indent` and `classified->classify` propagation;
- live `_classify_indent` membership and RETRIEVE.LIVE.1 eligibility;
- successful recall cannot become hotspot-only;
- unresolved queries retain PROJECT_MAP fallback;
- exact, calc, longest-substring and substring-false-positive compatibility;
- a supplied eligible population is iterated once;
- the receipt carries navigation facts and grants no authority.

## Final production retrieval-half measurement

The single permitted full-repository run used the unchanged graph builder and
the real `run_control_structured` prefix. It performed no model or network call
and did not patch or validate anything.

```text
graph nodes                         27,759
graph edges                        581,678
eligible localization candidates   18,761
raw query terms                    space, indentation, classified
normalized query terms             space, indentation, classified,
                                   indent, classify
query-derived entries              6
_classify_indent entry member      true
entry match kind                   multi_token_identifier
PROJECT_MAP fallback used          false
graph fallback used                false
hotspot-only                       false
final CONTROL rank                 1
final CONTROL score                14.01

graph build                        55.018119 s
canonical query resolution          0.454069 s
production CONTROL prefix           5.450624 s
retrieval half total               60.468766 s
```

The six production entries were:

1. `core/code_dna.py::_classify_indent`
2. `tests/test_localization_candidate_population.py::test_classify_indent_defect_remains_reproducible`
3. `tests/test_localization_candidate_population.py::test_classify_indent_is_an_eligible_primary_candidate`
4. `tests/test_localization_candidate_population.py::test_classify_indent_source_is_untouched_by_this_phase`
5. `tests/test_query_symbol_entry_recall.py::test_classify_indent_remains_intentionally_broken_and_untouched`
6. `tests/test_dream_taxonomy.py::test_legacy_reference_study_alias_with_space_is_accepted`

The optional historical DB code-unit search reported that
`sentence_transformers` was unavailable and skipped itself. No embedding was
computed and canonical query recall is independent of that optional path.

## Verification results

- RETRIEVE.LIVE.3 plus frozen RETRIEVE.LIVE.2 suite: 37 passed.
- Registry and picker suite: 249 passed.
- Eligibility, CONTROL, WAITER, PATCH.BASIS, OPS.PATCH, OPS.VALIDATE and
  EXEC.AUTH boundary group: 540 passed.
- Registry validator: valid, 151 phases, 147 complete, INDEX count 11.
- Benchmark check: 54 passed, 0 errors.
- `compileall` and `git diff --check`: passed (line-ending warnings only).
- Broad suite: 9,141 passed, 14 skipped, 52 failed.

The 52 broad-suite failures are the same known historical set recorded at the
RETRIEVE.LIVE.2 boundary: absent approval/hardening and mirror source artifacts,
stale tests expecting earlier registry recommendations or older phase statuses,
and the pre-existing context-selection contract failure involving
`core/direct_context_patch_attachment.py`. No query-recall, CONTROL, safety,
registry, picker, benchmark, or RETRIEVE.LIVE.3 test failed.
