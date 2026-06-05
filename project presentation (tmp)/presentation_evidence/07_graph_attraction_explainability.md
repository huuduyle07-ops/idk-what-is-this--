# 07 Graph Attraction / Repulsion Explainability

_No graph attraction/repulsion report was found under `.agent/reports/graph_attraction/` (or `.agent/graph_attraction*.md`)._

This section is explain-only: it visualizes which graph nodes attract attention (query / target / evidence-confidence matches) and which generic utility hubs repel it. A report is produced by the read-only evidence-spread export, which now embeds the Graph Attraction / Repulsion section:

```
POST /graph/evidence_spread/export  (repo_path, query, target_node)
```

> Graph attraction/repulsion is explain-only. It does not change Evidence Spread scoring, CONTROL ranking, Phantom Limb ranking, patch generation, validation, or benchmark scoring.
