# Graph Penalty From Lessons Design

## Goal

Add a fourth, history-driven term to the universal node-weight formula in
`graph/weights.py` so CONTROL DFS prioritizes files and symbols that have
failed before.
Failures come from two existing sources already present in this codebase:

1. Blocked lesson records in `.agent/lessons/blocked/*.json`.
2. Failed rows in the Postgres `patch_attempts` table.

The signal lands on file nodes when the source only knows a file, and on
symbol nodes (`<rel_path>::<symbol_name>`) when the source records a specific
symbol. Past failures push DFS toward those nodes first ("here be dragons" —
visit the likely culprit first when patching).

This builds directly on top of
`docs/superpowers/specs/2026-05-24-universal-graph-node-weights-design.md`.
The structural formula stays exactly as designed there; this spec only adds
one penalty term.

## Non-Goals

- Do not create a new `node_penalties` table, JSON cache, or `patch_failures.jsonl`.
  Both sources already exist; we read them at graph-build time.
- Do not migrate lessons to Postgres. Blocked lessons stay as JSON-on-disk.
- Do not add symbol-level penalty for blocked lessons. Blocked lesson records
  only store `changed_files` — no symbol info. Symbol-level penalty is only
  available for the `patch_attempts` source, which records `target_node_name`.
- Do not add an "avoid mode" (negative penalty) in v1. Penalty is additive only.
- Do not add time-based decay in v1. Counts are lifetime totals.
- Do not change `core/control_engine.py`, `graph/project_map.py`, or
  `graph/obsidian_exporter.py` formulas. They all read `NodeWeight.weight`, and
  the penalty rolls into that field — they pick up the new signal for free.

## Architecture

One new module, one modified module, zero changes to consumers:

```
graph/penalty.py          [NEW]
  @dataclass(frozen=True)
  class PenaltyResult:
      penalty_map: dict[str, float]     # node_id -> penalty value
      unmatched_paths: list[str]        # paths/symbols that couldn't be matched

  read_blocked_lesson_counts(graph, agent_dir)       -> tuple[dict[str, int], list[str]]
      # returns (file_node_id -> blocked_count, unmatched_paths)

  read_patch_attempt_counts(graph, project_tag)      -> tuple[dict[str, int], list[str]]
      # returns (node_id -> transient_count, unmatched_paths)
      # node_id is `<rel_path>::<symbol>` when target_node_name is present
      # in the row AND the symbol node exists, else the file rel_path

  build_penalty_map(graph, repo_path)                -> PenaltyResult
      # combines both sources, applies omega coefficients, concatenates
      # unmatched_paths from both reads

graph/weights.py          [MODIFIED]
  compute_node_weights(graph, ..., repo_path=None)
    - when repo_path is provided, internally calls
      graph.penalty.build_penalty_map(graph, repo_path) and applies the result
    - when repo_path is None, behavior is identical to v1 (structural only)
    - adds omega_blocked * blocked_count + omega_transient * transient_count
      to each node's weight (file nodes get both terms; symbol nodes only
      receive the transient term per the routing rules)
    - stores the resulting per-node penalty number on NodeWeight.penalty
    - appends a reason string for explainability

core/control_engine.py    [MINOR: 1-line]
  Pass `repo_path` through to compute_node_weights when it's available in the
  current execution context. control_dfs_v2 itself unchanged — it already sums
  NodeWeight.weight into Neighbor_Score at line 312, and penalty flows through
  via that field.

graph/project_map.py      [MINOR: 1-line]
graph/obsidian_exporter.py [MINOR: 1-line]
  Same pattern: thread repo_path through to compute_node_weights / rank_nodes_by_weight.
```

Constants live in a tiny dedicated module `graph/penalty_constants.py`:

```python
OMEGA_BLOCKED = 5.0       # heavy: lesson that was promoted to blocked bucket
OMEGA_TRANSIENT = 1.0     # light: individual failed patch_attempts row
```

