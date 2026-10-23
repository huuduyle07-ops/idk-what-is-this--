# SYNTH.REFLECT.1 — exact synthetic read-only observation contract

2026-10-08 KST. **`SYNTH_REFLECT_1_COMPLETE`** establishes the exact request,
definition, authentication, authorization-compatibility, and rendering contract.
The proof executes no Java, reflection, container, shell, network, or child
process. EXECUTOR.1R has not been retried; its blocked historical result remains
unchanged.

| Requested report item | Result |
| --- | --- |
| 1. Supported synthetic reflection targets | Exactly 1 |
| 2. Scenario | `synthetic.EXECUTOR.1R.decrement_3` |
| Scenario phase | `PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R` |
| 3. Source SHA-256 | `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302` (239 bytes) |
| 4. Definition SHA-256 | `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d` |
| 5. Owner / member / primitive type | `SyntheticStateBox` / `value` / `int` |
| 6. Allowed operation | `read_exact_bound_field` |
| 7. Supported reflection roles | `exact_private_state_before`, `exact_private_state_after` |
| 8. Renderer boundary | Complete fixed role-specific helper literals; `SyntheticStateBox.class`, `getDeclaredField("value")`, `setAccessible(true)`, `getInt(instance)` |
| 9. Field-write authority | false |
| 10. Enumeration authority | false |
| 11. Private-method authority | false |
| 12. Fresh SYNTH.AUTH.1 compatibility | Both requests accept a live authenticated exact-scenario handle without consuming or changing it |
| 13. Copied / exported authorization | Rejected, including matching typed copies and report JSON |
| 14. Reflection executions | 0 |
| 15. Java compilations | 0 |
| 16. JVM executions | 0 |
| 17. Containers created | 0 |
| 18. Runtime authorizations consumed | 0 synthetic; 0 real |
| 19. Real runtime authority | false; reflection execution, runtime, repository-write, and Apply authority all remain false |
| 20. Repository writes | 0 during the strict proof; exactly 5 additive implementation/test/replay/report artifacts listed below |
| 21. Historical preservation | All 1,555 captured existing files remain byte-identical, including 139 specifically protected historical files; no registry/reversal repinning |
| 22. Validation | 256 focused tests, 1,026 frozen regressions, 236 selected BANK/authority/Apply/path/patch regressions passed; 1,230 Python sources compiled in memory; 54 benchmark checks and whitespace checks passed |
| 23. Final status | `SYNTH_REFLECT_1_COMPLETE` |

`core/synthetic_read_only_reflection.py` owns two no-argument factories:
`executor1r_before_request()` and `executor1r_after_request()`. Each issuance is
a fresh frozen, slotted `SyntheticReflectionRequest` with a random issuance ID,
issuing PID, independent process-local HMAC key, and live weak-registry identity.
Validation checks the exact class, every field's immutable exact type/value,
the complete canonical projection, literal per-role fingerprint, signature,
and live object provenance. Matching constructors, shallow/deep copies,
`dataclasses.replace`, JSON reconstruction, subclasses, wrappers, incomplete
objects, and self-hashed altered values cannot establish a valid request.

`reflection_request_valid=true` describes a validated request contract. It
does not grant `reflection_execution_authority` or `runtime_authority`.
Rendering takes only an authenticated request, selects a complete fixed helper
literal, and returns text in memory. No caller-supplied class/member/reader
string reaches a Java reflection API. There is no enumeration, field setter,
private method invocation, constructor reflection, arbitrary class loading,
generic renderer, object creation, or execution entry point.

The definition verifier accepts only the exact SYNTH.AUTH.1 source bytes,
size, and digest. Its fixed prefix establishes the lexical owner; bytes
`[36:59]` must equal `private int value = 10;` and match the pinned declaration
digest. This uses the historical raw-declaration hashing convention without
importing or widening BANK's parser or reflection semantics.

`synthetic_reflection_satisfies_authorization(request, authorization)` validates
the SYNTH.AUTH.1 handle through that owner's public validator and exact owned
spec/source factories. It explicitly binds scenario, phase, source, source
kind, owner/member/type/definition, complete requested roles, and the exact
reflection-required flag. A compatible handle remains unavailable for
reflection execution and runtime execution. BANK handles, copied/exported
handles, mismatched scopes, and unauthenticated objects return false. No
authorization is consumed, upgraded, or mutated.

`SyntheticPrivateFieldObservation` is an immutable data shape for later
executor consumption. Its value must be an exact Python `int` within Java's
signed primitive-int range; bool, float, string, subclasses, and coercion are
rejected. Any valid int is accepted for either private role, without comparing
to expected 10/7. Caller construction validates only the data shape, providing
no measurement receipt, execution proof, or authority. This phase produces
no measured observations or positive runtime receipt. Public return values
remain outside reflection.

`scripts/replay_synth_reflect1.py` installs the existing strict effect-denial
guard before importing the new owner. It validates both requests, authenticates
a fresh compatible authorization, rejects exported authorization data, and
renders text. The strict guard records zero attempted effects; source
projection, Java compilation/execution, reflection execution, container
creation, and authorization consumption are all zero. Optional report export
occurs after this proof, excludes signatures/secrets, and cannot restore local
provenance.

Validation is selective and preserves the runtime prohibition. Historical BANK
reflection checks use 15 pure test functions; tests requiring the historical
Java probe and its renderer are excluded. Frozen regression collection runs
under process/network denial with the existing authenticated frozen-registry
plugin, projecting historical registry bytes only in memory. The historical
preflight denial test deliberately attempts nine forbidden operations and
confirms rejection; those attempts are separate from this phase's zero-attempt
strict proof.

The initial safety run passed 230 checks and blocked six existing Python Apply
integration fixtures at its blanket subprocess boundary. Those same six tests
then passed with only verified fixture commands allowed under the current
Python interpreter in temporary directories outside this repository. Five
fixtures run the exact tiny side-effect validation script; one runs the exact
temporary pytest fixture. Parent and child deny Java, Docker, shells, arbitrary
processes, and network; four unrelated process attempts were denied. These six
bounded Python regression processes are development validation, separate from
the strict SYNTH.REFLECT.1 proof, which launches none. No full-suite-green claim
or Java execution measurement is made.

Exactly five new repository artifacts belong to this slice:

- `core/synthetic_read_only_reflection.py`
- `tests/test_synthetic_read_only_reflection.py`
- `scripts/replay_synth_reflect1.py`
- `docs/roadmap/SYNTH_REFLECT_1.md`
- `docs/roadmap/SYNTH_REFLECT_1_LOCAL.json`

The local JSON records the strict proof, validation results, implementation
hashes, and preservation evidence against actual starting working-tree bytes.
SYNTH.AUTH.1, PREFLIGHT.RUNTIME.1, REFLECT.1, EXECUTOR.1/1R, SANDBOX.1/2,
JAVA.1/1A/1B/1C, BANK planning/specification, registry, and reversal history are
unchanged. Work stops at this observation contract.
