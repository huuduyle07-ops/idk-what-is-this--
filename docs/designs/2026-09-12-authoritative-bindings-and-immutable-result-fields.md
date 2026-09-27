# PATCH.MINIMAL.LIVE.3 — Authoritative Bindings and Immutable Result-Field Reads

Completed by LIVE.3A + LIVE.3B on 2026-09-13 (LIVE.3B began 2026-09-12). The exact remaining field read now passes the real safe_minimal gate and the unchanged eight-case verifier. PATCH.AUTHOR.LIVE.3 is a separate next phase and was not started.

The candidate used for the lifecycle is exactly the six-line body specified in the completion request (with normal function-body indentation):

```python
return assess_indentation_observation(
    observe_source_indentation(
        text,
        language=language,
    )
).value
```

INDENT.RUNTIME.1's older fixture puts the nested call on one line. Both byte forms remain intact; a test proves their ASTs match. No production repair was applied to `_classify_indent`.

The LIVE.3B file set is:

| Files | Change |
| --- | --- |
| `core/immutable_result_fields.py` | New bounded static source/declaration proof and occurrence-level receiver provenance. |
| `core/authoritative_binding_context.py` | Frozen callable/field proofs and supporting source identities; freshness checking. |
| `core/local_binding_novelty.py` | Narrow field classification, occurrence-specific exemption, unchanged structural rejection and caps. |
| `patching/patch_gates.py` | Pass the current authoritative context into novelty classification. |
| `core/pipeline.py` | Preserve/invalidate the two new timing telemetry fields with existing candidate novelty telemetry. No lifecycle or authority logic changed in LIVE.3B. |
| `tests/test_patch_minimal_binding_context_live3.py` | Carry forward LIVE.3A's exact PRE using a context with only the new proof disabled; update the current finalization expectation. |
| `tests/test_patch_minimal_result_fields_live3.py` | Positive/negative field controls, static bounds/freshness, body/full and inline/local parity, real frozen lifecycle, performance and completion checks. |
| `tests/test_patch_minimal_novelty_live.py` | Route its historical stdlib-only module assertion through the established reversal helper. The assertion itself remains intact. |
| `tests/test_phase_registry.py`, `tests/test_phase_picker.py` | One completed phase added: 179 total phases, 175 completed history entries. |
| `tests/test_defect_probe_matrix_live.py` | Registration-only guard advances to unused PATCH.MINIMAL.LIVE.4; no matrix data or behavior changed. |
| `tests/fixtures/patch_minimal_live3_reversal.json` | Combined reversal to the original pre-LIVE.3 bytes; existing older pins retained. |
| `tests/fixtures/patch_minimal_live3_frozen_boundaries.json` | Entry-state digests for 375 pre-existing production files outside the authorized slice. |
| `tests/fixtures/patch_minimal_live3_completion.json` | Recorded exact-candidate lifecycle and bounded timing evidence. |
| `docs/roadmap/phase_registry.json` | One complete PATCH.MINIMAL.LIVE.3 record; no separate 3A/3B product phases. |
| This document | Combined design, results, constraints and mandatory authoring follow-up. |

The combined phase also carries forward LIVE.3A's already-present `tests/_harness_maintenance.py` receipt wiring. That file was not edited in LIVE.3B. The working tree already contained extensive earlier work; the above list is measured against this slice's entry state, not against Git HEAD.

