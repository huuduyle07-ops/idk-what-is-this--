"""CONTROL.FRESH.1 - the one owner of a Generate request's ``control`` field.

Generate Patch and Generate Candidates continue from a prior run's CONTROL
context.  The field has exactly three meanings, decided here and nowhere else:

* a CONTROL object is **prior CONTROL**: continuation input, handed to the
  unchanged pipeline exactly as parsed;
* the JSON literal ``null`` is a **fresh start**: the page has no run eligible
  for its repository context.  That is a legitimate first-class state, not a
  malformed one.  But every stage behind this field needs CONTROL and nothing
  here may invent it, so the request stops at the bootstrap boundary as
  ``fresh_control_required``.  Creating CONTROL for a fresh request is
  CONTROL.BOOTSTRAP.1's job;
* anything else is a **structured rejection**: ``invalid_control_request``
  when the field itself is missing, repeated or a non-canonical null, and
  ``invalid_control_json`` when the supplied value is not a CONTROL object.

Pure and deterministic: standard library only, with no files, repository,
graph, retrieval, model, network, session or clock, and it grants nothing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

CONTROL_FIELD = "control"
#: The canonical fresh form: exactly these four characters, never an empty value.
FRESH_CONTROL_WIRE = "null"

PRIOR_CONTROL = "prior_control"
FRESH_BOOTSTRAP_REQUIRED = "fresh_bootstrap_required"
REJECTED = "rejected"

FRESH_CONTROL_REQUIRED = "fresh_control_required"
INVALID_CONTROL_JSON = "invalid_control_json"
INVALID_CONTROL_REQUEST = "invalid_control_request"

FRESH_CONTROL_MESSAGE = (
    "Fresh start: this request carries no prior CONTROL context, and Generate cannot create CONTROL yet. "
    "Run CONTROL for this repository or select one of its runs, then Generate again."
)
_REJECTION_ERRORS = {
    # Unchanged wording for malformed CONTROL, so existing clients keep their message.
    INVALID_CONTROL_JSON: "Invalid control JSON",
    INVALID_CONTROL_REQUEST: "Invalid control request",
}

#: CONTROL localizes something: at least one of these must carry a value.
CONTROL_ANCHOR_FIELDS = ("top_hypothesis", "hypotheses", "patch_intent", "related_snippets")
#: The JSON shape CONTROL produces for each field the Generate pipeline reads.  Null is
#: an absent value; "objects" is an array whose items are all objects.
CONTROL_FIELD_SHAPES = {
    "query": "string",
    "repo_path": "string",
    "patch_style": "string",
    "top_hypothesis": "object",
    "patch_intent": "object",
    "scout": "object",
    "patch_candidate_state": "object",
    "preflight_validation": "object",
    "live_route": "object",
    "phantom_limb": "object",
    "hypotheses": "objects",
    "related_snippets": "objects",
}


@dataclass(frozen=True)
class ControlContext:
    """The typed CONTROL context of one Generate request."""

    state: str
    control: dict[str, Any] | None = None
    code: str | None = None
    reason: str | None = None
    field: str | None = None

    def response(self) -> dict[str, Any]:
        """The typed answer for a request that stops here (a new dict each call)."""
        if self.state == PRIOR_CONTROL:
            raise ValueError("prior CONTROL continues into the pipeline; it has no boundary answer")
        if self.state == FRESH_BOOTSTRAP_REQUIRED:
            return {
                "error": FRESH_CONTROL_MESSAGE,
                "code": FRESH_CONTROL_REQUIRED,
                "control_context": FRESH_BOOTSTRAP_REQUIRED,
            }
        answer = {"error": _REJECTION_ERRORS[self.code], "code": self.code, "reason": self.reason}
        if self.field:
            answer["field"] = self.field
        return answer


def _rejected(code: str, reason: str, field: str | None = None) -> ControlContext:
    return ControlContext(REJECTED, code=code, reason=reason, field=field)


def _non_standard_constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def _has_shape(value: Any, shape: str) -> bool:
    if value is None:
        return True
    if shape == "string":
        return isinstance(value, str)
    if shape == "object":
        return isinstance(value, dict)
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def normalize_control_values(values: list[str]) -> ControlContext:
    """Map every submitted value of the ``control`` field to one typed context."""
    values = list(values)
    if not values:
        return _rejected(INVALID_CONTROL_REQUEST, "missing")
    if len(values) > 1:
        return _rejected(INVALID_CONTROL_REQUEST, "repeated")
    text = values[0]
    if text == FRESH_CONTROL_WIRE:
        return ControlContext(FRESH_BOOTSTRAP_REQUIRED, code=FRESH_CONTROL_REQUIRED)
    if not text:
        return _rejected(INVALID_CONTROL_JSON, "empty")
    if not text.strip():
        return _rejected(INVALID_CONTROL_JSON, "whitespace_only")
    try:
        value = json.loads(text, parse_constant=_non_standard_constant)
    except (ValueError, RecursionError):
        return _rejected(INVALID_CONTROL_JSON, "malformed_json")
    if value is None:
        # JSON null in any other spelling is not the fresh form: fail closed, never guess.
        return _rejected(INVALID_CONTROL_REQUEST, "non_canonical_null")
    if not isinstance(value, dict):
        return _rejected(INVALID_CONTROL_JSON, "wrong_top_level_type")
    for name, shape in CONTROL_FIELD_SHAPES.items():
        if name in value and not _has_shape(value[name], shape):
            return _rejected(INVALID_CONTROL_JSON, "invalid_field_type", name)
    if all(value.get(name) is None for name in CONTROL_ANCHOR_FIELDS):
        return _rejected(INVALID_CONTROL_JSON, "missing_required_fields")
    return ControlContext(PRIOR_CONTROL, control=value)


def control_context_from_form(form: Any) -> ControlContext:
    """The typed CONTROL context of a Generate request form (anything with ``getlist``)."""
    return normalize_control_values(form.getlist(CONTROL_FIELD))
