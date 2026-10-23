# EXECUTOR.1R — retry after lifecycle closure

2026-10-08 KST. **`PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_UNRESOLVED`**. The requested synthetic Java behavioral execution did not occur.

The fresh authority graph authenticates and all three leases remain ISSUED. The first blocker is `java_profile_contract_mismatch`, with existing infrastructure classification `RUNTIME_JAVA_1_BLOCKED_SANDBOX_INCOMPATIBLE`.

SYNTH.AUTH.1 requires the exact tuple `RUNTIME.JAVA.1`, `runtime_java_1_v1` and SANDBOX.2 policy `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75`. The original JAVA.1 receipt has that Java profile/schema but binds SANDBOX.1 policy `855462482bcdd76cd2b52d8cdd40683af1165a47c041d687bc64723acc4e1447`; its public compatibility predicate requires its original sandbox owner. The verified SANDBOX.2 continuation exposes `RUNTIME.JAVA.1C` / `runtime_java_1c_v1`. Its public predicate authenticates that continuation and sandbox pair, without asserting the required JAVA.1 schema mapping. No public owner-defined bridge was found.

This is a pure contract conflict, not a fresh infrastructure measurement. No profile was relabeled, policy weakened, capability reconstructed or historical receipt imported. The additive retry stops before infrastructure refresh, rendering, projection, compilation or lease consumption. Resolving the exact issuer contract is prerequisite work; this retry does not change frozen owners.

[Full report and live-process authentication results](PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_LIFECYCLE_RETRY_LOCAL.json). [Historical preservation manifest](PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_LIFECYCLE_RETRY_PRESERVATION.json). Exported JSON is report-only and restores no live authority.

| Required item | Result |
| --- | --- |
| 1. Final typed status | PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_UNRESOLVED |
| 2. Authorization ID / fingerprint | ca6adc1661329a159452160923afe8cffe9fc1e75adc604a8dc4f568fe5bee5a / d49b91970ed043155fdecf8770d3e44b8701e66d0a8917e783c698622779e02c |
| 3. Runtime lease ID / fingerprint | 73eb69acc7f7fd008d142e8d13d5658d43936011e7c238c05f7d49486954e0ac / f1fd7470b2cd4a8ec4208d990aea9f234cbe8a3f8258dc91d387a9ada03609b6 |
| 4. Runtime initial / final state | ISSUED / ISSUED; consumed = 0 |
| 5. BEFORE request / admission / lease IDs | 9ba9b98d79caa9ce119d63d22d4f4ed66f1ead5ba991b38d32372a4e22ec4e78 / 8d64fd8dc5684f621e0a75224e5f81b94dc91cdd7d5d2d39e7bfb109d368dad9 / 0c3b7fb390ab1ed3c962896a65ea96d9675d21412d033a64cdc439c26bb94d59 |
| 6. AFTER request / admission / lease IDs | 8bdd89e963d86bb246ca7d07825279ccf96a2e8b90d96c81a13e5cc2a0f1f7dc / f3c4314b1c12f8d97a955042780a9a497992b7d761f4368ac63373017fe3920a / 6fd7b2010b19a0cb543368fca9ed920807cab754edabdfc9b554dc9e5491f3fd |
| 7. One activation proof | All authorization IDs/fingerprints agree; both read leases bind the exact runtime ID/fingerprint above; all eight owner validators and three pure prechecks passed. |
| 8. SANDBOX.2 fresh authentication | Not attempted: pure Java contract gate stopped before Docker. No historical JSON used as authority. |
| 9. JAVA.1 fresh authentication | Not attempted: no compatible frozen issuer for the exact required profile/schema/policy tuple. |
| 10. Java compatibility | BLOCKED: JAVA.1 receipt binds SANDBOX.1 policy; JAVA.1C receipt has runtime_java_1c_v1, not required runtime_java_1_v1. |
| 11. Source SHA-256 / size | 813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302 / 239 bytes; exact owner source authenticated, never projected. |
| 12. Harness SHA-256 | null; not rendered after readiness gate failed. |
| 13. Compile argv / result | null / not attempted; compiler PID, exit and captured streams unmeasured. |
| 14. Class manifest / hashes | null; no classes created. |
| 15. Runtime argv / result | null / not attempted; JVM PID, exit and captured streams unmeasured. |
| 16. Runtime lease consumption point | None; left ISSUED. |
| 17. BEFORE lease consumption point | None; left ISSUED. |
| 18. AFTER lease consumption point | None; left ISSUED. |
| 19. Measured BEFORE | null; 10 remains an expectation. |
| 20. Measured direct boolean return | null; true remains an expectation. |
| 21. Measured AFTER | null; 7 remains an expectation. |
| 22. Fixture comparison | Not performed; no measurements exist. |
| 23. Reflection executions | 0 |
| 24. Public method invocations | 0 |
| 25. Synthetic behavioral executions | 0; requested bounded behavioral execution was not reached. |
| 26. BANK executions | 0 |
| 27. Real runtime authorizations consumed | 0 |
| 28. Timeout / output-bound status | Unmeasured; no compiler/JVM or runtime output. |
| 29. Controller Thread.start attempts | 0; strict denial recorded no attempts. |
| 30. Cleanup status | Not required; no runtime resources created, source/classes projected or controller workspace created. |
| 31. Remaining phase containers | null; not queried because no Docker calls occurred. Phase containers created = 0. |
| 32. Runtime receipt fingerprint | null; no positive runtime evidence receipt issued. |
| 33. Historical preservation | All 1,812 pre-existing files byte-identical; eight already-missing paths still missing; prior 1,806- and 1,800-file manifests verified. |
| 34. Baseline versus after failures | Same 12 distinct existing identities; no new identities; no historical repinning. |
| 35. Validation summary | 46 new tests pass; 801 synthetic/blocked regressions pass; adjacent results below. 54 benchmark checks, in-memory Python compilation and whitespace checks pass. Full suite not run. |

