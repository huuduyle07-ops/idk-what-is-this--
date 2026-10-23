# PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1

Outcome: **runtime_executor_capability_incomplete**. This phase is registered
as active with blocked risk. It does not claim a completed executor capability.
The user's isolation stop condition applies: an exact synthetic authorization
can reach a validated blocked execution receipt, but no candidate Java runs.
Real BANK still returns `diagnostic_execution_authority_missing`.

The additive consumer is `core/behavioral_diagnostic_executor.py`. It validates
PREFLIGHT.RUNTIME.1 against fresh exact supplied parents, preserves exact
scenario bindings and issues immutable authenticated blocked receipts. There
is no unsandboxed fallback, hidden execution setting, arbitrary command,
public harness renderer or actual candidate reflection issuance seam.

## Why execution stops

The frozen `RuntimeDiagnosticEffectBoundary` calls its prohibitions
**mandatory future enforcement**. It forbids network use, arbitrary filesystem
effects, environment inspection and spawning processes beyond the fixed
adapter. Frozen EXEC.ADMIT.1 also requires timeout/output bounds, cleanup,
exact virtual bytes and an ephemeral workspace, while explicitly recording
hard filesystem/network isolation as unavailable. Both owners remain frozen.

No verified candidate sandbox adapter exists in this project. Changing cwd,
sanitizing environment variables or copying sources into a temporary directory
cannot prevent arbitrary Java filesystem/network effects. The inspected local
JDK release file identifies Java 26.0.2.1; no Java process was needed to read it.
Java's Security Manager cannot supply this boundary: it was permanently
disabled in JDK 24. [Oracle's primary documentation](https://docs.oracle.com/en/java/javase/24/security/security-manager-is-permanently-disabled.html)
describes that restriction.

The new owner therefore stops before tool resolution, temporary workspace
creation, source projection, harness generation, compilation or JVM launch.
It does not relax the frozen policy or accept caller assertions about sandbox
availability. The first remaining synthetic blocker is a verified OS-enforced
candidate runtime boundary. Real operational authority and deterministic
console remain separate future capabilities.

## Receipt and authenticity

`BehavioralDiagnosticExecutionReceipt` is frozen and recursively immutable.
Its schema is `patch_candidate_behavior_executor_1_v1`. It binds authorization,
EXEC.PLAN, SPEC, materialization, candidate, compile receipt and repository
fingerprints; one exact scenario; constructor/setup/action identities and
fixture values; exact observation targets and authorized REFLECT requests;
virtual input hashes and sizes; and the unavailable executor descriptor.

Blocked receipts distinguish `diagnostic_execution_authority_missing`,
`runtime_executor_console_unavailable` and
`runtime_executor_capability_incomplete`. Missing, forged or stale authorization
raises `executor_authorization_missing`, with the original authorization error
in its reason and zero Java/javac counts. An unknown scenario cannot become an
execution target. A planned but unselected scenario stays unauthorized.

No constructor/action result, output, exit status, compiler/JVM identity,
harness hash or runtime observation is fabricated. These fields are explicitly
empty or absent-valued; the receipt records that no workspace was projected.
Supporting-file entries are labelled bound inputs not projected into a runtime
workspace. Their frozen source hashes and all virtual after-bytes are freshly
validated by the authorization parent's reconstruction.

The executor signs only its blocked facts with a private process-local HMAC.
The signature is omitted from JSON and the semantic fingerprint. Exported JSON
is report-only, not replayable authenticated evidence. The pure
`validate_behavioral_diagnostic_execution_receipt` verifies local issuance,
fresh authorization, exact input hashes, descriptor and exact invocation/read
set, then compares the complete canonical blocked facts. Edited observations,
authority fields or copied signatures reject. The public receipt constructor
cannot create authenticated provenance. Historical objects retain their bytes;
validation against changed parents rejects without rewriting old evidence.

This authenticates a blocked decision only. Actual candidate-runtime reflection
observation issuance is unavailable. Frozen REFLECT.1 permits only synthetic
infrastructure provenance and is preserved; it is not relabelled as candidate
execution. No behavioral oracle is evaluated and no pass/correctness field
exists in the new receipt.

## Changed files

| File | Purpose |
| --- | --- |
| `core/behavioral_diagnostic_executor.py` | Authorization-first consumer, truthful unavailable descriptor, immutable authenticated blocked receipt and pure validator. |
| `tests/test_patch_candidate_behavior_executor1.py` | Exact authority, scope, freshness, provenance, immutable facts and zero-effect regression matrix. |
| `scripts/replay_patch_candidate_behavior_executor1.py` | Guarded synthetic blocked replay, negatives and separate stage timings. |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1.md` | Outcome, requested report index and evidence limits. |
| `docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1_SYNTHETIC.json` | Measured synthetic blocked receipts and replay evidence. |
| `docs/roadmap/phase_registry.json` | One narrow active CONTROL phase with blocked risk. |
| `tests/test_phase_registry.py` | Updated counts and exact blocked phase metadata. |
| `tests/test_phase_picker.py` | Blocked bucket membership and unchanged recommendation. |
| `tests/_patch_candidate_behavior_executor1_maintenance.py` | Exact additive reversal of this phase's bookkeeping. |
| `tests/fixtures/patch_candidate_behavior_executor1_reversal.json` | Current entry/post hashes only, preserving old receipts. |
| `tests/_preflight_runtime1_maintenance.py` | Unwrap this phase before the existing frozen reversal chain. |

Pre-existing workspace changes are preserved. No stash/reset/clean, MainApp
change, Apply, runtime approval UI or real BANK consent consumption occurs.
Ignored verification scripts/logs live separately under `.tmp/executor1`.

## Requested report index

| Item | Result |
| --- | --- |
| 1. Files changed | Eleven phase/governance files listed above; ignored verification logs separately. |
| 2. Executor owner | `core/behavioral_diagnostic_executor.py`; unavailable pending enforced isolation. |
| 3. Receipt schema | `patch_candidate_behavior_executor_1_v1`, immutable blocked facts only. |
| 4. Executor descriptor | `bounded_java_diagnostic_executor`; available=false; console/command/shell/write/network authority=false; reflection read-only; enforcement unavailable. |
| 5. Authorization gate | Fresh `validate_runtime_diagnostic_authorization` before any possible runtime effect. |
| 6. Synthetic-only positive authority | Exact trusted process-local synthetic sources from PREFLIGHT.RUNTIME.1; positive authority reaches the isolation blocker. |
| 7. Real BANK authority | Absent source returns `diagnostic_execution_authority_missing`; no session consumed. |
| 8. Interest/console | Exact console-dependent authorization returns `runtime_executor_console_unavailable`; stdin is never used as console. |
| 9. Virtual-byte projection | Deferred before any write; receipt binds freshly validated exact after-byte SHA-256 and supporting hashes. |
| 10. Workspace isolation | Unavailable; no temporary runtime workspace created. |
| 11. Harness generation | Deferred; no generic renderer or model/UI generation authority. |
| 12. Harness identity | Empty/not generated; no deterministic harness success claim. |
| 13. Compiler policy | Frozen trusted VALIDATE.1A resolution preserved; not invoked by this consumer. |
| 14. JVM policy | No runtime executable accepted or resolved; fixed trusted launch awaits enforceable boundary. |
| 15. Shell | False; no shell or command-string schema. |
| 16. Classpath/sourcepath | Deferred; no environment or repository-wide discovery. |
| 17. Timeout | No process starts; runtime hard deadline implementation remains deferred. |
| 18. Output bounds | No process output captured; runtime bounded pipe implementation remains deferred. |
| 19. Cleanup | No runtime resources allocated; all-child cleanup capability remains unavailable. |
| 20. Network | Policy-forbidden; technically unenforced for hypothetical candidate Java; executor refuses to launch. |
| 21. Filesystem | Policy-forbidden; technically unenforced for hypothetical candidate Java; executor refuses to launch. |
| 22. Constructor | Exact frozen target and literal arguments bound in receipt; not called. |
| 23. Setup | Exact authorized setup invocations bound; expected setup returns never evaluated. |
| 24. Action | Exact authorized action binding preserved; not called. |
| 25. Direct return | No runtime value captured; primitive boolean capture deferred. |
| 26. Reflection request | Exact admitted `read_exact_bound_field` requests bound; no widening or issuance. |
| 27. Reflection receipt issuance | Zero actual candidate-runtime reflection receipts; frozen synthetic infrastructure seam unchanged. |
| 28. Normalization | Stable JSON/fingerprint for blocked facts; no duration/temp paths; runtime double normalization deferred. |
| 29. Execution authenticity | Process-local HMAC authenticates blocked issuance only; caller/exported JSON cannot prove execution. |
| 30. No oracle | No oracle reducer, assertions, pass/correctness field or setup expected-return comparison. |
| 31. Receipt | Authenticated blocked receipt; execution_completed=false; every execution/generation effect count=0. |
| 32. Validator | Pure local-authenticity and fresh-parent reconstruction; complete canonical facts comparison. |
| 33. Stale | Changed exact parents reject; old evidence remains unchanged. |
| 34. Forged authorization | Missing source attestation, altered typed authority and exported caller payloads rejected before any launch. |
| 35. Real BANK negative | Missing authority preserved with zero execution. |
| 36. Interest negative | Console unsupported, zero execution. |
| 37. Extra call | Fresh complete-scope reconstruction rejects; no invocation surface exists. |
| 38. Extra observation | Fresh complete-scope reconstruction/authenticity rejects; no observation can be emitted. |
| 39. Reflection writes | No write primitive; frozen requests only; write/enumeration/private invocation grants reject. |
| 40. Network/shell/write negatives | Closed authorization owner rejects payloads/grants; no command, network or write adapter exists. |
| 41. Timeout/errors | Runtime timeout/overflow/compile/launch/throw/nonfinite failure tests deferred because no safe process can launch; they are not reported as passed. |
| 42. Source mutation | Consumer and candidate/product mutation=0; phase implementation/governance edits are listed separately. |
| 43. Traversal | Execution consumer=0; only supplied exact buffers/parents. |
| 44. Model/author | Consumer calls=0; offline fixture construction does not call providers. |
| 45. JUnit/test generation | Zero Java/JUnit/product test source generated by the phase. Python governance tests only. |
| 46. Console usage | Zero console/PTY opens or stdin fallback. |
| 47. Java/javac counts | Executor=0/0; separately counted frozen REFLECT infrastructure verification=1/1. |
| 48. Synthetic scenarios executed | Zero. Three exact non-console synthetic authorities classified only. |
| 49. Real BANK scenarios executed | Zero. |
| 50. Performance | Authorization reconstruction and receipt normalization measured externally; every unentered runtime stage=0; measured table below. |
| 51. Focused tests | 76 accepted passing cases across initial and targeted added-case runs; no phase runtime effects. |
| 52. Adjacent tests | 1297 accepted passing checks, five platform skips, two reproduced baseline failures, and two guard-blocked integrations; details below. |
| 53. Registry/benchmarks | 223 phases, 41 CONTROL, 218 historical, one blocked; DOGFOOD.1B remains recommendation; 54 benchmark checks, zero errors. |
| 54. First remaining blocker | Synthetic: `runtime_executor_capability_incomplete`; real BANK: `diagnostic_execution_authority_missing`. |

## Explicit answers

| Question | Answer |
| --- | --- |
| Can one exact synthetic authorized scenario now execute? | **No.** Required isolation cannot currently be enforced; the explicit stop condition applies. |
| Does real BANK still refuse without an operational authority source? | Yes. |
| Does the executor decide authority itself? | No. It consumes and independently validates the frozen authority owner. |
| Can the harness call an unauthorized method? | No harness is generated or exposed; changed call scope rejects. |
| Can it observe an unadmitted field? | No observation path exists; changed exact REFLECT scope rejects. |
| Are reflection observations authenticated by an executor-owned path? | No actual candidate observations exist yet. Blocked receipts alone are executor-authenticated. |
| Is any behavioral oracle evaluated? | No. |
| Is deterministic console unsupported? | Yes. |
| Are repository/product writes technically prevented or policy-forbidden? | The consumer has no write/launch primitive; candidate-runtime filesystem isolation is unavailable, so candidate execution is refused. |
| Is network technically prevented or policy-forbidden? | Policy-forbidden; candidate-runtime network isolation is unavailable, so candidate execution is refused. |
| Does successful execution grant write/Apply authority? | No. Every authority field stays false; this phase performs no successful execution. |

## Verification

The saved synthetic replay uses **one sample per scenario**, so its median and
maximum are the same sample, not a statistical throughput estimate. A separate
earlier replay passed but discarded its full result; one additional replay
acquired the saved artifact. Neither run executed Java. Artifact timings are:

| Authorized synthetic scenario | Authorization reconstruction ms | Receipt normalization ms | Total ms |
| --- | ---: | ---: | ---: |
| Wrong credential transfer | 4541.4201 | 4.9612 | 4546.4359 |
| Successful transfer | 4688.9643 | 6.2030 | 4695.2097 |
| Unsuccessful debit | 4201.4263 | 2.5069 | 4203.9604 |

Projection, harness rendering, compilation, JVM startup, scenario execution,
reflection and cleanup fields are all zero because those stages were never
entered. Their latency is **unmeasured**, not a zero-latency execution claim.
All three blocked receipt identities are stable across repeated exact facts.
The report exports no private signatures and records no denied effect attempt.

All **76** focused cases pass: 57 initial cases in 173.35 seconds, nine added
cases in a separate targeted run, then ten rehashed typed-forgery cases in
37.31 seconds. The typed cases reach the fresh frozen validator and prove
that a correctly recomputed public fingerprint cannot widen scope or effects.
These are combined accepted selections, not a claim of one final monolithic
76-case run. No production-owner repair was needed.

Accepted adjacent selections total **1297 passing checks**:

| Selection | Accepted result |
| --- | --- |
| PREFLIGHT.RUNTIME.1 pure | 94 passed in 228.80 s; effect attempts=0. |
| EXEC.ADMIT.1 / EXEC.PLAN.1 / SPEC.1 / MATERIALIZE.1 / AUTHOR.STRUCTURAL.1 | 386 passed in the guarded selection; nine existing offline-author integration cases passed separately in 12.83 s after their exact canned fixture was permitted. Total 395. |
| VALIDATE.1A pure | 28 passed initially; one bookkeeping check passed separately after the new governance hashes settled. Total 29. |
| REFLECT.1 pure + required infrastructure | 98 passed in 40.66 s with exactly one trusted javac and one corresponding JVM, no incidental processes. |
| Human authority / Apply / ignore / execution eligibility / EVIDENCE / ACQUIRE / single-file path | 229 passed; two historical baseline failures and one process-dependent Apply fixture blocked by the verification guard. |
| Canonical repository identity / identity state / inventory | 155 passed, five platform skips; one two-process identity concurrency fixture blocked by the verification guard. |
| Registry / picker | 297 passed in 4.39 s; blocked capability cannot become the recommendation. |

The historical failures are
`test_real_registry_marks_human_close_complete_and_picker_recommends_adopt_model_1`
(expects UX.RUN.1 while the pre-existing registry recommends DOGFOOD.1B), and
`test_acquire_1_is_not_reachable_from_any_live_path` (finds two pre-existing
ignored `.tmp` snapshot files). Both reproduce with this phase's exact registry
addition removed in memory; no frozen expectation is rewritten. The retained
logs are `.tmp/executor1/baseline.log` and `authority_policy.log`.

Two existing process-dependent tests are not accepted as passing:
`test_t6_bounded_review_apply_is_authorized_before_real_executor` attempts
temporary-project validation processes; the guard denies 14 `subprocess.run`
calls before launch. `test_two_process_first_save_is_one_commit_and_one_stale`
requires Python workers; its first `Popen` is denied. Neither failure is
attributed to the new executor owner, and neither integration is weakened to
make this slice pass. Existing Apply/write semantics stay frozen.

The initial broad guard also rejected nine offline `SyntheticAuthor` facade
tests. Their accepted targeted runner restores only the exact canned fixture
class, retains process/network/provider denial, and observes 12 facade calls
(including pre-call rejections), zero live providers and zero process attempts.
Those verification fixture calls are separate from the new execution consumer's
zero model/author calls. The first narrow rerun had a pytest module-alias class
identity mismatch before any fixture invocation; its corrected run passes.

The required REFLECT infrastructure suite generates seven ephemeral existing
fixture Java files and measures 20 exact adapter attempts: 14 actual reads,
11 finite successes and three nonfinite rejections; six attempts reject before
reading. Its compiler/runtime durations are 1.872 s / 0.387 s. These are
frozen infrastructure integration effects, not candidate/BANK execution.
The initial infrastructure audit bootstrap mishandled Windows' null audit
executable argument and stopped before any compiler/JVM launch; corrected
exact-argv verification is the accepted 98-case result. Provisional logs remain
separate, and no frozen adapter owner or receipt is changed.

Benchmarks `--check`: **54 checked, zero errors**, under effect denial with
native Windows version metadata supplied without a subprocess. Compileall of
`core web tests scripts benchmarks` passes. `git diff --check` passes; existing
tracked-file CRLF conversion warnings are separate from whitespace failures.
The new untracked phase files also receive an explicit whitespace check.
All **24 captured frozen owner/artifact entry hashes** remain unchanged. The
new exact reversal plus seven downstream historical reversal chains preserve
their entry hashes; no historical receipt is repinned.

The whole-suite effect-denial guard is used only for the blocked path required
by the isolation stop condition. It does not pretend to test a runnable
capability. Required frozen REFLECT infrastructure integration uses a separate
guard that allows/counts its exact existing synthetic compiler/JVM pair and
rejects every incidental project process before launch.

The virtual environment's uv trampoline could not spawn its Python child
(`permission denied`); verification uses installed system Python 3.14.6.
This startup limitation is separate from executor capability and test outcomes.
