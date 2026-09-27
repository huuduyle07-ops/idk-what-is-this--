# PATCH.AUTHOR.LIVE.2 — Self-Contained Authoring Contract Parity

**Date:** 2026-09-10
**Track:** CONTROL (phase-id namespace `PATCH.*`, no new track, no schema dimension)
**Status:** complete
**Prerequisites:** PATCH.AUTHOR.LIVE.1, PATCH.MINIMAL.LIVE.1/.2,
DEFECT.PROBE.LIVE.4/.5, CANDIDATE.VERIFY.LIVE.1, DEFECT.FACT.LIVE.1,
PATCH.BASIS.LIVE.1, CONTROL.LOCALIZE.LIVE.2, RETRIEVE.LIVE.4

---

## 1. The measured defect

PATCH.AUTHOR.LIVE.1 did its job. In the Round-9 live T6 run it generated
deterministic behavioral counterexamples, performed exactly one stateless
revision provider call, and got back a materially better implementation
strategy — substance that passed the then-current four behavioral cases plus
eight diagnostic cases.

None of that reached candidate normalization, because the response came back as:

```json
{
  "target_snippet": "...",
  "replacement_snippet": "..."
}
```

The parser refused it as `revision_output_carried_no_patch_candidate`. That
refusal was **correct**: `replacement_snippet` is not a field the runtime reads,
and there is no top-level `patch_candidate` wrapper.

Comparing the two prompts established why the model wrote that envelope.

| material | initial-draft prompt | revision prompt (pre-LIVE.2) |
|---|---|---|
| `patch_candidate` wrapper | ✅ | ❌ |
| `patched_snippet` / `target_snippet` field names | ✅ | ❌ |
| operation types and required fields | ✅ | ❌ |
| output-only / "either candidate or plan" rules | ✅ | ❌ |
| response envelope (`PATCH_RESPONSE_SCHEMA`) | ✅ | ❌ |
| source-visible identifier constraints | ✅ | ❌ |
| `FORBIDDEN` / `safe_minimal` constraints | ✅ | ❌ |

The revision prompt said, in full:

> "Return the normal patch-candidate JSON schema and nothing else."

**The provider call is stateless.** "The normal schema" named a protocol that
call had never been shown. The model was asked to reproduce a contract from a
conversation it was not part of.

A second consequence was measured at the same time. The revision used the novel
member `lstrip`, which PATCH.MINIMAL.LIVE.2 blocks as `novel_external_reference`
— and the initial draft *had* been shown the candidate-language constraints
while the revision had not. Two symptoms, one asymmetry.

---

## 2. The invariant

> Every stateless model call expected to produce the same patch-candidate
> artifact type must receive the authoritative contract needed to construct it.

Initial patch authoring and verification-guided revision authoring share **one**
authoring-contract definition. Their task and evidence context differ — and
should. Their candidate wire contract must not.

---

## 3. Ownership graph, before

This was inventoried before anything was edited. The initial-draft contract was
not one function's property:

| material | pre-LIVE.2 owner |
|---|---|
| candidate + plan wire shapes, field names, operation shapes, "either/or" rules | `core/control_engine.py::_patch_output_format_block` (inner `common_shapes` literal) |
| per-style output rules (`safe_minimal` / `balanced` / `vibe`) | same function, three branches |
| source-visible identifier list, `FORBIDDEN in patched_snippet` | `core/control_engine.py::_safe_minimal_forbidden_block` |
| `balanced` / `vibe` candidate-language sentences | inline literals inside `build_control_prompt` (lines 2491–2500) |
| response envelope | `core/prompter.py::PATCH_RESPONSE_SCHEMA` |
| revision contract | **nothing** — one sentence in `core/candidate_revision.py::_INSTRUCTION` |

Three files, five sites, and the revision path connected to none of them.

## 4. Ownership graph, after

| responsibility | owner |
|---|---|
| how a model is told to construct a patch candidate | `core/patch_authoring_contract.py` |
| what payloads are accepted | `core/candidate_revision.py::parse_revised_candidate` — **untouched** |
| which candidate language is eligible | `PATCH.MINIMAL.LIVE.1/.2` — **untouched** |
| whether a candidate is correct | `DEFECT.PROBE.LIVE.4/.5` — **untouched** |

