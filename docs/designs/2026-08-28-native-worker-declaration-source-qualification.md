# WORKER.DECL.1 — Native Worker Declaration Source Qualification & Wiring

**Status:** complete — outcome `WORKER_DECL_1_SOURCE_UNAVAILABLE`
**Date:** 2026-08-28
**Depends on:** CHECK.LIVE.1B (complete, frozen). Not CHECK.2. Not CHECK.LIVE.2.

## Result, up front

> **No independent structured worker change declaration exists in this
> repository — pre-execution or post-execution — that could be wired without
> adding a model invocation.**

The CHECK.LIVE.1B seam stays exactly as it is, unpopulated, and every ordinary
production run keeps reporting `worker_declaration_source = legacy_plan_derived`
honestly. No production protocol was modified. What this phase adds is the
*qualification itself*: the traced call path, the reason each candidate fails,
and an executable test suite that will fail loudly the moment the architecture
grows the observation point it currently lacks.

Per §46 of the phase brief this is a successful completion, not a failure.
Discovering that the architecture has no worker-side self-report channel is the
useful result — it names precisely what a future worker-protocol phase has to
build before self-report fidelity can be measured at all.

## 1. The primary question

> Does the real worker/runtime already produce an independent structured
> declaration of intended or completed changes without an additional model
> invocation?

**No.** Neither outcome A (`post_execution_worker_declaration`) nor outcome B
(`pre_execution_worker_intent`) is available. Outcome C applies.

## 2. The real worker/model lifecycle

`run_patch_plan_with_artifacts` (`core/run_lifecycle.py:158`) is the one apply
entry point CHECK.LIVE.1B instrumented. It has exactly eight production callers:

| Caller | `source` | How the plan was produced |
|---|---|---|
| [`core/pipeline.py:717`](../../core/pipeline.py) `maybe_run_auto_patch` | `pipeline` | `state.json_block["patch_plan"]` |
| [`core/sleeping_consultant.py:613`](../../core/sleeping_consultant.py) `_run_patch_item` | `dream_patch_if_safe` | `_generate_patch_plan` → model |
| [`core/sleeping_consultant.py:1022`](../../core/sleeping_consultant.py) `_revalidate_ready_to_apply_item` | `dream_revalidation` | a saved `patch_plan.json`, no model at all |
| [`core/worker_runs.py:434`](../../core/worker_runs.py) `validate_imported_worker_proposal` | `worker_run_validate` | an external worker's `patch_plan.json` on disk |
| [`scripts/run_patch_proposal_queue.py:632`](../../scripts/run_patch_proposal_queue.py) `_process_item` | `proposal_queue` | `_generate_patch_payload` → model |
| [`web/app.py:998`](../../web/app.py) `dream_apply_route` | `web_dream_apply` | a stored dream artifact |
| [`web/routes/patch_routes.py:298`](../../web/routes/patch_routes.py) `test_patch_plan` | `web_test_patch_plan` | an operator-supplied plan |
| [`web/routes/patch_routes.py:393`](../../web/routes/patch_routes.py) `apply_patch_plan_route` | `web_apply_patch_plan` | an operator-supplied plan |

The full chain for the representative live path, traced rather than inferred:

```text
core/pipeline.py :: run_draft_pipeline / run_review_pipeline
    → agents/gemini_client.py :: run_gemini_request_2      # the last model turn
        → returns response.text — a bare string
    → core/pipeline.py :: finalize_answer
        → core/json_utils.py :: extract_json_block(answer)  # prose → dict
        → state.json_block = {summary, issues, patch_candidate,
                              patch_plan, confidence, needs_escalation}
    → core/pipeline.py :: maybe_run_auto_patch
        → plan = state.json_block["patch_plan"]
        → core/run_lifecycle.py :: run_patch_plan_with_artifacts(plan)
            → patching/patch_plan_executor.py :: apply_patch_plan   # ← mutation
            → _attach_shadow_post_run_reconciliation                # ← CHECK.LIVE.1B
```

### 2.1 When does the last model invocation occur?

**Strictly before patch application, on every instrumented path.** This is
verified mechanically, not asserted: `test_no_apply_path_reaches_a_model_after_applying_its_patch_plan`
builds a name-based transitive call graph over `core/`, `agents/`, `patching/`,
`web/` and `scripts/` (108 functions reach a model client), then checks every
function that calls `run_patch_plan_with_artifacts`. Zero model-reaching calls
occur after the apply call in any of them.

