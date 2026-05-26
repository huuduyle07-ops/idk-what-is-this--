"""Tests for Phase 5.7 — Prompt-Version & Cost Quantifier.

The quantifier is read-only over ``.agent/benchmarks/benchmark_report_*.json``.
These tests guard:

* grouping by ``brain_stamp.prompt_config_hash``,
* the ``unknown`` bucket when the stamp is missing or empty,
* averaging across runs (duration, fallbacks, cost, tokens, etc.),
* default sort = newest ``last_seen`` first,
* summary highlights for highest avg cost and avg fallback group,
* malformed reports skipped with a warning (no crash),
* source ``benchmark_report_*.json`` files are never modified,
* CLI markdown export works,
* ``GET /benchmarks/prompt-cost`` returns table-ready data,
* the module imports nothing that runs benchmarks, calls models, or applies
  patches.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from core import prompt_cost_quantifier as quantifier


def _write_report(root: Path, name: str, payload: dict) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _make_report(
    *,
    prompt_hash: str | None,
    created_at: str,
    success_rate: float = 1.0,
    total: int = 2,
    passed: int = 2,
    failed: int = 0,
    flaky: int = 0,
    duration: float = 10.0,
    fallbacks: int = 0,
    input_tokens: int = 100,
    output_tokens: int = 50,
    total_tokens: int = 150,
    estimated_cost: float = 0.01,
    unknown_cost_calls: int = 0,
    dirty: bool = False,
    model_calls: int | None = None,
    extra_brain_stamp: dict | None = None,
) -> dict:
    stamp: dict = {
        "git_sha": "deadbeef",
        "git_branch": "main",
        "git_dirty": dirty,
    }
    if prompt_hash is not None:
        stamp["prompt_config_hash"] = prompt_hash
    if extra_brain_stamp:
        stamp.update(extra_brain_stamp)

    results: list[dict] = []
    if model_calls is not None:
        per_case = max(1, model_calls // max(total, 1))
        for idx in range(total):
            results.append(
                {
                    "name": f"case_{idx}",
                    "success": True,
                    "model_calls": [
                        {"model": "fake", "role": "draft"}
                        for _ in range(per_case)
                    ],
                }
            )
    else:
        results = [{"name": f"case_{i}", "success": True} for i in range(total)]

    return {
        "created_at": created_at,
        "success_rate": success_rate,
        "total": total,
        "passed": passed,
        "failed": failed,
        "flaky": flaky,
        "avg_duration_sec": duration,
        "total_fallbacks": fallbacks,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "total_estimated_cost_usd": estimated_cost,
        "unknown_cost_calls": unknown_cost_calls,
        "results": results,
        "brain_stamp": stamp,
    }


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


def test_groups_reports_by_prompt_config_hash(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_1.json",
        _make_report(prompt_hash="aaa111", created_at="2026-05-20T01:00:00+00:00"),
    )
    _write_report(
        root,
        "benchmark_report_2.json",
        _make_report(prompt_hash="aaa111", created_at="2026-05-21T01:00:00+00:00"),
    )
    _write_report(
        root,
        "benchmark_report_3.json",
        _make_report(prompt_hash="bbb222", created_at="2026-05-22T01:00:00+00:00"),
    )

    report = quantifier.build_prompt_cost_report(root)

    assert {g["prompt_config_hash"] for g in report["groups"]} == {"aaa111", "bbb222"}
    aaa = next(g for g in report["groups"] if g["prompt_config_hash"] == "aaa111")
    assert aaa["runs"] == 2
    assert {r["report"] for r in aaa["reports"]} == {
        "benchmark_report_1.json",
        "benchmark_report_2.json",
    }


def test_default_sort_is_newest_last_seen_first(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_old.json",
        _make_report(prompt_hash="old111", created_at="2026-05-01T00:00:00+00:00"),
    )
    _write_report(
        root,
        "benchmark_report_new.json",
        _make_report(prompt_hash="new222", created_at="2026-05-25T00:00:00+00:00"),
    )

    report = quantifier.build_prompt_cost_report(root)

    assert [g["prompt_config_hash"] for g in report["groups"]] == ["new222", "old111"]
    new_group = report["groups"][0]
    assert new_group["latest_report"] == "benchmark_report_new.json"
    assert new_group["first_seen"] == new_group["last_seen"]


# ---------------------------------------------------------------------------
# Unknown bucket
# ---------------------------------------------------------------------------


def test_unknown_hash_group_when_brain_stamp_missing(tmp_path):
    root = tmp_path / "benchmarks"
    payload = _make_report(prompt_hash=None, created_at="2026-05-22T01:00:00+00:00")
    payload.pop("brain_stamp", None)
    _write_report(root, "benchmark_report_nostamp.json", payload)

    empty_stamp = _make_report(
        prompt_hash=None, created_at="2026-05-23T01:00:00+00:00"
    )
    empty_stamp["brain_stamp"] = {}
    _write_report(root, "benchmark_report_empty.json", empty_stamp)

    blank_hash = _make_report(
        prompt_hash="", created_at="2026-05-24T01:00:00+00:00"
    )
    _write_report(root, "benchmark_report_blank.json", blank_hash)

    report = quantifier.build_prompt_cost_report(root)

    assert len(report["groups"]) == 1
    unknown_group = report["groups"][0]
    assert unknown_group["prompt_config_hash"] == "unknown"
    assert unknown_group["runs"] == 3


# ---------------------------------------------------------------------------
# Metric averages
# ---------------------------------------------------------------------------


def test_average_metrics_are_computed_correctly(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_1.json",
        _make_report(
            prompt_hash="hash_a",
            created_at="2026-05-20T01:00:00+00:00",
            duration=10.0,
            fallbacks=2,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost=0.01,
            unknown_cost_calls=1,
            dirty=False,
            model_calls=4,
            total=2,
        ),
    )
    _write_report(
        root,
        "benchmark_report_2.json",
        _make_report(
            prompt_hash="hash_a",
            created_at="2026-05-21T01:00:00+00:00",
            duration=20.0,
            fallbacks=4,
            input_tokens=300,
            output_tokens=150,
            total_tokens=450,
            estimated_cost=0.03,
            unknown_cost_calls=3,
            dirty=True,
            model_calls=8,
            total=2,
        ),
    )

    report = quantifier.build_prompt_cost_report(root)
    group = report["groups"][0]

    assert group["avg_duration"] == pytest.approx(15.0)
    assert group["avg_fallback_count"] == pytest.approx(3.0)
    assert group["avg_input_tokens"] == pytest.approx(200.0)
    assert group["avg_output_tokens"] == pytest.approx(100.0)
    assert group["avg_total_tokens"] == pytest.approx(300.0)
    assert group["avg_estimated_cost"] == pytest.approx(0.02)
    assert group["avg_model_calls"] == pytest.approx(6.0)
    assert group["unknown_cost_call_count"] == pytest.approx(4.0)
    assert group["dirty_run_count"] == pytest.approx(1.0)
    assert group["latest_report"] == "benchmark_report_2.json"


def test_missing_metrics_become_unknown(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_sparse.json",
        {
            "created_at": "2026-05-24T01:00:00+00:00",
            "results": [{"name": "case_a", "success": True}],
            "brain_stamp": {"prompt_config_hash": "sparse_hash"},
        },
    )

    report = quantifier.build_prompt_cost_report(root)
    group = report["groups"][0]

    assert group["avg_duration"] == "unknown"
    assert group["avg_estimated_cost"] == "unknown"
    assert group["avg_total_tokens"] == "unknown"
    assert group["avg_fallback_count"] == "unknown"
    # No result entry exposed a ``model_calls`` list, so the field is unknown.
    assert group["avg_model_calls"] == "unknown"
    assert group["dirty_run_count"] == pytest.approx(0.0)


def test_summary_surfaces_highest_cost_and_fallback_groups(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_low.json",
        _make_report(
            prompt_hash="cheap",
            created_at="2026-05-20T01:00:00+00:00",
            estimated_cost=0.001,
            fallbacks=1,
        ),
    )
    _write_report(
        root,
        "benchmark_report_high_cost.json",
        _make_report(
            prompt_hash="expensive",
            created_at="2026-05-21T01:00:00+00:00",
            estimated_cost=0.50,
            fallbacks=2,
        ),
    )
    _write_report(
        root,
        "benchmark_report_high_fb.json",
        _make_report(
            prompt_hash="flaky_model",
            created_at="2026-05-22T01:00:00+00:00",
            estimated_cost=0.10,
            fallbacks=12,
        ),
    )

    summary = quantifier.build_prompt_cost_report(root)["summary"]

    assert summary["highest_avg_cost"]["prompt_config_hash"] == "expensive"
    assert summary["highest_avg_fallback_count"]["prompt_config_hash"] == "flaky_model"


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_malformed_reports_are_skipped_with_warning(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_good.json",
        _make_report(prompt_hash="good", created_at="2026-05-20T01:00:00+00:00"),
    )
    (root / "benchmark_report_bad.json").write_text("{not json", encoding="utf-8")
    (root / "benchmark_report_list.json").write_text("[]", encoding="utf-8")

    report = quantifier.build_prompt_cost_report(root)

    reasons = {entry["report"]: entry["reason"] for entry in report["skipped_reports"]}
    assert reasons["benchmark_report_bad.json"] == "malformed_json"
    assert reasons["benchmark_report_list.json"] == "not_object"
    assert len(report["groups"]) == 1
    assert report["summary"]["skipped_count"] == 2


def test_source_benchmark_reports_are_not_modified(tmp_path):
    root = tmp_path / "benchmarks"
    path = _write_report(
        root,
        "benchmark_report_1.json",
        _make_report(prompt_hash="hash_a", created_at="2026-05-20T01:00:00+00:00"),
    )
    before = path.read_text(encoding="utf-8")
    before_mtime = path.stat().st_mtime

    written = quantifier.write_prompt_cost_files(root, output_json=True, output_md=True)

    assert path.read_text(encoding="utf-8") == before
    assert path.stat().st_mtime == before_mtime
    # All emitted files live under the prompt_cost subdir.
    for out_path in written["paths"].values():
        assert out_path.parent == root / "prompt_cost"


def test_missing_benchmark_root_returns_empty_report(tmp_path):
    report = quantifier.build_prompt_cost_report(tmp_path / "does_not_exist")
    assert report["groups"] == []
    assert report["summary"]["group_count"] == 0
    assert report["summary"]["report_count"] == 0


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------


def test_markdown_export_renders_table(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_md.json",
        _make_report(
            prompt_hash="abcdef0123456789",
            created_at="2026-05-22T01:00:00+00:00",
            duration=12.5,
            fallbacks=3,
            total_tokens=900,
            estimated_cost=0.025,
        ),
    )

    written = quantifier.write_prompt_cost_files(
        root, output_json=True, output_md=True
    )
    md_path = written["paths"]["markdown"]
    markdown = md_path.read_text(encoding="utf-8")

    assert "# Prompt / Cost Quantifier" in markdown
    assert "| prompt_hash | runs | avg_success | avg_duration | avg_fallbacks |" in markdown
    # Long hashes are shortened to first 12 characters in the panel column.
    assert "`abcdef012345`" in markdown
    assert "`benchmark_report_md.json`" in markdown


# ---------------------------------------------------------------------------
# Web route
# ---------------------------------------------------------------------------


def test_web_route_returns_table_data(tmp_path):
    from web import app as web_app

    root = tmp_path / ".agent" / "benchmarks"
    _write_report(
        root,
        "benchmark_report_1.json",
        _make_report(
            prompt_hash="hash_a",
            created_at="2026-05-22T01:00:00+00:00",
            estimated_cost=0.05,
            fallbacks=2,
        ),
    )

    client = web_app.app.test_client()
    response = client.get(f"/benchmarks/prompt-cost?repo_path={tmp_path}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    report = body["report"]
    assert report["summary"]["group_count"] == 1
    group = report["groups"][0]
    assert group["prompt_config_hash"] == "hash_a"
    assert group["latest_report"] == "benchmark_report_1.json"


def test_web_route_rejects_missing_repo_path():
    from web import app as web_app

    client = web_app.app.test_client()
    response = client.get("/benchmarks/prompt-cost")
    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False


# ---------------------------------------------------------------------------
# Safety — no benchmark runner / model / patch imports
# ---------------------------------------------------------------------------


def test_module_does_not_import_runner_model_or_patch(tmp_path):
    """Calling ``build_prompt_cost_report`` must not import any of the
    runtime modules that execute benchmarks, call models, or apply patches.

    Some of these modules may already be loaded by other tests in the same
    process, so we only require that the quantifier itself does not pull in a
    *new* dependency on them — we snapshot ``sys.modules`` before the call
    and only fail if a forbidden module is loaded between the snapshot and
    the call. Additionally, the quantifier module's source text must not
    mention any of these modules.
    """
    forbidden = {
        "benchmarks.run_benchmarks",
        "agents.gemini_client",
        "agents.deepseek_client",
        "agents.ollama_client",
        "core.executor",
        "core.run_lifecycle",
        "core.proposal_runner",
        "core.benchmark_web",
        "patching.patch_executor",
    }
    before = set(sys.modules)

    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_safe.json",
        _make_report(prompt_hash="hash_a", created_at="2026-05-22T01:00:00+00:00"),
    )
    quantifier.build_prompt_cost_report(root)
    quantifier.write_prompt_cost_files(root, output_md=True)

    after = set(sys.modules)
    newly_loaded = (after - before) & forbidden
    assert newly_loaded == set(), (
        f"Quantifier loaded forbidden modules: {sorted(newly_loaded)}"
    )

    # Source guard: the module itself must not name any forbidden import.
    source = Path(quantifier.__file__).read_text(encoding="utf-8")
    for name in forbidden:
        assert name not in source, (
            f"core/prompt_cost_quantifier.py references forbidden module {name}"
        )


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_writes_json_and_markdown(tmp_path, monkeypatch):
    from scripts import build_prompt_cost_report as cli

    repo = tmp_path / "repo"
    bench_root = repo / ".agent" / "benchmarks"
    _write_report(
        bench_root,
        "benchmark_report_cli.json",
        _make_report(
            prompt_hash="cli_hash",
            created_at="2026-05-23T01:00:00+00:00",
        ),
    )

    exit_code = cli.main(["--repo-path", str(repo), "--output-md"])
    assert exit_code == 0

    out_dir = bench_root / "prompt_cost"
    assert (out_dir / "prompt_cost_report.json").is_file()
    assert (out_dir / "prompt_cost_report.md").is_file()
    json_data = json.loads(
        (out_dir / "prompt_cost_report.json").read_text(encoding="utf-8")
    )
    assert json_data["summary"]["group_count"] == 1
