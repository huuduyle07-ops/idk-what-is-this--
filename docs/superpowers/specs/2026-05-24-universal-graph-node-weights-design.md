# Universal Graph Node Weights Design

## Goal

Add one shared, explainable node-weight model for C.A.T.T.U.S graph reasoning.
The graph already exposes topology signals through call, import, and containment
edges, but importance is currently calculated in several local ways. This design
centralizes those signals so traversal, project maps, Obsidian summaries, and
future offline repair experiments can agree on what a critical node is.

## Non-Goals

- Do not add MCTS to the synchronous web patch flow.
- Do not prune low-weight nodes in the first version.
- Do not make graph construction fail when weights cannot be computed.
- Do not replace query relevance, source snippets, validation, or patch safety.
  Node weight is an evidence signal, not authority.

## Architecture

Create a new universal metrics module, `graph/weights.py`, that computes
derived node metrics for any `ProgramGraph`.

The graph builder remains lightweight. It still creates normal nodes and edges.
Callers opt in to metrics by calling a function such as:

```python
metrics = compute_node_weights(graph)
weight = metrics[node_id].weight
```

Each node metric should include:

- `node_id`
- `node_type`
- `in_degree`
- `out_degree`
- `complexity`
- `weight`
- `reasons`

This derived-on-demand design avoids making graph construction heavier and keeps
the scoring formula easy to evolve.

## Scoring Model

Use a simple weighted formula:

```text
weight = (alpha * normalized_in_degree)
       + (beta * normalized_out_degree)
       + (gamma * normalized_complexity)
```

Default coefficients:

```text
alpha = 2.0
beta = 1.0
gamma = 0.5
```

Topology matters more than complexity. A node imported or called by many other
nodes has high blast radius. A node that calls many other nodes is often an
orchestrator or dense logic point. Complexity adds useful risk signal, but it
should not dominate graph structure.

## Node-Type Rules

Function nodes:

- `in_degree`: incoming `resolved_call` edges.
- `out_degree`: outgoing `resolved_call` edges.
- `complexity`: execution-flow count when available, otherwise a safe fallback.

File nodes:

- `in_degree`: incoming `imports` edges.
- `out_degree`: outgoing `imports` edges.
- `complexity`: number of contained symbols.

Class, type, interface, struct, enum, trait, object, and record nodes:

- `in_degree`: incoming references when present.
- `out_degree`: contained child symbols.
- `complexity`: contained child symbol count.

Noise nodes:

- Normal rankings exclude `call::...` and `::expr::...` nodes.
- Debug/export callers may opt into noise later, but v1 should keep normal
  metrics focused on semantic nodes.

## Data Flow

1. `build_graph_from_repo()` creates the normal `ProgramGraph`.
2. A consumer calls `compute_node_weights(graph)`.
3. The returned metrics map is passed into ranking, traversal, or export code.
4. `core/control_engine.py` uses graph weight in DFS neighbor sorting:

   ```text
   neighbor_score = query_bonus * 2 + node_weight
   ```

5. CONTROL evidence items include `graph_weight` so debug context can explain
   why a node ranked highly.
6. `graph/project_map.py` uses the universal ranking for critical symbols.
7. `graph/obsidian_exporter.py` uses the universal ranking for `AI_READ_FIRST`.
8. Future Dream/MCTS research can reuse the same metric in offline reward
   functions without adding another definition of criticality.

## Existing Consumers To Update

`core/control_engine.py`:

- Update `control_dfs_v2()` to compute or accept node metrics.
- Sort neighbors by query relevance plus node weight.
- Include `graph_weight` in evidence.
- Keep all nodes reachable; no pruning in v1.

`graph/project_map.py`:

- Replace or route `compute_symbol_hotspots()` through universal weights.
- Keep the existing readable "Critical Symbols" section.

`graph/obsidian_exporter.py`:

- Rank `AI_READ_FIRST` using universal weights.
- Continue ignoring noise nodes by default.

`reasoning/reasoning_engine.py`:

- Keep `analyze_symbol_risk()` as patch-risk reasoning.
- Optionally include universal graph weight in risk output later, but do not
  merge risk and weight in v1. Risk answers "is patching this dangerous";
  weight answers "is this node structurally important".

## Error Handling

Metric computation should fail soft.

- Empty graph returns an empty metrics map.
- Missing node metrics default to `0.0` in consumers.
- Missing complexity inputs default to `0`.
- Unexpected edge types are ignored.
- Weight calculation must not block indexing, retrieval, patching, project-map
  generation, or Obsidian export.

## Testing

Add focused tests for:

- Degree and weight calculation on a small hand-built `ProgramGraph`.
- Noise nodes excluded from default metrics.
- CONTROL DFS prioritizes a higher-weight neighbor when query relevance is tied.
- CONTROL evidence includes `graph_weight`.
- Project-map critical symbols use universal ranking.
- Obsidian `AI_READ_FIRST` uses universal ranking.

## Future Work

After v1 has evidence from real usage, add optional pruning behind a config flag.
The first version should only prioritize traversal. Pruning may hide a boring
looking node that contains the actual bug, so it should wait until benchmark
evidence shows it helps.

For MCTS, keep usage offline in Dream or benchmark experiments. Node weight can
contribute to reward design, for example rewarding validated patches in
high-weight files and penalizing regressions in critical nodes, but that belongs
to the later Phase 10 experiment path.
