# PATCH.AUTHOR.SCOPE.1 — Measured Repair-Set Authoring Scope

Completed on 2026-09-22. Authoring across the exact measured repair set is expressible and bounded. One fresh read-only Java replay produced an invalid replacement span and stopped at `AUTHOR_OUTPUT_VALIDITY`; no Java file changed. DOGFOOD.JAVA.2 remains frozen audit history.

The [completion receipt](../../tests/fixtures/patch_author_scope1_completion.json) preserves the exact prompt, raw output, post-gate result, compiler/bootstrap receipts, provider attempts, fingerprints, and before/after file inventory. Local execution logs are under `.tmp/patch-author-scope1/`.

| # | Required report item | Result |
|---:|---|---|
| 1 | Files changed | Six production files (five existing and one new), three existing test/governance helpers, the phase registry, and six new test/evidence/document files. The exact 16-file list follows. |
| 2 | Old authoring scope | One primary function. DOGFOOD.JAVA.2 produced no candidate because the author treated multi-method repair as outside its capability. |
| 3 | New scope owner | CandidateAuthoringContext.authoring_repair_scope, backed by the additive AuthoringRepairScope projection/containment helper. No separate authoring system. |
| 4 | Primary target | MainApp.java::m1 is retained as the localized primary target and candidate target_node_name. |
| 5 | Repair-set source | Only the already-built PATCH.BASIS.SCOPE.1 RepairScope. AUTHOR verifies its members but never selects or adds members. |
| 6 | Repair members | MainApp.java::m1, MainApp.java::m2, MainApp.java::m3, ordered by their measured structural positions. |
| 7 | Receipt / freshness | Receipt, repository, CONTROL and raw-source fingerprints must agree with current-run preflight. Exact source is rechecked before rendering and candidate containment; stale bytes are rejected without rebuilding old evidence over a new file. |
| 8 | Same-file restriction | All members and candidate operations must name the primary file. Another file, traversal spelling or inconsistent file/relative_path is rejected. |
| 9 | Exact source exposure | Every member retains its complete measured snippet and span. replacement_source is a bounded quote covering the members; any intervening source remains read-only. No file contents are normalized on disk. |
| 10 | Diagnostic exposure | Each member receives only its associated typed compiler diagnostics. Live counts: m1=1, m2=1, m3=3. The compiler wording, file, line and column are preserved; model explanations are not substituted. |
| 11 | Member-local bindings | Each member has its own existing AuthoritativeBindingContext projection. A same-spelled parameter/local in another function is a different environment. The existing Python proof owner is reused; no new Java binding-proof policy is invented. |
| 12 | File-level bindings | Existing proven direct imports and immutable-result read capabilities remain under the existing owner and shadowing rules, projected within each member environment. Import modification authority does not expand. |
| 13 | Bounds | At most 8 definitions and 16,384 aggregate snippet bytes. The existing single-candidate representation also has a 16,384-byte replacement-envelope cap, including read-only gaps; canonical repair metadata is capped at 65,536 bytes. Overflow raises author_scope_budget_exceeded; no member is dropped. |
| 14 | Single-member behavior | One member keeps the LIVE.3 v2 contract and v1 scope text/fingerprint semantics. Absent/not-applicable RepairScope keeps the historical single-target path. A supplied stale/malformed measured receipt fails closed. |
| 15 | Two-member behavior | Deterministic tests expose both exact sources, diagnostics and separate binding namespaces, and admit edits confined to those members. |
| 16 | Three-member behavior | The stateless test author emits a real existing-format candidate editing all three members. It is admitted for authoring; no claim of correctness or minimality is made. |
| 17 | Unrelated-member negative | For measured [m1,m3], editing visible m2 is authoring_scope_violation. The model cannot enlarge the boundary with its own target list. main, helper and another class also fail. |
| 18 | Cross-file negative | Twosum.java is rejected by author containment before PATCH.MINIMAL, including conflicting file and relative_path fields. |
| 19 | Malformed / stale scope | Incomplete diagnostics, wrong receipt/source/repository/CONTROL binding, ambiguous members, cross-file members, overlap and budget failures all refuse multi-member authoring. Fresh bytes are never silently substituted. |
| 20 | Initial / revision parity | Both render the same measured boundary and shared v3 measured-repair contract. Revision still binds original primary source and counterexample provenance; the replacement base may span the measured set. The existing one-member parser behavior is retained. |
| 21 | Candidate representation | No new wire format. patch_candidate may quote a unique bounded portion or the whole replacement envelope. Existing patch_plan operations can be checked for containment, but safe_minimal still forbids plans; the author is instructed to use patch_candidate. |
| 22 | Overlap handling | Original-source operation intervals must be non-overlapping. Candidate differences must belong to exactly one measured member; structural checks also prevent new/renamed/duplicated definitions and edits escaping through braces or indentation. |
| 23 | Member coverage | A candidate may modify a subset, including only m1. It must account for the full diagnostic set, but neither touched_members==repair_members nor a model claim of completeness is required/accepted as verification. |
| 24 | Prompt delta | The shared measured-repair section explicitly permits drafting across exactly the measured members, separates primary target from editable set, preserves read-only gaps, and leaves PATCH.MINIMAL and human approval downstream. No solution hints. |
| 25 | Task text observation | The live downstream [USER] text is still exactly Generate patch. Original-task transport was not fixed. |
| 26 | Preflight evidence delta | Zero measurement-policy change. The [PREFLIGHT VALIDATION] evidence is retained. The measured-scope marker refers to the authoring projection rather than repeating a second full repair-set block. |
| 27 | Authority delta | None: write_authority=false, execution_authorized=false, auto_apply=false, human approval required. |
| 28 | PATCH.MINIMAL delta | None; patching/ and policy/ bytes are frozen. A deterministic candidate reaches the existing gate and is rejected by its unchanged no-op-function heuristic. This is not evidence of a live one-function-cap rejection: the live candidate stopped earlier. |
| 29 | PATCH.BASIS delta | No semantic change. repair_scope.py, patch_basis.py and the structural target owner are byte-identical. Authoring consumes the previously built receipt on repeated rendering instead of selecting members again. |
| 30 | CONTROL delta | No localization, freshness, bootstrap or target-selection semantics changed. control_engine.py changes only its author-context accessor, prompt rendering and an additive author-containment call before the existing grounding gate. |
| 31 | Track-A delta | Only this requested authoring capability changes. No T6 remediation, Round 11, probe/oracle, result-field admission or unrelated Track-A work. |
| 32 | UX / security / mutation delta | Zero production change to web/, agents/, security, Apply, rollback/Undo or AUTH.DREAM. UI receipt loss remains observability backlog; null-candidate success UI is untouched. |
| 33 | Model / network | Focused tests use a stateless stub and forbid provider/socket calls: zero live providers and external network. Scope selection adds zero model calls. One live request used one bootstrap provider boundary and one author boundary; existing author-client fallback made four remote attempts (three HTTP 503 failures, then gemini-2.5-flash success). Bootstrap succeeded once on gemini-3.1-flash-lite. Fallback was recorded, not added or hidden. |
| 34 | Performance | 15 deterministic samples, no model latency: construction median 23.075 ms (max 32.304); shared contract/scope render 3.053 ms; full prompt render 68.068 ms (max 110.581); containment validation 10.180 ms (max 28.069). No added repository traversal. |
| 35 | Focused tests | 41 PATCH.AUTHOR.SCOPE.1 tests pass, including Unicode/CRLF fidelity and repeat-render receipt reuse. The final combined scope + LIVE.3 + BASIS.SCOPE run passed 87 tests, with zero live providers/network. |
| 36 | Adjacent / broad tests | See the complete validation table below. Required suites were run; historic entry-state hash failures are explicitly attributed. No full-suite-green claim. |
| 37 | Registry / benchmarks | One completed PATCH.AUTHOR remediation phase registered. Registry/picker: 267 passed; CLI registry valid (195 phases). benchmarks --check: 54 checked, zero errors. compileall and git diff --check pass. |
| 38 | Frozen attribution | 1,514 pre-existing files are byte-identical. Reversal hunks reconstruct exact phase-entry bytes for all 9 modified existing files. Older receipts are not repinned. Historical reconstruction failures on core/control_engine.py and tests/test_phase_registry.py reproduce with entry bytes; detailed proofs and test logs are retained. |
| 39 | Live RepairScope | Complete: MainApp.java::m1 at lines 7–13, m2 at 15–21, m3 at 23–29; five compiler errors. Twosum was requested/source-read and was not separately compiled. |
| 40 | Live authoring scope | Exactly those same three measured members, with m1 still primary. Receipt 0c218e5838fe2551597bc51dbf3d0c02f69c32f76791f88cbf86d64361c6119e; source 6e84dc30157e53e9c10b775bc0da48b2be63f5a33583130527f7cd4edba7ae39; CONTROL 8b529f7251c4a755cdb640d98cf62ed7a4479424a442373a0b8acf1561b8175a. |
| 41 | Live author result | The author returned patch_candidate, confidence=1.0 and needs_escalation=false. The author-containment gate then set candidate=null and needs_escalation=true with authoring_scope_violation. Model prose claiming compilation repair was not evidence. |
| 42 | Candidate produced | Yes. Raw candidate fingerprint: d39dae24f688357177abc41a40b915bdba4d1f08f8a6280800407313b8c8290f. The raw candidate and exact prompt are preserved. |
| 43 | Touched definitions | The quoted replacement target covers only m1, while patched_snippet contains m1/m2/m3. Applying that shape would insert duplicate m2/m3 beside their originals. No accepted touched-member set exists; nothing was applied. |
| 44 | Live PATCH.MINIMAL result | Not reached: the authoring candidate was rejected before downstream acceptance. No minimality policy conclusion is inferred. |
| 45 | Live CRLF result | Not reached. MainApp.java and Twosum.java retain their original CRLF bytes. |
| 46 | Live Java validation result | Not reached. No Java candidate-validation command was added. Existing read-only preflight javac evidence is preserved separately. |
| 47 | Final Java hashes | All 17 file hashes, sizes and mtimes match entry, including 9 Java sources and 8 existing class files; no new output exists. Full hashes follow and are stored in the completion receipt. |
| 48 | Write / execution authority | No Apply call, repository patch write, execution authorization or auto-apply. Verification/approval authority remains with existing downstream gates. |
| 49 | First remaining blocker | AUTHOR_OUTPUT_VALIDITY: target/replacement span mismatch. The candidate quotes m1 but attempts to insert three definitions. The phase stops at this measured rejection. |
| 50 | Recommended next phase | A separate author-output validity investigation of replacement-span alignment is justified. This replay does not justify changing PATCH.MINIMAL, CRLF or Java validation. No next-blocker remediation or second replay was performed. |

