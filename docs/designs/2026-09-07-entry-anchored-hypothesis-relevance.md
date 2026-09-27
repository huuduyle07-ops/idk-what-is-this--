# CONTROL.LOCALIZE.LIVE.2 — Entry-Anchored Hypothesis Relevance

The exact long-form T6 deterministic prefix now localizes to
`core/code_dna.py::_classify_indent`. RETRIEVE.LIVE.4, the six-entry cap, graph
construction, numeric CONTROL coefficients, patch basis and authority remain
unchanged. This is a live selection and handoff change, not a report-only phase.

## Measured failure before implementation

The replay used the raw prompt preserved in
`tests/test_repository_specificity_entry_ordering.py::ROUND5_T6_PROMPT`:

> When I point the agent at a repository that uses 2-space indentation, the
> patches it writes come back using 4-space indentation instead. Something
> looks wrong with the way repo style gets detected. Please find the root
> cause and fix it.

The old code sorted DFS evidence by an additive graph score, discarded all but
eight rows before hypothesis inference, and then returned the five largest
scores. It returned RETRIEVE telemetry but did not consume it in hypothesis
ordering. The bounded replay had no executed evidence or source bodies.

| Candidate | Entry rank | Old score | Callers | Old reason |
|---|---:|---:|---:|---|
| `core/executor.py::run` | — | 223.2558 | 111 | has upstream callers |
| `core/code_dna.py::_classify_indent` | 2 | 22.0185 | 10 | has upstream callers |
| `core/harness_controls.py::_indent_of` | 3 | 12.0093 | 5 | has upstream callers |
| `core/pipeline.py::_indent_of` | 4 | 12.0093 | 5 | has upstream callers |
| `patching/patch_engine.py::_indent_of` | 5 | 12.0093 | 5 | has upstream callers |
| `patching/patch_engine.py::apply_patch_from_json` | — | 11.5595 | 5 | has upstream callers |
| `core/check_oracle_assessment.py::_indentation_signature` | 1 | 6.0037 | 2 | has upstream callers |
| `core/answer_entity_grounding.py::_annotation_point` | 6 | 6.0037 | 2 | has upstream callers |

For `executor.run`, the components were caller count × 2 = 222, risk score = 1,
low-risk level bonus = 1, graph weight = 0.2558, and depth penalty = −1.
Query bonus, downstream calls and impact were zero. No source-specific,
executed-frame or defect-grounding evidence explained its win.

Its actual relation is an **anchored expansion**, not an unanchored node:
`_indent_of ← apply_patch_from_json ← executor.run`, two upstream resolved-call
edges. The implementation therefore gates graph-only anchored expansions as
well as unanchored hubs below direct query entries. It does not falsely report
that this real graph lacks a path. The separate synthetic 100-caller hub pins
the unanchored case.

## Selection contract

The anchor vocabulary is `direct_query_entry`, `anchored_expansion`, and
`unanchored_expansion`. Direct membership comes only from RETRIEVE's
`query_derived_entry_nodes`; fallback entries do not acquire that label.
Expanded rows retain their originating entry, edge kind, direction and hop
count along the existing bounded DFS path. The legacy substring graph query
is not enough to certify an edge: the bounded trails are verified against the
already-loaded resolved-call edges. There is no additional neighborhood
expansion, repository walk, persistent index or graph mutation.

The ordering is lexicographic:

1. Existing typed executed-failure reference, explicit query reference, direct
   query entry, anchored expansion, unanchored expansion.
2. RETRIEVE's already-computed lexical specificity of the entry/anchor.
3. Bounded hop count.
4. The unchanged legacy navigation score, including structural centrality.
5. Canonical node identity.

All existing twenty bounded candidates reach this gate before the five public
hypotheses are chosen. DFS reserves room for pending entries within the same
twenty-node budget. Depth two, three neighbors and six entries remain fixed.

