# ANSWER.COHERENCE.LIVE.1 — Candidate-Bound Final Response Provenance

**Date:** 2026-09-11
**Track:** CHECK (phase-id namespace `ANSWER.*`, no new track, no schema dimension)
**Status:** complete
**Prerequisites:** PATCH.AUTHOR.LIVE.1/.2, CANDIDATE.VERIFY.LIVE.1,
DEFECT.PROBE.LIVE.5, PATCH.MINIMAL.LIVE.1/.2, ANSWER.GROUND.LIVE.4,
EXEC.POLICY.LIVE.1, EXEC.APPROVAL.LIVE.1, EXEC.AUTH.LIVE.1

---

## 1. The measured defect

Round 10 produced two real candidates for T6.

| | Candidate₀ | Candidate₁ |
|---|---|---|
| shape | inert guard (`and not line.startswith("    ")`) | branch reorder (2-space test first) |
| fingerprint | `9e6924f6…` | `368fc158…` |
| model confidence | 0.9 | 1.0 |
| verification | rejected — `primary_defect_not_closed` | rejected — `behavior_preservation_regressed` |

Candidate₁ came out of PATCH.AUTHOR.LIVE.1's single revision, parsed, earned its
own fingerprint and passed every gate before the matrix caught it. Containment
held: `approval_ready=false`, `human_review_eligible=false`,
`execution_authorized=false`. The answer did not:

| payload field | came from |
|---|---|
| `summary` | **Candidate₀** ("…Wait, the current order IS 4-space then 2-space…") |
| `issues` | **Candidate₀**'s own issue, beside the harness finding about **Candidate₁** |
| `patch_candidate` | Candidate₁ |
| `confidence` | Candidate₁ (1.0) |
| verification / rejection | Candidate₁ |

A reader was shown one patch explained by the author of another.

## 2. Root cause

The Round-10 tracer captured the block around every step of the revision.
Right after `_drop_candidate_bound_receipts` the payload still held
Candidate₀'s `summary` and its issue string — the drop removes harness receipts,
which is its job — and one step later it held Candidate₁'s patch and 1.0 with
Candidate₀'s `summary` untouched.

`_maybe_revise_rejected_candidate` installed Candidate₁ by writing exactly two
things: `patch_candidate`/`patch_plan` and, per §42, `confidence`.
`parse_revised_candidate` reads nothing else from the response, so
Candidate₁'s `summary` and `issues` were discarded at the parser and every other
field Candidate₀'s author had written simply stayed. The Round-10 revision
response *did* carry a summary ("…By checking for 2-space indentation first…")
and an issue; they never reached the payload.

It is an ownership bug at the one place a candidate is replaced, not a display
bug: `ground_state_answer` renders `final_answer` from the block, so the CLI,
the web result, the `structured_output` artifact, the assistant message and the
saved session all faithfully showed the same mixed block.

## 3. The invariant

> Every user-visible field that semantically describes a patch candidate is
> bound to exactly one candidate identity. Harness verification, escalation and
> authority are attached alongside it, and are the harness's.

## 4. Ownership of the authoring envelope

Both authoring calls are held to one envelope, `PATCH_RESPONSE_SCHEMA`
(PATCH.AUTHOR.LIVE.2). `core/candidate_presentation.py` classifies it once:

| field | owner | on the payload |
|---|---|---|
| `patch_candidate`, `patch_plan` | candidate bytes | installed by the lifecycle; gates may remove them |
| `summary`, `issues` | the author's narrative | follow the candidate they describe |
| `confidence` | the author's claim | the payload copy is the claim; existing gates may demote it, never replace it with another author's |
| `needs_escalation` | the author's claim | the payload copy is **harness-final**; the claim is recorded, never written back |

A test proves the table's keys equal the contract's fields, so a field added to
the contract fails there before it can escape classification. This is not a
key-name blacklist of harness fields: the harness key set is open-ended, and the
author's envelope is the closed set.

`issues` has two owners. The author's own entries follow its candidate; harness
findings (`candidate_verification`, `candidate_effect`, `policy`,
`control_grounding`, …) stay independent. Candidate₀'s entries are removed by
multiset equality against the record of what Candidate₀'s author actually
wrote — not by `type`, which a model can also write — so a finding that merely
resembles an authored line is not taken with it.

## 5. The composition boundary

```
finalize_answer(draft)            capture  Candidate₀'s account   (before any gate narrows it)
  … gates, CONTROL, lifecycle …
_maybe_revise_rejected_candidate
  history  ← Candidate₀'s account + its verification verdict   (before its receipts drop)
  drop Candidate₀'s receipts                                    (unchanged)
  capture  Candidate₁'s account from the revision response      (§42 confidence from the parser)
  install  bytes + summary + confidence + authored issues       (one unit)
  … Candidate₁'s gates and lifecycle …                          (unchanged)
_verify_authored_candidate_without_mutation
  bind     final identity ⇄ author record ⇄ payload             (lifecycle terminal)
ground_state_answer                                             (unchanged, runs after)
```

