# WORKER.DECL.2A — Strict Structured Patch Response Envelope

**Status:** complete, shadow-only, default off
**Date:** 2026-08-29
**Depends on:** WORKER.DECL.1 (complete). Not CHECK.2. Not CHECK.LIVE.2.

## The problem this phase closes

WORKER.DECL.1 ended with `WORKER_DECL_1_SOURCE_UNAVAILABLE` and named the reason
precisely: there is nowhere trustworthy to put a typed worker field. Every
patch-producing response in this repository is a free-form string, and the patch
plan is recovered from it by [`extract_json_block`](../../core/json_utils.py:45),
which regex-matches ` ```json ` fences and then walks the text brace by brace
looking for the first balanced object.

That is not a protocol. It is a salvage operation, and it succeeds on:

```text
Sure! Here is the patch:
```json
{ ... }
```
Let me know if you'd like me to adjust anything.
```

A channel that accepts *that* cannot carry `pre_execution_intent`, because
"a JSON object appeared somewhere in the answer" gives you no guarantee about
what else the answer contained, how many objects there were, or which one you
got. WORKER.DECL.2A builds the channel first. WORKER.DECL.2B puts the field in
it.

## The contract

```text
model response
    ↓
the entire non-whitespace text decodes as exactly one JSON object
    ↓
WorkerPatchEnvelope { schema_version, patch_plan }
    ↓
