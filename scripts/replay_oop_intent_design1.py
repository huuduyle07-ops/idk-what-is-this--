"""Replay only BANK.2's task-semantic projection; never run authoring or UI.

Run from the repository root: python scripts/replay_oop_intent_design1.py
"""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.input_understanding import understand_request
from core.proposed_design_intent import project_proposed_design_intent


BANK2_TASK = """SavingAccount extends BankAccount.

savingBalance should belong only to SavingAccount,
because not every BankAccount needs savings state.

Using the savings functionality should depend on the user
entering the correct password.

The current code does not yet contain password/authentication support."""


def replay() -> dict:
    contract = understand_request(BANK2_TASK)
    projection = project_proposed_design_intent(contract)
    assert contract.raw_request.text == BANK2_TASK
    assert projection.status == "resolved"
    assert [(item.child, item.parent) for item in projection.relationships] == [
        ("SavingAccount", "BankAccount")]
    assert [(item.state, item.owner, item.ownership_constraint, item.base_exclusion)
            for item in projection.state_commitments] == [
        ("savingBalance", "SavingAccount", "subclass_only", "BankAccount")]
    assert [(item.gated_behavior, item.condition) for item in projection.behavior_gates] == [
        ("savings functionality", "successful_password_verification")]
    assert [item.subject for item in projection.explicit_absences] == ["authentication_support"]
    assert len(projection.unresolved_dimensions) == 11

    durations = []
    for _ in range(100):
        started = perf_counter()
        repeated = project_proposed_design_intent(contract)
        durations.append((perf_counter() - started) * 1000)
        assert repeated.fingerprint == projection.fingerprint
    return {
        "phase_id": "OOP.INTENT.DESIGN.1",
        "task": BANK2_TASK,
        "preservation": contract.preservation.status,
        "projection": projection.as_dict(),
        "projection_fingerprint": projection.fingerprint,
        "projection_bytes": len(projection.to_json().encode("utf-8")),
        "performance": {
            "repetitions": 100,
            "projection_median_ms": round(statistics.median(durations), 3),
            "projection_max_ms": round(max(durations), 3),
        },
        "model_calls_added": 0,
        "author_calls": 0,
        "repository_traversal_delta": 0,
        "authority_delta": 0,
        "repair_scope_delta": 0,
        "implementation_defaults_selected": [],
        "clarification_sessions_created": 0,
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, ensure_ascii=False, sort_keys=True))
