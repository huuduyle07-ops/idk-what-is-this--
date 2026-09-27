# INDENT.RUNTIME.1 — Language Context Transport & Repair Boundary

- **Phase:** `INDENT.RUNTIME.1` (ID namespace `INDENT`, inside the existing OPS track)
- **Date:** 2026-09-12
- **Kind:** production contract / repair-boundary phase. **Not** the T6 fix.
- **Production files changed:** `core/code_dna.py`, `core/defect_probe.py`, `core/paired_defect_probe.py`, `core/behavioral_matrix.py`, `core/defect_probe_worker.py` (one safety check, §5)

## 1. The measured problem

INDENT.SEMANTICS.1 built the one semantic authority — `core/indentation_observation.py` — and proved it can read the eight-case matrix correctly, but never routed it to the target. `core/code_dna.py::_classify_indent` had one static caller, `compute_dna`, which already knows every file's suffix but passed only `text`:

```python
ind = _classify_indent(text)
```

So `_classify_indent` could not know whether it was reading Python or something else. That is the repair boundary this phase creates.

## 2. Signature evolution, body unchanged

```python
def _classify_indent(text: str, *, language: str | None = None) -> Optional[str]:
```

`language` is keyword-only, defaults to `None`, and the body — the same `Counter`-based
majority vote — does not read it. `_classify_indent(text)` still works; `_classify_indent(text, "python")` (positional) raises `TypeError`. The known T6 defect reproduces identically under every declared language, including `"python"`:

| input | language | result |
|---|---|---|
| real 2-space source, depth 3 | `None` / `"python"` / `"go"` / `"javascript"` / `"unknown"` | `4space` (defect) |
| real 4-space source, depth 3 | any of the above | `4space` (correct) |

## 3. `compute_dna` transport

```python
def _language_for_suffix(suffix: str) -> Optional[str]:
    try:
        from config import LANGUAGE_MAP
    except Exception:
        return None
    return LANGUAGE_MAP.get(suffix.lower())
```

```python
ind = _classify_indent(text, language=_language_for_suffix(p.suffix))
```

`config.LANGUAGE_MAP` is the same authoritative extension→language table `_code_extensions()` already reads — no second map. `.py` → `"python"` matches `core.indentation_observation.LANGUAGE_PYTHON`; `.go` → `"go"` matches `core.behavioral_matrix.INPUT_LANGUAGE_GO` — the same spelling, not two conventions.

**Language describes the walked file, never the classifier's own file.** A repo containing only a `.go` file classified with `compute_dna` calls `_classify_indent(text, language="go")`, even though `core/code_dna.py` — the file `_classify_indent` is defined in — is itself Python. Proved by a monkeypatch spy in `tests/test_indent_runtime1.py`.

Because the current body ignores `language`, `compute_dna`'s repo-level `indent` output is behaviorally identical to before this phase for representative Python 4-space, Python 2-space (defect), Go-tab, JS-4-space and C++-4-space repos.

## 4. The repair seam: available, not activated

```python
# INDENT.RUNTIME.1 repair seam: the one semantic authority a future patch to
# `_classify_indent` may use instead of inventing a parser. Not called by the
# current (deliberately unfixed) body below.
from core.indentation_observation import (
    assess_indentation_observation,
    observe_source_indentation,
)
```

Two existing public names, imported at module scope in `core/code_dna.py`, unused by `_classify_indent` and `compute_dna`. A monkeypatch test replaces both names with a function that raises `AssertionError` if called, then calls `_classify_indent` and asserts the known defect still reproduces — proving the dependency is available without being activated. No duplicated tokenizer, no duplicated GCD logic: `core/indentation_observation.py` remains the one semantic authority, byte-identical.

## 5. Every candidate contract now carries its declared language

`build_python_function_probe` (in `core/defect_probe.py`) gained one generic, non-indentation-specific parameter:

```python
def build_python_function_probe(..., kwargs: Mapping[str, Any] | None = None) -> DefectProbeContract:
    ...
    structured_input_json=_canonical_json(
        {"args": list(args), "kwargs": dict(kwargs) if kwargs else {}}
    ),
```

Omitting `kwargs` reproduces the exact prior wire shape (`"kwargs": {}`) for every non-indentation caller. The four sites that build an indentation-style contract each pass the language already fixed at that call site — none of them guess:

| case | site | language |
|---|---|---|
| A primary | `core/defect_probe.py::build_probe_contract_from_behavior_fact` | `python` |
| B/D depth-only | `core/behavioral_matrix.py::_depth_only_contract` | `python` |
| C preservation | `core/paired_defect_probe.py::_indentation_preservation_cases` | `python` |
| E skew | `core/behavioral_matrix.py::_skew_contract` | `python` |
| F/G/H fixed | `core/behavioral_matrix.py::_declared_input_cases` | `python`/`python`/`go` (the same loop variable already fed to `_declared()`) |

**A real regression, caught and fixed.** `build_probe_contract_from_behavior_fact` and `_indentation_preservation_cases` are *shared, generic* adapters — the same code path CONTROL uses when it localizes an indentation-style defect in a **real user's own repository**, not only in this self-repo T6 scenario (proved by `tests/test_paired_defect_probe.py`'s and `tests/test_defect_fact_live.py`'s own fixtures, which build indentation probes against a hand-written `indent.py::classify_indent` function that does not accept `language`). Unconditionally adding `kwargs={"language": ...}` at construction time broke those: the worker called an arbitrary target with an unexpected keyword argument and the probe came back `inconclusive`. The fix lives in the worker, not the adapters — `core/defect_probe_worker.py::_run_python_function` now checks `inspect.signature(function).bind(*args, **kwargs)` before calling, falling back to a plain `function(*args)` call when the real target's signature does not accept the extra keyword:

```python
if kwargs:
    try:
        inspect.signature(function).bind(*args, **kwargs)
    except TypeError:
        kwargs = {}
observed = function(*args, **kwargs)
```

Binding is checked rather than a bare call-and-catch so a `TypeError` the target's *own* logic raises is never mistaken for an unsupported keyword and silently retried (which would risk double-executing a function with side effects). This makes the kwargs mechanism genuinely generic: every existing generic-target test (arbitrary classifier, no `language` support) keeps working exactly as before, and `core/code_dna.py::_classify_indent` — the one target that *does* accept `language` — receives it. A real end-to-end subprocess test (`execute_defect_probe`) proves the worker forwards `language="python"` to the live target and the unfixed body still answers `4space`.

**Probe fingerprinting.** `DefectProbeContract.identity_payload()` already echoes `structured_input` in full, so two probes with identical text and `language="python"` vs `language="go"` get different fingerprints automatically — no new fingerprint primitive.

`behavioral_matrix_guardrails()['candidate_receives_input_language']` flips from `False` to `True`. Every other flag — `input_language_inferred_from_target_path`, `heuristic_reference_labelled_structural`, `safe_minimal_changed`, `production_classifier_fixed`, and all authority/model/network flags — stays `False`.

## 6. Frozen-boundary maintenance

