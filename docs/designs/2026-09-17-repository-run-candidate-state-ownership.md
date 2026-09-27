# UX.STATE.1 — Repository / Run / Candidate State Ownership & Truthful Actions

Date: 2026-09-17
Findings: UX-02, UX-03, UX-04 of the 2026-09-11 security and UI/UX review
Track: UX (prerequisite AUTH.WEB.READ.1)

## Scope and invariant

User-visible workflow state must be attributable to the exact context that
produced it: repository context, then request, then candidate, then action
outcome. A response may change the page only while it still belongs to the
current context.

This phase adds one bounded frontend owner, `web/static/workbench_state.js`
(`window.WorkbenchState`), and rewires the handlers in
`web/templates/index.html` that read or change repository, candidate, action
or mode state. Frozen: Track A, SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1,
AUTH.DREAM.1, DATA.ROLLBACK.1, AUTH.WEB.1, AUTH.WEB.READ.1, human Apply
authorization (EXEC.APPROVAL.LIVE.1), candidate fingerprints and every backend
route. Out of scope: UX-05 (Mermaid/CDN), UX-06 (keyboard/focus), visual
redesign, durable jobs, read authentication, PREFLIGHT.REQUEST.1, T6 Round 11.

## Measured entry state

Entry bytes are AUTH.WEB.READ.1's post-state (`index.html` sha256
`b8b3e9fc…`). Every measurement below is an executable PRE test in
`tests/test_ux_state1_browser.py`: it rebuilds the exact entry template from
this phase's reversal receipt and serves it through the same production app in
real Chromium.

- **UX-02, two repositories.** Generate in A, switch the input to B, Generate
  in B; B returns first and A last. The page showed A's candidate and usage in
  repository B, and Test Run Patch then sent A's patch with `repo_path=B`.
- **UX-02, one repository.** Two Generate requests; the newer returns first.
  The older response replaced the newer candidate ("last response wins").
- **UX-03.** The audit's exact `{"success": false, "message": "Backup not
  found"}` recorded `Last action: undone`. So did a real DATA.UNDO.1
  `stale_target` refusal from `/undo_patch`, with the file untouched.
- **UX-04.** Full + Ask before apply, then Chat, then Instant Run restored as
  Retrieve + Plan only while the button still said Run.
- **Additional entry finding (same root cause).** Test, Apply, Undo and Local
  Critique read the candidate from `#patchRawJson.innerText`. Chromium returns
  an empty string for it while the Patch tab is visible and the "Raw JSON"
  disclosure is collapsed, which is the state right after Generate. Test Run
  Patch then alerted "Patch tab does not contain valid JSON." and sent nothing.
  A hidden DOM value was acting as the candidate.

## Old ownership

No owner existed. Each handler independently read the repository input,
`#patchRawJson` text, `#applyPolicy` and `#modeSelect`, and wrote
`#patchRawJson`, the card state (`_setPatchState`), `window.patchCandidates`,
`#diff`, `#validation`, `#answer` and `#usage` when its own response
arrived. `setProductMode("chat")` and the submit listener wrote Retrieve and
Plan only into the Instant dropdowns. Undo wrote `last_action: "undone"`
unconditionally. The run-progress panel already had its own association
tokens; it is unrelated and unchanged.

## The state owner

`workbench_state.js` is a classic script loaded after `safe_content.js` and
before the page script. It holds navigation and presentation truth only. It
performs no fetch, storage, DOM access, fingerprinting or authority decision
(a static test enforces this). The page subscribes one renderer,
`renderWorkbench`, which is the only projection of owned state. Transitions
notify synchronously; a renderer error is rethrown asynchronously and never
undoes a transition.

### Data model

| Field | Meaning |
| --- | --- |
| `hydrated` | seeded once from the server-rendered page |
| `contextGeneration` | repository context generation (monotonic) |
| `repository` | trimmed repository input value of the current context |
| `run` | `{sessionId, repository}` of the displayed run (server-rendered) |
| `mode` | workspace mode, `chat` or `instant` |
| `instant` | Instant Run's remembered `{mode, apply_policy}` |
| `execution` | the active mode's effective `{web_mode, mode, apply_policy}` |
| `candidate` | `{id, source, requestId, contextGeneration, repository, runSessionId, backendCandidateFingerprint, text, payload}` or null |
| `candidates` | the listed candidates `{id, contextGeneration, repository, items, message}` or null |
| `review` | the displayed candidate's review outputs `{id, candidateId, kind, requestId, status, output}` or null |
| `action` | `{kind, status, code, message, requestId}` |
| `slots` | per result slot `{owner, kind, status}` |

