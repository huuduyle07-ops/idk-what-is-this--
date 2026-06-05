# 06 Graph Weight Explainability

Graph explainer ran automatically when this evidence pack was built.

- Top: 15
- Path prefixes: `core`, `graph`, `patching`
- Include zero-penalty nodes: True
- Hide empty symbols: True

## Top-ranked nodes

| rank | node | kind | weight | topology | complexity | penalty | reasons |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `core/run_artifacts.py::write_text` | function | 2.0283 | 2.0283 | 0.0 | 0.0 | in_degree=158 + out_degree=3 |
| 2 | `core/benchmark_web.py::_write_report` | function | 0.9429 | 0.9429 | 0.0 | 0.0 | in_degree=73 + out_degree=2 |
| 3 | `core/related_notes.py::_as_text` | function | 0.6294 | 0.6294 | 0.0 | 0.0 | in_degree=46 + out_degree=5 |
| 4 | `core/goal_brief.py::_as_text` | function | 0.5949 | 0.5949 | 0.0 | 0.0 | in_degree=47 |
| 5 | `core/goal_brief_autocomplete.py::_as_text` | function | 0.5949 | 0.5949 | 0.0 | 0.0 | in_degree=47 |
| 6 | `core/handoff_composer.py::_as_text` | function | 0.5949 | 0.5949 | 0.0 | 0.0 | in_degree=47 |
| 7 | `core/mode_router.py::_as_text` | function | 0.5949 | 0.5949 | 0.0 | 0.0 | in_degree=47 |
| 8 | `core/review_pack_generator.py::_as_text` | function | 0.5949 | 0.5949 | 0.0 | 0.0 | in_degree=47 |
| 9 | `graph/schema.py::ProgramGraph` | class | 0.5316 | 0.5316 | 0.0 | 0.0 | in_degree=42 |
| 10 | `core/experiments.py::<top-level>` | function | 0.5189 | 0.5189 | 0.0 | 0.0 | out_degree=55 |
| 11 | `core/replay_recorder.py::create_replay_bundle` | function | 0.4964 | 0.4964 | 0.0 | 0.0 | in_degree=34 + out_degree=7 |
| 12 | `core/goal_brief.py::<top-level>` | function | 0.4717 | 0.4717 | 0.0 | 0.0 | out_degree=50 |
| 13 | `core/explainability_dogfood.py::<top-level>` | function | 0.4528 | 0.4528 | 0.0 | 0.0 | out_degree=48 |
| 14 | `graph/schema.py::add_node` | function | 0.4272 | 0.4272 | 0.0 | 0.0 | in_degree=33 + out_degree=1 |
| 15 | `core/memory_temperature_dogfood.py::<top-level>` | function | 0.3962 | 0.3962 | 0.0 | 0.0 | out_degree=42 |

> Each row shows *why* the weighted graph promoted a node:
> topology (in/out degree), complexity, and failure penalty
> contributions. The same data is also available on the CLI:

```
python scripts\explain_graph_weights.py --repo-path . --top 15 --include-zero-penalty --path-prefix core --path-prefix graph --path-prefix patching --hide-empty-symbols
```
