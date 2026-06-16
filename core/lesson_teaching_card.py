"""F.6 Lesson Teaching Card / Teacher Mode v0.

Turns existing lesson-like artifacts into local, human-readable teaching cards.
This module is formatting/education only: it reads one JSON artifact and writes
inert ``teaching_card.json`` / ``teaching_card.md`` files under
``.agent/teaching_cards``. It never calls models, promotes lessons, creates
anti-lessons, applies patches, runs validation, launches workers, starts Dream,
runs Project Evolution, or calls webhooks/network.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEACHING_CARDS_DIRNAME = "teaching_cards"

SourceType = Literal["lesson", "anti_lesson", "benchmark_case", "failure_report"]

_EXECUTION_BOUNDARY = [
    "No model was called.",
    "No lesson was promoted.",
    "No anti-lesson was created.",
    "No patch was applied.",
    "No validation was run.",
    "No worker was launched.",
    "Dream was not triggered.",
    "Project Evolution was not triggered.",
    "No webhook or network call was made.",
]

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
_VISUAL_PHRASES = {
    "visual evidence",
    "ui layout",
    "user interface",
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
}
_SECURITY_PHRASES = {
    "api key",
    "api keys",
    "environment variable",
    "environment variables",
}

_UNTRUSTED_TOKENS = {
    "discord",
    "external",
    "n8n",
    "untrusted",
    "webhook",
}
_UNTRUSTED_PHRASES = {
    "external queue",
    "external_queue",
    "source trust",
}


def create_lesson_teaching_card(
    *,
    repo_path: str | None = ".",
    lesson_path: str | None = None,
    anti_lesson_path: str | None = None,
    benchmark_case_path: str | None = None,
    failure_report_path: str | None = None,
    source: dict[str, Any] | None = None,
    source_type: str | None = None,
    source_path: str | None = None,
    dry_run: bool = False,
    output_root: str | None = None,
    created_at: str | None = None,
    teaching_card_id: str | None = None,
) -> dict[str, Any]:
    """Build a teaching card and optionally write inert artifacts."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    selected = _selected_source(
        lesson_path=lesson_path,
        anti_lesson_path=anti_lesson_path,
        benchmark_case_path=benchmark_case_path,
        failure_report_path=failure_report_path,
        source=source,
        source_type=source_type,
    )
    if not selected:
        return _error_result("invalid_source", "exactly one source artifact is required")

    selected_type, selected_path, inline_source = selected
    resolved_source_path = ""
    if inline_source is not None:
        if not isinstance(inline_source, dict):
            return _error_result("source_invalid", "source must be a JSON object", status="invalid")
        source_data = inline_source
        resolved_source_path = _text(source_path) or _text(source_data.get("source_path"))
    else:
        path = Path(_text(selected_path)).expanduser()
        if not path.is_file():
            return _error_result(
                "source_not_found",
                f"source artifact not found: {path}",
                status="not_found",
                source_type=selected_type,
            )
        try:
            source_data = _read_json_object(path)
        except (json.JSONDecodeError, ValueError) as exc:
            return _error_result(
                "source_invalid",
                f"source artifact is invalid: {exc}",
                status="invalid",
                source_type=selected_type,
            )
        resolved_source_path = str(path.resolve())

    actual_source_type = _detect_source_type(selected_type, source_data)
    created = _text(created_at) or _utc_now_iso()
    record = _build_record(
        source=source_data,
        source_type=actual_source_type,
        source_path=resolved_source_path,
        created_at=created,
        teaching_card_id=teaching_card_id,
    )
    markdown = render_lesson_teaching_card_markdown(record)
    try:
        paths = _card_paths(repo_root, record["teaching_card_id"], output_root=output_root)
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
                "code": "teaching_card_already_exists",
                "message": "teaching card already exists; no files were overwritten",
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
        "status": "card_created",
        "dry_run": False,
        "json_path": str(paths["json"]),
        "md_path": str(paths["md"]),
        "record": record,
        "markdown": markdown,
    }


