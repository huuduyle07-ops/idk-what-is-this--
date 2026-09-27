# CANDIDATE.VERIFY.LIVE.1 — Read-Only Candidate Verification Before Human Review

**Date:** 2026-09-08
**Track:** OPS (`CANDIDATE.*` is a phase-id namespace, not a new registry track)
**Status:** complete
**Prerequisites (frozen):** DEFECT.PROBE.LIVE.3, DEFECT.FACT.LIVE.1,
CONTROL.LOCALIZE.LIVE.2, OPS.PATCH.2, OPS.VALIDATE.3, VALIDATE.ORACLE.LIVE.1,
EXEC.POLICY.LIVE.1, EXEC.APPROVAL.LIVE.1, EXEC.AUTH.LIVE.1

---

## 1. The defect this phase exists for

`AUTO_PATCH_ENABLED` names one thing: whether this process may **mutate** a
repository. Until this phase it silently named a second thing as well.

`core/pipeline.py::maybe_run_auto_patch` returned at the kill-switch check,
immediately after the WAITER read-only route guard:

```python
if not AUTO_PATCH_ENABLED:
    print("Auto-patch disabled by AUTO_PATCH_ENABLED=false.")
    _record_no_execution(state, DENIED_AUTO_PATCH_DISABLED)
    return
```

Everything downstream was therefore unreachable in the safe evaluation
configuration:

- candidate sandbox validation (OPS.PATCH.2),
- the paired candidate post-probe (DEFECT.PROBE.LIVE.3),
- defect-closure assessment,
- targeted baseline/candidate validation (OPS.VALIDATE.3),
- oracle assessment (VALIDATE.ORACLE.LIVE.1),
- the exact candidate fingerprint.

And yet the authored candidate was still rendered for the user. The T6 smoke
paid for it: the branch-reorder candidate reached a human with
`needs_escalation=false`, `confidence=0.4` and no evidence of any kind — not
because the evidence disagreed, but because nothing ran.

**Mutation-disabled had become verification-disabled.** That is the only thing
this phase fixes.

### Why the candidate is wrong, and why `safe_minimal` is right about it

The T6 candidate swaps two `elif` branches in `_classify_indent`:

```python
        elif line.startswith("    "):      # 4space
            counts["4space"] += 1
        elif line.startswith("  "):        # 2space
            counts["2space"] += 1
```

becomes

```python
        elif line.startswith("  "):        # 2space
            counts["2space"] += 1
        elif line.startswith("    "):      # 4space
            counts["4space"] += 1
```

One file. Identical token multiset. No new identifier, no new API. `safe_minimal`
**accepts** it, and that acceptance is correct — shape safety is shape safety and
was never asked to detect a semantic inversion. The candidate reverses the prefix
overlap instead of resolving it: two-space input now classifies as `2space`
(the primary probe reports **fixed**) and four-space input classifies as
`2space` too (the preservation counter-case reports **regressed**).

Both of those facts already existed, in DEFECT.PROBE.LIVE.3. Nothing ran them.

---

## 2. New lifecycle ordering

```
candidate authored
    ↓
safe_minimal / patch safety
    ↓
exact candidate sandbox                      (disposable copy, never the repo)
    ↓
candidate verification
    ├─ paired post-probe                     DEFECT.PROBE.LIVE.3
    ├─ preservation probe                    DEFECT.PROBE.LIVE.3
    ├─ targeted validation                   OPS.VALIDATE.3
    └─ oracle assessment                     VALIDATE.ORACLE.LIVE.1
    ↓
candidate verification receipt               CANDIDATE.VERIFY.LIVE.1  ← new
    ↓
execution policy / human review              EXEC.POLICY.LIVE.1
    ↓
mutation only if separately authorized       (never on this branch)
```

The read-only branch stops after the receipt and the **unchanged**
`auto_patch_disabled` denial. There is no executor call, no apply path and no
authority setter anywhere inside it.

### Meaning of `AUTO_PATCH_ENABLED` after this phase

| | before | after |
|---|---|---|
| may mutate the repository | no | no |
| may acquire write authority | no | no |
| candidate is verified | **no** | **yes, read-only** |
| candidate is shown to a human | yes | yes, with a receipt |

`AUTO_PATCH_ENABLED=true` is untouched: the mutation-enabled path does not enter
the new function, which a test asserts directly.

---

## 3. What was added

### `core/candidate_verification.py` — a pure reducer

No evidence producer. It consumes receipts the existing phases already wrote
onto the live payload and reduces them into one closed status. Its only imports
are `dataclasses`, `hashlib`, `json`, `re` and `typing`; a test walks its AST and
asserts no reference to `subprocess`, `open`, `Path`, `environ`, a network
client, a model client, or any of the three evidence producers.

