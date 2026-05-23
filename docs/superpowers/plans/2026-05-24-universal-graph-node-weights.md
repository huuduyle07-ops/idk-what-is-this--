# Universal Graph Node Weights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared graph node weight model and use it for CONTROL traversal, project-map critical symbols, and Obsidian `AI_READ_FIRST` rankings.

**Architecture:** Add `graph/weights.py` as a derived metrics layer over `ProgramGraph`; it does not mutate graph construction. Consumers call the metrics layer on demand and treat weight as an evidence signal alongside query relevance, risk, snippets, and validation.

**Tech Stack:** Python dataclasses, existing `ProgramGraph` schema, pytest.

---

## File Structure

- Create `graph/weights.py`: owns `NodeWeight`, noise filtering, degree/complexity collection, normalization, and ranked helpers.
- Create `tests/test_graph_weights.py`: unit tests for universal node metrics.
- Create `tests/test_control_graph_weights.py`: tests CONTROL traversal and evidence fields.
- Create `tests/test_project_map_weights.py`: tests project-map critical symbol ranking.
- Create `tests/test_obsidian_graph_weights.py`: tests Obsidian summary ranking.
- Modify `core/control_engine.py`: imports graph metrics, includes `graph_weight` in evidence/score, and ranks DFS neighbors by query relevance plus node weight.
- Modify `graph/project_map.py`: routes `compute_symbol_hotspots()` through universal node weights.
- Modify `graph/obsidian_exporter.py`: routes `AI_READ_FIRST` through universal node weights.

---

### Task 1: Universal Graph Metrics Module

**Files:**
- Create: `graph/weights.py`
- Create: `tests/test_graph_weights.py`

- [ ] **Step 1: Write the failing graph-weight tests**

Create `tests/test_graph_weights.py`:

```python
from graph.schema import ProgramGraph
from graph.weights import compute_node_weights, rank_nodes_by_weight


def build_weighted_graph() -> ProgramGraph:
    graph = ProgramGraph()
    graph.add_node("core/a.py", "file")
    graph.add_node("core/b.py", "file")
    graph.add_node("core/c.py", "file")
    graph.add_node("core/a.py::main", "function")
    graph.add_node("core/b.py::helper", "function")
    graph.add_node("core/c.py::utility", "function")
    graph.add_node("call::helper", "call")
    graph.add_node("core/a.py::main::expr::1", "expression")

    graph.add_edge("core/a.py", "core/b.py", "imports")
    graph.add_edge("core/a.py", "core/a.py::main", "contains")
    graph.add_edge("core/b.py", "core/b.py::helper", "contains")
    graph.add_edge("core/c.py", "core/c.py::utility", "contains")
    graph.add_edge("core/a.py::main", "core/b.py::helper", "resolved_call")
    graph.add_edge("core/c.py::utility", "core/b.py::helper", "resolved_call")
    graph.add_edge("core/a.py::main", "core/c.py::utility", "resolved_call")
    graph.add_edge("core/a.py::main", "core/a.py::main::expr::1", "executes")
    graph.add_edge("core/a.py::main", "call::helper", "calls")
    return graph


def test_compute_node_weights_excludes_noise_by_default():
    graph = build_weighted_graph()

    metrics = compute_node_weights(graph)

    assert "call::helper" not in metrics
    assert "core/a.py::main::expr::1" not in metrics
    assert metrics["core/b.py::helper"].in_degree == 2
    assert metrics["core/a.py::main"].out_degree == 2
    assert metrics["core/a.py::main"].complexity == 1
    assert metrics["core/b.py::helper"].weight > metrics["core/a.py"].weight
    assert "in_degree=2" in metrics["core/b.py::helper"].reasons


def test_rank_nodes_by_weight_orders_highest_weight_first():
    graph = build_weighted_graph()

    ranked = rank_nodes_by_weight(graph, limit=3)

    assert [item.node_id for item in ranked] == [
        "core/b.py::helper",
        "core/a.py::main",
        "core/b.py",
    ]
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
pytest tests/test_graph_weights.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graph.weights'`.

- [ ] **Step 3: Add the universal metrics implementation**

Create `graph/weights.py`:

```python
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable


TYPE_NODES = {
    "class",
    "struct",
    "interface",
    "type",
    "enum",
    "trait",
    "object",
    "record",
}


@dataclass(frozen=True)
class NodeWeight:
    node_id: str
    node_type: str
    in_degree: int = 0
    out_degree: int = 0
    complexity: int = 0
    weight: float = 0.0
    reasons: list[str] = field(default_factory=list)


def is_noise_node(node_id: str, node_type: str) -> bool:
    return (
        node_type in {"call", "expression"}
        or node_id.startswith("call::")
        or "::expr::" in node_id
    )


def compute_node_weights(
    graph,
    *,
    alpha: float = 2.0,
    beta: float = 1.0,
    gamma: float = 0.5,
    include_noise: bool = False,
) -> dict[str, NodeWeight]:
    if not getattr(graph, "nodes", None):
        return {}

    included = {
        node_id: node
        for node_id, node in graph.nodes.items()
        if include_noise or not is_noise_node(node_id, getattr(node, "type", ""))
    }
    if not included:
        return {}

    incoming: dict[str, int] = defaultdict(int)
    outgoing: dict[str, int] = defaultdict(int)
    contained: dict[str, int] = defaultdict(int)
    executed: dict[str, int] = defaultdict(int)

    for edge in getattr(graph, "edges", []):
        source = edge.source
        target = edge.target
        edge_type = edge.type

        if edge_type in {"resolved_call", "imports"}:
            if source in included:
                outgoing[source] += 1
            if target in included:
                incoming[target] += 1
        elif edge_type == "contains":
            if source in included and target in included:
                contained[source] += 1
        elif edge_type == "executes":
            if source in included:
                executed[source] += 1

    raw: dict[str, tuple[int, int, int]] = {}
    for node_id, node in included.items():
        node_type = getattr(node, "type", "")
        in_degree = incoming[node_id]
        out_degree = outgoing[node_id]
        complexity = 0

        if node_type == "function":
            complexity = executed[node_id]
        elif node_type == "file":
            complexity = contained[node_id]
        elif node_type in TYPE_NODES:
            out_degree += contained[node_id]
            complexity = contained[node_id]

        raw[node_id] = (in_degree, out_degree, complexity)

    max_in = max((value[0] for value in raw.values()), default=0)
    max_out = max((value[1] for value in raw.values()), default=0)
    max_complexity = max((value[2] for value in raw.values()), default=0)

    def normalize(value: int, max_value: int) -> float:
        if max_value <= 0:
            return 0.0
        return value / max_value

    metrics: dict[str, NodeWeight] = {}
    for node_id, node in included.items():
        in_degree, out_degree, complexity = raw[node_id]
        weight = (
            alpha * normalize(in_degree, max_in)
            + beta * normalize(out_degree, max_out)
            + gamma * normalize(complexity, max_complexity)
        )
        reasons = _build_reasons(in_degree, out_degree, complexity)
        metrics[node_id] = NodeWeight(
            node_id=node_id,
            node_type=getattr(node, "type", ""),
            in_degree=in_degree,
            out_degree=out_degree,
            complexity=complexity,
            weight=round(weight, 4),
            reasons=reasons,
        )

    return metrics


def get_node_weight(metrics: dict[str, NodeWeight], node_id: str) -> float:
    metric = metrics.get(node_id)
    if not metric:
        return 0.0
    return metric.weight


def rank_nodes_by_weight(
    graph,
    *,
    limit: int = 10,
    include_noise: bool = False,
    node_types: Iterable[str] | None = None,
) -> list[NodeWeight]:
    allowed_types = set(node_types or [])
    metrics = compute_node_weights(graph, include_noise=include_noise)
    ranked = [
        metric
        for metric in metrics.values()
        if not allowed_types or metric.node_type in allowed_types
    ]
    ranked.sort(key=lambda item: (-item.weight, item.node_id))
    return ranked[:limit]


def _build_reasons(in_degree: int, out_degree: int, complexity: int) -> list[str]:
    reasons: list[str] = []
    if in_degree:
        reasons.append(f"in_degree={in_degree}")
    if out_degree:
        reasons.append(f"out_degree={out_degree}")
    if complexity:
        reasons.append(f"complexity={complexity}")
    if not reasons:
        reasons.append("isolated_or_unresolved")
    return reasons
```

