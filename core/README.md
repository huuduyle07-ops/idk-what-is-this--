# Core ownership

Organize new code by responsibility. Phase IDs belong in reports and provenance;
they are not the package structure. See the [migration record](../docs/architecture/repository-organization.md).

The first extracted package is **[runtime/synthetic](runtime/synthetic/)**. It owns
synthetic scenario authorization, reflection admission and their lifecycles.
Import its owners explicitly, for example:

```python
from core.runtime.synthetic import synthetic_runtime_authorization
```

Its nine implementations retain their behavior and serialized owner IDs. The
package initializer does not load owners or issue capabilities. There are no
duplicate implementations or aliases at the old module paths.

The **[learning/](learning/)** package owns authored Teacher sessions and local
lecture-material preparation. Its local importer and browser-owner library preserve
source snapshots, page/slide/paragraph provenance and review status; the web upload
adapter lives in `web/routes/learning_material_routes.py`. Existing flat `lesson_*`
modules still own the agent's repair knowledge; they are not learner records.

The remaining flat modules are still active. Their intended boundaries are:

| Responsibility | Current entry points / families | Destination for a later extraction |
| --- | --- | --- |
| Lessons and teaching support | `lesson_*`, `anti_lesson_*`, `lesson_teaching_card.py` | `learning/` |
| Repository understanding | `indexer.py`, `context_*`, `code_parse.py`, `retrieval*`, `repository_*` | `context/` |
| Coding and verification | `candidate_*`, `patch_*`, `defect_*`, `structural_*`, `behavioral_*` | `coding/` |
| Runtime isolation and authority | `runtime_java_*`, `sandbox*`, `synthetic_*` (now extracted) | `runtime/` |
| Workflow coordination | `pipeline.py`, `preflight.py`, `run_lifecycle.py`, `control_engine.py`, Dream owners | `workflows/` |
| Advisory reports and phase bookkeeping | `commander_*`, `model_role_*`, `approval_enforcement_*`, `evidence_quality_*`, registry/picker | `governance/` |

These are extraction boundaries, not claims that the remaining packages already
exist. A report describing an execution plan belongs with advisory reporting;
the owner that actually admits an execution belongs with runtime authority.

Before extracting another family:

1. Inventory direct imports, string imports, source readers and cross-test imports.
2. Check both `tests/fixtures/` and phase preservation files under `docs/roadmap/`.
3. Preserve unrelated working changes; migrate a complete dependency boundary.
4. Compare collected test identities, run affected behavior checks, and keep
   historical failures visible. Do not rewrite old receipts to make them pass.

For the education-first direction, existing repair lesson storage is useful
support. Teacher attempts and source material have their own owners in
`learning/`; neither import success nor a few correct answers establish mastery.
