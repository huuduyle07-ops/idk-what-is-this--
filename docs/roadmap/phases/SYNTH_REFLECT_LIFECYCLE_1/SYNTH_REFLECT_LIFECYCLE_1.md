# SYNTH.REFLECT.LIFECYCLE.1 — single-use synthetic reflection execution leases

2026-10-08 KST. **`SYNTH_REFLECT_LIFECYCLE_1_COMPLETE`**.

The additive owner `core/synthetic_reflection_execution_lifecycle.py` gives each
live authenticated SYNTH.REFLECT.ADMIT.1 admission at most one process-local
reflection execution lease. Exactly two V1 scopes are supported: BEFORE and AFTER
reads of `SyntheticStateBox.value : int`, subordinate to one synthetic runtime
activation. No Java, reflection or operational executor retry was performed.

| Requested report item | Recorded result |
| --- | --- |
| 1. Final status | `SYNTH_REFLECT_LIFECYCLE_1_COMPLETE` |
| 2. Supported scopes | `exact_private_state_before`, `exact_private_state_after`; exactly two V1 scopes |
| 3. Shared runtime lease ID / fingerprint | `ec34f2c70d1a4e602480fe28abb4415669c6022f9feadc57a0ebfc4438694690` / `7b5eca5f552440cef017208cff2d99d29c2f0c3d7fa1e316d97d53526c560939` |
| 4. BEFORE lease ID / fingerprint | `8a746a04a8d18052de3cedbf4e2a2a27be1d275c225ce36c5de77ddde2a0e425` / `bc80929a9642053f285abccbd684496f14301d1bec48c5273eb61d66043bc7de` |
| 5. AFTER lease ID / fingerprint | `18a4faf429328ae2d84f448a67ca773165cb788b5c19f0daf14833bd7b5ca6f8` / `170b51e29eaf656d451fb907db0283fbca315d38545ef3657cd2ccf012a8aec6` |
| 6. Common authorization ID / fingerprint | `d2fc04a5f64615b48574c7dfc7d9b08f89a843ef12b06fa4b3ed0a4156409195` / `f64b1125377f7b6960a54eb8f561c6b684b6a4774a451af4064e41034adac560` |
| 7. Exact source / definition SHA-256 | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` / `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` |
| 8. Owner / member / type / operation | `SyntheticStateBox` / `value` / `int` / `read_exact_bound_field` |
| 9. Role isolation | Explicit expected role required for issuance, prechecks, consumption and invalidation; cross-use rejected both directions |
| 10. Duplicate issuance | `synthetic_reflection_admission_already_leased`; rejected after collection and both terminal states |
| 11. Lifecycle states | `ISSUED`, `CONSUMED`, `INVALIDATED`; only ISSUED to either terminal state is allowed |
| 12. Atomicity | One process-local `threading.Lock`; authenticate, check, sign and registry replacement share the critical section |
| 13. Runtime compatibility | Issuance/precheck: exact runtime ISSUED. Consumption: same exact runtime CONSUMED. INVALIDATED never activates reflection |
| 14. Pure runtime activation tests | 97 test-only runtime consumptions in the new suite; no Java/runtime effect |
| 15. BEFORE consume | Succeeds exactly once after test-only activation; strict proof does not consume |
| 16. AFTER consume | Succeeds exactly once in the same test activation as BEFORE; strict proof does not consume |
| 17. Second consume | Rejected: `synthetic_reflection_lease_not_issued`, reason `CONSUMED` |
| 18. Invalidation | ISSUED to INVALIDATED, even after runtime invalidation; no refund, reset, second invalidation, consume or reissue |
| 19. Copies / reconstruction | Authorization, runtime, request, admission and reflection lease copies, exports, JSON/manual constructors and equal dataclasses rejected |
| 20. Process / key rejection | Foreign PID rejected before inherited lock wait; changed HMAC key in each of five independent owners rejected |
| 21. Pre-execution compatibility | Both strict proof reflection leases pass exact mutual bindings with the one ISSUED runtime lease |
| 22. Final strict runtime state | `ISSUED` |
| 23. Final strict BEFORE state | `ISSUED` |
| 24. Final strict AFTER state | `ISSUED` |
| 25. Strict runtime consumptions | 0 |
| 26. Strict reflection consumptions | 0 |
| 27. Test-only runtime consumptions | 97 in new reflection lifecycle tests; 32 in frozen runtime lifecycle regressions; 129 total in final focused run |
| 28. Test-only reflection consumptions | 37 in final focused run; separate from strict proof |
| 29. Java / JVM / reflection / behavior | 0 / 0 / 0 / 0 in strict proof and pure lifecycle tests |
| 30. Containers / Docker / child process / network / shell / threads | 0 / 0 / 0 / 0 / 0 / 0 in strict proof; source projection false; repository runtime writes and Apply actions 0 |
| 31. BANK execution | 0 |
| 32. Real runtime authority consumed | 0 |
| 33. Historical preservation | All 1,806 pre-existing files byte-identical; eight already-missing paths remain missing; no historical repinning |
| 34. Baseline versus after failures | Same 12 exact distinct registry/reversal/recommendation identities; no new identities |
| 35. Validation | 801 focused tests pass, including 197 new lifecycle tests; details below |

## Capability and lifecycle contract

Each issuance requires the exact live authorization, runtime lease, reflection
request and admission. Each is independently authenticated through its public
owner. The runtime lease must bind the same authorization ID/fingerprint admitted
by the request/admission pair. Both read leases bind that same runtime lease
ID/fingerprint and the exact scenario `synthetic.EXECUTOR.1R.decrement_3` in
`PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R`. Scenario-lease aliases expose the same
immutable runtime identity; the signed fields use `runtime_execution_lease_*`.

The new independent HMAC-SHA256 domain, random lease IDs, issuing PID, weak live
lease identity and retained upstream objects prevent equal values or exports from
recreating capabilities. Permanent per-admission and dead/terminal lease records
prevent reissuance after collection, consumption or invalidation. No reset,
refund, restore, reissue or persistence API exists.

The frozen public issuance projection has an immutable fingerprint. A separate
private frozen record authenticates that projection together with current state.
Consumption replaces this record under the owner lock; it does not edit the
admission or authorization, consume the runtime lease, or widen authority.
Authentic terminal leases remain inspectable as historical evidence.

Only `synthetic_reflection_execution_lease` is true. Runtime, real-task runtime,
repository write, Apply, network, host mounts, shell, arbitrary commands, generic
reflection, field writes, enumeration, private methods, constructors and arbitrary
class loading remain false before and after consumption.

`synthetic_reflection_execution_lease_satisfies_executor` requires both leases
ISSUED. `consumable_during_active_execution` requires the reflection lease ISSUED
and the same runtime lease CONSUMED. Actual consumption reauthenticates all live
objects and role under the lock; a stale precheck never grants a transition.
Issuance eligibility is linearized at the final public runtime ISSUED check while
the reflection lock is held. The frozen runtime owner retains its own lock;
no private upstream lock or registry is accessed. Successful consumption is safe
across that boundary because upstream CONSUMED is terminal. Invalidation may
abandon an ISSUED reflection lease in any authentic runtime state.

## Frozen future executor sequence

1. Authenticate all capabilities and execution gates.
2. Establish source/harness readiness.
3. Consume the scenario runtime lease.
4. Consume the BEFORE reflection lease.
5. Perform the exact BEFORE reflection read.
6. Invoke the exact public `SyntheticStateBox.decrement(3)`.
7. Consume the AFTER reflection lease.
8. Perform the exact AFTER reflection read.

The executor owns read order and public invocation. This lifecycle owner proves
authority and state only; it cannot prove that the method or either read occurred.
A later failure never refunds a spent lease. No executor integration is added.

## Validation and preservation

| Selection | Baseline | After |
| --- | --- | --- |
| Frozen synthetic owners and blocked EXECUTOR.1R | 604 passed | 604 passed plus 197 new tests; 801 total |
| Registry / picker / reversal / recommendation | 292 passed, 12 failed | 292 passed, same 12 failed |
| Historical EXECUTOR.1, PREFLIGHT.RUNTIME authority separation, REFLECT.1 pure subset | 23 passed, 3 failed | 23 passed, same 3 failed |
| SANDBOX.1/2 and JAVA.1/A/B/C discovery/governance pure subset | 498 passed, 1 failed, 5 deselected | 498 passed, same 1 failed, same 5 deselected |
| Authority / Apply / path / patch safety | 241 passed, 1 failed | 241 passed, same 1 failed |
| Benchmarks `--check` | Configuration-only | 54 checked, 0 errors, 0 agent calls |
| In-memory Python compilation | No bytecode emission | 1,272 files, 0 failures |
| `git diff --check` and additive-file whitespace | Checked | Passed |

The new tests enumerate all six two-caller check/consume schedules for each role,
test consume versus invalidate, check real lock ownership during authentication,
signing and commits, and enforce identity/role/state isolation. No contention
threads are started. The final focused run records 97 new test runtime consumptions and
37 reflection consumptions independently of the strict proof's zeros.

Baseline hashes and initial failure identities were captured before implementation.
The initial infrastructure audit denied five historical reader-thread tests; the
final pure selection explicitly excludes those tests. The initial safety audit
also denied Windows command strings until exact fixture-command matching was
corrected. Corrected subset baselines read the byte-identical frozen files.
These initial audit failures are validation-harness limitations, distinct from
the preserved repository baseline failures. No registry snapshot projection or
historical repinning was used, and no frozen owner/test/report was changed.

The exact remaining distinct baseline failures are:

- `tests/test_human_authority_branch_checkpoint.py::test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1 [call]`
- `tests/test_patch_candidate_behavior_executor1.py::test_bookkeeping_reversal_preserves_exact_frozen_receipts [call]`
- `tests/test_patch_candidate_behavior_reflect1.py::test_bookkeeping_reversal_preserves_frozen_prerequisite_entry_receipts [call]`
- `tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation [call]`
- `tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets [call]`
- `tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked [call]`
- `tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call [call]`
- `tests/test_phase_registry.py::test_seed_registry_has_expected_phases [call]`
- `tests/test_phase_registry.py::test_seed_registry_is_conservative [call]`
- `tests/test_phase_registry.py::test_seed_registry_summary_counts [call]`
- `tests/test_preflight_runtime1.py::test_bookkeeping_reversal_preserves_frozen_receipts [call]`
- `tests/test_runtime_sandbox1.py::test_maintenance_reverses_only_exact_additive_bookkeeping [call]`

The complete preservation manifest retains SHA-256 for all 1,806 pre-existing
non-ignored files, including unrelated working-tree edits. It also rechecks the
prior 1,800-file runtime lifecycle manifest and the 134-file SYNTH.AUTH.1 and
139-file SYNTH.REFLECT.1 protected manifests. All match exactly.

The replay `scripts/replay_synth_reflect_lifecycle1.py` installs strict effect
denial before importing the owner and denies thread starts throughout. Its denied
attempts are `{}`. Evidence exports and development/test commands occur outside
the strict proof. Separate safety fixtures use temporary repositories and permit
only their exact Python pytest child and four read-only Git commands; other
process/network effects are denied. One deliberately failing validation child
is denied and its failure-path test passes. Those fixture processes do not enter
the strict proof counters.

`SYNTH_REFLECT_LIFECYCLE_1_LOCAL.json` contains the report-only strict proof,
separate test-only counters, exact baseline/after failure identities and validation
selections. `SYNTH_REFLECT_LIFECYCLE_1_PRESERVATION.json` contains the before-slice
hash manifest. Exported evidence cannot recreate live authority after the issuing
process exits. All three recorded final leases were left ISSUED and unconsumed.

Work stops after lifecycle proof. EXECUTOR.1R was not retried operationally.