- [ ] **Step 4: Run graph-weight tests and verify they pass**

Run:

```bash
pytest tests/test_graph_weights.py -v
```

Expected: PASS, `2 passed`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add graph/weights.py tests/test_graph_weights.py
git commit -m "feat(graph): add universal node weights"
```

Expected: commit succeeds and includes only `graph/weights.py` plus `tests/test_graph_weights.py`.

---

### Task 2: CONTROL DFS Uses Universal Weight

**Files:**
- Modify: `core/control_engine.py`
- Create: `tests/test_control_graph_weights.py`

- [ ] **Step 1: Write the failing CONTROL traversal tests**

Create `tests/test_control_graph_weights.py`:

```python
from core import control_engine
from graph.schema import ProgramGraph


def build_control_graph() -> ProgramGraph:
    graph = ProgramGraph()
    graph.add_node("core/start.py::start", "function")
    graph.add_node("core/high.py::high", "function")
    graph.add_node("core/low.py::low", "function")
    graph.add_node("core/other.py::caller", "function")
    graph.add_edge("core/start.py::start", "core/high.py::high", "resolved_call")
    graph.add_edge("core/start.py::start", "core/low.py::low", "resolved_call")
    graph.add_edge("core/other.py::caller", "core/high.py::high", "resolved_call")
    return graph


def test_control_dfs_ranks_tied_neighbors_by_graph_weight(monkeypatch):
    graph = build_control_graph()
    monkeypatch.setattr(
        control_engine,
        "analyze_symbol_risk",
        lambda graph, symbol: {"risk_level": "low", "risk_score": 0},
    )

    evidence = control_engine.control_dfs_v2(
        graph,
        ["core/start.py::start"],
        query="",
        max_depth=1,
        max_nodes=5,
        neighbor_limit=2,
    )

    positions = {item["symbol"]: index for index, item in enumerate(evidence)}
    high = next(item for item in evidence if item["symbol"] == "core/high.py::high")
    low = next(item for item in evidence if item["symbol"] == "core/low.py::low")

    assert high["graph_weight"] > low["graph_weight"]
    assert high["score"] > low["score"]
    assert positions["core/high.py::high"] < positions["core/low.py::low"]


def test_control_context_prints_graph_weight():
    result = {
        "query": "why does high fail?",
        "repo_path": ".",
        "entry_nodes": ["core/start.py::start"],
        "top_hypothesis": None,
        "hypotheses": [],
        "evidence": [
            {
                "symbol": "core/high.py::high",
                "depth": 1,
                "score": 4.0,
                "graph_weight": 2.0,
                "risk": {"risk_level": "low", "risk_score": 0},
                "called_by": ["core/start.py::start"],
                "calls": [],
                "impact": [],
            }
        ],
        "execution_trace": "",
        "phantom_limb": {},
        "control_rules": [],
    }

    text = control_engine.format_control_context(result)

    assert "- graph_weight: 2.00" in text
```

- [ ] **Step 2: Run the CONTROL tests and verify they fail**

Run:

```bash
pytest tests/test_control_graph_weights.py -v
```

Expected: FAIL because `graph_weight` is missing from evidence and formatted context.

- [ ] **Step 3: Import graph weights in CONTROL**

Modify the imports near the top of `core/control_engine.py`:

```python
from graph.builder import build_graph_from_repo
from graph.project_map import load_project_map
from graph.query import explain_symbol, impact_analysis
from graph.weights import NodeWeight, compute_node_weights, get_node_weight
```

- [ ] **Step 4: Update CONTROL node scoring**

Replace `score_control_node()` in `core/control_engine.py` with:

```python
def score_control_node(item: dict) -> float:
    risk = item.get("risk", {})
    risk_level = risk.get("risk_level", "low")
    risk_score = risk.get("risk_score", 0)

    level_bonus = {
        "high": 5,
        "medium": 3,
        "low": 1,
    }.get(risk_level, 0)

    return (
        len(item.get("called_by", [])) * 2
        + len(item.get("calls", []))
        + len(item.get("impact", [])) * 2
        + risk_score
        + level_bonus
        + item.get("query_bonus", 0) * 2
        + item.get("graph_weight", 0)
        - item.get("depth", 0) * 0.5
    )
