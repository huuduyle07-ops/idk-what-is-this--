# PATCH.MINIMAL.LIVE.1 — Exact No-Op Candidate Rejection

**Date:** 2026-09-09
**Track:** CONTROL (`PATCH.*` is an ID namespace, not a new track)
**Prerequisites:** PATCH.BASIS.LIVE.1, OPS.PATCH.2, DEFECT.PROBE.LIVE.3,
CANDIDATE.VERIFY.LIVE.1, ANSWER.GROUND.LIVE.4

## The defect

Round-7 black-box evidence established one narrow candidate-sanity defect. The
model authored a candidate whose patched snippet was byte-identical to its
target snippet:

```
target_snippet == patched_snippet
```

The candidate passed `safe_minimal`, and `safe_minimal` was right to pass it:

* it introduced no identifiers;
* it was structurally small;
* the existing no-op heuristic
  (`patching/patch_gates.py::_looks_like_noop_patch`) detects emptied or
  degenerate function *bodies*, not exact replacement equality.

Shape safety is shape safety. It was never asked to notice that two snippets
were the same bytes.

The expensive read-only verification chain then rejected the candidate
correctly, on the right grounds — the primary defect remained reproduced — but
only after building a disposable sandbox, applying the candidate there and
re-running the defect probe. Round 7 spent roughly **3.65 s of candidate
sandbox and 4.29 s of paired probe** proving that identical bytes do nothing.

The harness was safe. It was wasteful, and it was semantically late.

## The invariant

One cheap deterministic rule, and nothing more:

> A patch candidate that changes zero authoritative bytes is not a meaningful
> patch candidate.

For every authoritative patch operation where the original target bytes and the
proposed replacement bytes are both available:

```
original_bytes == replacement_bytes   →   exact_no_effect_operation
```

For a candidate whose operations are **all** exact-no-effect:

```
candidate_effect = no_op   →   reject before sandbox verification
```

## Exact bytes only

`LIVE.1` deliberately handles only exact byte equality. Whitespace,
indentation, line endings, CRLF/LF, trailing newlines, encoding, comments, AST,
syntax and formatting are **not** normalized.

Those deltas represent real repository changes, owned by byte-preserving
semantics. A gate that folded them in would stop being a mutation-effect check
and become a formatting policy — which this phase is not. Seven parametrized
negative controls pin it.

## Where it sits

```
candidate authored
  ↓
target / binding integrity        (enforce_payload_target, unchanged)
  ↓
exact mutation-effect check       ← this phase
  ↓
[if real mutation]
  existing safe_minimal / patch safety
  ↓
  exact candidate sandbox
  ↓
  paired probe / targeted validation / oracle
```

For an exact no-op the run stops at the third line: no candidate sandbox, no
paired post-probe, no targeted validation, no oracle execution. No verification
work is spent proving that identical bytes do nothing.

Implementation:

* `core/candidate_mutation_effect.py` — the pure evaluator and the payload
  rejection. It reads the bounded target/replacement representation the
  candidate pipeline already consumes and re-reads nothing.
* `core/pipeline.py` — three call sites of one adapter,
  `_record_candidate_mutation_effect`:
  1. `finalize_answer`, immediately before `_enforce_safe_minimal` — the stage
     order above, on every path the writer produces a payload on;
  2. the top of `maybe_run_auto_patch`, after target/binding integrity and
     before either the mutation-enabled or the read-only branch — this is what
     makes "zero producer calls" hold for a payload that reached the lifecycle
     another way;
  3. immediately after `normalize_patch_candidate_with_control_source`, which
     may broaden a partial body to the full CONTROL source snippet and so
     change the candidate's fingerprint. Broadening rewrites both sides
     identically, so it cannot turn a mutation into a no-op or the reverse;
     re-measuring re-binds the receipt to the bytes that would be applied.

The check is a single byte comparison, so repeating it costs nothing.

## `safe_minimal` is untouched

`patching/patch_gates.py` is not edited. `_looks_like_noop_patch` is not
taught to detect behavioral regressions, and `_classify_indent` — the
deliberately broken T6 target — is not repaired. The guard sits immediately
*before* the candidate-shape preflight and keeps its reason separate:

| gate | reason |
|---|---|
| PATCH.MINIMAL.LIVE.1 | `no_op_candidate` — no effect |
| `safe_minimal` | invented identifiers / plan forbidden — unsafe or non-minimal |

The Round-7 candidate was structurally minimal. It simply was not a patch.

## Not a semantic verdict

A no-op candidate says nothing about whether the model's diagnosis was correct.
Round 7 in fact had a **correct diagnosis and an empty implementation delta**.
The distinction is preserved:

