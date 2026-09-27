# WORKER.DECL.2A.2 — Live Strict Envelope Adoption Dogfood

**Status:** complete, observation-only, no production code changed
**Date:** 2026-08-30
**Depends on:** WORKER.DECL.2A.1 (complete, frozen), which depends on WORKER.DECL.2A.
Not WORKER.DECL.2B. Not CHECK.2.

## The one number this phase existed to produce

[WORKER.DECL.2A.1](2026-08-30-strict-envelope-emission-adoption-experiment.md)
shipped the ability to *ask* a real patch-producing call for one bounded JSON
object, and then said, in its own known limitations:

> **No live provider data is included in this report.** Every number here comes
> from fixtures and fakes. The experiment is *runnable* on real provider paths;
> it has not been *run* against a live provider in this phase.

So the question `can the existing patch-generation call be asked to conform?`
had a mechanism and no answer. This phase runs it and reports the answer.

It answers only that question. No production field was added, no production file
was edited, no production test was edited, the parser was not touched, authority
did not move, and `pre_execution_change_intent` is still `unknown_field`.

## What was run

Five runs of the **real** production entry point —
`scripts/run_patch_proposal_queue.py::main()`, which WORKER.DECL.2A.1 lists as
the **unconditionally enrolled** patch-producing site because its own prompt
already fixes `patch_candidate: null` and asks for a `patch_plan`, so the strict
block overrides no patch rule.

| | |
|---|---|
| Provider family | `google` |
| Model | `gemma-4-31b-it` (`run_gemini_request_2`'s first reviewer model) |
| Temperature | `0.0`, both arms, unchanged |
| Cases | `python_multifile_root_cause`, `python_off_by_one_pagination` |
| Repository under patch | a `shutil.copytree` of the case's `buggy_repo` into a `TemporaryDirectory` |
| Real repository writes | none |
| Approval gate | untouched: each item still required `human_approved_for_proposal: true` |

§14 asked for a bounded, disposable, safe target that still exercises the actual
patch-producing invocation. The proposal queue is exactly that by construction:
it copies a benchmark case into a temp directory, applies there, and runs the
case's own whitelisted `validation_command` there. Nothing was weakened to
obtain telemetry — the queue's existing gates (`human_approved_for_proposal`,
the `_is_inside` containment checks on the source report and case file, the
`ALLOWED_VALIDATION_TOOLS` whitelist, `_metadata_path_issue`) all ran as shipped.

The operator inputs — one `benchmark_report_*.json` and one
`background_dream_plan_*.json` under the gitignored `.agent/` tree — are the
queue's ordinary input data, authored by the operator, naming existing benchmark
cases. They assert no benchmark outcome.

### The harness is not in the repository

The runs were driven by a harness that lives **outside** the checkout, in the
session scratchpad. It installs two **pass-through** spies and then calls the
production `main()`:

| Spy | What it records | What it changes |
|---|---|---|
| `google.genai.models.Models.generate_content` | model, whether the config carried `response_mime_type`, whether the prompt on the wire carried the strict block, sha256 of prompt and of response text | nothing — calls the real method, returns its real result |
| `core.run_lifecycle.run_patch_plan_with_artifacts` | the `strict_envelope_emission` observation the production site actually built; copies the bundle's bounded artifacts out of the temp repo before it is deleted | nothing — calls the real function, returns its real result |

Keeping it outside `scripts/` is deliberate. WORKER.DECL.2A.1 already owns the
offline classifier that belongs in the tree
(`scripts/strict_envelope_emission_baseline.py`); a second helper added here
would be a production file added by an observation phase, and could later drift
into a run path. The phase's `allowed_files` is therefore a design document, the
registry, and the two registration test files — nothing else.

## The observations

Every row is a real provider response. `strict_status`, `legacy_status` and
`agreement_status` come from WORKER.DECL.2A's frozen parser via
WORKER.DECL.2A.1's frozen `observe_strict_envelope_emission`; nothing in this
phase parses anything.

