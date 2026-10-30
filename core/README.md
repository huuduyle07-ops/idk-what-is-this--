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
`learning/knowledge_graph.py` owns collection-scoped, user-confirmed concept links
in a learner-owned SQLite store. It reuses `graph.schema.ProgramGraph` for bounded
source/unit/concept views, without reusing code parsing, code weights or global
graph caches. Concept links do not approve sources or establish learner mastery.
`learning/chat_store.py` owns learner conversations, fixed collection scope,
retrieval snapshots and idempotent turn reservations. `learning/chat_retrieval.py`
selects bounded lexical excerpts from that owner's collection and resolves exact
learner-linked concept aliases to their source units. `knowledge_graph.py` also
projects a bounded collection map, with shared-unit associations explicitly
distinguished from causal or prerequisite relationships.
`learning/chat_provider.py` sends bounded history and optional source data to one
configured Ollama or Gemini model; it cannot read files, call coding tools or
grant access to authored answers. See [the chat guide](../docs/architecture/learning-chat-vi.md).
`learning/file_labels.py` owns typed file metadata and pending model suggestions,
separate from immutable source snapshots and per-unit concept links.
`learning/file_label_suggestions.py` samples bounded excerpts and validates model
label proposals before review. See [the file-label guide](../docs/architecture/file-labels-vi.md).
`learning/practice_generation.py` creates bounded question proposals from explicitly
selected lecture units. `learning/practice_store.py` pins source/answer snapshots,
generation reservations, review exposure and deterministic multiple-choice attempts.
It does not infer mastery or execute code. See [the practice guide](../docs/architecture/learning-practice-vi.md).
`learning/flashcard_store.py` derives review cards from completed Practice,
pins their answer/source snapshots and stores self-ratings with fixed due dates.
It calls no model and makes no mastery claim. See [the flashcards guide](../docs/architecture/learning-flashcards-vi.md).
`learning/test_maker.py` owns versioned seeded arithmetic, matrix, diagram and essay templates.
`learning/test_maker_store.py` pins tests and student work, grading objective items
only on explicit submission. Essays require human review and stay outside automatic
points. See [the Test Maker guide](../docs/architecture/learning-test-maker-vi.md).
`learning/source_visuals.py` captures selected source pages/slides or embedded raster
images without OCR or model calls. `learning/source_visual_store.py` pins their
owner-scoped provenance and raster hashes separately from the imported text corpus.
See [the source-visuals guide](../docs/architecture/learning-source-visuals-vi.md).

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
