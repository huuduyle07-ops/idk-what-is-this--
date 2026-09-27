# CONTROL.SAFETY.LIVE.1 — Localization Rank / Patch Authority Separation

Status: live production safety fix. Track: CONTROL. Prerequisite:
OPS.VALIDATE.1. This is not a report-only phase.

## Reproduced safety defect

CONTROL converted a relative navigation score into a generic number named
`confidence`, then converted that number into an execution-shaped recommendation.
The exact old chain was:

1. `select_entry_nodes` chose graph/project-map candidates.
2. `control_dfs_v2` called `score_control_node`, whose score combined callers,
   callees, impact, graph risk, query overlap, graph weight and depth.
3. `infer_hypotheses` added caller-query and trace bonuses, then normalized the
   raw score with `min(0.95, max(0.1, score / 25))`, plus reason/depth factors.
4. `recommend_action` returned `auto_patch_candidate_allowed` at confidence
   `>= 0.75` for a low-risk graph node, or `safe_patch_with_validation` at
   `>= 0.65`.
5. `build_control_result` copied this into `top_hypothesis`, `decision.action`
   and `patch_intent`.
6. `build_control_prompt` passed the number to `build_patch_policy` and told the
   model `confidence=<value>`.
7. `maybe_run_auto_patch` averaged CONTROL confidence with the model writer's
   separate patch confidence. `is_low_risk_single_file_patch` accepted a target
   merely because it matched the top CONTROL/Scout file. The resulting value was
   thresholded and passed back to `build_patch_policy`.
8. `build_patch_policy` used `control_confidence` thresholds to set
   `auto_apply_allowed`, after which the existing Executor / patch-plan lifecycle
   reached patch safety, apply, validation and rollback.

The deepseek-harness architecture comparison and C.A.T.T.U.S indentation report
both reproduced this chain. The wrong target was prevented from touching the real
checkout only by external or later gates; CONTROL itself had already laundered
navigation rank into authority.

## New contract

`localization_score` is the raw relative navigation heuristic used for ordering.
It is non-probabilistic and non-authoritative. `localization_strength_value` and
`weak|moderate|strong` are presentation-only normalizations. Lexical overlap,
callers, callees, graph risk/centrality, impact, depth and execution/state trace
proximity remain ranking inputs and are classified as navigation evidence.

For compatibility, new results still carry `confidence`, but only with:

```text
confidence_kind = localization_rank_legacy
legacy_control_confidence_deprecated = true
```

Historical `confidence` and unsafe `recommended_action` values remain readable.
The reader preserves the latter as `legacy_recommended_action`, then projects a
safe current action. No patch decision consumes the legacy localization value.

`patch_candidate_state` records three separate facts:

- a localization candidate may be present;
- a defect may or may not be established;
- an exact-source grounded candidate may or may not be ready to be handed to the
  existing patch-safety and authorization gates.

It explicitly records `patch_eligibility_granted=false`,
`auto_patch_candidate_allowed=false`, `write_authority=false` and
`patch_application_authority=false`. CONTROL produces candidate facts, not
authority.

## Defect grounding

`refresh_control_safety` asks OPS.VALIDATE.1's shared
`is_executed_failure_evidence` predicate. Grounding requires all of:

- validation actually ran;
- its legacy boolean is false;
- its typed category is genuine executed-failure evidence;
- a typed preflight location, or the executed output's exact candidate path,
  binds the failure to an already-ranked file.

The path-output fallback is bounded to candidate paths already produced by
CONTROL and performs no search or traversal. It supports Python tracebacks while
leaving OPS.VALIDATE.1 frozen. `no_validation_command`, `no_tests_collected`,
`validation_tool_unavailable`, `missing_toolchain`, validation-environment
failures and every other inconclusive category do not ground. A validation pass
does not ground. Merely detecting a command does not ground.

The grounded candidate is independent of rank. `top_hypothesis` remains the
highest localization candidate, while `grounded_hypothesis` may be lower-ranked.
`patch_intent` switches to that grounded candidate only when failure evidence
binds it. A nonempty exact `source_snippet` must still be a literal substring of
the named repository file before `eligible_for_patch_safety_handoff=true`.

Current localization-only actions are `inspect_candidate` and `needs_grounding`.
An executed failure without exact source uses `acquire_source_context`. A bound
failure plus exact source uses `grounded_defect_candidate`. None is execution
permission.

## Consumer audit

