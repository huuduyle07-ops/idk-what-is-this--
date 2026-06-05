# 00 Evidence Index

## Generated evidence files

- [01_full_suite_summary.md](01_full_suite_summary.md)
- [02_held_out_suite_summary.md](02_held_out_suite_summary.md)
- [03_held_out_watchlist.md](03_held_out_watchlist.md)
- [04_patch_minimality_experiment.md](04_patch_minimality_experiment.md)
- [05_same_suite_trends.md](05_same_suite_trends.md)
- [06_graph_weight_explainability.md](06_graph_weight_explainability.md)
- [07_graph_attraction_explainability.md](07_graph_attraction_explainability.md)
- [08_memory_temperature_explainability.md](08_memory_temperature_explainability.md)
- [09_memory_temperature_tiebreaker_dogfood.md](09_memory_temperature_tiebreaker_dogfood.md)

## Proof summary

- **Full benchmark suite passed.** See [01_full_suite_summary.md](01_full_suite_summary.md).
- **Held-out suite exists** as a separate evaluation split. See [02_held_out_suite_summary.md](02_held_out_suite_summary.md).
- **Watchlist tracks instability** across repeated held-out runs, observationally only. See [03_held_out_watchlist.md](03_held_out_watchlist.md).
- **Patch minimality measures patch quality beyond pass/fail**, so a green run with bloated patches still surfaces. See [04_patch_minimality_experiment.md](04_patch_minimality_experiment.md).
- **Same-suite trends prevent fake comparisons** from same-total / different-case reports. See [05_same_suite_trends.md](05_same_suite_trends.md).
- **Graph attraction/repulsion is explain-only**, visualizing which nodes pull attention and which generic hubs push it away. See [07_graph_attraction_explainability.md](07_graph_attraction_explainability.md).
- **Memory temperature is explain-only**, showing how warm each loaded lesson/note is (hot/warm/cold/frozen) and *why* it would or would not be surfaced. See [08_memory_temperature_explainability.md](08_memory_temperature_explainability.md).
- **Memory temperature tie-breaker is evidence-only dogfood**, showing what the default-off tie-breaker *would* do to near-equal candidates without changing live retrieval, the CONTROL prompt, or the harness flag (which is off by default). See [09_memory_temperature_tiebreaker_dogfood.md](09_memory_temperature_tiebreaker_dogfood.md).

## Generated at

- 2026-06-05T14:08:02+00:00
