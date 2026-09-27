# PATCH.AUTHOR.LIVE.1 — Verification-Guided Single Revision

**Date:** 2026-09-09
**Track:** CONTROL
**Status:** complete
**Prerequisites:** PATCH.MINIMAL.LIVE.1, PATCH.MINIMAL.LIVE.2, DEFECT.PROBE.LIVE.4,
CANDIDATE.VERIFY.LIVE.1, DEFECT.FACT.LIVE.1, PATCH.BASIS.LIVE.1, OPS.PATCH.2,
CONTROL.LOCALIZE.LIVE.2, RETRIEVE.LIVE.4, EXEC.POLICY.LIVE.1,
EXEC.APPROVAL.LIVE.1, EXEC.AUTH.LIVE.1

---

## 1. The measured problem

The T6 defect is structurally reachable. Localization binds
`core/code_dna.py::_classify_indent` exactly. The typed behavior fact is
`expected = 2space / claimed_observed = 4space`. Correct local-only solutions
are expressible under PATCH.MINIMAL.LIVE.2's bounded local-binding novelty.
DEFECT.PROBE.LIVE.4 can distinguish a shallow overfit from real
indentation-unit behavior. Candidate verification rejects wrong candidates.

Everything is in place except one thing: first-draft authorship keeps failing,
and it fails in different ways each round.

| Round | Candidate | How it failed |
|---|---|---|
| 6 | new external member | rejected by `safe_minimal` |
| 7 | inverted branch order | primary fixed, preservation regressed |
| 7 | exact no-op | changed zero bytes |
| 8 | exact no-op again | changed zero bytes |
| 8 | behaviorally dead guard | byte-changing, structurally valid, behaviorally identical |

The last one is the interesting failure:

```python
elif line.startswith("  ") and not line.startswith("    "):
```

It is a real byte change. It passes `safe_minimal`. It applies cleanly in the
sandbox. And it does nothing at all, because the `elif line.startswith("    ")`
branch above it has *already* consumed every line the new conjunct would have
excluded. The guard is dead.

DEFECT.PROBE.LIVE.4 measured exactly that, deterministically:

```
indentation_style.primary.2space            still_reproduced   (expected 2space, observed 4space)
indentation_style.generalize.2space.deep    still_reproduced   (expected 2space, observed 4space)
indentation_style.preserve.4space           preserved
indentation_style.preserve.4space.deep      preserved
                                 matrix →   still_reproduced
```

and CANDIDATE.VERIFY.LIVE.1 reduced it to `rejected /
primary_defect_not_closed`.

**The harness knew precisely why the candidate was wrong. The model was never
told.** That is the entire gap this phase closes.

---

## 2. What this phase is

One bounded counterexample-guided revision:

```
Candidate₀
    ↓  deterministic verification (frozen)
CandidateRevisionEvidence
    ↓  ONE author call, same provider/model
Candidate₁
    ↓  the entire frozen gate + verification pipeline, again, from nothing
verdict
```

The verifier stays authoritative. The model does not judge whether its own
revision passed. The phase manages one additional synthesis attempt and
nothing else.

## 3. What this phase is not

Not an unlimited repair loop — the budget is exactly one call per run and the
counter is structural. Not a reviewer, critic or debate turn — the same
authoring role is asked once, and the adapter is asserted by test to reference
no reviewer entry point. Not model self-reflection or chain-of-thought
extraction — the request never asks for reasoning. Not a hint channel — see §7.
Not a T6 recipe. Not verifier weakening, `safe_minimal` widening, retrieval
expansion, CONTROL retuning or authority widening. Not automatic application.

`_classify_indent` is **not** fixed. The shipped defect is this phase's
measuring instrument, and a test asserts its bytes are unchanged.

---

## 4. Files changed