**Status vocabulary (closed):** `verified`, `rejected`, `inconclusive`,
`unavailable`, `stale`, `invalid`.

**Component verdicts (closed):** `supporting`, `contradicting`, `inconclusive`,
`unavailable`, `not_applicable`, `stale`, `invalid`.

**Profiles**, derived from the existing typed patch basis — never invented here:

| profile | required components |
|---|---|
| `grounded_defect_bounded_evidence` | patch safety, exact sandbox, paired probe, targeted validation, oracle assessment |
| `explicit_change_sandbox_coherence` | patch safety, exact sandbox |

**Reduction precedence:**

```
invalid  >  stale  >  rejected  >  unavailable  >  inconclusive  >  verified
```

Integrity beats freshness; freshness beats a substantive verdict. Evidence we
cannot trust is never reported as a *finding about the candidate* — a stale
comparison does not get to say the candidate is bad any more than it gets to say
it is good.

### Three rules the reduction holds

**Verification is not authorization.** `verified` is a statement about evidence.
Under `AUTO_PATCH_ENABLED=false` a verified candidate still ends with
`execution_authorized=false` and `final_repository_changed=false`. The receipt
type raises if anything tries to give it an `authority_effect` other than
`none`, and its `execution_authorized` / `final_repository_changed` properties
are constants.

**Missing evidence is never a pass.** A required component that could not be
measured yields `unavailable` or `inconclusive` for the whole verification. The
single exception is stated out loud rather than hidden: OPS.VALIDATE.3 answering
`no_relevant_existing_checks` is a *completed* selection whose finding is that no
existing check is structurally related to the target. That is knowledge, not
absent knowledge, so it is recorded as `not_applicable` **and** listed in
`accepted_limitations`. It can never verify a candidate on its own, because the
paired probe must still be `supporting`.

**A paired result may not be flattened.** A regressed preservation case is read
*before* the closed paired status, so a receipt whose statuses disagree can never
resolve permissively. A test forces `defect_closure_status` and `paired_status`
back to the pre-DEFECT.PROBE.LIVE.3 reading of `fixed`, leaves the regressed
preservation case in place, and asserts the verdict is still `rejected`.

### Exact candidate binding and freshness

The fingerprint is `candidate_fingerprint_from_payload` — the existing OPS.PATCH.2
primitive. No second algorithm was invented. Verification is `stale` when:

| condition | source of truth |
|---|---|
| candidate bytes changed | producer receipt fingerprint ≠ current candidate fingerprint |
| relevant source changed | probe receipt's `executed_source_sha256` ≠ binding's `localized_source_sha256` |
| target binding changed | probe's bound file ∉ candidate's target paths |
| probe changed | closure's `probe_fingerprint` ≠ pre-probe's `probe_fingerprint` |
| stored receipt outlived its candidate | `candidate_verification_is_current` |

The receipt's keys are added to the pipeline's existing stale-drop, so a
refinement discards the verification with the evidence it reduced.

---

## 4. Binding into the existing eligibility and approval paths

`core/execution_eligibility_policy.py` (EXEC.POLICY.LIVE.1) and
`core/human_apply_authorization.py` (EXEC.APPROVAL.LIVE.1) are **byte-identical**.
No second approval system was added. The binding is by narrowing and omission:

1. When verification is not `verified`, the adapter forces
   `human_review_eligible=False`, `needs_escalation=True`, `approval_ready=False`.
   Narrowing only ever *removes* readiness; no eligibility is created that the
   frozen policy did not already grant.
2. Only a verified **and** eligible candidate is frozen into a
   `human_apply_review` receipt. The frozen Apply path already refuses any
   `grounded_defect` candidate that has none, so a rejected, stale or invalid
   verification cannot be turned into an authorized mutation by a human pressing
   Apply. A test drives `authorize_human_apply` on the rejected T6 payload and
   asserts `authorized=False`, `denial_reason=not_human_review_eligible`.

`human_review_eligible` was already false for this candidate under
EXEC.POLICY.LIVE.1 — the paired probe downgrades `defect_closure_status` to
`fixed_but_regressive`, which fails `REQ_POST_PROBE_FIXED`. The narrowing is a
second, independent lock, not a replacement for the first.

### Three separate user-facing facts

| field | meaning |
|---|---|
| `candidate_visible_for_debugging` | the candidate and its evidence stay readable — always true |
| `candidate_review_ready` | may this be *described* as ready to approve — only when verified |
| `human_review_eligible` | the frozen EXEC.POLICY reduction, narrowed by verification |

The operator message for a non-verified candidate reads *"The candidate below is
shown for inspection only — it is not verified and is not ready to approve or
apply"*, and rejection reasons are appended to the payload's `issues` list in the
existing canonical structured shape (`severity`/`type`/`file`/`symbol`/`reason`/
`fix`, plus a closed `code`). No new plain-string drift.

