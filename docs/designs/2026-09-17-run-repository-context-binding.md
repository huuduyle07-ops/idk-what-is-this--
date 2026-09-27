# UX.CONTEXT.1 — Run / Repository Context Binding

Date: 2026-09-17
Residual: recorded by UX.STATE.1 ("Generate still combines the displayed run's
CONTROL context with the current repository input")
Track: UX (prerequisite UX.STATE.1)

## Scope and invariant

Every context-bearing field in one Generate request belongs to one coherent
repository/run context: the current repository context plus only the run
context that is explicitly eligible for that same context. A run may stay
visible for reference; being displayed never makes its context eligible.

This phase extends the existing owner, `web/static/workbench_state.js`
(`window.WorkbenchState`), and changes two handlers and the hydration call in
`web/templates/index.html`. Frozen: backend authority and routes, Track A,
SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, AUTH.DREAM.1, DATA.ROLLBACK.1, AUTH.WEB.1,
AUTH.WEB.READ.1 and UX.STATE.1's stale-response (UX-02), action/Undo (UX-03)
and mode (UX-04) semantics. Out of scope: UX-05, UX-06, visual redesign, read
authentication, PREFLIGHT.REQUEST.1 (the Java preflight finding), T6 Round 11
and UX.RESILIENCE.1.

## Measured entry state

Entry bytes are UX.STATE.1's post-state (`index.html` `ba8ad87f…`,
`workbench_state.js` `36916265…`). Every item below is an executable PRE test
in `tests/test_ux_context1_browser.py` that serves the reconstructed entry
template and state module through the production app in real Chromium.

- **Repository A → B.** A run produced (or opened) in repository A renders its
  CONTROL context. After the repository input changes to B, Generate Patch and
  Generate Candidates both sent `repo_path=B` with run A's full CONTROL JSON.
- **Switching back.** A → B → A sent run A's CONTROL again; nothing ever bound
  it, so path text alone decided.
- **Browser-restored history.** Open historical run A, type repository B,
  navigate away, press Back: Chromium re-renders run A and then restores the
  typed B into the input after hydration. Generate sent B with run A's CONTROL.
- **Java two-file dogfood request.** Repository B holds a two-file Java
  project (`Greeter.java`, `Main.java`) and the query asks for a change across
  both; both Generate requests still carried run A's Python CONTROL (`a.py`).
- **Layout-dependent bytes.** The page formats every JSON `<pre>` at load with
  `p.innerText = JSON.stringify(obj, null, 2)`, which stores newlines as
  `<br>`. The entry read `#context.innerText` at click time, so the CONTROL
  text carried newlines only while the Context tab was visible (JSON-identical
  either way).

## Inventory of Generate request fields

| Request | Field | Source (entry → post) | Class |
| --- | --- | --- | --- |
| `/generate_patch` | `repo_path` | `ticket.repository` (unchanged) | repository-bound (defines the context) |
| `/generate_patch` | `control` | `#context.innerText` → `ticket.requestRun.context` or `""` | run-bound |
| `/generate_patch` | `runtime_environment` | form select (unchanged) | repository-independent config |
| `/generate_patch` | `anti_lesson_control_requested` | per-run checkbox (unchanged) | repository-independent user intent |
| `/generate_candidates` | `control` | `#context.innerText` → `ticket.requestRun.context` or `""` | run-bound |
| `/generate_candidates` | `repo_path` | `ticket.repository` (unchanged) | repository-bound |
| `/generate_candidates` | `runtime_environment` | form select (unchanged) | repository-independent config |

Transport fields (Origin, CSRF, sign-in) stay owned by `request_integrity.js`.
The backend also reads `runtime_environment_custom_name` and
`runtime_environment_notes`, which neither handler sends (unchanged).

Related run-bound fields outside Generate, unchanged:

- Local Critique sends `context` (`#context.innerText.trim()`) with the
  candidate and the query but no repository. It needs a candidate, and a
  candidate exists in a context only alongside the run that produced it or
  was hydrated with it, so the pair stays coherent by construction.
- Apply sends the server-rendered `session_id`. The backend already refuses to
  persist an Apply outcome onto a session whose recorded repository differs
  (`update_session_apply_outcome`), which remains the defense in depth.

## Old flow

Hydration recorded the displayed run as `{sessionId, repository}` and did
nothing else with it. `generatePatch` and `generateCandidates` read
`#context.innerText` directly and paired it with `ticket.repository`. The
repository context generation governed responses (UX.STATE.1), but not which
CONTROL a request carried.

## State owner change

No new owner and no new global. WorkbenchState keeps the displayed run and
derives eligibility from it; nothing copies CONTROL anywhere else.

### Run provenance

| Field | Meaning |
| --- | --- |
| `sessionId` | the server's existing session id for the displayed run (`""` when none) |
| `repository` | the repository the server recorded for the run (trimmed) |
| `source` | `server` for a run rendered for this page load, otherwise `none` |
| `contextGeneration` | the repository context generation the run belongs to, or `null` |
| `context` | the run's context as displayed, owned from hydration on |

Repository provenance is the existing pair: the trimmed repository value of
the current context and its monotonic `contextGeneration` (UX.STATE.1).

### Displayed run and eligible run

`snapshot().run` is the displayed run, kept after any repository change so the
page can still show it. `snapshot().requestRun` is derived on every snapshot:
the run itself while `run.source === "server"` and `run.contextGeneration`
equals the current generation, otherwise `null`. It is never stored, so it
cannot go stale.

### Binding

Hydration (`serverRun`) is the only place a run is bound: it takes the
generation current at hydration when the server-recorded repository equals the
hydrated repository, and `null` otherwise. Nothing compares repository text
after that. Any generation change (repository input, an upload into another
repository, the generic `invalidate` hook) ends eligibility for good on the
page, because generations never repeat.

### Policies

- **Repository change.** UX.STATE.1's candidate, list, review, critique and
  action invalidation is unchanged; additionally the displayed run becomes
  ineligible. The page keeps showing it.
- **Switch back.** Typing the old path back starts a new generation, so the
  old run stays ineligible. Continuing from it takes an explicit selection
  again (safety-preferred default).
- **Explicit history.** Selecting a run from the session list, or reloading
  its page, is a navigation that hydrates that run; it is eligible only when
  its recorded repository matches the hydrated repository.
- **Mismatched history.** A run rendered while the current repository is
  another one (browser form restoration, or hydration into a different
  repository) is viewable and never transported.
- **Same repository.** Input edits that trim to the same repository are not a
  repository change; continuation keeps working.

### Generate serialization and the ticket

`begin(kind)` adds one field to the frozen ticket: `requestRun`, captured at
dispatch for the kinds that transport run context (`KINDS.generate` and
`KINDS.candidates` carry `requestRun: true`), and `null` for every other kind.
Run records are frozen and replaced, never mutated, so later UI changes cannot
alter an in-flight ticket. Both handlers serialize
`control: ticket.requestRun ? ticket.requestRun.context : ""`. Key order and all
other fields are unchanged. The empty form is the fresh no-prior-context form a
New Session page already sends; the unchanged backend answers it with
`{"error": "Invalid control JSON"}` before any harness decision or model call.

### Hydrated context value

Hydration reads `#context.textContent` once, after the page's JSON formatting
pass. That is byte-identical to what the entry sent in the default layout
(Context tab hidden) and JSON-identical to what it sent while the Context tab
was visible; the transported bytes no longer depend on layout. The server's raw
text was deliberately not used, because the entry's JavaScript round trip
defines the existing bytes (for example numeric formatting).

## Unchanged semantics

