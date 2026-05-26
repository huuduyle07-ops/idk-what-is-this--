# Presentation Script — AI-Powered Code Analysis & Auto-Patching Agent
> Spoken script for each slide. Estimated total time: ~15 minutes.
> Narrative thread: We built the graph system → The benchmark exposed weaknesses → We improved the backend → The system stayed at 31/31 → We measured cost tradeoffs honestly.

---

## Slide 1 — Title

"This project is a code analysis and auto-patching agent. It takes a repository as input and tries to find bugs and produce validated patch proposals, while keeping risky actions behind evidence and review gates.

Although the project uses AI, the core reasoning layer is based on classical data structures and algorithms: directed graphs, DFS traversal, hash-based lookup tables, visited sets, weighted ranking, and bounded search.

The system does not just patch code.
It collects goals, creates evidence, validates changes, stores lessons safely, and prevents unrelated project memory from leaking into the current repo.

The design choice that drives everything else is treating code as a graph, not text. I'll explain what that buys us and where it falls short."

---

## Slide 2 — Project Overview

"The system does four things. It parses a repository into a directed multigraph. It runs a weighted DFS traversal to find high-risk symbols. It generates and scores patch candidates. And it checks each patch against the codebase's style fingerprint before applying it.

Those four steps exist because the earlier version — which worked on flat file text — kept producing patches that were syntactically correct but structurally wrong. It didn't know that the function it was patching had 12 callers. The graph model was added specifically to fix that."

---

## Slide 3 — Core Data Structure: ProgramGraph

"The graph has three primitives. A GraphNode has an ID, a type — file, function, class, expression, or call — a label, and a metadata dictionary. A GraphEdge connects two nodes with a typed relationship: imports, contains, calls, or resolved_call. ProgramGraph is the container.

**Hash map / dictionary** is the data structure behind every node's metadata field. Every attribute the system stores per node — weight, penalty, complexity, source path — goes into that dict and is retrieved in O(1). The same structure backs benchmark reports (stored as JSON dicts keyed by case name) and lesson records (keyed by source_key). source_key duplicate checking also relies on dictionary lookup: before writing a new lesson, the system checks whether that key already exists in the active/candidate/blocked index. If it does, the entry is skipped rather than duplicated.

Construction is four passes: enumerate files, parse each one with tree-sitter to get an AST, insert nodes and edges, then resolve call edges. That last pass is where we match placeholder call nodes to the actual symbol they refer to. Without it, the graph has no cross-file edges — just a collection of isolated file trees. Call resolution is what makes it a real call graph.

It's also the hardest part to get right, and I'll come back to that."

---

## Slide 4 — DFS Implementation

"There are two DFS implementations.

`walk_from_nodes()` in `core/graph_walker.py` is bidirectional — it goes up to callers and down to callees, depth 5, branching factor 2. At each node it calls `explain_symbol()` to collect context for the LLM prompt. The branching cap is deliberate: without it, a highly connected node sends the traversal in too many directions and the prompt becomes noise.

`trace_path()` in `graph/query.py` enumerates all paths between two nodes up to depth 5. It uses suffix matching, so you can query by symbol name without knowing the full node ID. This is what the impact analysis uses — if you're about to patch `::write_config`, trace_path tells you every call chain that reaches it.

The two strategies are not interchangeable. `walk_from_nodes` is for local context. `trace_path` is for checking propagation. Running only one of them was an early mistake that the benchmark caught."

---

## Slide 5 — CONTROL Engine

"The CONTROL Engine in `core/control_engine.py` runs the repair loop.

Before touching a symbol, it computes a risk score: 1 plus two times the caller count, plus the callee count. Callers are weighted more because they propagate breakage — a function with 10 callers that breaks, breaks 10 things. Callees are downstream.

Score 6 or above is high risk and goes to human review. Score 3 to 5 is medium. Below 3 is low and the system can attempt auto-repair.

`control_dfs_v2()` uses this score combined with the graph node weight to decide traversal order. It then builds a Gemini prompt from the traversal output, receives a repair suggestion, runs `build_patch_candidates()`, scores them, validates the winner, and commits only if validation passes.

The risk gating was added after early runs where the system attempted to auto-patch a function called from 30 places and produced a regression. That's now blocked at score 6."

---

## Slide 6 — Universal Graph Node Weights

"Node weights determine traversal priority.

The formula: alpha times normalized in-degree, plus beta times normalized out-degree, plus gamma times normalized complexity. Alpha is 2.0, beta is 1.0, gamma is 0.5.

In-degree gets the highest coefficient because blast radius is the primary risk signal. Out-degree matters — a node calling many things is a logic hub — but it's secondary. Complexity matters least because a complex function that nobody calls is lower risk than a simple function that everything depends on.

The coefficients were set based on this reasoning, not tuned against data. That's worth being honest about. The explainability CLI we built can print the weight breakdown per node — verified now with actual output — and it confirms the known false positive: `write_text` in `core/run_artifacts.py` ranks first with weight 2.0147 because it has in-degree 86. It is called everywhere as a utility wrapper. High topology score, not architecturally significant. The formula currently can't distinguish 'called everywhere because convenient' from 'called everywhere because central.' That's a known gap.

The full top-15 breakdown (from `python scripts\explain_graph_weights.py --repo-path . --top 15 --path-prefix core --path-prefix graph --path-prefix patching`) shows `graph/schema.py::ProgramGraph` at rank 3 (weight 0.7907, in-degree 34) and `core/control_engine.py` at rank 13 (weight 0.3939, complexity contributing 0.2321). Every row exposes topology, complexity, and penalty separately, so the reason a node ranked highly is always auditable."

---

## Slide 7 — Patch Synthesis Pipeline

"`build_patch_candidates()` generates all strategies. `score_patch()` picks one.

