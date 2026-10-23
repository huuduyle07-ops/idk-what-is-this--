"""Replay BANK.2 through DETECT.2 and the frozen OOP intent UI lifecycle.

This replay intentionally stops at one unanswered, durable clarification.  It
uses an isolated exact-source fixture and never invokes patch authoring, scope
expansion, a model provider, or repository discovery.

Run from the repository root:

    python scripts/replay_oop_intent_detect2.py
    python scripts/replay_oop_intent_detect2.py --output docs/roadmap/OOP_INTENT_DETECT_2_BANK2.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.class_semantic_context import project_class_semantic_context
from core.input_understanding import understand_request
from core.oop_intent_detector import (
    AUTH_DIMENSIONS,
    SAVINGS_DIMENSIONS,
    detect_missing_future_design_contract,
)
from core.proposed_design_intent import project_proposed_design_intent
from core.repository_identity import derive_repository_id
from core.treesitter_parse import structural_definitions
from web import session_store
from web.oop_intent_adapter import admit_future_design_control_wait


BANK = """class BankAccount {
  private double balance;
  BankAccount(double opening) { this.balance = opening; }
  void deposit(double amount) { balance += amount; }
  void withdraw(double amount) { balance -= amount; }
  void saving(double rate) { balance += balance * rate; }
}"""

MAIN_APP = """class MainApp {
  public static void main(String[] args) {}
}"""

BANK2_TASK = """SavingAccount extends BankAccount.

savingBalance should belong only to SavingAccount,
because not every BankAccount needs savings state.

Using the savings functionality should depend on the user
entering the correct password.

