"""In-memory compilation, strict JSON and source/document whitespace checks."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON value: " + value)


def main():
    sources = [ROOT / "core/synthetic_runtime_authorization_pinned_lifecycle.py",
        ROOT / "tests/test_synthetic_runtime_authorization_pinned_lifecycle.py", *OUTPUT.glob("*.py")]
    checked = {"python_compiled_in_memory": [], "strict_json_validated": [], "whitespace_checked": []}
    errors = []
    for path in sorted(set(sources)):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
            checked["python_compiled_in_memory"].append(path.relative_to(ROOT).as_posix())
        except Exception as error:
            errors.append(str(path) + ": " + str(error))
    for path in sorted(OUTPUT.glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                parse_constant=reject_constant)
            checked["strict_json_validated"].append(path.relative_to(ROOT).as_posix())
        except Exception as error:
            errors.append(str(path) + ": " + str(error))
    for path in sorted(set(sources + list(OUTPUT.glob("*.md")) + list(OUTPUT.glob("*.json")))):
        try:
            content = path.read_text(encoding="utf-8")
            bad_lines = [number for number, line in enumerate(content.splitlines(), 1)
                if line != line.rstrip(" \t")]
            if bad_lines or not content.endswith("\n"):
                errors.append(str(path) + ": trailing whitespace or missing final newline " + str(bad_lines))
            checked["whitespace_checked"].append(path.relative_to(ROOT).as_posix())
        except Exception as error:
            errors.append(str(path) + ": " + str(error))
    hash_sources = sources + [ROOT / "core/synthetic_runtime_authorization.py",
        ROOT / "core/synthetic_runtime_authorization_lifecycle.py",
        ROOT / "core/synthetic_runtime_authorization_pinned.py",
        ROOT / "core/runtime_java_pinned_provider.py",
        ROOT / "core/synthetic_read_only_reflection.py",
        ROOT / "core/synthetic_reflection_execution_admission.py",
        ROOT / "core/synthetic_reflection_execution_lifecycle.py",
        ROOT / "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json"]
    result = {"checks": checked, "errors": errors, "all_checks_passed": not errors,
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(hash_sources)) if path.is_file()}, "bytecode_written": False}
    (OUTPUT / "static_validation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_checks_passed": not errors, "errors": errors,
        "compiled_source_count": len(checked["python_compiled_in_memory"]),
        "json_file_count": len(checked["strict_json_validated"]),
        "whitespace_file_count": len(checked["whitespace_checked"])}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