**Exact answers**

| Question | Answer |
|---|---|
| Can the author now draft across m1/m2/m3? | Yes; deterministic contract tests prove a valid draft is expressible. |
| Can it draft outside the measured RepairScope? | Outside-scope output can be emitted by a model, but it is rejected before downstream acceptance. |
| Is m1 still primary? | Yes. |
| Is multi-definition scope derived only from measured evidence? | Yes, only PATCH.BASIS.SCOPE.1 RepairScope. |
| Are member-local bindings distinct? | Yes, each member retains its own proof/environment. |
| Does single-target authoring remain unchanged? | Yes, the one-member/absent-scope contract and prompt semantics are preserved. |
| Can visible Twosum become editable? | No. |
| Did PATCH.MINIMAL policy change? | No. |
| Did patch/write authority change? | No. |
| Did CONTROL/PREFLIGHT/BASIS semantics change? | No; only authoring consumes their existing result. |
| Were extra live model calls added for scope selection? | No. |
| Did the live replay produce a candidate? | Yes, but it was rejected as AUTHOR_OUTPUT_VALIDITY before PATCH.MINIMAL. |

**Files changed in this phase**

- `docs/roadmap/phase_registry.json`
- `core/candidate_authoring_context.py`
- `core/control_engine.py`
- `core/candidate_revision.py`
- `core/pipeline.py`
- `core/patch_authoring_contract.py`
- `tests/_patch_basis_scope1_maintenance.py`
- `tests/test_phase_registry.py`
- `tests/test_phase_picker.py`
- `core/authoring_repair_scope.py`
- `tests/test_patch_author_scope1.py`
- `tests/_patch_author_scope1_maintenance.py`
- `tests/fixtures/patch_author_scope1_reversal.json`
- `tests/fixtures/patch_author_scope1_frozen.json`
- `tests/fixtures/patch_author_scope1_completion.json`
- `docs/designs/2026-09-21-measured-repair-set-authoring-scope.md`