Both `graph/penalty.py` and `graph/weights.py` import from this module.
Keeping the constants out of `weights.py` avoids a circular import (weights →
penalty → would-need-weights for the constants) and gives them a stable home
that doesn't need either consumer to be loaded first.

## Scoring Model

```text
weight = (alpha  * normalized_in_degree)
       + (beta   * normalized_out_degree)
       + (gamma  * normalized_complexity)
       + (omega_blocked   * blocked_count_at_node)
       + (omega_transient * transient_count_at_node)
```

`blocked_count_at_node` is non-zero only on file nodes (blocked lessons have
no symbol info). `transient_count_at_node` may be non-zero on either a file
node or a symbol node, depending on whether `patch_attempts.target_node_name`
was recorded for that row.

Default coefficients (existing): `alpha=2.0`, `beta=1.0`, `gamma=0.5`.
New coefficients: `omega_blocked=5.0`, `omega_transient=1.0`.

The penalty terms are **raw counts, not normalized**. This is deliberate: a
single blocked lesson on a file (+5.0) outweighs the structural maximum
(`alpha + beta + gamma = 3.5`). Files with recorded failure history sort to the
top of any DFS neighbor list. The user calls this the "vung chien su nguy hiem"
philosophy — past pain dominates structural importance.

A file with no failures contributes `0.0` from the penalty terms; its weight is
identical to what the existing universal-weights design produces.

Symbol-level routing for transient failures (`patch_attempts` rows):

- If `target_node_name` is non-NULL AND `<rel_path>::<target_node_name>` exists
  as a node in the graph: penalty lands on that symbol node.
- If `target_node_name` is NULL: penalty rolls up to the file node.
- If `target_node_name` is non-NULL but the symbol node does NOT exist (e.g.,
  the function was renamed or deleted since the patch attempt was recorded):
  the entry is added to `unmatched_paths` and not counted. We do NOT silently
  roll up to the file — that would blur granularity and hide stale data.

This lets DFS get real per-function guidance for the source that has it,
without inventing precision the blocked-lesson source doesn't have.

Container roll-up (a file's penalty automatically flowing down to its
contained symbols, or vice versa) is **not** done. Each node's penalty
reflects only the failures recorded against that node specifically.

## NodeWeight Schema Change

One additive field:

```python
@dataclass(frozen=True)
class NodeWeight:
    node_id: str
    node_type: str
    in_degree: int = 0
    out_degree: int = 0
    complexity: int = 0
    weight: float = 0.0           # all-in (structural + penalty)
    penalty: float = 0.0          # NEW: visible portion contributed by penalty
    reasons: list[str] = field(default_factory=list)
```

- `weight` stays the all-in number. Existing consumers keep working with no
  code change.
- `penalty` is the visible breakdown — `omega_blocked * N_b + omega_transient * N_t`
  for that node. Zero for any node with no failures recorded. File nodes can
  receive contributions from both sources; symbol nodes only ever receive the
  transient contribution.
- `reasons` gains entries like `blocked_lessons=2` and `patch_failures=3` when
  the corresponding counts are non-zero, so debug output can explain why a node
  ranked highly.

## Data Sources

### Blocked lessons

Source: `core.lesson_store.list_lessons(status="blocked")`. Using the existing
API instead of a raw `glob("*.json")` gives us dedup across bucket-crash
edge cases and defensive filtering of corrupted records for free. Storage
backing is the AI project's own `.agent/lessons/blocked/` (org-wide).

Each blocked lesson record has a `candidate` blob containing
`changed_files: list[str]`. For each blocked record, every entry in
`changed_files` increments the `blocked_count` for the matching file node.

A lesson entry contributes nothing (and produces no exception) if:
- `list_lessons` returns nothing (no blocked lessons exist).
- The `candidate.changed_files` field is missing or not a list.
- An individual path entry is not a string.
- A path entry does not resolve to any file node in the current graph after
  normalization + case-insensitive fallback (e.g., a stale lesson referencing
  a renamed or deleted file). Such entries are appended to `unmatched_paths`
  so tests and debug UIs can surface them.