| File | Change |
|---|---|
| `core/candidate_revision.py` | **new.** Pure, stdlib-only. Vocabularies, the evidence receipt, the eligibility reduction, the prompt builder, the output parser, the telemetry receipt. |
| `core/pipeline.py` | Extracted `_run_read_only_candidate_lifecycle` out of `_verify_authored_candidate_without_mutation` verbatim; added the revision adapter and its telemetry key group. 35 → 42 top-level definitions: 7 added, 0 removed, 1 changed. |
| `core/agent_state.py` | One field: `candidate_revision`, which holds the receipt and with it the run's budget counter. |
| `tests/test_candidate_revision_live.py` | **new.** |
| `tests/fixtures/patch_author_live1_frozen_boundaries.json` | **new.** 31 pinned files + the reversible containment proof for `core/pipeline.py`. |
| `tests/test_answer_ground_payload_ownership.py` | `_CANDIDATE_REVISION_KEYS` appended to the control-plane group list. |
| `tests/test_phase_registry.py` | Counters; the "who may spend a model call" invariant re-homed onto every declarer. |
| `tests/test_phase_picker.py` | Counters. |
| `docs/roadmap/phase_registry.json` | The entry. |

---

## 5. The eligibility rule

Eligibility is a conjunction, not a score. Every clause is a lookup on a
receipt the run already produced; `assess_candidate_revision` is a pure
reduction and reads nothing from disk.

**Required, in cheap-first order:**

1. the run's revision budget is unspent
2. `route.selected_workflow == "defect_repair_patch"`
3. `patch_basis == grounded_defect`
4. the candidate is not a recorded exact no-op
5. `safe_minimal` did not reject the candidate
6. a candidate exists, with bytes and a fingerprint
7. `candidate_effect_status == mutating`
8. `patch_safety.ok is True`
9. `candidate_probe_apply_status == applied`
10. `pre_probe.probe_result == reproduced`
11. the target binding is exact and present (file **and** symbol)
12. the authoritative original source is available
13. the preserved task is available
14. the matrix's and the verification's candidate fingerprints both match the
    candidate currently on the payload
15. `candidate_verification_status == rejected`
16. at least one rejection reason is **behavioral**:
    `primary_defect_not_closed`, `behavior_preservation_regressed`,
    `subject_invariant_not_closed`
17. `behavioral_matrix_status ∈ {still_reproduced, partially_fixed,
    fixed_but_regressive, unresolved_matrix_failure}`
18. at least one matrix case actually failed

### Ineligible rejection classes — no model call, ever

| Class | Recorded reason |
|---|---|
| exact no-op | `candidate_was_an_exact_no_op` |
| `safe_minimal` rejection | `safe_minimal_rejected_the_candidate` |
| sandbox apply failure | `candidate_sandbox_apply_did_not_succeed` |
| patch safety rejection | `patch_safety_blocked_the_candidate` |
| stale candidate / fingerprint mismatch | `candidate_fingerprint_is_stale` |
| malformed / no candidate | `no_candidate_was_authored` |
| unmeasured or undetermined effect | `candidate_effect_is_not_mutating` |
| unavailable / stale target | `target_binding_is_not_current_and_exact` |
| baseline not reproduced | `baseline_defect_was_not_reproduced` |
| verifier verified / inconclusive / unavailable / stale / invalid | `candidate_verification_did_not_reject` |
| non-behavioral rejection, inconclusive matrix, no failing case | `no_deterministic_behavioral_counterevidence` |
| wrong route | `route_is_not_defect_repair` |
| explicit change | `patch_basis_is_not_grounded_defect` |
| budget spent | `revision_budget_already_consumed` |

**Why an exact no-op does not get a revision.** PATCH.MINIMAL.LIVE.1 already
gives the precise, cheap answer: *the model proposed no mutation.* Spending a
provider call to rescue it would make the trigger mean "something went wrong"
rather than "the verifier produced behavioral counterevidence". The phase is
verification-guided revision, not generic candidate retry.

**Why a `safe_minimal` rejection does not get one either.** That refusal is a
policy statement about the candidate's *form*. This phase does not use model
calls to negotiate around safety policy.

Every ineligible case is *recorded* — `not_eligible` with its named reason —
rather than left silent, so a reader can see the trigger was evaluated and
declined.

---

## 6. The evidence receipt