Three rules make the Round-10 mix impossible by construction:

1. **Capture where the response is parsed.** The record is taken in
   `finalize_answer` right after `extract_json_block`, before
   `reject_schema_drift`, the no-op gate or `safe_minimal` can touch the
   payload, so a demoted confidence or a harness-narrowed escalation is never
   mistaken for what the author said. The revision's record is taken from the
   same response the parser accepted, and takes its confidence from the parser
   so §42 has one reading, not two.
2. **Replace the whole account at once.** `install_candidate_presentation`
   writes the candidate bytes and the new author's summary, confidence and
   issues together, replacing values in place so the new account keeps the head
   of the payload. A field the new author did not supply is removed — never
   inherited, never composed.
3. **Bind once, at the end.** One function decides which candidate the final
   answer presents, and every surface consumes that one decision.

## 6. Final candidate selection

Read off existing lifecycle truth, never off "whichever dictionary has a patch":

* **Generation** — the revision receipt: `revision` exactly when
  `revised_candidate_present` is true, else `initial`.
* **Identity** — for a revision, the receipt's `revised_candidate_fingerprint`
  (recorded before Candidate₁'s gates run, so a candidate the no-op or
  `safe_minimal` gate then removes is still named). Otherwise the candidate
  receipts in order: `candidate_verification_candidate_fingerprint`, then the
  no-op and novelty receipts that survive a gate removing the candidate.
* **Cross-checks** — the payload bytes' existing exact fingerprint (when bytes
  remain) and every candidate-naming receipt present
  (`candidate_effect_…`, `candidate_novelty_…`, `candidate_validation_…`,
  `candidate_fingerprint`, `check_oracle_…`, `execution_eligibility_…`) must
  name the same candidate. The payload's bytes are checked, never trusted as
  the source.
* **No candidate** — if no receipt names a candidate and no bytes remain, the
  payload is not annotated at all.

No new fingerprint algorithm: the binding compares fingerprints the lifecycle
already recorded, and the pipeline passes in `candidate_fingerprint_from_payload`.

## 7. What the final payload carries

**Candidate presentation** (author-owned, bound to `final_candidate_fingerprint`):
`summary`, the author's `issues` entries, `confidence`, and — as recorded
claims — `candidate_presentation_model_confidence` and
`candidate_presentation_model_needs_escalation`.

**Harness truth** (unchanged, attached alongside): `candidate_verification_*`,
`needs_escalation`, `human_review_eligible`, `approval_ready`,
`execution_authorized`, `write_authority`, every other receipt and every
harness finding in `issues`.

**Binding telemetry** — one flat group, no nested receipt, no duplication:

| key | meaning |
|---|---|
| `final_candidate_fingerprint` | the candidate the answer presents (`""` when withheld) |
| `final_candidate_generation` | `initial` \| `revision` (`""` when withheld) |
| `candidate_presentation_coherent` | every author-facing field was bound to it |
| `candidate_presentation_authored_fields` | what that author actually supplied (`null` = no record) |
| `candidate_presentation_model_confidence` | the author's confidence claim, before any demotion |
| `candidate_presentation_model_needs_escalation` | the author's escalation claim |
| `candidate_presentation_incoherence_reasons` | closed vocabulary, empty when coherent |
| `candidate_presentation_phase_id`, `…_schema_version` | provenance of this group |

The group is candidate-bound, so it joins `_CANDIDATE_BOUND_RECEIPT_GROUPS` and
goes stale with the candidate it names.

## 8. Candidate₀ history

`candidate_revision_previous_candidate` keeps PATCH.AUTHOR.LIVE.1's five fields
and adds, from the record: `generation: "initial"`, `authored_fields`,
`summary`, `issues`, `model_confidence`, `model_needs_escalation`,
`verification_status` and `verification_rejection_reasons`. Serializing the
payload without that record finds neither Candidate₀'s summary nor its issue.
With no authoring record (a payload that did not come through
`finalize_answer`), `authored_fields` is `null` and no narrative is attributed.

## 9. Behavior by scenario

All replayed through `finalize_answer` and the real read-only lifecycle, with the
revision answered by a deterministic adapter and every provider refused.

