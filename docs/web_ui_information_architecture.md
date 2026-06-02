# Web UI — Information Architecture (Phase UI.1 freeze)

This document inventories and classifies every visible control in
`web/templates/index.html`, fixes the top-level information architecture (IA),
and records which controls are visible-by-default vs. collapsed behind an
*Advanced / More / Report* disclosure.

**Principle: keep power, hide complexity.** Nothing was removed or renamed —
secondary, advanced/debug, and dangerous/config controls are simply demoted into
collapsible `<details>` sections so the first screen reads as a small set of
primary demo actions. The contract is pinned by
`tests/test_web_ui_information_architecture.py`.

This is an IA *freeze*, not a visual redesign. A later phase may restyle; it must
not silently re-promote a dangerous control or drop a power feature past the
tests here.

---

## 1. Top-level structure

The UI already organizes work as a **persistent shell + 7 workspace tabs**:

```
┌ Sidebar ───────────┐  ┌ Main ────────────────────────────────────────┐
│ Brand + Help (?)   │  │ Header (mode title)                          │
│ Mode switcher:     │  │ Agent form: repo path · query · Run  (always)│
│   Chat / Instant   │  │ ┌ Workspace tabs ───────────────────────────┐│
│ + New Session      │  │ │ Chat/Patch · Goal Brief · Benchmarks ·     ││
│ Recent sessions    │  │ │ Dream · Memory · Graph · Settings / Health ││
│ Dream runs         │  │ └────────────────────────────────────────────┘│
└────────────────────┘  └──────────────────────────────────────────────┘
```

The seven workspace tabs (`#ws-tab-*` / `#ws-*`, switched by `showWorkspaceTab`):

1. **Chat / Patch** (`ws-chat`)
2. **Goal Brief** (`ws-goal-brief`)
3. **Benchmarks** (`ws-benchmarks`)
4. **Dream** (`ws-dream`)
5. **Memory** (`ws-memory`)
6. **Graph** (`ws-graph`)
7. **Settings / Health** (`ws-settings`)

### Suggested 6 groups → existing 7 tabs

The Phase UI.1 brief proposed six top-level groups. They map cleanly onto the
existing tabs, so the freeze **keeps the 7 tabs** rather than re-pointing the tab
JS (lower risk):

| Suggested group        | Realized by tab(s)                                  |
| ---------------------- | --------------------------------------------------- |
| **Chat / Patch**       | `Chat / Patch` (+ `Goal Brief` as a sibling helper) |
| **Graph / Explainability** | `Graph`                                         |
| **Benchmarks**         | `Benchmarks`                                         |
| **Memory / Lessons**   | `Memory`                                             |
| **Reports / Evidence** | Presentation evidence pack + Prompt/Cost (in `Benchmarks`); Dream reports (in `Dream`) |
| **Settings / Advanced**| `Settings / Health`                                 |

`Goal Brief` and `Dream` remain their own tabs (they are large independent
workflows). `Reports / Evidence` is not a separate tab — its panels live inside
`Benchmarks` and `Dream`; the *primary* report action ("Open evidence index")
stays visible, while the secondary report (Prompt/Cost) is collapsed.

---

## 2. Classification taxonomy

Every control is classified as exactly one of:

- **primary demo action** — the happy-path actions a demo/operator reaches for
  first. Visible by default.
- **secondary action** — useful but not first-reach (refresh, view, pickers,
  status). Visible, but visually muted or one tab deep.
- **advanced/debug** — inspection / debugging / raw views. Collapsed behind a
  disclosure.
- **dangerous/config** — actions that mutate machine/host config or spend quota
  (.env apply, docker-compose apply, apply dream). Collapsed **and** carry a
  warning accent; never a primary visual action.
- **deprecated/rare** — disabled placeholders or near-unused controls. Left in
  place, not promoted.

### Visible-by-default vs. collapsed (summary)

**Visible by default**

- Repo path, project tag, query input, **Run** (`#primarySubmit`)
- Chat/Patch: **Generate Patch**, **Apply / Review Patch**, result view sub-tabs
- Benchmarks: **Run all**, past-runs list/detail, **Open evidence index**
- Graph: **Clean Graph**
- Settings: Appearance, Keyboard Shortcuts, System health, Help