The first five T6 entries share lexical specificity. Their existing graph
support distinguishes `_classify_indent` after anchoring. This selects an
inspection target; it does not prove the defect. No source feature was added:
the current Python graph has source spans but no stored body/expressions for
these candidates. The phase neither reads their bodies to rank them nor infers
implementation semantics from their names. Entry rank is telemetry, not the
final tie-break, so the rank-one helper is not made unbeatable.

Every bounded row exposes anchor relation, origin, entry rank, query support,
source-support availability, graph path, centrality components, final class,
selection result and selection reason. Historical numeric score and normalized
localization fields remain compatible; no new confidence value is introduced.

## Target handoff

The target-consistency seam is separate from frozen answer-entity grounding.
A model payload cannot substitute its own target receipt or use entity
existence as defect localization. The operational guard rejects a candidate
which does not include the localized file/symbol; unnamed snippet operations
must quote its already-loaded body. A concrete source target no longer falls
back silently to another function when source extraction fails.

The existing PATCH.BASIS executed-failure binding can legitimately choose a
different bounded hypothesis. The handoff then records previous target,
replacement target, replacement basis, evidence source, current receipt
freshness and an evidence fingerprint. It derives that receipt from current
CONTROL state, never from model output. Free-text execution/state traces do
not count as typed executed evidence. No file is read by this seam.

CLI, web and follow-up display run the unchanged entity-grounding gate and
then preserve the localized target explicitly. Other recognized repository
references are marked as context references, not replacement targets. Text is
qualified, not deleted. Structured output carries the target receipt, while
execution receipts and candidate bytes remain untouched by display handling.
Explicit-change and analysis routes bypass this seam.

## Independent continuation limit

The exact long prompt routes to `defect_repair`, selects the correct target,
and acquires its exact source through the existing source step. With the
recorded full-validation budget-exhaustion condition, DEFECT.PROBE.LIVE.1 then
returns `probe_result=unavailable`, `defect_probe_attempted=false`, reason
`no deterministic typed adapter exists for the preserved task facts`.

The frozen adapter accepts the shorter previously tested formulation but does
not accept this exact long prompt. The replay does not shorten the input,
fabricate a candidate, or change that adapter. Consequently patch basis stays
unresolved, candidate is absent, and post-probe and OPS.VALIDATE.3 are not
reached for the exact prompt. This is a separate downstream limitation.

## Boundaries and evidence

Permanent tests retain the measured bounded T6 fixture and the actual entry
receipt. Additional regressions cover an unanchored hub at extreme magnitude,
verified/invalid expansion paths, entry budget reservation, typed executed
evidence override, explicit references, canonical ties, legitimate test
symbols, same-file symbol replacement, forged model receipts and unchanged
explicit/analysis handoffs. Hash/AST pins protect frozen retrieval, graph,
probe, validation, authority and CONTROL safety implementations.

The production change adds no model call, network call, repository traversal,
source read, graph build or index. The QA harness constructs ordinary graph
snapshots as replay inputs and measures CONTROL independently; those setup
costs are not attributed to the new ranking code. `_classify_indent` remains
byte-identical and intentionally unfixed. No stash, reset or clean was used.

## Completion record

These are the exact maintained files changed by this phase, relative to the
already-dirty starting workspace. Earlier unrelated changes were retained.

| File | Change |
|---|---|
| `core/control_engine.py` | Preserve entry slots, retain/verify DFS trails, consume entry telemetry, gate hypotheses before truncation, expose reasons and handoff, prevent concrete-target source fallback |
| `core/localization_relevance.py` | New deterministic relevance classes, path verification and ordering |
| `core/localization_handoff.py` | New target receipt, payload guard and display seam |
| `core/pipeline.py` | Guard target before normalization/apply handoff |
| `core/postprocess_gates.py` | Guard target before and after existing repair gates |
| `core/session_io.py` | Follow-up display uses target-consistent grounding wrapper |
| `main.py` | CLI terminal display uses the wrapper |
| `web/runner.py` | Web terminal display uses the wrapper |
| `tests/test_control_entry_relevance.py` | 21 phase regressions |
| `tests/fixtures/control_localize_live2_t6.json` | Measured pre-change bounded T6 features and entry receipt |
| `tests/fixtures/control_localize_live2_boundaries.json` | Frozen file and CONTROL function pins |
| `tests/test_phase_registry.py` | New phase membership and total/track counts |
| `tests/test_phase_picker.py` | Completed-history count |
| `docs/roadmap/phase_registry.json` | Completed phase record and frozen scope |
| `docs/designs/2026-09-07-entry-anchored-hypothesis-relevance.md` | This report |