---

## 5. Measured results

Both candidates measured against the real repository, read-only, with the real
producers. `core/code_dna.py` is asserted byte-identical before and after every
run.

| | known-wrong T6 (branch reorder) | positive control (width-distinguishing) |
|---|---|---|
| candidate authored | yes | yes |
| safe_minimal / patch safety | **accepted** | accepted |
| exact sandbox apply | `applied` | `applied` |
| primary defect probe | **fixed** | fixed |
| preservation probe | **regressed** | preserved |
| paired status | `fixed_but_regressive` | `fixed_and_preserved` |
| targeted validation | `no_relevant_existing_checks` (accepted limitation) | same |
| oracle assessment | `current` | `current` |
| **candidate verification** | **`rejected`** | **`verified`** |
| rejection reason | `behavior_preservation_regressed` | — |
| `human_review_eligible` | **false** | true |
| `needs_escalation` | **true** | false |
| approval-ready receipt | **none** | frozen, but unusable while mutation is off |
| `execution_authorized` | **false** | **false** |
| `final_repository_changed` | **false** | **false** |

The positive control is the proof that verification *opens* as well as closes,
and that opening it grants nothing.

---

## 6. Deltas

| dimension | delta |
|---|---|
| model calls | **zero added.** Verification reads the candidate the run already authored. |
| network calls | zero added |
| repository traversal | zero added |
| repository mutation | zero — every candidate byte lives in a disposable managed sandbox |
| authority | zero. `candidate_verification_authority_effect=none`; no authority setter outside the existing EXEC paths |
| validation semantics | zero. OPS.VALIDATE.3's selector, commands and budgets are untouched; the 30-second full-validation timeout was not raised |
| `safe_minimal` | unchanged, and deliberately so |
| candidate generation | unchanged |
| `_classify_indent` | **not fixed** — still deliberately broken, and pinned |

### Cost, measured separately

Each stage is timed on its own rather than folded into one number:
`candidate_probe_timings` (sandbox setup, post-probe, preservation probe),
`targeted_validation_timings`, `check_oracle_timings`, and
`candidate_verification_timings.verification_reduction_sec` for the reduction
itself. The reduction is pure and sub-millisecond; the cost of the branch is the
producers', and it is visible per stage.

---

## 7. Boundaries

`tests/fixtures/candidate_verify_live1_frozen_boundaries.json` pins 27 files by
whole-file digest: every evidence producer this phase orchestrates, every
authority / eligibility / approval surface, patch basis and safety, `safe_minimal`
(`patching/patch_gates.py`, `policy/decision_helper.py`), the sandbox and apply
primitives, validation command selection, CONTROL ranking, RETRIEVE recall,
`BehavioralExpectation`, and `core/code_dna.py`.

Pinning `safe_minimal` is deliberate: the phase's whole argument is that shape
safety correctly accepts the known-wrong candidate and that semantic rejection
belongs somewhere else. If a future change made `safe_minimal` reject it, the
argument would have moved without anyone noticing.

`candidate_verification_guardrails()` states the same boundaries in machine-
readable form, and a test asserts every one.

---

## 8. Scope

Out of scope, deliberately:

- **T1/T2/T3** disposable auto-patch flows and **T4** explicit-change human
  approval keep their existing control flow exactly. The mutation-enabled path
  does not enter the new function.
- **T5** `analysis_only` returns at the WAITER read-only guard, before this
  branch.
- No model-authoring improvement. This phase makes a wrong candidate *visible as
  wrong*; it does not try to stop the model authoring it.
- No cleanup phase. The existing candidate-sandbox cleanup is reused.
- No `issues` schema redesign.

## 9. Files

| file | change |
|---|---|
| `core/candidate_verification.py` | new — the pure reducer, vocabulary and receipt |
| `core/pipeline.py` | early return moved; `_record_candidate_verification` and `_verify_authored_candidate_without_mutation` added; verification keys added to the stale-drop |
| `core/phase_registry.py` | `CANDIDATE` appended to `PHASE_ID_PREFIXES` as an ID namespace inside OPS |
| `tests/test_candidate_verification.py` | new — 56 tests |
| `tests/fixtures/candidate_verify_live1_frozen_boundaries.json` | new — 27 pinned files |
| `tests/test_phase_registry.py` | counters: 167→168 phases, OPS 17→18 |
| `tests/test_phase_picker.py` | counter: `complete_or_history` 163→164 |
| `docs/roadmap/phase_registry.json` | one appended entry |
| `docs/designs/2026-09-08-read-only-candidate-verification-before-human-review.md` | this document |
