# INDENT.RUNTIME.1 — Language Context Transport & Repair Boundary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan is executed **inline, in the same session that wrote it** (not subagent-dispatched) — see "Why inline" below.

**Goal:** Transport the classified file's language from `compute_dna` into `core/code_dna.py::_classify_indent`, and from each T6 behavioral-matrix case into the candidate probe contract that invokes it — without fixing the deliberately-preserved T6 indentation-classifier defect, and without widening `safe_minimal`, authoring, validation, or authority.

**Architecture:** `_classify_indent` gains one keyword-only `language: str | None = None` parameter that its current (buggy) body ignores. `compute_dna` derives each file's language from the repo's existing `config.LANGUAGE_MAP` (no second suffix→language map) and passes it through. `core/code_dna.py` gains a module-level import of the existing `core.indentation_observation.{observe_source_indentation, assess_indentation_observation}` public API as an unused-by-production "repair seam" — available to a future patch, not activated now. The T6 probe contract (`build_python_function_probe`) gains a generic, non-indentation-specific `kwargs` parameter; the four indentation-case construction sites (case A in `core/defect_probe.py`, case C in `core/paired_defect_probe.py`, cases B/D/E/F/G/H in `core/behavioral_matrix.py`) pass `kwargs={"language": <the case's own already-known language constant>}`. The defect-probe worker already forwards kwargs generically (`function(*args, **kwargs)`) — zero changes needed there. A test-only candidate (never shipped) proves the new contract can express a correct 8-case implementation, and is run through the *real* `patch_gates._enforce_safe_minimal` to honestly determine — not assume — whether that repair is currently admissible.

**Tech Stack:** Python 3.14 stdlib (`tokenize`, `ast`, `hashlib`, `dataclasses`), pytest.

**Spec:** The phase spec is the task prompt that opened this session (INDENT.RUNTIME.1, 48 numbered sections + a 50-item final report + explicit yes/no questions). It is not a separate file; treat this plan's Global Constraints as its distillation and re-read the original prompt for exact wording when in doubt.