| Run | Case | Strategy | Calls | `response_mime_type` | Response | `strict_status` | `legacy_status` | Agreement |
|---|---|---|---|---|---|---|---|---|
| 1 | multifile | `legacy_prompt` | 1 | — | 398 ch, `` ` `` … `` ` `` | `surrounding_prose_rejected` | `legacy_plan_available` | `not_comparable` |
| 2 | multifile | `strict_prompt` | 1 | — | 343 ch, `{` … `}` | **`valid`** | `legacy_plan_available` | `agreed` |
| 3 | multifile | `provider_native_json` | 1 | `application/json` | 272 ch, `{` … `}` | **`valid`** | `legacy_plan_available` | `agreed` |
| 4 | pagination | `strict_prompt` | 1 | — | 361 ch, `{` … `}` | **`valid`** | `legacy_plan_available` | `agreed` |
| 5 | pagination | `provider_native_json` | 1 | `application/json` | 421 ch, `{` … `}` | **`valid`** | `legacy_plan_available` | `agreed` |

Each valid parse carried a distinct `envelope_fingerprint`
(`9ea5a4f8…`, `9c0cd41f…`, `a4c9e83c…`, `56611a5b…`), so no two rows are the
same response counted twice.

The frozen `summarize_strict_envelope_emission_observations` over all five,
persisted to `.agent/roadmap/strict_emission_dogfood.json`:

```json
"records": 5, "strict_valid": 4, "legacy_only": 1,
"invalid_both": 0, "semantic_mismatch": 0,
"strict_status_by_transport_strategy": {
  "legacy_prompt":        {"surrounding_prose_rejected": 1},
  "provider_native_json": {"valid": 2},
  "strict_prompt":        {"valid": 2}
}
```

§17 asked for raw observations and no adoption rate. These are counts over five
runs; nothing here is a compliance percentage, and nothing in the code reads
them.

### The control is not decoration

Run 1 is what the site does today: the model returned a fenced, four-key payload
(`summary`, `patch_candidate`, `patch_plan`, `needs_human_review`) whose first
and last characters are backticks. WORKER.DECL.2A predicted exactly this, and
WORKER.DECL.2A.1 measured exactly this from fixtures. It is now measured live.
The delta between row 1 and rows 2–5 is the phase's finding: **the same model,
same temperature, same site and same case emits prose-wrapped JSON when not
asked and a bare two-key object when asked.**

## §12 — proving these are live, and are what they claim

Four things had to be true of every reported observation. Each is checked, not
asserted.

**A real provider call occurred.** The boundary spy recorded a
`generate_content` return with non-empty text for all five runs. The pre-flight
run — identical in every respect except that the spy refused to send — produced
`AGENT_ERROR` text and `proposal_failed`, confirming the spy sits on the path
that actually reaches the network.

**A real enrolled patch-producing site was used.** The entry point was
`scripts.run_patch_proposal_queue.main()`; the lifecycle spy saw
`source="proposal_queue"`; the queue's own `summary.json` records
`status: proposal_validated` for the case.

**The strict emission flag and strategy were active.** For runs 2–5 the prompt
on the wire contained `[STRICT PATCH ENVELOPE - OUTPUT TRANSPORT ONLY]` and the
literal `"schema_version": "worker_decl_2a_patch_envelope_v1"`; for run 1 it did
not. For runs 3 and 5 the request config carried
`response_mime_type="application/json"`; for runs 1, 2 and 4 it was `None`.

**The observation came from that exact response.** For all five runs
`sha256(raw_model_response.txt) == sha256(the text the provider boundary
returned)`. For runs 2–5 the observation the production site handed the
lifecycle is **byte-identical** to the observation recomputed from that exact
recorded text with the frozen functions. No fixture is reported as live: the
`--dry-run` pre-flight is excluded from the table and from the summary.

### The arms differ by one thing

