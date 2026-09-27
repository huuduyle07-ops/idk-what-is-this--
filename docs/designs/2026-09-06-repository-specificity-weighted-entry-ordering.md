# RETRIEVE.LIVE.4 — Repository-Specificity Weighted Entry Ordering

## Scope

This phase owns exactly one thing: **the order of already-resolved eligible
entry candidates**, immediately before the bounded CONTROL entry cap.

It does not own:

| Concern | Owner |
|---|---|
| candidate existence / eligibility | RETRIEVE.LIVE.1 |
| query → symbol recall, decomposition, morphology | RETRIEVE.LIVE.2 / .3 |
| final graph ranking | downstream CONTROL |
| defect grounding, patch basis, authority | DEFECT.PROBE / PATCH.BASIS / EXEC.* |

`core/code_dna.py::_classify_indent` remains intentionally unfixed. It is the
dogfood target, not the deliverable.

## The measured failure

Round-5 production evidence, for the real long-form user prompt:

```text
When I point the agent at a repository that uses 2-space indentation, the
patches it writes come back using 4-space indentation instead. Something looks
wrong with the way repo style gets detected. Please find the root cause and fix
it.
```

`core/code_dna.py::_classify_indent` was present in the graph, source-backed,
localization-eligible, and **matched** — and ranked **723rd of 734** matched
entry candidates against a cap of **6**. Nothing downstream could recover it,
because it never entered CONTROL.

The cause was the ordering key, not recall:

```python
(
    _ENTRY_KIND_ORDER[match.entry_match_kind],   # 5 hard tiers
    -len(match.matched_query_tokens),            # raw count
    -(matched - morphology),
    match.node_id,
)
```

Two independent defects compound:

1. **`bounded_morphology` was a hard bottom tier.** The only route to the target
   is `indentation → indent`, so it started behind every other kind regardless
   of how informative the match was.
2. **The tie-break was a raw matched-token count**, which scores every token
   alike. A long prose request contains ordinary words that happen to be
   identifier tokens, so two worthless matches beat one excellent one.

Measured document frequency over the eligible population makes the second point
concrete:

| token | df | idf |
|---|---|---|
| `space` | 1 | 9.17 |
| `patches` | 1 | 9.17 |
| `indentation` | 4 | 8.26 |
| `indent` | 13 | 7.30 |
| `at` | 117 | 5.11 |
| `writes` | 210 | 4.51 |
| `repository` | 230 | 4.44 |

Matching `repository` is ~50× less informative than matching `indentation`, and
`-len(matched_query_tokens)` cannot tell them apart. The winners under the old
key were `test_ordering_falls_back_to_path_when_created_at` (matched: `at`,
`back`) and `test_create_experiment_writes_registry_record` (matched: `agent`,
`writes`).

## Reproducing before implementing

The recorded Round-5 rule was `max IDF × precision`. The phase gate was to
reproduce that calculation **exactly** rather than to implement a plausible
reading of its name. The verbatim experiment was recovered and replayed against
the real eligible population before any production edit:

```python
df[t]  # counted once per eligible candidate whose decomposed tail contains t
N    = len(eligible)
idf  = lambda t: math.log(N / (1 + df.get(t, 0)))
key  = lambda m: (
    -max((idf(t) for t in m.matched_query_tokens), default=0)
    * len(m.matched_query_tokens)
    / max(1, len(decompose_identifier(tail(m.node_id)))),
    m.node_id,
)
```

The replay returned the recorded top six, in the recorded order:

```text
1. core/check_oracle_assessment.py::_indentation_signature
2. core/code_dna.py::_classify_indent          <-- the target
3. core/harness_controls.py::_indent_of
4. core/pipeline.py::_indent_of
5. patching/patch_engine.py::_indent_of
6. core/mirror_tunnel_derailment_score.py::_point_lines
```

Two details of the recovered formula differ from the "obvious" reading and are
kept as measured, not normalized:

- IDF is `log(N / (1 + df))`, **not** `log((N + 1) / (df + 1))`.
- Precision is `|matched query tokens| / |candidate identifier tokens|` — the
  numerator counts *query* tokens, the denominator counts *identifier* tokens,
  and neither side filters low-information tokens.

## Repository-local specificity

```text
N          = eligible localization candidates for this query
df(token)  = candidates whose decomposed identifier CONTAINS token
             (candidate-level: repeats inside one identifier count once)
token_idf  = max(0, log(N / (1 + df(token))))
```

`max(0, …)` is the one deliberate addition. The raw logarithm turns negative
once a token is carried by nearly every candidate; multiplied by precision that
inverts the ordering and ranks sprawling identifiers above tight ones in a small
repository. The floor is verified inactive on the real T6 population, where the
least specific matched token still scores 4.44.

Frequencies are derived at use time from already-loaded canonical symbols. There
is no global English corpus, no pretrained table, no download, no persistence,
no schema and no index migration: a token that is rare here may be everywhere in
the next repository, which is the entire point.

Only the query's own normalized terms are tracked, so the map is bounded by the
query (13 entries for the T6 prompt) rather than by the ~19k-symbol vocabulary.

## Ordering

```python
(
    exact_identity_rank,            # 0 exact_symbol, 1 exact_tail, 2 lexical
    -lexical_specificity_score,     # max_match_specificity × identifier_precision
    -(matched - morphology),        # exact token equality ahead of a bridge
    node_id,                        # canonical, stable, scan-order independent
)
```

Four components, and no more. Each earns its place:

- **Explicit identity stays privileged.** A full `path::symbol` and an exact tail
  keep their own tiers, so `_classify_indent` and
  `core/code_dna.py::_classify_indent` still resolve first even when a partial
  match scores higher on specificity. User symbol intent is not a heuristic.
