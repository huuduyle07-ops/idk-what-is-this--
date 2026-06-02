from __future__ import annotations

import difflib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.replay_recorder import JSON_ARTIFACT_NAMES, MANIFEST_NAME, read_replay_manifest


COMPARE_ARTIFACT_NAMES = (
    "model_prompt.txt",
    "control_result.json",
    "active_lessons_injected.json",
    "scout_snippets.json",
    "patch_parsed.json",
    "brain_stamp.json",
    "final_status.json",
)
DEFAULT_MAX_CHARS = 20000
DEFAULT_MAX_DIFF_LINES = 200
GUARDRAIL_NOTE = (
    "Replay compare is read-only and does not rerun the model, patcher, "
    "validation, benchmark, Dream, or janitor."
)

CURRENT_ARTIFACT_PATHS = {
    "model_prompt.txt": Path(".agent") / "debug_last_control_prompt.txt",
}


@dataclass(frozen=True)
class ArtifactDiffSummary:
    artifact_name: str
    status: str
    old_size: int
    current_size: int
    line_additions: int
    line_deletions: int
    diff: str
    diff_truncated: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReplayCompareResult:
    replay_id: str
    created_at: str | None
    run_kind: str | None
    compared_at: str
    artifacts_compared: list[str]
    artifacts_missing_old: list[str]
    artifacts_missing_current: list[str]
    changed_count: int
    unchanged_count: int
    artifact_summaries: list[ArtifactDiffSummary]
    guardrail_note: str = GUARDRAIL_NOTE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifact_summaries"] = [
            summary.to_dict() for summary in self.artifact_summaries
        ]
        return data


def compare_replay_to_current(
    repo_path: str | Path,
    replay_id: str,
    *,
    current_artifacts: dict[str, Any] | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> ReplayCompareResult:
    """Compare stored replay artifacts to already available current artifacts."""
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo_path}")
    safe_id = _validate_replay_id(replay_id)
    max_chars = max(1, int(max_chars or DEFAULT_MAX_CHARS))

    manifest = read_replay_manifest(repo, safe_id)
    if manifest is None:
        raise FileNotFoundError(f"replay not found: {safe_id}")

    replay_dir = _replay_dir(repo, safe_id)
    current = _load_current_artifacts(
        repo,
        current_artifacts=current_artifacts,
        max_chars=max_chars,
    )

    summaries: list[ArtifactDiffSummary] = []
    artifacts_compared: list[str] = []
    artifacts_missing_old: list[str] = []
    artifacts_missing_current: list[str] = []
    changed_count = 0
    unchanged_count = 0

    for artifact_name in COMPARE_ARTIFACT_NAMES:
        old = _read_replay_artifact(
            replay_dir,
            artifact_name,
            max_chars=max_chars,
        )
        new = current.get(artifact_name, _ArtifactReadResult.missing())

        if not old.present:
            artifacts_missing_old.append(artifact_name)
            summaries.append(
                ArtifactDiffSummary(
                    artifact_name=artifact_name,
                    status="old_missing",
                    old_size=0,
                    current_size=new.size,
                    line_additions=0,
                    line_deletions=0,
                    diff="",
                    note="Stored replay artifact was not captured.",
                )
            )
            continue

        if not new.present:
            artifacts_missing_current.append(artifact_name)
            summaries.append(
                ArtifactDiffSummary(
                    artifact_name=artifact_name,
                    status="current_missing",
                    old_size=old.size,
                    current_size=0,
                    line_additions=0,
                    line_deletions=0,
                    diff="",
                    note="Current artifact is not available without rerunning.",
                )
            )
            continue

        if old.skipped_large or new.skipped_large:
            summaries.append(
                ArtifactDiffSummary(
                    artifact_name=artifact_name,
                    status="skipped_large",
                    old_size=old.size,
                    current_size=new.size,
                    line_additions=0,
                    line_deletions=0,
                    diff="",
                    note=f"Artifact skipped because it exceeds {max_chars} characters.",
                )
            )
            continue

        artifacts_compared.append(artifact_name)
        summary = compare_artifact_text(
            old.text,
            new.text,
            max_lines=DEFAULT_MAX_DIFF_LINES,
        )
        summary = ArtifactDiffSummary(
            artifact_name=artifact_name,
            status=summary.status,
            old_size=old.size,
            current_size=new.size,
            line_additions=summary.line_additions,
            line_deletions=summary.line_deletions,
            diff=summary.diff,
            diff_truncated=summary.diff_truncated,
            note=summary.note,
        )
        summaries.append(summary)
        if summary.status == "changed":
            changed_count += 1
        elif summary.status == "unchanged":
            unchanged_count += 1

    return ReplayCompareResult(
        replay_id=safe_id,
        created_at=_string_or_none(manifest.get("created_at")),
        run_kind=_string_or_none(manifest.get("run_kind")),
        compared_at=datetime.now(timezone.utc).isoformat(),
        artifacts_compared=artifacts_compared,
        artifacts_missing_old=artifacts_missing_old,
        artifacts_missing_current=artifacts_missing_current,
        changed_count=changed_count,
        unchanged_count=unchanged_count,
        artifact_summaries=summaries,
    )


