from core import control_engine


def _control_result(query: str) -> dict:
    return {
        "query": query,
        "repo_path": ".",
        "context_profile": control_engine.infer_context_profile(query),
        "top_hypothesis": {
            "symbol": "README.md::project_overview",
            "likely_issue": "unknown_logic_issue",
            "confidence": 0.7,
            "recommended_action": "collect_more_evidence",
            "language": "markdown",
            "reasons": ["authoritative overview source"],
        },
        "patch_intent": {
            "language": "markdown",
            "source_snippet": "# C.A.T.T.U.S\n\nAI coding mentor workspace.",
            "file": "README.md",
            "target_symbol": "project_overview",
            "target_node_kind": "section",
        },
        "evidence": [
            {
                "symbol": "README.md::project_overview",
                "depth": 0,
                "score": 4.0,
                "risk": {"risk_level": "low", "risk_score": 0},
                "called_by": [],
                "calls": [],
                "impact": [],
            }
        ],
    }


def test_identity_human_prompt_contains_evaluation_lab_framing():
    prompt = control_engine.build_control_prompt_human(
        _control_result("what is this project?"),
        "what is this project?",
    )

    assert "Benchmarks are the evaluation lab, not the whole product" in prompt


def test_identity_human_prompt_starts_with_human_user_product_identity():
    prompt = control_engine.build_control_prompt_human(
        _control_result("what is this project?"),
        "what is this project?",
    )

    assert "Start with what the product is for a human user" in prompt


def test_identity_human_prompt_does_not_start_from_main_py():
    prompt = control_engine.build_control_prompt_human(
        _control_result("what is this project?"),
        "what is this project?",
    )

    assert "Do not start from main.py" in prompt


def test_identity_agent_prompt_contains_identity_framing():
    prompt = control_engine.build_control_prompt(
        _control_result("what is this project?"),
        "what is this project?",
        repo_path=".",
    )

    assert "Start with what the product is for a human user" in prompt
    assert "Do not start from main.py" in prompt
    assert "Benchmarks are the evaluation lab, not the whole product" in prompt


def test_benchmark_human_prompt_omits_identity_only_framing():
    prompt = control_engine.build_control_prompt_human(
        _control_result("why did cpp_account_interest fail?"),
        "why did cpp_account_interest fail?",
    )

    assert "Start with what the product is for a human user" not in prompt
    assert "Do not start from main.py" not in prompt
    assert "Benchmarks are the evaluation lab, not the whole product" not in prompt


def test_test_human_prompt_omits_identity_only_framing():
    prompt = control_engine.build_control_prompt_human(
        _control_result("why does this pytest fail?"),
        "why does this pytest fail?",
    )

    assert "Start with what the product is for a human user" not in prompt
    assert "Do not start from main.py" not in prompt
    assert "Benchmarks are the evaluation lab, not the whole product" not in prompt


def test_benchmark_agent_prompt_omits_identity_only_framing():
    prompt = control_engine.build_control_prompt(
        _control_result("why did cpp_account_interest fail?"),
        "why did cpp_account_interest fail?",
        repo_path=".",
    )

    assert "Start with what the product is for a human user" not in prompt
    assert "Do not start from main.py" not in prompt
    assert "Benchmarks are the evaluation lab, not the whole product" not in prompt


def test_test_agent_prompt_omits_identity_only_framing():
    prompt = control_engine.build_control_prompt(
        _control_result("why does this pytest fail?"),
        "why does this pytest fail?",
        repo_path=".",
    )

    assert "Start with what the product is for a human user" not in prompt
    assert "Do not start from main.py" not in prompt
    assert "Benchmarks are the evaluation lab, not the whole product" not in prompt