**Prior context this plan depends on (read, not re-derived):**
- `core/indentation_observation.py` (INDENT.SEMANTICS.1) — the one semantic authority: `observe_source_indentation(text, *, language)`, `assess_indentation_observation(observation)`, constants `LANGUAGE_PYTHON="python"`, `LANGUAGE_UNKNOWN="unknown"`.
- `docs/designs/2026-09-11-language-aware-indentation-observation-contract.md` — measured facts (§16 retrieval ranking history, §20 "recommended next production phase" = this phase).
- `tests/test_indent_semantics1.py` — the 8-case matrix (`_t6_cases()`), the five pinned historical contract-identity hashes (`LIVE5_CONTRACT_SEMANTICS`), the frozen-boundary test (`FROZEN_FIXTURE`), the reversal-chain test (`LATER_RECEIPTS[0] == REVERSAL_FIXTURE`).
- `tests/_harness_maintenance.py` — `LATER_RECEIPTS` tuple (newest first) and `before_later_receipts`/`before_harness_remediation`, the generic mechanism every older frozen-boundary test already routes through.
- `tests/fixtures/indent_semantics1_frozen_boundaries.json` — pins 40 whole files (sha256) + 2 function-AST digests (`core/code_dna.py::_classify_indent`, `::compute_dna`), both of which this phase *must* change (that's the point of the phase).
- `tests/fixtures/indent_semantics1_reversal.json` — the reversal-receipt schema precedent (`schema_version`, `phase_id`, `reason`, `chain`, `new_module`, `reversals: [{path, pre_sha256, post_sha256, hunks:[{pre,post}], top_level_definitions_pre/post, added/removed/changed_definitions, added/changed_assignments}]`).

## Global Constraints

- Frozen prerequisites (do not alter their shipped behavior): INDENT.SEMANTICS.1, DEFECT.PROBE.LIVE.1–5, DEFECT.FACT.LIVE.1, CANDIDATE.VERIFY.LIVE.1, PATCH.MINIMAL.LIVE.1/.2, PATCH.AUTHOR.LIVE.1/.2, ANSWER.COHERENCE.LIVE.1, CONTROL.LOCALIZE.LIVE.2, RETRIEVE.LIVE.4, EXEC.POLICY/APPROVAL/AUTH.LIVE.1.
- Never `git stash` / `git reset` / `git clean`. Never revert or normalize unrelated concurrent (Track B / UI-security) changes.
- `_classify_indent`'s current buggy body must keep producing the *same wrong* answers on the known T6 cases (A, B, E in the 8-case matrix) after this phase. If it becomes correct, that is a scope violation to be reverted (only the accidental fix, not concurrent work).
- `language` is keyword-only on `_classify_indent`; omitting it must behave exactly as before. No path/suffix/repo/candidate-fingerprint parameter is ever added to `_classify_indent`.
- No new suffix→language map: reuse `config.LANGUAGE_MAP` (already the authoritative source; `.py`→`"python"`, `.go`→`"go"`, etc., matching `core.indentation_observation.LANGUAGE_PYTHON` and `core.behavioral_matrix.INPUT_LANGUAGE_GO` spellings exactly).
- No new probe/worker primitive: `core/defect_probe_worker.py::_run_python_function` already does `function(*args, **kwargs)` from `structured_input["kwargs"]` — zero changes to that file.
- No naming that leaks the T6 solution (forbidden: `structural_indent_fix`, `correct_indent_classifier`, `t6_solution`, `gcd_indent_unit`, or any new short identifier containing the exact token `indentation` — see `[[cattus-indent-semantics1-eight-case-oracle]]`, a two-token `indentation` name previously knocked the T6 target out of CONTROL's 6-entry retrieval cap).
- Do not touch: `patching/patch_gates.py` (safe_minimal logic itself), PATCH.AUTHOR prompts/contracts, ANSWER.COHERENCE presentation, targeted-validation file/check caps, execution authority policy, anything under `web/`, evidence viewer, Dream Apply/Undo, auth/origin, frontend state (Track B territory).
- Zero live provider calls in any new/modified test. Zero network, zero DB, zero embedding/index/graph traversal beyond `compute_dna`'s existing file loop.
- Every pinned/frozen file this phase legitimately touches gets re-pinned via a **new** reversal receipt added to the **front** of `tests/_harness_maintenance.py::LATER_RECEIPTS` — never by editing history's own reversal fixtures, never by silently bumping a hash with no proof.
- Why inline, not subagent-dispatched: `pytest.ini` uses a single shared `--basetemp`, so two pytest invocations must never run concurrently ([[cattus-pytest-shared-basetemp]]); the frozen-boundary re-pin step depends on exact byte snapshots taken *before* any edit in this same session; and CRLF-vs-LF is mixed per-file and the Edit tool normalizes to a file's dominant ending, so edits must be diffed against a snapshot immediately, in-session, not reconstructed later by a fresh agent.

## File Structure

Production (all already-tracked, existing files — no new production module):
- `core/code_dna.py` — signature + repair-seam import + `compute_dna` transport.
- `core/defect_probe.py` — generic `kwargs` param on `build_python_function_probe`; case-A language.
- `core/paired_defect_probe.py` — case-C language.
- `core/behavioral_matrix.py` — cases B/D/E/F/G/H language.

Tests:
- `tests/test_indent_semantics1.py` — surgical updates to the two assertions this phase legitimately supersedes (contract-identity hashes; "candidate receives no language"), plus the `LATER_RECEIPTS[0]` ordering assertion.
- `tests/test_indent_runtime1.py` — **new**, this phase's own suite (signature/compat, transport, repair-seam-not-activated, expressibility proof, safe_minimal verdict, probe-fingerprint, retrieval smoke).
- `tests/test_phase_registry.py`, `tests/test_phase_picker.py` — stale counters.

Fixtures:
- `tests/fixtures/indent_runtime1_reversal.json` — **new**, this phase's reversal receipt.
- `tests/fixtures/indent_semantics1_frozen_boundaries.json` — re-pinned sha256/AST-digest values for the files this phase touches.

Docs:
- `docs/designs/2026-09-12-language-context-transport-and-repair-boundary.md` — **new** design doc.
- `docs/roadmap/phase_registry.json` — one appended entry.

No commits are made as part of this plan (the user did not ask for one; the repo's convention on this branch is large uncommitted phase batches). Report readiness for a commit at the end instead of performing one.

---

### Task 1: `_classify_indent` signature evolution + repair-seam import (no behavior change)

**Files:**
- Modify: `core/code_dna.py:19-30` (imports), `core/code_dna.py:82-96` (`_classify_indent`)
- Test: `tests/test_indent_runtime1.py` (new file, created in this task)

**Interfaces:**
- Produces: `_classify_indent(text: str, *, language: str | None = None) -> Optional[str]` — `language` keyword-only, default `None`, **ignored by the body**.
- Consumes: `core.indentation_observation.{observe_source_indentation, assess_indentation_observation}` (imported, not called, by `core/code_dna.py`).

- [ ] **Step 1: Snapshot current bytes for the reversal receipt (Task 7 needs this)**

Before any edit, capture pre-image bytes of every file this phase will touch, from the scratchpad (not committed anywhere):

```python
# scratchpad script, run once
import hashlib
from pathlib import Path
ROOT = Path(r"C:\Users\Admin\Documents\Code\J.A.R.V.I.S\districts\C.A.T.T.U.S")
for rel in [
    "core/code_dna.py",
    "core/defect_probe.py",
    "core/paired_defect_probe.py",
    "core/behavioral_matrix.py",
]:
    data = (ROOT / rel).read_bytes()
    print(rel, len(data), hashlib.sha256(data).hexdigest())
```

Save this output somewhere you can paste back into Task 7 — it is the `pre_sha256` for each file's reversal hunk.

- [ ] **Step 2: Edit the import block**

In `core/code_dna.py`, after the existing `from core.credential_redaction import redact_credentials` line, add:

```python
# INDENT.RUNTIME.1 repair seam: the one semantic authority a future patch to
# `_classify_indent` may use instead of inventing a parser. Not called by the
# current (deliberately unfixed) body — see docs/designs/2026-09-12-...md.
from core.indentation_observation import (
    assess_indentation_observation,
    observe_source_indentation,
)
```

- [ ] **Step 3: Evolve the signature**

Replace:
```python
def _classify_indent(text: str) -> Optional[str]:
```
with:
```python
def _classify_indent(text: str, *, language: str | None = None) -> Optional[str]:
```
Do not touch the docstring's algorithmic description or the body below it — the `Counter`-based logic stays byte-for-byte identical.

- [ ] **Step 4: Write the compatibility + non-activation tests**

Create `tests/test_indent_runtime1.py` with this initial content:

```python
"""INDENT.RUNTIME.1 — language context transport & repair boundary.

Production files changed: core/code_dna.py, core/defect_probe.py,
core/paired_defect_probe.py, core/behavioral_matrix.py. This phase does not
fix core/code_dna.py::_classify_indent; see docs/designs/2026-09-12-....md.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import core.code_dna as code_dna_module
from core.code_dna import _classify_indent, compute_dna

ROOT = Path(__file__).resolve().parents[1]

PY_NESTED_2 = "def f(x):\n  if x:\n    return 1\n  return 2\n"
PY_NESTED_4 = "def f(x):\n    if x:\n        return 1\n    return 2\n"


def test_language_is_keyword_only_with_a_none_default():
    sig = inspect.signature(_classify_indent)
    assert list(sig.parameters) == ["text", "language"]
    assert sig.parameters["language"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["language"].default is None


def test_the_one_argument_legacy_call_still_works():
    assert _classify_indent(PY_NESTED_4) == "4space"
    assert _classify_indent(PY_NESTED_2) == "2space"


def test_a_positional_language_argument_is_rejected():
    with pytest.raises(TypeError):
        _classify_indent(PY_NESTED_4, "python")  # type: ignore[misc]


@pytest.mark.parametrize("language", [None, "python", "go", "javascript", "unknown"])
def test_the_current_body_ignores_language_and_stays_defective(language):
    """§9/§45 — the known T6 defect must still reproduce under every language."""
    # PY_NESTED_2 is a real 2-space file; the shipped bug reports it as 4space.
    assert _classify_indent(PY_NESTED_2, language=language) == "4space"
    assert _classify_indent(PY_NESTED_4, language=language) == "4space"


def test_the_repair_seam_is_imported_but_never_called_by_the_current_body(monkeypatch):
    """§9/§26/§27 — dependency available is not dependency activated."""
    calls: list[str] = []
    monkeypatch.setattr(
        code_dna_module,
        "observe_source_indentation",
        lambda *a, **k: calls.append("observe") or (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        code_dna_module,
        "assess_indentation_observation",
        lambda *a, **k: calls.append("assess") or (_ for _ in ()).throw(AssertionError()),
    )
    assert _classify_indent(PY_NESTED_2, language="python") == "4space"
    assert calls == []


def test_the_seam_names_do_not_leak_the_solution():
    """§13 — architecture, not the answer; no short `indentation` identifier."""
    source = inspect.getsource(code_dna_module)
    tree = ast.parse(source)
    forbidden = {
        "structural_indent_fix", "correct_indent_classifier",
        "t6_solution", "gcd_indent_unit",
    }
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    assert names.isdisjoint(forbidden)
```

- [ ] **Step 5: Run the new file and confirm every test passes**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py -q
```
Expected: all pass. (No prior pytest run may be in flight — see [[cattus-pytest-shared-basetemp]].)

---

### Task 2: `compute_dna` language transport (behaviorally inert)

**Files:**
- Modify: `core/code_dna.py:128-237` (`compute_dna`)
- Test: `tests/test_indent_runtime1.py` (append)

**Interfaces:**
- Produces: a private helper `_language_for_suffix(suffix: str) -> str | None` in `core/code_dna.py`, used only inside `compute_dna`.
- Consumes: `config.LANGUAGE_MAP` (already imported elsewhere in this file inside `_code_extensions()`; reuse the same try/except-on-import-failure idiom).

- [ ] **Step 1: Add the helper next to `_code_extensions()`**

```python
def _language_for_suffix(suffix: str) -> Optional[str]:
    """The same authoritative extension->language label compute_dna's own
    lang_mix already keys on suffix for — never a second mapping."""
    try:
        from config import LANGUAGE_MAP
    except Exception:
        return None
    return LANGUAGE_MAP.get(suffix.lower())
```

- [ ] **Step 2: Call it inside the per-file loop**

In `compute_dna`, replace:
```python
        # Indent detection (per-file, vote across files)
        ind = _classify_indent(text)
```
with:
```python
        # Indent detection (per-file, vote across files). INDENT.RUNTIME.1:
        # language describes this file, never core/code_dna.py itself.
        ind = _classify_indent(text, language=_language_for_suffix(p.suffix))
```

- [ ] **Step 3: Representative-baseline tests (append to `tests/test_indent_runtime1.py`)**

```python
def _write_repo(tmp_path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


PY_4SPACE_FILE = "def f(x):\n    if x:\n        return 1\n    return 2\n"
PY_2SPACE_FILE = "def f(x):\n  if x:\n    return 1\n  return 2\n"
GO_TAB_FILE = "package main\n\nfunc main() {\n\tif true {\n\t\tprintln(1)\n\t}\n}\n"
JS_4SPACE_FILE = "function f(a) {\n    if (a) {\n        return 1;\n    }\n    return 2;\n}\n"
CPP_4SPACE_FILE = "int main() {\n    if (x) {\n        return 1;\n    }\n    return 0;\n}\n"


@pytest.mark.parametrize(
    "filename, content, expected_indent",
    [
        ("a.py", PY_4SPACE_FILE, "4space"),
        # §16/§20/§45 — the known defect: a real 2-space Python file is still
        # misreported as 4space after this phase.
        ("a.py", PY_2SPACE_FILE, "4space"),
        ("a.go", GO_TAB_FILE, "tab"),
        ("a.js", JS_4SPACE_FILE, "4space"),
        ("a.cpp", CPP_4SPACE_FILE, "4space"),
    ],
)
def test_compute_dna_repo_level_indent_is_behaviorally_unchanged(
    tmp_path, filename, content, expected_indent
):
    repo = _write_repo(tmp_path, {filename: content})
    dna = compute_dna(str(repo))
    assert dna["indent"] == expected_indent


def test_compute_dna_passes_each_files_own_language_not_a_repo_majority(monkeypatch):
    """§7/§16 — language travels with the file compute_dna is currently reading."""
    seen: list[tuple[str, str | None]] = []
    real = code_dna_module._classify_indent

    def spy(text, *, language=None):
        seen.append((text[:1], language))
        return real(text, language=language)

    monkeypatch.setattr(code_dna_module, "_classify_indent", spy)
    repo = _write_repo(
        _tmp_multi_lang_dir := (Path(__file__).parent / "_indent_runtime1_scratch"),
        {"a.py": PY_4SPACE_FILE, "b.go": GO_TAB_FILE},
    )
    try:
        compute_dna(str(repo))
        languages = {lang for _, lang in seen}
        assert "python" in languages
        assert "go" in languages
    finally:
        import shutil
        shutil.rmtree(_tmp_multi_lang_dir, ignore_errors=True)
```

(Prefer `tmp_path` over a hand-rolled scratch dir if a monkeypatched spy composes cleanly with it — adjust during implementation; the point is asserting the seen `language` set contains both `"python"` and `"go"`, proving per-file transport rather than a single repo-wide guess.)

- [ ] **Step 4: Product test for §15 — target file's own language is `.py`, classified input's language is not**

```python
def test_a_go_files_language_is_go_even_though_the_classifier_lives_in_a_py_file(
    tmp_path, monkeypatch
):
    seen: list[str | None] = []
    real = code_dna_module._classify_indent

    def spy(text, *, language=None):
        seen.append(language)
        return real(text, language=language)

    monkeypatch.setattr(code_dna_module, "_classify_indent", spy)
    repo = _write_repo(tmp_path, {"main.go": GO_TAB_FILE})
    compute_dna(str(repo))
    assert seen == ["go"]
    assert "python" not in seen
```

- [ ] **Step 5: Run and confirm**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py -q
```

---

### Task 3: Generic `kwargs` on `build_python_function_probe`; wire case A (primary)

**Files:**
- Modify: `core/defect_probe.py:437-471` (`build_python_function_probe`), `core/defect_probe.py:517-560ish` (`build_probe_contract_from_behavior_fact`), import block near the top
- Test: `tests/test_indent_runtime1.py` (append)

**Interfaces:**
- Produces: `build_python_function_probe(..., kwargs: Mapping[str, Any] | None = None) -> DefectProbeContract` — omitting `kwargs` reproduces today's exact `{"args": [...], "kwargs": {}}` wire shape (byte-identical for every non-indentation caller).
- Consumes: `core.indentation_observation.LANGUAGE_PYTHON` (already re-exported/used the same way by `core/behavioral_matrix.py` — reuse, don't respell `"python"`).

- [ ] **Step 1: Add the parameter**

```python
def build_python_function_probe(
    *,
    target: ProbeTargetBinding,
    args: Sequence[Any],
    expected: Any,
    probe_basis: str,
    input_basis: str,
    expected_behavior_basis: str,
    provenance_reference: str,
    expectation_source_paths: Sequence[str] = (),
    timeout_seconds: int = DEFAULT_PROBE_TIMEOUT_SECONDS,
    kwargs: Mapping[str, Any] | None = None,
) -> DefectProbeContract:
    """Build a data-only invocation; no code or command text is accepted.

    ``kwargs`` is generic transport for any bounded, JSON-typed keyword the
    target function's real signature accepts (INDENT.RUNTIME.1) — never
    interpreted, never special-cased by target symbol name.
    """
    return DefectProbeContract(
        target=target,
        invocation_kind=INVOCATION_PYTHON_PURE_FUNCTION,
        structured_input_json=_canonical_json(
            {"args": list(args), "kwargs": dict(kwargs) if kwargs else {}}
        ),
        ...  # unchanged
    )
```
Add `Mapping` to the existing `typing` import if not already present.

- [ ] **Step 2: Wire case A**

In `build_probe_contract_from_behavior_fact`, add the import (top of file, near other `core.*` imports):
```python
from core.indentation_observation import LANGUAGE_PYTHON
```
and change its `build_python_function_probe(...)` call to add:
```python
        kwargs={"language": LANGUAGE_PYTHON},
```
(This function already early-returns `None` for every `subject_kind` except `SUBJECT_INDENTATION_STYLE`, and its fixture — `_nested_indentation_fixture` — is always Python-shaped nested text, so this is not a guess.)

- [ ] **Step 3: Non-indentation callers stay byte-identical (regression test)**

```python
def test_omitting_kwargs_reproduces_the_exact_prior_wire_shape():
    from core.defect_probe import build_python_function_probe, ProbeTargetBinding

    target = ProbeTargetBinding(
        file="core/code_dna.py",
        symbol="_classify_indent",
        localized_source_sha256="0" * 64,
        repository_identity="0" * 64,
    )
    contract = build_python_function_probe(
        target=target,
        args=("x",),
        expected="4space",
        probe_basis="task_fact_adapter",
        input_basis="task_fact_adapter",
        expected_behavior_basis="task_fact_adapter",
        provenance_reference="test",
    )
    assert contract.structured_input == {"args": ["x"], "kwargs": {}}
```

- [ ] **Step 4: Run `tests/test_indent_runtime1.py`, then the existing defect-probe suites for a fast regression check**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py tests/test_defect_fact_live.py -q
```
Expected: all pass (do not yet run the full matrix suites — cases C/E–H still lack `language`, which Tasks 4–5 add; running them now is fine too since nothing asserts their kwargs shape until Task 6, but keep runs scoped and sequential per [[cattus-pytest-shared-basetemp]]).

---

### Task 4: Wire case C (preservation) in `core/paired_defect_probe.py`

**Files:**
- Modify: `core/paired_defect_probe.py:296-330ish` (`_indentation_preservation_cases`), import block

**Interfaces:**
- Consumes: `core.indentation_observation.LANGUAGE_PYTHON` (same constant as Task 3).

- [ ] **Step 1: Add the import and the kwarg**

```python
from core.indentation_observation import LANGUAGE_PYTHON
```
In `_indentation_preservation_cases`, its `build_python_function_probe(...)` call gains:
```python
        kwargs={"language": LANGUAGE_PYTHON},
```

- [ ] **Step 2: Confirm `_bound_to_primary` is unaffected**

`_bound_to_primary` compares `target`, `invocation_kind`, `expected_relation`, `side_effect_policy`, `probe_basis`, `input_basis`, `expected_behavior_basis`, `expectation_source_paths`, and requires `fingerprint != primary.fingerprint` — none of those fields include `kwargs` directly and the inequality still holds (different fixture args). No code change needed here; add one assertion to `tests/test_indent_runtime1.py` proving it:

```python
def test_bound_to_primary_still_holds_after_kwargs_are_added():
    from core.paired_defect_probe import build_preservation_cases, _bound_to_primary
    from core.behavioral_expectation import extract_behavioral_expectations
    from core.defect_probe import build_probe_target_binding, build_probe_contract_from_behavior_fact
    from core.code_dna import _classify_indent

    (fact,), _ = extract_behavioral_expectations(
        "2-space indentation is classified as 4-space"
    )
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file="core/code_dna.py",
        target_symbol="_classify_indent",
        source_snippet=inspect.getsource(_classify_indent),
        candidate_eligible=True,
    )
    primary = build_probe_contract_from_behavior_fact(target=binding, behavior_fact=fact)
    (preservation_case,) = build_preservation_cases(target=binding, behavior_fact=fact)
    assert _bound_to_primary(preservation_case, primary) is True
```

- [ ] **Step 3: Run**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py tests/test_paired_defect_probe.py -q
```

---

### Task 5: Wire cases B/D/E/F/G/H in `core/behavioral_matrix.py`

**Files:**
- Modify: `core/behavioral_matrix.py` — `_depth_only_contract` (~line 1035), `_skew_contract` (~line 1066), `_declared_input_cases` (~line 921)

**Interfaces:**
- `_depth_only_contract` and `_skew_contract` are only ever called for Python-shaped fixtures (`indentation_depth_fixture`, `indentation_skew_fixture`); inline `kwargs={"language": INPUT_LANGUAGE_PYTHON}` directly — no new parameter needed.
- `_declared_input_cases` already loops over a `(case_id, provenance, expected, fixture, language, derivation, fixture_note)` tuple and passes that same `language` to `_declared(case, language)`; reuse that exact loop variable for the kwarg so the two can never drift apart.

- [ ] **Step 1: `_depth_only_contract`**

Inside its `build_python_function_probe(...)` call, add:
```python
        kwargs={"language": INPUT_LANGUAGE_PYTHON},
```

- [ ] **Step 2: `_skew_contract`**

Same addition, same constant.

- [ ] **Step 3: `_declared_input_cases`**

Inside the comprehension's `build_python_function_probe(...)` call (used for cases F, G, H), add:
```python
                    kwargs={"language": language},
```
using the tuple-unpacked `language` variable already in scope for that iteration (F/G → `"python"`, H → `"go"`).

- [ ] **Step 4: Add the cross-consistency invariant (append to `tests/test_indent_runtime1.py`)**

This is the one test that ties Tasks 3–5 together and directly answers §39 ("prove the candidate received the case's declared input language"):

```python
def test_every_case_contract_kwargs_language_matches_the_cases_declared_language():
    from tests.test_indent_semantics1 import _t6_cases  # reuse, don't re-derive

    for case in _t6_cases():
        assert case.contract.structured_input["kwargs"] == {"language": case.input_language}, (
            case.case_id
        )
```
(If a bare `from tests.test_indent_semantics1 import _t6_cases` doesn't resolve under this repo's pytest rootdir/sys.path convention, mirror the four-line `_t6_fact()`/`_t6_contract()`/`_t6_cases()` helpers locally instead of importing across test modules — check how other new test files in `tests/` cross-reference `test_indent_semantics1.py`'s helpers, if at all, before choosing.)

- [ ] **Step 5: Run**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py -q
```
Expected: new test currently **fails** here only if Task 6 hasn't yet updated `test_indent_semantics1.py`'s own pinned digests — this test only reads `case.contract`, so it should already pass. If it fails, diagnose before moving on (this is the direct proof the wiring worked).

---

### Task 6: Update the two `test_indent_semantics1.py` assertions this phase legitimately supersedes

This is the "previous phase's positive control" casualty pattern ([[cattus-phase-workflow]] item 9) — expected, and must be handled by proving the delta, not by silently overwriting.

**Files:**
- Modify: `tests/test_indent_semantics1.py` — `LIVE5_CONTRACT_SEMANTICS` dict + `test_the_five_historical_cases_keep_their_contracts_exactly`; `test_candidate_execution_receives_no_language`; the `LATER_RECEIPTS[0] == REVERSAL_FIXTURE` assertion (~line 2474, inside whatever test function contains it — re-read that function's full body first).

**Interfaces:**
- Consumes: `case.contract.structured_input`, `case.contract.identity_payload()` (existing, unchanged shape apart from the new `kwargs` content).

- [ ] **Step 1: Read the full surrounding context before editing**

Read `tests/test_indent_semantics1.py` lines 1331-2601 in full (not yet read this session) so the edit is exact — in particular the complete function containing `assert LATER_RECEIPTS[0] == REVERSAL_FIXTURE` and everything from `test_the_matrix_change_is_three_helpers_and_five_touched_definitions` onward, since Task 7 also touches this region.

- [ ] **Step 2: Prove the delta is exactly `kwargs`, then re-pin**

Replace the body of `test_the_five_historical_cases_keep_their_contracts_exactly` so it keeps the OLD digests as the "everything except kwargs" proof and adds new ones for the full identity:

```python
#: §22 (unchanged) — identity with kwargs stripped back to {}. Proves nothing
#: but the kwarg changed: fixture bytes, expected value, provenance text and
#: execution constraints are exactly INDENT.SEMANTICS.1's.
LIVE5_CONTRACT_SEMANTICS_PRE_RUNTIME1 = dict(LIVE5_CONTRACT_SEMANTICS)  # keep the old values verbatim above this line, renamed


def _contract_semantics_without_kwargs(contract) -> str:
    payload = contract.identity_payload()
    payload.pop("target")
    payload["structured_input"] = {**payload["structured_input"], "kwargs": {}}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_the_five_historical_cases_keep_their_contracts_exactly_apart_from_language():
    """§22, superseded by INDENT.RUNTIME.1 §17: only kwargs.language was added."""
    by_id = {case.case_id: case for case in _t6_cases()}
    for case_id, digest in LIVE5_CONTRACT_SEMANTICS_PRE_RUNTIME1.items():
        assert _contract_semantics_without_kwargs(by_id[case_id].contract) == digest, case_id
        assert by_id[case_id].contract.structured_input["kwargs"] == {"language": "python"}
    assert [by_id[case_id].expected for case_id in LIVE5_CASE_IDS] == [
        "2space", "2space", "4space", "4space", "2space",
    ]
    assert [by_id[case_id].provenance for case_id in LIVE5_CASE_IDS] == [
        PROVENANCE_EXPLICIT_USER_FACT,
        MATRIX_PROVENANCE_SUBJECT_INVARIANT,
        MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION,
        MATRIX_PROVENANCE_SUBJECT_INVARIANT,
        MATRIX_PROVENANCE_SUBJECT_INVARIANT,
    ]
```
Actually compute `LIVE5_CONTRACT_SEMANTICS_PRE_RUNTIME1` by literally keeping the five existing hex strings unchanged (rename the dict, do not touch the values) — the whole point is that the *old* hashes still verify once `kwargs` is stripped back out. Do not hand-wave new full-identity digests unless a later step actually needs them; the "without kwargs" proof plus the explicit `kwargs == {"language": "python"}` assertion is the complete, honest claim §17/§19 asks for.

- [ ] **Step 3: Replace `test_candidate_execution_receives_no_language`**

```python
def test_candidate_execution_now_receives_the_cases_declared_language():
    """§17/§21/§37/§44 of INDENT.RUNTIME.1 — supersedes the pre-phase invariant
    that the candidate was called as ``function(text)`` with nothing else.
    _classify_indent still accepts that legacy one-argument call (proved
    separately in tests/test_indent_runtime1.py); the production matrix now
    also exercises its keyword-only ``language`` contract."""
    assert list(inspect.signature(_classify_indent).parameters) == ["text", "language"]
    for case in _t6_cases():
        assert case.contract.structured_input == {
            "args": [_fixture(case)],
            "kwargs": {"language": case.input_language},
        }, case.case_id
        payload = case.contract.worker_payload(ROOT)
        assert payload["structured_input"]["kwargs"] == {"language": case.input_language}
```

- [ ] **Step 4: Fix the `LATER_RECEIPTS` ordering assertion to survive future phases too**

Change (wherever it lives, found in Step 1's read):
```python
    assert LATER_RECEIPTS[0] == REVERSAL_FIXTURE
```
to a relative-order invariant that keeps being true after INDENT.RUNTIME.1 (or any later phase) prepends its own receipt:
```python
    # Newest first: this phase's own reversal is undone before any receipt
    # older than it (ANSWER.COHERENCE.LIVE.1's), regardless of what a later
    # phase prepends in front of both.
    assert LATER_RECEIPTS.index(REVERSAL_FIXTURE) < LATER_RECEIPTS.index(
        ROOT / "tests/fixtures/answer_coherence_live1_reversal.json"
    )
```
(Match the exact existing path construction style used elsewhere in this file for the second operand.)

- [ ] **Step 5: Run just this file**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_semantics1.py -q
```
Expected: fails at this point only on tests whose fixtures Task 7 hasn't re-pinned yet (`test_classify_indent_and_compute_dna_are_unchanged_and_still_broken` and the frozen-boundary drift test) — confirm the *specific* failures are exactly those two/three, nothing else, before proceeding.

---

### Task 7: Frozen-boundary re-pin — `indent_runtime1_reversal.json` + `LATER_RECEIPTS` + updated digests

**Files:**
- Create: `tests/fixtures/indent_runtime1_reversal.json`
- Modify: `tests/_harness_maintenance.py` (`LATER_RECEIPTS`), `tests/fixtures/indent_semantics1_frozen_boundaries.json` (`files`/`definitions` entries for the 4 touched files)

**Interfaces:**
- Produces: `LATER_RECEIPTS = (ROOT / "tests/fixtures/indent_runtime1_reversal.json", ROOT / "tests/fixtures/indent_semantics1_reversal.json", ROOT / "tests/fixtures/answer_coherence_live1_reversal.json")`.

- [ ] **Step 1: Compute new digests and grouped-opcode hunks**

Write a scratchpad script (per [[bash-heredoc-mangles-backslash-escapes]], as a file via Write, not a heredoc) that, for each of the 4 touched files:
1. Reads current (post-Task-1–5) bytes via `read_bytes().decode("utf-8")`.
2. Reads the Task-1 pre-image bytes (saved earlier) the same way.
3. Builds hunks with `difflib.SequenceMatcher(None, pre_lines, post_lines).get_grouped_opcodes(3)` over `splitlines(keepends=True)` — **grouped**, not raw `get_opcodes`, per [[cattus-phase-workflow]] item 6.
4. Emits `{"path", "pre_sha256", "post_sha256", "hunks": [{"pre": ..., "post": ...}], "top_level_definitions_pre", "top_level_definitions_post", "added_definitions", "removed_definitions", "changed_definitions"}` matching `indent_semantics1_reversal.json`'s schema exactly (reuse its `definitions()`/digest helper from `tests/test_indent_semantics1.py::test_the_matrix_change_is_three_helpers_and_five_touched_definitions` verbatim rather than re-deriving the AST-digest formula).
5. Confirms each `post` hunk string is unique in the post file (`text.count(hunk["post"]) == 1`) before trusting it.

- [ ] **Step 2: Write `tests/fixtures/indent_runtime1_reversal.json`**

```json
{
  "schema_version": "indent_runtime1_reversal_v1",
  "phase_id": "INDENT.RUNTIME.1",
  "reason": "INDENT.RUNTIME.1 gives _classify_indent a keyword-only language parameter (default None, ignored by the current body), transports each walked file's language from compute_dna via config.LANGUAGE_MAP, adds an unused-by-production repair-seam import of core.indentation_observation's public API, and threads that same language into every T6 indentation matrix case's candidate probe contract as a generic kwargs entry. It does not change any fixture byte, expectation, role or provenance of the 8-case matrix, and the known T6 defect still reproduces.",
  "chain": {
    "core/code_dna.py": "this receipt's pre_sha256 is indent_semantics1_frozen_boundaries.json's files entry",
    "core/defect_probe.py": "this receipt's pre_sha256 is indent_semantics1_frozen_boundaries.json's files entry",
    "core/paired_defect_probe.py": "this receipt's pre_sha256 is indent_semantics1_frozen_boundaries.json's files entry",
    "core/behavioral_matrix.py": "this receipt's pre_sha256 is indent_semantics1_reversal.json's post_sha256"
  },
  "new_module": null,
  "reversals": [ /* 4 entries, one per touched file, from Step 1 */ ]
}
```
Fill `reversals` from Step 1's script output exactly (do not hand-type hashes).

- [ ] **Step 3: Prepend to `LATER_RECEIPTS`**

```python
LATER_RECEIPTS = (
    ROOT / "tests/fixtures/indent_runtime1_reversal.json",
    ROOT / "tests/fixtures/indent_semantics1_reversal.json",
    ROOT / "tests/fixtures/answer_coherence_live1_reversal.json",
)
```

- [ ] **Step 4: Update `indent_semantics1_frozen_boundaries.json`**

For `files["core/code_dna.py"]`, `files["core/defect_probe.py"]`, `files["core/paired_defect_probe.py"]`: replace each sha256 with the **new** (post-Task-1–5) whole-file digest. `core/behavioral_matrix.py` is not in this fixture's `files` list (confirmed absent) — no change there. Update `definitions["core/code_dna.py::_classify_indent"]` and `["::compute_dna"]` to the new `hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()` values (compute with the exact snippet from `test_indent_semantics1.py::test_classify_indent_and_compute_dna_are_unchanged_and_still_broken`, Step 1's read).

Preserve the file's exact CRLF/LF byte format and the `json.dumps(..., indent=2, ensure_ascii=False) + "\n"` then `.replace("\n","\r\n")` round-trip if this file is CRLF-serialized (check first — see [[cattus-phase-workflow]] "Serialization is CRLF"); prefer a single-token `raw.replace(old_digest, new_digest)` byte substitution over rewriting the whole file.

- [ ] **Step 5: Run the full re-pin verification loop**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_semantics1.py tests/test_defect_probe_matrix_live.py tests/test_defect_probe_matrix_live5.py tests/test_candidate_verification.py -q
```
Expected: all pass — these three older suites' frozen-boundary tests all route through `before_harness_remediation`/`before_later_receipts`, so they should transparently see through the new receipt. If any of the three still reads raw bytes directly instead of through the helper (a gap flagged once before in [[cattus-phase-workflow]] item 13), it will fail here with a literal digest mismatch — diagnose which file/line and route it through `before_later_receipts` rather than re-pinning its literal constant.

---

### Task 8: Probe worker kwargs proof + fingerprint differentiation (real subprocess, one test)

**Files:**
- Test: `tests/test_indent_runtime1.py` (append)

**Interfaces:**
- Consumes: `core.defect_probe.execute_defect_probe`, `build_python_function_probe`, `build_probe_target_binding` (all existing, unchanged this task).

- [ ] **Step 1: Fingerprint differs by declared language (in-process, no subprocess)**

```python
def test_probe_fingerprint_differs_by_declared_language_alone():
    from core.defect_probe import build_python_function_probe, build_probe_target_binding

    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file="core/code_dna.py",
        target_symbol="_classify_indent",
        source_snippet=inspect.getsource(_classify_indent),
        candidate_eligible=True,
    )
    common = dict(
        target=binding, args=("x\n  y\n",), expected="2space",
        probe_basis="task_fact_adapter", input_basis="task_fact_adapter",
        expected_behavior_basis="task_fact_adapter", provenance_reference="test",
    )
    py_contract = build_python_function_probe(**common, kwargs={"language": "python"})
    go_contract = build_python_function_probe(**common, kwargs={"language": "go"})
    assert py_contract.fingerprint != go_contract.fingerprint
    assert py_contract.structured_input["kwargs"] != go_contract.structured_input["kwargs"]
```

- [ ] **Step 2: One real end-to-end subprocess proof that the worker actually threads kwargs (slow; keep it singular)**

```python
def test_the_worker_actually_forwards_kwargs_language_to_the_real_target():
    """§37 — direct proof, not inference: execute_defect_probe end to end."""
    from core.defect_probe import (
        build_python_function_probe, build_probe_target_binding, execute_defect_probe,
        EXECUTION_STAGE_PRE_PATCH,
    )

    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file="core/code_dna.py",
        target_symbol="_classify_indent",
        source_snippet=inspect.getsource(_classify_indent),
        candidate_eligible=True,
    )
    contract = build_python_function_probe(
        target=binding,
        args=(PY_NESTED_2,),
        expected="2space",
        probe_basis="task_fact_adapter",
        input_basis="task_fact_adapter",
        expected_behavior_basis="task_fact_adapter",
        provenance_reference="test",
        kwargs={"language": "python"},
    )
    receipt = execute_defect_probe(contract, repo_path=ROOT, execution_stage=EXECUTION_STAGE_PRE_PATCH)
    # The unfixed body still says 4space even though it received language="python".
    assert receipt.observed == "4space"
    assert receipt.attempted is True
```
(Check `execute_defect_probe`'s exact keyword arguments and `DefectProbeReceipt` field names against `core/defect_probe.py` before finalizing — this plan's earlier read confirmed the receipt has `.observed`/`.attempted`/`.probe_result`, but confirm the call signature for `execute_defect_probe` itself, not shown in full above.)

- [ ] **Step 3: Run**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py -q
```

---

### Task 9: Expressibility proof — test-only correct candidate vs. the real `safe_minimal` gate

This is the phase's primary evidence (§21–§25, §44). Do not guess the outcome; run the real gate and report whatever it says.

**Files:**
- Test: `tests/test_indent_runtime1.py` (append)

**Interfaces:**
- Consumes: `patching.patch_gates._enforce_safe_minimal`, `core.agent_state.AgentState` — reuse `tests/test_patch_minimal_novelty_live.py`'s `_gate_state`/`_run_gate` construction pattern (read it once more in full before writing this task's code, to match field names exactly: `interface`, `mode`, `user_input`, `file_paths`, `primary_file`, `input_mode`, `language`, `task_type`, then `state.patch_style`, `state.task_info`, `state.json_block`).

- [ ] **Step 1: Define the test-only candidate body**

```python
#: §21 — test-only. Never shipped into _classify_indent. Uses only names this
#: phase's repair seam already makes source-visible in core/code_dna.py, so it
#: faces the same novelty gate a real authored patch would.
RUNTIME1_TEST_ONLY_CORRECT_BODY = (
    "    return assess_indentation_observation(\n"
    "        observe_source_indentation(text, language=language)\n"
    "    ).value\n"
)
```

- [ ] **Step 2: Prove it passes all 8 active matrix cases (in-process, no sandbox needed for this proof)**

```python
def test_the_test_only_candidate_expresses_all_eight_cases_correctly():
    from tests.test_indent_semantics1 import _t6_cases  # or locally re-derive; see Task 5 Step 4 note

    def candidate(text, *, language=None):
        return assess_indentation_observation(
            observe_source_indentation(text, language=language)
        ).value

    for case in _t6_cases():
        (text,) = case.contract.structured_input["args"]
        lang = case.contract.structured_input["kwargs"]["language"]
        assert candidate(text, language=lang) == case.expected, case.case_id
```

- [ ] **Step 3: Run it through the real `_enforce_safe_minimal` gate**

Build `target_snippet = inspect.getsource(_classify_indent)` (the *post-Task-1* source: signature already carries `language`, body still the old Counter logic) and `patched_snippet` = the same signature line plus `RUNTIME1_TEST_ONLY_CORRECT_BODY`. Reuse (or closely mirror) `test_patch_minimal_novelty_live.py`'s state-builder:

```python
def test_real_safe_minimal_verdict_on_the_test_only_correct_candidate():
    from patching import patch_gates
    from core.agent_state import AgentState

    target_snippet = inspect.getsource(_classify_indent)
    header, _, _ = target_snippet.partition(":\n")
    patched_snippet = header + ":\n" + RUNTIME1_TEST_ONLY_CORRECT_BODY

    state = AgentState(
        interface="agent", mode="reviewer", user_input="test",
        file_paths=[], primary_file=None, input_mode="terminal",
        language="python", task_type="bug_fix",
    )
    state.patch_style = "safe_minimal"
    state.task_info = {"intent": "bug_fix", "patch_style": "safe_minimal"}
    state.json_block = {
        "patch_candidate": {
            "target_snippet": target_snippet,
            "patched_snippet": patched_snippet,
            "file": "core/code_dna.py",
            "target_node_kind": "function",
            "target_node_name": "_classify_indent",
        },
        "confidence": 1.0,
        "issues": [],
    }
    patch_gates._enforce_safe_minimal(state)

    admitted = state.json_block.get("patch_candidate") is not None
    reason = state.json_block.get("candidate_novelty_reason", "")
    # Report honestly either way — do not assert a predetermined outcome.
    print(f"T6_REPAIR_EXPRESSIBLE_UNDER_CURRENT_POLICY = {admitted}")
    if not admitted:
        print(f"blocker: {reason}")
    # The only real assertion: the gate ran and left a legible verdict.
    assert "candidate_novelty_admitted" in state.json_block
```

Note the `header, _, _ = target_snippet.partition(":\n")` split is a sketch — confirm the exact way this codebase splits a function's signature line from its body elsewhere (e.g. how `T6_CLASSIFIER_BODY` in `test_indent_semantics1.py` is recombined with a signature to form `target_snippet`/`patched_snippet` for the gate tests) and match that convention exactly, rather than inventing a new one.

- [ ] **Step 4: Also record the negative/positive control shape**

If rejected, capture `state.json_block.get("candidate_new_identifiers")`/whatever field names `classify_candidate_novelty`'s telemetry uses (check `core/local_binding_novelty.py`'s `as_telemetry()` for exact keys) so the final report can state the *exact* gate/reason per §22, not a paraphrase.

