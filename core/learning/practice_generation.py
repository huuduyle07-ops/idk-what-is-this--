"""Generate reviewable practice from a pinned, explicitly selected source scope.

Exact quotes establish provenance, not the semantic correctness of a question or
answer. This module does not save practice, grade learners or execute code.
"""
from __future__ import annotations

import copy
import json
import re
import unicodedata

from .materials import MaterialsError
from .store import LearningError

MAX_UNITS = 8
MAX_EXCERPT_CHARACTERS = 1000
MAX_RESPONSE_CHARACTERS = 32000
_COLLECTION = re.compile(r"[a-f0-9]{32}\Z")
_UNIT = re.compile(r"unit-[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"sha256:[a-f0-9]{64}\Z")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}\Z")
_QUESTION_KEYS = {"objective", "question", "options", "correct_option", "explanation", "hints", "evidence"}
_SOURCE_KEYS = {"unit_id", "source_id", "source_name", "locator", "text", "origin"}


def _invalid_input():
    return LearningError("invalid_practice_input", "Chọn 1–8 phần nguồn hợp lệ và từ 3–5 câu hỏi.", 400)


def _invalid():
    return LearningError("practice_invalid", "Bộ câu hỏi chưa đúng định dạng hoặc thiếu đoạn nguồn đối chiếu. Chưa thể bắt đầu luyện tập; hãy thử lại hoặc chọn nguồn rõ hơn.", 502)


def _provider_error():
    return LearningError("practice_provider_error", "Model chưa tạo được bộ câu hỏi. Hãy kiểm tra kết nối hoặc thử lại sau.", 502)


def _text(value, maximum, *, single_line=False):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("invalid text")
    value.encode("utf-8")
    if any(unicodedata.category(char) == "Cc" and (single_line or char not in "\n\r\t") for char in value):
        raise ValueError("invalid control character")
    return value