Within each case, `strict_prompt` and `provider_native_json` sent a
**byte-identical prompt** — same sha256, `95d99567…` for the multifile case and
`a2d83100…` for the pagination case. The only difference on the wire is the
media type. That is a clean transport comparison, and it is also a limit: native
JSON was never tested *without* the strict block, so this phase cannot say
whether the media type alone would produce a conforming envelope.

## §13 — model call accounting

**Additional calls caused by strict checking: zero.** The boundary spy counted
exactly **one** `generate_content` per run, in the control arm and in both
experimental arms alike. No formatting turn, no repair turn, no verifier turn,
no retry. Nothing branched on a strict status.

The five runs are five separate operator dogfood runs of one call each — not
calls inside one run. `run_gemini_request_2` does carry a pre-existing
reviewer-model fallback loop that would attempt `gemma-4-26b-a4b-it` if the first
model raised; it is not caused by strict checking, and it did not fire in any
live run. (It fired twice in the suppressed pre-flight, which is how we know the
counter sees it.)

## §6 — JSON transport succeeded *and* the contract held

The distinction the spec asked to keep explicit — *provider returned JSON* ≠
*`WorkerPatchEnvelope` valid* — did not have to be exercised as a failure here,
because both held. The legacy payload keys recorded for runs 2–5 are exactly
`["patch_plan", "schema_version"]`: the model returned the two-key envelope and
no extra field, so there was no unknown field for the parser to reject. Run 1
demonstrates the machinery in the other direction — legacy JSON was extracted
successfully (`legacy_plan_available`) from a response the strict parser
rejected outright.

**The parser was not touched.** `core/worker_patch_envelope.py` is unmodified
and in this phase's `forbidden_files`. Nothing about the live results was
inconvenient enough to tempt a relaxation, and the guard exists regardless.

## §7, §8 — legacy stayed authoritative with a valid strict parse in hand

This is the interesting half. In WORKER.DECL.2A and 2A.1 the guardrail was
easy to honour because the strict parse always failed. Here it succeeded four
times, and authority still did not move:

- the applied plan came from `extract_json_block` → `_patch_payload_to_plan`, as always;
- `apply_result.applied_ops` was **1** in every run, `rollback_performed` **false** in every run;
- `validation_ok` was **true** in all five;
- `authoritative_effect` is `False` in every persisted observation, structurally.

No strict failure could have failed a run either, since no producer site reads a
strict status — but in these five runs no strict failure occurred outside the
control, so §8 was not exercised live. That remains proven by test rather than
by traffic.

## §11 — what the replay bundle actually records, and one thing it does not

`strict_envelope_emission.json` was present in the replay bundle of exactly the
four flag-on runs and absent from the control's bundle — correct, because
`run_patch_plan_with_artifacts` writes it only under
`is_strict_envelope_emission_enabled()`. Its content is byte-identical to the
in-run observation, and it carries `transport_strategy`, `strict_status`,
`legacy_status`, `agreement_status` and `envelope_fingerprint`: everything §11
asked to be establishable. No raw-response persistence was added.

**But the bundle does not survive this site.** `create_replay_bundle` writes to
`<repo_path>/.agent/replays/…`, and at the proposal queue the `repo_path` *is*
the `TemporaryDirectory`, which is deleted when the item finishes. The durable
`apply_result.json` keeps a `replay_dir` pointing at a path that no longer
exists. The harness copied the artifacts out from inside the temp directory's
lifetime; an operator who simply sets the flag and runs the queue will find the
emission telemetry gone.

That is a finding about the enrolled site, not a defect this phase may fix:
changing where the queue's bundle lands is a change to a production run path.
It is recorded here so a later phase owning that path can decide.

A second, smaller observation from the same area: `run_patch_plan_with_artifacts`
catches `OSError` from `create_replay_bundle` and continues with `bundle = None`,
so a bundle can silently not exist. That is by design, and it means absence of
an emission artifact is not evidence the flag was off.

## §16 — the decision table

**Case A: `strict_prompt` valid, `provider_native_json` valid, legacy agreement
clean → the strict channel is empirically demonstrated.**