```

- [ ] **Step 5: Update CONTROL DFS traversal**

Replace `control_dfs_v2()` in `core/control_engine.py` with:

```python
def control_dfs_v2(
    graph,
    entry_nodes: list[str],
    query: str = "",
    max_depth: int = 2,
    max_nodes: int = 20,
    neighbor_limit: int = 3,
    node_metrics: dict[str, NodeWeight] | None = None,
) -> list[dict]:
    visited = set()
    evidence: list[dict] = []
    words = query_words(query)
    metrics = node_metrics if node_metrics is not None else compute_node_weights(graph)

    def neighbor_score(node_id: str) -> float:
        return relevance_bonus(node_id, words) * 2 + get_node_weight(metrics, node_id)

    def dfs(symbol: str, depth: int):
        if depth > max_depth:
            return
        if symbol in visited:
            return
        if len(evidence) >= max_nodes:
            return

        visited.add(symbol)

        info = explain_symbol(graph, symbol)
        impact = impact_analysis(graph, symbol)
        risk = analyze_symbol_risk(graph, symbol)

        item = {
            "symbol": symbol,
            "depth": depth,
            "called_by": info.get("called_by", []),
            "calls": info.get("calls", []),
            "impact": impact,
            "risk": risk,
            "query_bonus": relevance_bonus(symbol, words),
            "graph_weight": get_node_weight(metrics, symbol),
        }
        item["score"] = score_control_node(item)
        evidence.append(item)

        neighbors = []
        neighbors.extend(info.get("called_by", []))
        neighbors.extend(info.get("calls", []))

        ranked_neighbors = sorted(
            set(neighbors),
            key=lambda n: (-neighbor_score(n), n),
        )[:neighbor_limit]

        for n in ranked_neighbors:
            dfs(n, depth + 1)

    for node in entry_nodes:
        dfs(node, 0)

    evidence.sort(key=lambda x: (-x.get("score", 0), x.get("symbol", "")))
    return evidence[:max_nodes]
```

- [ ] **Step 6: Print graph weight in formatted CONTROL context**

In `format_control_context()`, inside the `"## Graph Evidence"` loop, change this block:

```python
        lines.append(f"- depth: {item['depth']}")
        lines.append(f"- score: {item.get('score', 0):.2f}")
        lines.append(f"- risk: {risk.get('risk_level')} ({risk.get('risk_score')})")
```

to:

```python
        lines.append(f"- depth: {item['depth']}")
        lines.append(f"- score: {item.get('score', 0):.2f}")
        lines.append(f"- graph_weight: {item.get('graph_weight', 0):.2f}")
        lines.append(f"- risk: {risk.get('risk_level')} ({risk.get('risk_score')})")
```

- [ ] **Step 7: Run CONTROL tests and verify they pass**

Run:

```bash
pytest tests/test_control_graph_weights.py -v
```

Expected: PASS, `2 passed`.

- [ ] **Step 8: Run nearby CONTROL regression tests**

Run:

```bash
pytest tests/test_control_fallback_profiles.py tests/test_control_identity_prompt.py -v
```

Expected: PASS for both files.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add core/control_engine.py tests/test_control_graph_weights.py
git commit -m "feat(control): rank dfs with graph weights"
```

Expected: commit succeeds and includes only the CONTROL changes and CONTROL weight tests.

---

### Task 3: Project Map Uses Universal Critical Ranking

**Files:**
- Modify: `graph/project_map.py`
- Create: `tests/test_project_map_weights.py`

- [ ] **Step 1: Write the failing project-map ranking test**

Create `tests/test_project_map_weights.py`:

```python
from graph.project_map import compute_symbol_hotspots
from graph.schema import ProgramGraph


def test_compute_symbol_hotspots_uses_universal_node_weights():
    graph = ProgramGraph()
    graph.add_node("core/start.py::start", "function")
    graph.add_node("core/z_high.py::high", "function")
    graph.add_node("core/a_low.py::low", "function")
    graph.add_node("core/down1.py::down1", "function")
    graph.add_node("core/down2.py::down2", "function")
    graph.add_node("core/z_high.py::high::expr::1", "expression")
    graph.add_edge("core/start.py::start", "core/z_high.py::high", "resolved_call")
    graph.add_edge("core/start.py::start", "core/a_low.py::low", "resolved_call")
    graph.add_edge("core/z_high.py::high", "core/down1.py::down1", "resolved_call")
    graph.add_edge("core/z_high.py::high", "core/down2.py::down2", "resolved_call")
    graph.add_edge("core/z_high.py::high", "core/z_high.py::high::expr::1", "executes")

    ranked = compute_symbol_hotspots(graph)

    assert ranked[0][0] == "core/z_high.py::high"
    assert ranked[0][1] > ranked[-1][1]
```

- [ ] **Step 2: Run the project-map test and verify it fails against the old local formula**

Run:

```bash
pytest tests/test_project_map_weights.py -v
```

Expected: FAIL because the old local formula ties `core/z_high.py::high` with `core/a_low.py::low` on incoming degree and sorts `core/a_low.py::low` first, while universal weight should let `core/z_high.py::high` win on out-degree plus complexity.

- [ ] **Step 3: Import the universal ranking helper**

Modify imports near the top of `graph/project_map.py`:

```python
from graph.compressor import compress_to_modules
from graph.weights import rank_nodes_by_weight
from config import get_agent_dir, BASE_DIR
```

- [ ] **Step 4: Replace local critical-symbol scoring**

Replace `compute_symbol_hotspots()` in `graph/project_map.py` with:

```python
def compute_symbol_hotspots(graph):
    symbol_types = {
        "function",
        "class",
        "struct",
        "interface",
        "type",
        "enum",
        "trait",
        "object",
        "record",
    }
    ranked = rank_nodes_by_weight(graph, limit=10, node_types=symbol_types)
    return [(metric.node_id, metric.weight) for metric in ranked]
```

- [ ] **Step 5: Run project-map test and verify it passes**

Run:

```bash
pytest tests/test_project_map_weights.py -v
```

Expected: PASS, `1 passed`.

- [ ] **Step 6: Run project-map-adjacent graph tests**

Run:

```bash
pytest tests/test_project_map_weights.py tests/test_graph_weights.py -v
```

Expected: PASS for both files.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add graph/project_map.py tests/test_project_map_weights.py
git commit -m "feat(graph): use node weights for project map hotspots"
```

Expected: commit succeeds and includes only project-map ranking changes and tests.

---

### Task 4: Obsidian AI_READ_FIRST Uses Universal Weight

**Files:**
- Modify: `graph/obsidian_exporter.py`
- Create: `tests/test_obsidian_graph_weights.py`

- [ ] **Step 1: Write the failing Obsidian summary test**

Create `tests/test_obsidian_graph_weights.py`:

```python
from graph.obsidian_exporter import export_graph_to_obsidian
from graph.schema import ProgramGraph


def test_obsidian_ai_read_first_uses_universal_node_weights(tmp_path):
    graph = ProgramGraph()
    graph.add_node("core/start.py::start", "function")
    graph.add_node("core/a_high.py::high", "function")
    graph.add_node("core/z_low.py::low", "function")
    graph.add_node("core/a_high.py::high::expr::1", "expression")
    graph.add_node("call::high", "call")
    graph.add_edge("core/start.py::start", "core/a_high.py::high", "resolved_call")
    graph.add_edge("core/start.py::start", "core/z_low.py::low", "resolved_call")
    graph.add_edge("core/a_high.py::high", "core/a_high.py::high::expr::1", "executes")
    graph.add_edge("core/start.py::start", "call::high", "calls")

    export_graph_to_obsidian(graph, str(tmp_path))
    summary = (tmp_path / "GRAPH_SUMMARY.md").read_text(encoding="utf-8")

    first_ranked_line = next(
        line for line in summary.splitlines() if line.startswith("- [[")
    )

    assert "core_a_high.py__high" in first_ranked_line
    assert "call__high" not in summary