**Collapsed / advanced (behind a `<details>`)**

- Chat/Patch: Generate Candidates, Test Run Patch, Undo, Local Critique
  (`More actions`)
- Benchmarks: run options (Fast/Turbo/Skip-toolchain/Retry, `⚙ Options`),
  Prompt/Cost Quantifier
- Graph: Debug Graph, Scope Spread (debug)
- Settings: **Harness Controls** (incl. `.env` apply + docker-compose
  preview/apply), **Tool Registry**, **Recent MCP Audit**
- Memory: MCP Inspector, raw proposal/worker-run views
- Raw JSON / log / dogfood views throughout

---

## 3. Control inventory by area

Legend: **P** primary demo · **S** secondary · **A** advanced/debug ·
**D** dangerous/config · **X** deprecated/rare. *Vis.* = Visible / Collapsed.

### Shell — Sidebar (always present)

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Help `?` | `openHelpModal()` | S | Visible |
| Mode switcher: Chat / Instant Run | `setProductMode()` | P (nav) | Visible |
| + New Session | link | P | Visible |
| Recent sessions | links | P | Visible |
| Dream runs (list + ⟳) | `refreshDreamRuns()` | S | Visible |

### Shell — Agent form (always present)

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Repo path | `#repoPathInput` | P | Visible |
| Project tag | `name=project_tag` | S | Visible |
| Query | `name=query` | P | Visible |
| Options (Mode, Running environment, …) | `details.instant-run-controls` | S | Collapsible (open) |
| Run | `#primarySubmit` | P | Visible |

### Tab 1 — Chat / Patch

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Result sub-tabs (Answer…Candidates) | `showTab()` | S | Visible |
| Generate Patch | `generatePatch()` | P | Visible |
| Apply / Review Patch | `applyPatch()` | P | Visible |
| Generate Candidates | `generateCandidates()` | S | **More actions** |
| Test Run Patch | `testPatch()` | S | **More actions** |
| Undo | `undoPatch()` | S | **More actions** |
| 🧠 Local Critique | `localCritique()` | A | **More actions** |
| Local critique raw / Patch raw JSON | `<details>` | A | Collapsed |

### Tab 2 — Goal Brief

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Start brief / Send reply / Copy final prompt | `startGoalBrief()` … | P/S | Visible |
| Send to Dream later (disabled) | — | X | Visible (inert) |
| Quick-reply chips | `insertGoalBriefReply()` | S | Visible |
| Raw details | `<details>` | A | Collapsed |

### Tab 3 — Benchmarks

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Run all | `runAllBenchmarks()` | P | Visible |
| Run selected | `openBenchmarkCasePicker()` | S | Visible |
| Add case | `openCreateBenchmarkCaseModal()` | S | Visible |
| ⚙ Options (Fast/Turbo/Skip/Retry) | `toggleBenchmarkOptions()` → `#benchRunOptions` | A | Collapsed |
| Stop run / Refresh status | `stopBenchmarkRun()` / `refreshBenchmarkStatus()` | S | Visible |
| Past runs list + detail | — | P (view) | Visible |
| Build presentation evidence pack | `buildPresentationEvidence()` | S | Visible |
| Open evidence index | `openPresentationEvidenceIndex()` | P | Visible |
| Prompt / Cost Quantifier | `refreshPromptCost()` | A (report) | **Collapsed** |

### Tab 4 — Dream

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Work type / action level / title / hint | selects + inputs | S | Visible |
| Add / View / Clear queue | `addDreamItem()` … `clearDreamQueue()` | S | Visible |
| Start overnight | `startOvernight()` | S (heavy) | Visible |
| Apply dream | `applyDream()` | D | Visible (own panel) |
| Seed from benchmark / Stop / Refresh | `seedDreamFromBenchmark()` … | S | Visible |
| Research references, trials, plan items, reports | various | A | Collapsed / on-demand |