| scenario | final generation | summary | confidence | issues | notes |
|---|---|---|---|---|---|
| Candidate₀ verified, no revision | initial | Candidate₀'s | Candidate₀'s | Candidate₀'s | user-visible fields unchanged; authority still false |
| Candidate₀ exact no-op | initial | Candidate₀'s | Candidate₀'s | effect finding + Candidate₀'s | patch removed; identity from the effect receipt |
| Candidate₀ `safe_minimal` (lstrip) | initial | Candidate₀'s | 0.2 (existing demotion) | policy finding + Candidate₀'s | `model_confidence` 0.95 kept beside it |
| **Round 10**: Candidate₁ rejected | revision | Candidate₁'s | 1.0 | [finding on Candidate₁, Candidate₁'s] | harness truth identical to production |
| Candidate₁ verified | revision | Candidate₁'s | Candidate₁'s | Candidate₁'s | coherent presentation authorizes nothing |
| revision output invalid | initial | Candidate₀'s | 0.9 | Candidate₀'s + its finding | no Candidate₁ fingerprint, bundle or confidence; no history record |
| Candidate₁ `safe_minimal` (lstrip) | revision | Candidate₁'s | 0.2 (existing demotion) | policy finding + Candidate₁'s | identity = novelty receipt = revised fingerprint |
| Candidate₁ exact no-op | revision | Candidate₁'s | Candidate₁'s | effect finding only | identity = no-op receipt = revised fingerprint |
| Candidate₁ omits summary/issues/confidence | revision | **absent** | **absent** (reader sees 0.0) | findings only | never Candidate₀'s |

## 10. Fail closed, never guess

If the identity is missing or malformed, the payload bytes or a receipt name
another candidate, a revision left no author record, the record is from another
generation, the summary is not the final author's, or a superseded author's
issue is back, the binding is **withheld**: `candidate_presentation_coherent`
is false, no identity or generation is claimed, the reasons are listed from a
closed vocabulary of seven, and the author-facing `summary`, `confidence` and
authored issue entries are removed. Candidate bytes, harness findings and every
receipt stay — they name their own candidates. The four §25 cross-bindings
(summary₀+patch₁, confidence₀+patch₁, issues₀+fingerprint₁, patch₁ with no
identity) are each either refused by the install or caught by the binding.

## 11. Exact Round-10 red / green

`tests/fixtures/answer_coherence_live1_round10.json` freezes the verbatim draft
and revision responses, CONTROL's source snippet, the behavior fact and probe
fingerprint `15335911…`, and what production displayed. One detail mattered:
CONTROL's snippet is 660 characters with no trailing newline, while
`inspect.getsource(_classify_indent)` has one — a replay built from the latter
gets a different Candidate₁ fingerprint. With the recorded snippet the replay
reproduces `9e6924f6…`, `368fc158…`, both verdicts, and the 6,347-character
revision request **byte for byte** (sha256 `8f2c4080…`).

The toggle disabled only this phase's composition — the shipped reversal hunks
applied to `core/pipeline.py` and `core/agent_state.py`, the new module left on
disk — and replayed in a fresh interpreter:

| | summary | patch | confidence | Candidate₀ issue | Candidate₁ issue | bound identity |
|---|---|---|---|---|---|---|
| **pre** (fix disabled) | Candidate₀ | Candidate₁ | 1.0 | present | absent | — |
| **post** | Candidate₁ | Candidate₁ | 1.0 | absent | present | `368fc158…` (revision) |

Verification `rejected / behavior_preservation_regressed`, `needs_escalation`
true, `human_review_eligible` false, `approval_ready` false, one revision
request and zero provider calls in both. Restoring left all eight shipped
artifacts byte-identical to the post-change state.

## 12. Display, persistence, history reload

The binding is fixed before ANSWER.GROUND runs, so every downstream copy is the
same coherent block: the grounded display copy (`final_answer` parses to it), the
CLI's `structured_output` artifact and assistant message, and a web session
saved through `web.app.save_session` and reloaded through `find_session` (the
`/session/<id>` path). No surface re-derives provenance on its own.

## 13. ANSWER.GROUND interaction

The binding keys and the history record are harness-owned: disjoint from
`_ANSWER_SURFACE_KEYS` (the ownership test now lists the new group), and
byte-identical through grounding. Candidate₁'s own summary and issues are on the
answer surface and are grounded as before — a fabricated path in a Candidate₁
summary is still downgraded. The history record is quoted rejected evidence
under a harness key, so ANSWER.GROUND.LIVE.4's ownership inheritance keeps it
verbatim, as it keeps the no-op debugging copy; see §17.

## 14. Confidence and escalation

Model confidence never becomes harness confidence, and nothing is clamped by
this phase. The payload's `confidence` is the final author's claim; the existing
`safe_minimal` demotion still applies to it, and the undemoted claim is recorded
beside it. A Candidate₁ that supplies none leaves the field absent.
`needs_escalation` on the payload stays harness-final; the author's claim is
recorded as `candidate_presentation_model_needs_escalation`.

