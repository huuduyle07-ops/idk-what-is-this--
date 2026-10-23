"""Synthetic stored-answer dogfood. Never open or consume real waiting sessions."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.design_intent_continuation import continue_design_intent, compose_effective_design
from core.input_understanding import understand_request
from core.oop_intent_detector import detect_missing_future_design_contract
from core.oop_intent_session import bind_human_answer
from core.proposed_design_intent import project_proposed_design_intent
from core.repository_identity import derive_repository_id
from scripts.replay_oop_intent_detect2 import BANK, BANK2_TASK, MAIN_APP
from web import session_store
from web.oop_intent_adapter import admit_future_design_control_wait, _context_from_raw
from web.oop_intent_continuation import project_stored_oop_answer

AUTH = ("For this exercise, let SavingAccount own a simple password in memory.\n"
        "It does not need to persist across runs.\n"
        "Verify it when a savings operation is requested.")
SAVINGS = ("savingBalance should receive money transferred from the inherited balance,\n"
           "and interest should apply only to savingBalance.")
ANSWERS = {"complete": AUTH + "\n\n" + SAVINGS, "auth_only": AUTH,
           "savings_only": SAVINGS, "persistent_auth": "Credentials must persist across runs."}


def replay(repetitions=30):
    if repetitions < 1:
        raise ValueError("positive repetitions required")
    samples, cases = [], {}

    def forbidden(*args, **kwargs):
        raise AssertionError("continuation attempted provider, traversal, or execution")

    with tempfile.TemporaryDirectory(prefix="oop-continue1-synthetic-") as directory:
        root = Path(directory)
        for name, text in ANSWERS.items():
            repo = root / name
            repo.mkdir()
            raw = BANK.encode()
            (repo / "bank.java").write_bytes(raw)
            (repo / "MainApp.java").write_bytes(MAIN_APP.encode())
            control = {"patch_intent": {"file": "bank.java", "target_symbol": "BankAccount"}}
            with patch.object(session_store, "SESSION_FILE", repo / "synthetic_sessions.json"):
                waiting, _ = admit_future_design_control_wait(
                    control=control, task_text=BANK2_TASK, repo_path=str(repo))
                sid = waiting["clarification_session_id"]
                session = session_store.find_session(sid)
                gap = session["oop_intent_gap"]
                answer = bind_human_answer(gap, text).as_dict()
                session_store.update_oop_intent_wait(sid,
                    status="clarification_supplied_pending_projection", answer=answer)
                with ExitStack() as guard:
                    for target in ("os.walk", "os.scandir", "socket.create_connection", "subprocess.run",
                                   "core.semantic_waiter_adapter.SemanticWaiterModelAdapter._complete"):
                        guard.enter_context(patch(target, forbidden))
                    result = project_stored_oop_answer(sid)
                    assert result["status"] == "clarification_projected", result
                    assert project_stored_oop_answer(sid) == result
                    contract = understand_request(BANK2_TASK)
                    base = project_proposed_design_intent(contract)
                    before = base.as_dict()
                    rid = derive_repository_id(repo)
                    context = _context_from_raw(raw=raw, path="bank.java", design=base,
                                                repository_id=rid, target_symbol="BankAccount")
                    source_facts = context.as_dict()
                    for _ in range(repetitions):
                        start = perf_counter()
                        timings = {}
                        continuation = continue_design_intent(
                            task_contract=contract, base_design=base, stored_gap=gap,
                            stored_answer=answer, current_context=context, current_source=raw,
                            repo_path=str(repo), timings=timings)
                        tick = perf_counter()
                        effective = compose_effective_design(base, continuation)
                        effective.as_dict()
                        timings["effective_projection_seconds"] = perf_counter()-tick
                        tick = perf_counter()
                        detection = detect_missing_future_design_contract(
                            task_contract=contract, design_intent=effective, current_context=context,
                            current_source=raw, repository_id=rid, repo_path=str(repo),
                            stored_gap=gap, stored_answer=answer)
                        timings["detection_reentry_seconds"] = perf_counter()-tick
                        timings["total_seconds"] = perf_counter()-start
                        samples.append(timings)
                    assert base.as_dict() == before and context.as_dict() == source_facts
                stored = session_store.find_session(sid)
                assert len(session_store.load_sessions()) == 1
                assert (repo / "bank.java").read_bytes() == raw
                assert (repo / "MainApp.java").read_bytes() == MAIN_APP.encode()
                assert not (repo / "SavingAccount.java").exists()
                assert "repair_scope" not in control
                cases[name] = {
                    "stored_answer": answer, "session_events": stored["events"],
                    "session_count": 1, "retry_idempotent": True,
                    "continuation": continuation.as_dict(),
                    "base_fingerprint": base.fingerprint, "effective_fingerprint": effective.fingerprint,
                    "detection_status": detection.status,
                    "remaining_dimensions": list(detection.gap.subdimensions) if detection.gap else [],
                    "question": detection.gap.question if detection.gap else None,
                    "gap_count": len(detection.possible_intent_gaps),
                    "first_remaining_blocker": result["first_remaining_blocker"],
                    "exact_source_unchanged": True, "current_context_unchanged": True,
                    "no_saving_account_file": True, "scope_expansion": False,
                }
        assert cases["complete"]["detection_status"] == "no_gap"
        assert cases["auth_only"]["remaining_dimensions"] == ["savings_funding_semantics", "savings_interest_semantics"]
        assert len(cases["savings_only"]["remaining_dimensions"]) == 5
        assert "credential_persistence" not in cases["persistent_auth"]["remaining_dimensions"]
    return {
        "phase_id": "OOP.INTENT.CONTINUE.1", "fixture_kind": "synthetic_answer_records_only",
        "real_waiting_answer_consumed": False, "cases": cases,
        "performance": {"samples": len(samples), "provider_latency": "not_applicable",
            **{key: {"median_ms": round(statistics.median(s[key] for s in samples)*1000, 6),
                     "max_ms": round(max(s[key] for s in samples)*1000, 6)} for key in samples[0]}},
        "authority": {"write_authority": False, "execution_authorized": False,
                      "auto_apply": False, "repair_scope_authority": False},
        "author_calls": 0, "model_calls": 0, "repository_traversals": 0, "candidate": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=30)
    args = parser.parse_args()
    report = replay(args.repetitions)
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(json.dumps({"cases": {k: v["detection_status"] for k,v in report["cases"].items()},
                      "performance": report["performance"]}, indent=2))