- [ ] **Step 5: Run**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py -q -s
```
(`-s` to see the printed verdict line during this development run; remove reliance on stdout for the final report — read `state.json_block` fields directly instead.)

---

### Task 10: Retrieval / localization regression check (read-only verification, react only if needed)

**Files:**
- None modified unless the check fails.

- [ ] **Step 1: Run the real-population retrieval test**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_repository_specificity_entry_ordering.py -q
```
Budget ~1 minute ([[cattus-indent-semantics1-eight-case-oracle]]).

- [ ] **Step 2: Interpret**

If green: record `_classify_indent`'s entry rank and confirm it is still inside CONTROL's 6-entry cap (read the test's own printed/asserted rank, or add a one-off scratchpad script calling the same production ranking function directly if the test doesn't expose the number).

If red: this phase added exactly one new pair of identifiers to `core/code_dna.py` (`observe_source_indentation`, `assess_indentation_observation`, both *imported*, not newly *defined* — likely low retrieval weight since only defined symbols are typically scored, but verify rather than assume). Per §14, the fix is to change the runtime seam's naming/module exposure — **not** to update the expected-ranking snapshot to make the test pass. Escalate the specific finding rather than silently loosening the assertion.

---

### Task 11: Design doc + phase registry entry + stale counters

**Files:**
- Create: `docs/designs/2026-09-12-language-context-transport-and-repair-boundary.md`
- Modify: `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`, `tests/test_phase_picker.py`

