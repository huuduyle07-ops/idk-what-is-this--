"""Synthetic frozen candidate replay; all resulting Java files remain virtual."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.structural_candidate_materialization import (
    ByteEditEvent, MaterializationError, TIMING_FIELDS, compose_byte_events,
    materialize_structural_candidate, validate_materialized_structural_candidate,
)
from core.structural_patch_author import normalize_structural_author_output
from scripts.replay_patch_author_structural1 import synthetic_case, synthetic_author_output
from scripts.replay_patch_scope_expand1 import fixture_inputs


SCENARIOS = ("preserve_base_compatibility", "savings_only_on_subclass",
             "subclass_specialization", "nested", "lf", "crlf", "packaged")
PURE_GUARDS = (
    "core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
    "core.structural_patch_author.StructuralAuthorInvocation.run",
    "socket.create_connection", "socket.socket.connect", "subprocess.run",
    "subprocess.Popen", "os.system", "os.walk", "os.scandir", "os.listdir",
    "pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.read_text",
    "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open",
)


@contextmanager
def no_materialization_effects(*, allow_exact_reads=False):
    """Fail immediately on providers, execution, traversal or filesystem writes."""
    read_targets = {"pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.read_text", "builtins.open"}
    with ExitStack() as stack:
        for target in PURE_GUARDS:
            if allow_exact_reads and target in read_targets:
                continue
            stack.enter_context(patch(target, side_effect=AssertionError("materialization attempted a forbidden effect")))
        yield


def synthetic_candidate_case(name="preserve_base_compatibility", *, root=None, source=None):
    """Normalize frozen illustrative AUTHOR.STRUCTURAL.1 text without a provider."""
    if name not in SCENARIOS:
        raise ValueError("unknown synthetic materialization scenario")
    transition = name if name in SCENARIOS[:3] else "preserve_base_compatibility"
    if name in {"lf", "crlf"} and source is None:
        source = fixture_inputs()["current_source"].decode("utf-8")
        if name == "crlf":
            source = source.replace("\n", "\r\n")
    if name == "packaged":
        import scripts.replay_patch_scope_expand1 as expand_replay
        original = expand_replay.project_class_semantic_context

        def packaged(**kwargs):
            return original(**{**kwargs, "file": "edu/bank.java"})

        source = "package edu;\n" + fixture_inputs()["current_source"].decode("utf-8")
        with patch.object(expand_replay, "project_class_semantic_context", packaged):
            scope, fresh = synthetic_case(transition, root=root, source=source, path="edu/SavingAccount.java")
    else:
        scope, fresh = synthetic_case(transition, root=root, source=source, nested=name == "nested")
    normalized = normalize_structural_author_output(admitted_scope=scope,
        author_output=synthetic_author_output(scope), **fresh)
    assert normalized.candidate is not None, (normalized.status, normalized.reason)
    return scope, fresh, normalized.candidate


def _collision(evidence):
    return replace(evidence, paths=tuple(replace(w, state="file",
        source_fingerprint=sha256(b"occupied synthetic fixture").hexdigest()) if w.state == "absent" else w
        for w in evidence.paths))


def _facade_performance(repetitions):
    """Measure actual exact reads in an isolated source fixture, never the repo."""
    with tempfile.TemporaryDirectory(prefix="patch-candidate-materialize1-") as directory:
        root = Path(directory)
        scope, fresh, candidate = synthetic_candidate_case(root=root)
        (root / "bank.java").write_bytes(fresh["current_source"])
        samples, fingerprints = [], []
        with no_materialization_effects(allow_exact_reads=True):
            for _ in range(repetitions):
                timings = {}
                result = materialize_structural_candidate(candidate, admitted_scope=scope,
                    repository_root=root, timings=timings, **fresh)
                samples.append(timings)
                fingerprints.append(result.fingerprint)
        assert len(set(fingerprints)) == 1
        assert (root / "bank.java").read_bytes() == fresh["current_source"]
        assert not (root / "SavingAccount.java").exists()
        return {"fixture_kind": "isolated_temporary_named_source_only",
            "deterministic": True, "source_bytes_unchanged": True,
            "new_file_created": False, "repository_traversals": 0,
            "performance": {k: {"median_ms": round(statistics.median(s[k] for s in samples) * 1000, 6),
                                "max_ms": round(max(s[k] for s in samples) * 1000, 6)} for k in TIMING_FIELDS}}


def replay(*, repetitions=5):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    fixtures = {name: synthetic_candidate_case(name) for name in SCENARIOS}
    results, negatives = {}, {}
    with no_materialization_effects():
        for name, (scope, fresh, candidate) in fixtures.items():
            before = scope.to_json(), candidate.to_json(), fresh["current_source"], fresh["repository_evidence"]
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                result = materialize_structural_candidate(candidate, admitted_scope=scope, timings=timings, **fresh)
                assert validate_materialized_structural_candidate(result.as_dict(), candidate=candidate,
                    admitted_scope=scope, **fresh) == result
                assert set(timings) == set(TIMING_FIELDS)
                samples.append(timings)
                fingerprints.append(result.fingerprint)
            assert len(set(fingerprints)) == 1
            assert before == (scope.to_json(), candidate.to_json(), fresh["current_source"], fresh["repository_evidence"])
            expected_files = 1 if name == "nested" else 2
            assert len(result.virtual_files) == expected_files
            for virtual in result.virtual_files:
                assert virtual.after_sha256 == sha256(virtual.after_bytes).hexdigest()
                assert virtual.after_size == len(virtual.after_bytes)
                if virtual.before_state == "absent":
                    assert virtual.before_sha256 is None and virtual.before_size is None
            results[name] = {"materialized_candidate": result.as_dict(), "deterministic": True,
                "source_bytes_unchanged": True, "candidate_semantics_unchanged": True,
                "virtual_file_count": len(result.virtual_files),
                "performance": {k: {"median_ms": round(statistics.median(s[k] for s in samples) * 1000, 6),
                                    "max_ms": round(max(s[k] for s in samples) * 1000, 6)} for k in TIMING_FIELDS}}

        scope, fresh, candidate = fixtures["preserve_base_compatibility"]
        cases = {
            "stale_source": (candidate, {"current_source": fresh["current_source"] + b"\n// stale"}, {"reacquisition_required"}),
            "occupied_new_path": (candidate, {"repository_evidence": _collision(fresh["repository_evidence"])},
                                  {"materialization_conflict_existing_path", "admission_conflict_existing_path"}),
        }
        for key, value in (("candidate_fingerprint", "forged"), ("implementation_plan_fingerprint", "forged"),
                           ("authority", "write_authority"), ("apply_authority", True)):
            payload = candidate.as_dict()
            payload[key] = value
            cases["tampered_" + key] = (payload, {}, {"candidate_stale", "author_output_authority_escalation"})
        payload = candidate.as_dict()
        next(o for o in payload["operations"] if o["operation"] == "insert_member")["source_text"] += "\nprivate int invented;"
        cases["tampered_generated_declaration"] = (payload, {}, {"author_output_outside_admitted_scope", "candidate_stale"})
        payload = candidate.as_dict()
        payload["operations"].append(deepcopy(next(o for o in payload["operations"] if o["operation"] == "draft_new_file")))
        cases["duplicate_new_file_path"] = (payload, {}, {"author_output_outside_admitted_scope", "materialization_structural_conflict"})
        for name, (payload, changes, expected) in cases.items():
            try:
                materialize_structural_candidate(payload, admitted_scope=scope, **{**fresh, **changes})
            except MaterializationError as exc:
                assert exc.code in expected, (name, exc.code)
                negatives[name] = {"status": exc.code, "authoritative_virtual_candidate": None}
            else:
                raise AssertionError((name, "unsafe materialization accepted"))

        for name, events in (
            ("overlapping_removals", (ByteEditEvent("remove1", "remove", 1, 4, b"", 0),
                                      ByteEditEvent("remove2", "remove", 3, 5, b"", 1))),
            ("insertion_inside_removed_bytes", (ByteEditEvent("remove1", "remove", 1, 5, b"", 0),
                                                ByteEditEvent("insert1", "insert", 2, 2, b"x", 1))),
        ):
            try:
                compose_byte_events(b"abcdef", events)
            except MaterializationError as exc:
                assert exc.code == "materialization_structural_conflict"
                negatives[name] = {"status": exc.code, "authoritative_virtual_candidate": None}
            else:
                raise AssertionError((name, "ambiguous event composition accepted"))

    return {"phase_id": "PATCH.CANDIDATE.MATERIALIZE.1", "fixture_kind": "synthetic_frozen_AUTHOR_STRUCTURAL1_candidates",
        "scenarios": results, "negative_cases": negatives, "repetitions": repetitions,
        "facade_performance": _facade_performance(repetitions),
        "author_calls": 0, "model_calls": 0, "repository_traversals": 0, "source_mutation": False,
        "real_BANK2_approval_consumed": False, "MainApp_session_touched": False,
        "write_authority": False, "filesystem_write_authority": False,
        "filesystem_file_creation_authority": False, "execution_authorized": False,
        "apply_authority": False, "auto_apply": False,
        "first_remaining_blocker": "STRUCTURAL_CANDIDATE_VALIDATION_NOT_IMPLEMENTED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    result = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"phase_id": result["phase_id"], "negative_cases": result["negative_cases"],
        "scenarios": {name: {"fingerprint": scenario["materialized_candidate"]["materialization_fingerprint"],
                             "virtual_file_count": scenario["virtual_file_count"], "performance": scenario["performance"]}
                      for name, scenario in result["scenarios"].items()},
        "first_remaining_blocker": result["first_remaining_blocker"]}, indent=2))
