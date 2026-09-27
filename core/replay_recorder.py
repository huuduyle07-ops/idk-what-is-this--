from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MANIFEST_NAME = "replay_manifest.json"

TEXT_ARTIFACT_NAMES = {
    "user_query.txt",
    "model_prompt.txt",
    "model_raw_response.txt",
    "validation_output.txt",
}

JSON_ARTIFACT_NAMES = {
    "active_lessons_injected.json",
    "apply_result.json",
    "brain_stamp.json",
    "control_result.json",
    "final_status.json",
    "patch_parsed.json",
    "patch_plan.json",
    # EXEC.APPROVAL.LIVE.1 persists the typed human authorization before the
    # executor is entered. Older bundles simply do not carry this additive file.
    "human_apply_authorization.json",
    # CHECK.LIVE.1 attaches its shadow post-run reconciliation receipt to the
    # bundle the run already produces.  The addition is additive and
    # migration-safe: a bundle written before this phase simply does not carry
    # the file, and `files_present` is derived from disk.
    "post_run_reconciliation_shadow.json",
    # WORKER.DECL.2A records how the strict one-object patch envelope and the
    # legacy extractor each read the worker response behind this run.  Same
    # additive, migration-safe shape: bounded identity metadata only, and an
    # older bundle simply does not carry the file.
    "worker_patch_envelope.json",
    # WORKER.DECL.2A.1 records which output-transport strategy was asked of the
    # model call behind this run, beside the strict/legacy statuses above.
    # Additive and migration-safe in the same way: a bundle written before the
    # phase, or with the experiment off, simply does not carry the file.
    "strict_envelope_emission.json",
    # WORKER.DECL.2B freezes bounded pre-execution intent identity/status
    # telemetry.  It contains no response body, prompt, snippet or file body.
    "pre_execution_change_intent.json",
    "scout_snippets.json",
    "self_correct_attempts.json",
}

COMPAT_ARTIFACT_NAMES = {
    "events.jsonl",
}

ARTIFACT_NAMES = (
    TEXT_ARTIFACT_NAMES
    | JSON_ARTIFACT_NAMES
    | COMPAT_ARTIFACT_NAMES
    | {MANIFEST_NAME}
)


@dataclass(frozen=True)
class ReplayBundle:
    repo_path: Path
    replay_id: str
    replay_dir: Path
    run_kind: str
    created_at: str


def create_replay_bundle(
    repo_path: str | Path,
    *,
    run_kind: str,
    user_query: str | None = None,
    now: datetime | None = None,
) -> ReplayBundle:
    """Create a replay bundle under ``repo_path/.agent/replays``."""
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo_path}")
    created = _coerce_utc(now)
    replay_id = _new_replay_id(created)
    root = repo / ".agent" / "replays"
    root.mkdir(parents=True, exist_ok=True)

    replay_dir = root / replay_id
    suffix = 1
    while replay_dir.exists():
        replay_id = f"{_new_replay_id(created)}-{suffix}"
        replay_dir = root / replay_id
        suffix += 1
    replay_dir.mkdir(parents=True, exist_ok=False)

    bundle = ReplayBundle(
        repo_path=repo,
        replay_id=replay_id,
        replay_dir=replay_dir,
        run_kind=str(run_kind or "unknown"),
        created_at=created.isoformat(),
    )
    _write_manifest(bundle, final_status=None, brain_stamp=None)
    if user_query is not None:
        write_replay_artifact(bundle, "user_query.txt", user_query)
    return bundle


def write_replay_artifact(
    bundle: ReplayBundle,
    name: str,
    content: str | bytes | Any,
) -> Path:
    """Write a text artifact into a bundle and refresh its manifest."""
    if name not in TEXT_ARTIFACT_NAMES and name not in COMPAT_ARTIFACT_NAMES:
        raise ValueError(f"unsupported replay text artifact: {name!r}")
    path = _artifact_path(bundle, name)
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    elif isinstance(content, str):
        text = content
    else:
        text = str(content)
    _atomic_write_text(path, text)
    _refresh_manifest_from_disk(bundle)
    return path


def write_replay_json(bundle: ReplayBundle, name: str, obj: Any) -> Path:
    """Write a JSON artifact into a bundle and refresh its manifest."""
    if name not in JSON_ARTIFACT_NAMES:
        raise ValueError(f"unsupported replay JSON artifact: {name!r}")
    path = _artifact_path(bundle, name)
    _atomic_write_text(
        path,
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str),
    )
    _refresh_manifest_from_disk(bundle)
    return path


def finalize_replay_bundle(
    bundle: ReplayBundle,
    final_status: dict[str, Any] | str,
) -> dict[str, Any]:
    """Persist final status and return the updated replay manifest."""
    status_obj: dict[str, Any]
    if isinstance(final_status, dict):
        status_obj = dict(final_status)
    else:
        status_obj = {"status": str(final_status)}
    status_obj.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
    write_replay_json(bundle, "final_status.json", status_obj)
    return _write_manifest(
        bundle,
        final_status=status_obj,
        brain_stamp=_read_json_if_present(bundle, "brain_stamp.json"),
    )