```
diagnosis correctness   !=   candidate mutation effect
```

The closed reason vocabulary is `no_op_candidate` alone, and deliberately
excludes `validation_failed`, `probe_failed` and `semantic_error` — nothing was
executed, so borrowing execution vocabulary would be a lie. The payload's
`confidence` and `summary` are left exactly as the model wrote them, because
clamping them would re-conflate the two things this phase separates.

## Candidate status after rejection

Rejection can only narrow. Nothing here can grant.

| field | value | owner |
|---|---|---|
| `candidate_effect_authored` | `true` | this phase |
| `candidate_effect_status` | `no_op` | this phase |
| `candidate_effect_accepted` | `false` | this phase |
| `candidate_effect_rejection_reason` | `no_op_candidate` | this phase |
| `needs_escalation` | `true` | narrowed |
| `human_review_eligible` | `false` | narrowed (EXEC.POLICY) |
| `candidate_review_ready` | `false` | narrowed (CANDIDATE.VERIFY) |
| `approval_ready` | `false` | narrowed |
| `execution_authorized` | `false` | EXEC.AUTH, unchanged |
| `final_repository_changed` | `false` | EXEC.AUTH, unchanged |

The last two are **not** written by this phase. They come back false through the
existing no-execution path, because `needs_escalation=true` and the removed
candidate already terminate every write branch.

## Visibility without usability

The model's authored bytes stay inspectable under the harness-owned key
`candidate_effect_rejected_candidate`, so the output remains explainable. The
`patch_candidate` and `patch_plan` fields are cleared, so nothing downstream can
present it as a usable patch. User-facing semantics are *the model proposed no
repository change* — never *verified patch ready for review*.

## No fabricated evidence

Because the producers did not run, a rejected payload carries none of
`sandbox_apply_status`, `candidate_validation_status`, `post_probe_result`,
`paired_status`, `targeted_validation_status`, `check_oracle_assessment_status`
or `candidate_verification_status`. A test asserts each one is absent.
CANDIDATE.VERIFY.LIVE.1 semantics for real candidates remain frozen.

## Multi-operation policy is narrow on purpose

| candidate | outcome |
|---|---|
| all operations exact-no-op | reject as `no_op_candidate` |
| at least one operation differs | continue unchanged |
| byte sides not both available | `undetermined`, never `no_op` |

A mixed candidate has real mutation effect, so the model's operations stand:
none is dropped, rewritten or reordered, and no mixed-op rejection policy is
introduced. `exact_no_op_operation_count` is exposed as telemetry instead.
`undetermined` fails open, because rejection is the aggressive action and an
unprovable operation must never trigger it.

## Reuse, not new primitives

* Bytes come from `candidate_plan_from_payload` — the same bounded
  representation patch safety and the candidate pipeline already consume. No
  repository re-read, no traversal, no new scan.
* Candidate identity comes from the existing `patch_plan_fingerprint`. No second
  fingerprint subsystem was introduced or moved.
* The evaluator imports only `__future__`, `dataclasses`, `hashlib`, `json`,
  `time` and `typing`. Two AST tests pin that it opens no file, spawns no
  process and reaches no network.

## ANSWER.GROUND.LIVE.4 compatibility

The new telemetry is harness-authored control-plane state. Every new key sits
outside `_ANSWER_SURFACE_KEYS`, so the LIVE.4 ownership boundary returns it by
identity. A regression grounds a rejected payload and asserts every harness
field — the nested receipt's `phase_id` included — is value-identical across the
display boundary, so the new status and reason identifiers cannot become another
fabricated repository entity.

## The controls that matter most

**Negative control (§14).** The known semantically *wrong* branch-reorder
candidate changes bytes. It passes this gate untouched and is still rejected by
CANDIDATE.VERIFY.LIVE.1 on behavioral evidence — primary `fixed`, preservation
`regressed`. This is proved by a live end-to-end run through the real
`maybe_run_auto_patch`, with the producers wrapped in delegating counters rather
than stubs, so "the gate did not swallow it" and "the pipeline still judged it"
are established by the same execution.

**PATCH.MINIMAL.LIVE.1 must not, and does not, replace semantic candidate
verification.**

**Positive control (§15).** The deterministic width-distinguishing candidate
likewise passes the gate and continues into normal verification.

## Boundaries

No change to core retrieval semantics, CONTROL localization or ranking,
`BehavioralExpectation` extraction, probe execution, paired probe behavior,
targeted validation selection, validation budgets, candidate verification
reducer semantics for real candidates, model or provider calls, network,
repository traversal, or authority setters.