**Validation results**

| Check | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Focused scope + LIVE.3 + BASIS.SCOPE | 87 | 0 | 0 |
| BASIS.TARGET / PREFLIGHT / CONTROL / registry / picker | 627 | 9 | 1 |
| Security / mutation / Undo / rollback / AUTH.DREAM | 750 | 13 | 0 |
| Affected pipeline / executor / envelope / byte fidelity | 157 | 0 | 0 |
| Registry and picker separately | 267 | 0 | 0 |
| tests/test_patch_authoring_contract_live2.py | 42 | 2 | 0 |
| tests/test_candidate_revision_live.py | 97 | 1 | 0 |
| tests/test_indent_runtime1.py | 27 | 0 | 0 |
| tests/test_indent_semantics1.py | 147 | 1 | 1 |
| tests/test_answer_coherence_live1.py | 34 | 1 | 24 |
| tests/test_patch_minimal_live.py | 48 | 0 | 0 |
| tests/test_patch_minimal_novelty_live.py | 79 | 2 | 0 |
| tests/test_patch_minimal_binding_context_live3.py | 24 | 0 | 0 |
| tests/test_patch_minimal_result_fields_live3.py | 107 | 1 | 0 |
| tests/test_candidate_verification.py | 57 | 1 | 0 |
| tests/test_candidate_sandbox_validation.py | 40 | 0 | 0 |
| tests/test_execution_eligibility_policy.py | 36 | 0 | 0 |
| tests/test_human_apply_authorization.py | 22 | 0 | 0 |
| tests/test_control_safety_live.py | 15 | 0 | 0 |
| tests/test_patch_safety_chokepoint.py | 22 | 0 | 0 |
| tests/test_dream_apply_safety.py | 1 | 0 | 0 |

