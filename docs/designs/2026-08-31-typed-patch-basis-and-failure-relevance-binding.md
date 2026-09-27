# PATCH.BASIS.LIVE.1 — Typed Patch Basis & Failure-Relevance Binding

Status: complete  
Track: CONTROL (the registry has no PATCH track, and this phase changes the
existing CONTROL grounding/policy handoff rather than expanding taxonomy)  
Prerequisite: WAITER.LIVE.1  
Date: 2026-08-31

## Outcome

Production can now represent two legitimate reasons to consider a patch:

```text
none
grounded_defect
explicit_change_request
unresolved
```

The first two questions and the authority question remain structurally
separate:

```text
WHY may a change be considered?   patch_basis
WHERE may it operate?             exact acquired target source
MAY it write?                     existing safety, authorization and approval
```

`patch_basis` is categorical. It is not a confidence score and is never
derived from CONTROL rank or model confidence.

## Old failure

CONTROL.SAFETY.LIVE.1 correctly stopped graph/lexical rank from becoming patch
authority, but its live grounding binder required identity between the
validation failure file and the implementation candidate file. This rejected:

```text
main.py assertion -> calc.py::add
test_solution.py assertion -> solution.py::length_of_longest_substring
```

WAITER.LIVE.1 separately allowed an explicit-change plan through source
grounding, but the live policy/apply entry still asked whether the plan had a
grounded defect. A healthy baseline and a feature request therefore remained
impossible to represent together.

## Typed basis

`core.patch_basis` owns the small vocabulary and bounded reference binder.

- `grounded_defect` comes only from a genuine OPS.VALIDATE.1 executed-failure
  category, a deterministic binding, and exact acquired candidate source.
- `explicit_change_request` comes only from WAITER.LIVE.1's preserved
  `explicit_change` route and `change_need_source=explicit_user_request`.
- `unresolved` represents a defect claim without deterministic evidence.
- `none` covers analysis, clarification, an unrouted localization-only result,
  and every state with neither executed evidence nor an explicit change request.

An explicit change never sets `defect_established` or `defect_grounded`.
Passing and inconclusive baselines do not erase its typed basis. Conversely,
passing/inconclusive validation and user defect wording cannot create a defect
basis.

## Direct and failure-relevance binding

The existing direct candidate-file binding remains available as
`direct_location`. A second binding kind,
`direct_executed_reference`, handles a caller or test expression:

```text
executed failure
  -> exact failing file:line already named by validation
  -> read that one file
  -> inspect the Python AST statement at that line
  -> resolve its call against already-localized candidates
  -> acquire/verify exact candidate source
  -> failure-relevant candidate
```

The resolver understands ordinary Python imports, aliases and module-qualified
calls. It never selects among ambiguous candidates by score. Multiple plausible
candidate definitions produce `ambiguous`; a missing executable call produces
`unavailable`.

The binding means the executed failure directly exercised or referenced the
candidate. It does not claim that the candidate is the only mathematically
possible cause. Post-patch validation remains the test of the proposed fix.

## Boundedness

The binder reads only:

- locations already present in the validation receipt;
- Python traceback/pytest locations already present in the bounded validation
  output;
- the exact failing files named by those locations; and
- already-localized candidate files selected by deterministic reference
  resolution.

It performs no `glob`, `rglob`, filesystem walk, repository search, graph walk,
index operation, model call or network call. Graph edges, graph distance,
localization score, lexical overlap and execution-trace proximity are not
inputs to the binding function.

## Exact target grounding and scope

`acquired_source_files` now verifies that every recorded source quote remains a
literal substring of the named repository file. Merely naming a file through
Scout, CONTROL or a model plan is insufficient.

At the payload boundary:

- replacement targets must be a subset of exact acquired source files;
- a new path is accepted only when existing create-file semantics apply and
  the preserved route literally named the path;
- a defect payload must include its bound implementation candidate; and
- an explicit `across model/store/CLI` obligation must cover all three named
  surfaces and may not add an unrelated surface.

This is scope preservation over WAITER.LIVE.1's existing receipt. It does not
reclassify intent or redesign retrieval.

## Policy consumer audit

| Consumer | Category | Result |
|---|---|---|
| `defect_established` / `defect_grounded` | actual defect evidence | Kept defect-only |
| `patch_basis` | any legitimate basis | New categorical input |
| `change_need_source` | route/reason telemetry | Reused, not re-derived |
| payload grounding boundary | exact target source | Requires every concrete target |
| `eligible_for_patch_safety_handoff` | basis + targets | Set only on the concrete payload |
| `build_patch_policy.patch_basis_accepted` | any legitimate basis | Accepts defect or explicit change |
| `auto_apply_allowed` | automatic write policy | Still true only for a grounded defect satisfying existing style/confidence/validation rules |
| patch safety | write-path safety | Unchanged and still blocks test edits |
| `AUTO_PATCH_ENABLED` / runtime apply | write authorization | Unchanged |
| CTX.PATCH / CTX.APPLY | candidate/application safety | Unchanged |
| human approval | authority | Required and never minted by task intent |
| display/replay telemetry | display only | Additive typed facts |

