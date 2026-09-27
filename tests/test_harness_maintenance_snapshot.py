"""The maintenance proof preserves old audit/source evidence and detects drift."""
import hashlib
import json

import pytest

from _harness_maintenance import ROOT, FIXTURE, before_harness_remediation


@pytest.mark.parametrize("path", [
    "core/pipeline.py", "core/defect_probe.py", "patching/patch_gates.py",
    "core/targeted_repository_validation.py",
])
def test_maintenance_reconstructs_history_and_refuses_unrecorded_changes(path):
    restored = before_harness_remediation(path)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    reversal = next(item for item in fixture["reversals"] if item["path"] == path)
    assert hashlib.sha256(restored).hexdigest() == reversal["pre_sha256"]
    with pytest.raises(AssertionError):
        before_harness_remediation(path, (ROOT / path).read_bytes() + b"# unexpected change")


def test_pipeline_history_matches_the_original_blackbox_audit_snapshot():
    audit = json.loads((ROOT / "docs/audits/2026-09-10-harness-blackbox-results.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(before_harness_remediation("core/pipeline.py")).hexdigest() == audit["source_sha256_after_runs"]["core/pipeline.py"]
