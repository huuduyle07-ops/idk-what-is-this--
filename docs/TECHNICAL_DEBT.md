# Technical Debt

## Web Route Boundaries

- `web/app.py` still owns too many responsibilities: session handling, patch
  routes, Dream routes, benchmark routes, lesson routes, proposal routes, graph
  routes, and upload routes.
- Started: patch routes (`/test_patch`, `/apply_patch`, `/test_patch_plan`,
  `/apply_patch_plan`) now live in `web/routes/patch_routes.py`.
- Suggested split, when the next refactor window opens:
  - `web/routes/patch_routes.py`
  - `web/routes/dream_routes.py`
  - `web/routes/benchmark_routes.py`
  - `web/routes/lesson_routes.py`
  - `web/routes/proposal_routes.py`
- Keep behavior-preserving route extraction behind characterization tests; do
  not combine it with product behavior changes.
