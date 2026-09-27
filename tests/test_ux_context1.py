"""UX.CONTEXT.1: every Generate request carries one coherent repository/run context.

Static and contract checks over the shipped template, the WorkbenchState owner
and this phase's receipts.  The behavior (repository A -> B, same-repository
continuation, switching back, explicit and mismatched history, the Java
two-file dogfood request, in-flight tickets) is proven in real Chromium by
tests/test_ux_context1_browser.py.  No model, database or network is used here.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path

from tests.test_ux_state1 import _function

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TEMPLATE = "web/templates/index.html"
MODULE = "web/static/workbench_state.js"
TICKET_CONTROL = 'control: ticket.requestRun ? ticket.requestRun.context : ""'
GENERATE_HANDLERS = {"generatePatch": "generate", "generateCandidates": "candidates"}
HYDRATED_CONTEXT = 'context: document.getElementById("context")?.textContent || "",'
# Module definitions whose bytes carry the frozen UX.STATE.1 semantics: stale-response
# acceptance (UX-02), action and Undo outcomes (UX-03), per-mode execution (UX-04).
FROZEN_MODULE_FUNCTIONS = (
    "idleAction", "idleSlots", "text", "normalizeRepository", "nextId", "execution", "subscribe", "notify",
    "telemetry", "parsedPayload", "backendIdentity", "candidateRecord", "replaceCandidate", "refreshCandidate",
    "invalidateContext", "invalidate", "setRepository", "setMode", "setExecutionOption", "refusal",
    "mutationPending", "blocked", "staleReason", "reviewRecord", "settle", "refuse", "selectListed",
    "generateOutcome", "reviewOutcome", "undoOutcome", "describeAction",
)
EXISTING_FILES_CHANGED = (
    "web/static/workbench_state.js",
    "web/templates/index.html",
    "docs/roadmap/phase_registry.json",
    "tests/test_phase_registry.py",
    "tests/test_phase_picker.py",
    "tests/_ux_state1_maintenance.py",
    "tests/test_ux_state1.py",
)


def _post_state(relative: str) -> bytes:
    # UX.CONTEXT.1's own post-state: later CONTROL.FRESH.1 edits are reversed first.
    from tests._control_fresh1_maintenance import before_control_fresh1

    return before_control_fresh1(relative)


def _current(relative: str) -> str:
    # Byte-exact (CRLF kept) so it compares with the reconstructed entry bytes.
    return _post_state(relative).decode("utf-8")


def _entry(relative: str) -> str:
    from tests._ux_context1_maintenance import before_ux_context1

    return before_ux_context1(relative).decode("utf-8")


def _declared(source: str, indent: str) -> list[str]:
    return re.findall(rf"^{indent}(?:async )?function (\w+)\(", source, flags=re.M)


def _changed_spans(before: str, after: str) -> list[tuple[int, int]]:
    """Character spans of `after` that differ from `before` (line-based)."""
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    offsets = [0]
    for line in new:
        offsets.append(offsets[-1] + len(line))
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    return [(offsets[j1], offsets[j2]) for tag, _, _, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def _span(source: str, text: str) -> tuple[int, int]:
    start = source.index(text)
    return start, start + len(text)


# -- Generate serialization ------------------------------------------------------------

def test_generate_requests_transport_run_context_only_from_their_ticket():
    template = _current(TEMPLATE)
    for name, kind in GENERATE_HANDLERS.items():
        body = _function(template, f"function {name}(")
        assert f'WorkbenchState.begin("{kind}")' in body, name
        assert body.count(TICKET_CONTROL) == 1 and "repo_path: ticket.repository" in body, name
        assert body.index("WorkbenchState.begin(") < body.index("new URLSearchParams("), name
        assert 'getElementById("context")' not in body and "#context" not in body, name


def test_the_run_context_is_hydrated_once_after_the_formatting_pass_and_never_written_by_id():
    template = _current(TEMPLATE)
    script = template[template.index("<script>"):]
    hydration = script[script.index("WorkbenchState.hydrate({"):]
    hydration = hydration[: hydration.index("});") + 3]
    assert hydration.count(HYDRATED_CONTEXT) == 1
    # The page's pre-existing load-time JSON formatting pass runs before hydration.
    assert script.index('document.querySelectorAll("pre").forEach') < script.index("WorkbenchState.hydrate(")
    reads = re.findall(r'getElementById\("context"\)[^;\r\n]*', script)
    # Hydration, plus Local Critique's unchanged read (a candidate-bound request without a repository).
    assert reads == ['getElementById("context")?.textContent || "",', 'getElementById("context").innerText.trim()']
    assert 'getElementById("context").innerText.trim()' in _function(template, "async function localCritique(")
    assert not re.search(r'getElementById\("context"\)\??\.(innerText|textContent|innerHTML)\s*=(?!=)', script)


def test_the_state_owner_binds_runs_by_generation_not_by_repository_text():
    module = _current(MODULE)
    request_run = _function(module, "function requestRun(")
    assert "run.contextGeneration === contextGeneration" in request_run
    assert "repository" not in request_run  # no path comparison can resurrect a binding
    server_run = _function(module, "function serverRun(")
    assert "runRepository === repository ? contextGeneration : null" in server_run
    assert module.count("serverRun(") == 2 and "run = serverRun(session);" in _function(module, "function hydrate(")
    # Hydration is the only place a run is ever bound.
    assert re.findall(r"^\s*run = .*$", module, flags=re.M) == ["        run = serverRun(session);"]
    kinds = module[module.index("const KINDS = Object.freeze({"):]
    kinds = kinds[: kinds.index("});") + 3]
    assert [line.split(":")[0].strip() for line in kinds.splitlines() if "requestRun: true" in line] == [
        "generate", "candidates"]


# -- containment ---------------------------------------------------------------------------

def test_template_changes_are_confined_to_the_generate_handlers_and_hydration():
    entry, current = _entry(TEMPLATE), _current(TEMPLATE)
    head = current[: current.index("</head>")]
    assert entry[: entry.index("</head>")] == head
    assert entry[entry.index("</head>"):entry.index("<script>")] == current[current.index("</head>"):current.index("<script>")]
    assert entry[entry.rindex("</script>"):] == current[current.rindex("</script>"):]
    assert _declared(entry, "") == _declared(current, "")
    hydration_start = current.index("WorkbenchState.hydrate({")
    allowed = {name: _span(current, _function(current, f"function {name}(")) for name in GENERATE_HANDLERS}
    allowed["hydration"] = (hydration_start, current.index("});", hydration_start) + 3)
    touched = set()
    for start, end in _changed_spans(entry, current):
        owners = {name for name, (low, high) in allowed.items() if low <= start and end <= high}
        assert owners, current[start:end]
        touched |= owners
    assert touched == set(allowed)
    for name in GENERATE_HANDLERS:
        old = _function(entry, f"function {name}(")
        assert old.count('const control = document.getElementById("context").innerText;') == 1


def test_state_module_changes_are_confined_to_run_provenance():
    entry, current = _entry(MODULE), _current(MODULE)
    declared_entry, declared_current = _declared(entry, "    "), _declared(current, "    ")
    assert set(declared_current) - set(declared_entry) == {"serverRun", "requestRun"}
    assert set(declared_entry) <= set(declared_current)
    for name in FROZEN_MODULE_FUNCTIONS:
        assert _function(current, f"function {name}(") == _function(entry, f"function {name}("), name
    changed = {name for name in declared_entry
               if _function(current, f"function {name}(") != _function(entry, f"function {name}(")}
    assert changed == {"snapshot", "begin", "hydrate"}
    snapshot = _function(current, "function snapshot(").replace("            requestRun: requestRun(),\n", "")
    assert snapshot == _function(entry, "function snapshot(")
    begin = _function(current, "function begin(").replace(
        "            requestRun: spec.requestRun ? requestRun() : null,\n", "")
    assert begin == _function(entry, "function begin(")
    hydrate = _function(current, "function hydrate(").replace(
        "run = serverRun(session);",
        "run = Object.freeze({ sessionId: text(session.sessionId), repository: normalizeRepository(session.repository) });")
    assert hydrate == _function(entry, "function hydrate(")
    assert current.replace(", requestRun: true }", " }").count("requestRun: true") == 0
    # The exported API is unchanged: the binding is read through snapshots and tickets.
    exports = current[current.index("global.WorkbenchState = Object.freeze({"):]
    assert exports == entry[entry.index("global.WorkbenchState = Object.freeze({"):]


def test_every_other_request_handler_and_the_dream_review_binding_are_byte_identical():
    entry, current = _entry(TEMPLATE), _current(TEMPLATE)
    for signature in ("function applyPatch(", "function undoPatch(", "function testPatch(", "function selectCandidate(",
                      "async function localCritique(", "async function uploadFolderFiles(", "function setProductMode(",
                      "function renderWorkbench(", "function _renderWorkbenchRepository(",
                      "function _renderWorkbenchCandidate(", "function _bindWorkbenchInputs(",
                      "function _serializeWorkbenchExecution(", "function refreshSessionList(",
                      "function _selectDreamReview(", "function _mountDreamReview(", "function _selectAllDreamReviews(",
                      "function applyDream(", "function _doDreamApply("):
        assert _function(current, signature) == _function(entry, signature), signature


# -- registry, reversal, frozen boundaries and completion -------------------------------------

def test_registry_has_one_complete_ux_context1_phase_directly_after_ux_state1():
    from core.phase_picker import pick_phase_candidates
    from core.phase_registry import load_phase_registry, validate_phase_registry

    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    phases = [phase for phase in registry["phases"] if phase["phase_id"] == "UX.CONTEXT.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "UX" and phase["status"] == "complete"
    assert phase["prerequisites"] == ["UX.STATE.1"]
    ids = [entry["phase_id"] for entry in registry["phases"]]
    assert ids.index("UX.CONTEXT.1") == ids.index("UX.STATE.1") + 1
    assert phase["network_allowed"] is False and phase["model_calls_allowed"] is False
    assert phase["human_approval_required"] is True and phase["merge_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    for frozen in ("core/", "patching/", "web/app.py", "web/routes/", "web/session_store.py",
                   "web/static/request_integrity.js", "web/static/safe_content.js"):
        assert frozen in phase["forbidden_files"], frozen
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_reversal_receipt_reconstructs_every_entry_file_on_the_ux_state1_post_state():
    from tests._ux_context1_maintenance import before_ux_context1

    receipt = json.loads((FIXTURES / "ux_context1_reversal.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "UX.CONTEXT.1"
    assert set(receipt["files"]) == set(EXISTING_FILES_CHANGED)
    anchors = json.loads((FIXTURES / "ux_state1_completion.json").read_text(encoding="utf-8"))["source_sha256"]
    for relative, record in receipt["files"].items():
        restored = before_ux_context1(relative)
        assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"] == anchors[relative], relative
        assert hashlib.sha256(_post_state(relative)).hexdigest() == record["post_sha256"], relative


def test_frozen_phase_boundaries_are_byte_exact():
    manifest = json.loads((FIXTURES / "ux_context1_frozen_boundaries.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "UX.CONTEXT.1"
    for relative, digest in manifest["sha256"].items():
        assert hashlib.sha256(_post_state(relative)).hexdigest() == digest, relative
    groups = manifest["groups"]
    for group in ("UX.STATE.1", "AUTH.WEB.1", "AUTH.WEB.READ.1", "SEC.UI.1", "DATA.UNDO.1", "EXEC.PLAN.1",
                  "AUTH.DREAM.1", "DATA.ROLLBACK.1", "Track_A", "backend_web", "static_assets", "audit"):
        assert groups[group] and set(groups[group]) <= set(manifest["sha256"]), group
    assert {"web/app.py", "web/routes/patch_routes.py", "web/session_store.py", "web/static/request_integrity.js",
            "web/read_host.py", "web/static/safe_content.js", "core/dream_review_binding.py", "core/undo_backup.py",
            "tests/test_ux_state1_browser.py", "tests/fixtures/ux_state1_completion.json"} <= set(manifest["sha256"])
    assert not set(manifest["sha256"]) & set(EXISTING_FILES_CHANGED)


def test_completion_receipt_pins_every_phase_source():
    receipt = json.loads((FIXTURES / "ux_context1_completion.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "UX.CONTEXT.1"
    assert receipt["remaining_findings"] == ["UX-05", "UX-06"]
    assert receipt["model_calls"] == 0 and receipt["external_network_requests"] == 0
    assert set(receipt["frozen_production_deltas"].values()) == {0}
    assert set(receipt["existing_files_changed"]) == set(EXISTING_FILES_CHANGED)
    expected = set(receipt["existing_files_changed"] + receipt["new_files"])
    expected.remove("tests/fixtures/ux_context1_completion.json")
    assert set(receipt["source_sha256"]) == expected
    for relative, digest in receipt["source_sha256"].items():
        assert hashlib.sha256(_post_state(relative)).hexdigest() == digest, relative
