from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import get_agent_dir


JSON_ARTIFACTS = {
    "brain_stamp.json",
    "control_result.json",
    "patch_plan.json",
    "apply_result.json",
    "final_status.json",
}
TEXT_ARTIFACTS = {
    "user_query.txt",
    "validation_output.txt",
}
EVENTS_ARTIFACT = "events.jsonl"
TRUNCATION_MARKER = "\n\n[truncated: replay artifact text exceeded limit]\n"


@dataclass
class RunArtifactRecorder:
    replay_dir: Path
    source: str

    @classmethod
    def start(
        cls,
        repo_path: str | None,
        source: str,
        brain_stamp: dict[str, Any],
    ) -> "RunArtifactRecorder":
        root = get_agent_dir(repo_path) / "replays"
        root.mkdir(parents=True, exist_ok=True)
        stamp_id = str((brain_stamp or {}).get("brain_stamp_id") or uuid.uuid4().hex[:8])
        stamp_short = "".join(ch for ch in stamp_id if ch.isalnum())[:8] or uuid.uuid4().hex[:8]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        replay_dir = root / f"{ts}_{stamp_short}"
        suffix = 1
        while replay_dir.exists():
            replay_dir = root / f"{ts}_{stamp_short}-{suffix}"
            suffix += 1
        replay_dir.mkdir(parents=True)
        recorder = cls(replay_dir=replay_dir, source=source)
        recorder.write_json("brain_stamp.json", brain_stamp or {})
        return recorder

    def write_json(self, name: str, data: Any) -> None:
        path = self._artifact_path(name, JSON_ARTIFACTS)
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def write_text(self, name: str, text: str, max_chars: int = 200_000) -> None:
        path = self._artifact_path(name, TEXT_ARTIFACTS)
        content = text if isinstance(text, str) else str(text or "")
        if max_chars >= 0 and len(content) > max_chars:
            retained_chars = max(0, max_chars - len(TRUNCATION_MARKER))
            content = content[:retained_chars] + TRUNCATION_MARKER
            content = content[:max_chars]
        path.write_text(content, encoding="utf-8")

    def append_event(self, phase: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": self.source,
            "phase": phase,
            "payload": payload or {},
        }
        with (self.replay_dir / EVENTS_ARTIFACT).open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False, default=str) + "\n")

    def finish(self, status: str, result: dict[str, Any]) -> None:
        self.write_json(
            "final_status.json",
            {
                "status": status,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            },
        )

    def _artifact_path(self, name: str, allowed: set[str]) -> Path:
        if name not in allowed:
            raise ValueError(f"unsupported replay artifact name: {name!r}")
        path = (self.replay_dir / name).resolve()
        try:
            path.relative_to(self.replay_dir.resolve())
        except ValueError as e:
            raise ValueError(f"replay artifact path escapes replay dir: {name!r}") from e
        return path