Bounded debug telemetry (`WorkbenchState.telemetry()`): `requestSequence`,
`contextGeneration`, `lastInvalidation`, `ignoredStaleResponses` and
`lastIgnored = {requestId, kind, reason}`. No payload or secret is kept.

### Repository context generation

`setRepository(value)` compares the trimmed value with the current context.
On a change it increments `contextGeneration` and drops the candidate, the
candidate list, the review outputs, every slot's ownership and the action
state. Mode and Instant configuration are repository-independent and survive.
The repository input's `input` and `change` events, every dispatching handler
(before it reads the candidate) and an accepted folder upload call it. The
generation is captured when a request starts, so a late response is classified
by generation, never by comparing path strings after it arrives.

### Request identity

`begin(kind)` returns a frozen ticket `{id, kind, slot, contextGeneration,
repository, candidateId, execution}`. `id` comes from a monotonic counter. The
request body names `ticket.repository`, so the request and its ticket always
describe the same context. No server authority reads the ticket.

### Result-slot ownership

| Kind | Handler | Slot | Concurrency | Needs a candidate |
| --- | --- | --- | --- | --- |
| `generate` | `generatePatch` | candidate | latest dispatched request wins | no |
| `candidates` | `generateCandidates` | candidates | latest wins | no |
| `test` | `testPatch` | review | single-flight | yes |
| `apply` | `applyPatch` | review | single-flight (mutation) | yes |
| `undo` | `undoPatch` | review | single-flight (mutation) | yes |
| `critique` | `localCritique` | critique | latest wins | yes |
| `upload` | `uploadFolderFiles` | repository | latest wins | no |

The main run result is a native form POST that reloads the page, so no
in-page response competes for it; Dream, benchmarks and other auxiliary panels
keep their own flows. Only requests of the same slot supersede each other. A
new candidate (Generate accepted, or a listed candidate selected) resets the
review and critique slots, so earlier candidate-bound requests lose ownership.
A second Test, Apply or Undo while one is pending is refused locally ("Another
action is already pending…"), which also prevents duplicate mutation requests.
Generate and list selection are refused while an Apply or Undo is pending, so
the user cannot hide a mutation's outcome by replacing its candidate in the
same context.

### Stale-response policy

`settle(ticket, outcome)` accepts only when all hold: the ticket's
`contextGeneration` is current (else `context_changed`), a candidate-bound
ticket's candidate is still displayed (else `candidate_changed`), the ticket
still owns its slot (else `superseded`) and the slot is pending (else
`already_settled`). A stale response changes nothing but the telemetry
counter; handlers render auxiliary outputs (`#usage`, the generate error in
`#answer`, the critique content, alerts, tab switches) only after acceptance.
Failures follow the same rule: an accepted failure clears its own pending
state; a stale failure cannot clear a newer request's pending state or
overwrite a newer result. There is no "last response wins".

### Candidate ownership and provenance

The candidate text is owned by the state, not read back from the DOM. Its
provenance is the repository context, the request (or `server` for a
hydrated session payload, or the listed-candidates request), the displayed
run's session id and, when the payload carries one,
`human_apply_review.candidate_fingerprint` exactly as the server issued it.
Nothing is recomputed in JavaScript. An accepted Apply response refreshes the
payload of the same candidate (for example its `undo_backup` receipt) without
changing its identity. Apply still sends the payload, the policy and the
issued fingerprints; the server alone authorizes.

### Action state

The closed vocabulary is `idle`, `pending`, `succeeded` and `failed`; stale
responses are ignored rather than stored. Success is never set by a click: a
request enters `pending`, and only an accepted structured outcome moves it on.
`describeAction` maps the state to the existing card labels (`generated`,
`tested`, `applied`, `undone`, `candidate selected`, `… failed`,
`apply blocked (plan-only policy)`, `… error`) plus `… pending`.

### Undo

`undoOutcome(response, sentReceipt)` returns `succeeded` only when
`success === true`, `backup_id` equals the sent receipt's, `transaction_id` is
present (and equals the sent one whenever the receipt carried one), and
`restored_sha256` is 64 lowercase hex.
`success: false` keeps the backend `code` (`undo_failed` when absent). A
`success: true` without the complete receipt is `undo_receipt_incomplete`. A
confirmed Undo records success, replaces the applied diff with the Undo
message and keeps the candidate displayed. A failed Undo keeps the previous
review outputs, because the applied change is still in the repository. The
DATA.UNDO.1 vocabulary and transport are unchanged.

### Mode model

Two concepts are separate. The workspace mode (`chat` or `instant`) is
selected by the sidebar and the Ask / Preview Run buttons, which call
`setProductMode` and thus `WorkbenchState.setMode`. Execution configuration is
kept per mode. Instant remembers the user's last explicit `mode` (Retrieve,
Deep Understand, Control, Full Agent) and `apply_policy` (Ask before apply,
Auto apply, Plan only), updated by the dropdowns' `change` events. Chat's
execution is the product contract: the server runs `web_mode=chat` as
`retrieve` whatever mode is submitted, and Chat never applies (Plan only; its
Patch panel is hidden). `setExecutionOption` refuses edits while Chat is
active and re-renders the owned values. Entering Chat therefore displays and
submits Retrieve + Plan only, and returning to Instant Run restores exactly
what the user chose. Agent mode, patch style, repository DNA and runtime
environment were never rewritten by a mode switch and stay shared form fields.

