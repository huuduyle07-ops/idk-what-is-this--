from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANAGED_UPLOAD_TEMP_PREFIX = "cattus-upload-"
METADATA_FILENAME = ".agent/upload_temp_repo.meta"
DEFAULT_CLEANUP_POLICY = "failed_upload_cleanup_ttl_eligible"


@dataclass(frozen=True)
class ManagedUploadTempRepo:
    temp_root: Path
    repo_path: Path
    metadata: dict[str, Any]

    def to_response(self) -> dict[str, Any]:
        return {
            "managed": True,
            "status": self.metadata.get("status", "active"),
            "repo_path": str(self.repo_path),
            "temp_root": str(self.temp_root),
            "cleanup_policy": self.metadata.get("cleanup_policy", DEFAULT_CLEANUP_POLICY),
            "metadata_path": str(self.repo_path / METADATA_FILENAME),
        }


def create_managed_upload_temp_repo(
    top_folder: str,
    *,
    source_route: str = "/upload_folder",
    temp_base: str | Path | None = None,
) -> ManagedUploadTempRepo:
    base = _temp_base(temp_base)
    temp_root = Path(tempfile.mkdtemp(prefix=MANAGED_UPLOAD_TEMP_PREFIX, dir=str(base)))
    repo_path = temp_root / _safe_top_folder(top_folder)
    repo_path.mkdir(parents=True, exist_ok=True)
    metadata = write_upload_temp_repo_metadata(
        repo_path,
        temp_root=temp_root,
        source_route=source_route,
        status="active",
    )
    return ManagedUploadTempRepo(temp_root=temp_root, repo_path=repo_path, metadata=metadata)


def write_upload_temp_repo_metadata(
    repo_path: str | Path,
    *,
    temp_root: str | Path | None = None,
    source_route: str = "/upload_folder",
    status: str = "active",
    cleanup_policy: str = DEFAULT_CLEANUP_POLICY,
) -> dict[str, Any]:
    repo = Path(repo_path).resolve()
    root = Path(temp_root).resolve() if temp_root is not None else repo.parent.resolve()
    metadata_path = repo / METADATA_FILENAME
    now = _now()
    existing: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
            existing = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            existing = {}
    metadata = {
        "schema_version": 1,
        "managed_by": "C.A.T.T.U.S",
        "created_at": existing.get("created_at") or now,
        "last_accessed_at": now,
        "source_route": source_route,
        "repo_path": str(repo),
        "temp_root": str(root),
        "cleanup_policy": cleanup_policy,
        "status": status,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return metadata


def mark_upload_temp_repo_status(
    repo_path: str | Path,
    status: str,
    *,
    temp_root: str | Path | None = None,
) -> dict[str, Any]:
    return write_upload_temp_repo_metadata(
        repo_path,
        temp_root=temp_root,
        status=status,
    )


def upload_temp_repo_response(
    repo_path: str | Path,
    *,
    temp_root: str | Path | None = None,
    status: str = "active",
    cleanup_policy: str = DEFAULT_CLEANUP_POLICY,
) -> dict[str, Any]:
    repo = Path(repo_path).resolve()
    root = Path(temp_root).resolve() if temp_root is not None else repo.parent.resolve()
    return {
        "managed": _is_managed_root(root, _temp_base(None)),
        "status": status,
        "repo_path": str(repo),
        "temp_root": str(root),
        "cleanup_policy": cleanup_policy,
        "metadata_path": str(repo / METADATA_FILENAME),
    }


def cleanup_managed_upload_temp_repo(
    path: str | Path,
    *,
    temp_base: str | Path | None = None,
) -> dict[str, Any]:
    base = _temp_base(temp_base)
    target = Path(path).resolve(strict=False)
    managed_root = _managed_root_for(target)

    if managed_root is None:
        return _cleanup_result(
            ok=False,
            action="refused",
            target=target,
            managed=False,
            reason="path is not inside a managed C.A.T.T.U.S upload temp root",
        )

    if not _is_under(managed_root, base):
        return _cleanup_result(
            ok=False,
            action="refused",
            target=target,
            managed=True,
            managed_root=managed_root,
            reason="managed upload temp root is outside the expected temp base",
        )

    refusal = _dangerous_path_reason(target, managed_root, base)
    if refusal:
        return _cleanup_result(
            ok=False,
            action="refused",
            target=target,
            managed=True,
            managed_root=managed_root,
            reason=refusal,
        )

    if not managed_root.exists():
        return _cleanup_result(
            ok=True,
            action="missing",
            target=target,
            managed=True,
            managed_root=managed_root,
            reason="managed upload temp root is already missing",
        )

    if not managed_root.is_dir():
        return _cleanup_result(
            ok=False,
            action="refused",
            target=target,
            managed=True,
            managed_root=managed_root,
            reason="managed upload temp root is not a directory",
        )

    try:
        shutil.rmtree(managed_root)
    except OSError as exc:
        return _cleanup_result(
            ok=False,
            action="error",
            target=target,
            managed=True,
            managed_root=managed_root,
            reason=f"{type(exc).__name__}: {exc}",
        )

    return _cleanup_result(
        ok=True,
        action="deleted",
        target=target,
        managed=True,
        managed_root=managed_root,
        reason="managed upload temp root deleted",
    )


def _cleanup_result(
    *,
    ok: bool,
    action: str,
    target: Path,
    managed: bool,
    reason: str,
    managed_root: Path | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "action": action,
        "managed": managed,
        "target": str(target),
        "managed_root": str(managed_root) if managed_root is not None else "",
        "reason": reason,
    }


def _safe_top_folder(value: str) -> str:
    text = str(value or "repo").replace("\\", "/").strip()
    first = next((part for part in text.split("/") if part), "repo")
    if first in {".", ".."}:
        return "repo"
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in first)
    return cleaned.strip("._") or "repo"


def _managed_root_for(target: Path) -> Path | None:
    if target.name.startswith(MANAGED_UPLOAD_TEMP_PREFIX):
        return target
    parent = target.parent
    if parent.name.startswith(MANAGED_UPLOAD_TEMP_PREFIX):
        return parent
    return None


def _is_managed_root(path: Path, base: Path) -> bool:
    return path.name.startswith(MANAGED_UPLOAD_TEMP_PREFIX) and _is_under(path, base)


def _dangerous_path_reason(target: Path, managed_root: Path, base: Path) -> str:
    protected = {
        Path.cwd().resolve(),
        Path.home().resolve(),
        base,
    }
    anchors = {Path(anchor).resolve() for anchor in {target.anchor, managed_root.anchor} if anchor}
    protected |= anchors
    if target in protected or managed_root in protected:
        return "refusing to clean project root, home, temp base, or drive root"
    if ".git" in {part.lower() for part in target.parts}:
        return "refusing to clean a .git path"
    if managed_root.name in {"", ".", ".."}:
        return "managed root name is unsafe"
    return ""


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _temp_base(temp_base: str | Path | None) -> Path:
    return Path(temp_base or tempfile.gettempdir()).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