`remove_last_assignment` scores plus 3 — it removes a line that overwrites a value unnecessarily, high confidence. `swap_assignments` and `normalize_return_behavior` score plus 2. `mark_overwrite` scores zero and flags for LLM review without making a change. Any patch containing a TODO gets minus 1.

The scores are heuristic. They were chosen based on observed failure modes in early test runs, not derived from data. In easy and medium benchmark cases, this is sufficient — the strategy space is small enough that greedy selection works. In the hard case we added to the benchmark, two of them required the system to fall back to LLM-guided repair because none of the heuristic strategies applied. The scores didn't fail — they correctly returned no high-confidence candidate, and the fallback path handled it."

---

## Slide 8 — Supporting Systems

"Several supporting systems run alongside the main loop.

**Code DNA**, stored in `.agent/<tag>/code_dna.json`, fingerprints the codebase: indentation style, naming conventions, brace style, average function length. Every generated patch is checked against this fingerprint. Without it, early patches were syntactically valid but stylistically inconsistent — they would have failed code review.

**Set** is the data structure that makes Code DNA and the Patch Safety gate fast. Each style dimension — observed indentation widths, naming patterns, brace positions — is stored as a set of seen values, so membership checks are O(1). The Patch Safety gate's forbidden-file list (`.env`, `.agent`, `.git`, `node_modules`, benchmark validation files) and allowed-extension list are also sets: order doesn't matter, only membership does. The benchmark suite uses set-based fingerprinting to detect duplicate test cases — the suite fingerprint is a frozenset of case IDs, and a new run is only recorded if its fingerprint differs from the previous one.

**Queue** structures the asynchronous side of the system. The Dream queue, the proposal queue, and the background plan queue are all FIFO queues — items enter in arrival order and the system processes them head-first without reordering or skipping. This ordering guarantee is what lets overnight Dream runs and background proposal processing stay decoupled from the main repair loop: the operator queues work, the worker drains it, and nothing interferes with the interactive patch flow running in parallel.

**Agent Memory** is PostgreSQL-backed. Gemini extracts up to 3 engineering notes per session and stores them in three tiers: Engineering Memory, Tooling Context, and User Memory. The limit of 3 notes is intentional — uncapped extraction produced low-quality entries that added noise rather than context.

**Static analysis** runs in two layers. The **Phantom Limb Scanner** applies 10 language-gated rules: missing tearDown, swallowed exceptions, empty catch blocks, missing include guards, unimplemented macros. It covers Python, C#, C++, TypeScript, HTML, Rust, and CSS. The second layer is a **linter adapter**, added recently — not to replace Phantom Limb, but to feed external linter output as capped prompt hints into the CONTROL engine. Phantom Limb catches structural patterns. The linter catches syntactic and stylistic violations. They operate on different signals and the output from both is capped before entering the prompt to avoid context bloat."

---

## Slide 9 — Future Work: MCTS Patch Selection

"The current patch scorer is greedy. It picks the highest-scoring candidate and commits. For single-issue files this is fine. For multi-issue files, it can commit to a locally good patch that blocks a better global solution.

Monte Carlo Tree Search is a candidate replacement. The idea: treat each patch attempt as a node in a search tree. UCB1 selects which branch to explore. Rollout simulates patch quality through the validator. Backpropagation updates win rates. Over enough rollouts, it should find combinations the greedy scorer misses.

This is unvalidated. Before replacing the current scorer, the plan is to run a controlled benchmark comparing MCTS against the existing self-correction loop on the same set of cases. If it doesn't beat greedy on the benchmark, it doesn't ship."

---

## Slide 10 — Conclusion

"Here's the actual development sequence, backed by generated evidence files dated 2026-05-26.

We built the graph system and ran an initial benchmark at 22 cases. It passed 22 out of 22, but the fallback count was 16 — meaning 16 of those 22 cases reached the fallback path rather than the primary repair pipeline. That's not a failure number, but it told us the primary path had coverage gaps.

We identified the gaps: TypeScript import repair and hard nested-dispatch cases had no primary handler. We added both. We also expanded the benchmark to 31 cases — including medium adversarial cases and a hard TypeScript nested-dispatch case.

**Full suite result (report `benchmark_report_1779784439`):** 31 out of 31 passed, zero failures, zero flaky. Fallback count: 12. Average run time: 42.27 seconds. Total tokens: 181,326. Estimated cost per full run: $0.22.

Beyond pass/fail, we ran a **patch minimality experiment** — comparing a baseline pipeline against a variant with the minimality metric enabled. Both scored 31/31. The variant was 5.6 seconds faster per run and used 2 fewer fallbacks. Decision: greenlight. No human review required.

We also maintain a **held-out evaluation split** (`held_out_v1`) — 7 adversarial cases kept completely separate from the main benchmark. These test multi-file root cause tracing, callback dispatch ambiguity, and false-positive suppression (cases where the correct answer is no patch). Latest result: 7 out of 7 passed. Average duration: 50.31 seconds, fallback count: 5. One case — `go_multifile_root_cause` — is on the **watchlist** with a historical failure rate of 0.50 across prior runs; it passed this run. The watchlist is observational only: it flags instability without changing the pass/fail score.

The cost of getting here is real. Every run does full AST parsing, multi-pass graph construction, call edge resolution, node scoring, and patch validation. None of those steps are skipped. That is slow for an interactive tool. It is the tradeoff we made for correctness — the system does not apply a patch it has not validated, and both benchmark splits reflect that with zero regressions.

Performance optimisation is next. But the number we are tracking to justify any change is 31/31 on the main suite and 7/7 on the held-out split — both at the same time."

---

*Total slides: 10 | Estimated delivery time: 12–15 minutes at a comfortable pace*