Both arms parsed `valid` on both cases, `semantic_mismatch` is 0, `invalid_both`
is 0, and the legacy path applied and validated in every run.

Per §16 this is recorded descriptively. Nothing routes on it: no code reads the
distribution, `PATCH_PLAN_DECLARED_STYLES` is unchanged, the flag still defaults
to `legacy_prompt`, and an unrecognised value still resolves to `legacy_prompt`.

§22 warns against selecting A because infrastructure tests pass. That is not
what happened: four live provider responses parsed valid under the frozen
parser, and the control run on the same model and case did not.

## The registry finding

This is the **first phase in the roadmap to declare a model call.** All 138
prior phases are `local_only` with `model_calls_allowed: false`. WORKER.DECL.2A.2
is `strong_model_requires_approval` with `model_calls_allowed: true`, which is
the only combination `core/phase_registry.py` permits for a phase that spends
provider calls, and which routes it to `human_approval_required` in the picker.

`network_allowed` stays `false`, because the validator rejects `true` outright
for every ROAD.1-managed phase. The registry's vocabulary expresses provider
traffic through `model_calls_allowed` alone; the flag is **not** this phase
claiming it made no requests. Saying so here is the honest handling — the
alternative was editing `core/phase_registry.py`, which would be weakening a
gate to make a report look tidy.

`test_seed_registry_is_conservative` asserted that *every* phase had
`model_calls_allowed: false`. Its intent — that no phase quietly grants itself
provider traffic — is preserved and now enforced more precisely: a phase may
declare model calls only alongside the approval budget tier and the human
approval gate, and every other phase must stay `local_only`. Both directions are
asserted.

The picker is otherwise undisturbed: `safe_to_prepare` stays 3, in the same
order, with the same top recommendation (`DOGFOOD.1B`). Only
`complete_or_history` moves 135 → 136.

## §21 — validation

Offline, with both `STRICT_WORKER_PATCH_ENVELOPE_EMISSION` and
`STRICT_WORKER_PATCH_ENVELOPE_SHADOW` unset. No live call was converted into a
test.

| Suite | Result |
|---|---|
| `test_strict_envelope_emission` + boundaries | pass |
| `test_worker_patch_envelope` + boundaries | pass |
| `test_native_worker_declaration_qualification` | pass |
| `test_live_worker_declaration` (CHECK.LIVE.1B) | pass |
| `test_post_run_reconciliation_shadow` + boundaries | pass |
| `test_run_lifecycle`, `test_replay_recorder`, `test_replay_lifecycle_integration` | pass |
| `test_proposal_queue_lesson_candidates`, `test_seed_lessons_from_proposals` | pass |
| `test_phase_registry`, `test_phase_picker` | pass |

### One flake, diagnosed and not this phase

The first combined run reported
`test_run_lifecycle.py::test_lifecycle_success_writes_replay_bundle` failing with
`KeyError: 'replay_dir'` — meaning `create_replay_bundle` raised `OSError` and
the lifecycle degraded to `bundle = None`. It did not reproduce: the identical
command passed on rerun, and the file passed standalone and in four further
pairings. `pytest.ini` pins a **fixed** `--basetemp=tmp_tests` with
`tmp_path_retention_policy = failed`, so leftover directories from a previous
session are recreated and cleaned at session start; on Windows that races with
directory creation under the same path. It is a harness-configuration flake in
files this phase does not touch, and this phase changed no code that could cause
it.

## What was deliberately not done

| Asked for | Status |
|---|---|
| `change_intent` / `declared_changes` | not added; still `unknown_field` |
| Parser changes | none; `core/worker_patch_envelope.py` untouched and forbidden |
| Repair, retry, formatting or verifier calls | none; one call per run, measured |
| Promoting strict parsing to authority | not done; `authoritative_effect` `False` in every record |
| Widening the dream or pipeline path for data | not done; only the already-enrolled site ran |
| Gemini `response_schema` (§19) | not added; native JSON returned the right shape, so the follow-up it would have justified is not needed |
| Retrying until a valid envelope appeared (§18) | never needed; no run failed, no run was repeated for its result |
| CHECK.1 / CHECK.2 / CHECK.LIVE.* | untouched, unimported, unpromoted |