Diagnostic scripts, logs, graph inputs and JSON receipts additionally reside
under the ignored `.tmp/localize-*` paths; they are QA artifacts, not runtime
changes. The full bounded current receipt is
`.tmp/localize-live2/current-prefix.json`; the real preflight/continuation is
`.tmp/localize-live2/current-continuation.json`.

| Requested report item | Result |
|---|---|
| 1. Exact files | Fifteen maintained files listed above |
| 2. Old semantics | Numeric graph sort → first eight evidence rows → five hypotheses |
| 3. Reproduced hub factors | 111 callers; 222 caller points; risk 1 + level 1; weight 0.2558; depth −1; total 223.2558; only upstream-caller reason |
| 4. Anchor vocabulary | Direct query entry / anchored expansion / unanchored expansion |
| 5. Direct-entry meaning | Query navigation relevance only; no defect, patch basis or authority |
| 6. Expansion meaning | Verified originating entry, resolved-call direction and path of at most two hops |
| 7. Unanchored hub | Cannot cross a direct-entry class through any centrality magnitude |
| 8. Stronger override | Existing typed executed-failure binding or explicit reference; current existing grounded handoff can carry a replacement receipt |
| 9. Ordering | Evidence class → consumed specificity → bounded hops → unchanged numeric navigation support → canonical identity |
| 10. Centrality | Retained for expansion/navigation, impact and late ordering within comparable relevance |
| 11. RETRIEVE facts consumed | Direct membership, rank, matched tokens, match kind and lexical-specificity score; no IDF recomputation |
| 12. Source support | Unavailable at ranking time; no body feature used, no new source read |
| 13. RETRIEVE delta | Zero semantic/code delta; matching count 792 before and after this phase |
| 14. Coefficient delta | Zero; the score function and legacy relevance bonus are AST-pinned |
| 15. Authority delta | Zero; frozen safety/basis/authorization implementations stay unchanged |
| 16. Current matched population | 792 matches in 19,689 eligible symbols; repeated same-snapshot matching/order agrees |
| 17. Current entry set | Listed immediately below; six entries, no fallback |
| 18. Target retrieval rank | 2 |
| 19. CONTROL target | `core/code_dna.py::_classify_indent` |
| 20. Executor outcome | Rank 10 of the 15 visited candidates; anchored two-hop expansion; rejected below direct entries despite score 223.26 |
| 21. Handoff | Concrete target retained; current typed stronger evidence required for replacement; other recognized answer references explicitly marked as context |
| 22. Pre-probe | `unavailable`, attempted false; no deterministic adapter for the exact preserved long prompt |
| 23. Candidate | Not reached; patch basis unresolved; no model-generated or fabricated candidate |
| 24. Post-probe | Not reached |
| 25. Targeted validation | Not reached on the exact prompt; existing targeted/probe regression suite passed |
| 26. Full production validation | Actual 30-second run: inconclusive / validation_budget_exhausted; timeout unchanged |
| 27. T1/T2/T3 | Existing direct failure, caller assertion and pytest imported-implementation cases pass with `calc.py::add` / `solution.py::length_of_longest_substring` unchanged |
| 28. T4 | Explicit-change handoff remains bypassed; missing-import authorship regression not fixed |
| 29. T5 | Analysis route bypasses target-localization handoff; existing analysis/answer-grounding regression coverage passes |
| 30. Model delta | Zero added calls; no provider used for these replays |
| 31. Network delta | Zero added calls |
| 32. Traversal delta | Zero repository traversals added; bounded DFS trails are verified against already-loaded edges |
| 33. Graph/index delta | No runtime rebuild, graph mutation, persistent index or construction change; ordinary QA graph inputs were built separately |
| 34. Performance | Three paired CONTROL-only runs: median 9.865094 s → 9.998453 s, +0.133359 s / +1.35%; graph setup excluded |
| 35. Tests | Phase suite 21 passed; frozen matrix 390 passed; latest broader focused batch 461 passed; fresh affected-code batch 299 passed. These batches overlap |
| 36. Broad suite | Raw run: 9,637 passed, 85 failed, 15 skipped in 1,359.28 s. Thirty-six failures cleared in fresh affected-code tests; remaining 49 reproduced with pre-phase registry |
| 37. Benchmarks | `benchmarks/run_benchmarks.py --check`: 54 cases, zero errors |
| 38. Registry/governance | Registry valid, 165 phases; registry/picker tests pass. Compileall and git diff --check pass |
| 39. Limitations | Navigation support is not defect proof; source bodies absent; exact long-prompt probe adapter unavailable; 49 existing broad-suite failures; display qualifies recognized references without inferring arbitrary prose semantics |
| 40. Black-box readiness | Ready to rerun T5+T6 to verify localization and target consistency. Full T6 repair is not expected until the separate exact-prompt probe limitation is addressed |

