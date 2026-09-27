"""AUTH.DREAM.1: exact stored Dream candidate identity, never write authority.

The existing date[/run] key locates a report. Its commitment includes that key,
canonical repository ID, list.json bytes, displayed summary bytes and this
item's patch_plan.json bytes (including absence). The executable digest covers
kind/status plus ordered operations' op, relative_path, file, content,
target_snippet and patched_snippet fields. Other plan keys are ignored by the
executor; they remain covered by the stricter artifact freshness commitment.

Review displays the same captured plan that is fingerprinted. Apply reloads
only named artifacts and passes the verified in-memory payload to the existing
gates/executor. No latest lookup, repository walk, model, or consumption policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

from core import dream_artifacts
from core.repository_identity import build_repository_identity, is_repository_id
from core.execution_outcome_telemetry import DENIED_CANDIDATE_MISMATCH, no_execution


SCHEMA = "dream_reviewed_candidate_v1"
_RUN_KEY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:/[0-9]{6}-run(?:-[0-9]+)?)?")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_EXECUTABLE_FIELDS = (
    "op", "relative_path", "file", "content", "target_snippet", "patched_snippet",
)
FAILURE_CODES = frozenset({
    "review_binding_required", "reviewed_run_not_found",
    "reviewed_candidate_not_found", "reviewed_candidate_changed",
    "reviewed_repository_mismatch", "reviewed_artifact_stale",
})


class DreamReviewError(ValueError):
    def __init__(self, code: str):
        assert code in FAILURE_CODES
        self.code = code
        super().__init__(f"{code}: Review the Dream candidate again before Apply.")

    def as_payload(self) -> dict:
        return {
            "success": False, "status": self.code, "code": self.code,
            "error": str(self), "message": str(self), "review_required": True,
            **no_execution(DENIED_CANDIDATE_MISMATCH).as_payload_fields(),
        }


@dataclass(frozen=True)
class DreamReviewedCandidateBinding:
    schema_version: str
    repository_id: str
    run_key: str
    item_idx: int
    candidate_fingerprint: str
    artifact_fingerprint: str

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> DreamReviewedCandidateBinding:
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise DreamReviewError("review_binding_required")
        if (value["schema_version"] != SCHEMA
                or not is_repository_id(value["repository_id"])
                or type(value["run_key"]) is not str
                or len(value["run_key"]) > 80
                or not _RUN_KEY.fullmatch(value["run_key"])
                or type(value["item_idx"]) is not int or value["item_idx"] < 1
                or any(type(value[key]) is not str or not _DIGEST.fullmatch(value[key])
                       for key in ("candidate_fingerprint", "artifact_fingerprint"))):
            raise DreamReviewError("review_binding_required")
        return cls(**value)


@dataclass(frozen=True)
class ResolvedDreamCandidate:
    binding: DreamReviewedCandidateBinding
    canonical_root: str
    item_json: str
    plan_bytes: bytes | None

    @property
    def item(self) -> dict:
        return json.loads(self.item_json)

    @property
    def plan(self):
        return json.loads(self.plan_bytes.decode("utf-8")) if self.plan_bytes is not None else None

    def receipt(self, *, executed: bool = False) -> dict:
        identity = self.binding.as_dict()
        return {"identity_verified": True, "reviewed": identity,
                "resolved": identity, "executed": identity if executed else None}


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def candidate_fingerprint(item: dict, plan: object) -> str:
    # Preserve order, raw path aliases, missing fields and exact string content.
    executable = [
        {key: op[key] for key in _EXECUTABLE_FIELDS if key in op}
        if type(op) is dict else op for op in plan
    ] if type(plan) is list else plan
    return _digest(_json({"kind": item.get("kind"), "status": item.get("status"),
                          "patch_plan": executable}).encode("utf-8"))


def _contained(root: Path, *parts: str) -> Path:
    """Inspect only the named chain; disallow artifact links/alias retargeting."""
    path = root
    for part in parts:
        if not part or part in {".", ".."} or any(c in part for c in "/\\:\x00"):
            raise DreamReviewError("reviewed_artifact_stale")
        path = path / part
        if path.is_symlink() or path.is_junction():
            raise DreamReviewError("reviewed_artifact_stale")
    path.resolve().relative_to(root.resolve())
    return path


def _load_report(repo_path: str, run_key: str):
    try:
        identity = build_repository_identity(repo_path)
        root = dream_artifacts.dreams_root(identity.canonical_root).resolve()
        report_dir = _contained(root, *run_key.split("/"))
        list_path = _contained(root, *run_key.split("/"), "list.json")
        try:
            list_bytes = list_path.read_bytes()
        except FileNotFoundError:
            raise DreamReviewError("reviewed_run_not_found") from None
        data = json.loads(list_bytes.decode("utf-8"))
        if type(data) is not dict or type(data.get("items")) is not list:
            raise DreamReviewError("reviewed_artifact_stale")
        summary_name, summary_bytes = None, None
        for name in ("dream_run_summary.md", "morning_report.txt"):
            path = _contained(root, *run_key.split("/"), name)
            if path.exists():
                summary_name, summary_bytes = name, path.read_bytes()
                break
        commitment = {"repository_id": identity.repository_id, "run_key": run_key,
                      "list": _digest(list_bytes), "summary_name": summary_name,
                      "summary": _digest(summary_bytes)}
        return identity, report_dir, data, list_bytes, summary_bytes, commitment
    except DreamReviewError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise DreamReviewError("reviewed_artifact_stale") from None


def _resolve_item(snapshot, run_key: str, idx: int) -> ResolvedDreamCandidate:
    identity, report_dir, data, _, _, commitment = snapshot
    matches = [it for it in data["items"] if type(it) is dict and type(it.get("idx")) is int
               and it["idx"] == idx]
    if not matches:
        raise DreamReviewError("reviewed_candidate_not_found")
    if len(matches) != 1:
        raise DreamReviewError("reviewed_artifact_stale")
    item = matches[0]
    try:
        if any(item.get(key) is not None and type(item[key]) is not str
               for key in ("kind", "status", "title")):
            raise DreamReviewError("reviewed_artifact_stale")
        name = item.get("item_dir_name")
        if type(name) is not str:
            raise DreamReviewError("reviewed_artifact_stale")
        plan_path = _contained(report_dir, name, "patch_plan.json")
        plan_bytes = plan_path.read_bytes() if plan_path.exists() else None
        plan = json.loads(plan_bytes.decode("utf-8")) if plan_bytes is not None else None
        if plan_bytes is not None and type(plan) is not list:
            raise DreamReviewError("reviewed_artifact_stale")
        binding = DreamReviewedCandidateBinding(
            SCHEMA, identity.repository_id, run_key, idx,
            candidate_fingerprint(item, plan),
            _digest(_json({**commitment, "item_idx": idx, "item_dir_name": name,
                           "patch_plan": _digest(plan_bytes)}).encode("utf-8")),
        )
        return ResolvedDreamCandidate(binding, identity.canonical_root, _json(item), plan_bytes)
    except DreamReviewError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise DreamReviewError("reviewed_artifact_stale") from None


def attach_review_candidates(repo_path: str, report_dir: Path, report: dict) -> dict:
    """Offer selectors with exact displayed bytes; selection is a later UI action.

    Legacy reports can be freshly rebound here, never by numeric Apply alone.
    Unreadable/ambiguous legacy items remain viewable without a binding.
    """
    try:
        run_key = report_dir.relative_to(dream_artifacts.dreams_root(repo_path)).as_posix()
        if not _RUN_KEY.fullmatch(run_key):
            raise DreamReviewError("review_binding_required")
        snapshot = _load_report(repo_path, run_key)
        _, _, data, list_bytes, summary_bytes, _ = snapshot
        report.update({key: data.get(key) for key in ("patch_style", "dream_mode", "completed_at")})
        report["list_json_raw"] = list_bytes.decode("utf-8")
        report["morning_report"] = summary_bytes.decode("utf-8") if summary_bytes else ""
        items = dream_artifacts.enrich_report_patch_blockers(report_dir, data["items"], data.get("dream_mode"))
        for item in items:
            # Stored/client metadata is never a pre-existing review receipt.
            item.pop("review_binding", None)
            item.pop("reviewed_patch_plan", None)
            try:
                idx = item.get("idx")
                if type(idx) is not int or idx < 1:
                    raise DreamReviewError("review_binding_required")
                candidate = _resolve_item(snapshot, run_key, idx)
                item["review_binding"] = candidate.binding.as_dict()
                item["reviewed_patch_plan"] = candidate.plan
            except DreamReviewError as error:
                item["review_error"] = error.code
        report["items"] = items
    except (DreamReviewError, OSError, ValueError, RuntimeError) as error:
        report["review_error"] = getattr(error, "code", "reviewed_artifact_stale")
        for item in report.get("items", []):
            item.pop("review_binding", None)
            item.pop("reviewed_patch_plan", None)
    return report


def resolve_reviewed_candidate(repo_path: str, supplied: object) -> ResolvedDreamCandidate:
    binding = DreamReviewedCandidateBinding.from_dict(supplied)
    try:
        identity = build_repository_identity(repo_path)
    except (OSError, ValueError, RuntimeError):
        raise DreamReviewError("reviewed_repository_mismatch") from None
    if identity.repository_id != binding.repository_id:
        raise DreamReviewError("reviewed_repository_mismatch")
    current = _resolve_item(_load_report(identity.canonical_root, binding.run_key),
                            binding.run_key, binding.item_idx)
    if current.binding.candidate_fingerprint != binding.candidate_fingerprint:
        raise DreamReviewError("reviewed_candidate_changed")
    if current.binding.artifact_fingerprint != binding.artifact_fingerprint:
        raise DreamReviewError("reviewed_artifact_stale")
    return current


def resolve_reviewed_selection(repo_path: str, selection: str, encoded: str) -> list[ResolvedDreamCandidate]:
    try:
        supplied = json.loads(encoded)
        if type(supplied) is not list or not supplied:
            raise ValueError
        bindings = [DreamReviewedCandidateBinding.from_dict(value) for value in supplied]
        indexes = [binding.item_idx for binding in bindings]
        if (len(set(indexes)) != len(indexes)
                or len({binding.run_key for binding in bindings}) != 1
                or not selection):
            raise ValueError
        if selection != "all":
            selected = [int(value.strip()) for value in selection.split(",")]
            if len(selected) != len(indexes) or set(selected) != set(indexes):
                raise ValueError
    except (ValueError, TypeError):
        raise DreamReviewError("review_binding_required") from None
    # Validate the whole selection before the first item may execute.
    return [resolve_reviewed_candidate(repo_path, binding.as_dict()) for binding in bindings]
