"""Independent, offline acceptance scenarios at the public web-runner boundary.

These tests author a new toy repository instead of using product fixtures. Only
provider responses and optional persistence/configuration are substituted. Real
routing, inventory, localization, patch gates, probes and subprocess validation
run. Timings therefore measure local harness overhead, not live-model latency.

One exception, declared per scenario: INDENT.SEMANTICS.1 widened the
indentation_style matrix to eight cases, and no candidate within safe_minimal's
budget is known to close it, so the scenarios that need a verified candidate
run the five-case DEFECT.PROBE.LIVE.5 oracle (``oracle="live5"``, through
tests/_matrix_history.py).  One scenario runs the same CORRECT candidate
against the product's own eight cases and records the rejection.
"""
from __future__ import annotations

import hashlib
import json
import socket
import textwrap
import time
from pathlib import Path

import pytest


ORIGINAL = textwrap.dedent('''\
def describe_margin(text):
    sizes = []
    for row in text.splitlines():
        if row.startswith("    "):
            sizes.append("4space")
        elif row.startswith("  "):
            sizes.append("2space")
    return max(sizes, key=sizes.count) if sizes else None
''')
DEAD_GUARD = ORIGINAL.replace(
    'elif row.startswith("  "):',
    'elif row.startswith("  ") and not row.startswith("    "):',
)
#: A raw-width unit inference: the common unit of every row's leading-space
#: width.  Correct under the five-case DEFECT.PROBE.LIVE.5 oracle, which is what
#: these scenarios mean by CORRECT.  INDENT.SEMANTICS.1's eight-case oracle
#: rejects it — continuation alignment and docstring interiors are not
#: indentation — so the scenarios that need it verified declare the five-case
#: oracle, and one scenario records the eight-case verdict.
CORRECT = textwrap.dedent('''\
def describe_margin(text):
    sizes = []
    for row in text.splitlines():
        amount = 0
        for char in row:
            if char != " ":
                break
            amount += 1
        if amount:
            sizes.append(amount)
    unit = 0
    for amount in sizes:
        while amount:
            unit, amount = amount, unit % amount
    return "2space" if unit == 2 else "4space" if unit == 4 else None
''')
FSTRING_CORRECT = CORRECT.replace(
    'return "2space" if unit == 2 else "4space" if unit == 4 else None',
    'return f"{unit}space" if unit else None',
)
OVERFIT = ORIGINAL.replace(
    'return max(sizes, key=sizes.count) if sizes else None',
    'return "2space" if sizes else None',
)

REPO_TESTS = textwrap.dedent('''\
from margin_meter import describe_margin

def test_describe_margin_four_space_layout():
    assert describe_margin("root\\n    child\\n        grandchild\\n") == "4space"

def test_describe_margin_empty_layout():
    assert describe_margin("root\\n") is None
''')
FAILING_REPO_TESTS = REPO_TESTS + textwrap.dedent('''\

def test_describe_margin_two_space_layout():
    assert describe_margin("root\\n  child\\n    grandchild\\n    peer\\n") == "2space"

def test_describe_margin_depth_only_layout():
    assert describe_margin("root\\n      child\\n        grandchild\\n") == "2space"
''')


def _candidate(patched, relative_path="margin_meter.py"):
    return json.dumps({
        "summary": "Correct describe_margin in margin_meter.py.",
        "confidence": 0.99,
        "needs_escalation": False,
        "patch_candidate": {
            "relative_path": relative_path,
            "target_node_name": "describe_margin",
            "target_snippet": ORIGINAL.rstrip(),
            "patched_snippet": patched.rstrip(),
        },
    })


def _source_snapshot(repo):
    # Generated harness metadata and pytest caches may legitimately be written.
    return {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in repo.rglob("*")
        if path.is_file() and path.suffix in {".py", ".ini", ".md", ".bak"}
        and not any(part.startswith(".") for part in path.relative_to(repo).parts)
    }