def render_lesson_teaching_card_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_lesson_teaching_card_text(result: dict[str, Any]) -> str:
    lines = [
        "Teaching Card",
        f"Status: {_text(result.get('status'))}",
    ]
    record = result.get("record") if isinstance(result.get("record"), dict) else {}
    if record:
        lines.extend(
            [
                f"Teaching card id: {_text(record.get('teaching_card_id'))}",
                f"Source type: {_text(record.get('source_type'))}",
                f"Title: {_text(record.get('title'))}",
            ]
        )
    if result.get("json_path"):
        lines.append(f"JSON path: {_text(result.get('json_path'))}")
    if result.get("md_path"):
        lines.append(f"Markdown path: {_text(result.get('md_path'))}")
        if result.get("dry_run"):
            lines.append("Copy this Markdown: rerun without --dry-run, then copy the Markdown path above.")
        else:
            lines.append(f"Copy this Markdown: {_text(result.get('md_path'))}")
    if result.get("dry_run"):
        lines.append("Dry run: True")
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    if error:
        lines.append(f"Code: {_text(error.get('code'))}")
        lines.append(f"Reason: {_text(error.get('message'))}")
    return "\n".join(lines) + "\n"


def render_lesson_teaching_card_markdown(record: dict[str, Any]) -> str:
    return (
        "# Teaching Card\n\n"
        f"Teaching card id: `{_text(record.get('teaching_card_id'))}`\n\n"
        "## Source\n\n"
        f"- Source type: `{_text(record.get('source_type'))}`\n"
        f"- Source path: `{_text(record.get('source_path'))}`\n"
        f"- Title: {_text(record.get('title')) or 'Untitled source'}\n\n"
        "## Summary\n\n"
        f"{_text(record.get('summary')) or 'No concise summary was present in the source artifact.'}\n\n"
        "## What Happened\n\n"
        f"{_text(record.get('what_happened'))}\n\n"
        "## Why It Matters\n\n"
        f"{_text(record.get('why_it_matters'))}\n\n"
        "## Common Trap\n\n"
        f"{_text(record.get('common_trap'))}\n\n"
        "## Safe Fix Strategy\n\n"
        f"{_text(record.get('safe_fix_strategy'))}\n\n"
        "## Anti-pattern Warning\n\n"
        f"{_text(record.get('anti_pattern_warning')) or 'None from the source artifact.'}\n\n"
        "## Mini Quiz\n\n"
        f"{_bullet_list(_strings(record.get('mini_quiz')))}\n\n"
        "## Mini Exercise\n\n"
        f"{_text(record.get('mini_exercise'))}\n\n"
        "## Related Artifacts\n\n"
        f"{_bullet_list(_strings(record.get('related_artifacts')))}\n\n"
        "## Uncertainty Notes\n\n"
        f"{_bullet_list(_strings(record.get('uncertainty_notes')))}\n\n"
        "## Execution Boundary\n\n"
        "This teaching card is local artifact formatting only.\n\n"
        f"{_bullet_list(list(_EXECUTION_BOUNDARY))}\n"
    )


def _selected_source(
    *,
    lesson_path: str | None,
    anti_lesson_path: str | None,
    benchmark_case_path: str | None,
    failure_report_path: str | None,
    source: dict[str, Any] | None,
    source_type: str | None,
) -> tuple[SourceType, str | None, dict[str, Any] | None] | None:
    candidates: list[tuple[SourceType, str | None, dict[str, Any] | None]] = []
    if _text(lesson_path):
        candidates.append(("lesson", _text(lesson_path), None))
    if _text(anti_lesson_path):
        candidates.append(("anti_lesson", _text(anti_lesson_path), None))
    if _text(benchmark_case_path):
        candidates.append(("benchmark_case", _text(benchmark_case_path), None))
    if _text(failure_report_path):
        candidates.append(("failure_report", _text(failure_report_path), None))
    if source is not None:
        normalized = _normalize_source_type(source_type)
        if not normalized:
            return None
        candidates.append((normalized, None, source))
    if len(candidates) != 1:
        return None
    return candidates[0]