### 2.2 The one post-application model turn, and why it changes nothing

There *is* a production model invocation that happens after a patch is applied:
`core/self_correct_loop.py :: run_self_correct_loop` calls back into
`pipeline.py :: _re_patch_fn`, which asks Gemini/DeepSeek for a revised patch
after a failed attempt. Three facts disqualify it, and all three are pinned by
`test_the_only_post_apply_model_turn_drives_a_different_engine`:

1. **It is a re-patch request, not a report.** Its return value is a new
   `patch_candidate` — planning output, not self-report. §21 forbids a
   declaration from having planning authority; this is the mirror image, and it
   is not a declaration at all.
2. **Its response schema is the same six-key contract** (`summary`, `issues`,
   `patch_candidate`, `patch_plan`, `confidence`, `needs_escalation`) with no
   declaration field. Even a post-application turn would have nothing to read.
3. **It drives a different engine.** `run_self_correct_loop` uses
   `core.executor.Executor` directly and never reaches
   `run_patch_plan_with_artifacts`, so it is not on the CHECK.LIVE.1B boundary.
   The patch-plan branch of `maybe_run_auto_patch` returns before the loop can
   start, so the two paths are mutually exclusive within one run.

### 2.3 Does the worker remain active after application?

No. For the external CLI worker (`scripts/run_subagent_handoff.py`), the
subprocess runs to completion inside a throwaway clone, and only the files it
left behind survive. The plan is applied much later, from disk, by
`core/worker_runs.py` — a different module, in a different process, with no
live worker to ask. For in-process paths the model client is a stateless
request/response call.

## 3. Every candidate source, and why each fails

| Candidate | Where | Disqualified by |
|---|---|---|
| `patch_plan` / `patch_candidate` | the model response | §5 — it *is* `PatchPlan.operations` |
| `issues[].file` | the model response | a diagnosis of a problem, not a declared change; reading it as one infers a declaration from a field name (§3) |
| `ExecutionResult.target_file` / `.applied_patch` | `core/executor.py:66` | constructed from the patch dict handed in (§5) |
| `worker_run.json` | `scripts/run_subagent_handoff.py:184` | a subprocess process record — `dry_run`, `exit_code`, `timed_out`, `duration_sec`, `command`, `error`. Not one field about the repository. `error` is set by the *runner*, so it cannot stand in for §15's worker-declared status |
| `proposal.md` | the external worker's output | prose (§6) |
| `_extract_claimed_changed_files` | `core/worker_result_review.py:406` | a regex over prose (§6), and already labelled untrusted by its own module |
| `sleeping_consultant` `likely_files` | the dream planning pass | see §3.1 below |
| `commander_*` `changed_files` | `core/commander_run_contract.py` etc. | human-authored task scope in a report-only track that never executes; not worker output |
| `expected_changed_files` | benchmark case metadata | authored by the benchmark, not the worker |

### 3.1 The near miss — `likely_files`

`core/sleeping_consultant.py :: _generate_plan_analysis` is the strongest
candidate and deserves its own record, because it is the one a future reader is
most likely to mistake for outcome B. It genuinely is:

- a **separate** model invocation from the patch-drafting one;
- **already running today** in `patch_if_safe` dream mode, so wiring it would
  add no model call;
- **structured**, returning a `likely_files` array of repo-relative paths;
- **not derived** from the patch plan — it runs before the plan exists.

It still does not qualify, on two independent grounds:

1. **Semantics.** The field asks which files are *relevant to the problem*, in a
   pass whose own prompt says "Do not write any code patch." "Files that may be
   involved" is not "files I intend to change." Treating it as intent would be
   inferring a declaration from a field name — exactly what §3 rules out, and
   exactly the kind of manufactured outcome §1 forbids.
