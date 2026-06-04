# Phase UI.2 — Command Hierarchy / Progressive Disclosure (Design)

**Date:** 2026-06-04
**Phase:** UI.2 (follows the Phase UI.1 information-architecture *freeze*)
**Status:** Design only — approved decisions captured below; **no implementation until a plan is written and approved.**
**Scope:** Web UI re-layering only. No backend, route, handler, patch, benchmark, Dream, model, DB, or subprocess changes. Additive/visual only.

Related: [`docs/web_ui_information_architecture.md`](../../web_ui_information_architecture.md) (UI.1 freeze),
[`docs/superpowers/designs/2026-06-04-lesson-merge-dedupe-design.md`](2026-06-04-lesson-merge-dedupe-design.md) (the just-landed Memory merge/dedupe controls).

---

## 0. Problem statement

UI.1 reduced *button overload* by collapsing advanced/dangerous controls into `<details>`. It did **not** establish a **command hierarchy**: the first screen still presents many controls at *equal visual priority*. The UI reads as a control room.

The issue is not too many features — it is too many **co-equal** controls. UI.2 introduces clear primary/secondary/advanced/dangerous/debug hierarchy, fewer visible top-level controls, and stronger progressive disclosure, **without removing any feature and without breaking the UI.1 freeze contract**.

### Design goals (from brief)

1. One primary action per area.
2. Secondary actions behind *More / Details / Advanced*.
3. Debug/evidence tools remain reachable, one layer deeper.
4. New users see "what to do next."
5. Power users still reach advanced controls quickly.

