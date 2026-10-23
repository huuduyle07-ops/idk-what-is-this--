# SYNTH.AUTH.LIFECYCLE.1 — single-use synthetic runtime execution lease

2026-10-08 KST. **`SYNTH_AUTH_LIFECYCLE_1_COMPLETE`**.

The additive owner `core/synthetic_runtime_authorization_lifecycle.py` gives one
live SYNTH.AUTH.1 authorization at most one process-local execution lease. The
recorded proof authenticates one fresh pair, rejects duplicate lease issuance,
passes the pure executor compatibility predicate, and leaves the lease ISSUED.
It performs no Java, reflection, behavioral, container, process, network, shell,
repository-write, or Apply effect. No operational executor retry was performed.

| Requested report item | Recorded result |
| --- | --- |
| 1. Final status | `SYNTH_AUTH_LIFECYCLE_1_COMPLETE` |
| 2. Supported lifecycle scope count | 1 |
| 3. Upstream authorization identity / fingerprint | `1bfa89303a45ff780fb4a378da97c7a602bc60f6bb3d79010b8948fc8387a45e` / `fdc5c5a36a17b2fe327ef8f55761613a71e2953f5e27897aec415f2c62483ba0` |
| 4. Lifecycle lease identity / fingerprint | `7f0c790d1e5c19a0f80f709da67a33b598eabe17fdaca4b7b9ea3f057e675c89` / `e38b01fcbcc66f76a2dfc1821d6936d1ed17ea7fc5a14801418f6460997110c2` |
| 5. Exact scenario binding | `PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R`; `synthetic.EXECUTOR.1R.decrement_3`; `phase_owned_synthetic_fixture`; source SHA-256 `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302`; `SyntheticStateBox.decrement(3)` |
| 6. Duplicate lease issuance | Rejected: `synthetic_runtime_authorization_already_leased`; no second lease |
| 7. Initial lifecycle state | `ISSUED` |
| 8. Pure test consumption | `ISSUED -> CONSUMED` succeeds; the same lease remains authentic historical evidence |
| 9. Second consumption | Rejected: `synthetic_runtime_lease_not_issued`, reason `CONSUMED` |
| 10. Invalidation | `ISSUED -> INVALIDATED`; terminal; cannot consume, invalidate again, or issue another lease for that authorization |
| 11. Atomicity | One process-local `threading.Lock`; authentication, state check, signing and registry-record replacement share the critical section |
| 12. Live-object authentication | Exact lease type and weak identity, retained exact upstream object, public SYNTH.AUTH.1 validation, issuing PID, independent HMAC-SHA256 |
| 13. Copy / reconstruction | Copies, dataclasses.replace, manual matching constructors, JSON, reports, fingerprint-only, subclass and wrapper inputs rejected in all three states |
| 14. Process / key change | Rejected for validation, compatibility and consumption; foreign process rejected before acquiring an inherited lock |
| 15. Executor compatibility predicate | `synthetic_runtime_execution_lease_satisfies_executor(lease, authorization)` authenticates both, exact scope and ISSUED state; consumes nothing |
| 16. Final strict proof lease state | `ISSUED`; unconsumed |
| 17. Strict proof runtime authorizations consumed | 0 synthetic; 0 real; the immutable upstream still reports its original issued state and consumed count 0 |
| 18. Test-only lease consumptions | 32 in the final recorded focused suite, using separate fresh test pairs; 0 in the strict proof |
| 19. Java compile count | 0 |
| 20. JVM count | 0 |
| 21. Reflection execution count | 0 |
| 22. Behavioral execution count | 0 |
| 23. Container / Docker / child-process / network / shell counts | 0 / 0 / 0 / 0 / 0; thread starts 0; source projection false |
| 24. BANK execution count | 0 |
| 25. Real runtime authority consumed | 0 |
| 26. Historical byte preservation | 1,800 / 1,800 pre-existing non-ignored files unchanged; eight already missing paths remain missing; prior SYNTH.AUTH.1 134-file and SYNTH.REFLECT.1 139-file protected manifests also match |
| 27. Baseline versus after failures | The same 12 exact registry/reversal/recommendation identities; no new failure identities; no registry projection, repinning or historical edits |
| 28. Validation | 604 focused tests pass; remaining results and exact failure identities below |

## Owner contract

The public lease dataclass is frozen. Its immutable issuance projection contains
the upstream issuance ID and fingerprint, exact scenario and invocation, source
kind and hash, lease ID, PID, schema, issuer phase, initial state and authority
flags. The owner's private frozen record signs that canonical projection together
with the current lifecycle state. Consumption replaces the record under the lock;
it never mutates the upstream authorization or relies on a public field/counter.
The lease fingerprint identifies the immutable issuance and remains stable after
consumption. The current state is separately authenticated in the owner's registry.