2. **Channel.** It reaches Python through `extract_json_block`, which regex-
   matches ```` ```json ```` fences and then scans for balanced braces in
   free-form model prose (`core/json_utils.py:45`). §6 names "JSON extraction
   from free-form prose" as a forbidden source in as many words.

`test_the_nearest_near_miss_is_a_relevance_hypothesis_not_an_intent` pins both
facts so the near miss cannot quietly become a wired source later.

### 3.2 There is no structured-output mode anywhere on the patch path

`agents/gemini_client.py` calls `client.models.generate_content(...)` with
`GenerateContentConfig(temperature=0.0)` — no `response_schema`, no
`response_mime_type`. `agents/ollama_client.py` posts `{model, prompt, stream,
options}` — no `format`. `agents/deepseek_client.py` likewise. Every worker
output in this repository is prose that is scraped afterwards.

The only schema-validated model JSON in the codebase is
`core/semantic_waiter_adapter.py`, which is intake-side — it interprets the
*user's request* — and is architecturally upstream of and disconnected from
patch execution.

## 4. Why the answer is not "add the field"

The brief's §4 invariant is `model_calls_after = model_calls_before`, and §22
allows a declaration emitted as a *separate field of the same model response*.
So a natural next thought is: add a `declared_changes` field to
`PATCH_RESPONSE_SCHEMA` and read it alongside `patch_plan`.

That is a **worker-protocol change**, and it is out of scope here by
construction. It would touch `core/prompter.py`, `core/control_engine.py`,
`patching/patch_gates.py`, `core/pipeline.py` and `agents/` — every one of which
CHECK.LIVE.1, CHECK.LIVE.1B and this phase all place in `forbidden_files`.
WORKER.DECL.1 was scoped to *qualify and wire an existing source*, not to create
one. Recording that no such source exists is the deliverable.

It is also worth being precise about what that future field would and would not
buy, because §22 and §23 matter here:

- A `declared_changes` field emitted in the same model response as `patch_plan`
  would be an **`independently_declared_channel`**, not **independent
  evidence**. Two fields of one model invocation can measure *internal output
  consistency*; they cannot corroborate each other. That distinction must not
  leak into EVIDENCE.2's independence semantics.
- Because the last model turn is pre-application, such a field would be
  `pre_execution_worker_intent` — never `post_execution_completion`. Genuine
  completion reporting needs a worker that is still alive after the patch lands
  and is asked to report, which this architecture does not have and which §4
  forbids creating with an extra call.

## 5. What this phase changed

| File | Change |
|---|---|
| `docs/designs/2026-08-28-native-worker-declaration-source-qualification.md` | this document (new) |
| `tests/test_native_worker_declaration_qualification.py` | the qualification evidence suite (new, 13 tests) |
| `core/phase_registry.py` | `"WORKER"` added to `PHASE_ID_PREFIXES` |
| `docs/roadmap/phase_registry.json` | `WORKER.DECL.1` registered |
| `tests/test_phase_registry.py` | seed counts and a WORKER.DECL.1 registration test |
| `tests/test_phase_picker.py` | seed bucket counts |

**No production module was modified.** `core/live_worker_declaration.py`,
`core/live_worker_report.py`, `core/post_run_reconciliation_shadow.py` and
`core/run_lifecycle.py` are byte-identical to their CHECK.LIVE.1B state.

## 6. The evidence suite

`tests/test_native_worker_declaration_qualification.py` deliberately does not
re-test CHECK.LIVE.1B's seam behaviour, which its own 1,500-line suite already
owns. It pins the four facts behind the classification:

**There is no declaration field to read**
- `test_the_patch_response_contract_declares_operations_and_nothing_else` — the
  writer contract's six keys, and no declaration token among them.
- `test_no_production_response_contract_asks_a_worker_to_declare_its_changes` —
  every string literal in production that specifies a patch response
  (`prompter.py`, `control_engine.py`, `patch_gates.py`,
  `run_patch_proposal_queue.py`), found structurally rather than by location.
- `test_the_nearest_near_miss_is_a_relevance_hypothesis_not_an_intent` — §3.1.
- `test_the_external_worker_output_contract_is_prose_plus_the_patch_plan` — the
  runner directive asks for exactly `proposal.md` and `patch_plan.json`.
- `test_the_worker_run_record_is_a_process_record_not_a_self_report` — the
  twelve-key process record, asserted exactly.

**Every model invocation precedes patch application**
- `test_no_apply_path_reaches_a_model_after_applying_its_patch_plan` — §2.1.
- `test_the_only_post_apply_model_turn_drives_a_different_engine` — §2.2.
- `test_no_worker_stays_alive_across_the_apply_boundary` — §2.3.

**Nothing populates the seam**
- `test_no_production_caller_supplies_a_worker_declaration` — no call site
  passes `worker_declaration=`.
- `test_the_parsed_model_response_never_reaches_the_declaration_seam` —
  `control_result` carries the parsed model payload into the run lifecycle,
  where it is written to the replay bundle and read by nothing else. It is
  never passed to `LiveExecutionObservation`, so prose-extracted JSON cannot
  become a typed declaration by the back door.
- `test_a_live_production_run_reports_a_legacy_plan_derived_declaration` — a
  real apply over a real temporary repository with the observer on.

**Nothing moved**
- `test_a_legacy_declaration_receipt_claims_no_measurable_fidelity` — §17: the
  receipt serialises no truthy `*fidelity*` claim, and no honesty or trust
  score, for a plan-derived record.
- `test_the_qualification_changed_no_authoritative_run_behaviour` — two
  identical runs, observed and unobserved: same success, same applied ops in the
  same order, same diffs, same worktree; the observed run gains only the
  existing `RESULT_METADATA_KEYS`.

Two of these were checked to *bite* rather than pass vacuously: a throwaway
module that both passed `worker_declaration=` and called a model after applying
made exactly the two intended tests fail, and was then removed.

### 6.1 Known limitation of the ordering test

The call graph is name-based, so it merges same-named functions across modules.
That over-approximates edges — it can only produce false failures, never false
passes. Its one real blind spot is dynamic dispatch: `run_self_correct_loop`
receives `re_patch_fn` as a parameter, so no name-based analysis can follow it.
That single case is therefore pinned directly by
`test_the_only_post_apply_model_turn_drives_a_different_engine` rather than
being left to the graph.

## 7. Deltas

| Delta | Result | How |
|---|---|---|
| Model calls | unchanged (zero added) | no production module changed; the suite calls no client |
| Validation executions | unchanged | no plan in the suite requests validation; the apply engine is untouched |
| Repository traversal | unchanged | qualification is static AST work plus one bounded live run |
| Patch applications, order, payload | unchanged | asserted by `test_the_qualification_changed_no_authoritative_run_behaviour` |
| Network | unchanged (none) | no client, no socket |
| Latency | not applicable | there is no native producer to measure |
| Authority | unchanged | no producer, no path, no widening |

## 8. Persistence and replay

Nothing new is persisted. `worker_declaration_source` and
`worker_declaration_invalid` already ride inside the existing
`post_run_reconciliation_shadow.json` receipt that CHECK.LIVE.1 introduced and
CHECK.LIVE.1B extended, and `load_shadow_post_run_check` already defaults both
for older bundles. All three generations stay readable:

- pre-CHECK.LIVE.1 bundles: no receipt at all → readable;
- CHECK.LIVE.1 receipts: no declaration keys → defaulted to
  `None` / `False` → readable;
- CHECK.LIVE.1B receipts: `legacy_plan_derived` → readable.

WORKER.DECL.1 adds no fourth shape.

## 9. Dogfood

The existing shadow summary already answers the adoption question this phase was
meant to inform. `summarize_shadow_post_run_checks` tallies
`worker_declaration_source_counts` and `worker_declaration_invalid_runs`, and
every receipt carries `independent_worker_declaration_missing`. Under this
phase's outcome the honest answer those counters give is a single bucket:

```json
{"worker_declaration_source_counts": {"legacy_plan_derived": N},
 "worker_declaration_invalid_runs": 0}