### Decisions resolved before design (operator-confirmed 2026-06-04)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Migration discipline | **Strict additive** — zero renames of ids/handlers/pinned labels. Pure CSS + `<details>` + a new drawer layer, like UI.1. |
| D2 | Graph placement | **Keep the Graph workspace tab** (id stable per freeze invariant #1); demote it from the primary tab row; move **Debug Graph + Scope Spread** into the Inspector drawer. |
| D3 | Inspector/Debug drawer | **Right-side**, collapsed by default, toggled (Ctrl-J). |
| D4 | Top-level navigation | **Primary + secondary grouping** — ~5 primary destinations; Goal Brief folds into the Run/Chat area; Graph demoted. All `ws-*` panel ids preserved. |

---

## 1. Current UI problems found (audit synthesis)

Grounded in a full control inventory of `web/templates/index.html` (7,678 lines) across all areas. Representative problems:

**Shell / top nav**
- 7 workspace tabs at equal visual weight → choice overload; no primary/secondary signal.
- Agent-form **Options** `<details>` is `open` by default, pushing **Run** below the fold.
- Patch config (`patchStyleSelect`, `applyPolicy`) lives in the global form, far from the patch actions it governs.

**Chat / Patch + result tabs**
- **8 result sub-tabs** (Answer/Context/State/Patch/Validation/Cost/Diff/Candidates) render as one equal-weight row directly above the action buttons — navigation chaos; a new user can't tell which tab matters.
- `Apply / Review Patch` is always equally prominent even when no patch exists yet.
- Raw JSON / local-critique-raw panels float as debug surfaces with no consistent home.

**Memory**
- Acute density: in the Lessons section alone ~13 visible controls (4 status buttons + 5 selects + 2 toggles + Merge + Refresh) plus per-card Promote/Block/Archive plus the new merge bar and duplicate-hints panel.
- Four sibling sections (Consolidate, Proposals, Sub-agent[Handoffs+Worker Runs], Lessons) stack vertically with no segmentation, so the whole knowledge surface loads at once.
- Multiple refresh buttons scattered with no grouping.

**Benchmarks**
- Runner button row mixes primary (Run all) with secondary (Run selected, Add case, Refresh) and advanced (⚙ Options) at equal weight.
- Per-past-run **Delete** (dangerous, red) is always visible alongside Archive/Pin — N×3 buttons.

**Dream**
- `Apply Dream` (dangerous — commits to the real repo) sits in the same button row, at equal weight, as Start Overnight / Seed / Refresh.
- Budget, Research-References, Plan-items always visible regardless of work type.

**Graph**
- `Debug Graph` (advanced) and `Scope Spread` (debug, with target/Top-N inputs + output) render in the same visual plane as the primary `Clean Graph`. No disclosure.

**Settings / cross-cutting debug**
- Debug/inspection surfaces are scattered: graph evidence (visible), replay debugger + tool registry + MCP audit (3 levels deep in `settings-debug`), MCP inspector (in Memory), raw-JSON panels at varying depths. No unified "debug layer."
- 30+ modal flows funnel through one `#appModal`.

**Cross-cutting**
- Dangerous controls are demoted but inconsistently (some warning-styled, some not; not all require confirmation).

---

## 2. Design model: a 3-layer disclosure ladder

UI.2 standardizes **one ladder** applied to every area. A control sits on exactly one rung.

```
Layer 0 — PRIMARY        always visible      one happy-path action per area
Layer 1 — MORE / DETAILS one click (<details>) secondary actions + run evidence
Layer 2 — INSPECTOR      Ctrl-J, right drawer debug / evidence / inspection
─────────────────────────────────────────────────────────────────────────────
Cross-cut — DANGEROUS    behind disclosure + warning accent + confirm; NEVER L0,
                         and NEVER moved into the easier-to-reach drawer.
```

This extends UI.1's "keep power, hide complexity": UI.1 built Layer 1; UI.2 adds **Layer 2 (the Inspector drawer)** and enforces **Layer 0 = one primary per area**.

### Classification taxonomy (continues UI.1's 5-way scheme + a `debug-only` rung)

| Class | Meaning | Default rung |
|-------|---------|--------------|
| **primary** | The happy-path action an operator reaches for first. | Layer 0 |
| **secondary** | Useful but not first-reach (refresh, view, pickers, filters). | Layer 1 |
| **advanced** | Inspection / configuration / power features. | Layer 1–2 |
| **dangerous** | Mutates host/repo or spends quota (.env apply, compose apply, apply dream, block, delete). | Disclosure + warning + confirm (never L0/drawer) |
| **debug-only** | Raw views, evidence-spread, replay, tool/MCP audit. | Layer 2 (Inspector) |

---

## 3. A — Top-level navigation

**Keep all seven `ws-*` panels, ids, and `showWorkspaceTab` keys** (freeze invariant #1). Change only the **tab bar's visual grouping**, additively.

```
TODAY (7 equal peers):
[Chat/Patch] [Goal Brief] [Benchmarks] [Dream] [Memory] [Graph] [Settings/Health]

PROPOSED (primary row + secondary "Views" group):
Primary:    [ Run ] [ Benchmarks ] [ Dream ] [ Memory ] [ Settings ]
Secondary:    Goal Brief  (entered from inside Run)   ·   Graph  (+ Inspector ▸)
```

- **Primary destinations (5):** Run (= Chat/Patch, `ws-chat`), Benchmarks, Dream, Memory, Settings/Health. Styled `.ws-tab--primary`.
- **Secondary destinations:** Goal Brief and Graph, styled `.ws-tab--secondary` and visually separated (a divider or a "Views ▾" cluster). Both panels keep their ids and remain one click away.
  - **Goal Brief** gains an explicit entry affordance from the Run area (e.g., a "Refine goal (Goal Brief) →" link near the query box) so its discoverability does not depend on a peer tab.
  - **Graph** keeps `Clean Graph` in its panel; its debug tools relocate to the drawer (§5).

**Label note (honors D1 = zero renames):** the *conceptual* primary is "Run," but the tab's visible text and id are **unchanged by default** (`#ws-tab-chat`, "Chat / Patch"). Relabeling the visible text to "Run" is an **optional cosmetic tweak** — no test currently pins the literal "Chat / Patch" button text (verified against all four UI test files), but if taken it must be done as a deliberate one-line test update and called out in the plan. Default recommendation: **group visually, keep the label.**

**Why not remove the Graph/Goal-Brief tabs outright?** Freeze invariant #1 pins the seven tab ids and `showWorkspaceTab` keys. Removing a tab is a *migration*, not additive. Demoting it visually (CSS grouping; panel id intact) satisfies "fewer primary destinations" with zero contract risk.

---

## 4. B — Chat / Patch command hierarchy

Keep the existing primary row and the UI.1 `chat-more-actions` disclosure. Tighten three things, all additive:

| Control | Today | UI.2 | How (additive) |
|---|---|---|---|
| Generate Patch / Apply ‑ Review Patch | `.actions--primary`, always enabled | **Keep primary**; *Apply* dims/disables until a patch exists | JS state toggle keyed on `#patchRawJson` non-empty; id/handler unchanged |
| Generate Candidates / Test Run / Undo / Local Critique | `chat-more-actions` `<details>` | **Unchanged** (already Layer 1) | — |
| Vibecoding style (`patchStyleSelect`), Apply policy (`applyPolicy`) | visible in global form | stay in the **Options** disclosure (Layer 1) | move inside `instant-run-controls`; ids unchanged |
| Agent-form **Options** `<details>` | `open` by default | **collapsed by default** | change `open` attribute → closed |
| Patch Raw JSON, Local-critique raw | collapsed `<details>` in Chat | classified **debug**; remain collapsed, *also surfaced* in the Inspector "Raw state" panel | keep existing `<details>` in place; drawer links/mirrors |

Result: the Chat tab's first read is **Query → Generate Patch → Apply**, with everything else one disclosure away.

---

## 5. C — Result inspector (the 8 result tabs)

**Keep all 8 panes** (`#answer #context #state #patch #validation #usage #diff #candidates`) and the `showTab()` handler unchanged (D1). Regroup only the **tab bar**:

```
PRIMARY:  [ Answer ]  [ Patch ]
          └ Run details ▾ ──────────────────────────────────────┐
            [ Context ] [ State ] [ Validation ] [ Cost ] [ Diff ] [ Candidates ]
          └────────────────────────────────────────────────────┘
```

- Wrap the **six secondary tab buttons** in
  `<details class="run-details" data-ui-group="chat-run-details"> … <!-- /chat-run-details --></details>`
  (summary: "Run details"). The two primary buttons (**Answer**, **Patch**) stay outside it.
- `showTab(id)` is unchanged. Small additive JS: when `showTab()` targets a pane whose button lives inside `run-details`, open that disclosure first so the click always works (e.g. `generatePatch()`→`showTab('patch')` still lands on the primary Patch button; `applyPatch()`→`showTab('diff')` opens Run details).
- **Main output area** = Answer + Patch (the actionable artifact). **Run details** = Context, State, Validation, Cost, Diff, Candidates.

No pane is removed; the diff/candidate render targets keep their ids; `selectCandidate()` etc. unchanged.

---

## 6. D — Memory segmentation

Memory already has discrete sections; add a **segmented sub-nav** so they don't all load at once, and group the Lessons filter overload.

```
ws-memory:
  ┌ [ Lessons ] [ Proposals ] [ Handoffs ] [ Worker Runs ]      Consolidate ⌫ (utility) ┐
  │  (segmented sub-nav — shows one section, hides the rest)                              │
  └──────────────────────────────────────────────────────────────────────────────────────┘
```

- **New, additive** `showMemorySection(key)` + `data-ui-group="memory-nav"` segmented control. Existing section markup (`proposals-section`, `subagent-group`/`handoffs-section`/`worker-runs-section`, `lessons-section`) is **wrapped, not rewritten**; every existing id/handler/label preserved.
  - Handoffs and Worker Runs become **two segments** (today they share the `subagent-group`); both keep their existing ids.
  - **Consolidate memory** stays reachable as a small utility action in the Memory header (secondary), not a segment.
- **Duplicate hints stays inside Lessons** (already `#duplicateHintsPanel` within `lessons-section`) — per brief. Not a separate always-visible block.
- **Lessons filter de-clutter (Layer 1):** keep the primary status buttons (All / Candidate / Active / Blocked) + Refresh + Merge visible. Move the *metadata* filters — `lessonFilterKind`, `lessonFilterLanguage/Source/Category/Difficulty`, `showArchivedLessons`, `showSupersededLessons` — behind a **"More filters ▾"** `<details data-ui-group="lessons-more-filters">`. All ids remain in the DOM (tests assert presence in the template string, not visibility), so wrapping is contract-safe.
- **MCP Inspector** (today in the Sub-agent header) is reclassified **debug-only** and surfaced from the Inspector drawer (§7); its `launchMcpInspector()` handlers/ids are preserved and remain reachable.

---

## 7. E — Inspector / Debug drawer

A **new right-side drawer**, collapsed by default, toggled by a header **"Inspector ▸"** button and **Ctrl-J**. It is the single home for **debug-only** surfaces.

```
┌ Sidebar ─┬ Workspace ───────────────┬ Inspector ▸ ─────────┐
│ sessions │ (active workspace tab)   │ ▸ Graph evidence      │
│ dreams   │                          │ ▸ Replay debugger     │
│          │                          │ ▸ Raw state / JSON    │
│          │                          │ ▸ Tool/MCP (launch ↗) │
└──────────┴──────────────────────────┴───────────────────────┘
                                   collapsed by default · Ctrl-J
```

**Drawer panels:**

| Panel | Hosts | Source handlers (reused) |
|---|---|---|
| **Graph evidence** | Debug Graph, Scope Spread (target node, Top-N, output) | `viewGraph('debug')`, `explainEvidenceSpread('graph'|'chat')` |
| **Replay debugger** | replay list + detail + compare + artifact previews | `loadReplays`, `viewReplay`, `compareReplay` |
| **Raw state / JSON** | patch raw, local-critique raw, benchmark raw, dream-report raw (links/mirrors) | existing `<details>` nodes |
| **Tool / MCP (launchers)** | MCP Inspector launch; **links** to Tool Registry & MCP Audit | `launchMcpInspector`, jump-to-Settings |

**Strict-additive constraints that shape the drawer (important):**

1. **Inline only.** Freeze tests assert `<script src=>` count == 2 (mermaid CDN + `keybindings.js`). The drawer must be **inline JS + CSS** — no new external script.
2. **Do not move freeze-pinned debug nodes.** `test_web_ui_information_architecture.py` pins `toolRegistryList` and `mcpAuditList` *inside* the `settings-debug` segment. Those nodes **stay physically in Settings**; the drawer provides **launcher links** ("Open Tool Registry / MCP Audit in Settings →") rather than relocating the DOM (which would break the freeze test and produce duplicate ids).
3. **Free-to-relocate** surfaces (NOT freeze-pinned to a location): Graph debug/Scope Spread, Replay debugger (`replayList` is *not* asserted to be in `settings-debug`), raw-JSON/state viewers, MCP inspector launcher. These move/mirror into the drawer.
4. **Dangerous stays put.** `.env apply` and `docker-compose apply` (`harnessEnvApply`, `harnessComposeApply`) remain in the warning-accented `settings-harness` panel. They are **never** placed in the drawer (a drawer is *easier* to reach than a buried disclosure — moving them there would weaken safety).
5. **New contract anchors.** The drawer and each panel carry `data-ui-group="inspector-*"` + matching `<!-- /inspector-* -->` sentinels, per the UI.1 convention, so UI.2 tests can pin them.

The drawer is **collapsed by default** so it never competes with the primary workspace; power users reach all debug tooling with one keystroke.

---

## 8. F — Primary / secondary / advanced / dangerous / debug classification

Per-area reclassification (only the controls that *change rung* or anchor the hierarchy; full 80-control inventory lives in the audit). Rungs: **L0** primary · **L1** more/details · **L2** inspector · **DGR** dangerous · **DBG** debug-only.

**Shell / form**
| Control | Class | Rung |
|---|---|---|
| Repo path, Query, Run (`primarySubmit`) | primary | L0 |
| Mode switcher, + New Session | primary (nav) | L0 |
| Options disclosure (Mode/Agent/Style/DNA/Env/Apply policy) | secondary/advanced | L1 (collapsed by default) |
| Status chip | secondary | L1 (post-run) |

**Chat / Patch**
| Generate Patch, Apply‑Review Patch | primary | L0 (Apply gated on patch exists) |
| Answer, Patch (result tabs) | primary view | L0 |
| Context/State/Validation/Cost/Diff/Candidates | secondary view | L1 (`chat-run-details`) |
| Generate Candidates/Test Run/Undo | secondary | L1 (`chat-more-actions`) |
| Local Critique, raw JSON, critique raw | debug | L2 / collapsed |

**Memory**
| Segmented sub-nav, status filters, Promote | primary | L0 |
| Refresh, Merge lessons, View, Create candidate | secondary | L0–L1 |
| Kind/lang/source/category/difficulty filters, Show archived/superseded, Archive | secondary/advanced | L1 (`lessons-more-filters`) |
| Block, Promote (allow failed), Create+Run, Run subagent | dangerous | DGR (warning + confirm) |
| MCP Inspector, View MCP audit | debug | L2 |

**Benchmarks**
| Run all, past-runs list/detail, Open evidence index | primary | L0 |
| Run selected, Add case, Refresh, Build evidence pack | secondary | L1 |
| ⚙ Options (Fast/Turbo/Skip/Retry), Prompt/Cost | advanced | L1 (already collapsed) |
| Per-run Archive/Pin | secondary | L1 (per-card "⋯" menu) |
| Per-run **Delete** | dangerous | DGR (per-card menu + confirm) |

**Dream**
| Work type/level/title, Add/View queue, Start Overnight | primary/secondary | L0 |
| Clear queue, Seed from benchmark, Refresh status, Budget | secondary/advanced | L1 |
| Research references, Trials, Plan items | advanced | L1 (collapsible, work-type aware) |
| **Apply Dream**, Apply selected | dangerous | DGR (warning + confirm) |

**Graph**
| Clean Graph, zoom/reset, show tests | primary/secondary | L0 (Graph tab) |
| **Debug Graph**, **Scope Spread** (+inputs/output) | advanced/debug | L2 (Inspector) |

**Settings / Health**
| Appearance, Keyboard shortcuts, System health, Help | secondary | L0 |
| Harness Controls (live toggles incl. Cooling Brain) | advanced | L1 (`settings-harness`) |
| **.env apply**, **compose preview/apply** | dangerous | DGR (`settings-harness`, warning) |
| Tool Registry, MCP Audit, Replay | debug | L1 `settings-debug` (+ drawer launcher) |

### Controls to KEEP visible (Layer 0)

Repo path · Query · **Run** · Mode switcher · + New Session · **Generate Patch** · **Apply/Review Patch** (gated) · **Answer** + **Patch** result tabs · Memory segmented nav + status filters + **Promote** · **Run all benchmarks** · past-runs list + **Open evidence index** · **Start Overnight** · **Clean Graph** · Appearance / Health / Help · the new **Inspector ▸** toggle.

### Controls to HIDE behind More / Details / Inspector

- **More / Details (L1):** agent-form Options (collapsed by default) · Generate Candidates / Test Run / Undo · the 6 secondary result tabs (Run details) · Lessons metadata filters (More filters) · benchmark ⚙ Options + Prompt/Cost · per-run Archive/Pin · Dream Clear queue / Seed / Budget / Research / Trials / Plan items · Harness Controls.
- **Inspector drawer (L2 / debug):** Debug Graph · Scope Spread · Replay debugger · raw JSON / raw state viewers · MCP Inspector · (links to) Tool Registry + MCP Audit.
- **Dangerous (disclosure + warning + confirm, never primary, never in drawer):** `.env` apply · compose preview/apply · Apply Dream / Apply selected · Block lesson · Promote (allow failed) · Create+Run handoff · Run subagent · per-run Delete.

---

## 9. G — Implementation split

Four small, independently shippable, independently test-pinned phases. Each: additive markup + CSS + inline JS + a new contract-test file/section; run the full suite (+ `benchmarks/run_benchmarks.py --check`) green before the next.

| Sub-phase | Scope | Touches | New contract anchors |
|---|---|---|---|
| **UI.2a — Memory segmentation** | Segmented sub-nav over existing Lessons/Proposals/Handoffs/Worker Runs; group Lessons metadata filters behind "More filters"; keep Duplicate hints inside Lessons. | template + CSS + `showMemorySection()` (new, inline) | `memory-nav`, `lessons-more-filters` |
| **UI.2b — Chat/Patch result inspector** | Wrap 6 secondary result tabs in `run-details`; keep Answer/Patch primary; gate Apply on patch-exists; collapse form Options by default; relocate style/apply-policy into Options. | template + CSS + small `showTab()` open-on-demand | `chat-run-details` |
| **UI.2c — Inspector / debug drawer** | New right-side drawer (inline JS+CSS, Ctrl-J); host Graph debug + Scope Spread + Replay + raw-state; launcher links to Tool Registry/MCP Audit (kept in Settings); MCP inspector → drawer. | template + CSS + `toggleInspector()` (new, inline) | `inspector-drawer`, `inspector-graph`, `inspector-replay`, `inspector-raw`, `inspector-tools` |
| **UI.2d — Primary-action cleanup** | Top-nav primary/secondary grouping; demote Graph + Goal Brief; Goal-Brief entry from Run; per-card "⋯" menus for benchmark Archive/Pin/Delete; consistent dangerous warning + confirm (Apply Dream, Block, Delete). | template + CSS (+ minimal JS for menus/confirm) | `ws-nav-primary`, `ws-nav-secondary` |

**Sequencing:** 2a → 2b → 2c → 2d. 2d's Graph demotion depends on 2c (the drawer must exist to receive Debug Graph + Scope Spread). 2a and 2b are independent and could land in either order.

**Each sub-phase is reversible** (markup/CSS only) and leaves every prior phase's tests green.

---

## 10. H — Tests (contract test design)

New file **`tests/test_web_ui_command_hierarchy.py`** (same text-parsing, zero-heavy-import style as the UI.1 freeze test, with its own AST self-guard). It must assert:

**Feature reachability (regression guard)**
- Every preserved id/handler/label from the UI.1 + merge contracts is still present in the template (re-assert the existing pinned tokens; nothing dropped).
- All 8 result panes (`answer…candidates`) and `showTab(` still present; all `ws-*` panel ids + `showWorkspaceTab('…')` keys still present (freeze invariant #1).

**Result inspector (UI.2b)**
- `data-ui-group="chat-run-details"` exists with a matching `<!-- /chat-run-details -->` sentinel.
- `showTab('answer')` and `showTab('patch')` appear **before** the `chat-run-details` marker; `showTab('context'|'state'|'validation'|'usage'|'diff'|'candidates')` appear **inside** the segment (`_group_segment`).

**Memory segmentation (UI.2a)**
- `data-ui-group="memory-nav"` segmented control exists; `showMemorySection(` defined.
- `lessons-section`, `proposals-section`, `handoffs-section`, `worker-runs-section` all still present.
- `#duplicateHintsPanel` lies **inside** the Lessons segment (not a standalone always-visible block).
- `lessonFilterKind`, `showArchivedLessons`, `showSupersededLessons` live **inside** `lessons-more-filters`; status buttons (`filterLessons('')…`) stay **outside** it.

**Debug drawer (UI.2c)**
- `data-ui-group="inspector-drawer"` exists, with sentinel; the toggle (`toggleInspector` / `id="inspectorToggle"`) present; drawer markup carries a collapsed/`hidden` default (assert the default-closed attribute/class).
- `viewGraph('debug')` and `explainEvidenceSpread(` reachable from inside the inspector segment.
- **Dangerous-not-in-drawer:** `harnessEnvApply`, `harnessComposeApply` are **NOT** inside the `inspector-drawer` segment and **remain** inside `settings-harness`.
- **Freeze-pinned-stay-put:** `toolRegistryList`, `mcpAuditList` still inside `settings-debug`.
- `<script src=` count is still **2** (drawer added no external script).

**Dangerous controls never primary**
- `applyDream`, `applyEnvFiles`, `applyComposePatch`, `blockLessonById`, `_deleteBenchmark` handlers are **not** inside any `actions--primary` / primary-nav block; the buttons carry their warning/danger classes; the stylesheet styles those classes.

**No backend behavior changed**
- Reuse the UI.1 guards: forbidden tokens (`os.system`, `child_process`, `eval(`, `new Function(`, `document.write(`) absent; verbatim read-only safety copy preserved. The drawer reuses existing debug routes — UI.2 adds **no new backend endpoint** (assert via the unchanged forbidden-token + script-count guards rather than a brittle route allowlist).
- Continue the **convention test**: every `data-ui-group="x"` has a matching `<!-- /x -->` sentinel.

**Update existing tests minimally**
- `test_web_ui_information_architecture.py` / `test_web_ui_demo_flow.py`: only *additions* expected. If the optional "Run" relabel (D4 note) is taken, update the single affected label assertion in the same commit.

---

## 11. Safety invariants

1. **Additive only.** No backend, route, handler-name, element-id, or pinned-label change. Every control keeps its `onclick`/`id` so existing JS (`getElementById`, dynamic renders) keeps working open or closed.
2. **Freeze invariant #1 preserved.** All seven `ws-*` tab ids and `showWorkspaceTab` keys remain stable; reduction is visual grouping, not removal.
3. **Contract anchors.** Every new collapsible/drawer carries a unique `data-ui-group="…"` + matching `<!-- /… -->` sentinel; existing UI.1 anchors (`chat-more-actions`, `settings-harness`, `settings-debug`, `benchmark-prompt-cost`) are untouched (freeze invariant #4).
4. **Dangerous stays demoted.** `.env` apply, compose apply, Apply Dream, Block, per-run Delete, Promote-allow-failed, Create+Run, Run-subagent never become Layer-0 actions and are **never** moved into the Inspector drawer; they keep warning styling and gain/keep explicit confirmation.
5. **Reachability preserved.** No feature removed; only re-layered. Goal Brief, Graph, MCP Inspector, Tool Registry, MCP Audit, Replay all remain reachable.
6. **No new external script.** `<script src=>` count stays 2; the drawer is inline JS + CSS (mermaid CDN + `keybindings.js` are the only externals).
7. **Defaults unchanged.** Memory Temperature / Cooling Brain stays OFF by default; the `editable_live` render path is intact. No scoring/CONTROL-prompt/patch-safety logic touched.
8. **Verbatim safety copy** of read-only/inert panels preserved (asserted): benchmarks "writes reports to .agent/benchmarks", evidence "Read-only: never runs benchmarks or calls models", harness "This panel does not write", registry "Registry is metadata-only…", audit "Audit is read-only…".

---

## 12. Migration-safety map (the frozen contract — do not change without an explicit, test-updated migration)

Hard-pinned by substring assertions across `test_web_ui_information_architecture.py`, `test_web_ui_lesson_merge_controls.py`, `test_web_ui_history_controls.py`, `test_web_ui_demo_flow.py`:

- **Ids:** `repoPathInput`, `primarySubmit`, `harnessControlsList`, `harnessEnvApply`, `harnessComposeApply`, `toolRegistryList`, `mcpAuditList`, `promptCostSection`, `benchOptionsToggle`, `benchRunOptions`, `benchOptFast/Turbo/SkipToolchain/Retry`, `showArchivedBenchmarks`, `showArchivedDreamRuns`, `mergeSelectToggle`, `duplicateHintsPanel`, `lessonFilterKind`, `showArchivedLessons`, `showSupersededLessons`, `mergePreviewTitle`, `mergePreviewSummary`, `mergeConfirmSupersede`, `mergeCreateBtn`.
- **Handlers/labels:** `generatePatch()`, `applyPatch()`, `runAllBenchmarks()`, `openPresentationEvidenceIndex()`, `buildPresentationEvidence()`, `generateCandidates()`, `testPatch()`, `undoPatch()`, `localCritique()`, `_renderHarnessControls`, `loadHarnessControls`, `toggleBenchmarkOptions`, `refreshPromptCost()`, `refreshSessionList(`, `createMergedCandidate()`, `archiveLessonById`, `editable_live`; labels "Generate Candidates", "Test Run Patch", "Undo", "Local Critique", "Tool Registry", "Recent MCP Audit", "Merge lessons", and "Active lessons cannot be archived; supersede through merge instead."
- **Structure:** `class="actions actions--primary"`; `<details class="more-actions" data-ui-group="chat-more-actions">`; `<details class="advanced-panel" data-ui-group="settings-harness">`; `<details class="advanced-panel" data-ui-group="settings-debug">`; `<details class="reports-panel" data-ui-group="benchmark-prompt-cost">`; `generatePatch()`/`applyPatch()` **before** `chat-more-actions`; `harnessEnvApply`/`harnessComposeApply` **inside** `settings-harness`; `toolRegistryList`/`mcpAuditList` **inside** `settings-debug`; `openPresentationEvidenceIndex()` **outside** the prompt/cost and harness segments.
- **Counts / routes:** `<script src=>` == 2, `src="http"` == 1; history route strings (`/history/session|benchmark|dream/...`, `DELETE_SESSION|BENCHMARK_REPORT|DREAM_RUN`, `include_archived=1`, "Unpin before deleting").
- **Docs:** `docs/web_ui_information_architecture.md` and `docs/demo_flow.md` must keep their asserted sections/taxonomy.

UI.2 treats all of the above as **read-only**: it re-parents nodes only where doing so keeps the pinned token present and inside the asserted segment.

---

## 13. Non-goals (explicitly out of scope)

- No backend/route/handler/id changes; no patch-safety, validation, benchmark-scoring, or CONTROL-prompt logic.
- No DB, Docker lifecycle, model/API, Dream-runner, or subprocess changes.
- No feature removal; no modal-flow rewrite (the `#appModal` singleton stays).
- No new external JS/CSS dependency.
- No change to Memory Temperature / Cooling Brain defaults.
- No mandatory tab relabel (the "Run" label is optional and flagged).

---

## 14. Open questions for the implementation plan

1. **Goal Brief demotion mechanism:** keep it as a (secondary-styled) tab vs. fold it as a sub-view launched from Run. Both preserve `ws-goal-brief`; pick the smaller-footprint option in UI.2d.
2. **Per-card action menus (Benchmarks):** introduce a "⋯" kebab for Archive/Pin/Delete vs. keep inline buttons with stronger danger styling for Delete only.
3. **Drawer ↔ Graph-tab coupling:** does Debug Graph render into the existing `#graph` canvas (drawer hosts only controls) or into a drawer-local canvas? Recommend reusing `#graph`/`#graphSpreadOutput` to avoid duplicate render targets.
4. **Optional "Run" relabel** (D4 note): take it (with a one-line test update) or keep "Chat / Patch"?
5. **Confirm step for dangerous actions:** standardize on `openAppModal`-based confirmation vs. native `confirm()` — recommend the modal for consistency, but that is a small JS addition to verify against the "no backend behavior" guard.