| # | Requested finding | Result |
| --- | --- | --- |
| 1 | Exact LIVE.3B files | The 16 files listed above; five production files, six test files, three evidence fixtures, registry and design document. Ignored `.agent/live3b` files contain working snapshots and test logs. |
| 2 | LIVE.3A status | Parameters, baseline lexical locals and proven repository-local direct imports remain recognized, including body/full parity and shadowing behavior. |
| 3 | Old member policy | A novel Attribute load became `novel_external_reference`; knowing its receiver's name did not establish a data-field capability. Member spellings already present in the original snippet retain their independent legacy treatment. |
| 4 | New rule | `proven_immutable_result_field_read`, granted to an individual AST occurrence whose receiver, immutable record and declared field are proven. No name is added to a global field allowlist. |
| 5 | Root-call provenance | A pre-existing direct-imported repository-local synchronous function in the authoritative context, with no baseline/candidate shadowing, rebinding, decorator or generator return. A local result must originate from that direct call. |
| 6 | Return annotations | Direct named class, simple quoted identifier, postponed annotations, or one direct repository-local type import with alias. No eval, type-hint execution, general aliases, union/optional returns or generics. |
| 7 | Type locality | Exact bounded `.py`/`__init__.py` paths beneath the repository root, including relative imports; ambiguity or unresolved/nonlocal definitions fail closed. No repository search. |
| 8 | Immutability | Unshadowed recognized dataclasses decorator, literal `frozen=True`, optional literal `slots`, no base class or metaclass, no unknown class/method decorator, no custom attribute-access hook. The measured type satisfies this declaration. |
| 9 | Declared fields | Unique `AnnAssign` data field, exact name, no dunder, no method/property collision, literal/no default, transparent annotation. Descriptors and ClassVar/InitVar (including concealed/unresolved aliases) are unsupported. The proof is of record fields, not deep immutability of a field's contents. |
| 10 | Load only | Store/delete/augmented assignment receive no proof and are rejected before runtime. |
| 11 | Callable restriction | Attribute used as Call.func is denied; field-to-local callable aliases are not admitted. |
| 12 | Methods | No new method read/call privilege, including methods declared on frozen records. Independently existing legacy permissions remain unchanged. |
| 13 | Properties | Denied, including annotation/property name collisions. Read-only syntax is not proof against descriptor execution. |
| 14 | Module namespaces | No module object is a proven result receiver. Module.attr remains outside the new class. |
| 15 | Inline behavior | Direct `eligible_call(...).field` is supported in straight-line return expressions. Nested eligible argument calls in the T6 candidate are preserved. |
| 16 | Local behavior | `result = eligible_call(); return result.field` is supported when the one assignment is in the selected body, before all reads, with no reassignment or container/alias escape. A baseline local works under the same rule when its assignment is included. Provenance outside a selected fragment, branches, nested scopes and broader dataflow remain unsupported. |
| 17 | Body/full parity | Exact requested T6 body and full-function forms both admitted with the same field class. Local T6 receiver also receives that class. |
| 18 | T6 PRE | With LIVE.3B proof disabled and LIVE.3A active: exactly `value` remains unexplained; exactly `novel_external_reference` blocks. |
| 19 | T6 POST | Same candidate body: all names resolved, `.value` proven from authoritative return/type/field declarations. |
| 20 | Final gate verdict | Admitted, `candidate_novelty_reason=proven_immutable_result_field_read`. |
| 21 | Eight-case matrix | `fixed_and_preserved`, eight cases, unchanged contracts/fixtures/expectations. Sandbox `applied`; candidate effect `mutating`. |
| 22 | Candidate verification | `verified` through the real pipeline after actual sandbox and probe execution. No fabricated verifier outcome. |
| 23 | Authority | `execution_authorized=false`, `auto_apply_allowed=false`, `write_authority=false`, `final_repository_changed=false`; target bytes identical. |
| 24 | Round-9 lstrip | `stripped.lstrip(...)` and `text.lstrip()` remain rejected, `novel_external_reference`. Historical Round-9 envelope/rejection tests remain applicable. |
| 25 | String methods | Known parameter binding creates no new permission for strip/startswith/lower. Generic controls reject them; a method already in the selected baseline retains its old independent permission. |
| 26 | OS/subprocess/module negatives | subprocess.run, os.remove, path-like unlink and module namespaces receive no new field privilege. |
| 27 | Generic positive | Independent repository fixture's frozen Result.value is admitted without running its module; the fixture raises if executed. |
| 28 | Alternate field positive | Equivalent Result.payload is admitted, inline and through one local. A declared callback may be read as data, never called. |
| 29 | Undeclared negative | `.missing` and dunders rejected. |
| 30 | Mutable negative | Ordinary class, non-frozen dataclass and frozen=False reject `.value`. |
| 31 | Frozen method negative | render and render() rejected. |
| 32 | Property negative | dangerous and conflicting declared/property names rejected. |
| 33 | Attribute mutation negative | Assignment, delete and augmented assignment rejected. Runtime frozen errors are not relied upon. |
| 34 | Stdlib result negative | Stdlib direct imports and repository helpers annotated with stdlib results receive no proof. |
| 35 | Third-party negative | Third-party/unknown direct imports or return classes receive no proof; nothing is installed or executed to decide. |
| 36 | Candidate-created type | Class/definition additions and candidate-only signature annotations remain rejected by existing structure policy and cannot seed the baseline. |
| 37 | Static guarantees | Only AST and bounded file metadata/bytes; no authoritative module import/execution, eval, inspect.get_type_hints, dynamic import, sys.path mutation, network or subprocess in policy determination. Normal sandbox/probe subprocesses remain the frozen verification path. |
| 38 | Traversal delta | Zero. Source proofs read at most 16 exact files, 256 KiB each and 1 MiB total, with per-context parse reuse and one type-import hop. |
| 39 | Performance | Recorded separately in the completion fixture: return/declaration proof construction, field lookup and safe_minimal gate PRE/POST medians (31 samples). Construction is milliseconds; lookup is a fraction of a millisecond. |
| 40 | Local caps | Unchanged: 3 novel locals, 1 touched function, 24 changed lines. Field proof does not suppress structural or cap findings. |
| 41 | Authoring delta | Zero prompt/contract edits and zero additional model calls. |
| 42 | Authoring mismatch | Remains mandatory PATCH.AUTHOR.LIVE.3 input: prompt requires names from source_snippet, while policy recognizes authoritative bindings outside it. Next authoring must present actual proven available bindings without dumping arbitrary repository identifiers. |
| 43 | Matrix delta | Zero; all eight cases and their semantics remain frozen. |
| 44 | Validation delta | Zero targeted validation, sandbox, probe or verification code changes. |
| 45 | Authority delta | Zero policy/approval/authorization change. Passing safe_minimal grants only eligibility for verification. |
| 46 | UI/security delta | Zero; UI, security and Track B remain untouched. |
| 47 | Tests | Final focused/adjacent/broad results are recorded below and in the completion fixture. |
| 48 | Retrieval/localization | Existing real-population entry-ordering suite checks that `_classify_indent` remains inside CONTROL's six-entry cap. No retrieval/localization implementation changed. |
| 49 | Governance | One complete PATCH.MINIMAL.LIVE.3; registry and picker history updated. Combined reversible hunks restore all affected older production snapshots, and the 375-file manifest protects this slice's frozen surfaces. |
| 50 | Next phase readiness | Policy prerequisite fulfilled. PATCH.AUTHOR.LIVE.3 has a concrete mandatory input and is not started or registered here. |

