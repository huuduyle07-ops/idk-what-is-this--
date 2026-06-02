"""Phase 5P.1 — Dream report Markdown rendering.

The Dream report viewer used to dump the morning report into a plain
``<pre>`` block. Phase 5P.1 renders that Markdown into safe HTML so headings,
lists, code, and tables read properly. The renderer is a tiny, self-contained,
escape-by-default converter living in ``web/dream_report_markdown.py``.

Why a hand-rolled renderer instead of the project's ``markdown`` dependency:
``markdown.markdown`` passes raw HTML through unescaped (so ``<script>`` would
execute) and double-escapes code spans when the input is pre-escaped. This
renderer escapes HTML exactly once and never emits raw HTML, satisfying the
"escape by default / no raw HTML execution" safety requirement.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from web.dream_report_markdown import render_dream_report_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Renderer — headings, paragraphs
# ---------------------------------------------------------------------------

def test_headings_convert_to_safe_heading_tags():
    out = render_dream_report_markdown("# Top\n\n## Sub\n\n### Deep")
    assert "<h1>Top</h1>" in out
    assert "<h2>Sub</h2>" in out
    assert "<h3>Deep</h3>" in out


def test_paragraph_text_is_wrapped_and_escaped():
    out = render_dream_report_markdown("Plain line with <angle> & amp.")
    assert "<p>" in out and "</p>" in out
    assert "&lt;angle&gt;" in out
    assert "&amp;" in out
    # The literal raw angle bracket must never survive into the markup.
    assert "<angle>" not in out


# ---------------------------------------------------------------------------
# Renderer — lists
# ---------------------------------------------------------------------------

def test_bullet_list_renders_as_unordered_list():
    out = render_dream_report_markdown("- one\n- two\n- three")
    assert "<ul>" in out and "</ul>" in out
    assert "<li>one</li>" in out
    assert "<li>two</li>" in out
    assert "<li>three</li>" in out


def test_numbered_list_renders_as_ordered_list():
    out = render_dream_report_markdown("1. first\n2. second")
    assert "<ol>" in out and "</ol>" in out
    assert "<li>first</li>" in out
    assert "<li>second</li>" in out


def test_nested_bullet_list_indents_into_sublist():
    out = render_dream_report_markdown("- parent\n  - child")
    # The child becomes a nested <ul> inside the parent <li>.
    assert out.count("<ul>") == 2
    assert "<li>child</li>" in out


def test_marker_switch_within_list_block_keeps_all_items():
    """Regression: a ul->ol->ul switch at the same indent must not silently
    drop the items after the switch (Phase 5P.1 review finding)."""
    out = render_dream_report_markdown("- a\n- b\n1. c\n2. d\n- e")
    for needle in ("<li>a</li>", "<li>b</li>", "<li>c</li>", "<li>d</li>", "<li>e</li>"):
        assert needle in out, f"dropped {needle}: {out}"
    # The ordered run renders as its own <ol>; the bullet runs as <ul>.
    assert "<ol>" in out and "<ul>" in out


def test_multiline_field_injecting_ordered_marker_keeps_following_bullets():
    """Mirrors the real morning_report.txt shape where an LLM-controlled summary
    spilled a numbered line into the bullet block. The trailing artifacts bullet
    must still render — no content is lost."""
    src = (
        "## Items\n\n"
        "- status: **ok**\n"
        "- summary: do these:\n"
        "1. first step\n"
        "2. second step\n"
        "- artifacts: `x/`\n"
    )
    out = render_dream_report_markdown(src)
    assert "<li>first step</li>" in out
    assert "<li>second step</li>" in out
    assert "artifacts:" in out
    assert "<code>x/</code>" in out


# ---------------------------------------------------------------------------
# Renderer — code
# ---------------------------------------------------------------------------

def test_fenced_code_block_renders_escaped_pre_code():
    src = "```\n<b>hi</b>\nx = a < b\n```"
    out = render_dream_report_markdown(src)
    assert "<pre><code>" in out
    assert "</code></pre>" in out
    # Code content is escaped exactly once — no raw tags, no double escaping.
    assert "&lt;b&gt;hi&lt;/b&gt;" in out
    assert "a &lt; b" in out
    assert "<b>hi</b>" not in out
    assert "&amp;lt;" not in out


def test_inline_code_renders_code_span_escaped_once():
    out = render_dream_report_markdown("use `a < b` here")
    assert "<code>a &lt; b</code>" in out
    assert "&amp;lt;" not in out


def test_bold_and_inline_code_combine_in_a_line():
    out = render_dream_report_markdown("- status: **ready** see `app.py`")
    assert "<strong>ready</strong>" in out
    assert "<code>app.py</code>" in out


# ---------------------------------------------------------------------------
# Renderer — tables (the real morning report uses pipe tables)
# ---------------------------------------------------------------------------

def test_pipe_table_renders_table_with_headers_and_rows():
    src = (
        "| Pattern | Case |\n"
        "| --- | --- |\n"
        "| retry | add-retry |\n"
    )
    out = render_dream_report_markdown(src)
    assert "<table>" in out and "</table>" in out
    assert "<th>Pattern</th>" in out
    assert "<th>Case</th>" in out
    assert "<td>retry</td>" in out
    assert "<td>add-retry</td>" in out


# ---------------------------------------------------------------------------
# Renderer — security: raw HTML / scripts are escaped, never executed
# ---------------------------------------------------------------------------

def test_raw_script_is_escaped_not_executed():
    out = render_dream_report_markdown("Hello <script>alert(1)</script> world")
    assert "<script>" not in out
    assert "</script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_event_handler_html_is_escaped():
    out = render_dream_report_markdown('<img src=x onerror="alert(1)">')
    assert "<img" not in out
    assert "onerror=" not in out or "&lt;img" in out
    assert "&lt;img" in out


def test_empty_input_is_safe():
    assert render_dream_report_markdown("") == ""
    assert render_dream_report_markdown(None) == ""


# ---------------------------------------------------------------------------
# Route wiring — /dream/report exposes rendered HTML for the viewer
# ---------------------------------------------------------------------------

def test_dream_report_route_returns_rendered_morning_html(client, tmp_path, monkeypatch):
    from core import dream_artifacts

    repo = tmp_path / "repo"
    repo.mkdir()
    dreams = tmp_path / "dreams"
    date = "2026-06-02"
    run = "010203-run"
    report_dir = dreams / date / run
    report_dir.mkdir(parents=True)
    (report_dir / "morning_report.txt").write_text(
        "# Morning report\n\n- one\n- two\n", encoding="utf-8"
    )
    (report_dir / "list.json").write_text(
        json.dumps({"items": [], "dream_mode": "research"}), encoding="utf-8"
    )
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    resp = client.get(f"/dream/report?repo_path={repo}&date={date}&run={run}")
    assert resp.status_code == 200
    body = resp.get_json()
    # New field carries the rendered HTML the modal injects.
    assert "morning_report_html" in body
    assert "<h1>Morning report</h1>" in body["morning_report_html"]
    assert "<li>one</li>" in body["morning_report_html"]
    # The raw text is still present so older clients / fallbacks keep working.
    assert body["morning_report"].startswith("# Morning report")


def test_dream_report_route_html_escapes_injected_markup(client, tmp_path, monkeypatch):
    from core import dream_artifacts

    repo = tmp_path / "repo"
    repo.mkdir()
    dreams = tmp_path / "dreams"
    date = "2026-06-02"
    run = "020304-run"
    report_dir = dreams / date / run
    report_dir.mkdir(parents=True)
    (report_dir / "morning_report.txt").write_text(
        "<script>alert(1)</script>", encoding="utf-8"
    )
    (report_dir / "list.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    resp = client.get(f"/dream/report?repo_path={repo}&date={date}&run={run}")
    body = resp.get_json()
    assert "<script>" not in body["morning_report_html"]
    assert "&lt;script&gt;" in body["morning_report_html"]


# ---------------------------------------------------------------------------
# Template wiring — the modal uses the renderer output, not a raw <pre> dump
# ---------------------------------------------------------------------------

def test_index_template_uses_morning_report_html():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "morning_report_html" in tpl
    assert "dream-report-md" in tpl


def test_style_sheet_styles_rendered_report():
    styles = STYLE_SHEET.read_text(encoding="utf-8")
    assert ".dream-report-md" in styles


# ---------------------------------------------------------------------------
# Safety guards — renderer is import-pure, no routes removed
# ---------------------------------------------------------------------------

def test_renderer_module_is_import_pure():
    import web.dream_report_markdown as mod

    src = Path(mod.__file__).read_text(encoding="utf-8").lower()
    forbidden = [
        "subprocess",
        "patch_engine",
        "patch_plan_executor",
        "patch_planner",
        "run_patch_plan",
        "run_benchmarks",
        "benchmark_runner",
        "anthropic",
        "openai",
        "google.genai",
        "litellm",
        "run_gemini_request",
        "agents.gemini_client",
        "agents.deepseek_client",
        "agents.ollama_client",
        "urllib.request",
        "seed_lesson",
        "promote_lesson",
    ]
    for needle in forbidden:
        assert needle not in src, f"renderer leaked a forbidden import/usage: {needle}"


def test_dream_routes_still_registered():
    from web.app import app

    rules = {r.rule for r in app.url_map.iter_rules()}
    for route in [
        "/dream/report",
        "/dream/reports",
        "/dream/taxonomy",
        "/dream/trials/create",
        "/dream/trials/list",
        "/dream/trials/file",
        "/dream/queue",
    ]:
        assert route in rules, f"route disappeared: {route}"
