from core.context_profiles import infer_context_profile, score_multiplier_for_path


def test_infer_context_profile_identity():
    assert infer_context_profile("what is this project?") == "identity"


def test_infer_context_profile_benchmark():
    assert infer_context_profile("why did cpp_account_interest fail?") == "benchmark"


def test_infer_context_profile_test():
    assert infer_context_profile("why does this pytest fail?") == "test"


def test_identity_profile_downweights_benchmark_case_path():
    multiplier = score_multiplier_for_path(
        "benchmarks/cases/cpp/cpp_account_interest/buggy_repo/main.cpp",
        "identity",
    )

    assert multiplier < 0.2


def test_benchmark_profile_does_not_downweight_benchmark_case_path():
    multiplier = score_multiplier_for_path(
        "benchmarks/cases/cpp/cpp_account_interest/buggy_repo/main.cpp",
        "benchmark",
    )

    assert multiplier == 1.0


def test_test_profile_does_not_downweight_tests_path():
    assert score_multiplier_for_path("tests/test_control_engine.py", "test") == 1.0


def test_identity_profile_hard_boosts_authoritative_paths():
    assert score_multiplier_for_path("README.md", "identity") >= 4.0
    assert score_multiplier_for_path("docs/ROADMAP.md", "identity") >= 3.0
    assert score_multiplier_for_path("core/handoff_notes.py", "identity") >= 3.0
    assert score_multiplier_for_path("core/lesson_retrieval.py", "identity") >= 3.0
    assert score_multiplier_for_path("web/templates/index.html", "identity") >= 3.0