`core/patch_authoring_contract.py` is stdlib-only (`hashlib`, `re`,
`dataclasses`) and holds:

- `PATCH_RESPONSE_SCHEMA` — moved from `core/prompter.py`, which now re-exports it
- `patch_output_format_block(style)` — moved verbatim from `_patch_output_format_block`
- `safe_minimal_forbidden_block(source_snippet)` — moved verbatim
- `BALANCED_CANDIDATE_LANGUAGE` / `VIBE_CANDIDATE_LANGUAGE` — moved from the inline literals
- `candidate_language_block(style, source_snippet)` — the same three-way dispatch
- `render_patch_authoring_contract(*, style, source_snippet) -> PatchAuthoringContract`

`core/control_engine.py` keeps `_patch_output_format_block` and
`_safe_minimal_forbidden_block` as **delegating shims**, and gains one accessor:

```python
def authoring_contract_for_control_result(control_result) -> PatchAuthoringContract
```

which resolves the style from the same `build_patch_policy` call
`build_control_prompt` makes, and the source snippet from the same
`patch_intent`. Both authoring paths call **this one accessor**.

---

## 5. Shared contract vs call-specific context

`PatchAuthoringContract.sections` is the authoritative material and is
byte-identical in both prompts:

1. `output_format_block` — wire shapes, field names, operation shapes, output-only rules
2. `candidate_language_block` — identifier / novelty constraints for the style
3. `response_schema_block` — the response envelope

`text` is their canonical `"\n\n"`-joined concatenation; `fingerprint` is
`sha256(text)`.

Everything else stays where it belongs:

- **initial-draft-specific** — CONTROL framing, scout, related context, phantom
  limb, lessons, preflight, repo-style hint
- **revision-specific** — the rejected Candidate₀ marked evidence-only, the
  failed cases, the preserved cases, one-revision semantics

The two whole prompts are **not** equal, and a test asserts they are not. Making
them equal would mean sending the revision the first draft's framing instead of
its counterexamples.

---

## 6. Contract identity

```
authoring_contract_version   = "patch_authoring_contract_v1"
authoring_contract_fingerprint = sha256(contract.text)
```

This identifies **prompt contract content**, never candidate bytes. It takes no
candidate input, is computed in the contract module, and is never compared with
a candidate fingerprint. It is not a second candidate-fingerprint primitive.

Determinism: fixed section order, no timestamp, no set iteration, no
model-generated text. `sorted(set(...))` in the identifier derivation was already
deterministic and is unchanged. 25 renders per style produce identical bytes.

---

## 7. What the revision prompt looks like now

```
REVISION REQUEST. …
ORIGINAL TASK (verbatim, unchanged): …
TARGET: core/code_dna.py::_classify_indent

PATCH CANDIDATE CONTRACT - authoritative, and identical to the contract the
first draft was given. It is repeated in full because this request is
stateless: nothing you were told in an earlier call is available to you now.
Every field name in it is protocol, and a synonym is not read.
<contract.text — 2 425 chars>

AUTHORITATIVE ORIGINAL SOURCE. …
REJECTED CANDIDATE - EVIDENCE ONLY. …
DETERMINISTIC VERIFICATION. …
INSTRUCTION. … Return exactly the JSON object the PATCH CANDIDATE CONTRACT
above specifies: a top-level patch_candidate object, whose target_snippet field
holds the bytes you are replacing and whose patched_snippet field holds the
bytes that replace them. Those field names are the protocol and no other
spelling is read. Return that JSON object and nothing else.
```

The contract sits **above** the source section deliberately: the moved
`safe_minimal` text says "identifiers that appear in the source_snippet below",
and that remains literally true.

A reader with no access to the initial prompt can now answer all five §14
questions: which JSON object to return, which key holds the candidate, which key
holds the replacement bytes, which operation fields are required, and which
lexical/structural constraints apply.

---

## 8. What did **not** move

**The parser is unchanged.** `parse_revised_candidate` was not edited. Pinned by
test:

| input | result |
|---|---|
| the captured Round-9 response, unchanged | `revision_output_carried_no_patch_candidate` |
| `replacement_snippet` | `revision_candidate_has_no_patched_snippet` |
| `replacement`, `new_snippet`, `diff_text`, `new_code` | same |
| bare candidate object, no wrapper | `revision_output_carried_no_patch_candidate` |
| `target_snippet` from Candidate₀'s bytes | `revision_candidate_is_not_based_on_the_original_source` |

No alias mapping, no typo recovery, no auto-wrapping, no post-hoc repair. A test
greps `core/candidate_revision.py` and asserts none of those alias spellings
appears anywhere in it — there is no alias table to grow because there is no
alias table.

**`lstrip` is still blocked.** `safe_minimal` is unchanged, the local novelty
caps are unchanged, and there is no identifier allowlist.

**Prompt text is advisory; the gate is authoritative.** A test drives the raw
Round-9 envelope through the live pipeline and asserts the contract *did* travel
in the prompt and the run still ended at `revision_output_invalid`. Prompt
compliance never substitutes for gate evaluation.

---

## 9. Red / green

**Pre-LIVE.2 → post-LIVE.2, same substance:**

| scenario | before | after |
|---|---|---|
| A. raw Round-9 envelope | `revision_output_carried_no_patch_candidate` | **unchanged** — still invalid |
| B. same substance, correct envelope | (could not be produced) | parses → fresh fingerprint → `novel_external_reference` (`lstrip`) |
| C. local-only correct candidate | parses | parses, admitted, 5/5 cases, verified, authorizes nothing |
| D. dead-guard Candidate₀ → deterministic adapter | contract absent from prompt | full contract in prompt, exactly one Candidate₁, all gates rerun |

**B is the phase succeeding.** It fixes schema blindness, not the algorithm. The
Round-9 candidate remains rejected, and it should be.

C ends with `behavioral_matrix_case_count == 5`, `fixed_and_preserved`,
`candidate_verification_status == verified`, `execution_authorized == false`,
`auto_apply_allowed == false`, `write_authority == false` and
`core/code_dna.py` byte-identical on disk.

---

## 10. Parity and drift tests

- **Section parity** — every `contract.sections` entry appears verbatim in the
  initial-draft prompt; `contract.text` appears verbatim in the revision prompt.
- **Fingerprint parity** — both paths resolve the same contract for the same
  target/source/safety context.
- **Drift** — monkeypatching `patch_authoring_contract.patch_output_format_block`
  with a sentinel makes the sentinel appear in **both** prompts. A path that
  stopped consuming the shared renderer fails here.
- **Safe-minimal drift** — the same, for
  `patch_authoring_contract.safe_minimal_forbidden_block`.
- **No second definition** — `PATCH_RESPONSE_SCHEMA` is assigned in exactly one
  production module; the two `control_engine` shims are asserted to hold no
  string literal but their own docstring; `core/candidate_revision.py` is
  asserted to contain no schema literal of its own.

The parity tests do not maintain a second expected schema. There is one object,
so there is nothing to keep in sync by hand.

---

## 11. Containment

An A/B loaded the pre-phase `core/control_engine.py` alongside the shipped one
and compared `build_control_prompt` across **82 configurations** — five styles ×
defect/feature route × present/absent source × present/absent related context ×
handoff eligible/not, plus both human-prompt branches. **0 mismatches.** The
initial-draft prompt is byte-identical.

`tests/fixtures/patch_author_live2_contract_reversal.json` stores the hunks that
reverse this phase's edits, so a test reconstructs the pre-phase bytes from the
shipped files and asserts the pre digests:

| file | added | changed | removed | hunks |
|---|---|---|---|---|
| `core/candidate_revision.py` | 0 | 3 (`CandidateRevisionReceipt`, `build_revision_prompt`, `candidate_revision_guardrails`) | 0 | 9 |
| `core/control_engine.py` | 1 (`authoring_contract_for_control_result`) | 3 (two shims + `build_control_prompt`) | 0 | 4 |
| `core/pipeline.py` | 0 | 1 (`_maybe_revise_rejected_candidate`) | 0 | 3 |
| `core/prompter.py` | 0 | 0 | 0 | 1 |

