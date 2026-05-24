"""Phase 12.5k — tests for budgeted linter fusion into Phantom Limb."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import linter_fusion
from core.linter_fusion import (
    MAX_LINTER_BOOST,
    MAX_LINTER_FINDINGS_IN_PROMPT,
    MAX_LINTER_PROMPT_CHARS,
    fuse_for_repo,
    fuse_into_phantom,
    load_linter_findings,
)


# ---------------- helpers ----------------

def _write_findings(repo: Path, findings: list[dict]) -> Path:
    target = repo / ".agent" / "linter" / "findings.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(findings), encoding="utf-8")
    return target


def _err(file: str, line: int, rule: str, message: str = "X is bad") -> dict:
    return {
        "tool": "eslint", "file": file, "line": line, "column": 1,
        "severity": "error", "rule_id": rule, "message": message,
        "symbol": None, "source": "external_linter",
    }


def _warn(file: str, line: int, rule: str, message: str = "X is suspect") -> dict:
    return {
        "tool": "eslint", "file": file, "line": line, "column": 1,
        "severity": "warning", "rule_id": rule, "message": message,
        "symbol": None, "source": "external_linter",
    }


def _info(file: str, line: int, rule: str, message: str = "X is stylish") -> dict:
    return {
        "tool": "pylint", "file": file, "line": line, "column": 1,
        "severity": "info", "rule_id": rule, "message": message,
        "symbol": None, "source": "external_linter",
    }


def _phantom(file: str, rule: str = "ts_any_type", missing: str = "explicit type") -> dict:
    return {"rule": rule, "file": file, "missing": missing, "severity": "info"}


# ---------------- load_linter_findings ----------------

def test_missing_findings_file_returns_empty_list(tmp_path):
    assert load_linter_findings(str(tmp_path)) == []


def test_malformed_findings_file_returns_empty_list(tmp_path):
    target = tmp_path / ".agent" / "linter" / "findings.json"
    target.parent.mkdir(parents=True)
    target.write_text("{not valid json", encoding="utf-8")
    assert load_linter_findings(str(tmp_path)) == []


def test_non_list_findings_file_returns_empty_list(tmp_path):
    target = tmp_path / ".agent" / "linter" / "findings.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"wrong": "shape"}), encoding="utf-8")
    assert load_linter_findings(str(tmp_path)) == []


def test_load_filters_malformed_entries(tmp_path):
    _write_findings(tmp_path, [
        _err("src/foo.ts", 1, "no-undef"),
        "not a dict",                          # malformed
        {"file": "src/foo.ts"},                # missing severity
        {"severity": "error", "rule_id": "r"}, # missing file
        {**_err("src/bar.ts", 2, "no-undef"), "severity": "bogus"},  # bad severity
        _warn("src/bar.ts", 2, "semi"),
    ])
    out = load_linter_findings(str(tmp_path))
    assert len(out) == 2
    assert {f["file"] for f in out} == {"src/foo.ts", "src/bar.ts"}


def test_load_normalizes_backslash_paths(tmp_path):
    _write_findings(tmp_path, [_err("src\\foo.ts", 1, "no-undef")])
    out = load_linter_findings(str(tmp_path))
    assert out and out[0]["file"] == "src/foo.ts"


def test_load_rejects_invalid_repo_path(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert load_linter_findings(str(missing)) == []


# ---------------- fuse_into_phantom: matching + boost ----------------

def test_error_finding_on_same_file_boosts_phantom_candidate():
    fused = fuse_into_phantom(
        [_phantom("pricing.ts")],
        [_err("pricing.ts", 12, "no-undef", "multiplyCents is not defined")],
    )
    findings = fused["findings"]
    assert len(findings) == 1
    assert findings[0]["linter_suspicion_boost"] == pytest.approx(0.25)
    assert findings[0]["linter_evidence"][0]["rule_id"] == "no-undef"
    assert findings[0]["linter_evidence"][0]["severity"] == "error"
    assert fused["linter_summary"]["matched_files"] == 1
    assert fused["linter_summary"]["total_linter_findings"] == 1


def test_warning_and_info_boost_less_than_error():
    err_boost = fuse_into_phantom(
        [_phantom("a.ts")], [_err("a.ts", 1, "r")]
    )["findings"][0]["linter_suspicion_boost"]
    warn_boost = fuse_into_phantom(
        [_phantom("a.ts")], [_warn("a.ts", 1, "r")]
    )["findings"][0]["linter_suspicion_boost"]
    info_boost = fuse_into_phantom(
        [_phantom("a.ts")], [_info("a.ts", 1, "r")]
    )["findings"][0]["linter_suspicion_boost"]
    assert err_boost > warn_boost > info_boost
    assert err_boost == pytest.approx(0.25)
    assert warn_boost == pytest.approx(0.10)
    assert info_boost == pytest.approx(0.05)


def test_linter_boost_is_capped():
    # Eight errors would naively sum to 2.00 — must clamp at MAX_LINTER_BOOST.
    linter = [_err("a.ts", i, "r") for i in range(1, 9)]
    fused = fuse_into_phantom([_phantom("a.ts")], linter)
    boost = fused["findings"][0]["linter_suspicion_boost"]
    assert boost == pytest.approx(MAX_LINTER_BOOST)
    # Sanity check the cap is the documented value.
    assert MAX_LINTER_BOOST == 0.40


def test_boost_sums_mixed_severities_then_caps():
    # error (0.25) + warning (0.10) + warning (0.10) = 0.45 → clamp to 0.40
    fused = fuse_into_phantom(
        [_phantom("a.ts")],
        [_err("a.ts", 1, "r1"), _warn("a.ts", 2, "r2"), _warn("a.ts", 3, "r3")],
    )
    assert fused["findings"][0]["linter_suspicion_boost"] == pytest.approx(0.40)


def test_no_match_means_no_boost():
    fused = fuse_into_phantom(
        [_phantom("a.ts")],
        [_err("unrelated.ts", 1, "r")],
    )
    out = fused["findings"][0]
    assert "linter_suspicion_boost" not in out
    assert "linter_evidence" not in out


def test_input_dicts_are_not_mutated():
    phantom = _phantom("a.ts")
    linter = _err("a.ts", 1, "r")
    fuse_into_phantom([phantom], [linter])
    assert "linter_suspicion_boost" not in phantom
    assert "linter_evidence" not in phantom


# ---------------- prompt block: budget + selection ----------------

def test_prompt_block_includes_at_most_five_findings():
    linter = [_err("a.ts", i, f"r{i}", f"msg{i}") for i in range(1, 11)]
    fused = fuse_into_phantom([_phantom("a.ts")], linter)
    block = fused["prompt_block"]
    assert block.startswith("[LINTER HINTS")
    bullet_lines = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert len(bullet_lines) <= MAX_LINTER_FINDINGS_IN_PROMPT == 5
    assert len(bullet_lines) == 5


def test_prompt_block_respects_800_char_budget():
    # Each finding's message is huge so a single bullet eats the budget.
    huge_msg = "X" * 700
    linter = [_err("a.ts", i, f"rule-{i}", huge_msg) for i in range(1, 6)]
    fused = fuse_into_phantom([_phantom("a.ts")], linter)
    block = fused["prompt_block"]
    assert len(block) <= MAX_LINTER_PROMPT_CHARS == 800
    # At least the header plus one bullet should fit; we never emit a
    # header-only block (would be misleading).
    bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert len(bullets) >= 1


def test_prompt_block_returns_empty_string_when_no_relevant_findings():
    fused = fuse_into_phantom(
        [_phantom("a.ts")],
        [_err("unrelated.ts", 1, "r")],
    )
    assert fused["prompt_block"] == ""


def test_prompt_block_empty_when_no_phantom_candidates():
    fused = fuse_into_phantom([], [_err("a.ts", 1, "r")])
    assert fused["prompt_block"] == ""


def test_prompt_block_orders_by_severity_then_file_then_line():
    linter = [
        _info("z.ts", 5, "info-rule"),
        _warn("y.ts", 1, "warn-rule"),
        _err("y.ts", 99, "late-error"),
        _err("a.ts", 12, "early-error"),
    ]
    phantom = [_phantom("a.ts"), _phantom("y.ts"), _phantom("z.ts")]
    fused = fuse_into_phantom(phantom, linter)
    block = fused["prompt_block"]
    bullets = [ln for ln in block.splitlines() if ln.startswith("- ")]
    # Errors come first (sorted by file), then warnings, then info.
    assert "a.ts:12" in bullets[0]    # error, a.ts before y.ts
    assert "y.ts:99" in bullets[1]    # error, y.ts
    assert "y.ts:1" in bullets[2]     # warning
    assert "z.ts:5" in bullets[3]     # info


def test_irrelevant_files_are_not_injected_into_prompt():
    """Linter findings for files not touched by Phantom Limb stay out of
    the prompt entirely — Phantom Limb is the routing layer.
    """
    fused = fuse_into_phantom(
        [_phantom("interesting.ts")],
        [
            _err("noise1.ts", 1, "r"),
            _err("noise2.ts", 2, "r"),
            _err("interesting.ts", 5, "no-undef", "fooBar undefined"),
        ],
    )
    block = fused["prompt_block"]
    assert "noise1.ts" not in block
    assert "noise2.ts" not in block
    assert "interesting.ts" in block


# ---------------- fuse_for_repo (load + fuse) ----------------

def test_fuse_for_repo_with_missing_file_is_a_noop(tmp_path):
    """Missing .agent/linter/findings.json must yield no hints and no error."""
    fused = fuse_for_repo(str(tmp_path), [_phantom("a.ts")])
    assert fused["prompt_block"] == ""
    assert fused["linter_summary"]["total_linter_findings"] == 0
    # Phantom finding passes through unchanged.
    assert "linter_suspicion_boost" not in fused["findings"][0]


def test_fuse_for_repo_with_real_findings_file(tmp_path):
    _write_findings(tmp_path, [
        _err("pricing.ts", 12, "no-undef", "multiplyCents is not defined"),
        _warn("pricing.ts", 3, "no-unused-vars"),
    ])
    fused = fuse_for_repo(str(tmp_path), [_phantom("pricing.ts")])
    assert fused["linter_summary"]["total_linter_findings"] == 2
    assert fused["findings"][0]["linter_suspicion_boost"] == pytest.approx(
        0.25 + 0.10
    )
    block = fused["prompt_block"]
    assert "pricing.ts:12" in block
    assert "multiplyCents is not defined" in block


def test_fuse_for_repo_with_malformed_file_is_safe(tmp_path):
    target = tmp_path / ".agent" / "linter" / "findings.json"
    target.parent.mkdir(parents=True)
    target.write_text("not json", encoding="utf-8")
    fused = fuse_for_repo(str(tmp_path), [_phantom("a.ts")])
    assert fused["prompt_block"] == ""
    assert fused["linter_summary"]["total_linter_findings"] == 0


# ---------------- format details ----------------

def test_prompt_block_header_matches_spec():
    fused = fuse_into_phantom(
        [_phantom("a.ts")],
        [_err("a.ts", 12, "no-undef", "multiplyCents is not defined")],
    )
    block = fused["prompt_block"]
    assert block.startswith(
        "[LINTER HINTS — relevant static-analysis evidence]"
    )
    # Spec example bullet shape:
    # - pricing.ts:12 eslint/no-undef error: multiplyCents is not defined
    assert (
        "- a.ts:12 eslint/no-undef error: multiplyCents is not defined"
        in block
    )


def test_phantom_finding_with_no_file_does_not_match_anything():
    fused = fuse_into_phantom(
        [{"rule": "r", "missing": "x", "severity": "info"}],
        [_err("a.ts", 1, "r")],
    )
    out = fused["findings"][0]
    assert "linter_evidence" not in out
    assert "linter_suspicion_boost" not in out
    assert fused["prompt_block"] == ""


# ---------------- existing Phantom Limb regression ----------------

def test_existing_phantom_limb_scan_still_works(tmp_path):
    """Phantom Limb's own scanner is untouched — sanity-check a simple Python
    "missing __main__ guard" run still produces a finding without the new
    fusion module interfering.
    """
    from core import phantom_limb

    script = tmp_path / "main_thing.py"
    script.write_text(
        "import argparse\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.parse_args()\n",
        encoding="utf-8",
    )
    summaries = [{
        "file": "main_thing.py",
        "language": "python",
        "main_symbols": [],
    }]
    findings = phantom_limb.scan(summaries, str(tmp_path))
    rules = [f["rule"] for f in findings]
    assert "python_script_no_main_guard" in rules


# ---------------- control_engine integration ----------------

def test_control_engine_prompt_includes_linter_hints_when_findings_relevant(tmp_path):
    """End-to-end: build_control_prompt must inject [LINTER HINTS …] after
    [PHANTOM LIMB SUGGESTIONS …] when there's a matching linter finding.
    """
    from core.control_engine import build_control_prompt

    _write_findings(tmp_path, [
        _err("pricing.ts", 12, "no-undef", "multiplyCents is not defined"),
    ])
    control_result = {
        "top_hypothesis": {"symbol": "x", "confidence": 0.5, "language": "typescript"},
        "patch_intent": {"language": "typescript", "source_snippet": "x"},
        "related_snippets": [],
        "scout": {"request_type": "patch_existing"},
        "phantom_limb": {
            "findings": [_phantom("pricing.ts", "ts_any_type")],
        },
        "patch_style": "balanced",
    }
    prompt = build_control_prompt(
        control_result,
        "fix pricing.ts",
        repo_path=str(tmp_path),
    )
    assert "[PHANTOM LIMB SUGGESTIONS" in prompt
    assert "[LINTER HINTS" in prompt
    assert "pricing.ts:12" in prompt
    assert "multiplyCents is not defined" in prompt


def test_control_engine_prompt_omits_linter_block_when_no_findings(tmp_path):
    """No findings file → no [LINTER HINTS …] block in the prompt."""
    from core.control_engine import build_control_prompt

    control_result = {
        "top_hypothesis": {"symbol": "x", "confidence": 0.5, "language": "typescript"},
        "patch_intent": {"language": "typescript", "source_snippet": "x"},
        "related_snippets": [],
        "scout": {"request_type": "patch_existing"},
        "phantom_limb": {
            "findings": [_phantom("pricing.ts", "ts_any_type")],
        },
        "patch_style": "balanced",
    }
    prompt = build_control_prompt(
        control_result,
        "fix pricing.ts",
        repo_path=str(tmp_path),
    )
    assert "[PHANTOM LIMB SUGGESTIONS" in prompt
    assert "[LINTER HINTS" not in prompt