### Primary action and Mode Preview

The primary button keeps the product vocabulary, Ask in Chat and Run in
Instant Run, and the adjacent hint now states what the action does from the
owned execution: "Run executes Full Agent; Apply policy: Ask before apply.
Apply Patch stays a separate human action." or "Ask answers with Retrieve;
Apply policy: Plan only. Chat never applies." `_renderWorkbenchMode` derives
the title, subtitle, current-mode label, switcher `aria-pressed`, panels, the
Mode Preview chips, the button label, the hint, the New Session link and the
form fields from one snapshot. No displayed label is read back into state.

### Serialization and hydration

The submit listener calls `_serializeWorkbenchExecution`, which writes
`WorkbenchState.execution()` into `web_mode`, `mode` and `apply_policy`
immediately before the native POST. Hydration runs once, near the end of the
page script, from server-rendered values: the repository input, the workspace
mode (server mode for a session, otherwise the existing `activeProductMode`
preference), the Instant dropdown values, the `#patchRawJson` text and the
session id and repository. A second `hydrate` throws.

### Historical and session navigation

Session links, New Session and reload are full navigations, so a new page
hydrates from the server. A live candidate generated on one page never
survives into a historical session or a new session (browser-tested). No
historical-session behavior was redesigned.

### AbortController

Not used. Every flow here is a synchronous Flask request; aborting the browser
fetch would not stop a model call or a mutation and would only hide an
outcome. Correctness comes from ownership: a response that cannot be cancelled
is still ignored when stale.

### Reload

No new browser persistence. After reload, execution configuration and the
candidate come from the server again; the existing `activeProductMode`
preference is unchanged. Candidate authority is never reconstructed from
browser-only state.

### Transport separation and future read authentication

`request_integrity.js` is byte-identical and remains the only transport owner
(CSRF, Origin, sign-in). WorkbenchState has no transport code, and the
transport has no workflow vocabulary (both statically tested).
`WorkbenchState.invalidate(reason)` is a generic, dormant context-invalidation
hook: a future sign-in or session change could invalidate anonymous data and
re-fetch authenticated reads through it. No read-authentication policy was
added.

## Frozen authority

