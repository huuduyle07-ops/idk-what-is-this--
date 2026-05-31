"""Phase 12.15a - Harness Control Registry MVP.

A control surface (sibling to System Health) that shows the current effective
state of each harness gate/flag and lets the user persist a *desired* override
to ``.agent/harness_overrides.json``. For ``editable_live`` controls, saving an
override also patches the in-process ``config`` attribute so call-time readers
honor it immediately; ``editable_restart_required`` controls only persist the
desired value (the UI marks them restart-required).

This module **only flips existing flags**. It does not reimplement or change
ranking, patch generation, validation, benchmark scoring, lesson storage,
retrieval, CONTROL prompt injection, or graph weights. It performs no model/API
calls, no DB writes, and — in this phase — no ``.env`` / ``docker-compose.yml``
writes (that is Phase 12.15b / 12.15c). It only reads the registry, env/config,
and reads/writes the overlay JSON.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import config as _config


class HarnessControlError(Exception):
    """Raised when a control cannot be set (planned, locked, unknown, invalid)."""


# Control types --------------------------------------------------------------
EDITABLE_LIVE = "editable_live"
EDITABLE_RESTART_REQUIRED = "editable_restart_required"
READ_ONLY_PLANNED = "read_only_planned"
LOCKED_INVARIANT = "locked_invariant"

# source_of_truth values -----------------------------------------------------
SRC_OVERLAY = "overlay"
SRC_ENV = "env"
SRC_DOCKER_COMPOSE = "docker_compose"
SRC_LOCKED = "locked_invariant"
SRC_PLANNED = "planned"

_TRUE_STRINGS = {"1", "true", "yes", "y", "on"}
_FALSE_STRINGS = {"0", "false", "no", "n", "off"}


@dataclass(frozen=True)
class HarnessControl:
    id: str
    label: str
    env_var: str | None
    category: str
    control_type: str
    source_of_truth: str
    wired: bool
    risk: str
    value_kind: str  # "bool" | "enum" | "locked"
    description: str
    plan_ref: str = ""
    enum_options: tuple[str, ...] = field(default_factory=tuple)
    env_targets: tuple[str, ...] = field(default_factory=tuple)
    config_default: Any = None

    @property
    def editable(self) -> bool:
        return self.control_type in {EDITABLE_LIVE, EDITABLE_RESTART_REQUIRED}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
REGISTRY: tuple[HarnessControl, ...] = (
    # --- editable wired (live) ---
    HarnessControl(
        id="LESSON_RETRIEVAL_ENABLED",
        label="Lesson retrieval (CONTROL advisory injection)",
        env_var="LESSON_RETRIEVAL_ENABLED",
        category="gates",
        control_type=EDITABLE_LIVE,
        source_of_truth=SRC_OVERLAY,
        wired=True,
        risk="medium",
        value_kind="bool",
        description="Inject active-lesson advisory hints into the CONTROL prompt.",
        env_targets=(".env",),
        config_default=False,
    ),
    HarnessControl(
        id="MUTATION_ORACLE_ENABLED",
        label="Mutation oracle (post-validation mutant check)",
        env_var="MUTATION_ORACLE_ENABLED",
        category="gates",
        control_type=EDITABLE_LIVE,
        source_of_truth=SRC_OVERLAY,
        wired=True,
        risk="low",
        value_kind="bool",
        description="After a patch passes, re-validate small mutants to test the gate's strength.",
        env_targets=(".env",),
        config_default=False,
    ),
    HarnessControl(
        id="OLLAMA_ENABLED",
        label="Ollama local critic",
        env_var="OLLAMA_ENABLED",
        category="gates",
        control_type=EDITABLE_LIVE,
        source_of_truth=SRC_OVERLAY,
        wired=True,
        risk="low",
        value_kind="bool",
        description="Enable the local Ollama reviewer model.",
        env_targets=(".env",),
        config_default=False,
    ),
    # --- editable wired (restart required) ---
    HarnessControl(
        id="AUTO_PATCH_ENABLED",
        label="Auto-patch (pipeline applies patches)",
        env_var="AUTO_PATCH_ENABLED",
        category="gates",
        control_type=EDITABLE_RESTART_REQUIRED,
        source_of_truth=SRC_ENV,
        wired=True,
        risk="high",
        value_kind="bool",
        description="Allow the pipeline to apply patches. Bound at import; needs a restart.",
        env_targets=(".env",),
        config_default=True,
    ),
    HarnessControl(
        id="DB_ENABLED",
        label="Database persistence (Postgres)",
        env_var="DB_ENABLED",
        category="gates",
        control_type=EDITABLE_RESTART_REQUIRED,
        source_of_truth=SRC_ENV,
        wired=True,
        risk="medium",
        value_kind="bool",
        description="Master switch for DB persistence. Resolved at startup.",
        env_targets=(".env", "docker-compose.yml"),
        config_default=True,
    ),
    HarnessControl(
        id="EMBEDDING_PROVIDER",
        label="Embedding provider",
        env_var="EMBEDDING_PROVIDER",
        category="gates",
        control_type=EDITABLE_RESTART_REQUIRED,
        source_of_truth=SRC_ENV,
        wired=True,
        risk="medium",
        value_kind="enum",
        enum_options=("off", "local_minilm", "gemini"),
        description="Vector embedding provider. Changing it requires a re-index/restart.",
        env_targets=(".env", "docker-compose.yml"),
        config_default="off",
    ),
    # --- planned / not wired ---
    HarnessControl(
        id="MEMORY_TEMPERATURE_RETRIEVAL_ENABLED",
        label="Memory temperature → retrieval (planned)",
        env_var="MEMORY_TEMPERATURE_RETRIEVAL_ENABLED",
        category="gates",
        control_type=READ_ONLY_PLANNED,
        source_of_truth=SRC_PLANNED,
        wired=False,
        risk="medium",
        value_kind="bool",
        description="Future: let memory temperature influence retrieval. Not wired; greenlight-gated.",
        plan_ref="Phase 12.14d",
    ),
    HarnessControl(
        id="MEMORY_TEMPERATURE_TIEBREAK_ONLY",
        label="Memory temperature tie-break only (planned)",
        env_var="MEMORY_TEMPERATURE_TIEBREAK_ONLY",
        category="gates",
        control_type=READ_ONLY_PLANNED,
        source_of_truth=SRC_PLANNED,
        wired=False,
        risk="low",
        value_kind="bool",
        description="Future: first experiment uses memory temperature only as a tie-breaker.",
        plan_ref="Phase 12.14d",
    ),
    HarnessControl(
        id="dream_create_patches",
        label="Dream → create patches / human-approval (planned)",
        env_var=None,
        category="dream",
        control_type=READ_ONLY_PLANNED,
        source_of_truth=SRC_PLANNED,
        wired=False,
        risk="high",
        value_kind="bool",
        description="Future: allow Dream to create patches behind a human-approval gate. Dream is report-only today.",
        plan_ref="Dream report-only (future phase)",
    ),
    # --- locked safety invariants ---
    HarnessControl(
        id="quote_grounding",
        label="Quote grounding",
        env_var=None,
        category="invariants",
        control_type=LOCKED_INVARIANT,
        source_of_truth=SRC_LOCKED,
        wired=True,
        risk="low",
        value_kind="locked",
        description="Patches must quote real code they touch. Always on.",
    ),
    HarnessControl(
        id="patch_safety_path_traversal_guard",
        label="Patch safety / path-traversal guard",
        env_var=None,
        category="invariants",
        control_type=LOCKED_INVARIANT,
        source_of_truth=SRC_LOCKED,
        wired=True,
        risk="low",
        value_kind="locked",
        description="Path-traversal and forbidden-write guards. Always on.",
    ),
    HarnessControl(
        id="frozen_audit_only_exclusion",
        label="Frozen / audit-only memory exclusion",
        env_var=None,
        category="invariants",
        control_type=LOCKED_INVARIANT,
        source_of_truth=SRC_LOCKED,
        wired=True,
        risk="low",
        value_kind="locked",
        description="Frozen / audit-only memories are never surfaced or retrieved. Always on.",
    ),
    HarnessControl(
        id="harness_hard_deny_path_runtime",
        label="Harness hard-deny path/runtime conflict",
        env_var=None,
        category="invariants",
        control_type=LOCKED_INVARIANT,
        source_of_truth=SRC_LOCKED,
        wired=True,
        risk="low",
        value_kind="locked",
        description="Hard path/runtime conflicts are denied before draft generation. Always on.",
    ),
    HarnessControl(
        id="human_approval_dangerous_writes",
        label="Human approval for dangerous writes",
        env_var=None,
        category="invariants",
        control_type=LOCKED_INVARIANT,
        source_of_truth=SRC_LOCKED,
        wired=True,
        risk="low",
        value_kind="locked",
        description="Dangerous writes require explicit human approval. Always on.",
    ),
)

_BY_ID: dict[str, HarnessControl] = {c.id: c for c in REGISTRY}


def get_control(control_id: str) -> HarnessControl | None:
    return _BY_ID.get(control_id)


# ---------------------------------------------------------------------------
# Overlay store
# ---------------------------------------------------------------------------

def default_overlay_path() -> Path:
    return Path(_config.AGENT_DIR) / "harness_overrides.json"


def _resolve_overlay_path(overlay_path: str | Path | None) -> Path:
    if overlay_path is not None:
        return Path(overlay_path)
    return default_overlay_path()


def load_overlay(overlay_path: str | Path | None = None) -> dict[str, str]:
    """Read the overlay JSON. Fail-soft: missing/malformed → empty dict."""
    path = _resolve_overlay_path(overlay_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def save_overlay(values: dict[str, str], overlay_path: str | Path | None = None) -> Path:
    """Atomically write the overlay JSON."""
    path = _resolve_overlay_path(overlay_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {str(k): str(v) for k, v in (values or {}).items()},
        indent=2,
        ensure_ascii=False,
    )
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass
    return path


# ---------------------------------------------------------------------------
# Value normalization
# ---------------------------------------------------------------------------

def _normalize_value(control: HarnessControl, value: Any) -> tuple[str, Any]:
    """Return ``(overlay_string, typed_value)`` or raise HarnessControlError."""
    if control.value_kind == "bool":
        if isinstance(value, bool):
            b = value
        else:
            text = str(value).strip().lower()
            if text in _TRUE_STRINGS:
                b = True
            elif text in _FALSE_STRINGS:
                b = False
            else:
                raise HarnessControlError(
                    f"{control.id}: expected a boolean value, got {value!r}"
                )
        return ("true" if b else "false"), b
    if control.value_kind == "enum":
        text = str(value).strip()
        if text not in control.enum_options:
            raise HarnessControlError(
                f"{control.id}: {text!r} is not one of {control.enum_options}"
            )
        return text, text
    raise HarnessControlError(f"{control.id}: not an editable value kind")


# ---------------------------------------------------------------------------
# Effective-state probe (read-only)
# ---------------------------------------------------------------------------

def current_effective(control: HarnessControl, config_module: Any = None) -> str:
    """Read the current effective value of a control. Never mutates anything."""
    cfg = config_module if config_module is not None else _config
    if control.control_type == LOCKED_INVARIANT:
        return "on"
    if control.control_type == READ_ONLY_PLANNED:
        return "planned"

    if control.value_kind == "bool":
        if control.env_var and hasattr(cfg, control.env_var):
            return "true" if bool(getattr(cfg, control.env_var)) else "false"
        # fall back to env (e.g. flags not mirrored on the config module)
        raw = os.getenv(control.env_var or "", "")
        if raw:
            return "true" if raw.strip().lower() in _TRUE_STRINGS else "false"
        return "true" if bool(control.config_default) else "false"

    if control.value_kind == "enum":
        if control.env_var and hasattr(cfg, control.env_var):
            return str(getattr(cfg, control.env_var))
        raw = os.getenv(control.env_var or "", "").strip()
        return raw or str(control.config_default or "")

    return "unknown"


def _control_to_dict(
    control: HarnessControl,
    overlay: dict[str, str],
    config_module: Any,
) -> dict[str, Any]:
    effective = current_effective(control, config_module=config_module)
    pending = overlay.get(control.env_var) if control.env_var else None
    applied_differs = bool(pending is not None and pending != effective)
    return {
        "id": control.id,
        "label": control.label,
        "env_var": control.env_var,
        "category": control.category,
        "control_type": control.control_type,
        "source_of_truth": control.source_of_truth,
        "wired": control.wired,
        "risk": control.risk,
        "value_kind": control.value_kind,
        "enum_options": list(control.enum_options),
        "env_targets": list(control.env_targets),
        "description": control.description,
        "plan_ref": control.plan_ref,
        "editable": control.editable,
        "current_effective": effective,
        "pending": pending,
        "applied_differs": applied_differs,
    }


def list_controls(
    overlay_path: str | Path | None = None,
    config_module: Any = None,
) -> list[dict[str, Any]]:
    overlay = load_overlay(overlay_path)
    return [_control_to_dict(c, overlay, config_module) for c in REGISTRY]


def list_categories(
    overlay_path: str | Path | None = None,
    config_module: Any = None,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in list_controls(overlay_path=overlay_path, config_module=config_module):
        grouped.setdefault(entry["category"], []).append(entry)
    return grouped


# ---------------------------------------------------------------------------
# set_override (Save overlay)
# ---------------------------------------------------------------------------

def set_override(
    control_id: str,
    value: Any,
    overlay_path: str | Path | None = None,
    config_module: Any = None,
) -> dict[str, Any]:
    """Persist a desired override; live-patch ``editable_live`` controls.

    Raises HarnessControlError for unknown / planned / locked controls or for an
    invalid value. Never writes ``.env`` or ``docker-compose.yml``.
    """
    control = get_control(control_id)
    if control is None:
        raise HarnessControlError(f"unknown control: {control_id!r}")
    if control.control_type == LOCKED_INVARIANT:
        raise HarnessControlError(
            f"{control_id} is a locked safety invariant and cannot be changed."
        )
    if control.control_type == READ_ONLY_PLANNED or not control.wired:
        raise HarnessControlError(
            f"{control_id} is planned / not wired and cannot be set yet."
        )
    if not control.env_var:
        raise HarnessControlError(f"{control_id} has no env var to override.")

    overlay_string, typed = _normalize_value(control, value)

    overlay = load_overlay(overlay_path)
    overlay[control.env_var] = overlay_string
    save_overlay(overlay, overlay_path)

    applied_live = False
    if control.control_type == EDITABLE_LIVE:
        cfg = config_module if config_module is not None else _config
        setattr(cfg, control.env_var, typed)
        applied_live = True

    restart_required = control.control_type == EDITABLE_RESTART_REQUIRED
    result = _control_to_dict(control, load_overlay(overlay_path), config_module)
    result["applied_live"] = applied_live
    result["restart_required"] = restart_required
    return result


# ---------------------------------------------------------------------------
# Phase 12.15b - Apply overlay values to .env (backup first; never compose)
# ---------------------------------------------------------------------------
ENV_TARGET = ".env"


def default_env_path() -> Path:
    return Path(_config.BASE_DIR) / ".env"


def _env_path(repo_path: str | Path | None) -> Path:
    if repo_path is not None:
        return Path(repo_path) / ".env"
    return default_env_path()


def _selected_env_controls(control_ids) -> list[HarnessControl]:
    """Resolve the editable, .env-targeted controls to consider.

    With explicit ``control_ids``, planned / locked / unknown / non-editable /
    non-.env controls raise HarnessControlError. With ``None``, scan all
    editable controls whose ``env_targets`` include ``.env``.
    """
    if control_ids is None:
        return [c for c in REGISTRY if c.editable and ENV_TARGET in c.env_targets]
    selected: list[HarnessControl] = []
    for cid in control_ids:
        control = get_control(cid)
        if control is None:
            raise HarnessControlError(f"unknown control: {cid!r}")
        if control.control_type == LOCKED_INVARIANT:
            raise HarnessControlError(f"{cid} is a locked safety invariant.")
        if control.control_type == READ_ONLY_PLANNED or not control.wired:
            raise HarnessControlError(f"{cid} is planned / not wired.")
        if not control.editable or ENV_TARGET not in control.env_targets:
            raise HarnessControlError(f"{cid} does not target {ENV_TARGET}.")
        selected.append(control)
    return selected


_env_line_re_cache: dict[str, re.Pattern] = {}


def _env_key_pattern(key: str) -> re.Pattern:
    pat = _env_line_re_cache.get(key)
    if pat is None:
        pat = re.compile(r"^\s*(?:export\s+)?" + re.escape(key) + r"\s*=")
        _env_line_re_cache[key] = pat
    return pat


def _read_env_value(text: str, key: str) -> str | None:
    pattern = _env_key_pattern(key)
    for line in text.split("\n"):
        if pattern.match(line):
            return line.split("=", 1)[1].strip()
    return None


def _set_or_append_env_line(text: str, key: str, value: str) -> str:
    pattern = _env_key_pattern(key)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}"
            return "\n".join(lines)
    # Not found: append, preserving a trailing newline if present.
    if lines and lines[-1] == "":
        lines.insert(len(lines) - 1, f"{key}={value}")
    else:
        lines.append(f"{key}={value}")
    return "\n".join(lines)


def _normalize_env_current(control: HarnessControl, raw: str | None) -> str | None:
    if raw is None:
        return None
    if control.value_kind == "bool":
        t = raw.strip().lower()
        if t in _TRUE_STRINGS:
            return "true"
        if t in _FALSE_STRINGS:
            return "false"
    return raw.strip()


def pending_env_diff(
    control_ids=None,
    repo_path: str | Path | None = None,
    overlay_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return the overlay-vs-.env differences for editable .env controls.

    Each entry: ``{control_id, env_var, old, new, control_type, restart_required}``.
    Read-only — touches no files for writing.
    """
    overlay = load_overlay(overlay_path)
    env_path = _env_path(repo_path)
    try:
        env_text = env_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        env_text = ""

    diff: list[dict[str, Any]] = []
    for control in _selected_env_controls(control_ids):
        desired = overlay.get(control.env_var)
        if desired is None:
            continue
        raw_current = _read_env_value(env_text, control.env_var)
        if _normalize_env_current(control, raw_current) == desired:
            continue
        diff.append(
            {
                "control_id": control.id,
                "env_var": control.env_var,
                "old": raw_current,
                "new": desired,
                "control_type": control.control_type,
                "restart_required": control.control_type == EDITABLE_RESTART_REQUIRED,
            }
        )
    return diff