Five earlier fixtures pinned these files. All move, each with a
`*_pre_live2_sha256` and a `patch_author_live2_repin_note`.
PATCH.AUTHOR.LIVE.1's pipeline reversal now **chains** — undo LIVE.2, assert
LIVE.1's `post_sha256`, undo LIVE.1, assert its `pre_sha256` — which keeps that
number a live assertion rather than a stale one.

### 11b. The concurrent edits, and re-anchoring on them

While this phase was being verified, a separate, explicitly requested **harness
remediation** edited `core/pipeline.py`, `core/defect_probe.py`,
`patching/patch_gates.py` and `core/targeted_repository_validation.py`. Mid-phase
those edits looked like unrecorded drift, so this fixture was briefly rebuilt
against the in-flight bytes and two frozen pins were taken from them.

Once the remediation finalized it turned out to be documented and reversible:
`tests/fixtures/2026-09-10-harness-remediation-reversal.json` records exact hunks,
and the test-only helper `tests/_harness_maintenance.py::before_harness_remediation`
undoes them and asserts both digests. Its `core/pipeline.py` **preimage is exactly
this phase's post**, which gives one canonical chain:

```
shipped 6b9efb3f ──undo remediation──▶ d135ecda  (LIVE.2 post)
                 ──undo LIVE.2──────▶ 67c83a2e  (LIVE.1 post)
                 ──undo LIVE.1──────▶ 7bb9ca12  (LIVE.1 pre)
```

The fixture was re-anchored on it: the pipeline reversal is LIVE.2 post → LIVE.1
post again, the two in-flight pins (`patch_gates.py`,
`targeted_repository_validation.py`) are back to the history every other phase
pins, and every entry is evaluated after the helper. The remediation had routed
this suite's two governance tests around the stale entries by borrowing digests
from other fixtures and from its audit JSON; with the fixture correct those
special cases are gone, and each test asserts only this fixture's own digests.
PATCH.AUTHOR.LIVE.1's `_without_live2` asserts the LIVE.2 post digest again, so
its chain is checked at every link — and perturbing that one digest turns all
three chain tests red.

The remediation left three frozen-pin tests reading raw bytes —
DEFECT.PROBE.LIVE.4, DEFECT.PROBE.LIVE.5 and CONTROL.LOCALIZE.LIVE.2. They now
use the same helper: **71 pins, 0 mismatches, and not one historical fixture
re-pinned.** The remediation's own bytes are described only by its own receipt.

---

## 12. Cost

| measure | value |
|---|---|
| shared contract render | ~15 µs; 500 renders < 2 s |
| initial prompt size delta | **0 chars** (byte-identical) |
| revision prompt size delta | **+2 713 chars** — contract 2 425 + heading 285 + 3 separator chars |
| model calls added | **0** |
| network calls added | **0** |
| retrieval calls added | **0** |
| repository traversals added | **0** |
| index/embedding work added | **0** |

The intended cost is prompt text. Building the contract is prompt construction
over bounded state the caller already holds.

---

## 13. Telemetry

Three facts, inside `candidate_revision_receipt` only:

```
authoring_contract_version
authoring_contract_fingerprint
revision_contract_present
```

They are deliberately **not** flattened beside the receipt. §34 records that
`candidate_revision_receipt` already duplicates telemetry flattened next to it;
adding three more flattened keys would make that worse. No new payload key is
introduced, so ANSWER.GROUND.LIVE.4's ownership boundary is untouched and it
annotates nothing here. The contract text itself is never stored in a receipt.

---

## 14. Boundaries held

Unchanged, and pinned: `PATCH.MINIMAL.LIVE.1/.2`, `DEFECT.PROBE.LIVE.4/.5`,
candidate verification, revision eligibility, `MAX_REVISION_CALLS_PER_RUN = 1`,
retrieval, CONTROL, targeted validation, `EXEC.AUTH` / `EXEC.POLICY` /
`EXEC.APPROVAL`, `_classify_indent`, model confidence semantics, T5, and T4's
`explicit_change` lifecycle (its branch consumes the shared
`output_format_block`, which is where that material already came from; nothing
else about it moved).