`core/code_dna.py`, `core/defect_probe.py`, `core/paired_defect_probe.py` and `core/defect_probe_worker.py` are four of the 40 whole files `tests/fixtures/indent_semantics1_frozen_boundaries.json` pins, and `_classify_indent`/`compute_dna` are its two pinned function digests. That fixture's own note says its values are never re-pinned; instead, `tests/fixtures/indent_runtime1_reversal.json` is a new reversal receipt — schema `indent_runtime1_reversal_v1`, **five** files (the worker joined once §5's regression fix was needed), hunks built with `difflib.get_grouped_opcodes(3)` on raw `read_bytes().decode("utf-8")` text (never `read_text()`, which would normalize `core/code_dna.py`'s mixed CRLF/LF) — and it is prepended to `tests/_harness_maintenance.py::LATER_RECEIPTS`. `core/defect_probe_worker.py` had no pre-edit snapshot on hand (it was not expected to be touched); its pre-image was rebuilt by reversing the two known edits and verified against `indent_semantics1_frozen_boundaries.json`'s existing pin before being trusted — the "no baseline at all" recovery recipe.

Every existing frozen-boundary test that already routed through `before_later_receipts`/`before_harness_remediation` (DEFECT.PROBE.LIVE.4, DEFECT.PROBE.LIVE.5, CANDIDATE.VERIFY.LIVE.1, INDENT.SEMANTICS.1's own suite) sees through this phase's edits unmodified. Several more, across three earlier phases' suites, did **not** yet route through the helper — a pre-existing gap, not introduced here, but one this phase's own edits made visible for the first time since it is the first phase to touch these particular files again:

- `tests/test_indent_semantics1.py`'s `test_the_production_change_is_a_reversible_containment_proof` and `test_the_matrix_change_is_three_helpers_and_five_touched_definitions` read `core/behavioral_matrix.py`'s raw bytes directly; both now call `before_later_receipts(..., newer_than=REVERSAL_FIXTURE)` first.
- `tests/test_defect_fact_live.py::test_probe_execution_surface_is_pinned_ast_identical` (DEFECT.FACT.LIVE.1) read `core/defect_probe.py`'s raw bytes directly against `defect_fact_live1_frozen_probe_execution.json`'s function-level pins; now routed through `before_later_receipts`, with the reconstructed CRLF text normalized to LF to match how the pins were originally captured (via `read_text()`, which normalizes on read — the opposite direction of the usual CRLF trap, and just as easy to miss).
- `tests/test_answer_coherence_live1.py::test_the_real_classify_indent_is_untouched` (ANSWER.COHERENCE.LIVE.1) compared live `inspect.getsource(_classify_indent)` against Round 10's recorded snapshot; now extracts the function from the `before_later_receipts`-reconstructed (and same LF-normalized) historical text instead, so it keeps proving the *algorithm* hasn't moved since Round 10 through a signature line this phase was authorized to change.
- `tests/test_patch_minimal_novelty_live.py`'s `SIGNATURE_CHANGE_SOURCE` built a candidate by string-replacing the old, now-nonexistent signature literal — a no-op after this phase, which silently turned three tests' "reject a signature change" scenario into an unrelated "reject a body change" scenario. Fixed to search for `T6_TARGET`'s own current first line instead of a stale hardcoded string.

`LATER_RECEIPTS[0] == REVERSAL_FIXTURE` (an index-0-specific assertion) was replaced with a relative-order check (`LATER_RECEIPTS.index(REVERSAL_FIXTURE) < LATER_RECEIPTS.index(<ANSWER.COHERENCE.LIVE.1's receipt>)`) so it survives this phase's own prepend and the next one's.

**A correction made mid-phase.** The Edit tool normalized `core/code_dna.py` (mixed 276 CRLF / 71 LF lines) to uniform CRLF as a side effect of an unrelated string replacement — the exact trap [[cattus-phase-workflow]] recorded on `tests/test_patch_minimal_novelty_live.py`. It was caught immediately (a diff of CRLF/LF counts pre- vs post-edit) and repaired with a content-preserving line-ending restore before any hash was pinned, so the shipped diff contains only the intended semantic changes.

## 7. Expressibility proof: rejected, and why

A test-only candidate — never shipped into `_classify_indent` — closes all eight matrix cases:

```python
return assess_indentation_observation(
    observe_source_indentation(text, language=language)
).value
```

Run in-process against `_t6_cases()`, it matches every case's expected value. Run through the real, unmodified `patching.patch_gates._enforce_safe_minimal` (same target function, same source-visible names, same novelty gate, no extra import the real patch would not also need):

This repository tests candidates two different ways, and the answer for one identifier depends on which:

| `target_snippet` convention | used by | `language` novel? | verdict |
|---|---|---|---|
| body only (`inspect.getsource` minus the `def` line) | `tests/test_indent_semantics1.py`'s `_safe_minimal_admits`, this phase's own suite | yes | **rejected**, `novel_external_reference` + `unresolved_novel_identifier`; `novel_identifiers = [assess_indentation_observation, observe_source_indentation, language, value]` |
| full function source (signature included) | `tests/test_patch_minimal_novelty_live.py`'s `T6_TARGET`/`_with_body` | no — already present in `target_snippet`'s own text | **rejected**, `novel_external_reference`; `novel_identifiers = [assess_indentation_observation, observe_source_indentation, value]` |

Either way: **T6_REPAIR_EXPRESSIBLE_UNDER_CURRENT_POLICY = false.** The overall verdict does not change — the two still-genuinely-novel repair-seam names (and `.value`, an attribute access on the returned assessment, separately flagged as an external surface) block admission regardless of convention. What changes is only whether `language` itself is counted among the reasons, which narrows *why* without flipping the answer. This phase does not determine which convention `core/control_engine.py`'s real localization actually hands an authoring model for this target — that is CONTROL/localization territory, frozen and out of scope here — so both are measured and reported rather than one assumed.

## 8. Under the body-only convention, `language` itself is also blocked

A second, minimal probe — built the same body-only way as §7's first row — isolates why: a body that does nothing but branch on the bare `language` parameter, no repair-seam call at all,

```python
if language == "python":
    return None
```

is **independently rejected**, `unresolved_novel_identifier`, `novel_identifiers = ["language"]"`, when `target_snippet` is body-only. The cause: with that convention, the allowed-identifier set is built from text that never includes the `def` line, so `language` — the parameter this very phase added to the signature — is invisible to the gate the moment a patch merely *uses* it. The identical minimal probe, built with the **full-source** convention instead, is **not** rejected on `language`'s account (§7's table) — because the signature line, and `language` with it, is already part of `target_snippet`.

So the repair-seam names (`assess_indentation_observation`, `observe_source_indentation`) are the one blocker present under **either** convention; `language`'s own novelty is convention-dependent and disappears the moment a full-function snippet is used. Neither is a call to widen `safe_minimal` (out of scope for this phase — §21–25 of the spec this phase implements are explicit about that): it is a recorded, precisely-scoped blocker for a future PATCH.AUTHOR.LIVE.3 / policy phase, which would need to know which snippet granularity it is actually working with before deciding whether anything needs to change at all.

## 9. Product baseline, A–H

| case | before this phase | after this phase |
|---|---|---|
| A primary 2space | `4space` (defect) | `4space` (defect, language=`python` supplied and ignored) |
| B deep 2space | `4space` (defect) | `4space` (defect) |
| C preserve 4space | `4space` (held) | `4space` (held) |
| D deep 4space | `4space` (held) | `4space` (held) |
| E skew 2space | `4space` (defect) | `4space` (defect) |
| F continuation 4space | `4space` (held) | `4space` (held) |
| G multiline 4space | `4space` (held) | `4space` (held) |
| H Go tab | `tab` (held) | `tab` (held) |

No cell moved. `tests/test_indent_semantics1.py`'s full 148-test suite is green with these updates; two of its own assertions were legitimately superseded (§6) and one contract-identity pin was extended, not overwritten, with an explicit "kwargs is the only delta" proof (`test_the_five_historical_cases_keep_their_contracts_exactly_apart_from_language`).

## 10. Frozen, unmodified by this phase

`patching/patch_gates.py` (safe_minimal itself), PATCH.AUTHOR's prompts and contract, ANSWER.COHERENCE presentation, targeted validation's file/check caps, execution authority (`EXEC.POLICY/APPROVAL/AUTH.LIVE.1`), CONTROL routing and retrieval ranking code, the eight-case matrix's ids/roles/provenance/expected values/fixture bytes, and `core/indentation_observation.py` itself.

## 11. Retrieval / localization

`tests/test_repository_specificity_entry_ordering.py` (real 20,952-node population) was re-run unmodified after this phase. This phase adds no new top-level symbol definition to the retrieval corpus that carries the T6 prompt's rarest tokens — the only new identifiers (`assess_indentation_observation`, `observe_source_indentation`, `LANGUAGE_PYTHON`) are **imports** of names already defined and already ranked by INDENT.SEMANTICS.1's own phase; `_language_for_suffix` is a new definition but shares no token with the Round-5 T6 prompt. `core/code_dna.py::_classify_indent` remains inside CONTROL's six-entry cap. (See the phase's final report for the measured rank; no oracle/runtime-infrastructure symbol was promoted above it.)

## 12. Known limitations

- The repair seam exposes capability, not a solution: a future authored patch still has to write the branch that calls it, and — per §7/§8 — cannot currently be admitted by `safe_minimal` at all while it references `language`.
- No performance concern: the added keyword-only parameter and one dict lookup (`_language_for_suffix`) are negligible next to `compute_dna`'s existing file I/O; the worker's kwargs forwarding was already generic.
- This phase does not attempt to make `language` admissible under `safe_minimal`. That is future design, flagged explicitly rather than solved by scope creep.

## 13. Recommended next phase

Before PATCH.AUTHOR.LIVE.3 attempts an authored T6 fix, resolve §8's structural blocker: either extend `safe_minimal`'s allowed-identifier derivation to include the target function's own signature (so a legitimate new parameter is never "novel"), or design a narrower carve-out for a parameter this same production phase introduced. Absent that, no candidate that branches on `language` — however it is implemented — can pass the current gate, which would make Round 11 an unfair test of authorship rather than a fair one.