**Interfaces:** none (documentation + registry data).

- [ ] **Step 1: Dump the exact current schema of one full phase entry**

```bash
python -c "import json; d=json.load(open('docs/roadmap/phase_registry.json', encoding='utf-8')); print(json.dumps(d['phases'][-1], indent=2, ensure_ascii=False))"
```
Use every field name from `INDENT.SEMANTICS.1`'s own entry verbatim (`phase_id`, `title`, `track`, `status`, `automation_level`, `budget_tier`, `risk_level`, `summary`, plus whatever `writes_real_repo`/`human_approval_required`/`merge_allowed`/`model_calls_allowed` fields the full (untruncated) entry carries — the earlier truncated dump cut off before these; read them in full here).

- [ ] **Step 2: Append the INDENT.RUNTIME.1 entry**

`phase_id: "INDENT.RUNTIME.1"`, `track: "OPS"` (same track as INDENT.SEMANTICS.1 — same ID namespace), `status: "complete"`, `model_calls_allowed: false`, `budget_tier: "local_only"`, `writes_real_repo: true`, `human_approval_required: true`, `merge_allowed: false`. `summary` should mirror this plan's Architecture paragraph, compressed. Follow the exact CRLF round-trip discipline from [[cattus-phase-workflow]] ("Serialization is CRLF") — verify `render(json.loads(raw)) == raw` before writing, and prefer inserting the new object via a targeted string operation over `json.dumps`-ing the whole 1MB+ file if that risks reformatting unrelated entries.

