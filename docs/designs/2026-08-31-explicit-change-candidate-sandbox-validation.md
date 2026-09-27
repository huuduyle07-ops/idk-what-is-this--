# OPS.PATCH.2 — Explicit-Change Candidate Sandbox Validation

**Track:** OPS · **Status:** complete · **Prerequisite:** PATCH.BASIS.LIVE.1
**Also frozen:** OPS.PATCH.1, OPS.VALIDATE.1, CONTROL.SAFETY.LIVE.1, WAITER.LIVE.1

## What went wrong

The post-PATCH.BASIS six-task black-box rerun exercised an explicit change
request against a small task-manager repository. Everything upstream behaved:

- WAITER.LIVE.1 routed it as `explicit_change`;
- PATCH.BASIS.LIVE.1 gave it a legitimate `explicit_change_request` basis;
- target/source grounding accepted its targets;
- patch safety passed.

The final two-operation plan it then presented for human approval was
internally incoherent:

| file | in the plan |
| --- | --- |
| `store.py` | passes `priority=priority` into `Task(...)` |
| `filters.py` | reads `t.priority` |
| `models.py` | **unchanged** |
| `cli.py` | **unchanged** |

Applying that exact plan to a disposable copy failed every existing test:

```
TypeError: Task.__init__() got an unexpected keyword argument 'priority'
```

The same user task had produced a correct five-operation plan in an earlier
run; a later reviewer/refinement step degraded it. No production gate ran the
final plan anywhere before describing it as approval-ready.

## The distinction this phase preserves

Four questions, four owners:

| question | owner |
| --- | --- |
| Why consider this patch? | `core/patch_basis.py` (`patch_basis`) |
| Where may it operate? | target/source grounding in `core/control_engine.py` |
| **Is the candidate materializable and valid?** | **`core/candidate_sandbox_validation.py`** |
| May it write to the real repository? | patch safety, runtime authority, human approval |

OPS.PATCH.2 owns the third and only the third. In particular:

```
candidate_validation = passed   !=   write_authority
```

## The final-candidate boundary

The path traced before any edit:

```
draft response
    ↓
reviewer / refine step          (run_review_pipeline)
    ↓
final authoritative patch_plan  (state.json_block)
    ↓
PATCH.BASIS                     (enforce_control_grounding_on_payload)
    ↓
source grounding                (target_source_grounded / change_scope_grounded)
    ↓
patch safety                    (evaluate_patch_safety)
    ↓
human-review / apply handoff    (_record_patch_safety_handoff)  ← LAST STABLE POINT
```

`core/pipeline.py::_record_patch_safety_handoff` is the last point at which an
explicit-change candidate is stable. The payload there is exactly what the
human is handed; nothing downstream rewrites it. It has two call sites — the
`patch_plan` branch and the single `patch_candidate` branch — and both now pass
the validation command the run already selected.

Sandbox validation runs **there**, and only after patch safety has passed.

## Scope

`task_shape = explicit_change` with `patch_basis = explicit_change_request`.

A `grounded_defect` that reaches the same handoff (low confidence, or the
`vibe` style, where `auto_apply_allowed` is always false) keeps its existing
behaviour untouched, and the working grounded-defect auto-apply path never
arrives here at all. `analysis_only` and `needs_clarification` create no
sandbox, apply no patch and run no validation.

## Reused machinery

Nothing new was built where something existed:

| need | reused |
| --- | --- |
| disposable repository | `core.sandbox_self_evolution_runner.create_managed_sandbox` / `cleanup_managed_sandbox` |
| patch application | `patching.patch_plan_executor.apply_patch_plan` |
| validation command | the OPS.VALIDATE.1 string the run already selected, passed in |
| validation vocabulary | `core.validation_outcome` (`passed` / `failed` / `inconclusive`) |
| fingerprint | the existing canonical-JSON sha256 idiom |

No `sandbox_v2`, no `feature_clone_engine`, no `candidate_virtual_repo`, and no
new cryptographic subsystem.

`apply_patch_plan` is called once with the validation command, so apply and
validation share one measured timing span. Splitting them would mean
re-implementing OPS.VALIDATE.1's classification here, which is exactly the
duplication this phase avoids.

## No git mutation

No `git stash`, `git reset` or `git clean` appears anywhere in the path — a
test asserts this against the module's executable source with docstrings
stripped. The sandbox is a copy of the working tree **as it stands**, which is
the state the candidate was produced against, not an unrelated `HEAD` checkout.
Unrelated user work in a dirty worktree survives exactly.

## The three-way answer

| status | meaning |
| --- | --- |
| `passed` | candidate materialized, meaningful validation ran, validation passed |
| `failed` | candidate could not be applied, or validation actually failed |
| `inconclusive` | no command, no candidate, zero tests, tool unavailable, sandbox unavailable |