### Tab 5 — Memory

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Consolidate memory | `consolidateMemory()` | S | Visible |
| Proposals: Create candidate / Promote (allow failed) | `promoteProposalToLesson()` | S/A | Visible |
| MCP Inspector | `launchMcpInspector()` | A | `<details>` |
| Mayor Mode: Create handoff / Create + Run | `createHandoff()` | S/D | `<details>` (opt-in run) |
| Worker runs: Import / Validate / View | `importWorkerRun()` … | A | Visible (cards) |
| Lessons: filters + Promote / Block | `filterLessons()` / `blockLessonById()` | S/D | Visible |

### Tab 6 — Graph / Explainability

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Clean Graph | `viewGraph('clean')` | P | Visible |
| Debug Graph | `viewGraph('debug')` | A | Visible (labeled debug) |
| show tests | `#graphShowTests` | S | Visible |
| Open in Obsidian | `openObsidian()` | S | Visible |
| Scope Spread | `explainEvidenceSpread('graph')` | A | Visible (debug) |
| Zoom +/−/reset | `zoomGraph()` / `resetGraph()` | S | Visible |

### Tab 7 — Settings / Health

| Control | Handler | Class | Vis. |
| --- | --- | --- | --- |
| Appearance (theme chips) | `setTheme()` | S | Visible |
| Keyboard Shortcuts | `kbResetAll()` | S | Visible |
| System health | `loadHealthPanel()` | S | Visible |
| **Harness Controls** (live toggles incl. Cooling Brain) | `loadHarnessControls()` | S | **Advanced `<details>`** |
| ↳ `.env` apply | `applyEnvFiles()` | **D** | **Advanced (warning)** |
| ↳ docker-compose preview / apply | `previewComposePatch()` / `applyComposePatch()` | **D** | **Advanced (warning)** |
| Help / Open README | `openHelpModal()` | S | Visible |
| **Tool Registry** | `loadToolRegistry()` | A | **Advanced `<details>`** |
| **Recent MCP Audit** | `loadMcpAudit()` | A | **Advanced `<details>`** |

> The **Cooling Brain (Memory Temperature)** toggle is rendered dynamically into
> `#harnessControlsList` from `GET /harness/controls` via the `editable_live`
> render path. It remains reachable inside the (now collapsed) Harness Controls
> panel; it is OFF by default. See the README "Cooling Brain" section.

---

## 4. What Phase UI.1 changed (and what it did not)

**Changed (template + CSS + this doc + tests only):**

- Chat/Patch action row → primary row (`actions--primary`) + collapsed
  `More actions` (`<details data-ui-group="chat-more-actions">`).
- Settings/Health → Harness Controls wrapped in
  `<details class="advanced-panel" data-ui-group="settings-harness">`; Tool
  Registry + MCP Audit wrapped in
  `<details class="advanced-panel" data-ui-group="settings-debug">`.
- Benchmarks → Prompt/Cost wrapped in
  `<details class="reports-panel" data-ui-group="benchmark-prompt-cost">`.
- CSS: primary/secondary button hierarchy, compact disclosure styling, a warning
  accent on the dangerous `settings-harness` panel and a danger focus ring on the
  `.env` / compose apply buttons.

**Explicitly NOT changed:**

- No backend behavior, no routes, no JS handler names, no element `id`s, no
  button labels (every pinned substring survives).
- No patch-safety, validation-command, benchmark-scoring, or CONTROL-prompt
  logic.
- No DB, Docker lifecycle, or model/API behavior.
- No Memory Temperature defaults (the Cooling Brain toggle stays OFF by default).

Each collapsed control still lives in the DOM, so existing JS
(`getElementById`, dynamic renders, `onclick`) keeps working whether a panel is
open or closed.

---

## 5. Freeze invariants (for the next redesign)

1. The seven workspace tab `id`s and `showWorkspaceTab` keys are stable.
2. Dangerous/config actions (`applyEnvFiles`, `applyComposePatch`, apply dream)
   must never be promoted to an always-visible primary button.
3. The primary demo actions in §2 must remain visible by default.
4. The `data-ui-group="…"` markers + `<!-- /… -->` sentinels are the contract
   anchors for `tests/test_web_ui_information_architecture.py`; keep them when
   moving a panel.
5. Read-only/inert panels keep their safety copy verbatim (it is asserted).
