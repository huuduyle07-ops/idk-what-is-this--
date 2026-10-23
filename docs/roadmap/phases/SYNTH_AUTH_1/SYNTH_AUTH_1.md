# SYNTH.AUTH.1 — exact phase-owned synthetic authorization

2026-10-08 KST. **`SYNTH_AUTH_1_COMPLETE`** means the authorization contract
proof is complete. One synthetic authorization was issued and authenticated in
its issuing process. Java execution, compilation, reflection, and authorization
consumption remain zero. The historical EXECUTOR.1R blocked result remains
unchanged.

The additive owner is `core/synthetic_runtime_authorization.py`. Its only
supported V1 scenario is supplied by `executor1r_decrement_3_spec()`. An equal
public constructor, `dataclasses.replace`, or JSON reconstruction cannot become
a supported spec. Validation requires the factory's exact object, recursively
exact immutable types, and the pinned full contract projection. The spec has
no executable argv, shell text, repository path, or arbitrary source input.

| Binding | Exact requirement |
| --- | --- |
| Issuer phase | `SYNTH.AUTH.1` |
| Scenario phase | `PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R` |
| Scenario ID | `synthetic.EXECUTOR.1R.decrement_3` |
| Source SHA-256 | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` |
| Source size | 239 bytes |
| Public invocation | `SyntheticStateBox.decrement(3)`, exact primitive `int` argument and `boolean` return |
| Observation roles | `exact_private_state_before`, `direct_public_return`, `exact_private_state_after` |
| Requested private metadata | `SyntheticStateBox.value`, primitive `int`, definition SHA-256 `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` |
| Requested facts | before = 10; return = true; after = 7. These are expectations, not measurements. |
| Sandbox requirement | `runtime_sandbox_2_v1`, policy SHA-256 `5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75` |
| Java requirement | `RUNTIME.JAVA.1`, schema `runtime_java_1_v1` |
| Allowed synthetic operation | `direct_public_invocation`, bound to this exact invocation only |
| Source kind | `phase_owned_synthetic_fixture` |
| Required external effects | console = false; network = false; repository access = false |
| Real task / human approval | real task source = false; human approval required = false; human approval/session consumed = false |

`issue_synthetic_runtime_authorization(spec, source=...)` validates the owned
spec and supplied immutable source bytes by exact content, digest, and size.
It issues a fresh typed handle with a random issuance ID and HMAC-SHA256 using
a process-local key. Validation rechecks the complete fixed scope, originating
process ID, HMAC, and the live issued object's identity in a weak registry.
Copied signatures, equal typed replacements, self-hashed reports, unsigned
objects, and serialized data cannot recreate a live handle. Authentication is
an internal trusted-Python boundary; exported hashes are report identities.

The grant is synthetic invocation scope only. `runtime_authority` and
`real_task_runtime_authority` remain false. Reflection metadata records a
requirement for a future compatible exact reflection owner, with
`reflection_authority=false`. Sandbox, Java, and reflection capability
availability and `execution_ready` remain false. This owner neither imports
the frozen runtime owners nor accepts their historical reports as live
capabilities. A future executor still needs independently authenticated
compatible infrastructure and reflection admission. The existing BANK planner,
PREFLIGHT issuer, REFLECT.1, and executor gates are unchanged.

The replay is `scripts/replay_synth_auth1.py`. It installs the existing strict
effect-denial guard before importing the new owner, proves issuance and
validation, and checks that no denied effect was even attempted. Optional
report export occurs after the guarded proof. The new
`docs/roadmap/SYNTH_AUTH_1_LOCAL.json` is report-only: it omits the signature and
cannot restore authority in any process. `measured_observations` and
`positive_runtime_receipt` are null. No Java source, harness, class, process,
or container is created. Remaining containers are unmeasured (`null`).

Validation and historical preservation are recorded in the local JSON. All
existing core, script, test, and roadmap files were hashed before this slice;
protected frozen files and registry/reversal records are checked against their
actual starting bytes, including pre-existing working-tree changes. No phase
registry or historical status was repinned. The focused suite covers every
spec, nested metadata, and authorization field; source byte/type mismatches;
factory and issuance provenance; process/key changes; executable payload
rejection; and zero attempted runtime effects.

Completed checks: 117 focused tests and 936 adjacent regression tests passed;
three Python sources compiled in memory; whitespace and `git diff --check`
passed. All 1,273 pre-existing files in the captured source/test/script/roadmap
inventory and all 134 specifically protected historical files remain
byte-identical. The latter include the earlier 129-file preservation list and
the five EXECUTOR.1R artifacts.

The adjacent run passed 935 tests under blanket process/network effect denial.
Its one remaining Apply integration test initially failed because that guard
blocked its Python validation child. The same unchanged test then passed in
isolation, allowing only the exact current interpreter's `-m pytest` invocation
inside its temporary fixture directory. Java, shells, other child commands,
and network remained denied. This temporary Python Apply fixture is separate
from the SYNTH.AUTH.1 proof, whose strict guard recorded zero attempted effects
and created no runtime resources. Frozen registry compatibility was projected
only in memory by the existing regression plugin. No historical artifact was
edited to obtain these results.