Fail closed: if a safe sandbox cannot be materialized, the answer is
`inconclusive`, never `passed`. There is no score, no confidence and no
regression delta.

`approval_ready` is true only for `passed`. `reviewable` is always true — a
failed candidate keeps its diagnostics, because reading the `TypeError` is the
entire point of having run it.

## Candidate identity

`candidate_validation_fingerprint` is a sha256 over the canonical JSON of the
plan's materially-significant operations (`op`, path, `target_snippet`,
`patched_snippet`, `content`). `file` and `relative_path` normalize to the same
key, so the two spellings of one path are one candidate.

A refinement that rewrites the plan changes the fingerprint. The stored verdict
stops matching, and `_drop_stale_candidate_validation` removes the stale keys at
the top of `maybe_run_auto_patch` rather than letting a verdict travel forward
attached to a plan it never described. There is no path by which an earlier
`passed` is silently reused.

## What this phase deliberately does not do

- **It does not fix the reviewer.** A degraded refinement is contained, not
  repaired: the refined candidate must pass its own validation.
- **It does not resurrect the draft.** A failing refinement next to a passing
  earlier draft blocks the handoff; it does not swap the draft back in. That
  would be a new validation-based plan-selection policy.
- **It does not prove goal fidelity.** Passing the repository's existing tests
  is a coherence/regression fact. Old tests know nothing about a requested CLI
  flag, list column or filter. CHECK.2 remains unwired.
- **It does not generate tests, install dependencies, call a model or touch the
  network.** Model-call delta: zero. Network delta: zero.
- **It does not change timeout semantics.** Timeout classification keeps its
  existing OPS.VALIDATE.1 behaviour; OPS.VALIDATE.2 owns that.
- **It does not fix the execution-authority telemetry bug.** The same rerun
  found T1/T2/T3 payloads reporting `write_authority=false` while files had
  actually been written. That is `EXEC.AUTH.LIVE.1 — Execution Authority &
  Outcome Telemetry Reconciliation`, the immediate next phase.

## Ordering

```
patch basis → target/source grounding → patch safety
    → sandbox materialization → validation
```

A test-path rewrite and an arbitrary/unrequested target are refused before any
sandbox exists. Sandbox validation cannot be used to legitimise a path the
earlier gates reject, even if the corrupted test would have passed.

## Isolation

The real repository is byte-identical before and after, whether the candidate
passes or fails. Validation side effects (`__pycache__`, `.pytest_cache`, build
output) live and die inside the disposable sandbox and are never copied back.
Cleanup failure may leave a temp directory but never mutates the source
repository. OPS.PATCH.1 byte semantics hold in the sandbox path: a CRLF file
keeps CRLF, and only the requested replacement differs.

## Telemetry

Bounded categorical facts, no secrets, no full validation log:

```
candidate_validation_status              passed | failed | inconclusive
candidate_validation_category
candidate_validation_command
candidate_validation_fingerprint
candidate_validation_inconclusive_reason
candidate_validation_reviewable
candidate_validation_output_excerpt      (tail-capped)
candidate_validation_timings             sandbox_create / apply+validation / cleanup / total
baseline_validation_status               passed | failed | inconclusive | unavailable
baseline_validation_category
sandbox_apply_status                     not_attempted | applied | failed | sandbox_unavailable
sandbox_apply_error
approval_ready
```

Historical explicit-change artifacts carry none of these keys. They read back as
`legacy_unvalidated`, never `passed`, and are not rewritten.

## Baseline

The baseline is the run's **existing** preflight outcome, read rather than
re-run, so the phase adds exactly one validation execution. `baseline = passed`
next to `candidate = failed` reads as a plain regression. `baseline = failed`
and `baseline = inconclusive` are preserved as their own facts; no "no worse
than baseline" equivalence is attempted, and the candidate is still not
approval-ready.

## Cost

For the T4-class small repository, measured end to end:

| stage | incoherent candidate | coherent candidate |
| --- | --- | --- |
| sandbox creation | ~0.007 s | ~0.004 s |
| apply + validation | ~1.04 s | ~0.69 s |
| cleanup | ~0.003 s | ~0.003 s |
| **total** | **~1.05 s** | **~0.70 s** |

No such promise is made for large repositories: the sandbox copy is
proportional to the tree. No second repository analysis, index build or graph
traversal was added — only the copy the existing sandbox mechanism performs.

## Wording

A candidate is never called clean, validated, working or ready to apply unless
it passed. Failed reads: *"Candidate materialized in a disposable sandbox but
failed repository validation. It has not been applied to the real
repository."* Inconclusive reads: *"Candidate validation could not establish
success."*