### Failed patch_attempts

Source: `patch_attempts` table in `codex_db`, scoped to the current
`project_tag` (derived via `core.project_tag.build_project_tag(repo_abs)`).

```sql
SELECT target_file,
       target_node_name,
       COUNT(*) AS fail_count
FROM patch_attempts
WHERE project_tag = %s
  AND target_file IS NOT NULL
  AND (
      phase IN ('validation_failed', 'apply_failed', 'dry_run_blocked')
      OR validation_ok IS FALSE
      OR rollback_performed IS TRUE
  )
GROUP BY target_file, target_node_name;
```

A row is counted as a failure if **any** of these is true:
- `phase` indicates a known failure state.
- `validation_ok` is explicitly `false` (NULL does not count — that means the
  attempt never reached validation).
- `rollback_performed` is `true` (the attempt was undone).

The OR semantics overlap on purpose: a single attempt failing in multiple ways
still increments by one (one row, one count), but any single failure signal is
enough to count it.

For each result row, `read_patch_attempt_counts` routes the count as follows:

- `target_node_name` non-NULL and `<rel_path>::<target_node_name>` is a node
  in the graph → count goes to that **symbol node**.
- `target_node_name` is NULL → count goes to the **file node** for `rel_path`.
- `target_node_name` non-NULL but the symbol node is missing → the entry is
  added to `unmatched_paths` (string form: `<rel_path>::<target_node_name>`).
  No fallback to file-level — see Scoring Model for the reasoning.

Multiple result rows for the same file (e.g., one with a symbol, one without)
are handled independently: the file node accumulates only the NULL-symbol
rows; each named symbol accumulates its own rows.

## Path Matching and Project Scoping

This is the gnarly bit. Three normalizations apply to every path before lookup:

1. **Slashes**: backslashes converted to forward slashes (Windows recordings
   often use `\`).
2. **Leading marker stripped**: `./` and `.\` prefixes removed.
3. **Absolute paths**: rebased against the current repo root if and only if
   they fall inside it; otherwise added to `unmatched_paths` (a foreign-repo
   path can't match anything in this graph).

After normalization, lookup proceeds in two stages:

1. **Exact match** against `graph.nodes` keys (file node ids are the
   repo-relative POSIX path itself, verified in `graph/builder.py:49`,
   `graph.add_node(rel, "file", rel)` — no prefix).
2. **Case-insensitive fallback**: if exact match fails, look up the path
   against a case-folded index of file node ids. Windows filesystems are
   case-insensitive, so `src/Foo.py` (recorded by one tool) and `src/foo.py`
   (in the graph) refer to the same file. The case-folded index is built once
   per graph at penalty-computation time, O(n) in number of file nodes. Linux
   builds also enjoy the fallback; collisions (two real files differing only
   in case) are extraordinarily rare and resolve to whichever appears first
   in the index — acceptable for a debug-signal feature.

When a symbol-level lookup is attempted (`<rel_path>::<name>`), only the
**path part** uses the case-insensitive fallback; the symbol name part is
compared case-sensitively (function/class names are case-sensitive in all
languages we index).

If both stages fail, the original (pre-normalization) string is appended to
`unmatched_paths` in the returned `PenaltyResult`. The penalty module never
calls a global logger for this. Callers (tests, a future debug UI) can
inspect the list. In normal execution, an unmatched path simply contributes
nothing to the penalty map — same fail-soft behavior as before, but now
observable when you want it.

Project scoping is enforced two ways:
- Blocked lessons are org-wide on disk, but path matching against the current
  graph's file nodes naturally filters them — a Rust project's lessons can't
  match a Python project's file nodes.
- `patch_attempts` is filtered by `project_tag` at the SQL level. If the
  current repo's tag cannot be determined, no transient counts are loaded.

## Existing Consumers

Each consumer needs a **one-line change** to thread `repo_path` into the
weights call. The DFS / ranking / formatting code inside each consumer is
unchanged — penalty rides in via `NodeWeight.weight`.

- `core/control_engine.py` — pass `repo_path` into `compute_node_weights`
  wherever it's currently called. `control_dfs_v2` itself does not change;
  it already sums `NodeWeight.weight` into `Neighbor_Score = Query_Bonus * 2
  + Weight_node` at line 312, and penalty is inside `weight`.
- `graph/project_map.py` — same pass-through. The Critical Symbols section
  starts surfacing high-penalty files and symbols automatically.
- `graph/obsidian_exporter.py` — same pass-through. `AI_READ_FIRST` ranking
  picks up the new signal for both files and symbols.

Consumers that don't have a `repo_path` in context (e.g., unit tests that
hand-build a `ProgramGraph`) simply omit the argument and get the v1
structural-only behavior — no DB call, no lesson scan, no breakage.

If a consumer wants to display the penalty breakdown separately (e.g., a
debug view), it can read `NodeWeight.penalty` directly.

## Error Handling (Fail-Soft)

The codebase's pattern is "metric computation never blocks the agent". This
design preserves it.

| Condition                                       | Behavior                              |
|-------------------------------------------------|---------------------------------------|
| `<agent_dir>/lessons/blocked/` missing          | `blocked_count = 0` for all files     |
| Individual blocked lesson JSON malformed        | Skip that file; continue              |
| `candidate.changed_files` missing or wrong type | Skip that lesson; continue            |
| `DB_ENABLED=false`                              | `transient_count = 0` for all files   |
| Postgres unreachable or query fails             | `transient_count = 0` for all files   |
| `project_tag` cannot be derived                 | `transient_count = 0` for all files   |
| Path / symbol entry does not match any node     | Append to `unmatched_paths`; contribute 0 |
| Empty graph                                     | Return empty penalty map              |

The penalty module is wrapped so any unexpected exception during source
reading yields an empty per-source map; the structural weight calculation is
never blocked.

## Testing

New test file `tests/test_graph_penalty.py`:

1. **Empty graph** → `build_penalty_map` returns `PenaltyResult({}, [])` and
   makes no DB call.
2. **Blocked-only** — hand-built graph + temp `<agent_dir>/lessons/blocked/`
   with two JSON lessons touching `foo.py`:
   `penalty_map["foo.py"] == 10.0` (2 * OMEGA_BLOCKED), `unmatched_paths == []`.
3. **Transient at file level** — mocked `patch_attempts` rows for `bar.py`
   with `target_node_name = NULL`, 3 rows: `penalty_map["bar.py"] == 3.0`.
4. **Transient at symbol level** — mocked rows for `bar.py` /
   `target_node_name = "do_thing"`, 2 rows; symbol node `bar.py::do_thing`
   exists in graph: `penalty_map["bar.py::do_thing"] == 2.0`,
   `penalty_map.get("bar.py", 0) == 0`.
5. **Mixed routing** — same file gets both: 2 rows NULL + 3 rows for
   `do_thing` + 1 row for `helper`: `penalty_map["bar.py"] == 2.0`,
   `penalty_map["bar.py::do_thing"] == 3.0`,
   `penalty_map["bar.py::helper"] == 1.0`.
6. **Symbol gone** — row references `bar.py::renamed_func` but graph has no
   such symbol: `unmatched_paths` contains `"bar.py::renamed_func"`; no
   silent rollup to file.
7. **Combined sources** — `foo.py` has 1 blocked + 2 transient (NULL symbol):
   `penalty_map["foo.py"] == 5.0 + 2.0 == 7.0`.
8. **DB disabled** — `DB_ENABLED=false`: transient counts all 0; blocked
   still computed correctly; `unmatched_paths` reflects only blocked-side
   misses.
9. **Path normalization** — lesson with `changed_files: ["./foo.py"]`,
   `["foo\\bar.py"]` (Windows backslash), and `"/etc/passwd"` (foreign-repo
   absolute): first two normalize and match; third lands in `unmatched_paths`.
10. **Case-insensitive fallback** — graph has `src/foo.py`; lesson recorded
    `src/Foo.py` (different case): match succeeds via fallback,
    `penalty_map["src/foo.py"] > 0`, `unmatched_paths == []`.
11. **Stale lesson** — lesson touches `removed.py` not in the graph:
    `"removed.py"` appears in `unmatched_paths`; no exception.
12. **Malformed JSON** — one lesson file is invalid JSON; others process
    normally; no exception.

Updates to existing test files (untracked but adjacent to this work):
- `tests/test_graph_weights.py` — new test: file with non-zero penalty has
  `weight == structural + penalty`, `penalty` field populated, reasons list
  includes the new entries.
- `tests/test_control_graph_weights.py` — new tests:
  (a) two file nodes tied on structural weight, one has high penalty; CONTROL
  DFS visits high-penalty neighbor first; `graph_weight` in evidence reflects
  the boost.
  (b) a symbol node with non-zero penalty outranks a sibling symbol with the
  same structural weight — verifies the symbol-level routing reaches DFS.

## Out of Scope (Deliberately)

- **Time-based decay.** Lifetime counts only in v1. Revisit when a single
  node has accumulated 20+ failures and the signal becomes muddy.
- **Penalty capping / sigmoid smoothing.** Constants stay raw and unbounded
  in v1. The `OMEGA_BLOCKED=5.0` choice deliberately dominates structural
  signal (Q5: "history dominates"). If a single node ever accumulates enough
  failures that the linear scaling becomes pathological, switch the formula
  to `min(MAX_PENALTY, omega * count)` — a one-line change.
- **Symbol-level penalty for blocked lessons.** Blocked lesson records only
  store `changed_files`; no symbol info exists in the data. Would require
  extending the lesson schema and re-synthesizing existing lessons.
- **Container roll-up.** A file's penalty does NOT bleed into its contained
  symbols, and a symbol's penalty does NOT bleed into its parent file. Each
  node's penalty is scoped to failures recorded directly against it.
- **Avoid-mode.** Negative penalty for "explore-safe-code" workflows is a
  future feature. Plumbing the sign as a config flag is the natural extension.
- **Pruning low-weight nodes.** Same stance as the universal-weights design:
  not until benchmark data shows it helps.
- **Cache.** A precomputed cache is a real future optimization if graph
  builds start scanning thousands of lesson files. For the codebase's current
  size (handfuls of lessons, handfuls of patch attempts), derive-on-demand
  is fine.
- **Global logger warnings on unmatched paths.** Inspection happens via the
  returned `unmatched_paths` list; the penalty module never calls a logger.
  Avoids dev-console noise from the expected steady-state population of stale
  lessons.

## Future Work

- Once enough data accumulates, calibrate `OMEGA_BLOCKED` and `OMEGA_TRANSIENT`
  against patch-fix success rates. The defaults are a strong-prior guess.
- If the heavy penalty starts to overwhelm legitimate structural signal
  (e.g., every important file accumulates blocked lessons), switch to a
  normalized or capped formulation: `min(MAX_PENALTY, omega * count)` or
  `omega * (blocked + 0.2*transient) / max_count`.
- Extending the lesson record schema to track which symbol within
  `changed_files` was the actual subject of the failure would let
  blocked-lesson penalty also land at symbol granularity (currently only the
  transient source can).
- A repair-mode flag in `control_dfs_v2` could let the operator pick
  prioritize vs. avoid for the same penalty data.
- A small debug UI / CLI command that surfaces `unmatched_paths` would help
  operators spot lesson-store drift (renamed files, deleted symbols) without
  needing to write a test.