The second case was added as **replication, not retry**: both arms had already
returned `valid` on the first case, so a second case could only weaken the
finding. Every run performed is reported.

## Known limitations

1. **One model, one provider family, one site.** `gemma-4-31b-it` via `google`
   at the proposal queue. `ollama_http`, `ollama_chat` and DeepSeek remain
   proven by test rather than by traffic, and `gemini-*` models were never
   exercised — `run_gemini_request_2` uses the hardcoded reviewer list, not
   `config.MODELS`.
2. **Five runs.** Enough to answer "can it conform?" — not enough to characterise
   how often it does. No rate is published, on purpose.
3. **Native JSON was never tested alone.** Both native runs also carried the
   strict prompt block, by WORKER.DECL.2A.1's design.
4. **§8 was not exercised live.** No experimental run produced a strict
   rejection, so "a strict failure cannot fail a run" remains a test-proven
   claim here.
5. **Emission telemetry does not survive the queue site**, as described above.
6. **Patch quality is unmeasured.** `validation_ok: true` in all five runs is
   execution context only. Five runs across two cases and one model are not a
   controlled A/B, and no claim is made that either arm produces better patches.
7. **The unenrolled sites are unchanged.** The pipeline still needs a `vibe`
   style; the dream site still carries the pre-existing `safe_minimal`
   contradiction WORKER.DECL.2A.1 documented.
8. **`patch_candidate`-only responses remain invisible**, inherited from 2A.

## Files changed

| File | Change |
|---|---|
| `docs/designs/2026-08-30-live-strict-envelope-adoption-dogfood.md` | new — this document |
| `docs/roadmap/phase_registry.json` | one appended phase; every prior phase byte-identical |
| `tests/test_phase_registry.py` | registration tests; phase count, WORKER track count, and the conservatism invariant refined |
| `tests/test_phase_picker.py` | registration tests; `complete_or_history` 135 → 136 |

No file under `core/`, `agents/`, `scripts/`, `patching/`, `policy/` or `web/`
was modified, and no production test was modified.

Artifact: `.agent/roadmap/strict_emission_dogfood.json` (gitignored) — the five
per-run records with their proof chain, plus the frozen summary.

## Recommendation

**A — ready for WORKER.DECL.2B.**

The question 2B was waiting on was whether the two-field envelope channel
survives live production before a third semantic field is added to it. It does:
the real production invocation, asked for one bounded JSON object, returned one
bounded JSON object that the frozen parser accepted, under both transport
strategies, on both cases, with the legacy channel agreeing and the applied
patch unaffected.

The three alternatives are ruled out by the observations rather than by
preference. **B** (more adoption dogfood first) would be right if the result
were mixed; it is not, and §17 warns that more runs of the same single model
would buy a rate, not a fact. **C** (test provider-native schema enforcement
first) is what §19 reserves for native JSON returning the *wrong shape*; it
returned the right shape. **D** (revise the emission protocol) is for a channel
that failed; nothing failed.

Two qualifications belong on that recommendation:

- The evidence is **one model on one site**. It demonstrates the channel is
  usable, not that it is universal. WORKER.DECL.2B should keep
  `pre_execution_change_intent` behind the same opt-in flag and the same
  shadow-only, non-authoritative posture, so a provider that conforms less well
  degrades to a rejected observation rather than a failed run.
- Adding a third key is a **new** compliance question, not a settled one. These
  runs show the model reproduces a two-key contract it was shown; they do not
  show it will populate a semantic field truthfully. 2B's own dogfood should
  repeat this measurement rather than inherit this result — and
  [WORKER.DECL.1's qualification](2026-08-28-native-worker-declaration-source-qualification.md)
  still blocks treating two fields of one response as independent evidence.
