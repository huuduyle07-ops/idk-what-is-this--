# C.A.T.T.U.S — Demo Flow

> Last updated: 2026-06-02. Covers Phase UI.2 (IA freeze active).

**Safety message:** Dangerous controls are available but collapsed; automation is gated.

---

## 3-Minute Demo

Eight stops. Each stop has a *click* action and a *say* line.

| # | Tab / Area | Click | Say |
|---|-----------|-------|-----|
| 1 | **Agent form** | Point at repo path field and query textarea | "You give it a repo path and a question — that's the whole input." |
| 2 | **Agent form** | Click **Run** (or load a pre-run session — see Fallback) | "It runs the full retrieval + analysis pipeline." |
| 3 | **Graph** tab | Click **Clean Graph**, then click **Scope Spread** | "This is the explainability layer — every node is a code file, edges are evidence links." |
| 4 | **Chat / Patch** tab | Click **Generate Patch** | "Based on that graph evidence, it proposes a targeted patch." |
| 5 | **Chat / Patch** tab | Click **Apply / Review Patch** | "Apply writes the patch to disk; the diff is shown immediately for review." |
| 6 | **Benchmarks** tab | Click on the latest run in the past-runs list | "32 checks, 0 errors — the safety suite runs after every patch." |
| 7 | **Benchmarks** tab | Click **Open evidence index** | "This is the full audit trail — every benchmark result linked to its evidence pack." |
| 8 | **Settings / Health** tab | Point at the **Advanced** disclosure (do not open) | "Harness controls, .env apply, and docker-compose are all here — available but collapsed. Nothing dangerous runs automatically." |

**Total time:** ~3 minutes at a comfortable pace.

---

## 5-Minute Demo

Run the 8 stops above, then continue:

| # | Tab / Area | Click | Say |
|---|-----------|-------|-----|
| 9 | **Goal Brief** tab | Click **Start brief** | "Goal Brief guides you through scoping the problem before generating anything." |
| 10 | **Memory** tab | Scroll through the Lessons list | "Every run produces lessons. These feed back into the retrieval graph on the next run." |
| 11 | **Settings / Health** tab | Open the **Advanced** disclosure → point at **Cooling Brain** toggle | "This is the Memory Temperature toggle — it gates retrieval. It's OFF by default; you enable it deliberately." |
| 12 | **Dream** tab | Show the queue panel only — do not click Start | "The overnight queue lets you schedule a batch of Dream items. Nothing runs until you explicitly start it." |

**Total time:** ~5 minutes.

---

## Fallback (if live analysis is slow)

If the live Run in stop 2 takes too long during the demo:

1. **Pre-load a session.** Open the app, load a previously completed session from the sidebar. Skip stop 2 entirely — the graph, patch, and benchmark results are all already populated.
2. **Benchmark results are cached.** The Benchmarks tab shows the last run result without re-running. Stop 6 always works without a new run.
3. **Evidence index is static.** The evidence index opened in stop 7 is a static file written by the last `build_presentation_evidence` call. It loads instantly.

---

## Screenshot Checklist

Prepare these screenshots before the demo. Each one covers a key demo stop.

- [ ] **Chat/Patch primary row** — both "Generate Patch" and "Apply / Review Patch" buttons visible; "More actions" disclosure closed.
- [ ] **Graph — clean graph** — at least one rendered graph with nodes and edges; zoom controls visible.
- [ ] **Graph — evidence spread** — Scope Spread output panel open and showing spread data.
- [ ] **Benchmarks — runner with options collapsed** — "Run all" and "Run selected" visible; ⚙ Options disclosure closed (default state).
- [ ] **Benchmarks — result 32 / 0** — detail panel showing 32 checked, 0 errors.
- [ ] **Memory — Lessons list or Cooling Brain toggle** — either the lessons list with at least one entry, or the Cooling Brain toggle visible inside the Harness Controls panel.
- [ ] **Settings — Harness Controls collapsed** — Advanced disclosure closed, showing only the summary label ("Advanced — Harness Controls, .env, docker-compose").
