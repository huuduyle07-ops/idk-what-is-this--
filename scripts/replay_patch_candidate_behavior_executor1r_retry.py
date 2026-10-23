"""Record the additive EXECUTOR.1R retry without changing historical evidence."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def replay():
    from tests._preflight_runtime1_guard import no_runtime_effects
    with no_runtime_effects(strict=True) as effects:
        with patch("threading.Thread.start", side_effect=effects.deny("threading.Thread.start")):
            from core.behavioral_diagnostic_executor_retry import verify
            report = verify()
        if effects.denied_attempts:
            raise AssertionError("retry attempted a runtime effect")
        report["effect_denial"] = {"strict": True,
            "denied_attempts": dict(effects.denied_attempts),
            "controller_thread_start_attempts": 0}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = replay()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps({key: report[key] for key in (
        "phase_id", "status", "reason", "synthetic_runtime_authorizations_issued",
        "shared_authorization_coherence", "synthetic_runtime_authorizations_consumed",
        "synthetic_behavioral_execution_count", "bank_execution_count",
        "positive_runtime_receipt_issued", "effect_denial")}, indent=2, sort_keys=True))
