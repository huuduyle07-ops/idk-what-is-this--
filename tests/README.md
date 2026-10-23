# Test organization

Run commands from the repository root with the working Python environment.
The root `conftest.py` continues to apply to all subdirectories.

| Current directory | What it checks |
| --- | --- |
| `runtime/synthetic/` | Synthetic authorization, reflection, lifecycle, source contracts and replay controls: 14 migrated modules |
| `architecture/` | Relocation integrity, unchanged runtime logic and detection of source tampering |
| `learning/` | Teacher session behavior, lecture extraction, source snapshots, chunk provenance and owner-scoped material library |
| `integration/test_learning_*.py` | Teacher web API, lecture upload boundaries and browser file/folder import flows |
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
