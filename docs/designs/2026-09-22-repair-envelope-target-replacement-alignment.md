# PATCH.AUTHOR.SPAN.1 — Repair-Envelope Target / Replacement Alignment

Implemented on 2026-09-22. Deterministic envelope alignment is complete. The single completed read-only Java replay returned no candidate and stopped at AUTHOR_MODEL_OUTPUT; Java files are unchanged.

The [completion receipt](../../tests/fixtures/patch_author_span1_completion.json) preserves the exact prompt, raw author response, scope/envelope, bootstrap/preflight receipts, before/after inventory, validation results and historical failure attribution. Local logs are in `.tmp/patch-author-span1/`.

| # | Required report item | Result |
|---:|---|---|
| 1 | Files changed | Six production files (five existing plus one new), one new focused suite, two maintenance helpers, registry/picker expectations, one registry record, and three evidence files plus this report. The exact 16-file list follows. |
| 2 | Old invalid shape | target_snippet=m1, patched_snippet=m1+m2+m3 would leave original m2/m3 outside the replacement and duplicate them. The deterministic live-shape regression rejects it before PATCH.MINIMAL. |
| 3 | Canonical envelope owner | Reuse AuthoringRepairScope.replacement_source and member_ranges. candidate_replacement_span.py projects and validates that interval; it never selects repair members or infers an interval from model output. |
| 4 | Source / binding | Same normalized authoring source, raw source fingerprint, repository/CONTROL/preflight evidence, and existing freshness/binding checks. The envelope has explicit Unicode-codepoint and UTF-8 offsets plus its own original-text SHA-256. |
| 5 | Primary target | MainApp.java::m1 remains the semantic target and target_node_name. Replacement span metadata is separate. |
| 6 | Editable members | Exactly the authoritative measured RepairScope members. No member-selection change; model-provided member/envelope claims grant nothing. |
| 7 | Read-only gaps | Every intervening byte outside measured members stays exact, including unmeasured definitions, whitespace, comments and unowned annotations. |
| 8 | One member | Historical prompt, context, telemetry, target/replacement validation and revision rebasing remain unchanged. No envelope contract is added. |
| 9 | Two members | A full canonical two-member envelope is admitted; supported exact sub-envelopes remain valid only when self-consistent. |
| 10 | Three members | The stateless deterministic author quotes all three members and replacement for that exact envelope. The candidate reaches the real unchanged minimality gate. |
| 11 | Subset edits | Full-envelope replacements may modify only m1 and m3, or only m1. No requirement that every measured member differ. |
| 12 | Target uniqueness | Canonical baseline envelope and candidate target must occur exactly once. Zero, multiple and overlapping exact matches are rejected; no first-match behavior. |
| 13 | Alignment | Exact original quote must stay within the canonical interval. Structural definition counts are checked on the projected whole-source replacement, followed by all existing member-diff and structural containment checks. |
| 14 | Duplicate prevention | The primary-only target plus multi-member replacement and duplicate-definition insertions receive duplicate_definition_risk. |
| 15 | Missing prevention | Missing or renamed definitions receive missing_definition_risk. New definitions or structurally unavailable output receive replacement_span_mismatch; existing structural post-checks remain mandatory. |
| 16 | Gap protection | Changes outside member-owned diff spans receive readonly_gap_modified. For measured [m1,m3], visible m2 stays exact even though the envelope includes it. |
| 17 | Stale source | Existing raw-byte freshness checks reject source changes before rendering or containment. No rebase onto fresh text. |
| 18 | Cross-file behavior | Existing author_scope_cross_file rejects another file, traversal spelling, or conflicting file/relative_path. Twosum stays outside the editable scope. |
| 19 | Initial / revision parity | Both receive identical canonical contract and scope metadata. Revision counterexample provenance and primary-source digest remain unchanged. Multi-member revision preserves the validated pair instead of expanding it; historical one-member rebase is unchanged. |
| 20 | Representation | Existing patch_candidate fields target_snippet and patched_snippet. original_snippet is author-context envelope metadata, not a new candidate wire field. patch_plan guidance and downstream prohibition remain unchanged. |
| 21 | Fingerprint | Existing primitive is byte-identical. Fingerprints commit to the actual original target and replacement. Tests prove both fields affect identity and accepted revision pairs retain it; invalid output is never silently rewritten. |
| 22 | Typed reasons | author_output_status reports valid_replacement_span or a specific typed reason. authoring_scope_status retains the historical containment classification. Revision uses the same span rejection vocabulary. |
| 23 | Prompt delta | Multi-member edits explicitly quote replacement_envelope.original_snippet as target_snippet and replace that same interval. Separate primary source, member snippets, envelope and read-only whole-file context. No solution hints or span-selection model calls. |
| 24 | Task-text observation | The completed replay still sends [USER] = Generate patch. Original-task transport was not repaired. |
| 25 | AUTHOR.SCOPE delta | Membership, measured ordering, overlap checks, source binding and editable spans are unchanged. Only additive span checking and typed output validity are introduced. SCOPE.1 completion evidence is byte-identical. |
| 26 | BASIS delta | Zero. repair_scope.py, patch_basis.py and structural source-grounding code are byte-identical. |
| 27 | PREFLIGHT / CONTROL delta | Zero semantic change. control_engine.py has one multi-member prompt sentence change; localization, bootstrap, preflight measurement and authority functions remain unchanged. |
| 28 | PATCH.MINIMAL delta | Zero. policy/ and patching/ are frozen. Deterministic valid-envelope fixtures reach the existing gate and are rejected by its existing no-op-function heuristic. The live replay did not reach it. |
| 29 | Authority delta | None: write_authority=false, execution_authorized=false, auto_apply=false; human approval remains required. No Apply was invoked. |
| 30 | UX / security / mutation delta | None. web/, agents/, mutation, rollback/Undo and security production files are frozen. UI receipt loss, null-candidate status, UX-05/06 and T6 Round 11 are untouched. |
| 31 | Performance | 15 samples, no model latency. Median/max milliseconds: envelope 2.486/5.320; alignment 1.375/2.430; full structural containment gate, including alignment, 9.615/18.731. No traversal. |
| 32 | Model / network | Focused tests: zero providers and external network. One completed live replay used one normal bootstrap boundary and one normal author boundary. A preceding transport attempt failed with sandbox WinError 10013 before a provider response and was retried with network permission. Zero extra span-selection calls and no replay retry after the author result. |
| 33 | Focused tests | 37 SPAN.1 tests passed; combined earlier SPAN/SCOPE/LIVE.3/BASIS.SCOPE/registry/picker run passed 389 tests. Phase-entry baseline passed 354. Detailed matrices include Unicode, normalized CRLF, adjacent/overlapping definitions, malformed spans, readonly gaps, stale source, revisions and fingerprints. |
| 34 | Adjacent / broad tests | Affected pipeline/envelope/byte-fidelity/plan suite: 129 passed. Security/mutation suite: 764 passed, 13 historical pin failures. All requested adjacent/gate results appear below. The initial revision run timed out under concurrent validation; its completed isolated rerun is recorded. |
| 35 | Registry / benchmarks | Exactly one PATCH.AUTHOR.SPAN.1 record; 196 phases validate. Registry/picker tests pass. benchmarks --check: 54 checked, 0 errors. compileall and git diff --check pass. No full-suite-green claim. |
| 36 | Frozen attribution | 1143 phase-entry files remain byte-identical; ten authority/semantic definitions compare equal as ASTs. All 31 historical pin failures reproduce against captured entry bytes. Test-only reversal removes this phase before older immutable receipts; old fixtures were not repinned. |
| 37 | Live RepairScope | Complete same-file measured scope: MainApp.java::m1, ::m2, ::m3. Primary is m1; compiler error counts are 1, 1, 3. |
| 38 | Live AuthoringRepairScope | Same three members, same receipt/source binding and bounded normalized source. Whole-file context grants no outside edit authority. |
| 39 | Live envelope | Normalized interval [115,828), 713 UTF-8 bytes, from m1 start to m3 end. SHA-256 ee6f58cff81fa3e62064a722b7581ae05fc980c1cd2367cbf7d1f6fb09ede26f. Raw-file binding 6e84dc30157e53e9c10b775bc0da48b2be63f5a33583130527f7cd4edba7ae39. |
| 40 | Live raw candidate | patch_candidate=null, confidence=0.2, needs_escalation=true. The author declined to draft a fix under existing variable-scope/class-structure constraints. Raw response and prompt are preserved in the completion receipt; prose is not validation evidence. |
| 41 | Live validity | No candidate was emitted, so span validation was not invoked. Candidate original/replacement spans are absent, not inferred or filled in. |
| 42 | Live fingerprint | None: no admitted live candidate. Deterministic fingerprint parity passed. |
| 43 | PATCH.MINIMAL result | Live: not reached. Deterministic valid-envelope candidate: reached; frozen rejection remains authoritative. |
| 44 | CRLF result | Live apply/exact-byte matching: not reached. Authoring-normalized CRLF test passes without changing raw files. Raw-file CRLF behavior is untouched. |
| 45 | Java validation result | Not reached; no Java candidate validator was added. |
| 46 | Final Java hashes | All 17 top-level repository file hashes, sizes and mtimes match before/after and final recheck. MainApp.java=6e84dc30157e53e9c10b775bc0da48b2be63f5a33583130527f7cd4edba7ae39; Twosum.java=b6164c74cd30eeaabf6368346b36e08e23fdf2afb6f36471bcf12e611decfc8c. Full inventory is in the receipt. |
| 47 | First remaining blocker | AUTHOR_MODEL_OUTPUT: the single live author abstained despite the expressible deterministic envelope contract. No evidence that live minimality, CRLF or Java verification is the next blocker. |
| 48 | Recommended next phase | A separately scoped investigation of author abstention/output under existing constraints. No PATCH.MINIMAL remediation is justified by this replay. |