`CandidateRevisionEvidence` is frozen and slotted. It binds:

- the preserved task, verbatim, plus its sha256
- `target_file`, `target_symbol`
- the authoritative original source and its sha256
- `rejected_candidate_fingerprint`, and Candidate₀'s target/patched bytes
- `verification_status` and its rejection reasons
- `matrix_status`
- `failed_cases`, `preserved_cases`
- `probe_fingerprint`, `trigger`, `phase_id`, `schema_version`
- `evidence_fingerprint` — a sha256 over the serialized record

There is no prose field. The serialized `as_dict()` carries digests, not source
bytes, and a test asserts the target body does not appear in it.

### Failed / preserved case shape

Each case is a `RevisionCounterexample` with exactly six bounded machine facts:

```
case_id, role, provenance, expected, candidate_observed, status
```

For the T6 dead guard, that is literally:

```
- case_id=indentation_style.primary.2space         role=primary_defect
  provenance=explicit_user_fact                    expected='2space' observed='4space' status=still_reproduced
- case_id=indentation_style.generalize.2space.deep role=defect_generalization
  provenance=system_derived_subject_invariant      expected='2space' observed='4space' status=still_reproduced
```

with the two preservation cases carried as constraints:

```
- case_id=indentation_style.preserve.4space        role=preservation
  provenance=system_derived_behavior_preservation  expected='4space' observed='4space' status=preserved
- case_id=indentation_style.preserve.4space.deep   role=preservation_generalization
  provenance=system_derived_subject_invariant      expected='4space' observed='4space' status=preserved
```

### Provenance semantics

`RevisionCounterexample.__post_init__` refuses to construct a non-primary case
carrying `explicit_user_fact` provenance — the same rule
`BehavioralMatrixCase` enforces upstream. The user said one thing and it is the
primary case; a system-derived generalization may not borrow their authority on
its way into a prompt. A case that arrives mislabelled is **discarded**, never
relabelled, which can only make the evidence smaller.

### Freshness

`revision_evidence_is_current` re-checks, immediately before the call is spent:
the candidate fingerprint, the original source digest, the target file and the
target symbol. Any drift → outcome `stale`, no model call.

---

## 7. No implementation hints — proved structurally

The mechanism is not a filter. It is that **there is no advice written down for
a code path to compose.** Every fixed sentence the request can contain is a
module constant, and all of them are listed in `PROMPT_TEMPLATE_CONSTANTS`.

Two tests hold the line:

1. `test_no_template_constant_names_a_technique` reads that tuple and asserts
   none of them contains `gcd`, `lstrip`, `strip`, `width`, `unit`, `divisor`,
   `modulo`, `greatest common divisor`, `leading space`, `count the`,
   `local variable`, `branch order`, `reorder`, `measure`, `loop over` or
   `helper function` — which is why the request says "executed" and "observed"
   rather than "measured". A template added later without being listed fails here.
2. `test_the_prompt_is_exactly_template_plus_measured_facts` subtracts the
   template constants, the user's own task, the target identifier, the original
   source, the rejected bytes and every measured case field from the rendered
   prompt, and asserts the residue is only punctuation and field labels.

The harness tells the model **what behavior failed**, never **how to fix it**.

### No hidden reasoning

The request contains task, target, authoritative source, prior candidate and
deterministic evidence, and asks for a corrected candidate. It never asks the
model to reveal or critique its reasoning; a test asserts the prompt contains
none of `reasoning`, `think step`, `chain of thought`, `explain why`,
`critique`, `reflect`, `what went wrong`.

---

## 8. The request

Deterministic concatenation, in this order:

```
REVISION REQUEST. ...asked once for a corrected candidate.
ORIGINAL TASK (verbatim, unchanged):        <preserved user task>
TARGET:                                     core/code_dna.py::_classify_indent
AUTHORITATIVE ORIGINAL SOURCE. ...the base your candidate must replace:
                                            <original bytes>
REJECTED CANDIDATE - EVIDENCE ONLY. ...not a starting point, and no part of it
is known to be right.                       <Candidate₀ bytes>
DETERMINISTIC VERIFICATION. ...an observed result, not an opinion.
                                            matrix_status / verification_status / reasons
Cases the rejected candidate did not satisfy:     <failed cases>
Cases the rejected candidate did satisfy, which your candidate must continue
to satisfy:                                       <preserved cases>
INSTRUCTION. Produce one revised patch candidate ... Author it against the
authoritative original source shown above; do not build on the rejected
candidate and do not assume it was correct. ... Return the normal
patch-candidate JSON schema and nothing else.
```

Candidate₀ is shown, clearly labelled, positioned *after* the authoritative
source, and explicitly denied the status of a base. A test asserts that
ordering and that label.

---

## 9. Original source remains the patch base

`rebase_onto_original_source` performs **exactly one** substitution into the
authoritative original bytes — the same arithmetic the existing partial-body
normalizer uses:

- `target_snippet == original_source` → accepted as-is
- `target_snippet` occurs exactly once in `original_source` → grafted in
- anything else → `revision_candidate_is_not_based_on_the_original_source`

The third branch is the mechanism that prevents compounding edits: a fragment
that exists only in Candidate₀'s bytes is not found in the original, so
Candidate₁ can never be an incremental mutation of Candidate₀'s sandbox.

---

## 10. Candidate₁ earns everything again

On acceptance, `_drop_candidate_bound_receipts` removes **all seven**
candidate-bound key groups before anything is measured:

`_CANDIDATE_VALIDATION_KEYS`, `_TARGETED_VALIDATION_KEYS`,
`_CANDIDATE_DEFECT_PROBE_KEYS`, `_EXECUTION_ELIGIBILITY_KEYS`,
`_CANDIDATE_VERIFICATION_KEYS`, `_CANDIDATE_EFFECT_KEYS`,
`_CANDIDATE_NOVELTY_KEYS`

plus `patch_safety`, `patch_safety_passed`, `patch_safety_blocked`,
`eligible_for_patch_safety_handoff`, `approval_ready`, `human_review_eligible`,
`candidate_review_ready`, `candidate_visible_for_debugging`,
`needs_escalation`, and Candidate₀'s `candidate_verification` issues.

Candidate₁ then goes through, in order:

1. `normalize_patch_candidate_with_control_source` — new normalization
2. a fresh exact fingerprint
3. `_record_candidate_mutation_effect` — PATCH.MINIMAL.LIVE.1, unchanged
4. `_enforce_safe_minimal` — PATCH.MINIMAL.LIVE.2, unchanged
5. fresh patch safety, fresh candidate sandbox
6. the **full four-case** DEFECT.PROBE.LIVE.4 matrix — no case is dropped
   because this is a revision
7. OPS.VALIDATE.3, with its existing budgets and selectors untouched
8. a fresh CANDIDATE.VERIFY.LIVE.1 reduction

No Candidate₀ result may authorize Candidate₁, and a test asserts every
candidate-bound fingerprint on the finished payload names Candidate₁.

**Baseline evidence** — the reproduction receipt, the target digest, the
preserved behavioral expectation — is reused where existing freshness semantics
already allow it, because it is bound independently of any candidate. If
freshness changed, the existing semantics fail closed.

---

## 11. The budget

`MAX_REVISION_CALLS_PER_RUN = 1`. There is no configuration knob.

The counter lives on `AgentState.candidate_revision`, which *is* the receipt —
the payload's candidate is exactly the thing a revision replaces, so the budget
cannot live there. `CandidateRevisionReceipt.__post_init__` raises on
`attempt_count > 1`, on `attempted` with `attempt_count != 1`, and on
unattempted with a non-zero count, so a receipt claiming two calls cannot be
constructed at all.

Re-entering the read-only branch re-reads a spent budget and refuses with
`revision_budget_already_consumed`. A test drives the branch twice and asserts
the adapter was called once.

Outcomes that consume the budget: `revised_candidate_produced`,
`revised_candidate_verified`, `revised_candidate_rejected`,
`revision_output_invalid`, `revision_unavailable`. A failed attempt consumes it
too — retrying would be a loop (§45).

