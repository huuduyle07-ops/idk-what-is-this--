# DIAG.REPAIR.FEASIBILITY.1 — Repair-Scope Sufficiency & Author Abstention Audit

**Primary classification: `COMPILE_FEASIBLE_BUT_SEMANTICS_UNDERDETERMINED`.**

Two isolated variants eliminate all five measured errors while editing only `MainApp.java::m1`, `::m2`, and `::m3`. Both pass the frozen SPAN.1 replacement-envelope and AUTHOR.SCOPE containment checks, preserve all read-only bytes, and retain the original signatures and callsites. Their behavioral assumptions are not established by the source, compiler receipt, bootstrap CONTROL, or original task. Compilation therefore disproves unconditional outside-scope necessity but does not establish a safe behavioral repair that the author should have emitted.

The audit recommends exactly one next phase: **`DIAG.REPAIR.INTENT.1 — MainApp behavior and state-ownership clarification`**. No remediation, scope expansion, provider replay, Apply, or registry modification was performed. PATCH.AUTHOR.SPAN.1 remains frozen. This is an audit artifact, not a registered implementation phase.

The [machine-readable evidence](2026-09-22-repair-scope-feasibility-evidence.json) contains the exact source bytes as base64, normalized source, full preserved prompt and response, compiler receipts, full scratch sources and diffs, structural observations, and before/after manifests. The authoritative history is [SPAN.1's completion receipt](../../tests/fixtures/patch_author_span1_completion.json). The local [audit runner](../../.tmp/diag-repair-feasibility1/audit.py) and [scratch measurements](../../.tmp/diag-repair-feasibility1/compile-results.json) are audit artifacts only.

**Answers to the three questions**

- **A — Can all five errors be removed in scope? Yes, for compilation.** Variants A and B compile with zero diagnostics. All bytes outside the measured members remain exact, including class fields, `main`, and intervening whitespace. Neither changes a method signature or the binding of an existing caller. There is no claim of behavioral equivalence to the uncompilable baseline.
- **B — Does a repair fit the existing constraints? At the structural/reference level, yes.** Variant B introduces no identifier, declaration, API, field, import, or external capability; it uses names already present in the corresponding member and numeric literals. The full semantic requirement, “Behavioural redesign — only fix the literal bug,” cannot be certified from the preserved evidence. Neither passing variant is presented as an authorized or behaviorally verified product patch.
- **C — Is an outside edit necessary? No unconditional outside location is required for compilation.** A receiver-based strategy needs the `main` call at line 37 to change; a parameter-based strategy needs calls at lines 34, 35, and 37 to change. Those are conditional obligations, not evidence that every repair requires wider scope. No outside-scope probe was needed or constructed.

**Source identity and authoritative diagnostics**

The only Java file inspected structurally was `C:\Users\Admin\Documents\Code\Side quest\java\MainApp.java`.

| Fingerprint | Exact value |
|---|---|
| Raw MainApp SHA-256 | `6e84dc30157e53e9c10b775bc0da48b2be63f5a33583130527f7cd4edba7ae39` |
| Raw size / mtime_ns | `1076` bytes / `1789363985057404200` |
| Normalized authoring-source SHA-256 | `b706f0622972d451892acc499170d1a32cebeeb00a54e452e0db0ad9eaf545b0` |
| Compiler evidence fingerprint | `0c218e5838fe2551597bc51dbf3d0c02f69c32f76791f88cbf86d64361c6119e` |
| CONTROL fingerprint | `8b529f7251c4a755cdb640d98cf62ed7a4479424a442373a0b8acf1561b8175a` |
| SPAN.1 completion-receipt SHA-256 | `4b13dccae727d4a0c469ad4e8b8f73cef9845867619bee69ec8597b067b69783` |

The baseline scratch compilation reproduced all five authoritative structured diagnostics exactly, including raw diagnostic blocks. The original compiler and the audit compiler were both `javac 26.0.2.1`.

| MainApp location | Diagnostic owner | Exact compiler message | Symbol / source expression |
|---|---|---|---|
| 12:49 | m1 | `cannot find symbol` | `variable no2`, `(no1 + no2)` |
| 20:49 | m2 | `cannot find symbol` | `variable no1`, `(no2 + no1)` |
| 26:49 | m3 | `non-static variable no cannot be referenced from a static context` | `(no3 + no)` |
| 28:43 | m3 | `cannot find symbol` | `variable no1`, `(no1 + no2 + no3)` |
| 28:49 | m3 | `cannot find symbol` | `variable no2`, `(no1 + no2 + no3)` |

**Java scope and same-file callers**

| Declaration / call | Structural location | Meaning for repair |
|---|---|---|
| `int no = 100;` | Class field, line 3; instance state | Available through `this` in m1/m2. Static m3 has no implicit receiver. Class-field edits are outside RepairScope. |
| `static int sno = 200;` | Class field, line 5; static state | Accessible in all three methods. It is a different field and value from `no`. |
| `int no1 = 10;` | m1 body, line 9 | Scope begins at its local declaration and ends with the m1 block at line 13. It is not a class field or an m2/m3 binding. |
| `int no2 = 20;` | m2 body, line 17 | Scope begins at its local declaration and ends with the m2 block at line 21. It is not an m1/m3 binding. |
| `int no3 = 30;` | m3 body, line 25 | Local only to m3, through line 29. |
| `void m1()` / `void m2()` | Lines 7–13 / 15–21 | Instance methods, no parameters. |
| `static void m3()` | Lines 23–29 | Static method, no parameters. |
| `MainApp obj = new MainApp();` | main body, line 33 | Local receiver in main; not visible in m3. No explicit constructor exists in this file. |
| `obj.m1();` / `obj.m2();` | main lines 34 / 35 | The only same-file callers of m1/m2; outside RepairScope. |
| `MainApp.m3();` | main line 37 | The only same-file caller of m3; class-qualified static invocation, outside RepairScope. |

The parser inspected only the exact MainApp buffer. No other Java source was inspected for declarations or calls. “All callsites” here means all callsites in that file, as requested; cross-file callers were not searched.

**Exact live contract clauses and their implications**

These quotations are from the completion receipt's actual live prompt, not reconstructed current prompt templates:

> [STYLE & CONSTRAINTS — authoritative, overrides later rules]
> PATCH STYLE: safe_minimal
> - allow_new_api: False
> - allow_multifile_patch: False

> - Use only APIs, fields, functions, and classes already present in the provided context.
> - Do not introduce new fields, methods, classes, imports, or framework assumptions.
> - If a safe patch requires missing context, set needs_escalation=true.

> Candidate references must come from authoritative baseline bindings shown in
> AUTHORITATIVE AUTHORING SCOPE, permitted bounded candidate-local bindings, or
> the gate's existing source-snippet, language-keyword and supported-builtin classes.
> Baseline locals remain subject to initialization and lexical shadowing; their
> presence does not prove a value at an arbitrary point in the function.

> - Behavioural redesign — only fix the literal bug.

> You may draft changes inside exactly the measured repair members in
> AUTHORITATIVE AUTHORING SCOPE. The primary target remains separate and unchanged.
> Account for all associated compiler diagnostics; you need not edit every member.
> Member-local bindings belong only to their named member.

> Visible context and the source between members are read-only.

> For edits spanning multiple measured
> members, copy that entire original_snippet verbatim into target_snippet and put
> its replacement in patched_snippet. Both fields must describe the SAME interval.

> Preserve every byte outside the measured members in patched_snippet, including
> intervening definitions, comments, annotations, blank lines and whitespace.

> No new definitions, files, imports or extra targets may be proposed.
> The measured set is permitted for drafting even when it contains several methods.
> Draft permission does not certify safety, minimality or completeness.
> Existing PATCH.MINIMAL (including its one-function limit), verification and human
> approval remain downstream authorities and may reject this draft.

> PATCH TARGET remains the primary grounded target; editing every member is not required.
> When [MEASURED REPAIR SCOPE] is present, its exact members are the only
> additional same-file definitions the compiler receipt grounds for this repair.

> Do not invent identifiers unless style explicitly permits it.
> If source does not support a safe fix, return patch_candidate=null and needs_escalation=true.

No surviving primary-only or single-function **drafting** prohibition was found. The one-function wording explicitly describes a downstream gate, alongside an explicit permission to draft several methods. No global “no new locals” or “immutable bindings” prohibition was found. The immutable-result paragraph governs a specific proven read capability, not all local declarations. The raw author's phrase “changing the class structure” is not a verbatim blanket prompt clause; the actual prompt forbids new fields/methods/classes and outside-member edits. Those restrictions are real, but A/B avoid them.

All three Java `available_baseline_bindings` projections are empty. That is not evidence that sibling locals become visible, nor proof that Java lacks its shown class fields. Variant B relies on existing member source names and literals, so the feasibility evidence does not depend on new Java local-binding support. No deterministic PATCH.MINIMAL gate was evaluated.

**No author-contract contradiction was established.** This does not certify candidate safety or every downstream restriction. It establishes that a multi-member drafting prohibition is not the measured cause of abstention.

**Canonical envelope and scratch measurement**

The canonical normalized interval is `[115, 828)`, 713 UTF-8 bytes, with SHA-256 `ee6f58cff81fa3e62064a722b7581ae05fc980c1cd2367cbf7d1f6fb09ede26f`. Its raw CRLF interval is `[121, 856)`. The primary remains m1; editable members are exactly m1/m2/m3. Every compiled variant uses the entire canonical original envelope and replaces that same interval. Existing `consume_repair_scope`, `canonical_replacement_envelope`, and `AuthoringRepairScope.validate_candidate` were used without modification.

Read-only raw ranges `[0,121)`, `[358,366)`, `[603,611)`, and `[856,1076)` are copied byte-for-byte. These cover the class prefix/fields, both gaps, and the suffix containing main. Their hashes are in each measurement. CRLF source bytes are retained; normalized authoring coordinates are not misapplied as raw-byte offsets.

| Audit variant | Exact strategy / touched locations | Envelope result | javac result | Introduced assumption |
|---|---|---|---|---|
| Baseline | Exact original bytes; no changes | Not applicable | `compile_failed`, 5 errors | None; diagnostic reproduction. |
| A: literal values, fresh instance | m1: inaccessible no2 → `20`; m2: inaccessible no1 → `10`; m3: no → `new MainApp().no`, no1/no2 → `10`/`20` | Accepted; m1/m2/m3 only | `compile_passed`, 0 errors | Cross-method references mean copies of initializer values; m3 may read a fresh instance rather than main's object. |
| B: literal values, static field | Same constant substitutions; m3's Result 7 uses existing `sno` instead of `no` | Accepted; m1/m2/m3 only | `compile_passed`, 0 errors | Result 7 meant static state and its `no` reference was a typo. This changes the displayed value relative to A. |
| C: instance-method negative control | Same constants; `static void m3()` → `final void m3()`, retaining instance-field read `no` | Accepted structurally; m1/m2/m3 only | `compile_failed`, 1 error at 37:16 | m3 should use a receiver. Unchanged `MainApp.m3()` lacks it. `final` also forbids overriding; this is a negative control, not a repair proposal. |
| D: parameter negative control | `m1(int no2)`, `m2(int no1)`, `m3(MainApp obj, int no1, int no2)`; m3 reads `obj.no` | Accepted structurally; m1/m2/m3 only | `compile_failed`, 3 errors at lines 34/35/37 | Callers supply state/values. Existing callers have no arguments. API changes also conflict with `allow_new_api: False`. |

An earlier C0 shape simply deleted `static`. The frozen validator rejected it with `readonly_gap_modified` before compilation because its diff alignment assigned the deletion across the preceding whitespace. It was not used as compile-feasibility evidence. C replaces the modifier with `final`, passes containment, and isolates the missing-receiver obligation. No validator was bypassed or repaired.

Each compilation used an isolated source directory, isolated class output, empty sourcepath/classpath, `-proc:none`, `-implicit:none`, UTF-8, fixed English diagnostics, and the frozen PREFLIGHT compiler argument builder, sanitized environment, bounded process runner, and parser. Per-process timeout: 60 seconds; version timeout: 30 seconds; capture limit: 65,536 bytes per stream; diagnostic limit: 32. There were five separate audit compiler invocations and one version probe. The adapter's 180-second cycle setting is recorded but is not asserted as an overall deadline for this multi-step audit. No target program was executed. Successful measurements were reused after audit-runner corrections, not recompiled.

The initial sandbox denied the virtualenv Python child process. Execution permission was requested through the tool before running the isolated audit. This changed no repository authorization.

**Causal table**

| Constraint / question | Evidence | Result | Causal implication |
|---|---|---|---|
| Five compiler errors | Frozen receipt and identical baseline scratch diagnostics | Reproduced 5/5 | Measured Java defects, not model-invented diagnoses. |
| Declaration scopes | no is a field; no1/no2 are locals in different methods | Cross-method local references invalid | Shared values require an interpretation, not just spelling reuse. |
| Callsites | Three calls in main, outside measured members | A/B leave all calls and signatures exact; C/D expose call errors | Caller edits are strategy-dependent. |
| Static/instance relationship | m3 has no receiver; no belongs to instances | A constructs one; B selects a different static field | Several legal expressions encode different intent. |
| Current editable members | RepairScope = AuthoringRepairScope = m1/m2/m3 | No widening | All successful scratch edits fit the measured set. |
| Candidate envelope | Frozen contract and containment validator; raw-gap hashes | A/B accepted with exact read-only preservation | Compile proof is not an envelope bypass. |
| Author constraints | Explicit multi-member drafting; no new fields/APIs; no redesign | No drafting contradiction established | Do not classify `AUTHOR_CONTRACT_CONFLICT` or blame provider refusal to do a single-function repair. |
| Scratch compile feasibility | Two accepted variants, javac exit 0 and no diagnostics | All five errors eliminated in scope | `REQUIRES_OUTSIDE_SCOPE_EDIT` is disproved as an unconditional compile classification. |
| Semantic ambiguity | A reads new-instance no; B reads static sno; constants replace inaccessible locals | No expected output or ownership invariant selects a repair | Compile success does not establish a defensible behavior-preserving candidate. |
| Task-text loss | Original: “Help me check if the code in twosum.java and MainApp.java is ok, then fix them”; author: “Generate patch” | Loss is real; original contains no additional behavior specification | Restoring this task alone would not resolve the choice. No task-transport repair. |
| Historical terminal state | `patch_candidate=null`, confidence 0.2, escalation true | Abstention is observed | `AUTHOR_MODEL_OUTPUT` remains a terminal label, not the established causal root. |

The semantic verdict is **not** a requirement that one repair be uniquely correct. A/B differ in an observable result and state ownership, and none of the preserved evidence supplies an acceptance invariant sufficient to justify either under the no-redesign clause. Under the shown initializers, A's Result 7 would be 130 and B's would be 230; these are source-based arithmetic inferences, not runtime measurements or asserted intended outputs. Source comments distinguishing instance/static/local variables provide context, but do not specify whether the requested repair should preserve those roles, share values, or change an erroneous operand.

For a chosen interpretation, the smallest outside location can be identified conditionally: main's line-37 call for an instance m3; main's three callsites for the tested parameter strategy; class-level declarations for genuinely shared no1/no2 fields; line-3 field declaration if no itself must become static. None is unconditionally necessary, and none is authorized by this audit. No constructor edit is proven necessary.

**Provider identity and prompt provenance**

The successful completed author response came from provider `google`, model `gemini-3.1-flash-lite`, role `draft`, success `true`, one attempt, zero fallbacks, 6,915 input tokens and 204 output tokens. This is the author usage record in the completion receipt, not an attribution from a failed transport attempt or from the separate bootstrap call. The author identified the Java scope errors correctly. Its implication that class changes are required for every compile repair is too strong; A/B refute that. Abstention remains epistemically defensible because no behaviorally warranted repair was established. This audit does **not** conclude `AUTHOR_MODEL_ABSTENTION` as a causal failure.

The completion receipt stores a newline-normalized prompt: SHA-256 `7fbf2ee3c4d9193eaee2aa1fef7aae2f876487c4307130335c10909afe088eb1`. Its writer used `read_text`, converting 64 CRLF pairs to LF. The preserved provider-boundary prompt hashes to `fafbd6e3e8e9d8309b64c12f034ce9e9e270969f964ae9faf0c05e753e314665`, exactly the recorded boundary hash, and normalizes exactly to the receipt text. Both representations are retained; there is no wording discrepancy. The exact response stored in the receipt hashes to `bb087b83fb87db8aed8de9d145bd59f86436742fad3201b76794091b09694462`. No provider was called to recover history.

**Required final accounting**

| # | Required item | Finding |
|---:|---|---|
| 1 | MainApp fingerprint | Raw SHA-256, size, mtime and normalized SHA-256 recorded above and in evidence. |
| 2 | Five authoritative diagnostics | Full raw and structured diagnostics retained; exact baseline reproduction. |
| 3 | diagnostic_owners | m1, m2, m3, owning 1/1/3 errors. |
| 4 | Current RepairScope | m1, m2, m3; primary m1; AuthoringRepairScope identical. |
| 5 | no/no1/no2 declarations | Class instance field / m1 local / m2 local. |
| 6 | Lexical scopes | Field plus two separate method blocks; no sibling-local visibility. |
| 7 | Static/instance relationships | m1/m2 instance; m3/main static; no instance; sno static. |
| 8 | Relevant callsites | main lines 34, 35, 37; all same-file calls identified structurally. |
| 9 | Exact author constraints | Quoted above; full exact receipt prompt retained. |
| 10 | Contradictory clauses | No multi-member drafting contradiction established. |
| 11 | Canonical envelope | Normalized [115,828), raw [121,856); exact gaps preserved. |
| 12 | Scratch variants | Baseline plus A/B/C/D compiled; C0 shape rejected before compilation. |
| 13 | Touched structural locations | A/B/C/D change m1/m2/m3 only; no real file edited. |
| 14 | Compile outcomes | Baseline failed 5; A passed 0; B passed 0; C failed 1; D failed 3. |
| 15 | Any in-scope compile pass? | Yes, A and B. |
| 16 | Behavioral assumptions | Initializer-value substitution and either fresh-instance state or a static-field typo; no correctness claim. |
| 17 | Outside edits required? | Not for demonstrated compile repairs; conditional for C/D. |
| 18 | Smallest required outside location | None unconditionally; conditional callsite/field locations described above. |
| 19 | Task-text loss | Present, but original task supplies no missing behavior specification. |
| 20 | Deterministic primary class | `COMPILE_FEASIBLE_BUT_SEMANTICS_UNDERDETERMINED`. |
| 21 | Was abstention justified? | Epistemically defensible; raw structural impossibility rationale was broader than the evidence supports. |
| 22 | Is AUTHOR_MODEL_OUTPUT causal? | Observed terminal state only; causal model failure is not established. |
| 23 | Is RepairScope sufficient? | Independently proven compile-sufficient for this file. As produced it is a diagnostic-owner surface; semantic sufficiency is not established. Do not equate diagnostic owners with universally required repair locations. |
| 24 | Final Java hashes | All 17 receipt-listed files retain exact SHA-256, byte size and mtime_ns, matching both audit entry and frozen SPAN.1. Complete before/after maps retained in evidence. |
| 25 | Product files changed | Exactly zero. All 1,159 recorded C.A.T.T.U.S files retain hash, size and mtime. Only new audit documents/data and isolated scratch artifacts were written. |
| 26 | Live provider calls | Zero. No comparative models, replay, network request, or installation. |
| 27 | Graph/index/traversal | Graph/index/embedding operations zero; Java repository traversal zero. Hash reads use only 17 known receipt paths. Initial C.A.T.T.U.S guidance/artifact discovery used rg and directory listings; it was not a Java source search. |
| 28 | Exactly one next phase | `DIAG.REPAIR.INTENT.1 — MainApp behavior and state-ownership clarification`. Establish intended outputs and whether values are shared or independent, including m3's receiver/static-state intent. |

Twosum remained preserved requested context and an integrity-hash entry only; it was not analyzed or compiled. No Apply, PATCH.MINIMAL evaluation, remediation code, or expansion of authority occurred. Stop condition reached: the current edit surface can express compile fixes, while the evidence does not establish that the live author could safely select a behaviorally defensible one.
