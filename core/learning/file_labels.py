"""Owner-scoped file labels and suggestions, separate from source/unit tags."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from .knowledge_graph import LearningKnowledgeGraph
from .material_library import MaterialLibrary, _IMPORT_LOCK
from .materials import MaterialsError, MAX_FILES

MAX_LABELS_BYTES = 512 * 1024
MAX_EVIDENCE = 12
MAX_EVIDENCE_TEXT = 1000
MAX_REVISION = 2**53 - 1
SCHEMA_VERSION = "learning-file-labels-v1"
ROLES = {"lecture", "exercises", "solutions", "reference", "syllabus", "unknown"}
LANGUAGES = {"English", "Chinese", "Korean", "Vietnamese", "Mixed", "Other", "unknown"}
_FIELDS = {"subject", "topics", "role", "language"}
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_UNSET = object()


def _invalid_labels():
    return MaterialsError("invalid_file_labels", "File labels have invalid fields or values.")


def _invalid_suggestion():
    return MaterialsError("invalid_label_suggestion", "The label suggestion does not match this file's source evidence.")


def _invalid_storage():
    return MaterialsError("invalid_storage", "Cannot read file labels safely. Check the saved metadata before trying again.")


def _label_text(value, maximum, *, empty=False):
    if (not isinstance(value, str) or len(value) > maximum * 4
            or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)):
        raise _invalid_labels()
    value = " ".join(unicodedata.normalize("NFKC", value).split())
    if (not value and not empty) or len(value) > maximum:
        raise _invalid_labels()
    return value


def validate_labels(labels):
    """Normalize the complete label object, preserving first topic spelling."""
    if (not isinstance(labels, dict) or set(labels) != _FIELDS
            or not isinstance(labels["topics"], list) or len(labels["topics"]) > 5
            or not isinstance(labels["role"], str) or labels["role"] not in ROLES
            or not isinstance(labels["language"], str) or labels["language"] not in LANGUAGES):
        raise _invalid_labels()
    subject = _label_text(labels["subject"], 120, empty=True)
    topics = {}
    for value in labels["topics"]:
        topic = _label_text(value, 80)
        topics.setdefault(topic.casefold(), topic)
    return {"subject": subject, "topics": list(topics.values()),
            "role": labels["role"], "language": labels["language"]}


def _empty_labels():
    return {"subject": "", "topics": [], "role": "unknown", "language": "unknown"}


def _default():
    return {"revision": 0, "labels": _empty_labels(), "status": "unclassified", "suggestion": None,
            "last_action": None}


def _revision(value):
    if type(value) is not int or not 0 <= value <= MAX_REVISION:
        raise MaterialsError("invalid_file_labels", "A valid file-label revision is required.")
    return value


def _strict_json(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON key")
        data[key] = value
    return data


class FileLabelStore:
    def __init__(self, library: MaterialLibrary):
        self.library = library

    def _corpus(self, owner, collection_id, digest=_UNSET):
        corpus = self.library.get(owner, collection_id)
        if digest is not _UNSET and (not isinstance(digest, str) or not _DIGEST.fullmatch(digest)
                                  or not any(s["source_id"] == "sha256:" + digest for s in corpus["sources"])):
            raise MaterialsError("not_found", "Cannot find this file in the selected collection.")
        return corpus, self.library._folder(owner, collection_id)

    @staticmethod
    def _path(folder: Path):
        path = folder / "labels.json"
        try:
            if (folder.is_symlink() or path.is_symlink() or path.resolve().parent != folder.resolve()
                    or (path.exists() and not path.is_file())):
                raise _invalid_storage()
            return path
        except OSError as error:
            raise _invalid_storage() from error

    @staticmethod
    def _suggestion(value, corpus, source_id, *, reading=False):
        try:
            required = {"labels", "evidence", "provider", "model", "sampled_units", "total_units"}
            if not isinstance(value, dict) or set(value) != required:
                raise _invalid_suggestion()
            labels = validate_labels(value["labels"])
            units = {unit["unit_id"]: unit for unit in corpus["units"] if unit["source_id"] == source_id}
            source = next(item for item in corpus["sources"] if item["source_id"] == source_id)
            if (type(value["sampled_units"]) is not int or type(value["total_units"]) is not int
                    or value["total_units"] != len(units)
                    or not 1 <= value["sampled_units"] <= min(8, value["total_units"])
                    or not isinstance(value["evidence"], list) or len(value["evidence"]) > MAX_EVIDENCE):
                raise _invalid_suggestion()
            provider = _label_text(value["provider"], 80)
            model = _label_text(value["model"], 200)
            evidence, fields, sampled, stale = [], set(), set(), False
            for item in value["evidence"]:
                keys = {"field", "unit_id", "locator", "text", "origin"}
                if (not isinstance(item, dict) or not keys <= item.keys() or item.keys() - keys - {"annotation_revision"}
                        or not isinstance(item["field"], str) or item["field"] not in _FIELDS
                        or not isinstance(item["unit_id"], str) or item["unit_id"] not in units
                        or not isinstance(item["text"], str) or not item["text"].strip()
                        or len(item["text"]) > MAX_EVIDENCE_TEXT
                        or any(unicodedata.category(c) in {"Cc", "Cs"} and c not in "\n\r\t" for c in item["text"])):
                    raise _invalid_suggestion()
                unit = units[item["unit_id"]]
                if (not isinstance(item["locator"], dict) or item["locator"] != unit["locator"]
                        or set(item["locator"]) != {"kind", "index"}
                        or not isinstance(item["locator"]["kind"], str)
                        or type(item["locator"]["index"]) is not int):
                    raise _invalid_suggestion()
                copied = {key: copy.deepcopy(item[key]) for key in keys}
                if source["format"] in {"png", "jpeg"}:
                    note = source.get("description", {})
                    actual_revision = note.get("revision", 0)
                    requested_revision = item.get("annotation_revision", actual_revision)
                    if (item["origin"] != "user_note" or type(requested_revision) is not int
                            or not 1 <= requested_revision <= actual_revision
                            or (reading and "annotation_revision" not in item)):
                        raise _invalid_suggestion()
                    if requested_revision != actual_revision:
                        if not reading:
                            raise _invalid_suggestion()
                        stale = True
                    elif item["text"] not in note.get("text", ""):
                        raise _invalid_suggestion()
                    copied["annotation_revision"] = requested_revision
                elif (item["origin"] != "extracted" or "annotation_revision" in item
                      or item["text"] not in unit["text"]):
                    raise _invalid_suggestion()
                fields.add(item["field"])
                sampled.add(item["unit_id"])
                evidence.append(copied)
            needed = {key for key in _FIELDS if labels[key] not in ("", "unknown", [])}
            if not needed <= fields or len(sampled) > value["sampled_units"]:
                raise _invalid_suggestion()
            return {"labels": labels, "evidence": evidence, "provider": provider, "model": model,
                    "sampled_units": value["sampled_units"], "total_units": value["total_units"]}, stale
        except (KeyError, TypeError, ValueError, StopIteration, UnicodeError) as error:
            raise _invalid_suggestion() from error

    def _load(self, folder, corpus):
        path = self._path(folder)
        if not path.exists():
            return {}
        try:
            with path.open("rb") as stream:
                raw = stream.read(MAX_LABELS_BYTES + 1)
            if len(raw) > MAX_LABELS_BYTES:
                raise ValueError("oversized metadata")
            data = json.loads(raw, object_pairs_hook=_strict_json)
            if (not isinstance(data, dict) or set(data) != {"schema_version", "files"}
                    or data["schema_version"] != SCHEMA_VERSION or not isinstance(data["files"], dict)
                    or len(data["files"]) > MAX_FILES):
                raise ValueError("invalid metadata")
            sources = {source["source_id"] for source in corpus["sources"]}
            records = {}
            for source_id, value in data["files"].items():
                if (source_id not in sources or not isinstance(value, dict)
                        or set(value) != {"revision", "labels", "status", "suggestion", "last_action"}
                        or _revision(value["revision"]) < 1 or value["status"] not in {"unclassified", "confirmed"}
                        or value["last_action"] not in {"labels", "suggestion"}):
                    raise ValueError("invalid file record")
                labels = validate_labels(value["labels"])
                if labels != value["labels"] or (value["status"] == "unclassified" and labels != _empty_labels()):
                    raise ValueError("invalid canonical labels")
                if value["last_action"] == "labels" and (value["status"] != "confirmed" or value["suggestion"] is not None):
                    raise ValueError("invalid human save")
                if value["last_action"] == "suggestion" and value["suggestion"] is None:
                    raise ValueError("missing suggestion")
                if value["suggestion"] is not None:
                    proposal, _ = self._suggestion(value["suggestion"], corpus, source_id, reading=True)
                    if proposal != value["suggestion"]:
                        raise ValueError("noncanonical suggestion")
                records[source_id] = value
            return records
        except (OSError, KeyError, ValueError, TypeError, UnicodeError, RecursionError) as error:
            # MaterialsError inherits ValueError: malformed saved labels,
            # evidence and revisions are storage failures, not client errors.
            raise _invalid_storage() from error

    def _write(self, folder, records):
        path = self._path(folder)
        raw = json.dumps({"schema_version": SCHEMA_VERSION, "files": records},
                         ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
        if len(raw) > MAX_LABELS_BYTES:
            raise MaterialsError("file_labels_limit", "File-label metadata exceeds its storage limit.")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=folder, prefix=".labels-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self._path(folder)
            os.replace(temporary, path)
        except OSError as error:
            raise MaterialsError("write_failed", "Could not save file labels. The previous labels were kept.") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _concepts(self, owner, collection_id, corpus):
        unit_sources = {unit["unit_id"]: unit["source_id"] for unit in corpus["units"]}
        grouped = {source["source_id"]: [] for source in corpus["sources"]}
        for concept in LearningKnowledgeGraph(self.library).concept_links(owner, collection_id):
            counts = {}
            for uid in concept["unit_ids"]:
                sid = unit_sources.get(uid)
                if sid in grouped:
                    counts[sid] = counts.get(sid, 0) + 1
            for sid, count in counts.items():
                grouped[sid].append({"label": concept["label"], "unit_count": count})
        return grouped

    def _view(self, source_id, value, corpus, concepts):
        result = {key: copy.deepcopy(value[key]) for key in ("revision", "labels", "status", "suggestion")}
        stale = self._suggestion(value["suggestion"], corpus, source_id, reading=True)[1] if value["suggestion"] is not None else False
        return {"source_id": source_id, **result, "suggestion_stale": stale,
                "concepts": copy.deepcopy(concepts.get(source_id, []))}

    def list(self, owner, collection_id):
        with _IMPORT_LOCK:
            corpus, folder = self._corpus(owner, collection_id)
            records = self._load(folder, corpus)
            concepts = self._concepts(owner, collection_id, corpus)
            return [self._view(source["source_id"], records.get(source["source_id"], _default()), corpus, concepts)
                    for source in corpus["sources"]]

    def get(self, owner, collection_id, digest):
        with _IMPORT_LOCK:
            corpus, folder = self._corpus(owner, collection_id, digest)
            records = self._load(folder, corpus)
            concepts = self._concepts(owner, collection_id, corpus)
            source_id = "sha256:" + digest
            return self._view(source_id, records.get(source_id, _default()), corpus, concepts)

    def save(self, owner, collection_id, digest, labels, expected_revision):
        return self._save(owner, collection_id, digest, labels, expected_revision, suggestion=False)

    def save_suggestion(self, owner, collection_id, digest, suggestion, expected_revision):
        return self._save(owner, collection_id, digest, suggestion, expected_revision, suggestion=True)

    def _save(self, owner, collection_id, digest, payload, expected_revision, *, suggestion):
        with _IMPORT_LOCK:
            corpus, folder = self._corpus(owner, collection_id, digest)
            _revision(expected_revision)
            source_id = "sha256:" + digest
            value = self._suggestion(payload, corpus, source_id)[0] if suggestion else validate_labels(payload)
            records = self._load(folder, corpus)
            concepts = self._concepts(owner, collection_id, corpus)
            current = records.get(source_id, _default())
            action = "suggestion" if suggestion else "labels"
            if (current["last_action"] == action and current[action] == value
                    and expected_revision in {current["revision"], current["revision"] - 1}):
                return self._view(source_id, current, corpus, concepts)
            if expected_revision != current["revision"]:
                raise MaterialsError("file_labels_conflict", "File labels changed elsewhere. Read the saved version before saving again.")
            if current["revision"] >= MAX_REVISION:
                raise MaterialsError("file_labels_limit", "File labels reached their revision limit.")
            updated = {**current, "revision": current["revision"] + 1, "last_action": action}
            if suggestion:
                updated["suggestion"] = value
            else:
                updated.update(labels=value, status="confirmed", suggestion=None)
            records[source_id] = updated
            self._write(folder, records)
            return self._view(source_id, updated, corpus, concepts)