```

No confidence value, no trust score, no worker-honesty score exists anywhere in
the receipt — asserted by `test_a_legacy_declaration_receipt_claims_no_measurable_fidelity`.

## 10. What a future phase must do first

The vocabulary gaps below are **not defects today**, because no native producer
exists to expose them. They become blocking the moment one does, so they are
recorded here rather than fixed speculatively:

1. **`declaration_stage` accepts only `"completed"`.**
   `core/live_worker_declaration.py` hard-codes
   `DECLARATION_STAGE_COMPLETED` as the sole legal stage. Since this
   architecture's last model turn is pre-application, the first realistic
   producer will be a *pre-execution intent* — and today's contract would force
   it to be labelled a completion. That is exactly the §2 confusion between
   "I intend to modify A.py" and "I believe I modified A.py". A
   `pre_execution_intent` stage must be added **before** any producer is wired.
2. **`DECLARATION_SOURCE_INDEPENDENT` serialises as
   `"independent_worker_declaration"`,** which carries no temporal stage — the
   vague value §8 warns against. It should become
   `pre_execution_worker_intent` / `post_execution_worker_declaration`.
3. **Measurability flags do not exist.** `self_report_fidelity_measurable` and
   `intent_fidelity_measurable` (§9) should be derived read-only properties of
   the provenance value, never caller-settable, so a legacy record cannot claim
   a fidelity it did not measure.
4. **`native_worker_declaration_invalid` telemetry** (§18) is present today as
   `worker_declaration_invalid` and is adequate; only the name would change.

## 11. Answers to the required questions

- **Does a genuine post-execution worker declaration already exist?** No.
- **If not, does an independent pre-execution intent declaration exist?** No.
  The nearest candidate, `likely_files`, is a relevance hypothesis reached
  through prose-JSON extraction (§3.1).
- **Is the declaration derived from PatchPlan paths?** There is no native
  declaration. The legacy fallback *is* plan-derived and says so explicitly.
- **Is it derived from observed filesystem changes?** No — nothing is.
- **Does it require another model call?** A genuine one would require a worker
  protocol change; a genuine *completion* report would additionally require a
  post-application model turn. Neither was made.
- **Can it authorize a path?** No. `worker_declaration_authority()` grants only
  `worker_self_report_authority`; `ExecutionAuthorization` is upstream and
  independent.
- **Can it change patch operations?** No. The seam is read after
  `apply_patch_plan` returns.
- **Can intent be mistaken for completion?** Not in production, because no
  declaration is produced. It *could* be by a future producer, because the
  contract accepts only `"completed"` — see §10.1.
- **Is self-report fidelity genuinely measurable?** No.
- **Is intent fidelity measurable?** No.
- **Are two fields from the same model invocation independent evidence?** No.
  That would be an `independently_declared_channel` measuring internal output
  consistency, never independent corroboration (§4).
- **Is prose parsed?** No. This phase adds no parser, and
  `core/live_worker_report.py` still contains no `re` import.
- **Is validation rerun?** No.
- **Is traversal added?** No.
- **Does a malformed declaration alter the authoritative run outcome?** No —
  CHECK.LIVE.1B's fail-closed fallback is unchanged and the checker stays
  shadow-only.
- **Is CHECK.2 live?** No.
- **Is any checker authoritative?** No. `authoritative_effect` remains a
  constant `False` property that no caller can set.

## 12. Registry

`WORKER.DECL.1` is registered on a new `WORKER` track. The track is new because
the phase id the brief prescribes (`WORKER.DECL.1`) determines the prefix, and
`core/phase_registry.py` warns on an unrecognised one. Adding it is a one-line
change to `PHASE_ID_PREFIXES`, in the same shape as the six prefixes added
immediately before it (`INPUT`, `WAITER`, `ACQUIRE`, `EVIDENCE`, `CLAIM`,
`SYNTHESIS`), so it causes no registry disruption. Prerequisite: `CHECK.LIVE.1B`.
`model_calls_allowed`, `network_allowed`, `writes_real_repo` and `merge_allowed`
are all false; `human_approval_required` is true.

## 13. CHECK.LIVE.2 readiness

CHECK.LIVE.2 is **not** started here and gains nothing from this phase except a
correction: it must not assume self-report fidelity is measurable, because it is
not. Whatever CHECK.LIVE.2 wires, its worker-side inputs remain
`legacy_plan_derived` until a worker-protocol phase lands.

**Recommended next phase:** `WORKER.DECL.2 — Pre-Execution Intent Declaration
Channel`. Scope: add a `declared_changes` field to the patch response contract
(`core/prompter.py`, `core/control_engine.py`, `patching/patch_gates.py`) as a
field the model emits *beside* `patch_plan`; add the `pre_execution_intent`
stage, the staged provenance vocabulary and the derived measurability flags from
§10; wire it through the existing CHECK.LIVE.1B seam from `core/pipeline.py`.
That phase must own the `forbidden_files` relaxation this one refused to take,
and must label what it produces `independently_declared_channel` — never
`independent_evidence`.
