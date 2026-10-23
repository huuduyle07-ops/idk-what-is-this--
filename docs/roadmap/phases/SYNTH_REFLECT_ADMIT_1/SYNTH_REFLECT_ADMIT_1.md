# SYNTH.REFLECT.ADMIT.1 — exact read-only reflection execution admission

2026-10-08 KST. **`SYNTH_REFLECT_ADMIT_1_COMPLETE`** proves that exactly two
SYNTH.REFLECT.1 reads may be admitted when each is bound to a fresh live
SYNTH.AUTH.1 authorization and a fresh live SYNTH.REFLECT.1 request. The proof
does not execute reflection, run Java, create a container, or consume either
upstream authorization.

| Requested report item | Result |
| --- | --- |
| 1. Supported admissions | Exactly 2: one per SYNTH.REFLECT.1 role |
| 2. Before admission identity | `a461458b0599a519c9ab1881dd73433eeb06879c8e4064975660c2b8136386d0` |
| 3. After admission identity | `2aff017aadbfa5e05a26c465c5f2df4438af03e7ecc5d02c058b89bdfe1a4dc4` |
| 4. Source SHA-256 | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` |
| 5. Definition SHA-256 | `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` |
| 6. Owner / member / primitive type | `SyntheticStateBox` / `value` / `int` |
| 7. Allowed operation | `read_exact_bound_field` |
| 8. Role separation | Enforced; before and after admissions bind different request and authorization issuance identities |
| 9. SYNTH.AUTH.1 compatibility | Both admissions validate against a fresh authenticated `synthetic.EXECUTOR.1R.decrement_3` handle for `SyntheticStateBox.decrement(3)` |
| 10. SYNTH.REFLECT.1 compatibility | Both fresh factory requests validate; their role, target, source, definition, operation, and fixed renderer output are bound |
| 11. Synthetic reflection execution authority | true, subordinate to the separate synthetic runtime authorization |
| 12. Real runtime authority | false |
| 13. Field-write authority | false |
| 14. Enumeration authority | false |
| 15. Private-method authority | false |
| 16. Constructor-reflection authority | false |
| 17. Arbitrary-class-loading authority | false |
| 18. Consumption semantics | Not implemented here. Future executor consumption is single-use, in the executor's issuing process, immediately before the exact read; no replay after a successful read. A failure before a reflection effect may remain unconsumed. Exported receipts cannot restore a handle. |
| 19. Synthetic authorization consumed | 0 |
| 20. Reflection admissions consumed | 0 |
| 21. Java compile count | 0 |
| 22. JVM execution count | 0 |
| 23. Reflection execution count | 0 |
| 24. Containers created | 0 |
| 25. Effect denial | Strict guard active; denied attempts `{}`; Java, JVM, reflection, container, Docker, network, shell, and child-process counts are all 0 |
| 26. Historical preservation | 134/134 SYNTH.AUTH.1 protected-file hashes and 139/139 SYNTH.REFLECT.1 protected-file hashes still match their prior manifests. Registry and reversal files were not edited. |
| 27. Validation | Focused admission: 79 passed. SYNTH.AUTH.1 + SYNTH.REFLECT.1 + EXECUTOR.1R blocked preflight: 385 passed. PREFLIGHT.RUNTIME.1 and pure historical REFLECT.1 subset: 151 passed, 2 reversal checks blocked by the pre-existing registry bytes. Authority/Apply/path/patch-safety: 181 passed, 1 registry reversal check deselected. Registry/picker: 292 passed, 7 expected-count checks fail because the current registry already contains `RUNTIME.JAVA.1`. Frozen sandbox/JAVA governance and discovery: 106 passed. Benchmarks `--check`: 54 passed. In-memory Python compile: 1,262 files. `git diff --check`: passed. |
| 28. Final typed status | `SYNTH_REFLECT_ADMIT_1_COMPLETE` |

`core/synthetic_reflection_execution_admission.py` calls the public validators
for both upstream handles, then also invokes SYNTH.REFLECT.1's public
compatibility predicate. It checks the exact scenario phase and ID, source
kind and hash, SYNTH.AUTH.1 public invocation, complete expected role tuple,
reflection-required flag, and requested owner/member/type/definition. It
accepts no caller role, Java source, renderer string, or target override.

The new immutable `SyntheticReflectionExecutionAdmission` has an independent
process-local HMAC key, random admission ID, issuing PID, complete canonical
projection, and a weak live-identity registry. Each admission stores its
upstream issuance IDs and fingerprints. It also binds the renderer identity
`SYNTH.REFLECT.1.render_synthetic_read_only_reflection` and a fingerprint of
the fixed role-specific helper returned by the authenticated request. The
admission and compatibility validators are pure and do not consume handles.
Copies, exported data, `dataclasses.replace`, reconstruction, tampering,
process changes, and a key change cannot authenticate.

The future executor still needs the separately authorized synthetic runtime
execution to be active. This admission does not launch Java, create a sandbox,
consume SYNTH.AUTH.1, return a measured value, or compare against expected
values. `measured_observations` and `positive_runtime_receipt` remain null.

The proof replay is `scripts/replay_synth_reflect_admit1.py`; its strict guard
is installed before the owner import. Its report-only output is
`docs/roadmap/SYNTH_REFLECT_ADMIT_1_LOCAL.json`. The historic registry and
reversal receipts remain as they were. The reported registry/reversal test
failures arise because the already modified working-tree registry includes
`RUNTIME.JAVA.1`, while earlier frozen tests expect a pre-JAVA snapshot; this
phase did not repin or edit that history.

Work stops at execution admission. EXECUTOR.1R was not retried.
