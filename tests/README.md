# Test organization

Run commands from the repository root with the working Python environment.
The root `conftest.py` continues to apply to all subdirectories.

| Current directory | What it checks |
| --- | --- |
| `runtime/synthetic/` | Synthetic authorization, reflection, lifecycle, source contracts and replay controls: 14 migrated modules |
| `architecture/` | Relocation integrity, unchanged runtime logic and detection of source tampering |
| `learning/` | Teacher sessions, lecture extraction, source snapshots, provenance, owner-scoped library and collection-scoped concept links |
| `integration/test_learning_*.py` | Teacher API, lecture upload boundaries, images/notes and concept navigation through real browser flows |
| Root `test_*.py` | Existing families awaiting extraction; these remain part of default pytest collection |
| `fixtures/`, root maintenance helpers | Shared fixtures and historical reconstruction; retained at stable paths |

```powershell
# Extracted runtime family
python -m pytest tests/runtime/synthetic -q --basetemp=.tmp/pytest-synthetic

# Layout integrity
python -m pytest tests/architecture -q --basetemp=.tmp/pytest-architecture

# Complete collection, including legacy families
python -m pytest --collect-only -q --basetemp=.tmp/pytest-collection

# Complete execution; some existing historical assertions currently fail
python -m pytest -q --basetemp=.tmp/pytest-full
```

Use a different `--basetemp` for concurrent runs. Collection is not execution or
proof that every test passes. No suite is excluded from default collection.

The focused learning-graph suite is `learning/test_knowledge_graph.py`,
`integration/test_learning_knowledge_web.py` and
`integration/test_learning_knowledge_browser.py`. It uses temporary lecture
fixtures and no model calls. Browser tests require Chromium and a loopback test
listener. Symlink confinement cases skip explicitly on hosts without symlink
creation rights; database/sidecar directory and access-error checks still run.

General and lecture-grounded AI chat are checked by `learning/test_chat_store.py`,
`learning/test_chat_provider.py`, `integration/test_learning_chat_web.py` and
`integration/test_learning_chat_browser.py`. Provider transports are mocked in
automated tests; Chromium uses a scripted responder with temporary storage.
Retrieval is covered by `learning/test_chat_retrieval.py`; collection selection,
source snapshots and citation handling by `integration/test_learning_chat_grounding_web.py`
and `integration/test_learning_chat_grounding_browser.py`.
Collection concept maps and their read-only boundary are covered by
`learning/test_learning_concept_map.py`, `integration/test_learning_concept_map_web.py`
and `integration/test_learning_concept_map_browser.py`. Exact source navigation
is exercised by `integration/test_learning_material_links_browser.py`.
Real-model smoke measurements are recorded separately in the chat architecture
guide and must not be reported as part of the automated test count.

File classification is covered by `learning/test_file_labels.py`,
`learning/test_file_label_suggestions.py`, `integration/test_learning_file_labels_web.py`
and `integration/test_learning_file_labels_browser.py`. They check typed metadata,
bounded model proposals, ownership, revision conflicts and explicit human review;
mocked classification does not measure model accuracy.

Source-backed practice is covered by `learning/test_practice_generation.py`,
`learning/test_practice_store.py`, `integration/test_learning_practice_web.py`
and `integration/test_learning_practice_browser.py`. These separate exact source
provenance, answer visibility and assistance-aware attempt records from model
question/answer quality; real-model smoke results are recorded separately.

Flashcards from completed Practice are covered by `learning/test_flashcard_store.py`,
`integration/test_learning_flashcards_web.py` and `integration/test_learning_flashcards_browser.py`.
They check hidden answers, source snapshots, self-rating schedule boundaries,
request replay, ownership and browser recovery without additional model calls.

Mixed-format authored tests are covered by `learning/test_test_maker.py`,
`learning/test_test_maker_store.py`, `integration/test_learning_test_maker_web.py`
and `integration/test_learning_test_maker_browser.py`. These check independent
arithmetic across seeds, bounded numeric parsing, diagram aliases, partial credit,
essay review boundaries, hidden keys, owner isolation and draft/submission recovery.
They do not call models or measure learning outcomes.

Source appearance and provenance are checked by `learning/test_source_visuals.py`,
`learning/test_source_visual_store.py`, `integration/test_learning_source_visuals_web.py`
and `integration/test_learning_source_visuals_browser.py`. Real PDF rendering is
checked separately from mocked renderer/UI recovery. The opt-in PowerPoint smoke
creates only its own hidden temporary presentation; skipped renderer or Windows
permission checks must be reported separately from passed tests.

New tests should follow their component's responsibility. Future families are
`context/`, `coding/`, `workflows/`, `web/`, `benchmarks/` and
`governance/`; create them when extracting actual owners, not as empty scaffolding.
Do not put a behavior regression into an archive merely because its name contains
a phase ID.

Historical checks need a deliberate distinction:

- Behavior and authority checks inspect the current implementation.
- A recorded source hash describes a particular earlier state. The explicit
  relocation bridge can undo only recorded layout edits, validates both hashes,
  and rejects any other code change. It is not used to authorize execution.
- An assertion that a future implementation does not yet exist can become stale
  when that implementation ships. Keep such failures visible until the historical
  contract test is separated from current product regressions.

Old nodeids recorded in reports are historical. Find their current paths in
[source_relocations.json](../docs/architecture/source_relocations.json). Use the
new file path for direct pytest commands; no duplicate wrapper tests are retained.
