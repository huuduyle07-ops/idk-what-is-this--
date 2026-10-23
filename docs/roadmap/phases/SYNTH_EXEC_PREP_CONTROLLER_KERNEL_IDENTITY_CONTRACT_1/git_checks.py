"""Required read-only Git verification, never a target runtime subprocess probe."""
import argparse
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
parser = argparse.ArgumentParser()
parser.add_argument("--stage", choices=("before", "after"), required=True)
stage = parser.parse_args().stage
destination = OUT / ("git_" + stage + ".json")
if stage == "before" and destination.exists():
    raise AssertionError("Git baseline is immutable")
checks = [
    ("diff", ["git", "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol", "diff", "--check"]),
    ("cached", ["git", "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol", "diff", "--cached", "--check"]),
    ("status", ["git", "status", "--porcelain=v1"]),
]
result = dict(scope="Fixed read-only Git checks explicitly required by user; no runtime probe, shell, network, owner import, mutation, stash/reset/clean or target inspection.", checks={})
for name, command in checks:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    result["checks"][name] = dict(command=command, exit_code=completed.returncode,
        stdout=completed.stdout.decode("utf-8", errors="replace").splitlines(),
        stderr=completed.stderr.decode("utf-8", errors="replace").splitlines())
result["passed"] = all(item["exit_code"] == 0 for item in result["checks"].values())
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(stage=stage, passed=result["passed"], exit_codes={name: item["exit_code"] for name, item in result["checks"].items()})))
raise SystemExit(0 if result["passed"] else 1)