| Contract | Delta |
| --- | --- |
| Backend routes, `web/app.py`, execution decisions | 0 (byte-identical) |
| Human Apply authorization, candidate fingerprint/freshness, write authority | 0 |
| AUTH.WEB.1 transport (`request_integrity.js`, gate, origin, session) | 0 |
| AUTH.WEB.READ.1 Host boundary and route classification | 0 |
| SEC.UI.1 sanitizer, policy and bounded sinks | 0 (no new HTML sink; Local Critique rendering unchanged) |
| DATA.UNDO.1 owner, vocabulary and transport | 0 production; two test pins that recorded UX-03 as deferred were re-homed |
| AUTH.DREAM.1 review binding | 0 (the five Dream review functions are byte-identical to entry) |
| EXEC.PLAN.1, DATA.ROLLBACK.1, Track A | 0 |

`tests/fixtures/ux_state1_frozen_boundaries.json` pins 582 unchanged files.

## Template containment

The `<head>` gains one local script tag, and markup outside the page script is
byte-identical (tested). Inside the page script, the changed definitions are
`setProductMode`, the submit listener, `applyPatch`, `generatePatch`,
`undoPatch`, `generateCandidates`, `testPatch`, `selectCandidate`,
`localCritique`, `uploadFolderFiles` and the initial hydration.
`_initPatchCardFromRaw` was replaced by hydration. The added renderers are
`renderWorkbench`, `_renderWorkbenchMode`, `_renderWorkbenchRepository`,
`_renderWorkbenchCandidate`, `_renderWorkbenchCandidates`,
`_renderWorkbenchCritique`, `_optionLabel`, `_bindWorkbenchInputs` and
`_serializeWorkbenchExecution`. The candidate-list markup construction moved
unchanged from `generateCandidates` into its renderer.

## Tests

- `tests/test_ux_state1_browser.py`: real Chromium against the production
  app on a loopback listener. Race responses are held and fulfilled in order;
  the Undo matrix uses real DATA.UNDO.1 artifacts and the real route; mode
  tests submit the real form and read what the server received. The PRE tests
  run the same scenarios on the reconstructed entry template.
- `tests/test_ux_state1.py`: state-module contract, transport separation,
  bounded ownership regression (the repaired handlers write no owned state
  directly), single projection, Dream binding identity, no new HTML sink,
  template containment, registry, reversal, frozen boundaries and completion
  receipt.

Test counts, timings and the performance numbers are recorded in
`tests/fixtures/ux_state1_completion.json`.

## Limitations and remaining UX work

- Editing the repository input invalidates the displayed candidate on the
  first changed character, and typing the old path back does not restore it.
  Reload the session to see it again.
- A mutation response that becomes stale (the user switched repositories while
  Apply or Undo was pending) is recorded only in debug telemetry and in the
  server's persisted session and backup state; the page shows the new context.
- Generate still combines the displayed run's CONTROL context with the current
  repository input; this phase binds responses to their context but did not
  change which CONTROL is sent.
- Repository-scoped auxiliary panels outside the candidate workflow (Dream
  runs sidebar, benchmarks, evidence pack) keep their own request handling.
- UX-05 (a missing Mermaid CDN still stops the page script before hydration)
  and UX-06 (keyboard/focus) remain open, as do the audit's layout and copy
  recommendations.

## Explicit answers

| Question | Answer |
| --- | --- |
| Can an old repo-A response overwrite repo-B state? | No. It is `context_changed` and ignored. |
| Can an older same-repo request overwrite a newer one? | No. It is `superseded`, regardless of arrival order. |
| Can `success:false` ever set `last_action=undone`? | No. Only a confirmed DATA.UNDO.1 receipt succeeds. |
| Does a successful Undo still produce a true success state? | Yes, `undone` with the backend message, from the real route. |
| Does switching Chat/Instant destroy prior Instant configuration? | No. |
| Does the primary button reflect the actual action semantics? | Yes: Ask/Run plus the owned execution and apply policy beside it. |
| Is Mode Preview derived from the same state owner? | Yes. |
| Is `request_integrity.js` still transport-only? | Yes, byte-identical. |
| Were backend authority semantics changed? | No. |
| Was AUTH.WEB.READ.1 changed? | No; only its test pins now route through this phase's reversal. |
| Was SEC.UI.1 changed? | No. |
| Was Track A changed? | No. |
| Were live provider calls added? | No. |