Explicit answers:

| Question | Answer |
|---|---|
| Does a multi-member candidate quote the same original envelope it replaces? | Yes for the canonical deterministic shape; coherent exact sub-envelopes remain supported. The live author emitted no candidate. |
| Can the model replace only m1 while injecting m2/m3? | No. Rejected before PATCH.MINIMAL. |
| Can read-only gaps be changed? | No. |
| Is m1 still the primary semantic target? | Yes. |
| Are editable members exactly the measured RepairScope? | Yes. |
| Did PATCH.MINIMAL policy change? | No. |
| Did authority change? | No. |
| Were CONTROL/PREFLIGHT/BASIS semantics changed? | No. |
| Were extra live model calls added for span selection? | No. |
| Did the replay reach PATCH.MINIMAL? | No; AUTHOR_MODEL_OUTPUT returned patch_candidate=null. Deterministic valid-envelope tests did reach it. |

Files changed in this phase:

- `docs/roadmap/phase_registry.json`
- `core/control_engine.py`
- `core/candidate_revision.py`
- `core/candidate_authoring_context.py`
- `core/authoring_repair_scope.py`
- `core/patch_authoring_contract.py`
- `tests/test_phase_registry.py`
- `tests/test_phase_picker.py`
- `tests/_patch_author_scope1_maintenance.py`
- `core/candidate_replacement_span.py`
- `tests/test_patch_author_span1.py`
- `tests/_patch_author_span1_maintenance.py`
- `tests/fixtures/patch_author_span1_reversal.json`
- `tests/fixtures/patch_author_span1_frozen.json`
- `tests/fixtures/patch_author_span1_completion.json`
- `docs/designs/2026-09-22-repair-envelope-target-replacement-alignment.md`