| Consumer | Former class | Current class and behavior |
| --- | --- | --- |
| `format_control_context` | display | Displays score/strength as localization and labels legacy confidence. |
| `build_control_prompt`, `build_control_prompt_human` | prompt | Says highest-ranked localization candidate; localization-only model output is forced to null patch/escalation. |
| `build_patch_intent` | candidate projection | Carries the legacy value only with its localization kind and projects source/context facts; the refreshed action is inspection/acquisition/grounded-candidate vocabulary, never execution. |
| `feature_context.should_call_scout`, `build_fallback_scout` | ranking/context acquisition | Reads the top candidate/localization only to decide whether and where more context is useful; grants nothing. |
| `source_snippet_fallback.hydrate_control_source_from_scout` | source acquisition/candidate | Acquires exact source but no longer raises confidence or writes `recommended_action=patch`. |
| `pipeline.run_review_pipeline` | review optimization | Uses only the OPS.VALIDATE.1 executed-failure predicate; model patch confidence remains separate. |
| `pipeline.normalize_patch_candidate_with_control_source` | exact-source normalization | May broaden a model quote to CONTROL's exact source, but runs behind the independent grounding boundary and grants nothing. |
| `postprocess_gates` | patch candidate | Rejects model patch/plan output before repair when CONTROL has no grounded exact-source candidate. |
| `web.app._control_target_path`, `_control_source_text`, `web.runner` equivalents | source acquisition/display | Resolve candidate context for harness checks; top-rank fallback is non-authoritative and the payload boundary still applies. |
| `web.app.generate_patch`, `generate_candidates` | candidate generation | Applies the same payload boundary to direct web generation results. |
| `sleeping_consultant._generate_patch_plan` | candidate generation | Applies the same payload boundary; source acquisition alone grants nothing. |
| `pipeline.is_low_risk_single_file_patch` | patch policy | Requires the grounded exact target, not top rank or Scout membership. |
| `pipeline.maybe_run_auto_patch` | patch policy/apply decision | Requires grounded handoff, thresholds only model writer confidence, and never reads CONTROL confidence or recommended action. |
| `decision_helper.build_patch_policy` | patch policy | Ignores retained `control_confidence`; requires independent grounding plus model patch confidence and existing language/validation/style gates. |
| `patch_gates.reject_ungrounded_candidate_quotes` | patch safety | Demotes the model patch only; no longer rewrites localization rank when quote grounding fails. |
| `patch_grounding.enforce_patch_candidate_grounding` | patch safety | Its historical payload-level `control_confidence` field is only zeroed on rejection; it cannot authorize a patch and is not a CONTROL-result read. |
| `prompter.build_control_patch_recheck_prompt` | repair prompt | Serializes the already-labelled CONTROL hypothesis for an existing failed-patch repair; it does not threshold rank or grant authority. |
| web runner harness | display/apply gate | Treats a CONTROL-grounding rejection as the existing ungrounded-patch blocked mode. |
| persistence/replay JSON | persistence | Old fields remain readable; new metadata attaches semantics without rewriting stored history. |

The model response's top-level `confidence` remains the patch writer's separate
self-assessment. It may participate in existing writer thresholds only after
independent grounding. It is not CONTROL localization confidence.

## Authority and scope

The postprocess boundary is a necessary precondition only. Passing it hands the
candidate to literal quote grounding, patch safety, patch policy, Executor or
patch-plan lifecycle, validation, rollback, CTX.PATCH/CTX.APPLY and any required
human approval. None was weakened or reimplemented. `AUTO_PATCH_ENABLED=false`
still returns before any candidate can execute.

There is no rule forbidding test files. A real failure may ground a test-file
candidate exactly as it may ground production source. There is no non-lexical
signal shortcut: graph topology and trace proximity remain navigation evidence.

No retrieval weight, entry-node choice, traversal depth, lexical ranking,
project map, indexing, validation detection/classification, patch write/rollback,
model invocation, network operation or repository traversal was added or
redesigned. WAITER.LIVE.1, code_dna indentation, Phantom Limb, CLI DB/session
behavior and WORKER.DECL.2B remain out of scope.

## Known limitation

Until WAITER.LIVE.1 supplies an independently typed change-request route,
feature/refactor requests that reach CONTROL without genuine executed failure
evidence remain localization-only and cannot auto-apply through this path. They
may still be inspected and shown. This conservative limitation is preferable to
recreating task semantics inside CONTROL.