The current code does not yet contain password/authentication support."""

FORBIDDEN_INVENTIONS = (
    "sqlite", "database", "csv", "json", "bcrypt", "sha-256", "salt",
    "jwt", "oauth", "session token", "retry limit", "lockout",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _milliseconds(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": round(statistics.median(values) * 1000, 6),
        "max_ms": round(max(values) * 1000, 6),
    }


def replay(*, repetitions: int = 100) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")

    with tempfile.TemporaryDirectory(prefix="oop-intent-detect2-bank2-") as temporary:
        fixture = Path(temporary)
        bank_path = fixture / "bank.java"
        main_path = fixture / "MainApp.java"
        bank_path.write_bytes(BANK.encode("utf-8"))
        main_path.write_bytes(MAIN_APP.encode("utf-8"))
        bank_before = bank_path.read_bytes()
        main_before = main_path.read_bytes()

        control = {
            "patch_intent": {
                "file": "bank.java",
                "relative_path": "bank.java",
                "target_symbol": "BankAccount",
                "target_node_kind": "class",
                "language": "java",
                "source_snippet": BANK,
            },
        }
        control_before = json.loads(json.dumps(control))
        original_session_file = session_store.SESSION_FILE
        session_store.SESSION_FILE = fixture / "sessions.json"
        try:
            first, first_owned = admit_future_design_control_wait(
                control=control, repo_path=str(fixture), task_text=BANK2_TASK)
            second, second_owned = admit_future_design_control_wait(
                control=control, repo_path=str(fixture), task_text=BANK2_TASK)
            sessions = session_store.load_sessions()
        finally:
            session_store.SESSION_FILE = original_session_file

        assert first_owned is second_owned is True
        assert first is not None and second is not None
        assert first["status"] == second["status"] == "waiting_for_clarification"
        assert first["clarification_kind"] == second["clarification_kind"] == "oop_intent"
        assert first["clarification_session_id"] == second["clarification_session_id"]
        assert first["patch_candidate"] is second["patch_candidate"] is None
        assert first["patch"] == second["patch"] == ""
        assert first["patch_plan"] is second["patch_plan"] is None
        assert first["patch_author_calls"] == second["patch_author_calls"] == 0
        assert all(first[key] is False for key in (
            "write_authority", "execution_authorized", "auto_apply",
            "repair_scope_authority",
        ))
        assert len(sessions) == 1
        session = sessions[0]
        assert session["status"] == "waiting_for_clarification"
        assert session["clarification_answer"] is None
        assert session["result"]["patch_candidate"] is None
        assert session["result"]["patch"] == ""
        assert session["oop_intent_gap"]["scope_expansion"] == "deferred"
        assert session["control"] == control_before == control
        assert "repair_scope" not in control
        assert bank_path.read_bytes() == bank_before
        assert main_path.read_bytes() == main_before

        raw = bank_path.read_bytes()
        source = raw.decode("utf-8")
        target = next(
            item for item in structural_definitions(source, "java")["definitions"]
            if item["kind"] == "class" and item["name"] == "BankAccount"
        )
        repository_id = derive_repository_id(fixture)
        context = project_class_semantic_context(
            raw=raw,
            language="java",
            file="bank.java",
            target=target,
            expected_source_fingerprint=_sha(raw),
            repository_id=repository_id,
        )
        contract = understand_request(BANK2_TASK)
        design = project_proposed_design_intent(contract)
        detections = [
            detect_missing_future_design_contract(
                task_contract=contract,
                design_intent=design,
                current_context=context,
                current_source=raw,
                repository_id=repository_id,
            )
            for _ in range(repetitions)
        ]
        assert all(item.status == "clarification_required" for item in detections)
        assert all(len(item.possible_intent_gaps) == 1 for item in detections)
        assert all(item.gap == detections[0].gap for item in detections)

        detection = detections[0]
        gap = detection.gap
        assert gap is not None
        expected_material = AUTH_DIMENSIONS | SAVINGS_DIMENSIONS
        assert gap.dimension == "future_design_contract"
        assert set(gap.subdimensions) == expected_material
        assert gap.question.startswith(
            "You've already specified that SavingAccount extends BankAccount")
        assert "savingBalance belongs only to SavingAccount" in gap.question
        assert "successful password verification" in gap.question
        assert "source layout" not in gap.question.casefold()
        assert 2 <= len(gap.alternatives) <= 4
        semantic_prompt = " ".join((
            gap.question, *(item.description for item in gap.alternatives)))
        assert not any(term in semantic_prompt.casefold() for term in FORBIDDEN_INVENTIONS)
        dispositions = {item.dimension: item.disposition for item in detection.assessments}
        assert dispositions["source_layout"] == "deferred_implementation"
        assert dispositions["subclass_creation_lifecycle"] == "deferred_implementation"
        assert all(dispositions[item] == "human_owned_material"
                   for item in expected_material)
        assert detection.author_calls == detection.model_calls == 0
        assert detection.repository_traversals == 0
        assert detection.patch_candidate is None and detection.patch == ""

        adapter_detection = first["oop_intent_detection"]
        adapter_gap = adapter_detection["possible_intent_gaps"][0]
        assert adapter_detection["status"] == detection.status
        assert adapter_gap["dimension"] == gap.dimension
        assert set(adapter_gap["subdimensions"]) == set(gap.subdimensions)

        timing_fields = {
            "projection_validation": "projection_validation_seconds",
            "current_vs_desired": "current_vs_desired_seconds",
            "materiality_classification": "materiality_classification_seconds",
            "gap_construction": "gap_construction_seconds",
            "total_detector": "total_seconds",
        }
        performance = {
            name: _milliseconds([getattr(item, attribute) for item in detections])
            for name, attribute in timing_fields.items()
        }
        assessments = {
            item.dimension: {
                "disposition": item.disposition,
                "reason": item.reason,
            }
            for item in detection.assessments
        }
        comparisons = [
            {
                "kind": item.kind,
                "current": item.current,
                "desired": item.desired,
                "current_provenance": item.current_provenance,
                "desired_provenance": item.desired_provenance,
                "is_defect": item.is_defect,
            }
            for item in detection.comparisons
        ]

        return {
            "phase_id": "OOP.INTENT.DETECT.2",
            "task": BANK2_TASK,
            "admission": {
                "schema_version": detection.schema_version,
                "status": detection.status,
                "gap_count": len(detection.possible_intent_gaps),
                "dimension": gap.dimension,
                "subdimensions": list(gap.subdimensions),
                "question": gap.question,
                "alternatives": [
                    {"effect": item.effect, "description": item.description}
                    for item in gap.alternatives
                ],
                "evidence_ref_count": len(gap.evidence_refs),
                "unresolved_dimension_ref_count": len(gap.unresolved_dimension_refs),
                "task_contract_fingerprint": gap.task_contract_fingerprint,
                "design_fingerprint": gap.design_fingerprint,
                "source_fingerprint": gap.source_fingerprint,
                "repository_identity_bound": gap.repository_id == repository_id,
                "comparisons": comparisons,
                "dimension_assessments": assessments,
            },
            "durable_ui": {
                "status": first["status"],
                "clarification_kind": first["clarification_kind"],
                "session_count": len(sessions),
                "session_id_reused": (
                    first["clarification_session_id"]
                    == second["clarification_session_id"]
                ),
                "clarification_answer": session["clarification_answer"],
                "candidate": first["patch_candidate"],
                "patch": first["patch"],
                "patch_plan": first["patch_plan"],
                "apply_available": False,
            },
            "ordering_and_authority": {
                "author_calls": first["patch_author_calls"],
                "scope_expansion": session["oop_intent_gap"]["scope_expansion"],
                "repair_scope_present": "repair_scope" in control,
                "write_authority": first["write_authority"],
                "execution_authorized": first["execution_authorized"],
                "auto_apply": first["auto_apply"],
                "repair_scope_authority": first["repair_scope_authority"],
            },
            "side_effects": {
                "model_calls": detection.model_calls,
                "repository_traversals": detection.repository_traversals,
                "implementation_defaults_selected": [],
                "storage_or_security_invention": False,
            },
            "integrity": {
                "bank_java_unchanged": bank_path.read_bytes() == bank_before,
                "main_app_unchanged": main_path.read_bytes() == main_before,
                "control_unchanged": control == control_before,
            },
            "performance": {
                "repetitions": repetitions,
                "provider_latency": "not_applicable",
                **performance,
            },
            "known_upstream_limit": (
                "Frozen OOP.INTENT.DESIGN.1 does not type arbitrary raw complete or "
                "partial answer clauses; DETECT.2 rejects altered projection payloads and "
                "returns projection_bounded for those raw fixtures until a typed answer "
                "continuation exists."
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=100)
    arguments = parser.parse_args()
    rendered = json.dumps(
        replay(repetitions=arguments.repetitions),
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    )
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