def _normalize_source_type(value: str | None) -> SourceType | None:
    key = _text(value).lower().replace("-", "_").replace(" ", "_")
    aliases: dict[str, SourceType] = {
        "lesson": "lesson",
        "anti_lesson": "anti_lesson",
        "antilesson": "anti_lesson",
        "benchmark": "benchmark_case",
        "benchmark_case": "benchmark_case",
        "failure": "failure_report",
        "failure_report": "failure_report",
        "failure_category": "failure_report",
    }
    return aliases.get(key)


def _read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("source JSON must contain an object")
    return data


def _detect_source_type(selected_type: SourceType, source: dict[str, Any]) -> SourceType:
    if selected_type == "lesson" and _source_is_anti_lesson(source):
        return "anti_lesson"
    return selected_type


def _source_is_anti_lesson(source: dict[str, Any]) -> bool:
    candidate = source.get("candidate") if isinstance(source.get("candidate"), dict) else {}
    return bool(
        source.get("kind") == "anti_lesson"
        or source.get("anti_lesson") is True
        or candidate.get("anti_lesson") is True
        or candidate.get("tempting_wrong_pattern")
    )


def _build_record(
    *,
    source: dict[str, Any],
    source_type: SourceType,
    source_path: str,
    created_at: str,
    teaching_card_id: str | None,
) -> dict[str, Any]:
    title = _title(source_type, source)
    summary = _summary(source_type, source)
    warnings, uncertainty = _warnings_and_uncertainty(source_type, source, summary, title, source_path)
    record = {
        "teaching_card_id": _safe_segment(
            teaching_card_id or f"{_timestamp_segment(created_at)}-{title}",
            "teaching-card",
        ),
        "created_at": created_at,
        "source_type": source_type,
        "source_path": source_path,
        "title": title,
        "summary": summary,
        "what_happened": _what_happened(source_type, source, summary),
        "why_it_matters": _why_it_matters(source_type, source),
        "common_trap": _common_trap(source_type, source),
        "safe_fix_strategy": _safe_fix_strategy(source_type, source),
        "anti_pattern_warning": _anti_pattern_warning(source_type, source, warnings),
        "mini_quiz": _mini_quiz(source_type, source),
        "mini_exercise": _mini_exercise(source_type, source),
        "related_artifacts": _related_artifacts(source),
        "uncertainty_notes": uncertainty,
        "human_review_recommended": True,
        "model_call_performed": False,
        "lesson_promotion_performed": False,
        "anti_lesson_created": False,
        "patch_applied": False,
        "validation_run": False,
        "worker_launch_performed": False,
        "dream_triggered": False,
        "project_evolution_triggered": False,
    }
    return record


def _title(source_type: SourceType, source: dict[str, Any]) -> str:
    if source_type == "benchmark_case":
        name = _first_text(source.get("name"), source.get("case_name"), source.get("title"))
        return f"Benchmark case: {name}" if name else "Benchmark case"
    if source_type == "failure_report":
        phase = _first_text(
            source.get("phase"),
            _nested(source, "meta", "report_path"),
            source.get("title"),
        )
        return f"Failure report: {phase}" if phase else "Failure report"
    if source_type == "anti_lesson":
        return _first_text(
            source.get("title"),
            _nested(source, "candidate", "tempting_wrong_pattern"),
            source.get("summary"),
            "Anti-lesson teaching card",
        )
    return _first_text(
        source.get("title"),
        source.get("summary"),
        source.get("case_name"),
        _nested(source, "candidate", "case_name"),
        "Lesson teaching card",
    )


