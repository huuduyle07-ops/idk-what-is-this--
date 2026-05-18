from types import SimpleNamespace

from agents.model_stats import (
    ModelStatsScope,
    build_usage_report,
    record_model_call,
    summarize,
    usage_from_gemini_response,
    usage_from_ollama_response,
)


def test_record_model_call_estimates_gemini_cost():
    with ModelStatsScope() as stats:
        record_model_call(
            "gemini-2.5-flash-lite",
            success=True,
            role="draft",
            provider="google",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )

    assert stats[0]["estimated_cost_usd"] == 0.5
    assert stats[0]["cost_rates_per_1m"] == {"input": 0.1, "output": 0.4}

    summary = summarize(stats)
    assert summary["input_tokens"] == 1_000_000
    assert summary["output_tokens"] == 1_000_000
    assert summary["total_tokens"] == 2_000_000
    assert summary["estimated_cost_usd"] == 0.5
    assert summary["costed_calls"] == 1


def test_gemini_usage_counts_thinking_tokens_as_output():
    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=20,
            thoughts_token_count=5,
            total_token_count=125,
        )
    )

    usage = usage_from_gemini_response(response)

    assert usage == {
        "input_tokens": 100,
        "output_tokens": 25,
        "thinking_tokens": 5,
        "total_tokens": 125,
    }


def test_ollama_usage_is_zero_cost_for_local_model():
    with ModelStatsScope() as stats:
        record_model_call(
            "deepseek-r1:1.5b",
            success=True,
            role="local_critic",
            provider="local",
            usage=usage_from_ollama_response(
                {"prompt_eval_count": 12, "eval_count": 8}
            ),
        )

    assert stats[0]["input_tokens"] == 12
    assert stats[0]["output_tokens"] == 8
    assert stats[0]["estimated_cost_usd"] == 0.0
    assert summarize(stats)["estimated_cost_usd"] == 0.0


def test_usage_report_includes_per_call_details():
    with ModelStatsScope() as stats:
        record_model_call(
            "gemini-3-flash-preview",
            success=True,
            role="draft",
            provider="google",
            usage={"input_tokens": 10, "output_tokens": 5},
        )

    report = build_usage_report(stats)

    assert report["summary"]["attempts"] == 1
    assert report["calls"][0]["call"] == 1
    assert report["calls"][0]["model"] == "gemini-3-flash-preview"