The current six entries, in RETRIEVE order, are:

1. `core/check_oracle_assessment.py::_indentation_signature`
2. `core/code_dna.py::_classify_indent`
3. `core/harness_controls.py::_indent_of`
4. `core/pipeline.py::_indent_of`
5. `patching/patch_engine.py::_indent_of`
6. `core/answer_entity_grounding.py::_annotation_point`

`core/mirror_tunnel_derailment_score.py::_point_lines` exists in the eligible
population but is outside the current entries and bounded CONTROL evidence.
It was not invented as a competing source-supported hypothesis.

The 49 remaining broad failures concern retained approval/hardening artifacts,
historical roadmap recommendations, and the unchanged
`core/direct_context_patch_attachment.py` selector-import assertion. They were
re-executed against the pre-phase registry without swapping workspace files:
the same 49 fail. The broad process had started before the final registry
count corrections and before a handoff keyword-argument update; its other 36
failures are cleared by a fresh process running all affected modules (299
passed). A second 22-minute broad run was not performed, and no clean broad
run is claimed. Logs: `.tmp/localize-broad-1.log`,
`.tmp/localize-affected-rerun.log`, `.tmp/localize-baseline-failures.log`.

The real production validation command was
`python -m pytest -q --basetemp=.tmp/localize-production-validation -p no:cacheprovider`.
The temporary directory isolates test outputs; the existing validation runner
still enforces its 30-second budget. The adapter result above was observed
again using this actual timeout receipt, not just a replayed timeout fixture.

## Explicit answers

| Question | Answer |
|---|---|
| Can “has upstream callers” alone make an unanchored hub win? | It cannot displace a query-anchored entry. With no query anchor, fallback hypotheses remain weak navigation hypotheses, never defect evidence |
| Is centrality removed? | No |
| Can stronger traceback/execution evidence override an entry? | Yes, through an existing typed binding; free-form trace text cannot |
| Was RETRIEVE.LIVE.4 changed? | No |
| Did the entry cap change? | No, still six |
| Did matching semantics change? | No |
| What is `_classify_indent` retrieval rank now? | 2 |
| What does CONTROL select? | `core/code_dna.py::_classify_indent` |
| Can downstream silently name another target? | The operational and display handoffs retain the canonical target; a replacement needs current typed stronger evidence |
| Does localization create patch authority? | No |
| Were model calls added? | No |
| Was traversal added? | No repository traversal; verification uses the already-loaded graph edge list |
| Was graph rebuilt? | No new runtime rebuild; QA constructed ordinary replay snapshots separately |
| Was `_classify_indent` fixed? | No; real source is byte-identical |
| Is this report-only? | No; selection, candidate handoff and CLI/web/follow-up display are wired live |