def _summary(source_type: SourceType, source: dict[str, Any]) -> str:
    if source_type == "anti_lesson":
        return _first_text(
            source.get("summary"),
            _nested(source, "candidate", "why_wrong"),
            _nested(source, "candidate", "tempting_wrong_pattern"),
            "This anti-lesson source is missing a concise summary.",
        )
    if source_type == "benchmark_case":
        return _first_text(
            source.get("prompt"),
            source.get("summary"),
            source.get("description"),
            source.get("category"),
            "This benchmark case source is missing a concise summary.",
        )
    if source_type == "failure_report":
        return _first_text(
            source.get("summary"),
            source.get("guardrail_note"),
            _run_health_summary(source),
            "This failure report source is missing a concise summary.",
        )
    return _first_text(
        source.get("summary"),
        _nested(source, "candidate", "patch_summary"),
        _nested(source, "candidate", "validation_summary", "validation_output_tail"),
        "This lesson source is missing a concise summary.",
    )


def _what_happened(source_type: SourceType, source: dict[str, Any], summary: str) -> str:
    if source_type == "anti_lesson":
        parts = [
            _sentence("Tempting pattern", _nested(source, "candidate", "tempting_wrong_pattern")),
            _sentence("Why wrong", _nested(source, "candidate", "why_wrong")),
            _sentence("Evidence refs", _join(_strings(_nested(source, "candidate", "evidence_refs")))),
        ]
        return _join_sentences(parts) or summary
    if source_type == "benchmark_case":
        parts = [
            _sentence("Case", _first_text(source.get("name"), source.get("case_name"))),
            _sentence("Language", source.get("language")),
            _sentence("Category", source.get("category")),
            _sentence("Difficulty", source.get("difficulty")),
            _sentence("Prompt", source.get("prompt")),
            _sentence("Expected changed files", _join(_strings(source.get("expected_changed_files")))),
            _sentence("Forbidden changed files", _join(_strings(source.get("forbidden_changed_files")))),
            _sentence("Validation command", source.get("validation_command")),
        ]
        return _join_sentences(parts) or summary
    if source_type == "failure_report":
        parts = [
            _sentence("Phase", source.get("phase")),
            _sentence("Guardrail note", source.get("guardrail_note")),
            _sentence("Run health", _run_health_summary(source)),
            _sentence("Failure categories", _failure_category_summary(source)),
        ]
        return _join_sentences(parts) or summary
    candidate = source.get("candidate") if isinstance(source.get("candidate"), dict) else {}
    parts = [
        _sentence("Summary", summary),
        _sentence("Case", _first_text(source.get("case_name"), candidate.get("case_name"))),
        _sentence("Language", candidate.get("language")),
        _sentence("Category", candidate.get("category")),
        _sentence("Changed files", _join(_strings(candidate.get("changed_files")))),
        _sentence("Validation", _validation_summary(candidate)),
        _sentence("Evaluation", _join(_strings(_nested(source, "evaluation", "reasons")))),
    ]
    return _join_sentences(parts) or summary


def _why_it_matters(source_type: SourceType, source: dict[str, Any]) -> str:
    if source_type == "anti_lesson":
        why = _text(_nested(source, "candidate", "why_wrong"))
        return why or "This anti-lesson matters because the artifact marks a tempting pattern as unsafe."
    if source_type == "benchmark_case":
        category = _text(source.get("category"))
        expected = _strings(source.get("expected_changed_files"))
        if category or expected:
            return _join_sentences(
                [
                    _sentence("Benchmark category", category),
                    _sentence("Expected scope", _join(expected)),
                ]
            )
        return "This benchmark case matters because it defines a concrete expected behavior and validation target."
    if source_type == "failure_report":
        health = _run_health_summary(source)
        categories = _failure_category_summary(source)
        return _join_sentences(
            [
                _sentence("Failure evidence", health),
                _sentence("Category signal", categories),
            ]
        ) or "This report matters because it preserves observed failure evidence."
    source_report = _first_text(source.get("source_report"), _nested(source, "candidate", "source_report"))
    reasons = _join(_strings(_nested(source, "evaluation", "reasons")))
    return _join_sentences(
        [
            _sentence("Evidence source", source_report),
            _sentence("Evaluation reasons", reasons),
        ]
    ) or "This lesson matters only when the current situation matches the source artifact evidence."