def _identity(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError("invalid identity")


def _selection(unit_ids, count):
    if type(count) is not int or not 3 <= count <= 5:
        raise ValueError("invalid count")
    if not isinstance(unit_ids, list) or not 1 <= len(unit_ids) <= MAX_UNITS:
        raise ValueError("invalid units")
    for unit_id in unit_ids:
        _identity(unit_id, _UNIT)
    if len(set(unit_ids)) != len(unit_ids):
        raise ValueError("duplicate unit")


def validate_prepared_practice(prepared):
    """Validate/copy a server-owned snapshot; this does not authorize its owner."""
    try:
        if not isinstance(prepared, dict) or set(prepared) != {"scope", "excerpts"}:
            raise ValueError("invalid prepared scope")
        scope = prepared["scope"]
        if not isinstance(scope, dict) or set(scope) != {"collection_id", "collection_title", "unit_ids", "count"}:
            raise ValueError("invalid scope")
        _identity(scope["collection_id"], _COLLECTION)
        _text(scope["collection_title"], 200, single_line=True)
        _selection(scope["unit_ids"], scope["count"])
        excerpts = prepared["excerpts"]
        if not isinstance(excerpts, list) or len(excerpts) != len(scope["unit_ids"]):
            raise ValueError("invalid excerpts")
        for index, excerpt in enumerate(excerpts):
            if not isinstance(excerpt, dict):
                raise ValueError("invalid excerpt")
            expected = _SOURCE_KEYS | {"excerpt_id"}
            if excerpt.get("origin") == "user_note":
                expected |= {"annotation_revision"}
                if type(excerpt.get("annotation_revision")) is not int or excerpt["annotation_revision"] < 1:
                    raise ValueError("invalid note revision")
            elif excerpt.get("origin") != "extracted":
                raise ValueError("invalid origin")
            if set(excerpt) != expected or excerpt["excerpt_id"] != f"E{index + 1}" or excerpt["unit_id"] != scope["unit_ids"][index]:
                raise ValueError("invalid excerpt identity")
            _identity(excerpt["source_id"], _SOURCE)
            _text(excerpt["source_name"], 500, single_line=True)
            _text(excerpt["text"], MAX_EXCERPT_CHARACTERS)
            locator = excerpt["locator"]
            if (not isinstance(locator, dict) or set(locator) != {"kind", "index"}
                    or locator["kind"] not in ("page", "slide", "paragraph", "table", "image")
                    or type(locator["index"]) is not int or locator["index"] < 1):
                raise ValueError("invalid locator")
            if (excerpt["origin"] == "user_note") != (locator["kind"] == "image"):
                raise ValueError("image source mismatch")
        return copy.deepcopy(prepared)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise _invalid_input() from None


def prepare_practice(library, owner, collection_id, unit_ids, count):
    """Read owned units once, before reservation; retain their exact source text."""
    corpus = library.get(owner, collection_id)
    try:
        _selection(unit_ids, count)
    except (ValueError, TypeError):
        raise _invalid_input() from None
    try:
        units = {unit["unit_id"]: unit for unit in corpus["units"]}
        sources = {source["source_id"]: source for source in corpus["sources"]}
        if any(unit_id not in units for unit_id in unit_ids):
            raise _invalid_input()
        excerpts = []
        for index, unit_id in enumerate(unit_ids):
            unit = units[unit_id]
            source = sources[unit["source_id"]]
            is_image = source["format"] in {"png", "jpeg"}
            note = source.get("description", {}) if is_image else {}
            content = note.get("text", "") if is_image else unit["text"]
            if not isinstance(content, str):
                raise ValueError("invalid source text")
            if not content.strip():
                raise LearningError("practice_no_text", "Một phần nguồn đã chọn chưa có văn bản đọc được. Hãy bỏ chọn phần đó hoặc thêm ghi chú đã lưu cho ảnh; hệ thống chưa tự nhận diện ảnh.", 422)
            start = len(content) - len(content.lstrip())
            excerpt = {"excerpt_id": f"E{index + 1}", "unit_id": unit_id,
                       "source_id": source["source_id"], "source_name": source["original_names"][0],
                       "locator": copy.deepcopy(unit["locator"]), "text": content[start:start + MAX_EXCERPT_CHARACTERS],
                       "origin": "user_note" if is_image else "extracted"}
            if is_image:
                excerpt["annotation_revision"] = note["revision"]
            excerpts.append(excerpt)
        prepared = {"scope": {"collection_id": corpus["id"], "collection_title": corpus["title"],
                              "unit_ids": list(unit_ids), "count": count}, "excerpts": excerpts}
    except (KeyError, TypeError, ValueError, IndexError):
        raise MaterialsError("invalid_collection", "Không đọc được những phần nguồn đã chọn để tạo câu hỏi.") from None
    return validate_prepared_practice(prepared)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite number")


def _canonical(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _same_snapshot(actual, expected):
    # Python considers 1, 1.0 and True equal; source identities and revisions
    # must preserve their JSON types as well as their values.
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(_same_snapshot(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same_snapshot(left, right) for left, right in zip(actual, expected))
    return actual == expected


def _questions(data, prepared):
    if not isinstance(data, dict) or set(data) != {"title", "questions"}:
        raise ValueError("invalid model schema")
    title = _text(data["title"], 160).strip()
    questions = data["questions"]
    if not isinstance(questions, list) or len(questions) != prepared["scope"]["count"]:
        raise ValueError("wrong question count")
    by_id = {excerpt["excerpt_id"]: excerpt for excerpt in prepared["excerpts"]}
    seen, result = set(), []
    for index, question in enumerate(questions):
        if not isinstance(question, dict) or set(question) != _QUESTION_KEYS:
            raise ValueError("invalid question schema")
        item = {"id": f"q{index + 1}"}
        for field, maximum in (("objective", 160), ("question", 600), ("explanation", 1000)):
            item[field] = _text(question[field], maximum).strip()
        normalized_question = _canonical(item["question"])
        if normalized_question in seen:
            raise ValueError("duplicate question")
        seen.add(normalized_question)
        options = question["options"]
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError("invalid options")
        item["options"] = []
        for position, option in enumerate(options):
            if not isinstance(option, dict) or set(option) != {"id", "text"} or option["id"] != "abcd"[position]:
                raise ValueError("invalid option")
            item["options"].append({"id": option["id"], "text": _text(option["text"], 240).strip()})
        if len({_canonical(option["text"]) for option in item["options"]}) != 4:
            raise ValueError("duplicate option")
        if question["correct_option"] not in ("a", "b", "c", "d"):
            raise ValueError("invalid answer")
        item["correct_option"] = question["correct_option"]
        hints = question["hints"]
        if not isinstance(hints, list) or len(hints) != 2:
            raise ValueError("invalid hints")
        item["hints"] = [_text(hint, 240).strip() for hint in hints]
        evidence = question["evidence"]
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 2:
            raise ValueError("missing or oversized evidence")
        item["evidence"] = []
        for reference in evidence:
            if not isinstance(reference, dict) or set(reference) != {"excerpt_id", "quote"}:
                raise ValueError("invalid evidence schema")
            if not isinstance(reference["excerpt_id"], str) or reference["excerpt_id"] not in by_id:
                raise ValueError("unknown excerpt")
            excerpt = by_id[reference["excerpt_id"]]
            quote = _text(reference["quote"], 600)
            if quote not in excerpt["text"]:
                raise ValueError("invented source quote")
            entry = {key: copy.deepcopy(value) for key, value in excerpt.items() if key != "excerpt_id"}
            entry["text"] = quote
            if entry in item["evidence"]:
                raise ValueError("duplicate evidence")
            item["evidence"].append(entry)
        result.append(item)
    return {"title": title, "questions": result}


def validate_practice_bundle(bundle, prepared):
    """Recheck a saved/result bundle against the originally reserved snapshots."""
    prepared = validate_prepared_practice(prepared)
    try:
        if not isinstance(bundle, dict) or set(bundle) != {"title", "questions", "scope", "provider", "model"}:
            raise ValueError("invalid bundle")
        if not _same_snapshot(bundle["scope"], prepared["scope"]) or bundle["provider"] not in ("ollama", "gemini"):
            raise ValueError("changed scope or provider")
        _identity(bundle["model"], _MODEL)
        if not isinstance(bundle["questions"], list) or len(bundle["questions"]) != prepared["scope"]["count"]:
            raise ValueError("invalid questions")
        by_unit = {excerpt["unit_id"]: excerpt for excerpt in prepared["excerpts"]}
        raw_questions = []
        for index, question in enumerate(bundle["questions"]):
            if not isinstance(question, dict) or set(question) != _QUESTION_KEYS | {"id"} or question["id"] != f"q{index + 1}":
                raise ValueError("invalid question identity")
            raw = {key: copy.deepcopy(value) for key, value in question.items() if key not in {"id", "evidence"}}
            if not isinstance(question["evidence"], list) or not 1 <= len(question["evidence"]) <= 2:
                raise ValueError("invalid evidence")
            raw["evidence"] = []
            for evidence in question["evidence"]:
                if not isinstance(evidence, dict) or not isinstance(evidence.get("unit_id"), str) or evidence["unit_id"] not in by_unit:
                    raise ValueError("unknown evidence")
                excerpt = by_unit[evidence["unit_id"]]
                expected = {key: value for key, value in excerpt.items() if key != "excerpt_id"}
                expected["text"] = evidence.get("text")
                if not _same_snapshot(evidence, expected):
                    raise ValueError("source snapshot changed")
                raw["evidence"].append({"excerpt_id": excerpt["excerpt_id"], "quote": evidence["text"]})
            raw_questions.append(raw)
        validated = _questions({"title": bundle["title"], "questions": raw_questions}, prepared)
        return {**validated, "scope": copy.deepcopy(prepared["scope"]), "provider": bundle["provider"], "model": bundle["model"]}
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise _invalid() from None


def generate_prepared_practice(prepared, responder):
    """Call one model with pinned excerpts; never refresh sources after claiming."""
    prepared = validate_prepared_practice(prepared)
    config = responder.public_config()
    if not config.get("available"):
        raise LearningError("chat_not_configured", "Chưa cấu hình model để tạo bộ câu hỏi.", 503)
    excerpts = [{key: excerpt[key] for key in ("excerpt_id", "text", "origin")} for excerpt in prepared["excerpts"]]
    try:
        raw = responder.generate_practice(excerpts, count=prepared["scope"]["count"])
    except LearningError as error:
        if error.code == "chat_not_configured":
            raise LearningError("chat_not_configured", "Chưa cấu hình model để tạo bộ câu hỏi.", 503) from None
        if error.code == "practice_invalid":
            raise _invalid() from None
        raise _provider_error() from None
    except Exception:
        raise _provider_error() from None
    try:
        _text(raw, MAX_RESPONSE_CHARACTERS)
        data = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite)
        bundle = {**_questions(data, prepared), "scope": prepared["scope"], "provider": config["provider"], "model": config["model"]}
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise _invalid() from None
    return validate_practice_bundle(bundle, prepared)


def generate_practice(library, owner, collection_id, unit_ids, count, responder):
    return generate_prepared_practice(prepare_practice(library, owner, collection_id, unit_ids, count), responder)
