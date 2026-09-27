# CONTROL.FRESH.1 — Explicit No-Prior-Run Context Contract

Date: 2026-09-18
Residual: recorded by UX.CONTEXT.1 ("Without an eligible run, Generate shows the
backend's generic 'Invalid control JSON', exactly as on a New Session page")
Track: CONTROL (prerequisite UX.CONTEXT.1)

## Scope and invariant

The `control` field of a Generate request has three distinct meanings, and no
two of them may be confused:

- **A. prior CONTROL**: a CONTROL object from a run eligible for the current
  repository context. It is continuation input.
- **B. no prior CONTROL** (fresh run / fresh repository context): the explicit
  statement that no run is eligible. It is a legitimate first-class state.
- **C. malformed CONTROL**: anything else. It is rejected.

B must never be answered as C, and the parser must not accept anything it
rejected before except the one explicit fresh form.

**Decision recorded for this phase: a fresh request stops at the bootstrap
boundary.** Every stage behind the `control` field needs CONTROL (see the
audit below), and creating CONTROL for a fresh task needs source acquisition,
graph work and routing that this phase does not add. So state B becomes a typed
`fresh_bootstrap_required` state that answers `fresh_control_required` with no
harness decision, prompt, provider call, graph, retrieval, preflight, mutation
or session. **A fresh Generate is not executable yet: CONTROL.BOOTSTRAP.1 is
required before a fresh task can proceed into CONTROL-dependent analysis and
provider stages.**

Frozen: UX.CONTEXT.1 provenance, UX.STATE.1 (UX-02, UX-03, UX-04), Track A,
execution and human Apply authority, AUTH.DREAM.1, AUTH.WEB.1, AUTH.WEB.READ.1,
SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, DATA.ROLLBACK.1 and Local Critique. Out of
scope: CONTROL.BOOTSTRAP.1, UX-05, UX-06, UX.RESILIENCE.1, PREFLIGHT.REQUEST.1
and T6 Round 11.

## Measured entry state

Entry bytes are UX.CONTEXT.1's post-state. Every item below is an executable
PRE test: `tests/test_control_fresh1.py` runs the entry Generate routes compiled
from reconstructed `web/app.py` bytes, and `tests/test_control_fresh1_browser.py`
serves the reconstructed template in real Chromium against those routes.

- **New Session and every ineligible run.** Both handlers sent `control=""`.
  The backend's `json.loads("")` failed and it answered
  `{"error": "Invalid control JSON"}` before any harness decision or model call.
  Repository A → B, switch-back and mismatched history all reached this answer.
- **The entry parser also let non-CONTROL through.** `null` parsed to `None`;
  `[]`, `{}` and `{"hello": 1}` parsed as well. None of them was rejected. Each
  reached the harness gate, which refused with `source_missing` for lack of
  source text.
- **Omission was inconsistent.** `/generate_patch` read a missing field as `""`,
  giving Invalid control JSON. `/generate_candidates` raised a
  `BadRequestKeyError`, an unstructured HTML 400.
- **Non-standard JSON parsed.** `NaN` and `Infinity` were accepted by the
  Python parser.

## Audit: where CONTROL becomes necessary

| Stage (both routes) | Reads from CONTROL | With no CONTROL |
| --- | --- | --- |
| `_patch_generation_harness_block` → `decide_harness_mode` | target path, source text | `source_missing`: generation refused |
| `build_control_prompt` → `refresh_control_safety` | localization, patch intent, defect grounding, live route, snippets, style | no grounded prompt can be built (`None` raises) |
| providers (`run_gemini_request`, `run_deepseek_review`) | the prompt | nothing to ask |
| `enforce_control_grounding_on_payload` | grounded target, patch basis, acquired files | a non-dict CONTROL returns the payload **unchanged**, so absence must never reach it |

CONTROL is necessary from the first stage after the parse. The stages that
create initial CONTROL for a task (WAITER.LIVE.1 routing and the INPUT.1 Task
Contract, indexing, preflight, `run_control_structured`) belong to the run
pipeline, not to Generate. A Generate request does not even carry the user's
request text. The parse point is therefore the bootstrap boundary: the fresh
state is decided there and goes no further, and no `{}` or synthesized CONTROL
is fabricated to get past it.

## Wire representation

The canonical fresh form is **`control=null`**: the JSON literal `null` in the
existing `control` field, exactly those four characters.

- The field already carries JSON, and JSON `null` is the typed absence of a
  CONTROL object. No new field or schema is needed.
- The field stays present, so an omitted field (a client that forgot it)
  remains distinguishable and fails closed.
- `""` is no longer overloaded: it stays what it always parsed as, malformed.

Rejected alternatives: omitting `control` (implicit, and identical to a broken
client), keeping `""` (indistinguishable from malformed input), and a new typed
field (the request contract has none).

## Normalization owner

`web/control_context.py` is the only reader of the field. It is pure
standard-library code, with no files, repository, graph, retrieval, model,
network, session or clock. `control_context_from_form(form)` reads
`form.getlist("control")`, and `normalize_control_values(values)` returns a
frozen `ControlContext(state, control, code, reason, field)`:

| Submitted `control` | State | Answer |
| --- | --- | --- |
| a CONTROL object | `prior_control` | continues into the pipeline |
| `null` (exact) | `fresh_bootstrap_required` | `fresh_control_required` |
| field omitted | `rejected` | `invalid_control_request` / `missing` |
| field repeated | `rejected` | `invalid_control_request` / `repeated` |
| `null` spelled otherwise (` null`, `null\n`) | `rejected` | `invalid_control_request` / `non_canonical_null` |
| `""` | `rejected` | `invalid_control_json` / `empty` |
| whitespace only | `rejected` | `invalid_control_json` / `whitespace_only` |
| not JSON (`{`, `hello`, `NULL`, `NaN`, `Infinity`) | `rejected` | `invalid_control_json` / `malformed_json` |
| array, string, number, boolean | `rejected` | `invalid_control_json` / `wrong_top_level_type` |
| a recognized field with a shape CONTROL never produces | `rejected` | `invalid_control_json` / `invalid_field_type` (+ `field`) |
| an object with no non-null anchor | `rejected` | `invalid_control_json` / `missing_required_fields` |

Checks run in that order. The answers are new dicts each call:

```json
{"error": "Fresh start: this request carries no prior CONTROL context, and Generate cannot create CONTROL yet. Run CONTROL for this repository or select one of its runs, then Generate again.",
 "code": "fresh_control_required", "control_context": "fresh_bootstrap_required"}
{"error": "Invalid control JSON", "code": "invalid_control_json", "reason": "missing_required_fields"}
{"error": "Invalid control request", "code": "invalid_control_request", "reason": "missing"}
```

Malformed CONTROL keeps its exact `Invalid control JSON` text, so existing
clients keep their message, and gains a typed `code` and `reason`. Every answer
stays HTTP 200 JSON, as the entry routes answered.

### The CONTROL shape

A CONTROL context localizes something: at least one of `top_hypothesis`,
`hypotheses`, `patch_intent` or `related_snippets` must carry a non-null value.
Recognized fields must have the JSON shape CONTROL produces, with null meaning
absent:

- strings: `query`, `repo_path`, `patch_style`
- objects: `top_hypothesis`, `patch_intent`, `scout`, `patch_candidate_state`,
  `preflight_validation`, `live_route`, `phantom_limb`
- arrays of objects: `hypotheses`, `related_snippets`

Unrecognized fields pass through untouched. The shape was calibrated against
the canonical producer `build_control_result` and the partial CONTROL that
`tests/test_harness_modes_web.py` posts, which both stay continuation input. It
was also checked against every JSON-object context in the local session store:
all four CONTROL objects conform, and the only anchorless context recorded
there is `{}`, written by a harness-blocked full run.

## Backend pipeline entry

Each route calls the owner once, before anything else. When the owner returns
no CONTROL, the route returns the owner's answer. Prior CONTROL is handed to
the route's harness, prompt, provider, grounding and answer tail, which is
byte-identical to the entry. A/B runs with a deterministic provider adapter
return the same answer and pipeline stages for the entry and post routes, with
identical provider prompts. The only other `web/app.py` change is the owner
import. No other definition or statement changed.

## Frontend serialization

WorkbenchState stays authoritative and unchanged (`web/static/workbench_state.js`
is byte-identical to UX.CONTEXT.1). Both handlers serialize
`control: ticket.requestRun ? ticket.requestRun.context : JSON.stringify(null)`.
Freshness comes from the frozen ticket alone, never from `#context`. The
template differs from UX.CONTEXT.1 by those two expressions and one comment
line. The fresh answer reaches the page through the frozen `generateOutcome`
and candidate-list paths. Generate Patch shows the fresh message in Answer as a
failed `generate` action with no candidate. Generate Candidates records it as
the list message with no items.

## Behavior

| Scenario | Entry (UX.CONTEXT.1) | Post (CONTROL.FRESH.1) |
| --- | --- | --- |
| New Session → Generate Patch / Candidates | `control=""` → `Invalid control JSON` | `control=null` → `fresh_control_required`, no stage reached |
| Repository A run → B → Generate | `control=""` → `Invalid control JSON` | `control=null` → `fresh_control_required`; run A displayed, never sent |
| Same-repository continuation | run A's CONTROL → pipeline | byte-identical bodies; identical pipeline answer, stages and prompts |
| Mismatched history (restored B over run A) | `control=""` → `Invalid control JSON` | `control=null` → `fresh_control_required` |
| A → B → A without reselect | `control=""` → `Invalid control JSON` | `control=null` → `fresh_control_required`; reselecting the run restores continuation |
| Java two-file request in fresh repository B | `control=""` → `Invalid control JSON` | `control=null` → `fresh_control_required`; files untouched, no analysis |
| `null` sent directly | parsed to `None` → harness `source_missing` | `fresh_control_required`, no stage reached |
| `[]`, `{}`, a non-CONTROL object | harness `source_missing` | `wrong_top_level_type` / `missing_required_fields`, no stage reached |
| omitted field on Generate Candidates | unstructured HTML 400 | `invalid_control_request` / `missing` |

No fake run: a fresh request creates no session, session id, run id, CONTROL
receipt, candidate or execution result. The New Session browser test proves
that no session store is written. Fresh context grants nothing. Execution
authority, human Apply, Dream review binding, patch eligibility,
auth/Origin/CSRF/Host, rollback and Undo are untouched.

## Unchanged semantics

| Area | Delta |
| --- | --- |
| UX.CONTEXT.1 run/repository provenance, `requestRun` derivation, ticket capture | 0 (`workbench_state.js` byte-identical) |
| UX-02 stale responses, UX-03 actions and Undo, UX-04 modes | 0 |
| Task Contract / user intent | 0: Generate never transported request text, and nothing is created or discarded |
| Repository context | 0: the request still carries `repo_path` from the ticket |
| Local Critique | 0: it sends `context` as prompt text and never parses CONTROL |
| Track A (PATCH.AUTHOR, PATCH.MINIMAL, DEFECT.PROBE, CANDIDATE.VERIFY, ANSWER.COHERENCE) | 0 |
| Execution authority, human Apply, AUTH.DREAM.1, patch eligibility, rollback, Undo | 0 |
| AUTH.WEB.1, AUTH.WEB.READ.1, SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, DATA.ROLLBACK.1 | 0 |
| Model and network calls | 0 added |

`tests/fixtures/control_fresh1_frozen_boundaries.json` pins the unchanged files.
`tests/fixtures/control_fresh1_reversal.json` reconstructs every changed file's
UX.CONTEXT.1-era bytes, and `before_ux_context1` undoes this phase first, so
every older pin keeps checking history.

## Tests

- `tests/test_control_fresh1.py`: the owner (canonical fresh form, prior CONTROL
  including the canonical producer, the full omitted/null/empty/whitespace/valid
  matrix, malformed JSON, wrong types, missing required fields, invalid shapes,
  determinism, purity). It also covers both production routes through the Flask
  test client with analysis entry points that raise if reached, recorded
  pipeline stages, a deterministic provider adapter and file-tree snapshots:
  continuation A/B against the entry routes, PRE on the entry routes, and the
  Java regression. The rest is containment, performance, registry, reversal,
  frozen boundaries and the completion receipt.
- `tests/test_control_fresh1_browser.py`: real Chromium with the production app
  and handlers. It covers New Session, repository A → B, same-repository
  continuation into the real pipeline, byte-identical continuation bodies,
  mismatched history, switch-back, and the Java two-file request, plus PRE on
  the UX.CONTEXT.1 post-state page and routes.
- UX.CONTEXT.1's browser tests keep their invariant (repository B never carries
  run A's CONTROL) with the fresh form re-homed to `null` and its typed answer.
  UX.CONTEXT.1's empty form and `Invalid control JSON` answer stay pinned as PRE
  here.

Test counts, timings, the red-green toggle and performance numbers are recorded
in `tests/fixtures/control_fresh1_completion.json`.

## Limitations

- **A fresh Generate is not executable.** It reaches the bootstrap boundary and
  stops. CONTROL.BOOTSTRAP.1 must add the step that creates CONTROL for a fresh
  task in the current repository. That step also needs the user's request text,
  which a Generate request does not carry today.
- A run whose recorded context is not a CONTROL object still cannot be
  continued, as before. Retrieve text, the empty context of full and deep runs,
  and a harness-blocked `{}` all answer `invalid_control_json` with a reason.
  For `{}` the answer was the harness's `source_missing`; neither calls a model.
- A run whose recorded context is exactly the text `null` would be read as the
  fresh form. No producer records that context.
- UX-05, UX-06, UX.RESILIENCE.1, PREFLIGHT.REQUEST.1 and T6 Round 11 remain open.

## Explicit answers

| Question | Answer |
| --- | --- |
| Is "no prior CONTROL" distinct from "malformed CONTROL"? | Yes: `null` is the typed `fresh_bootstrap_required` state (`fresh_control_required`); malformed input is `invalid_control_json` or `invalid_control_request`. |
| Can a New Session Generate proceed without historical CONTROL? | It is accepted as a legitimate fresh state and reaches the bootstrap boundary without historical CONTROL, but it cannot run yet: CONTROL.BOOTSTRAP.1 is required. |
| Can repo B start fresh after leaving repo A? | Yes, as the explicit fresh form, stopping at the same boundary. |
| Can repo A CONTROL leak into repo B? | No. |
| Does same-repo continuation still preserve CONTROL? | Yes, byte-identical request bodies and an identical pipeline tail. |
| Are malformed CONTROL payloads still rejected? | Yes, with a typed code and reason. The entry parser's gaps (`null`, `[]`, `{}`, non-CONTROL objects, `NaN`) are now rejected too. |
| Does fresh context invent a fake prior run? | No. |
| Were Track-A semantics changed? | No. |
| Were authority semantics changed? | No. |
| Were live provider calls added? | No. |