All authority fields remain false: real task/runtime, repository write, Apply, network, host mount, shell, arbitrary command, generic reflection, field write, enumeration, private method, constructor reflection and arbitrary class loading.

The strict recorded retry issued one synthetic authorization, one runtime execution lease, one BEFORE lease and one AFTER lease. All consumption counts are zero. Model/author calls, runtime repository writes, Apply actions, network, console/PTY, child processes and Docker calls are zero. The strict guard reports `{}` denied attempts. Development and unit-test handle issuances are separate, effect-free processes/fixtures and are not replayed operational executions.

| Validation selection | Baseline | After |
| --- | --- | --- |
| New operational stop gate | Not present | 46 passed |
| Synthetic owners, lifecycles and historical EXECUTOR.1R | 801 passed, 0 failed | 801 passed, 0 failed |
| Historical EXECUTOR.1 / PREFLIGHT / REFLECT pure subset | 23 passed, 3 failed | 23 passed, 3 failed |
| SANDBOX.1/2 and JAVA.1/A/B/C pure subset | 498 passed, 1 failed, 5 deselected | 498 passed, 1 failed, 5 deselected |
| Authority / Apply / path / patch safety | 241 passed, 1 failed | 241 passed, 1 failed |
| Registry / picker / historical reversal | 292 passed, 12 failed | 292 passed, 12 failed |

The five deselections are the prior historical reader-thread tests, not silent skips. Safety tests operate only on temporary fixture repositories and allow their exact Python pytest child and four read-only Git commands; those development fixtures do not exercise the operational retry. An initial safety baseline hit the Windows pipe-thread denial; the corrected baseline and after selections both record the same one existing failure. No registry snapshot projection was used.

Benchmark configuration check: 54 checked, zero errors, zero agent calls. In-memory `compile(bytes, path, "exec")`: 1218 project Python files, zero failures, no bytecode emission; benchmark input fixtures excluded. `git diff --check` and additive-file whitespace checks passed. The full test suite was not run.

Exact distinct baseline and after failure identities:

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

Only additive retry source, replay, tests and these new evidence files were added. Original EXECUTOR.1, EXECUTOR.1R preflight, authorization-blocked retry, lifecycle owners, sandbox/Java owners, historical tests, registry and all existing reports remain byte-identical. Work stops with the Java profile contract unresolved; no real candidate execution or BANK run follows.