Explicit answers:

| Question | Answer |
| --- | --- |
| Is `.value` admitted because of its spelling? | No. |
| Would `.payload` on an equivalent frozen result also be admitted? | Yes. |
| Are methods admitted? | No new method permission. |
| Are properties admitted? | No. |
| Is arbitrary attribute reading admitted? | No. |
| Is arbitrary module.attr admitted? | No. |
| Does lstrip become allowed? | No. |
| Can mutable result objects gain this privilege? | No. |
| Can third-party or stdlib result types gain it? | No. |
| Does the exact T6 candidate now reach fixed_and_preserved? | Yes, all eight cases. |
| Does it reach verified? | Yes. |
| Is execution authorized? | No. |
| Were authoring prompts changed? | No. |
| Does the prompt/policy mismatch remain? | Yes; mandatory next-phase input. |
| Was the eight-case matrix changed? | No. |
| Was `_classify_indent` fixed? | No. |
| Were UI/security behaviors changed? | No. |

Final validation evidence:

| Check | Result |
| --- | --- |
| LIVE.3A + LIVE.3B focused suites | 132 passed. |
| Five adjacent policy/indentation/frozen-history suites | 309 passed, 1 skipped. |
| Registry, picker and real-population retrieval/localization | 310 passed; together with focused suites, the final run was 442 passed. |
| Benchmark fixture structure | 54 checked, 0 errors; no agent/model execution. |
| Remaining broad suite (ten already-tested files excluded) | 9,953 passed, 39 skipped, 50 failed in 1,496.84 seconds. |
| Replay of those 50 failures with the entry-state registry | 49 failed, 1 passed. The diagnostic intercepts only reads of the phase registry; it does not claim a full checkout rollback. The repeated failures concern existing roadmap expectations, missing historical artifacts, and an unchanged context-selector boundary. Exact node IDs are in the completion receipt. |
| Repair of the one new registration failure | The old assertion that PATCH.MINIMAL.LIVE.3 must not exist now guards unused PATCH.MINIMAL.LIVE.4. Its targeted rerun, final registry checks and frozen/combined-phase checks: 170 passed. The broad suite was not rerun after this metadata-only correction. |
| Frozen surfaces | All 375 entry-state production hashes match. Existing older snapshot expectations pass through the combined reversal; none were re-pinned. |

The broad suite is not fully green: the 49 reproduced failures remain outside this slice. Their entry-registry diagnostic and the final registration recheck are recorded separately so the passing scoped checks do not hide that result.

Measured medians over 31 samples: return/declaration proof construction **15.0584 ms**; field lookup **0.0334 ms**; safe_minimal gate PRE **1.3591 ms**, POST **2.0905 ms**, delta **0.7314 ms**. The estimated total incremental cost is **15.7898 ms**, calculated by adding proof-construction median to the gate-median delta, rather than measuring one end-to-end median. Analysis adds no repository traversal, model call or network call. Existing local caps remain 3 novel locals, 1 touched function and 24 changed lines.

The real lifecycle's targeted-validation component is `not_applicable`: the reused graph fixture has no existing check structurally related to the target. Its patch-safety, exact sandbox, paired probe and oracle components are supporting, and the unchanged verifier reports `verified`. The candidate is test-only: execution authorization, automatic application and write authority are false, and real target bytes are unchanged.

PATCH.MINIMAL.LIVE.3 is complete and registered once. PATCH.AUTHOR.LIVE.3 can now address the documented authoring mismatch; it was not begun in this run.