def list_replay_bundles(
    repo_path: str | Path,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return newest-first replay manifests for ``repo_path``."""
    if limit <= 0:
        return []
    root = Path(repo_path).resolve() / ".agent" / "replays"
    if not root.is_dir():
        return []

    manifests: list[dict[str, Any]] = []
    for replay_dir in root.iterdir():
        if not replay_dir.is_dir():
            continue
        manifest_path = replay_dir / MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(manifest, dict):
            manifests.append(manifest)

    manifests.sort(
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("replay_id") or ""),
        ),
        reverse=True,
    )
    return manifests[:limit]


def read_replay_manifest(
    repo_path: str | Path,
    replay_id: str,
) -> dict[str, Any] | None:
    """Read one replay manifest by id, or return ``None`` when absent."""
    safe_id = _validate_replay_id(replay_id)
    root = Path(repo_path).resolve() / ".agent" / "replays"
    manifest_path = (root / safe_id / MANIFEST_NAME).resolve()
    try:
        manifest_path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"replay id escapes replays dir: {replay_id!r}") from exc
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return manifest if isinstance(manifest, dict) else None


def _coerce_utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _new_replay_id(created: datetime) -> str:
    timestamp = created.strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return f"{timestamp}_{short_id}"


def _validate_replay_id(replay_id: str) -> str:
    if not replay_id or replay_id != Path(replay_id).name:
        raise ValueError(f"invalid replay id: {replay_id!r}")
    if "/" in replay_id or "\\" in replay_id:
        raise ValueError(f"invalid replay id: {replay_id!r}")
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in replay_id):
        raise ValueError(f"invalid replay id: {replay_id!r}")
    return replay_id


def _artifact_path(bundle: ReplayBundle, name: str) -> Path:
    if name not in ARTIFACT_NAMES:
        raise ValueError(f"unsupported replay artifact name: {name!r}")
    if not name or name != Path(name).name or "/" in name or "\\" in name:
        raise ValueError(f"invalid replay artifact name: {name!r}")
    path = (bundle.replay_dir / name).resolve()
    replay_dir = bundle.replay_dir.resolve()
    try:
        path.relative_to(replay_dir)
    except ValueError as exc:
        raise ValueError(f"replay artifact path escapes replay dir: {name!r}") from exc
    return path


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_name, path)


def _files_present(bundle: ReplayBundle) -> list[str]:
    if not bundle.replay_dir.is_dir():
        return []
    files = [
        path.name
        for path in bundle.replay_dir.iterdir()
        if path.is_file() and not path.name.endswith(".tmp")
    ]
    if MANIFEST_NAME not in files:
        files.append(MANIFEST_NAME)
    return sorted(files)


def _read_json_if_present(bundle: ReplayBundle, name: str) -> dict[str, Any] | None:
    path = _artifact_path(bundle, name)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _brain_stamp_fields(
    brain_stamp: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    if not isinstance(brain_stamp, dict):
        return None, None
    stamp_id = brain_stamp.get("brain_stamp_id") or brain_stamp.get("id")
    stamp_hash = brain_stamp.get("brain_stamp_hash") or brain_stamp.get("hash")
    return (
        str(stamp_id) if stamp_id else None,
        str(stamp_hash) if stamp_hash else None,
    )


def _status_value(final_status: dict[str, Any] | None) -> Any:
    if not isinstance(final_status, dict):
        return None
    return final_status.get("status", final_status)


def _write_manifest(
    bundle: ReplayBundle,
    *,
    final_status: dict[str, Any] | None,
    brain_stamp: dict[str, Any] | None,
) -> dict[str, Any]:
    stamp_id, stamp_hash = _brain_stamp_fields(brain_stamp)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "replay_id": bundle.replay_id,
        "created_at": bundle.created_at,
        "run_kind": bundle.run_kind,
        "repo_path": str(bundle.repo_path),
        "files_present": _files_present(bundle),
        "brain_stamp_id": stamp_id,
        "brain_stamp_hash": stamp_hash,
        "final_status": _status_value(final_status),
        "pinned": False,
    }
    _atomic_write_text(
        _artifact_path(bundle, MANIFEST_NAME),
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
    )
    return manifest


def _refresh_manifest_from_disk(bundle: ReplayBundle) -> dict[str, Any]:
    final_status = _read_json_if_present(bundle, "final_status.json")
    brain_stamp = _read_json_if_present(bundle, "brain_stamp.json")
    return _write_manifest(
        bundle,
        final_status=final_status,
        brain_stamp=brain_stamp,
    )