def _common_trap(source_type: SourceType, source: dict[str, Any]) -> str:
    if source_type == "anti_lesson":
        return _first_text(
            _nested(source, "candidate", "tempting_wrong_pattern"),
            source.get("summary"),
            "Repeating the unsafe pattern from the anti-lesson.",
        )
    if source_type == "benchmark_case":
        forbidden = _join(_strings(source.get("forbidden_changed_files")))
        if forbidden:
            return f"Editing forbidden files: {forbidden}."
        return _first_text(source.get("category"), "Treating the benchmark prompt as broader than it is.")
    candidate = source.get("candidate") if isinstance(source.get("candidate"), dict) else {}
    missing_expected = _join(_strings(candidate.get("missing_expected_files")))
    touched_forbidden = _join(_strings(candidate.get("touched_forbidden_files")))
    if touched_forbidden:
        return f"Touching forbidden files: {touched_forbidden}."
    if missing_expected:
        return f"Missing expected files: {missing_expected}."
    if source_type == "failure_report":
        return "Assuming the category report proves a fix instead of treating it as failure evidence."
    return _first_text(
        candidate.get("category"),
        "Applying the lesson without matching evidence from the current task.",
    )


def _safe_fix_strategy(source_type: SourceType, source: dict[str, Any]) -> str:
    if source_type == "anti_lesson":
        return _first_text(
            _nested(source, "candidate", "safer_alternative"),
            "Avoid the tempting pattern and gather stronger evidence before acting.",
        )
    if source_type == "benchmark_case":
        expected = _join(_strings(source.get("expected_changed_files")))
        forbidden = _join(_strings(source.get("forbidden_changed_files")))
        command = _text(source.get("validation_command"))
        parts = [
            _sentence("Stay within expected files", expected),
            _sentence("Avoid forbidden files", forbidden),
            _sentence("Validation named by artifact", command),
        ]
        return _join_sentences(parts) or "Use the benchmark prompt as the scope boundary before proposing any fix."
    candidate = source.get("candidate") if isinstance(source.get("candidate"), dict) else {}
    changed = _join(_strings(candidate.get("changed_files")))
    validation = _validation_summary(candidate)
    if source_type == "failure_report":
        return "Use the report to identify the failure category, then inspect original evidence before trusting any fix."
    return _join_sentences(
        [
            _sentence("Review changed files", changed),
            _sentence("Review validation evidence", validation),
        ]
    ) or "Compare the artifact evidence to the current situation before applying the lesson."


def _anti_pattern_warning(source_type: SourceType, source: dict[str, Any], warnings: list[str]) -> str:
    parts: list[str] = []
    if source_type == "anti_lesson":
        tempting = _text(_nested(source, "candidate", "tempting_wrong_pattern"))
        if tempting:
            parts.append(f"Do not repeat this anti-lesson: {tempting}.")
        else:
            parts.append("Do not treat this anti-lesson as a positive recommendation.")
    parts.extend(warnings)
    return " ".join(parts).strip()