`validate_synthetic_runtime_execution_lease` accepts authentic ISSUED, CONSUMED
and INVALIDATED historical handles. `synthetic_runtime_execution_lease_state`,
`lease_is_issued` and `lease_is_consumed` distinguish authenticity from readiness.
Inspection can omit the upstream argument and authenticate the owner's retained
upstream handle. The executor predicate and consumption require the exact supplied
live upstream object. A lease cannot replace SYNTH.AUTH.1.

The registry uses only authenticated upstream issuance keys and owner-generated
random lease IDs. It retains upstream identity and terminal/dead-lease tombstones
for the process lifetime. Collecting an issued, consumed or invalidated lease does
not allow reissuance. There is no reset, replay, restore, refund or persistence API.
JSON exports contain no key, signature, registry record or restorable capability.

The lease exposes `synthetic_runtime_execution_lease=true`. Runtime, real-task
runtime, repository write, Apply, network, host mounts, shell, arbitrary command
and reflection authority remain false. Consumption cannot widen any of these.
SYNTH.REFLECT.ADMIT.1 and its consumption domain remain frozen and separate.

The focused tests enumerate all six valid schedules for two callers performing
prechecks then consumption, including both prechecks succeeding before one caller
consumes. Exactly one transition succeeds. They also check real lock ownership
during authentication and registry commits, consumption versus invalidation,
dead-handle reissuance, terminal-state tampering, and process/key rejection. These
are pure state-machine tests; they start no threads and do not exercise live
thread contention.

## Future consumption boundary and failure semantics

The future executor must authenticate the synthetic authorization, both reflection
requests/admissions, SANDBOX.2 and JAVA.1, and establish exact source/harness
readiness before consuming. Consumption occurs immediately before the first
behavioral runtime effect. The compatibility predicate is only a precheck;
consumption repeats authentication under the transition lock.

A failure before consumption may leave the lease ISSUED. A failure after the
successful transition always leaves it CONSUMED, including launch, reflection,
invocation, protocol, timeout and cleanup failures. There is no refund.

The frozen EXECUTOR.1 and EXECUTOR.1R paths stop before compilation and expose no
established lifecycle consumption boundary. Structural compilation remains
separate diagnostic evidence in VALIDATE.1A. No existing contract classifying
compilation as runtime activation was identified, and this phase grants no compile
permission or changes compilation classification. If a future executor encounters
such a contract, it must report the conflict before proceeding; it must not move
the boundary merely to simplify implementation.

## Recorded validation

| Check | Result |
| --- | --- |
| Lifecycle plus SYNTH.AUTH.1, SYNTH.REFLECT.1, SYNTH.REFLECT.ADMIT.1 and blocked EXECUTOR.1R regressions | 604 passed: 113 lifecycle tests plus 491 frozen regressions; 32 separate test-only consumptions |
| SANDBOX.1/2, JAVA.1/A/B/C, Java discovery and current governance pure regressions | 503 passed, 1 pre-existing SANDBOX.1 reversal failure |
| Selected historical EXECUTOR.1, PREFLIGHT.RUNTIME authority-separation and REFLECT.1 pure regressions | 23 passed, 3 pre-existing reversal failures |
| Authority / Apply / path / patch safety | 241 passed, 1 pre-existing registry recommendation failure |
| Exact registry / reversal / recommendation baseline | 292 passed, 12 failed |
| Same selection after lifecycle addition | 292 passed, same 12 failed |
| Benchmarks `--check` | 54 checked, 0 errors, 0 agent calls |
| In-memory Python compilation | 1,212 files, 0 failures; no bytecode output |
| `git diff --check` and all six additive files' whitespace | Passed |
| Historical preservation | All 1,800 recorded pre-existing files retain their exact SHA-256; prior protected manifests match |
| Strict proof effect denial | Active before owner import; denied attempts `{}`; thread starts 0 |

Full-suite green is not claimed. The baseline and after selections read the actual
unchanged registry. The exact existing failures are:

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

Historical coverage uses explicit pure subsets and excludes Java runtime fixtures.
The required frozen blocked-executor regressions exercise their existing stop
gates; they do not attempt a new operational executor retry.

Separate safety fixtures write only temporary repositories. Their existing exact
Python pytest child and four read-only Git command forms are permitted by an audit
guard; other process and network effects are denied. One intentionally failing
validation command was denied and its failure-path regression passed. These fixture
processes, development commands and test runners are outside the strict lifecycle
proof's zero-effect counters.

The replay is `scripts/replay_synth_auth_lifecycle1.py`. The final report-only proof
and validation evidence are `docs/roadmap/SYNTH_AUTH_LIFECYCLE_1_LOCAL.json`.
`docs/roadmap/SYNTH_AUTH_LIFECYCLE_1_PRESERVATION.json` preserves the complete
before-slice hash manifest. Export happens after the strict no-write proof closes.
The recorded final lease was never consumed; exported evidence cannot recreate it.

Work stops after lifecycle proof. No operational EXECUTOR.1R retry or reflection
admission consumption was implemented.