- [ ] **Step 3: Bump `tests/test_phase_registry.py` counters**

- `assert len(data["phases"]) == 177` → `178`.
- The `counts_by_track` dict literal's `"OPS"` entry: read its current value from this test file directly (not from the JSON, which doesn't store this dict — confirmed during Task 1 exploration) and increment by 1.
- Check whether `INDENT.SEMANTICS.1`'s own test (or `test_phase_registry.py`) contains an `assert "INDENT.RUNTIME.1" not in ids`-style forward-reference guard; if so, remove or update it per [[cattus-phase-workflow]] item 4.

- [ ] **Step 4: Bump `tests/test_phase_picker.py` counters**

Per [[cattus-phase-workflow]]: `report["bucket_counts"]["complete_or_history"]` simple-form sites (search for the exact bracketed substring, not the bare key) plus the one full-dict-literal `"complete_or_history": N,` site. Cross-check the new value with:
```bash
python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json
```

- [ ] **Step 5: Write the design doc**

Mirror `docs/designs/2026-09-11-language-aware-indentation-observation-contract.md`'s structure (numbered `##` sections, tables for the candidate/verdict matrix) but content per this phase's own 50-item final report (Task 12 produces the report; the design doc is its permanent, numbered-section form — write it last, after Task 12's numbers are in hand, so it states measured facts rather than predictions).

- [ ] **Step 6: Run**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q
```

---

### Task 12: Full verification pass + Final Report

**Files:** none (verification only), unless a genuine regression surfaces.

- [ ] **Step 1: Focused suite**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_indent_runtime1.py tests/test_indent_semantics1.py tests/test_defect_probe_matrix_live.py tests/test_defect_probe_matrix_live5.py tests/test_candidate_verification.py tests/test_candidate_revision_live.py tests/test_patch_minimal_live.py tests/test_patch_minimal_novelty_live.py tests/test_answer_coherence_live1.py tests/test_paired_defect_probe.py tests/test_defect_probe_live.py tests/test_defect_fact_live.py tests/test_repository_specificity_entry_ordering.py tests/test_phase_registry.py tests/test_phase_picker.py -q
```

- [ ] **Step 2: Adjacent/broad check via A/B against the known 49-failure baseline**

Per [[cattus-pytest-shared-basetemp]]: do not just run the full suite and eyeball red. Either scope to `grep -rl "code_dna\|defect_probe\|behavioral_matrix\|paired_defect_probe" tests/*.py` plus the 24 known-baseline files, or run the full suite once (budget hours, background it, do not start a second pytest invocation while it runs) and diff the sorted FAILED set against the documented 49.

- [ ] **Step 3: Black-box compatibility spot check**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_harness_blackbox_revision.py -q
```
Expected: still 9/9 ([[cattus-blackbox-revision-suite-baseline]]) — this phase changes no fixture, expectation or oracle exception.

- [ ] **Step 4: Static checks**

```bash
./.venv/Scripts/python.exe -m compileall core patching tests -q
./.venv/Scripts/python.exe -m benchmarks.run_benchmarks --check
git diff --check
```
(Confirm `run_benchmarks --check`'s exact invocation from `benchmarks/run_benchmarks.py`'s own `__main__`/argparse block before relying on this exact flag spelling.)

- [ ] **Step 5: Assemble the Final Report**

Answer all 50 numbered items from the phase spec's §48 and the explicit yes/no questions at its end, using only measured results from Steps 1–4 and Tasks 1–11 — no predicted numbers. Explicitly separate: (a) this phase's own production/test changes, (b) any pre-existing baseline failures encountered (attribute to the known 49 or to concurrent Track-B work by mtime, never assume), (c) the honest `T6_REPAIR_EXPRESSIBLE_UNDER_CURRENT_POLICY` verdict and exact blocker if false.

---

## Self-Review Notes

- **Spec coverage:** §1–9 (state + goal + non-goal) → Task 1. §7–8 (compute_dna transport + normalization reuse) → Task 2. §10–13 (repair seam, no accidental fix, no unused-import handwaving, no leaked naming) → Task 1 Steps 2/4. §14/§43 (retrieval) → Task 10. §15/§18 (no target-file inference) → Task 2 Step 4, Task 5 Step 4. §17/§19 (probe contract alignment, matrix cases unchanged) → Tasks 3–6. §21–25/§44 (expressibility + safe_minimal verdict) → Task 9. §26–27 (seam is not authority) → Task 1 Step 4 (`test_the_repair_seam_is_imported_but_never_called...`). §33 (LIVE.5 exception not expanded) → touched nowhere in this plan (verified: Tasks 1–11 never write `oracle="live5"` anywhere). §36–41 (compatibility, fingerprinting, matrix receipts, schema) → Tasks 3, 5, 8. §46 (required test matrix) → cross-checked against Tasks 1, 2, 5, 6, 9. §47 (governance suite) → Task 12.
- **Placeholder scan:** every code block above is real, runnable-shaped code, not "add appropriate handling." The two spots deliberately marked for in-session confirmation (Task 9 Step 3's snippet-split convention; Task 6/7's exact surrounding test-file context) are flagged because this plan was written without yet reading those exact lines — not because the work is hand-waved; resolve them by reading, then implementing, in that order, when the task is reached.
- **Type/name consistency:** `_language_for_suffix` (Task 2) is the only new name introduced anywhere in production code; every task that reads a case's language uses `case.input_language` / `case.contract.structured_input["kwargs"]["language"]` consistently.

## Execution Choice

**Inline Execution**, using superpowers:executing-plans conventions (batch a few steps, verify, continue) rather than subagent-per-task — justified above under Global Constraints ("Why inline, not subagent-dispatched"). No commit is planned; this repo's convention on this branch is large uncommitted phase batches, and the user did not ask for one.