def _mini_quiz(source_type: SourceType, source: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    if source_type == "anti_lesson":
        if _text(_nested(source, "candidate", "tempting_wrong_pattern")):
            questions.append("What tempting pattern does this anti-lesson warn against?")
        if _text(_nested(source, "candidate", "why_wrong")):
            questions.append("Why does the artifact say that pattern is unsafe?")
        if _text(_nested(source, "candidate", "safer_alternative")):
            questions.append("What safer alternative does the artifact name?")
    elif source_type == "benchmark_case":
        if _text(source.get("category")):
            questions.append("What benchmark category does this case belong to?")
        if _strings(source.get("expected_changed_files")):
            questions.append("Which files does the artifact expect to change?")
        if _strings(source.get("forbidden_changed_files")):
            questions.append("Which files does the artifact forbid changing?")
    elif source_type == "failure_report":
        if _failure_category_summary(source):
            questions.append("Which failure categories appear in this report?")
        if _run_health_summary(source):
            questions.append("What passed and failed counts does the report record?")
    else:
        if _text(source.get("source_report")):
            questions.append("Which source report supports this lesson?")
        if _strings(_nested(source, "candidate", "changed_files")):
            questions.append("Which files did the lesson artifact say changed?")
        if _validation_summary(source.get("candidate") if isinstance(source.get("candidate"), dict) else {}):
            questions.append("What validation evidence does the artifact include?")

    questions.extend(
        [
            "What evidence supports this lesson?",
            "What would make this lesson unsafe to apply?",
            "What validation would you run before trusting this fix?",
        ]
    )
    return _dedupe([q if q.endswith("?") else f"{q}?" for q in questions])[:3]


def _mini_exercise(source_type: SourceType, source: dict[str, Any]) -> str:
    if source_type == "anti_lesson":
        tempting = _text(_nested(source, "candidate", "tempting_wrong_pattern"))
        if tempting:
            return (
                "Find one situation where this tempting pattern might appear, "
                "then write the evidence you would need before rejecting it."
            )
    files = _strings(source.get("expected_changed_files"))
    if not files:
        files = _strings(_nested(source, "candidate", "changed_files"))
    if files:
        return (
            f"Pick one listed file ({files[0]}) and list what evidence you would "
            "need before using this teaching card."
        )
    return (
        "Find one file or situation where this lesson might apply, then list "
        "what evidence you would need before using it."
    )


def _related_artifacts(source: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "source_report",
        "source_item_path",
        "source_review_path",
        "report_path",
        "guardrail_note",
    ):
        values.append(_text(source.get(key)))
    meta = source.get("meta") if isinstance(source.get("meta"), dict) else {}
    values.extend([_text(meta.get("report_path")), _text(meta.get("source_path"))])
    candidate = source.get("candidate") if isinstance(source.get("candidate"), dict) else {}
    values.extend(
        [
            _text(candidate.get("source_report")),
            *_strings(candidate.get("evidence_refs")),
            *_strings(candidate.get("related_lesson_ids")),
        ]
    )
    return _dedupe([value for value in values if value])


def _warnings_and_uncertainty(
    source_type: SourceType,
    source: dict[str, Any],
    summary: str,
    title: str,
    source_path: str,
) -> tuple[list[str], list[str]]:
    scan_text = " ".join([_flatten_text(source), source_path]).lower()
    warnings: list[str] = []
    notes: list[str] = []
    if _mentions(scan_text, _VISUAL_TOKENS, _VISUAL_PHRASES):
        warning = "Visual claims need visual verification before they are trusted."
        warnings.append(warning)
        notes.append(warning)
    if _mentions(scan_text, _SECURITY_TOKENS, _SECURITY_PHRASES):
        warning = (
            "Security-sensitive warning: auth/secrets/API keys/env/token evidence "
            "must be reviewed carefully before applying this card."
        )
        warnings.append(warning)
        notes.append(warning)
    if _mentions(scan_text, _UNTRUSTED_TOKENS, _UNTRUSTED_PHRASES):
        warning = (
            "Source-trust warning: this artifact appears to come from an external "
            "or untrusted source; verify provenance before using it."
        )
        warnings.append(warning)
        notes.append(warning)

    if _is_thin_source(source_type, source, summary, title):
        notes.append(
            "Source artifact is thin or incomplete; review the original artifact before using this card."
        )
    return _dedupe(warnings), _dedupe(notes)


def _is_thin_source(source_type: SourceType, source: dict[str, Any], summary: str, title: str) -> bool:
    if not source:
        return True
    generic_bits = [
        "missing a concise summary",
        "teaching card",
        "benchmark case",
        "failure report",
    ]
    generic_summary = any(bit in summary.lower() for bit in generic_bits)
    generic_title = title in {
        "Lesson teaching card",
        "Anti-lesson teaching card",
        "Benchmark case",
        "Failure report",
    }
    if generic_summary or generic_title:
        return True
    if source_type in {"lesson", "anti_lesson"}:
        candidate = source.get("candidate") if isinstance(source.get("candidate"), dict) else {}
        return not any(
            _text(value)
            for value in [
                source.get("summary"),
                source.get("source_report"),
                candidate.get("patch_summary"),
                candidate.get("why_wrong"),
                candidate.get("safer_alternative"),
            ]
        )
    return False


def _run_health_summary(source: dict[str, Any]) -> str:
    health = source.get("run_health") if isinstance(source.get("run_health"), dict) else {}
    parts = []
    if "passed" in health:
        parts.append(f"passed={health.get('passed')}")
    if "failed" in health:
        parts.append(f"failed={health.get('failed')}")
    return ", ".join(parts)


def _failure_category_summary(source: dict[str, Any]) -> str:
    health = source.get("run_health") if isinstance(source.get("run_health"), dict) else {}
    counts = health.get("failure_category_counts")
    if isinstance(counts, dict):
        return ", ".join(f"{key}: {value}" for key, value in counts.items())
    category_fields = source.get("category_fields") if isinstance(source.get("category_fields"), dict) else {}
    values = _strings(category_fields.get("cases_with_all_fields"))
    return _join(values)


def _validation_summary(candidate: dict[str, Any]) -> str:
    validation = candidate.get("validation_summary") if isinstance(candidate.get("validation_summary"), dict) else {}
    parts = []
    if "validation_ok" in candidate:
        parts.append(f"validation_ok={candidate.get('validation_ok')}")
    if "validation_ok" in validation:
        parts.append(f"validation_ok={validation.get('validation_ok')}")
    tail = _text(validation.get("validation_output_tail"))
    if tail:
        parts.append(tail)
    return "; ".join(parts)


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _flatten_text(value: Any) -> str:
    out: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            out.append(str(key))
            out.append(_flatten_text(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            out.append(_flatten_text(item))
    elif value is not None:
        out.append(str(value))
    return " ".join(out)


def _mentions(text: str, tokens: set[str], phrases: set[str]) -> bool:
    if any(phrase in text for phrase in phrases):
        return True
    words = set(re.findall(r"[a-z0-9]+", text))
    return not words.isdisjoint(tokens)


def _sentence(label: str, value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return f"{label}: {text}."


def _join_sentences(parts: list[str]) -> str:
    return " ".join(part for part in parts if part)


def _join(values: list[str]) -> str:
    return ", ".join(_dedupe(values))


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text[:600]
    return ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _card_paths(repo_root: Path, card_id: str, *, output_root: str | None) -> dict[str, Path]:
    root = _output_root(repo_root, output_root)
    directory = root / _safe_segment(card_id, "teaching-card")
    return {
        "dir": directory,
        "json": directory / "teaching_card.json",
        "md": directory / "teaching_card.md",
    }


def _output_root(repo_root: Path, output_root: str | None) -> Path:
    base = (repo_root / ".agent" / DEFAULT_TEACHING_CARDS_DIRNAME).resolve()
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
    source_type: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "status": status,
        "dry_run": False,
        "json_path": "",
        "md_path": "",
        "error": {"code": code, "message": message},
    }
    if source_type:
        result["source_type"] = source_type
    return result


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
    return _safe_segment(created_at.replace(":", "-"), "teaching-card")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
