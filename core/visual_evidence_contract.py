"""A.16 Visual Evidence Intake Contract — contract/report-only.

Text/code validation can pass while nobody has actually confirmed that a
visual / UI / design issue was fixed. A.16 closes that gap with a *pure*
contract: given a Worker Assignment (F.5) or a Driver Decision (H.1) it records
whether a visual issue is referenced, whether visual evidence or a human
caption summary exists, whether a model could even read that evidence, and
whether validation explicitly covers the visual issue. From those facts it
decides whether a "resolution claim" is allowed.

Core rule: do **not** claim a visual/UI/design issue is resolved just because
text tests passed.

This module never:

* performs OCR
* calls a vision model
* calls any model
* switches providers / spends API credits
* launches workers
* applies patches
* runs validation
* triggers Dream
* triggers Project Evolution execution
* calls webhooks / network
* promotes lessons

It only reads a source artifact (a JSON file or an in-memory dict) and writes
inert ``visual_evidence_contract.json`` / ``visual_evidence_contract.md``
artifacts under ``.agent/visual_evidence``. It does not inspect image bytes —
``visual_evidence_readable_by_model`` and ``validation_covers_visual_issue`` are
only ever set true when the operator passes them explicitly.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VISUAL_EVIDENCE_DIRNAME = "visual_evidence"

# Driver vehicle level (H.1) that signals a visual task. Kept as a local string
# constant so A.16 does NOT import the routing module (and so the guardrail
# tests can keep this layer free of cross-module dependencies).
VISION_OR_HUMAN_CAPTION_REQUIRED = "vision_or_human_caption_required"

# --- Stable risk flags ----------------------------------------------------
SOURCE_MENTIONS_VISUAL_ISSUE = "source_mentions_visual_issue"
VISUAL_PATHS_MISSING = "visual_paths_missing"
VISION_MODEL_UNAVAILABLE = "vision_model_unavailable"
HUMAN_VISUAL_SUMMARY_MISSING = "human_visual_summary_missing"
VALIDATION_DOES_NOT_COVER_VISUAL_ISSUE = "validation_does_not_cover_visual_issue"
VISUAL_EVIDENCE_UNVERIFIED = "visual_evidence_unverified"
RESOLUTION_CLAIM_NOT_ALLOWED = "resolution_claim_not_allowed"

RISK_FLAGS = [
    VISUAL_EVIDENCE_UNVERIFIED,
    HUMAN_VISUAL_SUMMARY_MISSING,
    VISION_MODEL_UNAVAILABLE,
    VALIDATION_DOES_NOT_COVER_VISUAL_ISSUE,
    RESOLUTION_CLAIM_NOT_ALLOWED,
    VISUAL_PATHS_MISSING,
    SOURCE_MENTIONS_VISUAL_ISSUE,
]

# --- Stable missing requirements ------------------------------------------
HUMAN_VISUAL_SUMMARY_OR_VISION_MODEL = "human_visual_summary_or_vision_model"
VISUAL_EVIDENCE_PATH_OR_CAPTION = "visual_evidence_path_or_caption"
VISUAL_VERIFICATION_STEP = "visual_verification_step"
EXPLICIT_VISUAL_VALIDATION_COVERAGE = "explicit_visual_validation_coverage"

MISSING_REQUIREMENTS = [
    HUMAN_VISUAL_SUMMARY_OR_VISION_MODEL,
    VISUAL_EVIDENCE_PATH_OR_CAPTION,
    VISUAL_VERIFICATION_STEP,
    EXPLICIT_VISUAL_VALIDATION_COVERAGE,
]

# Visual-reference keyword sets. Single tokens are matched on word boundaries
# (so "building" does NOT match "ui"); phrases are matched as substrings.
VISUAL_TOKENS = {
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
VISUAL_PHRASES = {
    "screenshot evidence",
    "ui layout",
    "user interface layout",
}

# Boilerplate that every F.5 worker assignment carries. These generic guardrail
# lines mention "visual evidence" / "secrets/env" but are NOT task-specific
# signals, so they are excluded from keyword scanning to avoid flagging every
# assignment as a visual task. Mirrors the H.1 driver-routing exclusion list.
_BOILERPLATE_MARKERS = (
    "visual evidence is required",
    "secrets/env",
    "do not apply patches",
    "do not call models",
)

_EXECUTION_BOUNDARY = [
    "No OCR was performed.",
    "No vision model was called.",
    "No model was called.",
    "No worker was launched.",
    "No patch was applied.",
    "No validation was run.",
    "No promotion occurred.",
]


# ==========================================================================
# Pure policy
# ==========================================================================


def evaluate_visual_evidence_policy(
    source: dict[str, Any],
    *,
    visual_paths: list[str] | None = None,
    human_summary: str = "",
    visual_readable_by_model: bool = False,
    validation_covers_visual: bool = False,
) -> dict[str, Any]:
    """Evaluate a source artifact and return the visual-evidence policy.

    Pure function: no IO, no side effects. The four operator inputs are taken at
    face value — A.16 never infers ``visual_evidence_readable_by_model`` from
    file presence and never inspects image bytes.
    """
    scan_text = _scan_text(source)
    referenced = _is_visual_referenced(source, scan_text)

    paths = _dedupe([*(visual_paths or []), *_source_visual_paths(source)])
    summary = _text(human_summary)

    has_path = bool(paths)
    has_summary = bool(summary)
    readable = bool(visual_readable_by_model)
    covers = bool(validation_covers_visual)

    risk_flags: list[str] = []
    missing: list[str] = []
    reasons: list[str] = []

    summary_required = False
    verification_required = False
    claim_allowed = True

    if referenced:
        _add(risk_flags, SOURCE_MENTIONS_VISUAL_ISSUE)
        reasons.append(
            "Source references a visual/UI/design issue (screenshot, image, UI, "
            "layout, OCR, chart, poster, or design)."
        )

        # Rule 2 — visual evidence present / paths missing.
        if not has_path and not has_summary:
            _add(risk_flags, VISUAL_PATHS_MISSING)
            _add(missing, VISUAL_EVIDENCE_PATH_OR_CAPTION)
            reasons.append(
                "No visual evidence path and no human caption summary were provided "
                "for a visual issue."
            )

        # Rule 3/4 — model readability + human summary.
        if not readable:
            _add(risk_flags, VISION_MODEL_UNAVAILABLE)
        if not readable and not has_summary:
            summary_required = True
            _add(risk_flags, HUMAN_VISUAL_SUMMARY_MISSING)
            _add(missing, HUMAN_VISUAL_SUMMARY_OR_VISION_MODEL)
            reasons.append(
                "No model is declared able to read the visual evidence and no human "
                "summary was provided; a human caption summary or a vision-capable "
                "model is required."
            )

        # Rule 5 — validation coverage.
        if not covers:
            _add(risk_flags, VALIDATION_DOES_NOT_COVER_VISUAL_ISSUE)
            _add(missing, EXPLICIT_VISUAL_VALIDATION_COVERAGE)
            reasons.append(
                "Validation does not explicitly cover the visual issue; passing "
                "text/code tests does not prove the visual/UI/design issue is fixed."
            )

        # Rule 6 — resolution claim. The "readable vision model OR human summary"
        # requirement plus explicit validation coverage must both be satisfied.
        verification_satisfied = (readable or has_summary) and covers
        if not verification_satisfied:
            verification_required = True
            claim_allowed = False
            _add(risk_flags, VISUAL_EVIDENCE_UNVERIFIED)
            _add(risk_flags, RESOLUTION_CLAIM_NOT_ALLOWED)
            _add(missing, VISUAL_VERIFICATION_STEP)
            reasons.append(
                "A visual verification step (a vision model or human summary, plus "
                "explicit visual validation coverage) is required before claiming "
                "the visual issue is resolved."
            )
        else:
            reasons.append(
                "Visual evidence is backed by a human summary or a vision-capable "
                "model and validation covers the visual issue; a resolution claim "
                "is allowed."
            )
    else:
        reasons.append(
            "Source does not reference a visual/UI/design issue; no visual "
            "verification is required and a resolution claim is allowed."
        )

    return {
        "visual_evidence_present": has_path,
        "visual_evidence_referenced": referenced,
        "visual_evidence_paths": paths,
        "visual_evidence_readable_by_model": readable,
        "human_visual_summary": summary,
        "human_visual_summary_required": summary_required,
        "validation_covers_visual_issue": covers,
        "visual_verification_required": verification_required,
        "resolution_claim_allowed": claim_allowed,
        "risk_flags": _dedupe(risk_flags),
        "missing_requirements": _dedupe(missing),
        "reasons": _dedupe(reasons),
    }


# ==========================================================================
# Contract record + IO
# ==========================================================================


def create_visual_evidence_contract(
    *,
    source_path: str | None = None,
    source: dict[str, Any] | None = None,
    repo_path: str | None = None,
    visual_paths: list[str] | None = None,
    human_summary: str | None = None,
    visual_readable_by_model: bool = False,
    validation_covers_visual: bool = False,
    dry_run: bool = False,
    output_root: str | None = None,
    created_at: str | None = None,
    visual_evidence_id: str | None = None,
) -> dict[str, Any]:
    """Build a visual-evidence contract and (optionally) write inert artifacts."""
    source_path_str = ""
    record_source: dict[str, Any]

    if source is not None:
        if not isinstance(source, dict):
            return _error_result("invalid_source", "source must be a dict", status="invalid")
        record_source = source
        source_path_str = _text(source.get("source_path"))
    elif _text(source_path):
        sp = Path(_text(source_path)).expanduser()
        if not sp.is_file():
            return _error_result(
                "source_not_found",
                f"source not found: {sp}",
                status="not_found",
            )
        try:
            parsed = json.loads(sp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            return _error_result(
                "source_invalid",
                f"source is invalid: {exc}",
                status="invalid",
            )
        if not isinstance(parsed, dict):
            return _error_result(
                "source_invalid",
                "source JSON must contain an object",
                status="invalid",
            )
        record_source = parsed
        source_path_str = str(sp.resolve())
    else:
        return _error_result(
            "invalid_source",
            "a source path or source dict is required",
        )

    repo_root = Path(
        _text(repo_path) or _text(record_source.get("repo_path")) or "."
    ).expanduser().resolve()

    created = _text(created_at) or _utc_now_iso()
    policy = evaluate_visual_evidence_policy(
        record_source,
        visual_paths=list(visual_paths or []),
        human_summary=_text(human_summary),
        visual_readable_by_model=bool(visual_readable_by_model),
        validation_covers_visual=bool(validation_covers_visual),
    )
    record = _build_record(
        policy=policy,
        source=record_source,
        source_path=source_path_str,
        created_at=created,
        visual_evidence_id=visual_evidence_id,
    )
    markdown = render_visual_evidence_markdown(record)

    try:
        paths = _contract_paths(repo_root, record["visual_evidence_id"], output_root=output_root)
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
                "code": "visual_evidence_contract_already_exists",
                "message": "visual evidence contract already exists; no files were overwritten",
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
        "status": "contract_created",
        "dry_run": False,
        "json_path": str(paths["json"]),
        "md_path": str(paths["md"]),
        "record": record,
        "markdown": markdown,
    }


def _build_record(
    *,
    policy: dict[str, Any],
    source: dict[str, Any],
    source_path: str,
    created_at: str,
    visual_evidence_id: str | None,
) -> dict[str, Any]:
    title = _text(source.get("title")) or "Visual Evidence Contract"
    final_id = _safe_segment(
        visual_evidence_id or f"{_timestamp_segment(created_at)}-{title}",
        "visual-evidence",
    )
    return {
        "visual_evidence_id": final_id,
        "created_at": created_at,
        "source_type": _detect_source_type(source),
        "source_path": source_path,
        "title": title,
        "visual_evidence_present": policy["visual_evidence_present"],
        "visual_evidence_referenced": policy["visual_evidence_referenced"],
        "visual_evidence_paths": list(policy["visual_evidence_paths"]),
        "visual_evidence_readable_by_model": policy["visual_evidence_readable_by_model"],
        "human_visual_summary": policy["human_visual_summary"],
        "human_visual_summary_required": policy["human_visual_summary_required"],
        "validation_covers_visual_issue": policy["validation_covers_visual_issue"],
        "visual_verification_required": policy["visual_verification_required"],
        "resolution_claim_allowed": policy["resolution_claim_allowed"],
        "risk_flags": list(policy["risk_flags"]),
        "missing_requirements": list(policy["missing_requirements"]),
        "reasons": list(policy["reasons"]),
        # Inert flags — A.16 performs none of these.
        "model_call_performed": False,
        "ocr_performed": False,
        "vision_model_called": False,
        "worker_launch_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "promotion_performed": False,
    }


# ==========================================================================
# Rendering
# ==========================================================================


def render_visual_evidence_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_visual_evidence_text(result: dict[str, Any]) -> str:
    lines = [
        "Visual Evidence Contract",
        f"Status: {_text(result.get('status'))}",
    ]
    record = result.get("record") if isinstance(result.get("record"), dict) else {}
    if record:
        lines.extend(
            [
                f"Visual evidence id: {_text(record.get('visual_evidence_id'))}",
                f"Visual issue referenced: {record.get('visual_evidence_referenced')}",
                f"Visual verification required: {record.get('visual_verification_required')}",
                f"Resolution claim allowed: {record.get('resolution_claim_allowed')}",
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


def render_visual_evidence_markdown(record: dict[str, Any]) -> str:
    summary = _text(record.get("human_visual_summary"))
    return (
        "# Visual Evidence Contract\n\n"
        f"Visual evidence id: `{_text(record.get('visual_evidence_id'))}`\n\n"
        f"Created at: `{_text(record.get('created_at'))}`\n\n"
        "## Source\n\n"
        f"- Source type: `{_text(record.get('source_type'))}`\n"
        f"- Source path: `{_text(record.get('source_path'))}`\n"
        f"- Title: {_text(record.get('title')) or 'Untitled source'}\n\n"
        "## Visual Evidence Status\n\n"
        f"- Visual issue referenced: `{_bool(record.get('visual_evidence_referenced'))}`\n"
        f"- Visual evidence present: `{_bool(record.get('visual_evidence_present'))}`\n"
        f"- Visual evidence readable by model: `{_bool(record.get('visual_evidence_readable_by_model'))}`\n"
        "- Visual evidence paths:\n"
        f"{_bullet_list(_strings(record.get('visual_evidence_paths')), indent='  ')}\n\n"
        "## Human Summary\n\n"
        f"- Human visual summary required: `{_bool(record.get('human_visual_summary_required'))}`\n"
        f"- Human visual summary: {summary or '(none provided)'}\n\n"
        "## Validation Coverage\n\n"
        f"- Validation covers visual issue: `{_bool(record.get('validation_covers_visual_issue'))}`\n\n"
        "## Resolution Claim Status\n\n"
        f"- Visual verification required: `{_bool(record.get('visual_verification_required'))}`\n"
        f"- Resolution claim allowed: `{_bool(record.get('resolution_claim_allowed'))}`\n\n"
        "## Risk Flags\n\n"
        f"{_bullet_list(_strings(record.get('risk_flags')))}\n\n"
        "## Missing Requirements\n\n"
        f"{_bullet_list(_strings(record.get('missing_requirements')))}\n\n"
        "## Reasons\n\n"
        f"{_bullet_list(_strings(record.get('reasons')))}\n\n"
        "## Execution Boundary\n\n"
        "This is a contract/report-only artifact. A.16 inspects metadata only — it "
        "never reads image bytes.\n\n"
        f"{_bullet_list(list(_EXECUTION_BOUNDARY))}\n"
    )


# ==========================================================================
# Helpers
# ==========================================================================


def _detect_source_type(source: dict[str, Any]) -> str:
    if "recommended_vehicle" in source or "driver_decision_id" in source:
        return "driver_decision"
    return "worker_assignment"


def _scan_text(source: dict[str, Any]) -> str:
    parts = [
        _text(source.get("title")),
        _text(source.get("expected_output")),
        _text(source.get("worker_role")),
        _text(source.get("source_context")),
    ]
    for key in ("stop_conditions", "safety_rules", "reasons"):
        for line in _string_list(source.get(key)):
            if _is_boilerplate(line):
                continue
            parts.append(line)
    return " \n ".join(part for part in parts if part).lower()


def _is_visual_referenced(source: dict[str, Any], scan_text: str) -> bool:
    if _mentions(scan_text, VISUAL_TOKENS, VISUAL_PHRASES):
        return True
    # Driver Decision (H.1) direct signals: a routed visual vehicle or the
    # visual risk flag already mark the task as visual.
    if _text(source.get("recommended_vehicle")).lower() == VISION_OR_HUMAN_CAPTION_REQUIRED:
        return True
    if VISUAL_EVIDENCE_UNVERIFIED in _string_list(source.get("risk_flags")):
        return True
    return False


def _source_visual_paths(source: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("visual_evidence_paths", "visual_paths"):
        out.extend(_string_list(source.get(key)))
    return out


def _is_boilerplate(line: str) -> bool:
    lowered = _text(line).lower()
    return any(marker in lowered for marker in _BOILERPLATE_MARKERS)


def _mentions(text: str, tokens: set[str], phrases: set[str]) -> bool:
    if any(phrase in text for phrase in phrases):
        return True
    words = set(re.findall(r"[a-z0-9]+", text))
    return not words.isdisjoint(tokens)


def _contract_paths(repo_root: Path, contract_id: str, *, output_root: str | None) -> dict[str, Path]:
    root = _output_root(repo_root, output_root)
    directory = root / _safe_segment(contract_id, "visual-evidence")
    return {
        "dir": directory,
        "json": directory / "visual_evidence_contract.json",
        "md": directory / "visual_evidence_contract.md",
    }


def _output_root(repo_root: Path, output_root: str | None) -> Path:
    base = (repo_root / ".agent" / DEFAULT_VISUAL_EVIDENCE_DIRNAME).resolve()
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
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "dry_run": False,
        "json_path": "",
        "md_path": "",
        "error": {"code": code, "message": message},
    }


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = re.split(r"[,\n]", value)
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    return [text for text in (_text(item) for item in items) if text]


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _bullet_list(items: list[str], *, indent: str = "") -> str:
    if not items:
        return f"{indent}- None"
    return "\n".join(f"{indent}- {item}" for item in items)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _add(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


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
    return _safe_segment(created_at.replace(":", "-"), "contract")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