def compare_artifact_text(
    old_text: str,
    new_text: str,
    *,
    max_lines: int = DEFAULT_MAX_DIFF_LINES,
) -> ArtifactDiffSummary:
    """Return a bounded unified diff summary for two text blobs."""
    old_text = str(old_text)
    new_text = str(new_text)
    if old_text == new_text:
        return ArtifactDiffSummary(
            artifact_name="artifact",
            status="unchanged",
            old_size=len(old_text),
            current_size=len(new_text),
            line_additions=0,
            line_deletions=0,
            diff="",
        )

    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="replay",
            tofile="current",
            lineterm="",
        )
    )
    additions = sum(
        1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
    )
    deletions = sum(
        1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
    )
    max_lines = max(1, int(max_lines or DEFAULT_MAX_DIFF_LINES))
    truncated = len(diff_lines) > max_lines
    visible_lines = diff_lines[:max_lines]
    if truncated:
        visible_lines.append(f"... diff truncated at {max_lines} lines ...")

    return ArtifactDiffSummary(
        artifact_name="artifact",
        status="changed",
        old_size=len(old_text),
        current_size=len(new_text),
        line_additions=additions,
        line_deletions=deletions,
        diff="\n".join(visible_lines),
        diff_truncated=truncated,
    )


def format_replay_compare_markdown(result: ReplayCompareResult) -> str:
    """Format a compare result as read-only markdown."""
    lines = [
        f"# Replay Compare: {result.replay_id}",
        "",
        f"- Created: {result.created_at or 'unknown'}",
        f"- Run kind: {result.run_kind or 'unknown'}",
        f"- Compared: {result.compared_at}",
        f"- Changed: {result.changed_count}",
        f"- Unchanged: {result.unchanged_count}",
        f"- Missing old: {len(result.artifacts_missing_old)}",
        f"- Missing current: {len(result.artifacts_missing_current)}",
        "",
        f"> {result.guardrail_note}",
        "",
        "## Artifacts",
    ]
    for summary in result.artifact_summaries:
        lines.extend(
            [
                "",
                f"### {summary.artifact_name}: {summary.status}",
                "",
                (
                    f"- Old size: {summary.old_size}; current size: "
                    f"{summary.current_size}"
                ),
                (
                    f"- Additions: {summary.line_additions}; deletions: "
                    f"{summary.line_deletions}"
                ),
            ]
        )
        if summary.note:
            lines.append(f"- Note: {summary.note}")
        if summary.diff:
            lines.extend(["", "```diff", summary.diff, "```"])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class _ArtifactReadResult:
    present: bool
    text: str
    size: int
    skipped_large: bool = False

    @classmethod
    def missing(cls) -> "_ArtifactReadResult":
        return cls(present=False, text="", size=0)


