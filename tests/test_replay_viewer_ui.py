"""Template guards for the Phase 13R.2 replay viewer panel."""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _group_segment(template: str, group: str) -> str:
    start_marker = f'data-ui-group="{group}"'
    end_marker = f"<!-- /{group} -->"
    start = template.index(start_marker)
    end = template.index(end_marker, start)
    return template[start:end]


def _replay_panel_segment(template: str) -> str:
    start = template.index('class="health-section replay-debugger-section"')
    end = template.index("</div>\n          </details>", start)
    return template[start:end]


def _replay_js_segment(template: str) -> str:
    start = template.index("// Phase 13R.2: Replay Debugger panel.")
    end = template.index("// Phase 5 Slice 3: Benchmarks panel", start)
    return template[start:end]


def test_replay_panel_exists_inside_settings_debug():
    template = _template()
    debug = _group_segment(template, "settings-debug")

    assert "Replay Debugger" in debug
    assert 'id="replayList"' in debug
    assert 'id="replayDetail"' in debug
    assert 'onclick="loadReplays(true)"' in debug
    assert "Refresh replays" in debug
    assert "Replay viewer is read-only" in debug
    assert ".agent/replays" in debug


def test_replay_panel_is_not_primary_or_dangerous_config_ui():
    template = _template()
    panel = _replay_panel_segment(template)
    harness = _group_segment(template, "settings-harness")

    assert 'id="replayList"' not in harness
    assert "generatePatch()" not in panel
    assert "applyPatch()" not in panel
    assert "runAllBenchmarks()" not in panel
    assert "startOvernight()" not in panel


def test_replay_artifact_sections_are_listed_in_ui_renderer():
    js = _replay_js_segment(_template())
    for name in (
        "user_query.txt",
        "control_result.json",
        "scout_snippets.json",
        "active_lessons_injected.json",
        "model_prompt.txt",
        "model_raw_response.txt",
        "patch_parsed.json",
        "apply_result.json",
        "validation_output.txt",
        "self_correct_attempts.json",
        "brain_stamp.json",
        "final_status.json",
    ):
        assert name in js


def test_replay_panel_has_no_delete_or_execution_buttons():
    template = _template()
    panel = _replay_panel_segment(template)
    js = _replay_js_segment(template)

    button_texts = [
        re.sub(r"<[^>]+>", "", text).strip().lower()
        for text in re.findall(r"<button\b[^>]*>(.*?)</button>", panel, re.S)
    ]
    assert button_texts == ["refresh replays"]

    forbidden_tokens = (
        "deleteReplay",
        "rerunReplay",
        "replayRun",
        "applyPatch(",
        "runAllBenchmarks(",
        "startOvernight(",
        "run_validation_command",
        "run_patch_plan",
    )
    for token in forbidden_tokens:
        assert token not in js


def test_replay_fetches_are_get_only_and_route_scoped():
    js = _replay_js_segment(_template())

    assert "fetch(`/replays?repo_path=${encodeURIComponent(repo)}&limit=50`)" in js
    assert "fetch(`/replays/${encodeURIComponent(replayId)}?repo_path=${encodeURIComponent(repo)}`)" in js
    assert 'method: "POST"' not in js
    assert "fetch(\"/replays" not in js


def test_artifact_text_is_escaped_and_large_preview_note_exists():
    js = _replay_js_segment(_template())

    assert '_escapeHtml(artifact.preview || "")' in js
    assert "_escapeHtml(JSON.stringify(manifest, null, 2))" in js
    assert "Preview truncated at" in js
    assert "innerHTML = artifact.preview" not in js


def test_json_artifacts_are_rendered_as_json_type_when_marked_by_route():
    js = _replay_js_segment(_template())

    assert 'artifact.content_type === "json"' in js
    assert 'const type = artifact.content_type === "json" ? "json" : "text";' in js
    assert 'replay-artifact__pre--${_escapeHtml(type)}' in js


def test_existing_web_controls_and_ids_are_preserved():
    template = _template()
    for token in (
        'id="repoPathInput"',
        'id="primarySubmit"',
        'id="healthList"',
        'id="toolRegistryList"',
        'id="mcpAuditList"',
        'id="harnessControlsList"',
        "generatePatch()",
        "applyPatch()",
        "loadToolRegistry(true)",
        "loadMcpAudit(true)",
    ):
        assert token in template


def test_replay_ui_text_guard_has_no_privileged_backend_tokens():
    text = (_replay_panel_segment(_template()) + _replay_js_segment(_template())).lower()
    forbidden = (
        "subprocess",
        "docker.from_env",
        "run_benchmarks",
        "run_validation_command",
        "run_patch_plan_with_artifacts",
        "run_gemini_request",
        "run_deepseek_review",
        "openai",
        "anthropic",
        "google.genai",
        "database.",
        "unlink(",
        "rmtree(",
        "remove(",
    )
    for token in forbidden:
        assert token not in text