There are 31 historical hash failures across these reported runs. The separate registry run overlaps the combined boundary run; BASIS.SCOPE also appears in both the focused and boundary runs. Counts are per run, not a claim of distinct tests or a full repository suite.

All 31 failures name historical `core/control_engine.py` / `tests/test_phase_registry.py` reconstruction. The exact entry/current comparison is retained in the completion receipt. No frozen history was repinned.

Failures are not suppressed. The historical failures reproduce from captured entry bytes. Earlier aggregate author/gate runs interrupted during continuation were superseded by durable per-file runs; they are not counted as complete. Unrelated live-provider test debt is not modified.

**Final Java-folder SHA-256 hashes**

| File | SHA-256 |
|---|---|
| `armstrong.java` | `c5df23eb11358dcabcc93da39de57b791fb75f63904169f0bb6d9c2b5f6c2422` |
| `bank.java` | `361a600f98447b05876e3d0fbf3a6ea56e4bcf82abf588df6fb09a312fc7d806` |
| `BankAccount.class` | `d71ced44380a37609f954b1a2f99115c6b526c64ae7543cf9945b1b21f7b85c6` |
| `fibonacci.java` | `0d462d1bff4a6d8c8db963343030a558b6f98c956e65656d34212e4cd02345db` |
| `library.java` | `96bbbd21f528616adf68674bc2561a679a20618f2a67491fbfc624b5f171f635` |
| `MainApp.class` | `861b89fc437033d1b890a742a9ef834f5cb6e12b4d16a34ee67debebcdf0b88f` |
| `MainApp.java` | `6e84dc30157e53e9c10b775bc0da48b2be63f5a33583130527f7cd4edba7ae39` |
| `Number.class` | `f5aacd34d00a08e742e9c87ca89d3354287cc03d693152d5dc90ad8599885fc1` |
| `Number.java` | `b2c14795b46840946dbd30ac887f1b1e82572356ea58a0f6a7ed5db6abdb3a27` |
| `Solution.class` | `0bc15508dbc170f22092bc80ffafa8945e3fef67b7a5bfab585c4ae6217b136e` |
| `star.class` | `ebf3e39afff1604ec2d8a355885ddc3a03791a03c0a8ed552abe5adb04744f4e` |
| `star.java` | `695b7f8adb414fd62aa6804facfbe8e05401a0415f2389137d3d872837c1268e` |
| `Student.class` | `d4763b44c30f29f654d683a6a00f01c116bcbfc0671def6cdfcaf5cb47498b01` |
| `student.java` | `f373fbf64bcdec6f8a72b4631455ccb164326605a1cd4cf15d75a311025da4d9` |
| `Students.class` | `5f1e6f7c9b30c97e243f016cffc7d1c25c6ba54fee3ae7781f7e469dfc2c8071` |
| `Twosum.class` | `0bc62faf57345cf83697c76db4c3b6b8b006f22f068b2aa4b2b07d5870dd2665` |
| `Twosum.java` | `b6164c74cd30eeaabf6368346b36e08e23fdf2afb6f36471bcf12e611decfc8c` |

Both requested source files remain byte-identical, including line endings. Compilation evidence does not certify the rejected candidate.