def _load_current_artifacts(
    repo: Path,
    *,
    current_artifacts: dict[str, Any] | None,
    max_chars: int,
) -> dict[str, _ArtifactReadResult]:
    if current_artifacts is not None:
        return {
            name: _coerce_current_artifact(name, value, max_chars=max_chars)
            for name, value in current_artifacts.items()
            if name in COMPARE_ARTIFACT_NAMES
        }

    loaded: dict[str, _ArtifactReadResult] = {}
    for artifact_name, relative_path in CURRENT_ARTIFACT_PATHS.items():
        path = (repo / relative_path).resolve()
        try:
            path.relative_to(repo)
        except ValueError:
            loaded[artifact_name] = _ArtifactReadResult.missing()
            continue
        loaded[artifact_name] = _read_path_artifact(
            path,
            artifact_name,
            max_chars=max_chars,
        )
    return loaded


def _coerce_current_artifact(
    artifact_name: str,
    value: Any,
    *,
    max_chars: int,
) -> _ArtifactReadResult:
    if value is None:
        return _ArtifactReadResult.missing()
    text = _normalize_artifact_text(artifact_name, value)
    if len(text) > max_chars:
        return _ArtifactReadResult(
            present=True,
            text="",
            size=len(text),
            skipped_large=True,
        )
    return _ArtifactReadResult(present=True, text=text, size=len(text))


def _read_replay_artifact(
    replay_dir: Path,
    artifact_name: str,
    *,
    max_chars: int,
) -> _ArtifactReadResult:
    if artifact_name not in COMPARE_ARTIFACT_NAMES:
        raise ValueError(f"unsupported compare artifact: {artifact_name!r}")
    path = (replay_dir / artifact_name).resolve()
    try:
        path.relative_to(replay_dir)
    except ValueError as exc:
        raise ValueError(f"replay artifact escapes bundle: {artifact_name!r}") from exc
    return _read_path_artifact(path, artifact_name, max_chars=max_chars)


def _read_path_artifact(
    path: Path,
    artifact_name: str,
    *,
    max_chars: int,
) -> _ArtifactReadResult:
    if not path.is_file():
        return _ArtifactReadResult.missing()
    size = path.stat().st_size
    if size > max_chars:
        return _ArtifactReadResult(
            present=True,
            text="",
            size=size,
            skipped_large=True,
        )
    text = path.read_text(encoding="utf-8", errors="replace")
    normalized = _normalize_artifact_text(artifact_name, text)
    if len(normalized) > max_chars:
        return _ArtifactReadResult(
            present=True,
            text="",
            size=len(normalized),
            skipped_large=True,
        )
    return _ArtifactReadResult(present=True, text=normalized, size=size)


def _normalize_artifact_text(artifact_name: str, value: Any) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    elif isinstance(value, str):
        text = value
    else:
        text = json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )

    if artifact_name in JSON_ARTIFACT_NAMES:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        return json.dumps(
            parsed,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
    return text


def _replay_dir(repo: Path, replay_id: str) -> Path:
    root = (repo / ".agent" / "replays").resolve()
    replay_dir = (root / replay_id / MANIFEST_NAME).resolve().parent
    try:
        replay_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"replay id escapes replays dir: {replay_id!r}") from exc
    return replay_dir


def _validate_replay_id(replay_id: str) -> str:
    if not replay_id or replay_id != Path(replay_id).name:
        raise ValueError(f"invalid replay id: {replay_id!r}")
    if "/" in replay_id or "\\" in replay_id:
        raise ValueError(f"invalid replay id: {replay_id!r}")
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in replay_id):
        raise ValueError(f"invalid replay id: {replay_id!r}")
    return replay_id


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