---

## 12. Provider and model

`_revision_author_configuration()` reads `config.MODELS` — the same list
`run_draft_pipeline` uses — and reports `provider="google"`,
`model=MODELS[0]`, `author_selection="same_as_initial_draft"`. There is no path
to a bigger model, a reviewer model or a different provider, and a test asserts
that as well as the absence of every reviewer/debate/retrieval entry point from
the adapter's source.

`_call_revision_provider` contains exactly one `run_gemini_request` call and no
loop of any kind. It attaches **no files**: the request is self-contained by
construction, so re-uploading the draft call's attachments would add network
without adding information. The revision context delta is therefore only the
rejected candidate and the counterexample evidence — a *reduction* on
Candidate₀'s context, not an expansion.

---

## 13. Outcomes (closed vocabulary)

`not_eligible`, `revised_candidate_produced`, `revision_output_invalid`,
`revised_candidate_rejected`, `revised_candidate_verified`,
`revision_unavailable`, `stale`.

Output rejections (also closed): `revision_provider_returned_nothing`,
`revision_provider_reported_an_error`, `revision_output_carried_no_json_payload`,
`revision_output_carried_no_patch_candidate`,
`revision_candidate_has_no_patched_snippet`,
`revision_candidate_has_no_target_snippet`,
`revision_candidate_names_a_different_file`,
`revision_candidate_names_a_different_symbol`,
`revision_candidate_is_not_based_on_the_original_source`.

An improved *explanation* is not success: a response whose `patched_snippet` is
empty is `revision_candidate_has_no_patched_snippet`, however good its
diagnosis.

---

## 14. Authority

Revision success grants **zero** authority. `CandidateRevisionReceipt` has no
authorization field that can be true: `execution_authorized` and
`final_repository_changed` are read-only properties returning `False`, and
`authority_effect` is the literal `"none"`.

Under `AUTO_PATCH_ENABLED=false`, a verified Candidate₁ ends the run with
`execution_authorized=false`, `final_repository_changed=false`,
`auto_apply_allowed=false`, `write_authority=false` and the target file
byte-identical on disk. Existing human approval boundaries are untouched; no
approval-ready mutation receipt is invented.

A failed, malformed or unavailable revision ends with
`human_review_eligible=false` and `needs_escalation=true`. Candidate₀ survives
only as bounded historical evidence under
`candidate_revision_previous_candidate`, tagged `rejected_evidence_only`.

---

## 15. Confidence

Confidence is not an eligibility input in either direction. Two payloads
differing only in `confidence` produce byte-identical evidence, which a test
pins. Candidate₀'s confidence is not clamped merely because it failed, and it
is not carried onto Candidate₁ — the key is removed and restored only if the
revision response actually returned a new value in the normal schema.

---

## 16. Deterministic controls

All run against the live `core/code_dna.py` defect with a deterministic
adapter in place of the provider, asserting the real file's bytes before and
after.

| Control | Candidate₀ | Revision | Result |
|---|---|---|---|
| §29 dead guard, first pass | dead guard | — | matrix `still_reproduced`, verification `rejected`, eligible |
| §30 positive | dead guard | correct local-only | 1 call, fresh fingerprint, novelty admitted, matrix `fixed_and_preserved`, **verified**, `execution_authorized=false`, repo unchanged |
| §31 failure | dead guard | inverted reorder | Candidate₁ `fixed_but_regressive` → rejected, `attempt_count=1`, no third call, `needs_escalation=true` |
| §32 inverted reorder | inverted reorder | correct | eligible on `fixed_but_regressive`, one revision, verified |
| §33 Round-8 ceiling | ceiling | correct | eligible on the depth cases, no algorithm in the prompt, verified |
| §34 exact no-op | no-op | — | 0 calls, 0 probes, `not_eligible / candidate_was_an_exact_no_op` |
| §35 safe_minimal | new import | — | 0 calls, `not_eligible / safe_minimal_rejected_the_candidate` |
| §20 malformed | dead guard | non-JSON | `revision_output_invalid`, no further call |
| §45 unavailable | dead guard | `AGENT_ERROR:` | `revision_unavailable`, no retry |
| §10 rebase | dead guard | based on Candidate₀ | `revision_candidate_is_not_based_on_the_original_source` |
| §21 no-op revision | dead guard | original body | stopped by PATCH.MINIMAL.LIVE.1, no third call |
| §22 novel revision | dead guard | new import | stopped by PATCH.MINIMAL.LIVE.2, no third call |
| §28/§46 first-draft success | correct | — | 0 calls, `not_eligible / candidate_verification_did_not_reject` |
| §47 explicit change | dead guard | — | 0 calls, `patch_basis_is_not_grounded_defect` |
| §48 analysis | dead guard | — | 0 calls, branch never entered |

