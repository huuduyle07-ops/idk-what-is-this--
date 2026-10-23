# SYNTH.AUTH.PINNED.1 — exact frozen scenario authorization

2026-10-10 KST. This additive epoch uses schema
`synthetic_runtime_authorization_pinned_1_v1`. A successful
`SYNTH_AUTH_PINNED_1_COMPLETE` result means only that the frozen scenario is
authorized to rely on the exact authenticated live PINNED.1C provider graph.
The scenario's expected facts remain expectations. Authorization scope is
separate from an execution lease.

| Binding | Frozen identity |
| --- | --- |
| Scenario | `synthetic.EXECUTOR.1R.decrement_3` |
| Source SHA-256 | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` |
| Source size | 239 bytes |
| Definition SHA-256 | `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` |
| Method contract | `boolean SyntheticStateBox.decrement(int)` with sole argument `3` |
| Private field | `SyntheticStateBox.value:int` |
| Expected facts | before `10`, return `true`, after `7`; no measurements |
| Provider requirement | `RUNTIME.JAVA.PINNED.1` / `runtime_java_pinned_1_v1` |
| Provider proof | `RUNTIME.JAVA.PINNED.1C` / `runtime_java_pinned_provider_1c_v1`, complete with `exact_provider_proven=true` |

`core/synthetic_runtime_authorization_pinned.py` recovers scenario identities
through the unchanged SYNTH.AUTH.1 public spec/source factories and validator.
It renders the signature from that exact method contract; it does not
regenerate the source or revise the historical Java requirement projection.
The old schema and validators do not accept the new authorization class.

The sole issuance entry point, `issue_pinned_synthetic_runtime_authorization()`,
takes no arguments and invokes the public PINNED.1C issuer exactly once in its
process. It authenticates the original receipt and all ten original upstream
objects through `validate_pinned_java_exact_provider`. The new owner retains
the provider outcome, binding wrapper, original root, complete graph, original
frozen scenario spec, and exact authorization object. Every validation repeats
public provider authentication and checks retained object identities. Provider
reports and chronology cannot establish the binding.

The authorization binds the full fixed scenario, new phase/schema/owner,
random authorization and context IDs, issuing PID, provider proof context,
receipt ID, fingerprint, evidence digest, requirement, target image, runtime
sandbox profile/policy, authenticated controller evidence and cleanup evidence.
Its separate random process-local HMAC key and domain cover the payload and
authority matrix. Exact type checks reject Python equality aliases. Live
registry identity rejects copied handles, replaced dataclasses, typed JSON
reconstructions, wrappers, subclasses, and signatures copied to new objects.
Exported reports omit signatures and cannot restore capabilities. Authentication
is an owner boundary within trusted Python, not isolation from hostile Python
that can rewrite module internals.

`synthetic_scenario_authorized=true` permits only this scenario's scope on this
exact provider graph. Runtime execution, execution lease, reflection execution,
real task runtime, repository writes, Apply, network, host mounts, shell,
arbitrary commands, arbitrary Java/class/method/source, repository Java,
executor and BANK authorities all remain false. No lease or reflection admission
is issued. `lifecycle_compatibility_evaluated=false` and
`lifecycle_execution_ready=false`; a later phase must review lifecycle support.
The provider proof remains reusable live evidence and is never consumed.

The replay `scripts/replay_synth_auth_pinned1.py` requires fresh pure gates and
source/validation/preservation hashes, then exclusively reserves the new local
report before any operation. Reservation permits at most one live authorization
attempt, including failure. Provider infrastructure effects are reported
separately from the new owner's HMAC/registry effects and zero synthetic
behavioral effects. The provider may perform its frozen target inspection,
BIND/SANDBOX verification and fixed JAVA.1C infrastructure probe. The new phase
executes no SyntheticStateBox, reflection, executor, BANK, behavioral candidate,
lease consumption, or Apply. Source/report authoring and provider temporary
infrastructure files are distinct from repository runtime write authority.

Reversible live negative controls use the same proof without fresh issuance.
They check copies, JSON, wrong process/key/signature, every scenario binding,
old Java requirements, provider identities/evidence/authority flags, actual
retained graph substitutions and historical report substitution. Pure tests
also substitute a different independently authenticated graph through virtual
transports. The replay reauthenticates the originals after all controls. Failed
controls withdraw only the new authorization and preserve the provider proof;
exceptions leave a blocked JSON report and restore temporary-directory state.

Historical owners, tests, reports, registry/picker and reversal artifacts remain
unchanged. `preservation_baseline.json` records their byte identities, including
existing working-tree changes. Its initial capture covers 341 files; 14 additional
dependencies were confirmed against frozen prior-phase hash bindings, with that
provenance recorded in `supplemental_historical_pins.json`.
`validation_summary.json` records focused and
frozen suites, registry/picker baseline-versus-after failures, benchmarks,
compilation, JSON, whitespace and preservation checks. `SYNTH_AUTH_PINNED_1_LOCAL.json`
is the report-only result of the sole live authorization attempt. Stop at
authorization issuance; lifecycle compatibility and execution are downstream.
