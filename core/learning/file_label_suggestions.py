"""Read-only file label proposals with exact sampled-source evidence.

An exact quote proves its location, not that a label is semantically correct.
Nothing here writes labels, edits source files or builds a graph.
"""
from __future__ import annotations

import json
import re

from .file_labels import validate_labels
from .material_library import MaterialLibrary
from .materials import MaterialsError
from .store import LearningError

MAX_SAMPLED_UNITS = 8
MAX_EXCERPT_CHARACTERS = 1000
MAX_EVIDENCE = 12
MAX_RESPONSE_CHARACTERS = 24000
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_FIELDS = {"subject", "topics", "role", "language"}


def _invalid():
    return LearningError("label_suggestion_invalid", "Gợi ý nhãn không đúng định dạng hoặc thiếu đoạn nguồn đối chiếu. Chưa lưu nhãn nào; hãy thử lại hoặc tự nhập nhãn.", 502)


def _provider_error():
    return LearningError("label_suggestion_provider_error", "Model chưa tạo được gợi ý nhãn. Chưa lưu thay đổi nào; hãy thử lại sau.", 502)


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError("nonfinite number")


def _sample(corpus, source):
    units = [unit for unit in corpus["units"] if unit["source_id"] == source["source_id"]]
    candidates = []
    for unit in units:
        is_image = source["format"] in {"png", "jpeg"}
        note = source.get("description", {}) if is_image else {}
        content = note.get("text", "") if is_image else unit["text"]
        if not isinstance(content, str):
            raise MaterialsError("invalid_collection", "Không đọc được văn bản nguồn để gợi ý nhãn.")
        if not content.strip():
            continue
        start = len(content) - len(content.lstrip())
        item = {"unit_id": unit["unit_id"], "locator": dict(unit["locator"]),
                "text": content[start:start + MAX_EXCERPT_CHARACTERS], "origin": "user_note" if is_image else "extracted"}
        if is_image:
            item["annotation_revision"] = note["revision"]
        candidates.append(item)
    count = min(len(candidates), MAX_SAMPLED_UNITS)
    # Include both ends and spaced interior units. Blank units still count in
    # the whole-file denominator; this is a sample, never whole-file analysis.
    indices = [index * (len(candidates) - 1) // (count - 1) for index in range(count)] if count > 1 else [0] if count else []
    return [{**candidates[index], "excerpt_id": f"E{ordinal + 1}"} for ordinal, index in enumerate(indices)], len(units)


def _parse(raw, samples):
    try:
        if not isinstance(raw, str) or len(raw) > MAX_RESPONSE_CHARACTERS:
            raise ValueError("invalid response")
        raw.encode("utf-8")
        result = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
        if not isinstance(result, dict) or set(result) != {"labels", "evidence"}:
            raise ValueError("invalid schema")
        labels = validate_labels(result["labels"])
        if not isinstance(result["evidence"], list) or len(result["evidence"]) > MAX_EVIDENCE:
            raise ValueError("invalid evidence")
        by_id = {item["excerpt_id"]: item for item in samples}
        evidence = []
        for item in result["evidence"]:
            if not isinstance(item, dict) or set(item) != {"field", "excerpt_id", "quote"}:
                raise ValueError("invalid evidence schema")
            if not isinstance(item["field"], str) or item["field"] not in _FIELDS:
                raise ValueError("invalid evidence field")
            if not isinstance(item["excerpt_id"], str) or item["excerpt_id"] not in by_id:
                raise ValueError("unknown excerpt")
            quote = item["quote"]
            sample = by_id[item["excerpt_id"]]
            if not isinstance(quote, str) or not quote.strip() or len(quote) > MAX_EXCERPT_CHARACTERS or quote not in sample["text"]:
                raise ValueError("quote not in sample")
            entry = {"field": item["field"], "unit_id": sample["unit_id"], "locator": sample["locator"],
                     "text": quote, "origin": sample["origin"]}
            if "annotation_revision" in sample:
                entry["annotation_revision"] = sample["annotation_revision"]
            if entry not in evidence:
                evidence.append(entry)
        supported = {item["field"] for item in evidence}
        required = {field for field in _FIELDS if labels[field] and labels[field] != "unknown"}
        if not required <= supported:
            raise ValueError("missing supporting evidence")
        return labels, evidence
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, MaterialsError):
        raise _invalid() from None


def suggest_file_labels(library: MaterialLibrary, owner, collection_id, digest, responder):
    """Suggest labels for one owned source, without saving the model's proposal."""
    corpus = library.get(owner, collection_id)
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise MaterialsError("not_found", "Không tìm thấy file trong bộ tài liệu.")
    source = next((item for item in corpus["sources"] if item["source_id"] == "sha256:" + digest), None)
    if source is None:
        raise MaterialsError("not_found", "Không tìm thấy file trong bộ tài liệu.")
    try:
        samples, total = _sample(corpus, source)
    except (KeyError, TypeError, ValueError):
        raise MaterialsError("invalid_collection", "Không đọc được nguồn để gợi ý nhãn.") from None
    if not samples:
        raise LearningError("label_suggestion_no_text", "File chưa có văn bản đọc được để gợi ý nhãn. Với ảnh, hãy thêm ghi chú trước; hệ thống chưa tự nhận diện nội dung ảnh.", 422)
    config = responder.public_config()
    if not config.get("available"):
        raise LearningError("chat_not_configured", config.get("reason") or "Chưa cấu hình model để gợi ý nhãn.", 503)
    excerpts = [{key: sample[key] for key in ("excerpt_id", "text", "origin")} for sample in samples]
    try:
        raw = responder.classify_file(excerpts)
    except LearningError as error:
        if error.code == "chat_not_configured":
            raise LearningError("chat_not_configured", "Chưa cấu hình model để gợi ý nhãn.", 503) from None
        if error.code == "label_suggestion_invalid":
            raise _invalid() from None
        raise _provider_error() from None
    except Exception:
        raise _provider_error() from None
    labels, evidence = _parse(raw, samples)
    return {"labels": labels, "evidence": evidence, "provider": config["provider"], "model": config["model"],
            "sampled_units": len(samples), "total_units": total}
