# Phase UI.2 — Demo Flow & Screenshot Polish: Design Spec

**Date:** 2026-06-02  
**Scope:** Documentation + tests only. No template, CSS, route, or backend changes.  
**Builds on:** Phase UI.1 (IA freeze — `docs/web_ui_information_architecture.md`)

---

## 1. Goal

Prepare C.A.T.T.U.S for a clean presentation/demo by:

1. Writing a structured demo flow document with 3-min and 5-min scripts.
2. Embedding a screenshot checklist in that document.
3. Adding a test file that pins the demo path as a contract — verifying the
   UI structure supports the demo and that no safety-critical core behavior
   has been altered.

There are **no template, CSS, route, or backend changes** in this phase.
UI.1 already ensured the primary actions are visible and dangerous controls
are collapsed; UI.2 documents and tests that state.

---

## 2. Deliverables

### 2a. `docs/demo_flow.md`

Single Markdown file. Screenshot checklist embedded (no separate file).

**Required sections:**

| Section | Content |
|---|---|
| `## 3-Minute Demo` | 8 numbered stops: what to click, one-liner script per stop |
| `## 5-Minute Demo` | Same 8 stops + 4 extras (Goal Brief, Memory, Cooling Brain, Dream queue) |
| `## Fallback` | What to do if live analysis is slow (use pre-run session; benchmarks are cached) |
| `## Safety message` | Verbatim: *"Dangerous controls are available but collapsed; automation is gated."* |
| `## Screenshot Checklist` | 7-item checklist (see §3) |

**3-minute demo stops:**

1. Open app — show repo path + query fields.
2. Run analysis (or load pre-run session for fallback).
3. Graph tab — clean graph + evidence spread.
4. Chat/Patch tab — Generate Patch.
5. Chat/Patch tab — Apply / Review Patch.
6. Benchmarks tab — show last result (32 checked, 0 errors); do not re-run.
7. Benchmarks tab — click "Open evidence index."
8. Settings tab — point at collapsed Harness Controls (safety proof).

**5-minute extras (after stop 8):**

9. Goal Brief tab — start a brief, show guided checklist.
10. Memory tab — show lessons list.
11. Settings → open Harness Controls → show Cooling Brain toggle (OFF by default).
12. Dream tab — show queue panel only; do not start a run.

### 2b. `tests/test_web_ui_demo_flow.py`

8 tests. Text-only parsing (no Flask, no heavy imports). Mirrors the IA test
pattern from `tests/test_web_ui_information_architecture.py`.

| Test | Purpose |
|---|---|
| `test_demo_flow_doc_exists_and_has_required_sections` | Doc exists; contains "3-minute", "5-minute", "fallback", "screenshot checklist", safety message text |
| `test_primary_demo_actions_visible` | Template contains repo path, query, run, generatePatch(), applyPatch(), runAllBenchmarks(), openPresentationEvidenceIndex() |
| `test_advanced_dangerous_controls_remain_collapsed` | harness, settings-debug, benchmark-prompt-cost panels still inside `<details>` anchors |
| `test_evidence_index_visible_outside_collapsed_panels` | openPresentationEvidenceIndex() appears in template outside all collapsed groups |
| `test_harness_controls_reachable` | harnessControlsList, harnessEnvApply, harnessComposeApply in DOM inside harness `<details>` |
| `test_no_new_backend_tokens_in_template` | No privileged tokens; `<script src=` count == 2; `src="http` count == 1 |
| `test_ast_safety_guards` | Core safety tokens present: `reject_ungrounded_patch` in `patching/patch_gates.py`, `run_validation_command` in `core/validator.py`, `MEMORY_TEMPERATURE_RETRIEVAL_ENABLED` + `EDITABLE_LIVE` in `core/harness_controls.py`, `"PASS"` scoring token in `benchmarks/run_benchmarks.py` |
| `test_audit_module_has_no_forbidden_imports` | Self-guard: only `ast`, `pathlib`, `re`, `__future__` imported |

**Deliberate overlap with IA tests** (tests 2, 3, 5, 6): the demo-flow test
file should read as a standalone contract. Someone preparing for a demo can
read this file alone and trust the UI is ready.

---

## 3. Screenshot Checklist (7 items)

To be embedded in `docs/demo_flow.md`:

1. Chat/Patch primary row — Generate Patch + Apply/Review Patch visible.
2. Graph tab — clean graph rendered with at least one node.
3. Graph tab — Evidence Spread output visible.
4. Benchmarks tab — runner with ⚙ Options collapsed (default state).
5. Benchmarks tab — result detail showing 32 checked, 0 errors.
6. Memory tab — Lessons list or Cooling Brain shadow/toggle.
7. Settings tab — Harness Controls `<details>` collapsed (advanced panel closed).

---

## 4. Hard guardrails (unchanged from spec)

- No backend routes changed.
- No patch safety changed (`reject_ungrounded_patch` remains the live gate).
- No validation safety changed (`run_validation_command` unchanged).
- No benchmark scoring changed.
- No CONTROL prompt changed.
- No DB/Docker/model/API behavior changed.
- No Memory Temperature defaults changed (Cooling Brain stays OFF).
- No controls deleted.

The `test_ast_safety_guards` test enforces these mechanically by checking
that known safety tokens are still present in their respective source files:
`patching/patch_gates.py`, `core/validator.py`, `core/harness_controls.py`,
and `benchmarks/run_benchmarks.py`.

---

## 5. Validation commands

```
python -m compileall web tests
python -m pytest tests/test_web_ui_information_architecture.py tests/test_web_ui_demo_flow.py -q
python -m pytest tests -q --basetemp .fresh_tmp_ui2
python benchmarks/run_benchmarks.py --check
```

---

## 6. What this phase does NOT do

- No template edits (no empty-state copy, no Step 1/2/3 labels).
- No CSS changes.
- No new routes or Flask views.
- No changes to any `core/` module.

A future UI.3 may add template copy polish once the demo is validated
against this baseline.
