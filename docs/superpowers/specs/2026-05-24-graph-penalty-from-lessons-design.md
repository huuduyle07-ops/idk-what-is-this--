# Graph Penalty From Lessons Design

## Goal

Add a fourth, history-driven term to the universal node-weight formula in
`graph/weights.py` so CONTROL DFS prioritizes files that have failed before.
Failures come from two existing sources already present in this codebase:

1. Blocked lesson records in `.agent/lessons/blocked/*.json`.
2. Failed rows in the Postgres `patch_attempts` table.

The signal lands on file nodes only. Past failures push DFS toward those nodes
first ("here be dragons" — visit the likely culprit first when patching).

This builds directly on top of
`docs/superpowers/specs/2026-05-24-universal-graph-node-weights-design.md`.
The structural formula stays exactly as designed there; this spec only adds
one penalty term.

## Non-Goals

- Do not create a new `node_penalties` table, JSON cache, or `patch_failures.jsonl`.
  Both sources already exist; we read them at graph-build time.
- Do not migrate lessons to Postgres. Blocked lessons stay as JSON-on-disk.
- Do not add symbol-level penalty in v1. `patch_attempts.target_node_name`
  exists and could power this later, but v1 is file-only.
- Do not add an "avoid mode" (negative penalty) in v1. Penalty is additive only.
- Do not add time-based decay in v1. Counts are lifetime totals.
- Do not change `core/control_engine.py`, `graph/project_map.py`, or
  `graph/obsidian_exporter.py` formulas. They all read `NodeWeight.weight`, and
  the penalty rolls into that field — they pick up the new signal for free.

## Architecture

One new module, one modified module, zero changes to consumers:

```
graph/penalty.py          [NEW]
  read_blocked_lesson_counts(graph, agent_dir)       -> dict[file_node_id, int]
  read_patch_attempt_counts(graph, project_tag)      -> dict[file_node_id, int]
  build_penalty_map(graph, repo_path)                -> dict[file_node_id, float]

graph/weights.py          [MODIFIED]
  compute_node_weights(graph, ..., repo_path=None)
    - when repo_path is provided, internally calls
      graph.penalty.build_penalty_map(graph, repo_path) and applies the result
    - when repo_path is None, behavior is identical to v1 (structural only)
    - applies omega_blocked * blocked_count + omega_transient * transient_count
      to each file node's weight, additively after the structural terms
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

Constants at the top of `graph/weights.py`:

```python
OMEGA_BLOCKED = 5.0       # heavy: lesson that was promoted to blocked bucket
OMEGA_TRANSIENT = 1.0     # light: individual failed patch_attempts row
```

## Scoring Model

```text
weight = (alpha  * normalized_in_degree)
       + (beta   * normalized_out_degree)
       + (gamma  * normalized_complexity)
       + (omega_blocked   * blocked_count_at_file)
       + (omega_transient * transient_count_at_file)
```

Default coefficients (existing): `alpha=2.0`, `beta=1.0`, `gamma=0.5`.
New coefficients: `omega_blocked=5.0`, `omega_transient=1.0`.

The penalty terms are **raw counts, not normalized**. This is deliberate: a
single blocked lesson on a file (+5.0) outweighs the structural maximum
(`alpha + beta + gamma = 3.5`). Files with recorded failure history sort to the
top of any DFS neighbor list. The user calls this the "vung chien su nguy hiem"
philosophy — past pain dominates structural importance.

A file with no failures contributes `0.0` from the penalty terms; its weight is
identical to what the existing universal-weights design produces.

The penalty terms apply only to nodes where `node_type == "file"`. Function,
class, and other symbol nodes are unaffected in v1. Container roll-up
(parent file's penalty flowing down to its symbols) is deferred to future work.

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
  for that file. Zero for any non-file node and any file with no failures.
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

A lesson entry is dropped silently if:
- `list_lessons` returns nothing (no blocked lessons exist).
- The `candidate.changed_files` field is missing or not a list.
- An individual path entry is not a string.
- A path entry does not resolve to any file node in the current graph (e.g.,
  a stale lesson referencing a renamed or deleted file).

### Failed patch_attempts

Source: `patch_attempts` table in `codex_db`, scoped to the current
`project_tag` (derived via `core.project_tag.build_project_tag(repo_abs)`).

```sql
SELECT target_file,
       COUNT(*) AS fail_count
FROM patch_attempts
WHERE project_tag = %s
  AND target_file IS NOT NULL
  AND (
      phase IN ('validation_failed', 'apply_failed', 'dry_run_blocked')
      OR validation_ok IS FALSE
      OR rollback_performed IS TRUE
  )