| Area | Delta |
| --- | --- |
| Candidate state and provenance (UX-02 ownership) | 0: `candidateRecord`, `replaceCandidate`, `refreshCandidate`, invalidation byte-identical |
| Stale-response acceptance (UX-02) | 0: `staleReason`, `settle` byte-identical; late responses are still `context_changed`, `candidate_changed`, `superseded`, `already_settled` |
| Action and Undo (UX-03) | 0: `refuse`, `undoOutcome`, `describeAction`, `reviewOutcome` byte-identical |
| Mode (UX-04) | 0: `setMode`, `setExecutionOption`, `execution` byte-identical |
| Dream review binding (AUTH.DREAM.1) | 0: the five Dream review functions byte-identical |
| Local Critique, Test, Apply, Undo, upload, session list | 0: handlers byte-identical |
| ANALYSIS.MULTIROOT.LIVE.1 | 0: read-only analysis in the run form; never a license to blend CONTROL across repositories |
| Backend routes, `web/app.py`, authority | 0 (byte-identical) |
| `request_integrity.js`, AUTH.WEB.1, AUTH.WEB.READ.1, SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, DATA.ROLLBACK.1, Track A | 0 |

`tests/fixtures/ux_context1_frozen_boundaries.json` pins 587 unchanged files.
Static tests prove the template changed only inside `generatePatch`,
`generateCandidates` and the hydration call, and the module only by run
provenance: `requestRun: true` on the `generate` and `candidates` kinds, the
`NO_RUN` constant, the new `serverRun` and `requestRun`, one field each in
`snapshot` and `begin`, and one line in `hydrate`. Every other module function
and the exported API are byte-identical.

## Tests

- `tests/test_ux_context1_browser.py`: real Chromium, production app on a
  loopback listener. Runs are produced with the agent form or selected from
  the session list; Generate requests are captured in Chromium and compared
  field by field; where the backend answer matters the captured request
  continues to the real route. Module contract tests load the shipped state
  module on a blank page. PRE tests replay the scenarios on the reconstructed
  entry.
- `tests/test_ux_context1.py`: handler serialization, hydration, binding by
  generation, template and module containment, registry, reversal, frozen
  boundaries and completion receipt.

Test counts, timings, the red-green toggle and performance numbers are recorded
in `tests/fixtures/ux_context1_completion.json`.

## Limitations and remaining UX work

- Without an eligible run, Generate shows the backend's generic
  "Invalid control JSON", exactly as on a New Session page. Clearer guidance
  ("run Control or select a run for this repository") would be a copy change.
- After Back navigation Chromium restores a typed repository into the input
  after hydration, so the input can show B while WorkbenchState still holds A
  until the next input event or dispatch. Every dispatching handler reconciles
  first, so requests stay coherent; a render in between writes the owned value
  back into the input.
- Continuing from a run after a repository change takes a new selection of
  that run (history link or reload); there is no in-page run picker.
- On a hydration mismatch (possible only if a browser restores the input before
  the page script runs) the server-rendered candidate still takes the hydrated
  repository, as in UX.STATE.1. Chromium restores after hydration, so the
  dispatch-time reconciliation drops it.
- UX-05 and UX-06 remain open.

## Explicit answers

| Question | Answer |
| --- | --- |
| Can repo B Generate carry CONTROL context from displayed repo A run? | No. The run is ineligible after the change; both Generate requests send the fresh form. |
| Can legitimate same-repo continuation still carry context? | Yes, byte-identical to UX.STATE.1 in the default layout. |
| Can simply typing the old repo path back resurrect stale context? | No. That is a new generation; only an explicit run selection binds again. |
| Can mismatched historical runs inject context? | No. They stay viewable and are never eligible. |
| Is displayed-run state distinct from Generate-eligible context? | Yes: `run` versus the derived `requestRun`. |
| Did UX-02 behavior change? | No. |
| Did UX-03 behavior change? | No. |
| Did UX-04 behavior change? | No. |
| Were backend authority semantics changed? | No. |
| Was Track A changed? | No. |
| Were live model calls added? | No. |
