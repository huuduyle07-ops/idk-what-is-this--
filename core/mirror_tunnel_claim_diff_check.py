"""MIRROR.3 - Claim-vs-Diff Mirror Check (report-only).

MIRROR.3 compares agent/worker/final claims against existing patch, diff,
changed-file, validation, benchmark, replay, and artifact evidence. It is a
deterministic report layer only: no models, embeddings, semantic APIs,
validation/benchmark execution, workers, MCP calls, Docker/subprocess, network,
database writes, route/auth changes, patch application, or execution blocking.
It writes only ``mirror_tunnel_claim_diff_check.json`` /
``mirror_tunnel_claim_diff_check.md`` when the writer is called.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPORT_KIND = "mirror_tunnel_claim_diff_check"
JSON_NAME = "mirror_tunnel_claim_diff_check.json"
MD_NAME = "mirror_tunnel_claim_diff_check.md"
DEFAULT_TRACE_PATH = Path(".agent") / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
DEFAULT_SCORE_PATH = Path(".agent") / "mirror_tunnel" / "derailment_score" / "mirror_tunnel_derailment_score.json"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "mirror_tunnel" / "claim_diff_check"
DEFAULT_EXCERPT_LIMIT = 260

CLAIM_CATEGORIES: tuple[str, ...] = (
    "changed_files_claim",
    "no_change_claim",
    "validation_claim",
    "benchmark_claim",
    "test_claim",
    "safety_claim",
    "scope_claim",
    "completion_claim",
    "uncertainty_claim",
)

EVIDENCE_CATEGORIES: tuple[str, ...] = (
    "actual_changed_files",
    "patched_files",
    "generated_artifacts",
    "unexpected_mutations",
    "validation_status",
    "benchmark_status",
    "replay_status",
    "patch_safety_status",
    "missing_evidence",
)

VERDICTS: tuple[str, ...] = (
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "insufficient_evidence",
)

RECOMMENDED_NEXT_ACTIONS: dict[str, str] = {
    "supported": "continue_normal_review",
    "partially_supported": "human_review_recommended",
    "unsupported": "collect_missing_evidence",
    "contradicted": "do_not_trust_without_replay",
    "insufficient_evidence": "collect_more_artifacts",
}

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.3 is report-only.",
    "MIRROR.3 reads existing MIRROR.1, MIRROR.2, and explicit evidence artifacts only.",
    "MIRROR.3 uses deterministic text and pattern heuristics only.",
    "MIRROR.3 does not call models.",
    "MIRROR.3 does not use embeddings or semantic APIs.",
    "MIRROR.3 does not apply patches.",
    "MIRROR.3 does not run validation.",
    "MIRROR.3 does not run benchmarks.",
    "MIRROR.3 does not invoke MCP tools.",
    "MIRROR.3 does not launch workers.",
    "MIRROR.3 does not execute Dream actions.",
    "MIRROR.3 does not apply Replay janitor actions.",
    "MIRROR.3 does not use Docker or subprocess.",
    "MIRROR.3 does not contact network services.",
    "MIRROR.3 does not write to a database.",
    "MIRROR.3 does not change route behavior.",
    "MIRROR.3 does not change auth policy.",
    "MIRROR.3 does not block execution.",
    "MIRROR.3 writes claim-diff artifacts only.",
)

_SUCCESS_RE = re.compile(r"\b(pass|passed|success|succeeded|ok|green|0 errors?)\b", re.IGNORECASE)
_FAILURE_RE = re.compile(r"\b(fail|failed|failure|error|timeout|timed out|blocked|regression)\b", re.IGNORECASE)
_CHANGE_RE = re.compile(r"\b(changed|modified|updated|touched|edited|fixed|patched)\b", re.IGNORECASE)
_ONLY_RE = re.compile(r"\b(only|just|solely)\b", re.IGNORECASE)
_NO_CHANGE_RE = re.compile(r"\b(no code changes|no changes|did not change|didn't change|no files? changed)\b", re.IGNORECASE)
_VALIDATION_CLAIM_RE = re.compile(r"\b(validated|validation passed|validation succeeded|ran validation)\b", re.IGNORECASE)
_TEST_CLAIM_RE = re.compile(r"\b(tests? passed|pytest passed|suite passed|full suite passed)\b", re.IGNORECASE)
_BENCHMARK_CLAIM_RE = re.compile(r"\b(benchmark(?:s)? passed|benchmark check passed|benchmarks? succeeded)\b", re.IGNORECASE)
_SAFETY_CLAIM_RE = re.compile(r"\b(report-only|safe|no route|no auth|no mutation|no patch apply|no execution)\b", re.IGNORECASE)
_COMPLETION_CLAIM_RE = re.compile(r"\b(complete|completed|done|fixed|resolved|shipped)\b", re.IGNORECASE)
_UNCERTAINTY_RE = re.compile(
    r"\b(did not run|didn't run|not run|not validated|not counted as passed|timed out|timeout|unable to validate|not verified)\b",
    re.IGNORECASE,
)
_UNSAFE_PATCH_RE = re.compile(
    r"\b(apply_patch|mutation route|methods\s*=\s*\[[^\]]*(post|put|patch|delete)|@app\.route|auth policy)\b",
    re.IGNORECASE,
)


def build_mirror_tunnel_claim_diff_check(
    *,
    trace: dict[str, Any] | None = None,
    score: dict[str, Any] | None = None,
    explicit_artifacts: dict[str, Any] | None = None,
    trace_path: str = "",
    score_path: str = "",
    check_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a deterministic MIRROR.3 claim-vs-evidence report."""
    trace_data = trace if isinstance(trace, dict) else {}
    score_data = score if isinstance(score, dict) else {}
    artifact_data = explicit_artifacts if isinstance(explicit_artifacts, dict) else {}
    frames = _frames(trace_data)
    evidence = _evidence_detected(trace_data, frames, artifact_data)
    claims = _claims_detected(frames, artifact_data)
    matches, mismatches, unsupported, honest = _compare_claims_to_evidence(claims, evidence, score_data)
    missing = _missing_evidence(trace_data, evidence, claims)
    verdict = _overall_claim_support(claims, matches, mismatches, unsupported, honest, evidence)

    return {
        "report_kind": REPORT_KIND,
        "check_id": check_id or _default_check_id(trace_data, score_data, trace_path, score_path, created_at),
        "created_at": str(created_at or ""),
        "trace_id": str(trace_data.get("trace_id", "")),
        "trace_path": str(trace_path or ""),
        "score_id": str(score_data.get("score_id", "")),
        "score_path": str(score_path or ""),
        "mirror2_verdict": str(score_data.get("verdict", "")),
        "overall_claim_support": verdict,
        "recommended_next_action": RECOMMENDED_NEXT_ACTIONS[verdict],
        "recommended_next_phase": "MIRROR.4",
        "claims_detected": claims,
        "evidence_detected": evidence,
        "matches": matches,
        "mismatches": mismatches,
        "unsupported_claims": unsupported,
        "honest_uncertainty_claims": honest,
        "missing_evidence": missing,
        "artifact_references": _artifact_references(trace_data, artifact_data),
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def write_mirror_tunnel_claim_diff_check(
    *,
    repo_path: str = ".",
    trace_path: str | None = None,
    score_path: str | None = None,
    patch_json_path: str | None = None,
    diff_path: str | None = None,
    validation_json_path: str | None = None,
    benchmark_json_path: str | None = None,
    final_answer_file: str | None = None,
    worker_reply_file: str | None = None,
    output_root: str | None = None,
    check_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Read input artifacts and write MIRROR.3 JSON + Markdown artifacts."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    try:
        trace_file = _resolve_input_path(repo_root, trace_path or str(DEFAULT_TRACE_PATH), required=True)
        score_file = _resolve_input_path(repo_root, score_path, required=False)
        output_dir = _resolve_output_root(repo_root, output_root)
        artifact_paths = {
            "patch_json": _resolve_input_path(repo_root, patch_json_path, required=False),
            "diff": _resolve_input_path(repo_root, diff_path, required=False),
            "validation_json": _resolve_input_path(repo_root, validation_json_path, required=False),
            "benchmark_json": _resolve_input_path(repo_root, benchmark_json_path, required=False),
            "final_answer_file": _resolve_input_path(repo_root, final_answer_file, required=False),
            "worker_reply_file": _resolve_input_path(repo_root, worker_reply_file, required=False),
        }
        trace = _load_json_object(trace_file, "trace contract")
        score = _load_json_object(score_file, "derailment score") if score_file else {}
        artifacts = _load_explicit_artifacts(artifact_paths)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = _blocked_report(check_id=check_id, created_at=created_at, message=str(exc))
        return {
            "ok": False,
            "status": "blocked",
            "json_path": "",
            "md_path": "",
            "report": report,
            "markdown": render_mirror_tunnel_claim_diff_markdown(report),
        }

    report = build_mirror_tunnel_claim_diff_check(
        trace=trace,
        score=score,
        explicit_artifacts=artifacts,
        trace_path=str(trace_file),
        score_path=str(score_file or ""),
        check_id=check_id,
        created_at=created_at,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_NAME
    md_path = output_dir / MD_NAME
    markdown = render_mirror_tunnel_claim_diff_markdown(report)
    json_path.write_text(render_mirror_tunnel_claim_diff_json(report), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "status": report["overall_claim_support"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "markdown": markdown,
    }


def render_mirror_tunnel_claim_diff_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_mirror_tunnel_claim_diff_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Mirror Tunnel Claim-vs-Diff Check",
        "",
        "## Summary",
        "",
        f"- **Check id:** `{_md(report.get('check_id'))}`",
        f"- **Trace id:** `{_md(report.get('trace_id'))}`",
        f"- **MIRROR.2 verdict:** `{_md(report.get('mirror2_verdict'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Overall Claim Support",
        "",
        f"`{_md(report.get('overall_claim_support'))}`",
        "",
        "## Claims Detected",
        "",
        _bullet_list(_claim_lines(report.get("claims_detected"))),
        "",
        "## Evidence Detected",
        "",
        _bullet_list(_evidence_lines(report.get("evidence_detected"))),
        "",
        "## Matches",
        "",
        _bullet_list(_check_lines(report.get("matches"))),
        "",
        "## Mismatches",
        "",
        _bullet_list(_check_lines(report.get("mismatches"))),
        "",
        "## Unsupported Claims",
        "",
        _bullet_list(_check_lines(report.get("unsupported_claims"))),
        "",
        "## Honest Uncertainty Claims",
        "",
        _bullet_list(_check_lines(report.get("honest_uncertainty_claims"))),
        "",
        "## Missing Evidence",
        "",
        _bullet_list(_missing_lines(report.get("missing_evidence"))),
        "",
        "## Recommended Next Action",
        "",
        f"`{_md(report.get('recommended_next_action'))}`",
        "",
        "## Boundaries / Guardrails",
        "",
    ]
    for boundary in report.get("boundaries", []):
        lines.append(f"- {_md(boundary)}")
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}` = `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def _frames(trace: dict[str, Any]) -> list[dict[str, Any]]:
    raw = trace.get("frames")
    return [frame for frame in raw if isinstance(frame, dict)] if isinstance(raw, list) else []


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return data


def _load_json_lenient(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"items": data}


def _load_explicit_artifacts(paths: dict[str, Path | None]) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for key, path in paths.items():
        if path is None:
            continue
        if key.endswith("_json") or key == "patch_json":
            artifacts[key] = {"path": str(path), "data": _load_json_lenient(path), "text": path.read_text(encoding="utf-8")}
        else:
            artifacts[key] = {"path": str(path), "text": path.read_text(encoding="utf-8")}
    return artifacts


def _claims_detected(frames: list[dict[str, Any]], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[tuple[str, str, str]] = []
    for frame in frames:
        frame_type = str(frame.get("frame_type", ""))
        if frame_type in {"worker_reply", "final_answer"}:
            sources.append((frame_type, str(frame.get("artifact_path", "")), str(frame.get("excerpt", ""))))
    for key in ("worker_reply_file", "final_answer_file"):
        item = artifacts.get(key)
        if isinstance(item, dict):
            sources.append((key, str(item.get("path", "")), str(item.get("text", ""))))

    claims: list[dict[str, Any]] = []
    for source, artifact_path, text in sources:
        lower = text.lower()
        files = sorted(_file_paths(text))
        changed_files = sorted(_positive_changed_files(text))
        uncertain = bool(_UNCERTAINTY_RE.search(text))
        if uncertain:
            claims.append(_claim("uncertainty_claim", source, artifact_path, text, files=files, polarity="uncertain"))
        if _NO_CHANGE_RE.search(text):
            claims.append(_claim("no_change_claim", source, artifact_path, text, files=[], polarity="affirmed"))
        if _CHANGE_RE.search(text) and changed_files:
            claims.append(
                _claim(
                    "changed_files_claim",
                    source,
                    artifact_path,
                    text,
                    files=changed_files,
                    polarity="affirmed",
                    only=bool(_ONLY_RE.search(text)),
                )
            )
        if files and (_ONLY_RE.search(text) or "did not touch" in lower or "do not touch" in lower):
            claims.append(_claim("scope_claim", source, artifact_path, text, files=files, polarity="affirmed"))
        if not uncertain and _VALIDATION_CLAIM_RE.search(text):
            claims.append(_claim("validation_claim", source, artifact_path, text, files=[], polarity="affirmed"))
        if not uncertain and _TEST_CLAIM_RE.search(text):
            claims.append(_claim("test_claim", source, artifact_path, text, files=[], polarity="affirmed"))
        if not uncertain and _BENCHMARK_CLAIM_RE.search(text):
            claims.append(_claim("benchmark_claim", source, artifact_path, text, files=[], polarity="affirmed"))
        if _SAFETY_CLAIM_RE.search(text):
            claims.append(_claim("safety_claim", source, artifact_path, text, files=files, polarity="affirmed"))
        if not uncertain and _COMPLETION_CLAIM_RE.search(text):
            claims.append(_claim("completion_claim", source, artifact_path, text, files=files, polarity="affirmed"))
    return _dedupe_claims(claims)


def _claim(
    category: str,
    source: str,
    artifact_path: str,
    text: str,
    *,
    files: list[str],
    polarity: str,
    only: bool = False,
) -> dict[str, Any]:
    return {
        "claim_category": category,
        "source": source,
        "artifact_path": artifact_path,
        "polarity": polarity,
        "claimed_files": files,
        "only_claim": only,
        "excerpt": _cap(text, DEFAULT_EXCERPT_LIMIT),
    }


def _evidence_detected(trace: dict[str, Any], frames: list[dict[str, Any]], artifacts: dict[str, Any]) -> dict[str, Any]:
    patch_text = "\n".join(
        [str(frame.get("excerpt", "")) for frame in frames if str(frame.get("frame_type", "")) == "patch_or_diff"]
        + [str((artifacts.get("diff") or {}).get("text", ""))]
        + [str((artifacts.get("patch_json") or {}).get("text", ""))]
    )
    validation_text = "\n".join(
        [str(frame.get("excerpt", "")) for frame in frames if str(frame.get("frame_type", "")) == "validation_evidence"]
        + [str((artifacts.get("validation_json") or {}).get("text", ""))]
    )
    benchmark_text = "\n".join(
        [str(frame.get("excerpt", "")) for frame in frames if str(frame.get("frame_type", "")) == "benchmark_evidence"]
        + [str((artifacts.get("benchmark_json") or {}).get("text", ""))]
    )
    replay_text = "\n".join(
        [str(frame.get("excerpt", "")) for frame in frames if str(frame.get("frame_type", "")) == "replay_evidence"]
    )

    patch_json = (artifacts.get("patch_json") or {}).get("data", {})
    patched_files = set(_file_paths(patch_text))
    patched_files.update(_paths_from_json(patch_json, ("patched_files", "changed_files", "files")))
    actual_changed = set(patched_files)
    actual_changed.update(_paths_from_json(patch_json, ("actual_changed_files",)))
    generated = set(_artifact_paths(trace))
    generated.update(_paths_from_json(patch_json, ("generated_artifacts", "artifacts")))
    unexpected = set(_paths_from_json(patch_json, ("unexpected_mutations",)))

    if _UNSAFE_PATCH_RE.search(patch_text):
        patch_safety = "unsafe"
        unexpected.update(sorted(patched_files))
    elif patch_text.strip():
        patch_safety = "safe"
    else:
        patch_safety = "missing"

    return {
        "actual_changed_files": sorted(actual_changed),
        "patched_files": sorted(patched_files),
        "generated_artifacts": sorted(generated),
        "unexpected_mutations": sorted(unexpected),
        "validation_status": _status_from_text(validation_text),
        "benchmark_status": _status_from_text(benchmark_text),
        "replay_status": _status_from_text(replay_text),
        "patch_safety_status": patch_safety,
        "missing_evidence": _missing_from_trace(trace),
    }


def _compare_claims_to_evidence(
    claims: list[dict[str, Any]],
    evidence: dict[str, Any],
    score: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    matches: list[dict[str, str]] = []
    mismatches: list[dict[str, str]] = []
    unsupported: list[dict[str, str]] = []
    honest: list[dict[str, str]] = []
    changed_files = set(evidence.get("actual_changed_files") or [])
    patched_files = set(evidence.get("patched_files") or [])
    evidence_files = changed_files | patched_files
    mirror2_verdict = str(score.get("verdict", ""))

    for claim in claims:
        category = str(claim.get("claim_category", ""))
        claimed_files = set(claim.get("claimed_files") or [])
        if category == "uncertainty_claim":
            honest.append(_check(category, "supported_uncertainty", "claim honestly preserves missing or timed-out evidence"))
        elif category == "no_change_claim":
            if evidence_files:
                mismatches.append(_check(category, "mismatch", "claim says no code changes, but patch/diff evidence exists"))
            else:
                matches.append(_check(category, "match", "no-change claim is consistent with missing patch/diff evidence"))
        elif category == "changed_files_claim":
            extra = sorted(evidence_files - claimed_files)
            missing = sorted(claimed_files - evidence_files)
            if claimed_files and claim.get("only_claim") and extra:
                mismatches.append(_check(category, "mismatch", "claim says only these files changed, but evidence includes: " + ", ".join(extra)))
            elif claimed_files and missing:
                unsupported.append(_check(category, "unsupported", "claimed changed files lack patch/diff evidence: " + ", ".join(missing)))
            elif claimed_files and evidence_files:
                matches.append(_check(category, "match", "claimed changed files are present in patch/diff evidence"))
            else:
                unsupported.append(_check(category, "unsupported", "changed-files claim lacks patch/diff evidence"))
        elif category == "scope_claim":
            extra = sorted(evidence_files - claimed_files)
            if extra:
                mismatches.append(_check(category, "mismatch", "scope claim is contradicted by additional changed files: " + ", ".join(extra)))
            elif evidence_files:
                matches.append(_check(category, "match", "scope claim is consistent with detected changed files"))
            else:
                unsupported.append(_check(category, "unsupported", "scope claim lacks changed-file evidence"))
        elif category in {"validation_claim", "test_claim"}:
            _compare_status_claim(category, evidence.get("validation_status"), matches, mismatches, unsupported)
        elif category == "benchmark_claim":
            _compare_status_claim(category, evidence.get("benchmark_status"), matches, mismatches, unsupported)
        elif category == "safety_claim":
            if evidence.get("patch_safety_status") == "unsafe":
                mismatches.append(_check(category, "mismatch", "safety/report-only claim is contradicted by unsafe patch indicators"))
            else:
                matches.append(_check(category, "match", "no unsafe patch indicators detected"))
        elif category == "completion_claim":
            if mirror2_verdict in {"insufficient_trace", "severe_derailment"}:
                unsupported.append(_check(category, "unsupported", f"completion claim is not supported by MIRROR.2 verdict {mirror2_verdict}"))
            elif evidence_files or evidence.get("validation_status") == "passed" or evidence.get("benchmark_status") == "passed":
                matches.append(_check(category, "match", "completion claim has some supporting change or evidence frame"))
            else:
                unsupported.append(_check(category, "unsupported", "completion claim lacks change, validation, or benchmark evidence"))
    return _dedupe_checks(matches), _dedupe_checks(mismatches), _dedupe_checks(unsupported), _dedupe_checks(honest)


def _compare_status_claim(
    category: str,
    status: Any,
    matches: list[dict[str, str]],
    mismatches: list[dict[str, str]],
    unsupported: list[dict[str, str]],
) -> None:
    if status == "passed":
        matches.append(_check(category, "match", f"{category} is supported by passing evidence"))
    elif status == "failed":
        mismatches.append(_check(category, "mismatch", f"{category} is contradicted by failed evidence"))
    else:
        unsupported.append(_check(category, "unsupported", f"{category} lacks available evidence"))


def _check(category: str, status: str, message: str) -> dict[str, str]:
    return {"claim_category": category, "status": status, "message": message}


def _overall_claim_support(
    claims: list[dict[str, Any]],
    matches: list[dict[str, str]],
    mismatches: list[dict[str, str]],
    unsupported: list[dict[str, str]],
    honest: list[dict[str, str]],
    evidence: dict[str, Any],
) -> str:
    if mismatches:
        return "contradicted"
    if unsupported:
        if matches or honest:
            return "partially_supported"
        if not _has_substantive_evidence(evidence):
            return "insufficient_evidence"
        return "unsupported"
    if matches or honest:
        return "supported"
    if not claims or not _has_substantive_evidence(evidence):
        return "insufficient_evidence"
    return "partially_supported"


def _has_substantive_evidence(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("actual_changed_files")
        or evidence.get("patched_files")
        or evidence.get("generated_artifacts")
        or evidence.get("validation_status") in {"passed", "failed"}
        or evidence.get("benchmark_status") in {"passed", "failed"}
        or evidence.get("replay_status") in {"passed", "failed"}
    )


def _missing_evidence(trace: dict[str, Any], evidence: dict[str, Any], claims: list[dict[str, Any]]) -> list[dict[str, str]]:
    missing = [{"category": "trace", "reason": item} for item in evidence.get("missing_evidence", [])]
    categories = {str(claim.get("claim_category", "")) for claim in claims}
    if {"validation_claim", "test_claim"} & categories and evidence.get("validation_status") == "missing":
        missing.append({"category": "validation_status", "reason": "validation/test claim exists but validation evidence is missing"})
    if "benchmark_claim" in categories and evidence.get("benchmark_status") == "missing":
        missing.append({"category": "benchmark_status", "reason": "benchmark claim exists but benchmark evidence is missing"})
    if not _frames(trace):
        missing.append({"category": "trace_frames", "reason": "trace contract has no available frames"})
    return _dedupe_missing(missing)


def _status_from_text(text: str) -> str:
    if not text.strip():
        return "missing"
    if _FAILURE_RE.search(text):
        return "failed"
    if _SUCCESS_RE.search(text):
        return "passed"
    return "unknown"


def _positive_changed_files(text: str) -> set[str]:
    paths: set[str] = set()
    for sentence in re.split(r"(?:\r?\n|;|(?<=[.!?])\s+)", text):
        lower = sentence.lower()
        if not _CHANGE_RE.search(sentence):
            continue
        if "did not touch" in lower or "do not touch" in lower or "no changes" in lower:
            continue
        paths.update(_file_paths(sentence))
    return paths


def _file_paths(text: str) -> set[str]:
    paths: set[str] = set()
    normalized = text.replace("\\", "/")
    for raw in re.findall(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", normalized):
        clean = raw.strip("`'\"),.;:")
        clean = clean.removeprefix("a/").removeprefix("b/")
        if clean in {"dev/null", "a/dev/null", "b/dev/null"}:
            continue
        if "/" in clean and not clean.startswith(".agent/"):
            paths.add(clean)
    return paths


def _paths_from_json(data: Any, keys: tuple[str, ...]) -> set[str]:
    paths: set[str] = set()
    if not isinstance(data, dict):
        return paths
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            paths.update(_file_paths(value))
            if "/" in value.replace("\\", "/"):
                paths.add(value.replace("\\", "/").strip("`'\"),.;:"))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    paths.update(_file_paths(item))
                    if "/" in item.replace("\\", "/"):
                        paths.add(item.replace("\\", "/").strip("`'\"),.;:"))
                elif isinstance(item, dict):
                    paths.update(_paths_from_json(item, ("path", "file", "filename")))
    return {path for path in paths if path and not path.startswith(".agent/")}


def _artifact_paths(trace: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    raw = trace.get("artifact_references")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                path = str(item.get("artifact_path", ""))
                if path:
                    out.add(path.replace("\\", "/"))
    return out


def _missing_from_trace(trace: dict[str, Any]) -> list[str]:
    out: list[str] = []
    raw = trace.get("missing_evidence")
    if not isinstance(raw, list):
        raw = trace.get("missing_frames")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                frame_type = str(item.get("frame_type", "unknown"))
                reason = str(item.get("reason", item.get("evidence_status", "missing")))
                out.append(f"{frame_type}: {reason}")
    return _dedupe_text(out)


def _artifact_references(trace: dict[str, Any], artifacts: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    raw = trace.get("artifact_references")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                refs.append({"source": "trace", "artifact_path": str(item.get("artifact_path", ""))})
    for key, value in artifacts.items():
        if isinstance(value, dict):
            refs.append({"source": key, "artifact_path": str(value.get("path", ""))})
    return [ref for ref in refs if ref["artifact_path"]]


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "model_call_performed": False,
        "embedding_call_performed": False,
        "semantic_api_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "mcp_invocation_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "docker_or_subprocess_used": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "execution_blocking_performed": False,
        "writes_claim_diff_artifacts_only": True,
    }


def _blocked_report(*, check_id: str | None, created_at: str, message: str) -> dict[str, Any]:
    return {
        "report_kind": REPORT_KIND,
        "check_id": check_id or _default_check_id({}, {}, "", "", created_at),
        "created_at": str(created_at or ""),
        "trace_id": "",
        "trace_path": "",
        "score_id": "",
        "score_path": "",
        "mirror2_verdict": "",
        "overall_claim_support": "insufficient_evidence",
        "recommended_next_action": "collect_more_artifacts",
        "recommended_next_phase": "MIRROR.4",
        "claims_detected": [],
        "evidence_detected": {key: [] if key.endswith("files") or key.endswith("artifacts") else "missing" for key in EVIDENCE_CATEGORIES},
        "matches": [],
        "mismatches": [],
        "unsupported_claims": [],
        "honest_uncertainty_claims": [],
        "missing_evidence": [{"category": "blocked", "reason": message}],
        "artifact_references": [],
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def _resolve_input_path(repo_root: Path, raw: str | None, *, required: bool) -> Path | None:
    if raw is None or str(raw).strip() == "":
        return None
    raw_text = str(raw)
    raw_path = Path(raw_text).expanduser()
    if any(part == ".." for part in raw_path.parts):
        raise ValueError(f"refusing traversal path: {raw_text}")
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    _ensure_inside_repo(repo_root, resolved)
    if _is_forbidden_path(resolved):
        raise ValueError(f"refusing secret/env/key path: {raw_text}")
    if required and not resolved.is_file():
        raise ValueError(f"required input artifact is missing: {raw_text}")
    if not required and not resolved.exists():
        raise ValueError(f"input artifact is missing: {raw_text}")
    if not resolved.is_file():
        raise ValueError(f"input artifact is not a file: {raw_text}")
    return resolved


def _resolve_output_root(repo_root: Path, raw: str | None) -> Path:
    raw_path = Path(raw or DEFAULT_OUTPUT_ROOT).expanduser()
    if any(part == ".." for part in raw_path.parts):
        raise ValueError(f"refusing traversal output path: {raw or DEFAULT_OUTPUT_ROOT}")
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    _ensure_inside_repo(repo_root, resolved)
    return resolved


def _ensure_inside_repo(repo_root: Path, candidate: Path) -> None:
    try:
        candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"refusing path outside repository: {candidate}") from exc


def _is_forbidden_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if ".env" in parts or ".agent" in parts and "private" in parts:
        return True
    if any("secret" in part or "credential" in part for part in parts):
        return True
    if name.endswith((".key", ".pem")) or name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}:
        return True
    if "private_key" in name:
        return True
    return False


def _default_check_id(trace: dict[str, Any], score: dict[str, Any], trace_path: str, score_path: str, created_at: str) -> str:
    seed = json.dumps(
        {
            "trace_id": trace.get("trace_id", ""),
            "score_id": score.get("score_id", ""),
            "trace_path": str(trace_path or ""),
            "score_path": str(score_path or ""),
            "created_at": str(created_at or ""),
        },
        sort_keys=True,
    )
    return "mirror-claim-diff-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 22)] + " [excerpt truncated]"


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _claim_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{_md(item.get('claim_category'))}` from `{_md(item.get('source'))}` - {_md(item.get('excerpt'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _evidence_lines(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [f"`{_md(key)}` = `{_md(value[key])}`" for key in EVIDENCE_CATEGORIES if key in value]


def _check_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{_md(item.get('claim_category'))}` `{_md(item.get('status'))}` - {_md(item.get('message'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _missing_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{_md(item.get('category'))}` - {_md(item.get('reason'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _dedupe_text(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _dedupe_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for claim in claims:
        key = (
            claim.get("claim_category"),
            claim.get("source"),
            tuple(claim.get("claimed_files") or []),
            claim.get("polarity"),
            claim.get("only_claim"),
            claim.get("excerpt"),
        )
        if key not in seen:
            seen.add(key)
            out.append(claim)
    return out


def _dedupe_checks(checks: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for check in checks:
        key = (check["claim_category"], check["status"], check["message"])
        if key not in seen:
            seen.add(key)
            out.append(check)
    return out


def _dedupe_missing(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item["category"], item["reason"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
