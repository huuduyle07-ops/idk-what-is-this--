"""F.7 Worker Result Import / Review Stub.

Worker output from an external model is untrusted evidence until a human
reviews it. This module creates local review-stub artifacts only. It never
calls models, launches workers, applies patches, runs validation, imports
proposals, promotes lessons, creates teaching cards, triggers Dream, runs
Project Evolution, or calls webhooks/network.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_WORKER_RESULT_REVIEWS_DIRNAME = "worker_result_reviews"
MAX_EXCERPT_CHARS = 4000

REVIEW_STATUSES = {
    "pending_review",
    "needs_more_evidence",
    "ready_for_manual_proposal_review",
    "rejected",
}
TRUST_LEVELS = {"untrusted", "partially_supported", "review_ready", "rejected"}

_VISUAL_TOKENS = {
    "screenshot",
    "screenshots",
    "image",
    "images",
    "visual",
    "visuals",
    "ui",
    "layout",
    "layouts",
    "ocr",
    "chart",
    "charts",
    "poster",
    "posters",
    "design",
    "designs",
}
_SECURITY_TOKENS = {
    "auth",
    "authentication",
    "authorization",
    "credential",
    "credentials",
    "env",
    "secret",
    "secrets",
    "security",
    "token",
    "tokens",
    "webhook",
}
_SECURITY_PHRASES = {"api key", "api keys", "webhook security"}
_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_:/.\\-])"
    r"([A-Za-z0-9_.-]+(?:[/\\][A-Za-z0-9_.-]+)*"
    r"\.(?:py|js|ts|tsx|jsx|go|rs|cpp|c|h|hpp|cs|java|md|json|yaml|yml|html|css|sql|toml|txt))"
)
_VALIDATION_PATTERNS = [
    re.compile(r"\bpython\s+-m\s+pytest(?:\s+[^\n;]*)?", re.IGNORECASE),
    re.compile(r"\bpython\s+benchmarks/run_benchmarks\.py\s+--check(?:\s+[^\n;]*)?", re.IGNORECASE),
    re.compile(r"\bpytest(?:\s+[^\n;]*)?", re.IGNORECASE),
    re.compile(r"\bnpm\s+test(?:\s+[^\n;]*)?", re.IGNORECASE),
    re.compile(r"\bgo\s+test(?:\s+[^\n;]*)?", re.IGNORECASE),
    re.compile(r"\bcargo\s+test(?:\s+[^\n;]*)?", re.IGNORECASE),
]
_PASS_RE = re.compile(r"\b(tests?|validation|check|pytest)\s+(passed|pass|green|succeeded|ok)\b", re.IGNORECASE)
_FAIL_RE = re.compile(r"\b(tests?|validation|check|pytest)\s+(failed|fail|failing|red)\b", re.IGNORECASE)

_EXECUTION_BOUNDARY = [
    "No model was called.",
    "No worker was launched.",
    "No patch was applied.",
    "No validation was run.",
    "No proposal was imported.",
    "No lesson was promoted.",
    "No teaching card was created.",
    "No Dream / Project Evolution workflow was triggered.",
    "No webhook/network call occurred.",
]


def create_worker_result_review(
    *,
    repo_path: str | None = ".",
    worker_assignment_path: str | None = None,
    result_text: str | None = None,
    result_file_path: str | None = None,
    driver_decision_path: str | None = None,
    visual_evidence_contract_path: str | None = None,
    dry_run: bool = False,
    output_root: str | None = None,
    review_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path or ".").expanduser().resolve()
    assignment_path = Path(_text(worker_assignment_path)).expanduser()
    if not _text(worker_assignment_path):
        return _error_result(
            "missing_worker_assignment",
            "--worker-assignment is required",
            risk_flag="missing_worker_assignment",
        )
    if not assignment_path.is_file():
        return _error_result(
            "worker_assignment_not_found",
            f"worker assignment not found: {assignment_path}",
            status="not_found",
            risk_flag="missing_worker_assignment",
        )

    try:
        assignment = _read_json_object(assignment_path)
    except (json.JSONDecodeError, ValueError) as exc:
        return _error_result(
            "worker_assignment_invalid",
            f"worker assignment is invalid: {exc}",
            status="invalid",
        )

    driver_path = ""
    if _text(driver_decision_path):
        path = Path(_text(driver_decision_path)).expanduser()
        if not path.is_file():
            return _error_result("driver_decision_not_found", f"driver decision not found: {path}", status="not_found")
        driver_path = str(path.resolve())

    visual_path = ""
    if _text(visual_evidence_contract_path):
        path = Path(_text(visual_evidence_contract_path)).expanduser()
        if not path.is_file():
            return _error_result(
                "visual_evidence_contract_not_found",
                f"visual evidence contract not found: {path}",
                status="not_found",
            )
        visual_path = str(path.resolve())

    selected = _select_result_input(result_text=result_text, result_file_path=result_file_path)
    if not selected["ok"]:
        return selected
    worker_result_source = selected["source"]
    worker_result_path = selected["path"]
    worker_result = selected["text"]

    created = _text(created_at) or _utc_now_iso()
    record = _build_record(
        assignment=assignment,
        worker_assignment_path=str(assignment_path.resolve()),
        driver_decision_path=driver_path,
        visual_evidence_contract_path=visual_path,
        worker_result_source=worker_result_source,
        worker_result_path=worker_result_path,
        worker_result=worker_result,
        created_at=created,
        review_id=review_id,
    )
    markdown = render_worker_result_review_markdown(record)
    try:
        paths = _review_paths(repo_root, record["review_id"], output_root=output_root)
    except ValueError as exc:
        return _error_result("invalid_output_root", str(exc))

    if dry_run:
        return {
            "ok": True,
            "status": "dry_run",
            "dry_run": True,
            "json_path": str(paths["json"]),
            "md_path": str(paths["md"]),
            "record": record,
            "markdown": markdown,
        }

    if paths["json"].exists() or paths["md"].exists():
        return {
            "ok": False,
            "status": "already_exists",
            "dry_run": False,
            "json_path": str(paths["json"]),
            "md_path": str(paths["md"]),
            "record": record,
            "markdown": markdown,
            "error": {
                "code": "worker_result_review_already_exists",
                "message": "worker result review already exists; no files were overwritten",
            },
        }

    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["json"].write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["md"].write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "status": "review_created",
        "dry_run": False,
        "json_path": str(paths["json"]),
        "md_path": str(paths["md"]),
        "record": record,
        "markdown": markdown,
    }


def render_worker_result_review_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_worker_result_review_text(result: dict[str, Any]) -> str:
    lines = [
        "Worker Result Review Stub",
        f"Status: {_text(result.get('status'))}",
    ]
    record = result.get("record") if isinstance(result.get("record"), dict) else {}
    if record:
        lines.extend(
            [
                f"Review ID: {_text(record.get('review_id'))}",
                f"Trust level: {_text(record.get('trust_level'))}",
                f"Review status: {_text(record.get('review_status'))}",
                f"Eligible for proposal import: {record.get('eligible_for_proposal_import')}",
            ]
        )
    if result.get("json_path"):
        lines.append(f"JSON path: {_text(result.get('json_path'))}")
    if result.get("md_path"):
        lines.append(f"Markdown path: {_text(result.get('md_path'))}")
    if result.get("dry_run"):
        lines.append("Dry run: True")
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    if error:
        lines.append(f"Code: {_text(error.get('code'))}")
        lines.append(f"Reason: {_text(error.get('message'))}")
    return "\n".join(lines) + "\n"


def render_worker_result_review_markdown(record: dict[str, Any]) -> str:
    return (
        "# Worker Result Review Stub\n\n"
        f"Review ID: `{_text(record.get('review_id'))}`\n\n"
        "## Source Assignment\n\n"
        f"- Worker assignment: `{_text(record.get('worker_assignment_path'))}`\n"
        f"- Worker result source: `{_text(record.get('worker_result_source'))}`\n"
        f"- Worker result path: `{_text(record.get('worker_result_path')) or '(manual paste)'}`\n\n"
        "## Linked Driver / Visual Evidence\n\n"
        f"- Driver decision: `{_text(record.get('driver_decision_path')) or '(none)'}`\n"
        f"- Visual evidence contract: `{_text(record.get('visual_evidence_contract_path')) or '(none)'}`\n\n"
        "## Worker Result Excerpt\n\n"
        f"{_text(record.get('worker_result_excerpt')) or '(empty)'}\n\n"
        "## Claimed Changed Files\n\n"
        f"{_bullet_list(_strings(record.get('claimed_changed_files')))}\n\n"
        "## Claimed Validation\n\n"
        f"- Claimed validation passed: `{record.get('claimed_validation_passed')}`\n"
        "- Claimed validation commands:\n"
        f"{_bullet_list(_strings(record.get('claimed_validation_commands')), indent='  ')}\n\n"
        "## Risk Flags\n\n"
        f"{_bullet_list(_strings(record.get('risk_flags')))}\n\n"
        "## Missing Requirements\n\n"
        f"{_bullet_list(_strings(record.get('missing_requirements')))}\n\n"
        "## Recommended Next Actions\n\n"
        f"{_bullet_list(_strings(record.get('recommended_next_actions')))}\n\n"
        "## Review Status\n\n"
        f"- Review status: `{_text(record.get('review_status'))}`\n"
        f"- Trust level: `{_text(record.get('trust_level'))}`\n"
        f"- Human review required: `{record.get('human_review_required')}`\n"
        f"- Eligible for proposal import: `{record.get('eligible_for_proposal_import')}`\n"
        f"- Eligible for teaching card: `{record.get('eligible_for_teaching_card')}`\n\n"
        "## Execution Boundary\n\n"
        "This is an artifact-only review stub. Worker output remains untrusted until human review.\n\n"
        f"{_bullet_list(list(_EXECUTION_BOUNDARY))}\n"
    )


def _build_record(
    *,
    assignment: dict[str, Any],
    worker_assignment_path: str,
    driver_decision_path: str,
    visual_evidence_contract_path: str,
    worker_result_source: str,
    worker_result_path: str,
    worker_result: str,
    created_at: str,
    review_id: str | None,
) -> dict[str, Any]:
    excerpt = worker_result[:MAX_EXCERPT_CHARS]
    claimed_files = _extract_claimed_changed_files(worker_result)
    validation_commands = _extract_validation_commands(worker_result)
    validation_passed = _extract_validation_passed(worker_result)
    risk_flags: list[str] = ["worker_result_untrusted", "external_worker_output"]
    missing: list[str] = []
    actions: list[str] = ["Treat this worker result as untrusted evidence until a human reviews it."]

    if len(worker_result) > MAX_EXCERPT_CHARS:
        _add(risk_flags, "large_result_truncated")
        actions.append("Open the original worker result if the excerpt is insufficient.")
    if claimed_files:
        _add(risk_flags, "patch_claim_unverified")
        actions.append("Inspect claimed changed files before importing as a proposal.")
    if validation_passed is True:
        _add(risk_flags, "validation_claim_unverified")
        actions.append("Run validation yourself before trusting this result.")
    elif validation_passed is False:
        actions.append("Review failure before promotion/import.")
    if _mentions_visual(worker_result):
        _add(risk_flags, "visual_claim_requires_visual_contract")
        if not visual_evidence_contract_path:
            _add(missing, "visual_evidence_contract")
            actions.append(
                "Create or attach A.16 Visual Evidence Contract before claiming visual result is fixed."
            )
    if _mentions_security(worker_result):
        _add(risk_flags, "security_sensitive_claim")
        actions.append("Manually review security-sensitive changes before importing as a proposal.")
    if _has_blocked_execution_intent(worker_result):
        actions.append("Reject or manually inspect any worker claim of real repo apply, commit, push, or deploy.")

    eligible_for_proposal_import = bool(
        assignment
        and worker_result.strip()
        and claimed_files
        and not _has_blocked_execution_intent(worker_result)
    )
    title = _text(assignment.get("title")) or "worker-result-review"
    final_id = _safe_segment(
        review_id or f"{_timestamp_segment(created_at)}-{title}",
        "worker-result-review",
    )
    return {
        "review_id": final_id,
        "created_at": created_at,
        "source_type": "worker_result_review",
        "worker_assignment_path": worker_assignment_path,
        "driver_decision_path": driver_decision_path,
        "visual_evidence_contract_path": visual_evidence_contract_path,
        "worker_result_source": worker_result_source,
        "worker_result_path": worker_result_path,
        "worker_result_excerpt": excerpt,
        "claimed_changed_files": claimed_files,
        "claimed_validation_commands": validation_commands,
        "claimed_validation_passed": validation_passed,
        "claimed_risks": [],
        "review_status": "pending_review",
        "trust_level": "untrusted",
        "human_review_required": True,
        "eligible_for_proposal_import": eligible_for_proposal_import,
        "eligible_for_teaching_card": True,
        "risk_flags": _dedupe(risk_flags),
        "missing_requirements": _dedupe(missing),
        "recommended_next_actions": _dedupe(actions),
        "model_call_performed": False,
        "worker_launch_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "proposal_imported": False,
        "lesson_promotion_performed": False,
        "teaching_card_created": False,
        "dream_triggered": False,
        "project_evolution_triggered": False,
        "webhook_called": False,
    }


def _select_result_input(*, result_text: str | None, result_file_path: str | None) -> dict[str, Any]:
    has_text = bool(_text(result_text))
    has_file = bool(_text(result_file_path))
    if has_text and has_file:
        return _error_result(
            "ambiguous_result_input",
            "provide --result-text or --result-file, not both",
        )
    if has_text:
        return {
            "ok": True,
            "source": "manual_paste",
            "path": "",
            "text": _text(result_text),
        }
    if has_file:
        path = Path(_text(result_file_path)).expanduser()
        if not path.is_file():
            return _error_result("result_file_not_found", f"worker result file not found: {path}", status="not_found")
        return {
            "ok": True,
            "source": "file",
            "path": str(path.resolve()),
            "text": path.read_text(encoding="utf-8"),
        }
    return _error_result(
        "missing_result_text",
        "provide --result-text or --result-file",
        risk_flag="missing_result_text",
    )


def _extract_claimed_changed_files(text: str) -> list[str]:
    paths: list[str] = []
    for match in _PATH_RE.finditer(text):
        cleaned = _safe_rel_path(match.group(1))
        if cleaned:
            paths.append(cleaned)
    return _dedupe(paths)


def _extract_validation_commands(text: str) -> list[str]:
    commands: list[str] = []
    for line in text.splitlines():
        matched_spans: list[tuple[int, int]] = []
        for pattern in _VALIDATION_PATTERNS:
            for match in pattern.finditer(line):
                if _span_overlaps(match.span(), matched_spans):
                    continue
                matched_spans.append(match.span())
                command = _clean_validation_command(match.group(0))
                if command:
                    commands.append(command)
    return _dedupe(commands)


def _span_overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < existing_end and end > existing_start for existing_start, existing_end in spans)


def _clean_validation_command(command: str) -> str:
    cleaned = re.split(
        r"\s+\b(?:and|then)\b\s+(?:all\s+)?(?:tests?|validation|check|pytest)\s+"
        r"(?:passed|pass|failed|fail|green|red|succeeded|ok)\b",
        _text(command),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return cleaned.strip(" ,.;:")


def _extract_validation_passed(text: str) -> bool | None:
    if _FAIL_RE.search(text):
        return False
    if _PASS_RE.search(text):
        return True
    return None


def _mentions_visual(text: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return not words.isdisjoint(_VISUAL_TOKENS)


def _mentions_security(text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in _SECURITY_PHRASES):
        return True
    words = set(re.findall(r"[a-z0-9]+", lowered))
    return not words.isdisjoint(_SECURITY_TOKENS)


def _has_blocked_execution_intent(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "applied patch to your repo",
        "committed",
        "pushed",
        "deployed",
        "opened a pr",
        "launched worker",
        "promoted lesson",
    ]
    return any(marker in lowered for marker in markers)


def _read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("source JSON must contain an object")
    return data


def _review_paths(repo_root: Path, review_id: str, *, output_root: str | None) -> dict[str, Path]:
    root = _output_root(repo_root, output_root)
    directory = root / _safe_segment(review_id, "worker-result-review")
    return {
        "dir": directory,
        "json": directory / "worker_result_review.json",
        "md": directory / "worker_result_review.md",
    }


def _output_root(repo_root: Path, output_root: str | None) -> Path:
    base = (repo_root / ".agent" / DEFAULT_WORKER_RESULT_REVIEWS_DIRNAME).resolve()
    if _text(output_root):
        root = Path(_text(output_root)).expanduser()
        if not root.is_absolute():
            root = repo_root / root
        resolved = root.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"output_root must stay inside {base}: {resolved}") from exc
        return resolved
    return base


def _error_result(
    code: str,
    message: str,
    *,
    status: str = "error",
    risk_flag: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "status": status,
        "dry_run": False,
        "json_path": "",
        "md_path": "",
        "error": {"code": code, "message": message},
    }
    if risk_flag:
        result["risk_flags"] = [risk_flag]
    return result


def _safe_rel_path(value: str) -> str:
    text = _text(value).replace("\\", "/")
    if not text or text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        return ""
    parts = [part for part in text.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return ""
    return "/".join(parts)


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _bullet_list(items: list[str], *, indent: str = "") -> str:
    if not items:
        return f"{indent}- None"
    return "\n".join(f"{indent}- {item}" for item in items)


def _add(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_segment(value: str, fallback: str) -> str:
    chars: list[str] = []
    last_dash = False
    for char in _text(value):
        if char.isalnum():
            chars.append(char.lower())
            last_dash = False
        elif char in {"-", "_"}:
            chars.append(char)
            last_dash = False
        elif chars and not last_dash:
            chars.append("-")
            last_dash = True
    segment = "".join(chars).strip("-_")
    return segment[:96] or fallback


def _timestamp_segment(created_at: str) -> str:
    return _safe_segment(created_at.replace(":", "-"), "worker-result-review")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
