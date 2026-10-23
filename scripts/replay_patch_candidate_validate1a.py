"""Compile unchanged frozen synthetic virtual candidates in ephemeral workspaces."""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.structural_candidate_materialization import materialize_structural_candidate
from core.structural_compile_validation import (
    FIRST_REMAINING_BLOCKER, PHASE_ID, TIMING_FIELDS,
    compile_materialized_structural_candidate, validate_structural_compile_receipt,
)
from scripts.replay_patch_candidate_materialize1 import SCENARIOS, synthetic_candidate_case


@contextmanager
def _diagnostic_guards(repository_root):
    """Permit compiler/temp lifetime; reject model/author and repository walks."""
    root = repository_root.resolve()

    def forbidden(*args, **kwargs):
        raise AssertionError("compile replay attempted model/author/network/arbitrary execution")

    def bounded_walk(original):
        def guarded(path, *args, **kwargs):
            if not isinstance(path, int):
                try:
                    Path(path).resolve().relative_to(root)
                except (TypeError, ValueError):
                    pass
                else:
                    raise AssertionError("compile replay attempted repository traversal")
            return original(path, *args, **kwargs)
        return guarded

    with ExitStack() as stack:
        for target in ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
                       "core.structural_patch_author.StructuralAuthorInvocation.run",
                       "socket.create_connection", "socket.socket.connect", "os.system"):
            stack.enter_context(patch(target, side_effect=forbidden))
        for name in ("walk", "scandir", "listdir"):
            stack.enter_context(patch("os." + name, bounded_walk(getattr(os, name))))
        yield


def replay(*, repetitions=3):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    scenarios = {}
    total_javac, total_version_probes = 0, 0
    for name in SCENARIOS:
        with tempfile.TemporaryDirectory(prefix="patch-candidate-validate1a-fixture-") as directory:
            root = Path(directory)
            scope, fresh, candidate = synthetic_candidate_case(name, root=root)
            target = root / fresh["current_context"].file
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fresh["current_source"])
            materialized = materialize_structural_candidate(candidate, admitted_scope=scope,
                repository_root=root, **fresh)
            before = (scope.to_json(), candidate.to_json(), materialized.to_json(),
                      fresh["plan"].to_json(), target.read_bytes())
            samples, fingerprints = [], []
            with _diagnostic_guards(root):
                for _ in range(repetitions):
                    timings = {}
                    receipt = compile_materialized_structural_candidate(materialized,
                        candidate=candidate, admitted_scope=scope, repository_root=root,
                        timings=timings, **fresh)
                    rebuilt = validate_structural_compile_receipt(receipt.as_dict(),
                        materialized=materialized, candidate=candidate, admitted_scope=scope,
                        repository_root=root, **fresh)
                    assert rebuilt == receipt
                    assert set(timings) == set(TIMING_FIELDS)
                    assert before == (scope.to_json(), candidate.to_json(), materialized.to_json(),
                                      fresh["plan"].to_json(), target.read_bytes())
                    assert all(not (root / file.path).exists() for file in materialized.virtual_files
                               if file.before_state == "absent")
                    samples.append(timings)
                    fingerprints.append(receipt.fingerprint)
                    total_javac += receipt.javac_invocation_count
                    total_version_probes += receipt.version_probe_count
            assert len(set(fingerprints)) == 1
            scenarios[name] = {
                "compile_receipt": receipt.as_dict(), "deterministic": True,
                "source_bytes_unchanged": True, "virtual_bytes_unchanged": True,
                "candidate_semantics_unchanged": True, "historical_plan_unchanged": True,
                "new_repository_source_created": False,
                "performance": {key: {
                    "median_ms": round(statistics.median(sample[key] for sample in samples) * 1000, 6),
                    "max_ms": round(max(sample[key] for sample in samples) * 1000, 6),
                } for key in TIMING_FIELDS},
            }
    return {
        "phase_id": PHASE_ID,
        "fixture_kind": "synthetic_frozen_MATERIALIZE1_candidates_compiled_without_revision",
        "scenarios": scenarios, "repetitions": repetitions,
        "frozen_BANK_scenario": "preserve_base_compatibility",
        "javac_invocation_count": total_javac, "version_probe_count": total_version_probes,
        "javac_total_invocation_count": total_javac + total_version_probes,
        "arbitrary_command_execution_count": 0, "model_calls": 0, "author_calls": 0,
        "repository_traversals": 0, "source_mutation": False, "virtual_source_repair": False,
        "test_generated": False, "java_code_executed": False,
        "real_BANK2_approval_consumed": False, "MainApp_session_touched": False,
        "write_authority": False, "filesystem_write_authority": False,
        "filesystem_file_creation_authority": False, "execution_authorized": False,
        "apply_authority": False,
        "first_remaining_blocker": FIRST_REMAINING_BLOCKER,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    result = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8", newline="\n")
    print(json.dumps({
        "phase_id": result["phase_id"],
        "scenarios": {name: {"status": row["compile_receipt"]["status"],
                              "diagnostics": row["compile_receipt"]["diagnostics"],
                              "performance": row["performance"]}
                      for name, row in result["scenarios"].items()},
        "javac_invocation_count": result["javac_invocation_count"],
        "version_probe_count": result["version_probe_count"],
        "javac_total_invocation_count": result["javac_total_invocation_count"],
        "first_remaining_blocker": result["first_remaining_blocker"],
    }, indent=2))
