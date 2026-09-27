"""UX.STATE.1: one frontend owner for repository, request, candidate, action and mode state.

Static and contract checks over the shipped template and static assets.  The
behavior (UX-02 races, UX-03 Undo outcomes, UX-04 mode round trips) is proven in
real Chromium by tests/test_ux_state1_browser.py.  No model, database or
network is used here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TEMPLATE = ROOT / "web" / "templates" / "index.html"
MODULE = ROOT / "web" / "static" / "workbench_state.js"
TRANSPORT = ROOT / "web" / "static" / "request_integrity.js"

# Handlers that read or change repository, candidate, action or mode state.
REPAIRED_HANDLERS = (
    "function setProductMode(",
    "function applyPatch(",
    "function generatePatch(",
    "function undoPatch(",
    "function generateCandidates(",
    "function testPatch(",
    "function selectCandidate(",
    "async function localCritique(",
    "async function uploadFolderFiles(",
)
DISPATCHING_HANDLERS = (
    "function applyPatch(",
    "function generatePatch(",
    "function undoPatch(",
    "function generateCandidates(",
    "function testPatch(",
    "async function localCritique(",
    "async function uploadFolderFiles(",
)
DREAM_REVIEW_FUNCTIONS = (
    "function _selectDreamReview(",
    "function _mountDreamReview(",
    "function _selectAllDreamReviews(",
    "function applyDream(",
    "function _doDreamApply(",
)


def _template() -> str:
    # Byte-exact (CRLF kept) so it compares with the reconstructed entry bytes.
    return TEMPLATE.read_bytes().decode("utf-8")


def _function(source: str, signature: str) -> str:
    """Return one top-level JS function declaration, matched by braces."""
    start = source.index(signature)
    index = source.index("{", source.index(")", start))
    depth, quote, escaped = 0, "", False
    line_comment = block_comment = False
    while index < len(source):
        char, pair = source[index], source[index:index + 2]
        if line_comment:
            line_comment = char != "\n"
        elif block_comment:
            if pair == "*/":
                block_comment, index = False, index + 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif pair == "//":
            line_comment = True
        elif pair == "/*":
            block_comment = True
        elif char in "\"'`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
        index += 1
    raise AssertionError(f"unterminated function {signature}")


def _entry_template() -> str:
    from tests._ux_state1_maintenance import before_ux_state1

    return before_ux_state1("web/templates/index.html").decode("utf-8")


def _before_ux_context1(relative: str) -> bytes:
    # Later phases edit some pinned files; their receipts are undone first.
    from tests._ux_context1_maintenance import before_ux_context1

    return before_ux_context1(relative)


# -- the state owner ------------------------------------------------------------------

def test_one_local_state_module_is_loaded_after_the_security_assets_and_before_the_page_script():
    template = _template()
    head = template[: template.index("</head>")]
    scripts = re.findall(r"<script\b[^>]*>", head)
    assert "filename='request_integrity.js'" in scripts[0]
    assert sum("workbench_state.js" in tag for tag in scripts) == 1
    order = [head.index(f"filename='{name}'") for name in
             ("request_integrity.js", "vendor/dompurify/purify.min.js", "safe_content.js", "workbench_state.js")]
    assert order == sorted(order)
    assert head.index("filename='workbench_state.js'") < template.index("<script>")
    assert MODULE.is_file()


def test_state_module_owns_state_only_no_transport_storage_dom_or_authority():
    module = MODULE.read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "sendBeacon", "EventSource", "WebSocket", "document.", "window.",
                      "localStorage", "sessionStorage", "cookie", "innerHTML", "outerHTML", "insertAdjacentHTML",
                      "eval(", "new Function", "csrf", "CSRF", "X-CATTUS", "web_auth_token", "AbortController",
                      "candidate_fingerprint =", "sha256(", "crypto."):
        assert forbidden not in module, forbidden
    assert "global.WorkbenchState = Object.freeze(" in module
    for vocabulary in ('"idle"', '"pending"', '"succeeded"', '"failed"', '"context_changed"', '"superseded"',
                       '"candidate_changed"', '"retrieve"', '"plan"'):
        assert vocabulary in module, vocabulary


def test_request_integrity_remains_transport_only():
    transport = TRANSPORT.read_text(encoding="utf-8")
    for workflow in ("WorkbenchState", "contextGeneration", "candidate", "setMode", "apply_policy", "repo_path",
                     "last_action", "undo"):
        assert workflow not in transport, workflow
    module = MODULE.read_text(encoding="utf-8")
    for transport_name in ("CattusRequestIntegrity", "protectedFetch", "refreshSession"):
        assert transport_name not in module


def test_context_invalidation_hook_is_generic_and_dormant():
    module = MODULE.read_text(encoding="utf-8")
    assert "function invalidate(reason)" in module and "        invalidate,\n" in module
    from tests._repair_intent1_maintenance import before_repair_intent1
    template = before_repair_intent1("web/templates/index.html", TEMPLATE.read_bytes()).decode("utf-8")
    # No read-authentication policy: nothing invalidates on sign-in or transport events yet.
    assert "WorkbenchState.invalidate(" not in template
    assert "cattus:request-integrity" not in template and "cattus:request-integrity" not in module


# -- bounded ownership regression ---------------------------------------------------

def test_repaired_handlers_never_write_owned_state_directly():
    template = _template()
    owned_writes = (
        re.compile(r"last_action"),
        re.compile(r"_setPatchState\("),
        re.compile(r"patchRawJson"),
        re.compile(r"patchCandidates"),
        re.compile(r"(repoInput|repo_path'\]\"\)|repoPathInput\"\))\??\.value\s*=(?!=)"),
        re.compile(r"(modeSelect|applyPolicy|webModeInput)\"?\)?\??\.value\s*=(?!=)"),
        re.compile(r"dataset\.productMode\s*=(?!=)"),
        re.compile(r"primarySubmit\"?\)?\.textContent\s*=(?!=)"),
    )
    for signature in REPAIRED_HANDLERS:
        body = _function(template, signature)
        for pattern in owned_writes:
            assert not pattern.search(body), (signature, pattern.pattern)
    for signature in DISPATCHING_HANDLERS:
        body = _function(template, signature)
        assert "WorkbenchState.begin(" in body, signature
        assert "WorkbenchState.settle(" in body, signature


def test_owned_state_has_one_projection_in_the_template():
    template = _template()
    script = template[template.index("<script>"):]
    renderer = _function(template, "function renderWorkbench(")
    candidate_renderer = _function(template, "function _renderWorkbenchCandidate(")
    mode_renderer = _function(template, "function _renderWorkbenchMode(")
    # _setPatchState: its definition plus the single candidate projection.
    assert script.count("_setPatchState(") == 2 and "_setPatchState(" in candidate_renderer
    assert script.count("last_action:") == 2  # _currentPatchState's field and the projection
    assert "last_action:" in candidate_renderer
    assert "WorkbenchState.describeAction(" in candidate_renderer
    writes = re.findall(r"(modeSelect|applyPolicy|webModeInput)\.value\s*=(?!=)", script)
    assert len(writes) == 6  # the mode projection and submit serialization each write all three fields
    assert len(re.findall(r"(modeSelect|applyPolicy|webModeInput)\.value\s*=(?!=)", mode_renderer)) == 3
    assert "_renderWorkbenchMode(view)" in renderer and "_renderWorkbenchCandidate(view)" in renderer
    assert script.count("WorkbenchState.subscribe(renderWorkbench)") == 1
    assert script.count("WorkbenchState.hydrate(") == 1


def test_mode_transitions_are_requested_never_assigned():
    template = _template()
    body = _function(template, "function setProductMode(")
    assert "WorkbenchState.setMode(" in body
    assert "retrieve" not in body and "plan" not in body
    submit = template[template.index('document.addEventListener("submit"'):]
    submit = submit[: submit.index("});") + 3]
    assert "_serializeWorkbenchExecution(" in submit
    assert '"retrieve"' not in submit and '"plan"' not in submit
    assert "setProductMode('chat')" in template and "setProductMode('instant')" in template


def test_undo_success_requires_the_structured_data_undo1_receipt():
    module = MODULE.read_text(encoding="utf-8")
    outcome = module[module.index("function undoOutcome("):]
    outcome = outcome[: outcome.index("\n    }\n") + 6]
    for required in ("success !== true", "backup_id", "transaction_id", "restored_sha256", '"undo_receipt_incomplete"',
                     '"undo_failed"'):
        assert required in outcome, required
    handler = _function(_template(), "function undoPatch(")
    assert "WorkbenchState.undoOutcome(" in handler
    assert '"undone"' not in handler


def test_dream_review_binding_is_untouched():
    template, entry = _template(), _entry_template()
    for signature in DREAM_REVIEW_FUNCTIONS:
        assert _function(template, signature) == _function(entry, signature), signature
        assert "WorkbenchState" not in _function(template, signature)


def test_repaired_handlers_add_no_html_sink():
    template = _template()
    for signature in REPAIRED_HANDLERS:
        body = _function(template, signature)
        current = len(re.findall(r"\.innerHTML\s*=", body))
        try:
            previous = len(re.findall(r"\.innerHTML\s*=", _function(_entry_template(), signature)))
        except ValueError:
            previous = 0
        assert current <= previous, signature
        assert not re.search(r"outerHTML\s*=|insertAdjacentHTML|document\.write", body), signature


# -- registry -----------------------------------------------------------------------

def test_registry_has_one_complete_ux_phase_and_picker_is_unchanged():
    from core.phase_picker import pick_phase_candidates
    from core.phase_registry import load_phase_registry, validate_phase_registry

    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    phases = [phase for phase in registry["phases"] if phase["phase_id"] == "UX.STATE.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "UX" and phase["status"] == "complete"
    assert phase["prerequisites"] == ["AUTH.WEB.READ.1"]
    ids = [entry["phase_id"] for entry in registry["phases"]]
    assert ids.index("UX.STATE.1") == ids.index("AUTH.WEB.READ.1") + 1
    assert phase["network_allowed"] is False and phase["model_calls_allowed"] is False
    assert phase["human_approval_required"] is True and phase["merge_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


# -- containment, frozen boundaries and receipts ---------------------------------------

EXISTING_FILES_CHANGED = (
    "web/templates/index.html",
    "docs/roadmap/phase_registry.json",
    "tests/test_phase_registry.py",
    "tests/test_phase_picker.py",
    "tests/_auth_web_read1_maintenance.py",
    "tests/test_auth_web_read1.py",
    "tests/test_auth_web1.py",
    "tests/test_data_undo1.py",
    "tests/test_web_ui_command_hierarchy.py",
    "tests/test_web_ui_cutoff_1.py",
    "tests/test_web_ui_demo_flow.py",
    "tests/test_web_ui_information_architecture.py",
    "tests/test_web_ui_result_readability.py",
)


def test_template_markup_is_unchanged_outside_one_script_tag_and_the_page_script():
    import difflib

    from tests._repair_intent1_maintenance import before_repair_intent1
    entry = _entry_template()
    current = before_repair_intent1("web/templates/index.html", TEMPLATE.read_bytes()).decode("utf-8")
    head_delta = [line for line in difflib.ndiff(entry[: entry.index("</head>")].splitlines(True),
                                                 current[: current.index("</head>")].splitlines(True))
                  if line[:2] in {"+ ", "- "}]
    assert len(head_delta) == 1 and head_delta[0].startswith("+ ")
    assert "filename='workbench_state.js'" in head_delta[0]
    # Body markup (everything before the page script) and the document tail are identical.
    assert entry[entry.index("</head>"):entry.index("<script>")] == current[current.index("</head>"):current.index("<script>")]
    assert entry[entry.rindex("</script>"):] == current[current.rindex("</script>"):]


def test_reversal_receipt_reconstructs_every_entry_file_on_the_auth_web_read1_post_state():
    from tests._ux_state1_maintenance import before_ux_state1

    receipt = json.loads((FIXTURES / "ux_state1_reversal.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "UX.STATE.1"
    assert set(receipt["files"]) == set(EXISTING_FILES_CHANGED)
    anchors: dict[str, str] = {}
    for name, key in (("auth_web1_completion.json", "source_sha256"), ("auth_web1_reversal.json", "files"),
                      ("auth_web_read1_frozen_boundaries.json", "sha256"),
                      ("auth_web_read1_completion.json", "source_sha256"), ("auth_web_read1_reversal.json", "files")):
        for relative, value in json.loads((FIXTURES / name).read_text(encoding="utf-8"))[key].items():
            anchors[relative] = value["post_sha256"] if isinstance(value, dict) else value
    anchored = 0
    for relative, record in receipt["files"].items():
        restored = before_ux_state1(relative)
        assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
        assert hashlib.sha256(_before_ux_context1(relative)).hexdigest() == record["post_sha256"], relative
        if relative in anchors:
            anchored += 1
            assert record["entry_sha256"] == anchors[relative], relative
    assert anchored == len(EXISTING_FILES_CHANGED) - 1  # tests/test_data_undo1.py predates both AUTH.WEB phases


def test_frozen_phase_boundaries_are_byte_exact():
    manifest = json.loads((FIXTURES / "ux_state1_frozen_boundaries.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "UX.STATE.1"
    for relative, digest in manifest["sha256"].items():
        assert hashlib.sha256(_before_ux_context1(relative)).hexdigest() == digest, relative
    groups = manifest["groups"]
    for group in ("AUTH.WEB.1", "AUTH.WEB.READ.1", "SEC.UI.1", "DATA.UNDO.1", "EXEC.PLAN.1", "AUTH.DREAM.1",
                  "DATA.ROLLBACK.1", "Track_A", "backend_web", "static_assets", "audit"):
        assert groups[group] and set(groups[group]) <= set(manifest["sha256"]), group
    assert {"web/static/request_integrity.js", "web/read_host.py", "web/app.py", "web/static/safe_content.js",
            "core/undo_backup.py", "core/dream_review_binding.py", "core/human_apply_authorization.py",
            "web/routes/patch_routes.py"} <= set(manifest["sha256"])
    assert not set(manifest["sha256"]) & set(EXISTING_FILES_CHANGED)


def test_completion_receipt_pins_every_phase_source():
    receipt = json.loads((FIXTURES / "ux_state1_completion.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "UX.STATE.1"
    assert receipt["closed_findings"] == ["UX-02", "UX-03", "UX-04"]
    assert receipt["remaining_findings"] == ["UX-05", "UX-06"]
    assert receipt["model_calls"] == 0 and receipt["external_network_requests"] == 0
    assert set(receipt["frozen_production_deltas"].values()) == {0}
    assert set(receipt["existing_files_changed"]) == set(EXISTING_FILES_CHANGED)
    expected = set(receipt["existing_files_changed"] + receipt["new_files"])
    expected.remove("tests/fixtures/ux_state1_completion.json")
    assert set(receipt["source_sha256"]) == expected
    for relative, digest in receipt["source_sha256"].items():
        assert hashlib.sha256(_before_ux_context1(relative)).hexdigest() == digest, relative