Historical `defect_grounded` artifacts remain loadable. Projection to
`patch_basis=grounded_defect` occurs only when the artifact also retained exact
source grounding and an executed-validation-failure record. Historical
localization confidence is never reinterpreted.

## Policy and human handoff

`PatchPolicy` exposes `patch_basis`, `patch_basis_accepted`,
`human_approval_required` and the pre-existing `auto_apply_allowed` separately.

A grounded explicit-change payload is evaluated by the existing patch-safety
gate. When safe, it remains authored and reviewable, but `write_authority=false`,
`patch_application_authority=false`, `auto_apply_allowed=false`, and
`human_approval_required=true`. The web apply button / existing approval path
remains the authority boundary. The original feature request is task intent,
not an approval token for arbitrary expansion.

Grounded defect repairs retain the existing automatic path where its separate
policy conditions already permit it. A candidate no longer remains escalated
merely because its executed failing location is a caller or test file; other
independent escalation reasons are untouched.

## Telemetry

CONTROL and concrete patch payloads expose bounded fields:

```text
patch_basis
patch_basis_source
failure_binding_kind
failure_binding_location
candidate_binding
target_source_grounded
eligible_for_patch_safety_handoff
write_authority
patch_application_authority
human_approval_required
```

Binding kinds remain small:

```text
direct_location
direct_executed_reference
explicit_change_request
unavailable
ambiguous
```

No confidence or reasoning transcript was added.

## Product smoke outcomes

### A. calc indirect failure

- Route: `defect_repair`
- Basis: `grounded_defect`
- Binding: `direct_executed_reference` at `main.py:2`
- Candidate: `calc.py::add`
- Patch authored: yes
- Patch safety: passed
- Write authorized by the existing grounded-defect automatic policy: yes
- Validation: passed
- Delivered: yes

### B. flat pytest sliding-window

- Route: `defect_repair`
- Basis: `grounded_defect`
- Binding: `direct_executed_reference` in `test_solution.py`
- Candidate: `solution.py::length_of_longest_substring`
- Root-level pytest detection: used
- Patch authored: yes
- Patch safety: passed
- Write authorized by the existing grounded-defect automatic policy: yes
- Validation: passed
- Delivered: yes

### C. explicit feature

- Route: `explicit_change`
- Basis: `explicit_change_request`
- Defect established: no
- Targets: exact acquired `model.py`, `store.py`, `cli.py`
- Patch authored: yes
- Patch safety: passed
- Write authorized: no
- Human approval required: yes
- Validation/write result: not run at the non-writing handoff
- Delivered automatically: no; correctly pending the existing approval path

## Harmful test regression

A plan that changes a production implementation and rewrites its assertion is
still rejected by the existing test-path safety rule before any write. A
separately grounded request to repair a test remains a distinct future/approval
case; this phase creates no blanket test edit permission and no blanket
production-is-wrong assumption.

## Deltas and frozen systems

- Added model calls: zero.
- Added network calls: zero.
- Added repository/index traversal: zero.
- Retrieval ranking/indexing/embeddings: unchanged.
- Validation timeout classification: unchanged; remains OPS.VALIDATE.2.
- OPS.PATCH.1 byte semantics: unchanged and regressed.
- OPS.VALIDATE.1 outcome semantics/detection: unchanged and regressed.
- CONTROL.SAFETY.LIVE.1 rank/authority separation: preserved.
- WAITER.LIVE.1 routing: reused and regressed.
- Patch safety and harmful-test protection: preserved.
- CTX.PATCH / CTX.APPLY: unchanged.
- CHECK.LIVE lifecycle and WORKER.DECL compatibility: unchanged.
- Human approval: unchanged and required.

## Known limitations

The new syntactic reference resolver is intentionally limited to direct Python
failure expressions/imports, which covers the two field regressions. Other
languages retain direct-location grounding until an equally deterministic,
bounded resolver already available in their runtime can be reused. There is no
recursive caller chase, no inference through dynamic dispatch and no attempt to
prove sole causality.

Retrieval quality remains the next hard problem. In particular the 1,249-file
wrong-target stress case was not rerun and no ranking/index change was made.
Validation timeout classification also remains out of scope.

## Readiness

The runtime is ready for the next black-box rerun: it can represent both typed
patch bases, bind the calc and flat-pytest caller/test failures to their
implementation candidates, refuse ambiguity and navigation-only evidence,
preserve exact target/scope requirements, and stop explicit features at human
authority without weakening any write gate.

`PATCH` is an accepted phase-id namespace only; the registered track remains
`CONTROL` and no separate PATCH track exists.