Validation results (overlapping runs are listed separately and are not summed):

| Suite | Result |
|---|---|
| Phase-entry baseline | 354 passed, 1 warning in 77.67s (0:01:17) |
| Focused SPAN.1 final | 37 passed, 1 warning in 11.16s |
| Combined SPAN / SCOPE / LIVE.3 / BASIS.SCOPE / registry / picker | 389 passed, 1 warning in 49.60s |
| Security / mutation / Undo / rollback / AUTH.DREAM | 13 failed, 764 passed, 1 warning in 488.96s (0:08:08) |
| Affected pipeline / envelope / byte fidelity / plan routes | 129 passed, 1 warning in 30.17s |
| tests/test_patch_authoring_contract_live2.py | 2 failed, 42 passed, 1 warning in 332.76s (0:05:32) |
| tests/test_candidate_revision_live.py | 1 failed, 97 passed, 1 warning in 278.88s (0:04:38) |
| tests/test_patch_basis_target1.py | 35 passed in 3.47s |
| tests/test_preflight_request1.py | 3 failed, 94 passed, 1 warning in 166.46s (0:02:46) |
| tests/test_control_fresh1.py | 3 failed, 102 passed, 1 warning in 11.41s |
| tests/test_control_bootstrap1.py | 3 failed, 111 passed, 1 skipped, 3 warnings in 21.31s |
| tests/test_indent_runtime1.py | 27 passed, 1 warning in 3.25s |
| tests/test_indent_semantics1.py | 1 failed, 147 passed, 1 skipped, 1 warning in 234.99s (0:03:54) |
| tests/test_answer_coherence_live1.py | 1 failed, 34 passed, 24 skipped, 1 warning in 2.78s |
| tests/test_patch_minimal_live.py | 48 passed, 1 warning in 99.35s (0:01:39) |
| tests/test_patch_minimal_novelty_live.py | 2 failed, 79 passed, 1 warning in 195.74s (0:03:15) |
| tests/test_patch_minimal_binding_context_live3.py | 24 passed, 1 warning in 5.29s |
| tests/test_patch_minimal_result_fields_live3.py | 1 failed, 107 passed, 1 warning in 56.75s |
| tests/test_candidate_verification.py | 1 failed, 57 passed, 1 warning in 262.59s (0:04:22) |
| tests/test_candidate_sandbox_validation.py | 40 passed, 1 warning in 155.15s (0:02:35) |
| tests/test_execution_eligibility_policy.py | 36 passed, 1 warning in 4.54s |
| tests/test_human_apply_authorization.py | 22 passed in 22.36s |
| tests/test_control_safety_live.py | 15 passed, 1 warning in 7.83s |
| tests/test_patch_safety_chokepoint.py | 22 passed, 1 warning in 12.75s |
| tests/test_dream_apply_safety.py | 1 passed, 1 warning in 6.20s |

The 31 failed historical pin assertions also fail against captured phase-entry bytes. They concern earlier frozen reconstruction, principally core/control_engine.py and tests/test_phase_registry.py. Their individual node IDs and assertion details are preserved in the completion receipt. They were not repaired or relabeled as passes.