- **Specificity × precision replaces the raw count.** `max`, not `sum`: a sum
  rewards a long identifier for accumulating several mediocre coincidences.
  Precision prevents one rare token buried among unrelated identifier tokens
  from winning outright — `_classify_indent` (1/2) beats
  `_classify_indent_repository_configuration_manager` (1/5).
- **Morphology is a tie-break, not a tier.** `bounded_morphology` no longer
  starts last; it competes on specificity and loses only to exact token equality
  at *equal* specificity. That is precisely why `_indentation_signature` (exact
  `indentation`) ranks above `_classify_indent` (bridged `indentation → indent`)
  while both sit above every `repository`/`writes` coincidence.
- **Canonical id last**, so equal evidence never depends on graph scan order.

Match kind is not deleted — it still drives tiers 0/1, still rides on
`IdentifierEntryMatch`, and is still reported in telemetry.

## Comparative measurement

One candidate population, the exact Round-5 long prompt, 19,264 eligible /
747 matched:

| ordering rule | target rank |
|---|---|
| current / legacy key | 736 |
| morphology promoted one tier | 736 |
| sum IDF | 17 |
| max IDF | 6 |
| max IDF × precision (Round-5) | **2** |
| **chosen production key** | **2** |

Round-5 recorded 723 / 269 / 19 / 6 / 2 over **19,177 eligible / 734 matched**.
The eligible population grew by **87 nodes** between the two runs, accounted for
by the ANSWER.GROUND.LIVE.2 modules that landed afterwards, so the legacy and
sum-IDF numbers come from different repository states and are reported as such.
The corrected rank is 2 in both states.

Round-5's 269 was "morphology promoted **and** filler words removed"; the exact
filler list was not recorded, so that cell is not reproducible on its own. The
two components were therefore measured separately here — promotion alone leaves
the rank at 736, and the filler variant is reported in the next section.

### The stopword route does not work

No stopword was added. Measured on the same population, dropping the nine filler
terms this prompt actually contributes — `at`, `back`, `repository`, `writes`,
`point`, `come`, `using`, `uses`, `agent`:

| variant | matched | target rank |
|---|---|---|
| filler removed, legacy key | 18 | 7 |
| filler removed, morphology promoted | 18 | 7 |
| filler removed, chosen key | 18 | 2 |
| **no stopword change, chosen key** | **747** | **2** |

The stopword route fails twice over. It still misses the cap — rank 7 of 18 —
and it gets there by *deleting recall*: the matched population collapses from
747 to 18, which is exactly the invariant this phase is required to preserve.
Specificity reaches rank 2 while leaving all 747 matches intact.

`_QUERY_STOP_WORDS` is unchanged and still contains none of `at`, `back`,
`repository`, `writes`, pinned by test.

## What did not change

- **Matching semantics.** For an identical query and eligible population the SET
  of matched candidates before the cap is byte-identical — verified against the
  reconstructed pre-phase module across six queries (747 / 122 / 300 / 333 /
  517 / 318 matches), including per-candidate match kinds and raw query terms.
- **Identifier decomposition, bounded morphology, low-information tokens, the
  query stop word list.** RETRIEVE.LIVE.2 stays frozen.
- **The entry cap is still 6.** The target earns its place; it is not admitted
  by widening the gate.
- **`relevance_bonus`, `score_control_node`, graph weights, path multipliers,
  DFS depth, neighbour limits.** Pinned in tests. Any downstream difference
  arises only because a better entry set now reaches CONTROL.
- **Fallback semantics.** A resolved query-derived entry set still avoids
  hotspot-only fallback; an unresolved query still reaches PROJECT_MAP.
- **Graph node ids, canonical symbol names, source spans, edges.** The index is
  auxiliary retrieval metadata.
- **Historical artifacts.** Old retrieval receipts stay readable and their ranks
  are not reinterpreted as if specificity had been active.

## Cost

Measured on the real population:

| measurement | value |
|---|---|
| frequency-map build, 19,264 candidates | 12.1 ms |
| ordering 747 matched candidates | 0.82 ms |
| full resolve, legacy → current | 512 ms → 557 ms (+8.8%) |
| graph build (for scale) | ~76,000 ms |
| full resolve, 3-node repository | 0.103 ms |

The map is built inside the **existing** single population scan: each candidate
is decomposed once and the same tokens feed both the matcher and the frequency
counter. No second traversal, no second decomposition, and no
`matches × population` term — ordering is linear in the eligible population plus
the matched set.

## CONTROL safety

`token_idf`, `max_match_specificity`, `identifier_precision` and
`lexical_specificity_score` are navigation evidence. None is called confidence
or probability, none is stored on `IdentifierEntryMatch`, and none can reach
defect grounding, patch basis, validation authority or write authority. The
score answers "which symbols should CONTROL look at", never "is this the bug".

## Observability

`IdentifierRecallResult.as_debug_dict()` gains bounded facts: document frequency
for the query's own terms, the specificity population count, and one row per
entry that survived the cap — matched tokens, strongest match token and its df,
max match specificity, identifier precision, score and rank. The repository
vocabulary is never dumped.

## Product smokes

No provider call, no network, no write.

| smoke | result |
|---|---|
| real repository, exact Round-5 long prompt | target rank **2**, inside the 6-node query-derived entry set, `fallback_used=False`, `hotspot_only=False` |
| small calc repository | `calc.py::add` rank 1 by exact tail |
| filler-heavy prompt, 61 synthetic candidates | rare `_indent_width` rank 1 against 60 `repository` coincidences |
