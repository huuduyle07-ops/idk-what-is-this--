"""Flask-friendly wrapper around scripts/run_patch_proposal_queue.py.

The patch proposal flow already lives as a one-shot CLI in
`scripts/run_patch_proposal_queue.py`. This module surfaces the same
flow to the web UI so the "Make proposal" button does not need to
shell out.

Contract:
- One concurrent run at a time (module-level lock). A second request
  while a run is in-flight returns busy without crashing.
- The UI click IS the explicit human approval (the CLI's
  `human_approved_for_proposal=true` requirement is satisfied by the
  fact that a human pressed a button — the wrapper sets the flag for
  the in-memory copy of the item, never on disk).
- Never modifies the real repo. Uses the same temp-clone code path
  the CLI uses (via `_process_item`).
"""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any

# Reuse the CLI's helpers — single source of truth for the proposal flow.
from scripts.run_patch_proposal_queue import (
    PROPOSAL_ROOT,
    _process_item,
)


_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "running": False,
    "run_id": None,
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


def get_status() -> dict:
    """Return a shallow snapshot of the runner state for polling."""
    return dict(_STATE)


def _reset_state(run_id: str | None) -> None:
    _STATE.update(
        running=True,
        run_id=run_id,
        started_at=datetime.now().isoformat(timespec="seconds"),
        finished_at=None,
        result=None,
        error=None,
    )


def make_proposal_for_item(
    item: dict,
    *,
    validation_timeout_sec: int = 60,
) -> dict:
    """Kick off a proposal run for one plan item. Returns immediately.

    Response shape:
      {"ok": True, "run_id": str, "run_dir": str}   on accepted
      {"ok": False, "error": str}                    on bad input / busy
    """
    if not isinstance(item, dict) or not item.get("case_name"):
        return {"ok": False, "error": "item must be a dict including case_name"}

    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "error": "another proposal run is already in progress"}

    # The UI click IS the explicit human approval.
    approved_item = dict(item)
    approved_item["human_approved_for_proposal"] = True

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_run_dir = PROPOSAL_ROOT / run_id
    suffix = 0
    run_dir = base_run_dir
    while run_dir.exists():
        suffix += 1
        run_dir = PROPOSAL_ROOT / f"{run_id}-{suffix}"
    run_dir.mkdir(parents=True, exist_ok=False)

    _reset_state(run_dir.name)

    def _run():
        try:
            result = _process_item(
                item=approved_item,
                idx=1,
                run_dir=run_dir,
                validation_timeout_sec=validation_timeout_sec,
            )
            _STATE["result"] = result
        except Exception as exc:
            _STATE["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            _STATE["running"] = False
            _STATE["finished_at"] = datetime.now().isoformat(timespec="seconds")
            _LOCK.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "run_id": run_dir.name, "run_dir": str(run_dir)}