```

- [ ] **Step 2: Run the Obsidian test and verify it fails against the old summary ranking**

Run:

```bash
pytest tests/test_obsidian_graph_weights.py -v
```

Expected: FAIL because the old summary formula ties `core/a_high.py::high` with `core/z_low.py::low` and reverse tuple sorting places `core/z_low.py::low` first, while universal weight should let `core/a_high.py::high` win on complexity.

- [ ] **Step 3: Import the universal ranking helper**

Modify imports near the top of `graph/obsidian_exporter.py`:

```python
from pathlib import Path
from datetime import datetime
import re

from graph.weights import rank_nodes_by_weight
```

- [ ] **Step 4: Replace Obsidian summary ranking**

Replace `write_summary()` in `graph/obsidian_exporter.py` with:

```python
def write_summary(vault: Path, graph, notes: dict) -> None:
    important = [
        (metric.weight, metric.node_id, notes[metric.node_id])
        for metric in rank_nodes_by_weight(graph, limit=len(notes))
        if metric.node_id in notes and metric.weight > 0
    ][:10]

    lines = [
        "# GRAPH SUMMARY",
        "",
        f"- Time Stamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Total raw nodes: {len(graph.nodes)}",
        f"- Total raw edges: {len(graph.edges)}",
        f"- Exported semantic notes: {len(notes)}",
        "",
        "## AI_READ_FIRST",
        "Read these notes first when analyzing this project:",
        "",
    ]

    for score, node_id, info in important:
        lines.append(f"- [[{sanitize(node_id)}]] score={score:.2f} type={info['type']}")

    lines.append("")
    lines.append("## Rule for small models")
    lines.append("- Start from AI_READ_FIRST.")
    lines.append("- Prefer `resolved_call` relationships over raw `call::` nodes.")
    lines.append("- Ignore expression nodes unless debugging exact execution state.")

    (vault / "GRAPH_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 5: Run Obsidian test and verify it passes**

Run:

```bash
pytest tests/test_obsidian_graph_weights.py -v
```

Expected: PASS, `1 passed`.

- [ ] **Step 6: Run graph export regression tests**

Run:

```bash
pytest tests/test_obsidian_graph_weights.py tests/test_graph_weights.py -v
```

Expected: PASS for both files.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
git add graph/obsidian_exporter.py tests/test_obsidian_graph_weights.py
git commit -m "feat(graph): rank obsidian summary with node weights"
```

Expected: commit succeeds and includes only Obsidian exporter changes and tests.

---

### Task 5: Final Verification And Integration Check

**Files:**
- Review: `graph/weights.py`
- Review: `core/control_engine.py`
- Review: `graph/project_map.py`
- Review: `graph/obsidian_exporter.py`
- Review: `tests/test_graph_weights.py`
- Review: `tests/test_control_graph_weights.py`
- Review: `tests/test_project_map_weights.py`
- Review: `tests/test_obsidian_graph_weights.py`

- [ ] **Step 1: Run the focused weight integration suite**

Run:

```bash
pytest tests/test_graph_weights.py tests/test_control_graph_weights.py tests/test_project_map_weights.py tests/test_obsidian_graph_weights.py -v
```

Expected: PASS for all new weight tests.

- [ ] **Step 2: Run nearby existing regression tests**

Run:

```bash
pytest tests/test_control_fallback_profiles.py tests/test_control_identity_prompt.py tests/test_help_route.py -v
```

Expected: PASS for all selected existing tests.

- [ ] **Step 3: Inspect the final diff**

Run:

```bash
git diff --stat HEAD~4..HEAD
```

Expected: output lists the new weights module, four test files, and the three consumer files.

- [ ] **Step 4: Confirm no pruning behavior was added**

Run:

```bash
rg -n "prune|pruning|min_weight|weight_threshold|skip_low" graph core tests
```

Expected: no production implementation of pruning or threshold skipping appears.

- [ ] **Step 5: Confirm no MCTS code was added**

Run:

```bash
rg -n "MCTS|mcts|rollout|reward" graph core tests
```

Expected: no new implementation code for MCTS appears in the changed files.

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short
```

Expected: clean for files touched by this implementation. Existing unrelated untracked files may remain visible and should not be staged.