def _backup_env_file(env_path: Path, now: datetime | None) -> Path:
    """Write a timestamped byte-for-byte backup of ``env_path``. May raise OSError."""
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    backup_path = env_path.parent / f"{env_path.name}.bak-{stamp}"
    backup_path.write_bytes(env_path.read_bytes())
    return backup_path


def apply_to_env_files(
    control_ids=None,
    repo_path: str | Path | None = None,
    now: datetime | None = None,
    overlay_path: str | Path | None = None,
) -> dict[str, Any]:
    """Apply overlay values to ``.env`` after a timestamped backup.

    Never writes ``docker-compose.yml``. Surgically updates only targeted
    ``KEY=value`` lines (appending if absent) and leaves all other lines
    byte-identical. Aborts (raising HarnessControlError) if the backup fails,
    leaving ``.env`` untouched. A no-op when there is no pending diff.
    """
    diff = pending_env_diff(control_ids, repo_path=repo_path, overlay_path=overlay_path)
    if not diff:
        return {
            "noop": True,
            "file_written": None,
            "backup_created": None,
            "changes": [],
            "restart_required": [],
        }

    env_path = _env_path(repo_path)

    backup_created: str | None = None
    if env_path.exists():
        try:
            backup_path = _backup_env_file(env_path, now)
        except OSError as exc:
            raise HarnessControlError(
                f"backup of {env_path} failed; .env left untouched: {exc}"
            ) from exc
        backup_created = str(backup_path)

    try:
        text = env_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    for entry in diff:
        text = _set_or_append_env_line(text, entry["env_var"], entry["new"])
    env_path.write_text(text, encoding="utf-8")

    changes = [
        {"control_id": e["control_id"], "env_var": e["env_var"], "old": e["old"], "new": e["new"]}
        for e in diff
    ]
    restart_required = [e["control_id"] for e in diff if e["restart_required"]]
    return {
        "noop": False,
        "file_written": str(env_path),
        "backup_created": backup_created,
        "changes": changes,
        "restart_required": restart_required,
    }


