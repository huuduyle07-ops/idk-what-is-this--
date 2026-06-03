from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
_TMPL = TEMPLATE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Session controls
# ---------------------------------------------------------------------------

def test_session_refresh_function_defined():
    assert "function refreshSessionList(" in _TMPL


def test_session_history_endpoint_referenced():
    assert "/history/sessions" in _TMPL


def test_session_include_archived_param():
    assert "include_archived=1" in _TMPL


def test_session_delete_confirm_string():
    assert "DELETE_SESSION" in _TMPL


def test_session_archive_and_delete_endpoints():
    t = _TMPL
    assert "/history/session/archive" in t
    assert "/history/session/delete" in t


# ---------------------------------------------------------------------------
# Benchmark controls
# ---------------------------------------------------------------------------

def test_benchmark_archived_toggle_id():
    assert 'id="showArchivedBenchmarks"' in _TMPL


def test_benchmark_delete_confirm_string():
    assert "DELETE_BENCHMARK_REPORT" in _TMPL


def test_benchmark_update_endpoint():
    assert "/history/benchmark/update" in _TMPL


def test_benchmark_delete_endpoint():
    assert "/history/benchmark/delete" in _TMPL


def test_benchmark_pinned_guard_phrase():
    assert "Unpin before deleting" in _TMPL


# ---------------------------------------------------------------------------
# Dream controls
# ---------------------------------------------------------------------------

def test_dream_archived_toggle_id():
    assert 'id="showArchivedDreamRuns"' in _TMPL


def test_dream_delete_confirm_string():
    assert "DELETE_DREAM_RUN" in _TMPL


def test_dream_update_endpoint():
    assert "/history/dream/update" in _TMPL


def test_dream_delete_endpoint():
    assert "/history/dream/delete" in _TMPL


def test_dream_pinned_guard_phrase():
    assert "Unpin before deleting" in _TMPL


# ---------------------------------------------------------------------------
# Execution fence
# ---------------------------------------------------------------------------

def test_history_actions_do_not_invoke_execution_endpoints():
    """No line containing a /history/* route path may also invoke an
    execution function — history-actions handlers must never trigger runs."""
    EXEC_FNS = [
        "start_benchmark_run_async",
        "start_overnight_async",
        "run_gemini_request",
        "promote_lesson",
    ]
    HISTORY_ROUTES = [
        "/history/session",
        "/history/benchmark",
        "/history/dream",
    ]
    lines = _TMPL.splitlines()
    for line in lines:
        if any(route in line for route in HISTORY_ROUTES):
            for fn in EXEC_FNS:
                assert fn not in line, (
                    f"Execution fn '{fn}' found on same line as history route: {line!r}"
                )