---

## 14b. The fix broke six tests that depended on it being broken

An A/B (revert LIVE.2's four files, move its module and suite aside, drop its
registry entry, re-run) attributed six adjacent failures to this phase —
**6 passed reverted, 6 failed present**:

- `test_defect_probe_matrix_live5.py::test_smoke_the_inverted_reorder_is_rejected_for_preservation`
- `test_defect_probe_matrix_live5.py::test_smoke_the_round8_ceiling_is_rejected_for_the_depth_variants`
- `test_defect_probe_matrix_live5.py::test_the_four_bad_candidates_fail_for_four_different_reasons`
- `test_patch_minimal_live.py::test_byte_changing_candidate_still_reaches_the_verification_producers`
- `test_candidate_verification.py::test_known_wrong_t6_candidate_through_the_live_no_mutation_branch`
- `test_candidate_verification.py::test_a_candidate_whose_subject_invariant_is_open_is_rejected_not_verified`

The chain, read straight off the captured stdout:

```
🧮 DEFECT.PROBE.LIVE.4 behavioral matrix: partially_fixed over 5 bounded cases
🛑 CANDIDATE.VERIFY.LIVE.1 candidate verification: rejected — subject_invariant_not_closed
✍️ PATCH.AUTHOR.LIVE.1 requesting one verification-guided revision on 1 counterexample(s)
🛡️ PATCH.MINIMAL: rejecting candidate — no_op_candidate
→ KeyError: 'behavioral_matrix_status'
```

Each of these fixtures drives the real `maybe_run_auto_patch` on a
behaviorally rejected T6 candidate **without stubbing
`_call_revision_provider`** — so PATCH.AUTHOR.LIVE.1's branch has been making a
**live Gemini call** in all three suites since it shipped. Before LIVE.2 the
answer was unusable, so `revision_output_invalid` returned early and Candidate₀'s
receipts survived for the assertions to read. After LIVE.2 the answer parses,
`_drop_candidate_bound_receipts` runs exactly as LIVE.1 specifies, Candidate₀'s
matrix and verification receipts are gone, and the assertions raise.

Nothing was weakened to fix this. Two of the three helpers already *claimed*
"§34 — no provider call" in their own docstrings; that claim was simply false.
An autouse fixture in each file now makes it true, holding the single revision
opportunity deterministically unavailable so the measurement stays on Candidate₀
and no provider is called. The revision path keeps its own coverage in
`test_candidate_revision_live.py` (98 tests) and
`test_patch_authoring_contract_live2.py` (44), both of which stub the adapter
explicitly.

The side benefit is real: three suites stopped making live network calls.

---

## 15. Known limitations

1. **The prompt is still only advice.** A model shown the exact schema can still
   return something else; when it does, the run ends at `revision_output_invalid`
   with no second attempt. Buying a guarantee would mean a repair call the budget
   forbids.
2. **The candidate-language block is style-shaped.** `balanced` and `vibe` still
   get their one-sentence constraints and `safe_minimal` still gets the
   identifier list — exactly as the initial author always did. Making the
   revision stricter or looser than the draft would be a new safety rule, which
   §9 forbids here.
3. **`AUTO_PATCH_ENABLED=true` is still out of scope.** LIVE.1's hook remains in
   the mutation-disabled branch only, so a default-configured run gets no
   revision. Wiring revision into the auto-apply path needs an explicit authority
   and lifecycle review and is deliberately not started.
4. **`candidate_revision_receipt` duplication is untouched.** §34 assigns it to a
   separate cleanup backlog, and extracting the contract did not require fixing
   it.

---

## 16. Readiness for the next provider smoke

Deterministic controls are green, so a live T6 run with the unchanged task, the
same Gemini author, `AUTO_PATCH_ENABLED=false` and one revision maximum is now
worth spending. What to record, per candidate, independently:

- whether Candidate₁ uses the correct envelope
- whether it respects the candidate-language constraints
- whether it introduces local novelty, and how much
- whether external novelty is rejected
- the five-case matrix result
- the final verification status

One sample settles the envelope question. It does not settle the algorithm
question, and nothing should be tuned from it.