@pytest.fixture
def run_scenario(tmp_path, monkeypatch, record_property):
    monkeypatch.setenv("DB_ENABLED", "false")
    monkeypatch.setenv("INDEX_USE_EMBEDDINGS", "false")
    monkeypatch.setenv("AUTO_PATCH_ENABLED", "false")
    monkeypatch.setenv("RUN_PROGRESS_SHADOW_WRITER_ENABLED", "false")
    monkeypatch.setenv("MIRROR_TUNNEL_SHADOW_LIVE_TRACE_ENABLED", "false")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    from agents import gemini_client
    import config
    from core import index_manifest
    from core import pipeline
    from database import memory
    from web.runner import run_agent_web

    # Config may have been imported by another test module during collection.
    monkeypatch.setattr(memory, "DB_ENABLED", False)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)

    def reject_network(*args, **kwargs):
        raise AssertionError("Black-box acceptance tests must never use a network")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    repo = tmp_path / "customer_repo"
    repo.mkdir()
    (repo / "margin_meter.py").write_bytes(ORIGINAL.encode())
    # A nested pytest suite with no root config reproduces a legitimate project
    # layout the global selector misses, while the graph can target its checks.
    (repo / "quality").mkdir()
    (repo / "quality" / "test_margin_meter.py").write_bytes(REPO_TESTS.encode())
    # Isolate debug_last_control_prompt and other relative harness artifacts.
    scratch = tmp_path / "harness_cwd"
    scratch.mkdir()
    monkeypatch.chdir(scratch)
    artifact_dir = scratch / ".agent"
    artifact_dir.mkdir()
    monkeypatch.setattr(config, "AGENT_DIR", artifact_dir)
    monkeypatch.setattr(config, "OUTPUT_FILE", artifact_dir / "session_log.txt")
    monkeypatch.setattr(index_manifest, "AGENT_DIR", artifact_dir)

    def run(first, revised=None, *, revision_file="margin_meter.py", validation="timeout", failing_checks=False, oracle="product"):
        calls = []
        if oracle == "live5":
            from _matrix_history import pin_live5_indentation_matrix

            pin_live5_indentation_matrix(monkeypatch)
        else:
            assert oracle == "product", oracle
        if failing_checks:
            (repo / "quality" / "test_margin_meter.py").write_bytes(FAILING_REPO_TESTS.encode())

        def provider(prompt, *args, **kwargs):
            calls.append(str(prompt))
            assert len(calls) <= 2, "The harness spent more than one revision call"
            if len(calls) == 1:
                return _candidate(first)
            assert revised is not None, "Unexpected model retry for an ineligible candidate"
            return _candidate(revised, revision_file)

        def scout_provider(*args, **kwargs):
            # Provider substitute only; actual scout trigger and source hydration run.
            return json.dumps({"request_type": "bug_fix", "likely_files": ["margin_meter.py"],
                               "likely_symbols": ["margin_meter.py::describe_margin"]})

        monkeypatch.setattr(pipeline, "run_gemini_request", provider)
        monkeypatch.setattr(gemini_client, "run_gemini_request", provider)
        monkeypatch.setattr(gemini_client, "run_gemini_request_2", scout_provider)
        monkeypatch.setattr(pipeline, "run_deepseek_review", reject_network)
        before = _source_snapshot(repo)
        started = time.perf_counter()
        validation_suffix = {
            # Model the expensive global command common in a large codebase.
            # It REALLY times out after the product's 30 s budget; no validation
            # receipt, timer, probe, gate, or control result is mocked here.
            "timeout": '\nvalidation command: python -c "import time; time.sleep(31)"',
            "suite": "\nvalidation command: python -m pytest -q",
            "auto": "",
        }[validation]
        result = run_agent_web(
            "Fix the bug in margin_meter.py::describe_margin: "
            "2-space indentation is classified as 4-space."
            + validation_suffix,
            str(repo), patch_style="safe_minimal", runtime_environment="local_windows",
        )
        elapsed = time.perf_counter() - started
        assert _source_snapshot(repo) == before, "Read-only execution changed customer files"
        (tmp_path / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        assert result.get("patch"), result.get("answer")
        payload = json.loads(result["patch"])
        record_property("elapsed_sec", round(elapsed, 3))
        record_property("validation_profile", validation)
        record_property("injected_timeout_sec", 30 if validation == "timeout" else 0)
        record_property("provider_calls", len(calls))
        record_property("verification_status", payload.get("candidate_verification_status"))
        record_property("revision_outcome", payload.get("candidate_revision_outcome"))
        print("BLACKBOX_CODING_RESULT " + json.dumps({
            "first": "correct" if first == CORRECT else "noop" if first == ORIGINAL else "wrong",
            "calls": len(calls), "elapsed_sec": round(elapsed, 3),
            "validation_profile": validation,
            "injected_timeout_sec": 30 if validation == "timeout" else 0,
            "verification": payload.get("candidate_verification_status"),
            "revision": payload.get("candidate_revision_outcome"),
            "matrix": payload.get("behavioral_matrix_status"),
            "repo_unchanged": True,
        }))
        assert payload.get("execution_authorized") is False
        assert payload.get("final_repository_changed") is False
        return payload, calls, result

    return run


def test_public_runner_accepts_a_correct_locally_novel_candidate_without_writing(run_scenario):
    payload, calls, _ = run_scenario(CORRECT, oracle="live5")
    assert len(calls) == 1
    assert payload.get("candidate_verification_status") == "verified"
    assert payload.get("patch_candidate", {}).get("patched_snippet", "").strip() == CORRECT.strip()


def test_public_runner_rejects_the_raw_width_candidate_under_the_eight_case_oracle(run_scenario):
    """INDENT.SEMANTICS.1 at the public boundary: the same CORRECT bytes, the
    product's own matrix.  Its 6-wide continuation and docstring rows make it
    answer 2space for code whose only block step is 4; the author repeats
    itself once, is rejected again, and nothing is written."""
    payload, calls, _ = run_scenario(CORRECT, CORRECT, validation="auto")
    assert len(calls) == 2
    assert "indentation_style.preserve.4space.continuation" in calls[1]
    assert "indentation_style.preserve.4space.multiline_string" in calls[1]
    assert payload.get("behavioral_matrix_case_count") == 8
    assert payload.get("behavioral_matrix_status") == "fixed_but_regressive"
    assert [
        case["case_id"]
        for case in payload.get("behavioral_matrix_cases", [])
        if case.get("candidate_status") == "regressed"
    ] == [
        "indentation_style.preserve.4space.continuation",
        "indentation_style.preserve.4space.multiline_string",
    ]
    assert payload.get("candidate_verification_status") == "rejected"
    assert payload.get("human_review_eligible") is not True


def test_public_runner_uses_counterexamples_to_revise_once_without_writing(run_scenario):
    payload, calls, _ = run_scenario(DEAD_GUARD, CORRECT, oracle="live5")
    assert len(calls) == 2
    assert "4space" in calls[1] and "2space" in calls[1]
    assert payload.get("candidate_verification_status") == "verified"
    assert payload.get("patch_candidate", {}).get("patched_snippet", "").strip() == CORRECT.strip()


def test_public_runner_rejects_a_revision_that_breaks_preserved_behavior(run_scenario):
    payload, calls, _ = run_scenario(DEAD_GUARD, OVERFIT)
    assert len(calls) == 2
    assert payload.get("candidate_verification_status") == "rejected"
    assert payload.get("behavioral_matrix_status") == "fixed_but_regressive"
    assert payload.get("human_review_eligible") is not True


def test_public_runner_rejects_exact_noop_without_spending_a_retry(run_scenario):
    payload, calls, _ = run_scenario(ORIGINAL, validation="auto")
    assert len(calls) == 1
    assert not payload.get("patch_candidate")
    assert payload.get("candidate_verification_status") != "verified"
    assert payload.get("candidate_effect_status") == "no_op"


def test_public_runner_cannot_move_a_revision_to_another_file(run_scenario):
    payload, calls, _ = run_scenario(DEAD_GUARD, CORRECT, revision_file="other_component.py")
    assert len(calls) == 2
    assert payload.get("candidate_verification_status") == "rejected"
    assert payload.get("patch_candidate", {}).get("relative_path") != "other_component.py"
    assert payload.get("human_review_eligible") is not True


def test_public_runner_accepts_equivalent_correct_fstring_implementation(run_scenario):
    payload, calls, _ = run_scenario(FSTRING_CORRECT, validation="auto", oracle="live5")
    assert len(calls) == 1
    assert payload.get("patch_candidate"), "Python's f-string prefix is not an external identifier"


def test_public_runner_can_revise_when_the_customer_supplies_a_failing_suite(run_scenario):
    payload, calls, _ = run_scenario(
        DEAD_GUARD, CORRECT, validation="suite", failing_checks=True, oracle="live5"
    )
    assert len(calls) == 2
    assert payload.get("candidate_verification_status") == "verified"


def test_public_runner_accepts_a_fix_that_turns_failing_targeted_checks_green(run_scenario):
    payload, calls, _ = run_scenario(CORRECT, failing_checks=True, oracle="live5")
    assert len(calls) == 1
    assert payload.get("candidate_verification_status") == "verified"
