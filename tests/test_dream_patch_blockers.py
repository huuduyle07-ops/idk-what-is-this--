import shutil
import subprocess
from pathlib import Path

from core import dream_artifacts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _codes(blockers):
    return {blocker["code"] for blocker in blockers}


def test_safe_to_patch_now_false_creates_blocker():
    blockers = dream_artifacts.classify_patch_blockers(
        {"status": "planned_no_patch"},
        {"safe_to_patch_now": False},
    )

    assert "safe_to_patch_false" in _codes(blockers)


def test_empty_validation_commands_creates_blocker_for_patch_if_safe():
    blockers = dream_artifacts.classify_patch_blockers(
        {"status": "planned_no_patch"},
        {"dream_mode": "patch_if_safe", "validation_commands": []},
    )

    assert "missing_validation_command" in _codes(blockers)


def test_empty_likely_files_creates_target_uncertain_blocker():
    blockers = dream_artifacts.classify_patch_blockers(
        {"status": "planned_no_patch"},
        {"likely_files": []},
    )

    assert "target_file_uncertain" in _codes(blockers)


def test_patch_style_required_none_creates_blocker():
    blockers = dream_artifacts.classify_patch_blockers(
        {"status": "planned_no_patch"},
        {"patch_style_required": "none"},
    )

    assert "patch_style_none" in _codes(blockers)


def test_patch_skipped_needs_vibe_creates_vibe_required_blocker():
    blockers = dream_artifacts.classify_patch_blockers(
        {"status": "patch_skipped_needs_vibe"},
    )

    assert "vibe_required" in _codes(blockers)


def test_planned_no_patch_patch_if_safe_without_payload_creates_generation_failed():
    blockers = dream_artifacts.classify_patch_blockers(
        {"status": "planned_no_patch"},
        {"dream_mode": "patch_if_safe"},
    )

    assert "patch_generation_failed" in _codes(blockers)


def _extract_between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_ui_renderer_includes_patch_blocker_badge_and_text():
    template = (PROJECT_ROOT / "web" / "templates" / "index.html").read_text(
        encoding="utf-8",
    )

    if not shutil.which("node"):
        assert "why no patch" in template
        assert "patch_blockers" in template
        assert "dream-patch-blocker-badge" in template
        return

    renderer = _extract_between(
        template,
        "function _dreamStatusClass",
        "// ============================================================\n// Phase 5 Slice 5",
    )
    escape_html = _extract_between(
        template,
        "function _escapeHtml",
        "function _renderHealth",
    )
    script = f"""
{renderer}
{escape_html}
const html = _renderDreamItemCard({{
    idx: 1,
    kind: "bug",
    title: "No patch",
    status: "planned_no_patch",
    patch_blocker_summary: "why no patch: safe_to_patch_false",
    patch_blockers: [{{
        code: "safe_to_patch_false",
        message: "Planner marked this item as not safe to patch now.",
        evidence: "safe_to_patch_now=false"
    }}]
}});
console.log(html);
"""
    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
    )

    assert "why no patch" in result.stdout
    assert "safe_to_patch_false" in result.stdout
    assert "Planner marked this item as not safe to patch now." in result.stdout