the existing patch-plan semantics, unchanged
```

`schema_version` must be `worker_decl_2a_patch_envelope_v1`. `patch_plan` holds
the **existing** operation mappings — this phase creates no `PatchPlanV2` and
reinterprets no operation. `WorkerPatchEnvelope.patch_plan_operations()` hands
the very same dicts to the very same `apply_patch_plan`.

Deliberately absent: `worker_metadata`, `declared_changes`, confidence,
reasoning, validation results, post-run claims. WORKER.DECL.1 found no genuinely
structured worker metadata to carry; adding a slot for it here would be exactly
the premature move this phase exists to avoid. A response carrying
`declared_changes` is rejected as `unknown_field` today, by test.

### §3 provider precheck

Every path capable of feeding patch-plan execution, traced rather than assumed:

| Provider path | Transport | Schema | Provider-native structured output | Enabled by caller | Bare string | Fences expected | `extract_json_block` |
|---|---|---|---|---|---|---|---|
| [`gemini_client.run_gemini_request`](../../agents/gemini_client.py:34) | `client.models.generate_content` | none in the request | `google-genai` supports `response_schema`/`response_mime_type` | **no** — config is `GenerateContentConfig(temperature=0.0)` only | yes (`response.text`) | yes | yes, at the caller |
| [`gemini_client.run_gemini_request_2`](../../agents/gemini_client.py:115) | same, reviewer models | none | same | **no** | yes | yes | yes |
| [`ollama_client.OllamaClient.generate`](../../agents/ollama_client.py:40) | `POST /api/generate` | `{model, prompt, stream, options}` | Ollama supports `format: "json"` | **no** — `format` is never sent | yes (`result["response"]`) | yes | via `_extract_json_object` regex |
| [`deepseek_client.run_deepseek_review`](../../agents/deepseek_client.py:18) | `ollama.chat` | none | same | **no** | yes (`response["message"]["content"]`) | yes | yes, at the caller |
| worker CLI subprocess ([`run_subagent_handoff`](../../scripts/run_subagent_handoff.py)) | files on disk | `proposal.md` + `patch_plan.json` | n/a | n/a | n/a (file) | n/a | no — reads `patch_plan.json` directly |

The response *contract* is the same six keys everywhere
(`summary`, `issues`, `patch_candidate`, `patch_plan`, `confidence`,
`needs_escalation`), defined in [`prompter.py`](../../core/prompter.py),
[`control_engine.py`](../../core/control_engine.py),
[`patch_gates.py`](../../patching/patch_gates.py) and
[`run_patch_proposal_queue.py`](../../scripts/run_patch_proposal_queue.py).

**No patch-path provider currently enables a structured-output mode**, which is
why §4 is right that the common contract must be a text-transported one-object
protocol rather than a proprietary API. Two providers *could* offer one; a
future provider adapter may use it, but the envelope semantics must not depend
on it, and `core/worker_patch_envelope.py` imports no provider SDK (asserted).

## What "strict" means, exactly

`parse_strict_worker_patch_envelope` does one decode of the whole stripped text:

```python
decoded = json.loads(response_text.strip())
```

There is no `re` import in the module, no fence reader, no brace scanner, no
first-object search, no Markdown cleanup — the boundary suite asserts each
absence by name, and a probe that added `import re` made it fail.

### Classifying a rejection without recovering anything

`invalid_json` and `surrounding_prose_rejected` are separate statuses (§12), so
a rejection has to be classified. `_rejection_status_for_undecodable` does it
using only the standard decoder's own report:

- text does not begin with `{` → `surrounding_prose_rejected`
- text begins with `{` and `JSONDecoder().raw_decode` also fails → `invalid_json`
- text begins with `{` and `raw_decode` succeeds → there is content *after* a
  complete object → `surrounding_prose_rejected`

That last branch is what makes "take the first one" structurally impossible: the
helper's every `return` is a bounded status name, so no value decoded there is
reachable by any caller. A boundary test asserts `raw_decode` appears exactly
once, inside that helper, and that all of its returns are bare names.

One honest imprecision: a response that is prose *throughout*, with no object at
all, also reports `surrounding_prose_rejected`. Telling it apart from prose
*around* an object would mean scanning for an object somewhere inside — the very
recovery this phase refuses. The compatibility record's `legacy_available`
already answers "would the legacy extractor have found something here?", so
nothing is lost.

### Bounds, and never truncation (§10, §11, §35)

| Bound | Value | Source |
|---|---|---|
| whole response | 1,000,000 chars | envelope-level, checked before any decode |
| operations | 256 | equal to CHECK.1's `MAX_DECLARED_CHANGES`, pinned by test |
| per-operation payload | 131,072 chars | envelope-level, per snippet / file body |
| path | 1,024 chars + `is_safe_repository_relative_path` | reused from `repository_path_policy` |

Every one rejects the **whole** envelope. The parser contains no slice of its
input and no truncation helper — asserted statically, because a silently trimmed
operation list or snippet would change what a patch means.

The operation ceiling is kept equal to `MAX_DECLARED_CHANGES` **by test rather
than by import**: a plan with more operations than CHECK.1 can represent as
declared changes is already unrepresentable downstream, so accepting one here
would only defer the rejection — but the worker protocol is upstream of every
checker and must not import one.

### Paths

Strict means strict: a path is accepted as written or not at all. `./main.py`,
`sub\windows.py`, `../outside.py`, `/etc/passwd` and `""` are all rejected. The
legacy path may still repair a spelling; this channel never does.

The explicit leading-separator guard is the same one
[`live_worker_declaration.py`](../../core/live_worker_declaration.py) carries:
`Path("/etc/passwd").is_absolute()` is **False** on Windows, because it has no
drive letter, so the shared lexical policy alone would let a rooted POSIX path
through.

### Unknown and authority-shaped keys (§8, §9, §34)

Top-level keys are the allow-list `{schema_version, patch_plan}`; operation keys
are per-op allow-lists mirroring what the executor reads (`file` stays in, since
it is the existing path alias the executor already honours). Everything else is
`unknown_field`.

`FORBIDDEN_AUTHORITY_KEYS` — `write_authority`, `write_allowed`,
`reviewer_approved`, `human_approved`, `merge_allowed`, `validation_passed`,
`secret_authority` and siblings — are rejected **by name** at both levels. They
would already fall out of the allow-list; naming them makes the refusal
deliberate and testable rather than incidental. A boundary test additionally
asserts no allow-listed key name contains an authority, approval or merge word.

## Semantic identity (§17, §26, §36)

`canonical_patch_plan_identity` reduces a plan to what the executor acts on:

- **order is preserved** — operations apply sequentially and `replace_snippet`
  rewrites only the first occurrence, so a reordered plan is a different plan;
- **the path alias resolves the executor's way** — `relative_path` first, then
  `file`, so two spellings of one operation reduce to one identity, and a plan
  carrying both keys identifies as `relative_path` does;
- **payloads are digested**, so a changed snippet changes the identity;
- **an uncanonical path is represented by a digest of what was written**, which
  keeps distinct unusable paths distinct without copying model text into a
  record;
- **an unsupported operation contributes its whole shape**, so two different
  unknown operations never collide.

JSON key order and insignificant whitespace cannot change the result. No clock,
latency or provider response id enters the fingerprint, so a replayed response
fingerprints identically.

## One response, two parsers (§14)

`compare_strict_and_legacy(response_text, legacy_payload)` takes the response the
run **already has** and the legacy payload it **already produced**. The model is
not called; the legacy extractor is not re-run; the module imports neither
`core.json_utils` nor any provider SDK.

| Field | Meaning |
|---|---|
| `strict_status` | one of the eight parse statuses |
| `strict_available` / `legacy_available` | did each channel yield a patch plan |
| `provenance` | `strict_worker_patch_envelope` / `legacy_extracted_json` / `no_patch_payload` |
| `semantic_agreement` | `agreed` / `strict_legacy_semantic_mismatch` / `not_comparable` |
| `strict_patch_plan_identity`, `legacy_patch_plan_identity` | canonical identities |
| `envelope_fingerprint` | present only for a valid strict parse |
| `unknown_keys` | bounded rejected key names, never their values |

§13 is enforced structurally: `provenance == strict_worker_patch_envelope`
requires `strict_available`, checked in `__post_init__`. A legacy payload
recovered from prose can never be labelled strict.

A payload carrying only a `patch_candidate` counts as **no plan** for this
measurement. Converting a candidate into a plan is the legacy path's own
business; doing it here would be this module reinterpreting a patch.

## Integration — shadow, and the legacy payload stays authoritative

```text
worker response ──┬── extract_json_block ──→ patch plan ──→ apply  (unchanged, authoritative)
                  │
                  └── parse_strict_worker_patch_envelope ──→ compatibility record
                                                                   ↓
                                              worker_patch_envelope.json in the replay bundle
```

Three producer sites hold both the raw response and the legacy payload already,
so measurement costs nothing structural:

| Site | Provider | Reaches |
|---|---|---|
| [`pipeline.finalize_answer`](../../core/pipeline.py:426) | Gemini | `maybe_run_auto_patch` → apply |
| [`sleeping_consultant._run_patch_item`](../../core/sleeping_consultant.py:571) | Gemini (dream) | apply |
| [`run_patch_proposal_queue._process_item`](../../scripts/run_patch_proposal_queue.py:615) | Gemini (queue) | apply |

Each computes the record only when the flag is on, through
`safe_compare_strict_and_legacy` (the guarded entry point — a measurement
failure returns `None` rather than escaping into the run), and passes it to
`run_patch_plan_with_artifacts(worker_patch_response=...)`.

The lifecycle argument **defaults to `None`**, the persistence branch is guarded
by the default-off flag, and only an already-typed
`WorkerPatchResponseCompatibility` is written — a raw mapping is not laundered
into one. The record reaches exactly one sink: the additive replay artifact. No
branch downstream reads it back, and `result_metadata()` is untouched, so the
result dict gains no key.

## Deltas

| Delta | Result | How verified |
|---|---|---|
| Model calls (§21) | zero added | no provider SDK, no `agents` import, no repair/verifier/formatting call; measurement is a pure function of two already-held values |
| Patch applications, order, payload (§22) | identical | two runs, flag off vs on, same `applied_ops`, `diffs`, `rollback_performed`, worktree, and identical result key set |
| Validation executions (§23) | unchanged | the parser executes nothing; no validation import |
| Repository traversal (§24) | zero | no `pathlib`, no `open`, no `walk`/`rglob`/`iterdir` — asserted statically |
| Network (§25) | zero | no `requests`/`httpx`/`urllib`/`socket` import |
| Prompt / temperature / provider (§19) | unchanged | no prompt file is in `allowed_files`; see below |
| Authority (§9) | unchanged | authority keys rejected by name; no allow-listed key names one |

The measurement never selects a patch: a live test records a deliberate
`strict_legacy_semantic_mismatch` and asserts the caller's plan is still exactly
what ran.

## §19 — why no prompt change here

§19 permits testing a minimal instruction asking the same model call for exactly
one JSON object, behind the flag. This phase does not do it, on §2's own logic:
*first measure compatibility*. Changing the request and the parser in one step
would conflate the transport-format experiment with a prompt experiment, and
§19 itself forbids bundling it with reasoning, temperature, provider or patch-
semantic changes.

The repository already has the exact wording pattern —
[`SCOUT_PROMPT`](../../core/prompter.py) says *"Return ONLY valid JSON. Do NOT
use Markdown. Do NOT wrap the JSON in ```json or ``` fences. The first character
of your response MUST be `{`"* — so a follow-up can apply it to the patch
contract with a one-paragraph change and re-read the same counters. That is the
cheapest possible next experiment, and it is now measurable.

## §18 — the expected result today

Current providers emit fenced or prose-wrapped JSON, so a dogfood run today
should report mostly `surrounding_prose_rejected` with
`provenance = legacy_extracted_json`. **That is expected, not a bug.** It is the
number §14 asked for: how often current worker output already conforms, measured
without changing behaviour.

## Persistence and replay (§28, §29)

No new database, no new store. `worker_patch_envelope.json` joins the existing
replay bundle's `JSON_ARTIFACT_NAMES` allow-list, the same additive,
migration-safe shape CHECK.LIVE.1 used for its shadow receipt.
`load_worker_patch_envelope_record` defaults every field for a bundle that
predates the phase, and forces `authoritative_effect` to `False` even if a
persisted record claims otherwise.

The record is **identity, not payload** (§27): statuses, provenance, plan
identities, a fingerprint, an operation count and bounded rejected key names. A
test feeds a response containing a secret-looking file body and asserts neither
the body, the snippet, nor the surrounding prose appears in the serialised
record.

## Dogfood (§38)

`summarize_worker_patch_envelope_records` tallies `strict_valid_responses`,
`legacy_only_responses`, `invalid_both_responses`, `strict_legacy_mismatches`,
plus per-status and per-provenance counts. Adoption counters only — a test
asserts the serialised summary contains no `confidence`, `score`, `trust`,
`quality` or `verdict`.

## Files changed

| File | Change |
|---|---|
| `core/worker_patch_envelope.py` | new — contract, strict parser, identity, comparison, summary |
| `core/run_lifecycle.py` | optional `worker_patch_response=None`; flag-guarded artifact write |
| `core/replay_recorder.py` | one artifact name added to the allow-list |
| `core/agent_state.py` | one optional field |
| `core/pipeline.py` | flag-guarded measurement in `finalize_answer`; passes it at the apply |
| `core/sleeping_consultant.py` | same, in `_run_patch_item` |
| `scripts/run_patch_proposal_queue.py` | same, in `_process_item` |
| `tests/test_worker_patch_envelope.py` | new — 52 behaviour tests |
| `tests/test_worker_patch_envelope_boundaries.py` | new — 14 static boundary tests |
| `tests/test_native_worker_declaration_qualification.py` | one over-tight assertion relaxed to its actual intent |
| `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`, `tests/test_phase_picker.py` | registration |

`core/json_utils.py`, `core/prompter.py`, `core/control_engine.py`,
`patching/`, `agents/`, `core/executor.py`, `core/self_correct_loop.py` and every
frozen checker are untouched and in `forbidden_files`.

### One WORKER.DECL.1 test was relaxed

`test_the_nearest_near_miss_is_a_relevance_hypothesis_not_an_intent` asserted the
*exact keyword set* of the dream apply call, which broke when this phase threaded
`worker_patch_response` through it. The assertion was over-tight for its own
claim: WORKER.DECL.1 was making a statement about **declaration provenance**, not
about the argument list. It now asserts what it meant — no `worker_declaration`
kwarg, and no kwarg fed from the planning payload — so a later phase threading
another bounded observation cannot silently turn `likely_files` into a
declaration. WORKER.DECL.1's global
`test_no_production_caller_supplies_a_worker_declaration` is unchanged and still
covers the seam.

## Known limitations

1. **A prose-only response reports `surrounding_prose_rejected`**, not a
   distinct "no JSON at all" status — see above; refining it would require the
   scanning this phase refuses.
2. **No production provider emits a strict envelope today.** Until §19's prompt
   experiment runs, the expected dogfood distribution is almost entirely
   `legacy_extracted_json`. The channel is proven; adoption is not.
3. **`patch_candidate`-only responses are `no_patch_payload`** for this
   measurement, so single-file-edit runs are invisible to the strict/legacy
   comparison. Extending the envelope to carry a candidate would be a contract
   change this phase declined to make.
4. **The web routes are not wired.** `web/app.py`'s two patch-generation
   endpoints produce a payload for operator review rather than applying it
   directly, so there is no lifecycle call to attach a record to. They can adopt
   the same two lines whenever a sink exists.

## What comes next

**WORKER.DECL.2A-followup (optional, cheap):** apply the existing `SCOUT_PROMPT`
wording to the patch response contract behind the same flag, change nothing
else, and re-read the counters. That answers "can current providers hit the
strict protocol at all?" with one variable moved.

**WORKER.DECL.2B:** add `pre_execution_change_intent` inside this now-proven
envelope, with the `pre_execution_intent` declaration stage, staged provenance
vocabulary and derived measurability flags that
[WORKER.DECL.1's qualification](2026-08-28-native-worker-declaration-source-qualification.md)
listed as blocking. Two fields of one model response are an
`independently_declared_channel` measuring internal output consistency — never
independent evidence, and never input to EVIDENCE.2's independence semantics.

**Then CHECK.LIVE.1B's native declaration seam**, and only after that
CHECK.LIVE.2A.