GROUP BY target_file;
```

A row is counted as a failure if **any** of these is true:
- `phase` indicates a known failure state.
- `validation_ok` is explicitly `false` (NULL does not count — that means the
  attempt never reached validation).
- `rollback_performed` is `true` (the attempt was undone).

The OR semantics overlap on purpose: a single attempt failing in multiple ways
still increments by one (one row, one count), but any single failure signal is
enough to count it.

## Path Matching and Project Scoping

This is the gnarly bit. Three normalizations apply to every path before lookup:

1. **Slashes**: backslashes converted to forward slashes (Windows recordings).
2. **Leading marker stripped**: `./` and `.\` prefixes removed.
3. **Absolute paths**: rebased against the current repo root if and only if
   they fall inside it; otherwise dropped (a foreign-repo path can't match
   anything in this graph).

After normalization, the path is looked up directly against the graph's node
keys. File node ids are the repo-relative POSIX path itself (verified in
`graph/builder.py:49`, `graph.add_node(rel, "file", rel)`) — no prefix.

If the normalized path is not a key in `graph.nodes`, the entry is dropped
silently. No warnings, no exceptions. A stale lesson or a `patch_attempts` row
referencing a deleted file simply contributes nothing.

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
  starts surfacing high-penalty files automatically.
- `graph/obsidian_exporter.py` — same pass-through. `AI_READ_FIRST` ranking
  picks up the new signal.

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
| Path entry does not match any graph node        | Drop silently, no warning             |
| Empty graph                                     | Return empty penalty map              |

The penalty module is wrapped so any unexpected exception during source
reading yields an empty per-source map; the structural weight calculation is
never blocked.

## Testing

New test file `tests/test_graph_penalty.py`:

1. **Empty graph** → `build_penalty_map` returns an empty dict and makes no DB call.
2. **Blocked-only** — hand-built graph + temp `<agent_dir>/lessons/blocked/`
   with two JSON lessons touching `foo.py`:
   `penalty[foo.py] == 10.0` (2 * OMEGA_BLOCKED), `weight` includes the bump.
3. **Transient-only** — hand-built graph + mocked `patch_attempts` query
   returning 3 failures on `bar.py`: `penalty[bar.py] == 3.0` (3 * OMEGA_TRANSIENT).
4. **Both sources combine** — `foo.py` has 1 blocked + 2 transient: `penalty == 7.0`.
5. **DB disabled** — `DB_ENABLED=false`: transient counts all 0; blocked still
   computed correctly.
6. **Path normalization** — lesson with `changed_files: ["./foo.py"]`,
   `["foo\\bar.py"]` (Windows), and a path outside the repo: first two match,
   third is dropped silently, no exception.
7. **Stale lesson** — lesson touches `removed.py` not in the graph:
   penalty map has no entry for it, no warning.
8. **Malformed JSON** — one lesson file is invalid JSON; others process normally.

Updates to existing test files (untracked but adjacent to this work):
- `tests/test_graph_weights.py` — new test: file with non-zero penalty has
  `weight == structural + penalty`, `penalty` field populated, reasons list
  includes the new entries.
- `tests/test_control_graph_weights.py` — new test: two file nodes tied on
  structural weight, one has high penalty; CONTROL DFS visits high-penalty
  neighbor first; `graph_weight` in evidence reflects the boost.

## Out of Scope (Deliberately)

- **Time-based decay.** Lifetime counts only in v1. Revisit when a single file
  has accumulated 20+ failures and the signal becomes muddy.
- **Symbol-level penalty.** `patch_attempts.target_node_name` exists; reading
  it would let us penalize specific functions instead of whole files. Trivial
  to add later by extending `read_patch_attempt_counts` to also group by
  `target_node_name` and look up `<rel_path>::<name>` node ids.
- **Avoid-mode.** Negative penalty for "explore-safe-code" workflows is a
  future feature. Plumbing the sign as a config flag is the natural extension.
- **Pruning low-weight nodes.** Same stance as the universal-weights design:
  not until benchmark data shows it helps.
- **Cache.** A precomputed cache is a real future optimization if graph builds
  start scanning thousands of lesson files. For the codebase's current size
  (handfuls of lessons, handfuls of patch attempts), derive-on-demand is fine.

## Future Work

- Once enough data accumulates, calibrate `OMEGA_BLOCKED` and `OMEGA_TRANSIENT`
  against patch-fix success rates. The defaults are a strong-prior guess.
- If the heavy penalty starts to overwhelm legitimate structural signal
  (e.g., every important file accumulates blocked lessons), switch to a
  normalized formulation: `omega * (blocked + 0.2*transient) / max_count`.
- Symbol-level granularity for the transient source is a small extension and
  may matter more than file-level once the project grows.
- A repair-mode flag in `control_dfs_v2` could let the operator pick
  prioritize vs. avoid for the same penalty data.