## 15. Schema

Additive only. The new group carries its own
`candidate_presentation_schema_version` (`candidate_presentation_live_1_v1`).
The revision receipt stays `candidate_revision_live_1_v1` — its fields did not
change — and the history record only gained optional keys. No wire version was
bumped for the sake of a new phase.

## 16. Containment

* `core/pipeline.py`: 2 helpers added (`_recorded_candidate_presentation`,
  `_record_candidate_presentation`), 3 definitions changed (`finalize_answer`,
  `_maybe_revise_rejected_candidate`,
  `_verify_authored_candidate_without_mutation`), 1 key group added
  (`_CANDIDATE_PRESENTATION_KEYS`) and 1 extended
  (`_CANDIDATE_BOUND_RECEIPT_GROUPS`), nothing removed.
* `core/agent_state.py`: one run field, `candidate_presentation`, beside
  PATCH.AUTHOR.LIVE.1's `candidate_revision`.
* `tests/fixtures/answer_coherence_live1_reversal.json` stores the exact hunks
  (raw bytes — `core/agent_state.py` mixes CRLF and LF, so nothing is
  normalised). Its `core/pipeline.py` preimage is the 2026-09-10 remediation's
  post, and its `core/agent_state.py` preimage is DEFECT.PROBE.LIVE.5's pin.
  `tests/_harness_maintenance.py` now undoes receipts newer than the remediation
  first (`LATER_RECEIPTS`, newest first, both digests asserted), so every earlier
  phase's pin is evaluated against history and **none was re-pinned**.
* `tests/fixtures/answer_coherence_live1_frozen_boundaries.json` pins 30 files
  this phase must not move — revision generation and parsing, verification,
  the probes and matrix, `safe_minimal` and novelty, the no-op gate, targeted
  validation, authority, grounding and display, the authoring contract, routing
  (`live_task_routing`, `live_task_shape`), `core/code_dna.py` and the
  display/persistence runners — evaluated through `before_later_receipts`.

### 16b. Concurrent-remediation reconciliation

The broad affected run (124 test files) reproduced the 49-failure baseline
exactly and added one failure outside it:
`tests/test_paired_defect_probe.py::test_frozen_probe_execution_and_authority_surfaces_are_unchanged`.
It hashed `core/defect_probe.py`'s raw bytes against DEFECT.PROBE.LIVE.3's pin
(`4f5c8cb1…`, the remediation's preimage) while the shipped file is the
remediation's post (`813dda87…`). With this phase reverted it fails identically,
so it predates this phase: the remediation routed the LIVE.4, LIVE.5 and
LOCALIZE.LIVE.2 raw-byte tests through its helper and missed this one. It now
calls `before_harness_remediation` like its siblings — all 16 of its pins
reconstruct with zero mismatches, and none was re-pinned. Production behavior
was not reverted to satisfy any pin. The three `test_harness_blackbox_revision.py`
scenarios once recorded as baseline failures now pass; that is the
remediation's doing, not this phase's.

## 17. Known limitations

* **The mutation-enabled branch is not stamped.** Only the read-only branch
  can hold two candidates. With `AUTO_PATCH_ENABLED=true` one authoring
  generation reaches the payload; the self-correct loop's re-authored attempts
  run from a side holder and never enter it — a separate presentation question,
  untouched here.
* **`needs_escalation` seeding is unchanged.** PATCH.AUTHOR.LIVE.1 seeds a
  fresh Candidate₁'s flag false and lets the gates raise it, so a verified
  Candidate₁ whose author asked for escalation shows `needs_escalation: false`
  where Candidate₀'s claim would have survived. Folding the claim into the harness
  flag is lifecycle policy; this phase records the claim instead.
* **The history record is not grounded.** It is harness-owned quoted evidence,
  so a fabricated path in Candidate₀'s rejected summary is shown verbatim inside
  it rather than annotated.
* **A payload that bypassed `finalize_answer`** has no author record: a single
  generation still binds (there is no other author), but `authored_fields` and
  the model claims are `null`, and a revision over it attributes no Candidate₀
  narrative to the history.
* **Grounding still reads harness findings inside `issues`**, because `issues`
  is an answer-surface field that also carries harness entries. That is
  ANSWER.GROUND's existing behavior and unchanged here.

## 18. Readiness for DIAG.INDENT.SEMANTICS.1

Ready. The next phase can read the final answer and trust that its summary,
patch, confidence and verification describe one candidate, and can tell a
first-draft result from a revision by `final_candidate_generation`.
`_classify_indent`, the probes, the matrix and the oracle's physical-width
reading are untouched; structural indentation semantics were not started.