# ---------------------------------------------------------------------------
# Phase 12.15c - Preview / apply to docker-compose.yml (cattus-web only)
# ---------------------------------------------------------------------------
COMPOSE_TARGET = "docker-compose.yml"
COMPOSE_SERVICE = "cattus-web"
_COMPOSE_KEY_RE = re.compile(r"^(\s+)([A-Za-z_][A-Za-z0-9_]*):\s?(.*)$")


def default_compose_path() -> Path:
    return Path(_config.BASE_DIR) / "docker-compose.yml"


def _compose_path(repo_path: str | Path | None) -> Path:
    if repo_path is not None:
        return Path(repo_path) / "docker-compose.yml"
    return default_compose_path()


def _selected_compose_controls(control_ids) -> list[HarnessControl]:
    """Resolve editable controls whose env_targets include docker-compose.yml.

    Explicit planned / locked / unknown / non-editable / non-compose ids raise.
    """
    if control_ids is None:
        return [c for c in REGISTRY if c.editable and COMPOSE_TARGET in c.env_targets]
    selected: list[HarnessControl] = []
    for cid in control_ids:
        control = get_control(cid)
        if control is None:
            raise HarnessControlError(f"unknown control: {cid!r}")
        if control.control_type == LOCKED_INVARIANT:
            raise HarnessControlError(f"{cid} is a locked safety invariant.")
        if control.control_type == READ_ONLY_PLANNED or not control.wired:
            raise HarnessControlError(f"{cid} is planned / not wired.")
        if not control.editable or COMPOSE_TARGET not in control.env_targets:
            raise HarnessControlError(f"{cid} does not target {COMPOSE_TARGET}.")
        selected.append(control)
    return selected


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unquote(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def _service_block_range(lines: list[str], service: str):
    services_idx = None
    for i, ln in enumerate(lines):
        if ln.strip() == "services:" and _indent_of(ln) == 0:
            services_idx = i
            break
    if services_idx is None:
        return None
    svc_idx = svc_indent = None
    for i in range(services_idx + 1, len(lines)):
        ln = lines[i]
        if ln.strip() == "":
            continue
        ind = _indent_of(ln)
        if ind == 0:
            break  # left the services: section
        if ln.strip() == f"{service}:":
            svc_idx, svc_indent = i, ind
            break
    if svc_idx is None:
        return None
    svc_end = len(lines)
    for i in range(svc_idx + 1, len(lines)):
        ln = lines[i]
        if ln.strip() == "":
            continue
        if _indent_of(ln) <= svc_indent:
            svc_end = i
            break
    return svc_idx, svc_indent, svc_end


def _env_block_range(lines: list[str], svc_idx: int, svc_indent: int, svc_end: int):
    env_idx = env_indent = None
    for i in range(svc_idx + 1, svc_end):
        ln = lines[i]
        if ln.strip() == "":
            continue
        ind = _indent_of(ln)
        if ind <= svc_indent:
            break
        if ln.strip() == "environment:" and ind == svc_indent + 2:
            env_idx, env_indent = i, ind
            break
    if env_idx is None:
        return None
    env_end = svc_end
    for i in range(env_idx + 1, svc_end):
        ln = lines[i]
        if ln.strip() == "":
            continue
        if _indent_of(ln) <= env_indent:
            env_end = i
            break
    return env_idx, env_indent, env_end


def _compose_env_keys(lines: list[str], env_idx: int, env_end: int) -> list[tuple[int, str, str, str]]:
    """Return (line_index, indent_str, key, raw_value) for each env key line."""
    keys: list[tuple[int, str, str, str]] = []
    for i in range(env_idx + 1, env_end):
        if lines[i].strip() == "":
            continue
        m = _COMPOSE_KEY_RE.match(lines[i])
        if m:
            keys.append((i, m.group(1), m.group(2), m.group(3)))
    return keys


def _read_compose_env_value(text: str, key: str) -> str | None:
    lines = text.split("\n")
    rng = _service_block_range(lines, COMPOSE_SERVICE)
    if rng is None:
        return None
    erng = _env_block_range(lines, *rng)
    if erng is None:
        return None
    env_idx, _env_indent, env_end = erng
    for _i, _ind, k, raw in _compose_env_keys(lines, env_idx, env_end):
        if k == key:
            return _unquote(raw)
    return None


def _set_compose_env_value(text: str, key: str, value: str) -> str:
    lines = text.split("\n")
    rng = _service_block_range(lines, COMPOSE_SERVICE)
    if rng is None:
        raise HarnessControlError(f"service {COMPOSE_SERVICE!r} not found in docker-compose.yml")
    erng = _env_block_range(lines, *rng)
    if erng is None:
        raise HarnessControlError(
            f"{COMPOSE_SERVICE}.environment block not found in docker-compose.yml"
        )
    env_idx, env_indent, env_end = erng
    env_keys = _compose_env_keys(lines, env_idx, env_end)

    for i, ind, k, _raw in env_keys:
        if k == key:
            lines[i] = f'{ind}{key}: "{value}"'
            return "\n".join(lines)

    # Append after the last existing env key (or right under environment:).
    key_indent = env_keys[0][1] if env_keys else " " * (env_indent + 2)
    insert_at = (env_keys[-1][0] + 1) if env_keys else (env_idx + 1)
    lines.insert(insert_at, f'{key_indent}{key}: "{value}"')
    return "\n".join(lines)


def preview_compose_patch(
    control_ids=None,
    repo_path: str | Path | None = None,
    overlay_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return the overlay-vs-docker-compose diff. Writes nothing."""
    overlay = load_overlay(overlay_path)
    compose_path = _compose_path(repo_path)
    try:
        text = compose_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""

    diff: list[dict[str, Any]] = []
    for control in _selected_compose_controls(control_ids):
        desired = overlay.get(control.env_var)
        if desired is None:
            continue
        raw_current = _read_compose_env_value(text, control.env_var)
        normalized = None
        if raw_current is not None:
            normalized = raw_current.strip()
            if control.value_kind == "bool":
                low = normalized.lower()
                if low in _TRUE_STRINGS:
                    normalized = "true"
                elif low in _FALSE_STRINGS:
                    normalized = "false"
        if normalized == desired:
            continue
        diff.append(
            {
                "control_id": control.id,
                "env_var": control.env_var,
                "old": raw_current,
                "new": desired,
                "restart_required": True,
            }
        )
    return diff


def _backup_compose_file(compose_path: Path, now: datetime | None) -> Path:
    """Write a timestamped byte-for-byte backup of docker-compose.yml. May raise OSError."""
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    backup_path = compose_path.parent / f"{compose_path.name}.bak-{stamp}"
    backup_path.write_bytes(compose_path.read_bytes())
    return backup_path


def apply_compose_patch(
    control_ids=None,
    repo_path: str | Path | None = None,
    now: datetime | None = None,
    overlay_path: str | Path | None = None,
) -> dict[str, Any]:
    """Apply overlay values to docker-compose.yml after a timestamped backup.

    Updates only the ``cattus-web`` service ``environment:`` keys; leaves all
    other services, volumes, healthchecks, and comments byte-identical. Aborts
    (raising HarnessControlError) if the backup fails. A no-op when there is no
    pending diff. Never runs Docker.
    """
    diff = preview_compose_patch(control_ids, repo_path=repo_path, overlay_path=overlay_path)
    if not diff:
        return {
            "noop": True,
            "file_written": None,
            "backup_created": None,
            "changes": [],
            "restart_required": False,
        }

    compose_path = _compose_path(repo_path)
    backup_created: str | None = None
    if compose_path.exists():
        try:
            backup_path = _backup_compose_file(compose_path, now)
        except OSError as exc:
            raise HarnessControlError(
                f"backup of {compose_path} failed; docker-compose.yml left untouched: {exc}"
            ) from exc
        backup_created = str(backup_path)

    try:
        text = compose_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    for entry in diff:
        text = _set_compose_env_value(text, entry["env_var"], entry["new"])
    compose_path.write_text(text, encoding="utf-8")

    changes = [
        {"control_id": e["control_id"], "env_var": e["env_var"], "old": e["old"], "new": e["new"]}
        for e in diff
    ]
    return {
        "noop": False,
        "file_written": str(compose_path),
        "backup_created": backup_created,
        "changes": changes,
        "restart_required": True,
    }
