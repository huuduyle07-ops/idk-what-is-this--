from __future__ import annotations

from pathlib import Path


def test_normalizes_statement_level_cpp_patch_for_whole_function_target(tmp_path):
    from core.agent_state import AgentState
    from core.pipeline import normalize_patch_candidate_with_control_source

    source = (
        'std::string_view extract_bracket_content(std::string_view input) {\n'
        "    std::size_t open  = input.find('[');\n"
        "    std::size_t close = input.rfind(']');\n"
        "    if (open  == std::string_view::npos ||\n"
        "        close == std::string_view::npos ||\n"
        "        close <= open) {\n"
        "        return {};\n"
        "    }\n"
        "    // BUG: off-by-one - includes '[' in result and misses last char before ']'\n"
        "    return input.substr(open, close - open);\n"
        "}"
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "processor.cpp").write_text(source, encoding="utf-8")

    state = AgentState(
        interface="cli",
        mode="reviewer",
        user_input="fix string_view extraction",
        file_paths=[],
        primary_file=None,
        input_mode="project",
        language="cpp",
        task_type="bug_fix",
        repo_path=str(repo),
        json_block={
            "patch_candidate": {
                "file": "processor.cpp",
                "relative_path": "processor.cpp",
                "target_node_name": "extract_bracket_content",
                "target_node_kind": "function",
                "target_snippet": source,
                "patched_snippet": (
                    "    // Return content between brackets.\n"
                    "    return input.substr(open + 1, close - open - 1);"
                ),
            }
        },
        control_result={"patch_intent": {"source_snippet": source}},
    )

    normalize_patch_candidate_with_control_source(state)

    patch = state.json_block["patch_candidate"]
    assert patch["target_snippet"] == source
    assert patch["patched_snippet"].startswith(
        "std::string_view extract_bracket_content"
    )
    assert "close <= open" in patch["patched_snippet"]
    assert "return input.substr(open + 1, close - open - 1);" in patch["patched_snippet"]
    assert patch["patched_snippet"].rstrip().endswith("}")
    assert patch["__normalized_from_statement_level_patch"] is True


def test_executor_allows_validated_literal_mapping_patch_tagged_as_class(
    monkeypatch, tmp_path
):
    import config
    import core.executor as executor_mod
    from core.validator import ValidationRun
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    target = (
        "PROVIDER_MAP = {\n"
        '    "openai": _embed_stub,\n'
        '    "cohere": _embed_stub,\n'
        '    # BUG: "openai_v3" was added to provider_config.py but not registered here\n'
        "}\n"
    )
    (repo / "embedding_adapter.py").write_bytes(target.encode("utf-8"))
    patch = {
        "file": "embedding_adapter.py",
        "relative_path": "embedding_adapter.py",
        "target_node_name": "PROVIDER_MAP",
        "target_node_kind": "class",
        "target_snippet": target,
        "patched_snippet": (
            "PROVIDER_MAP = {\n"
            '    "openai": _embed_stub,\n'
            '    "cohere": _embed_stub,\n'
            '    "openai_v3": _embed_stub,\n'
            "}\n"
        ),
    }

    monkeypatch.setattr(config, "MUTATION_ORACLE_ENABLED", False, raising=False)
    monkeypatch.setattr(
        executor_mod,
        "run_validation_command_detailed",
        lambda command, cwd, timeout=30: ValidationRun(
            ok=True, output="ok", exit_code=0
        ),
    )

    result = Executor(str(repo)).run(
        patch,
        language="python",
        validation_command="python main.py",
    )

    assert result.success is True
    assert result.phase == "validated"
    assert '"openai_v3": _embed_stub' in (repo / "embedding_adapter.py").read_text(
        encoding="utf-8"
    )


def test_typescript_ast_patch_expands_export_modifier_before_replacement(
    monkeypatch, tmp_path
):
    import config
    import core.executor as executor_mod
    from core.validator import ValidationRun
    import patching.patch_engine as patch_engine
    from core.executor import Executor

    repo = tmp_path / "repo"
    repo.mkdir()
    source = (
        'import type { EventPayload } from "./dispatcher.ts";\n\n'
        "export function handleRefund(payload: EventPayload): number {\n"
        "  return payload.balance - payload.amount;\n"
        "}\n"
    )
    (repo / "handlers.ts").write_bytes(source.encode("utf-8"))
    node_start = source.index("function handleRefund")
    node_end = source.index("\n}", node_start) + len("\n}")

    def fake_parse(code, language):
        return {
            "symbols": [
                {
                    "kind": "function",
                    "name": "handleRefund",
                    "content": code[node_start:node_end],
                    "start": node_start,
                    "end": node_end,
                }
            ]
        }

    patch = {
        "file": "handlers.ts",
        "relative_path": "handlers.ts",
        "target_node_name": "handleRefund",
        "target_node_kind": "function",
        "target_snippet": (
            "function handleRefund(payload: EventPayload): number {\n"
            "  return payload.balance - payload.amount;\n"
            "}"
        ),
        "patched_snippet": (
            "export function handleRefund(payload: EventPayload): number {\n"
            "  return payload.balance + payload.amount;\n"
            "}"
        ),
    }

    monkeypatch.setattr(config, "MUTATION_ORACLE_ENABLED", False, raising=False)
    monkeypatch.setattr(patch_engine, "parse_code_with_treesitter", fake_parse)
    monkeypatch.setattr(
        executor_mod,
        "run_validation_command_detailed",
        lambda command, cwd, timeout=30: ValidationRun(
            ok=True, output="ok", exit_code=0
        ),
    )

    result = Executor(str(repo)).run(
        patch,
        language="typescript",
        validation_command="node --experimental-strip-types main.ts",
    )

    text = (repo / "handlers.ts").read_text(encoding="utf-8")
    assert result.success is True
    assert "export export function" not in text
    assert text.count("export function handleRefund") == 1
    assert "return payload.balance + payload.amount;" in text


def test_go_access_denied_validation_is_environment_failure():
    from core.validator import classify_validation_output

    info = classify_validation_output(
        "fork/exec C:\\Users\\Admin\\AppData\\Local\\Temp\\go-build123\\b001\\exe\\case.exe: Access is denied."
    )

    assert info["category"] == "validation_environment"


def test_windows_go_validation_uses_repo_local_build_dirs(monkeypatch, tmp_path):
    import core.validator as validator

    repo = tmp_path / "repo"
    repo.mkdir()
    calls = []

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(validator.sys, "platform", "win32")
    monkeypatch.setattr(validator, "_native_toolchain_env", lambda: None)
    monkeypatch.setattr(validator.subprocess, "run", fake_run)

    ok, output = validator.run_validation_command("go run .", cwd=str(repo))

    assert ok is True
    assert output == "ok"
    env = calls[0][1]["env"]
    go_root = repo / ".agent" / "validation_go"
    assert Path(env["GOTMPDIR"]).is_relative_to(go_root)
    assert Path(env["GOCACHE"]).is_relative_to(go_root)