---

## 17. Static boundaries

`tests/fixtures/patch_author_live1_frozen_boundaries.json` pins 31 files by
sha256, covering RETRIEVE.LIVE.4, CONTROL.LOCALIZE.LIVE.2, DEFECT.FACT.LIVE.1,
PATCH.MINIMAL.LIVE.1/.2, the probes, DEFECT.PROBE.LIVE.4, OPS.VALIDATE.3,
CANDIDATE.VERIFY.LIVE.1, EXEC.AUTH/POLICY/APPROVAL and `core/code_dna.py`.

For `core/pipeline.py` — which this phase *is* authorized to change — the
fixture stores the six reversal hunks instead of only a hash. A test
reconstructs the pre-phase file from the shipped one, asserts its sha256, and
then **derives** the definition-level comparison rather than asserting it:

```
35 top-level definitions before, 42 after
added   (7): _call_revision_provider, _drop_candidate_bound_receipts,
             _maybe_revise_rejected_candidate, _record_candidate_revision,
             _revision_attempts_already_made, _revision_author_configuration,
             _run_read_only_candidate_lifecycle
removed (0): —
changed (1): _verify_authored_candidate_without_mutation
```

The one changed definition now delegates its body to the extracted lifecycle.
A separate test reads `_run_read_only_candidate_lifecycle` and asserts the
producers appear in the original order and that it references no provider.

No traversal, index rebuild, embedding or network is added beyond the single
provider revision call.

---

## 18. Known limitations

**The rebase rule is strict.** A revision whose `target_snippet` appears more
than once in the original source, or not at all, is refused rather than guessed
at. On a live provider that costs the opportunity when the model returns an
ambiguous fragment. The alternative — having the harness pick which occurrence
was meant — would be the harness authoring part of the patch, which is the
boundary this phase exists to hold.

**One subject has a matrix.** Counterexamples are only as rich as
DEFECT.PROBE.LIVE.4's adapters, and `indentation_style` is still the only
production subject with one. A defect whose subject has no matrix reaches
`no_deterministic_behavioral_counterevidence` and is never revised — correctly,
since there would be nothing measured to send back.

**One revision, by design.** If Candidate₁ fails there is no Candidate₂. That
is the specification, not an oversight; whether one bounded revision is enough
for a real provider is a question for the next black-box round, and the phase
deliberately does not pre-empt the answer by adding a loop.

**The hook lives in the mutation-disabled branch only.** `_maybe_revise_rejected_candidate` is called from `_verify_authored_candidate_without_mutation`, which `maybe_run_auto_patch` enters only when `AUTO_PATCH_ENABLED` is false. `config.py` defaults that switch to *true*, so a default-configured run gets no revision; the black-box eval harness and every control in this phase set it false, which is the configuration §26/§30/§51/§52 specify throughout. Placing the hook on the mutation-enabled path too would let a revised candidate reach an auto-apply path, which is exactly the authority widening §26 and §49 forbid, so it is deliberately not there. If a later phase wants revision under mutation, that is an authority decision and belongs in its own phase.

**The trigger is narrow on purpose.** A defect whose verification is
inconclusive because targeted validation could not select checks is *not*
eligible, even though a human might still see a useful revision there. Widening
that would make the trigger mean "the run was unsatisfying" instead of "the
verifier contradicted the candidate".
