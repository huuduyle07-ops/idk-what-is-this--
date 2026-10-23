# SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1

**SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_COMPLETE**

This additive requirement evolves exactly the historical
`first_behavior_boundary.first_behavioral_effect = BEFORE exact read` assertion
for `synthetic.EXECUTOR.1R.decrement_3`. The old contract and every pre-existing
file within the preservation scope retain their bytes. The historical assertion
remains a frozen historical requirement, superseded by measured semantic
evidence for this execution epoch. No history is repinned or retroactively
mutated, and no other historical claim is superseded.

The exact source literal in `core/synthetic_runtime_authorization.py` contains
`private int value = 10;`. Ordinary construction initializes mutable scenario
state before a BEFORE read can observe it. The first **known source-level**
mutable-state effect is ordinary construction initializing `value = 10`.
The full harness is unresolved; no earlier exact harness instruction is invented
and construction is not asserted to be its first executable effect.

The conservative activation boundary is **dispatch of the exact scenario-executing
JVM**, after all preparation evidence, full harness readiness, consumer readiness,
runtime consumption and BEFORE permission consumption. This classification is
scoped to the exact scenario consumer and makes no universal assertion about JVM
launches. Target loading/linking and initialization are behavioral activation
effects; ordinary construction and the BEFORE exact reflection read are
behavioral effects.

The revised normative order is:

1. All capability/authentication gates.
2. Source/harness preparation complete, with all preparation, full harness and consumer readiness evidence.
3. Runtime lease `ISSUED -> CONSUMED`.
4. BEFORE reflection lease `ISSUED -> CONSUMED`.
5. Dispatch exact scenario JVM.
6. Load/link/initialize exact target as required by the reviewed harness.
7. Ordinary exact `SyntheticStateBox` construction.
8. BEFORE exact reflection read.
9. Exact public `decrement(3)`.
10. AFTER reflection lease consumption.
11. AFTER exact reflection read.
12. Cleanup.

Only mandatory authenticated permission checks/commits may intervene between
runtime consumption and dispatch. No preparation may occur after runtime
consumption. Launch failure or any later failure does not refund consumption.
Permission consumption remains distinct from evidence of an observed effect.

Compatibility is semantic requirement placement only. Static evidence in
[compatibility_review.json](compatibility_review.json) confirms no changes to
`PinnedSyntheticRuntimeExecutionLease`,
`PinnedSyntheticReflectionExecutionAdmission`,
`PinnedSyntheticReflectionExecutionLease`, their state machines, one-shot
semantics, permanent terminal tombstones, public validators, HMAC domains,
activation policy identities/digests or authority matrices. Existing historical
narrow permissions remain intact; this phase grants none anew. Future owner and
lock integration is not preapproved.

Full executable harness source bytes/hash/size, main class, scenario JVM argv,
loader/controller implementation and staged BEFORE/AFTER protocol remain
**unresolved**. Behavioral activation readiness remains **false** with
`PROOF_UNRESOLVED`. This requirement authorizes no launch or implementation.

PREP's in-memory exact source projection (`PURE_DERIVATION`), sandbox exact source
materialization (`PREPARATION_EFFECT`) and bounded javac scenario compilation
(`PREPARATION_EFFECT`) remain non-operational proposals. This evolution does not
automatically adopt PREP materialization/compile/readiness requirements or grant
preparation authority. A separate small preparation-contract closure review must
confirm their compatibility with the new boundary before any implementation.

All **32 new authority flags are false**.
All **22 operational effect counters are zero**.
No preparation owner, receipt, consumer owner, runtime integration, harness or
executor was implemented. No source/class was materialized; no operational
owner was imported, capability issued/consumed, or Java/Docker scenario run.
Writes consist only of this additive requirement and its pure validation support.

Measured validation: **12 focused pure tests passed**;
registry/picker baseline and after each collected 299
tests, with 292 passing and
7 existing failures; exact node results and
registry/picker projections are identical. Benchmark `--check` checked
**54 cases with zero errors**.
In-memory Python compilation covered **1316 files**;
JSON/whitespace checks and `git diff --check` passed.
**26732 pre-existing non-cache workspace files/links
are unchanged**, with no additions outside this new phase. Preservation excludes
only the recorded cache/runtime directories, Git metadata and this new phase;
links are recorded without traversal. All guarded operational attempt counters
and owner imports are zero. Full issuance-dependent suites were not run.

Existing registry/picker failures, preserved exactly:

- `tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation` (call)
- `tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets` (call)
- `tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked` (call)
- `tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call` (call)
- `tests/test_phase_registry.py::test_seed_registry_has_expected_phases` (call)
- `tests/test_phase_registry.py::test_seed_registry_is_conservative` (call)
- `tests/test_phase_registry.py::test_seed_registry_summary_counts` (call)

See [requirement.json](requirement.json) for exact supersession metadata,
[validation_summary.json](validation_summary.json) for measured checks, and
[preservation_comparison.json](preservation_comparison.json) for preservation.

**STOP.** The next phase is the separate preparation-contract closure review.
Do not implement preparation, harness, consumer or runtime integration here.
