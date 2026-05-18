"""Phase 6.3 tests: lesson retrieval is injected into build_control_prompt
only when enabled, and never crashes the patch flow on error."""
import inspect

import pytest

import config as config_module
from core import control_engine, lesson_store


def _candidate(**overrides):
    base = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": ["src/app.py"],
        "diff_stats": {"added": 4, "removed": 2},
    }
    base.update(overrides)
    return base


def _control_result():
    """Minimal control_result that hits the normal bug-fix prompt branch."""
    return {
        "top_hypothesis": {
            "symbol": "foo",
            "likely_issue": "off-by-one",
            "confidence": 0.8,
            "recommended_action": "fix",
            "language": "python",
            "reasons": ["test reason"],
        },
        "patch_intent": {
            "language": "python",
            "source_snippet": "def foo():\n    pass\n",
            "file": "src/foo.py",
            "target_symbol": "foo",
            "target_node_kind": "function",
        },
        "preflight_validation": {},
        "related_snippets": [],
        "scout": {"request_type": "bug_fix"},
        "phantom_limb": {"findings": []},
        "patch_style": "safe_minimal",
        "code_dna_prompt": "REPO STYLE: idiomatic python",
    }


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    """Redirect lesson_store storage to tmp_path/.agent and reset flags."""
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", False)
    return tmp_path


def _save_active_lesson(*, case_name="x", title=None, summary=""):
    rec = lesson_store.save_candidate_lesson(
        _candidate(),
        source="manual",
        case_name=case_name,
        title=title,
        summary=summary,
    )
    return lesson_store.promote_lesson(rec["id"])


# --- 1. retrieval disabled ------------------------------------------------


def test_retrieval_disabled_no_lesson_block(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", False)
    _save_active_lesson(title="lesson_title_unique_disabled")

    prompt = control_engine.build_control_prompt(
        _control_result(), "fix the bug", repo_path=str(lessons_repo)
    )

    assert "[ACTIVE LESSONS" not in prompt
    assert "lesson_title_unique_disabled" not in prompt
    assert "[USER]" in prompt  # sanity: rest of prompt rendered


# --- 2. retrieval enabled, no lessons ------------------------------------


def test_retrieval_enabled_but_no_lessons_omits_block(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    # No lessons saved.

    prompt = control_engine.build_control_prompt(
        _control_result(), "fix the bug", repo_path=str(lessons_repo)
    )

    assert "[ACTIVE LESSONS" not in prompt
    assert "[USER]" in prompt


def test_retrieval_enabled_candidate_only_omits_block(lessons_repo, monkeypatch):
    """A candidate (non-promoted) lesson must not surface in the prompt."""
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    lesson_store.save_candidate_lesson(
        _candidate(), source="manual", title="candidate_title_should_not_leak"
    )

    prompt = control_engine.build_control_prompt(
        _control_result(), "anything", repo_path=str(lessons_repo)
    )

    assert "[ACTIVE LESSONS" not in prompt
    assert "candidate_title_should_not_leak" not in prompt


# --- 3. retrieval enabled with active lesson ----------------------------


def test_retrieval_enabled_with_active_lesson_includes_block(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    _save_active_lesson(
        case_name="python_off_by_one_pagination",
        title="Pagination off-by-one fix",
        summary="Fixed an off-by-one in the pagination logic",
    )

    # Query is a substring of the lesson title/summary → scoring returns it.
    prompt = control_engine.build_control_prompt(
        _control_result(),
        "off-by-one",
        repo_path=str(lessons_repo),
    )

    assert "[ACTIVE LESSONS" in prompt
    assert "advisory hints" in prompt.lower()
    assert "do not copy" in prompt.lower()
    assert "Pagination off-by-one fix" in prompt
    assert "python_off_by_one_pagination" in prompt
    # Lesson block lands between PHANTOM LIMB and USER sections.
    lessons_pos = prompt.index("[ACTIVE LESSONS")
    user_pos = prompt.index("[USER]")
    phantom_pos = prompt.index("[PHANTOM LIMB")
    assert phantom_pos < lessons_pos < user_pos


def test_retrieval_respects_max_chars(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_MAX_CHARS", 200)
    for i in range(10):
        _save_active_lesson(
            case_name=f"case_{i}",
            title=f"Lesson {i} shared_keyword",
            summary="x" * 400,
        )

    # Query matches the shared keyword in every lesson title.
    prompt = control_engine.build_control_prompt(
        _control_result(), "shared_keyword", repo_path=str(lessons_repo)
    )

    # The formatted block (between header and the next section) must be capped.
    lessons_pos = prompt.index("[ACTIVE LESSONS")
    user_pos = prompt.index("[USER]")
    block_text = prompt[lessons_pos:user_pos]
    # Header is ~280 chars; the formatted lessons body is capped at
    # max_chars=200, so the whole block is comfortably under 700.
    assert len(block_text) < 700


# --- 4. retrieval error ---------------------------------------------------


def test_retrieval_error_does_not_crash_prompt(lessons_repo, monkeypatch):
    monkeypatch.setattr(config_module, "LESSON_RETRIEVAL_ENABLED", True)

    def boom(**_kwargs):
        raise RuntimeError("simulated retrieval failure")

    monkeypatch.setattr("core.lesson_retrieval.find_active_lessons", boom)

    # Must not raise; lessons block omitted; rest of prompt intact.
    prompt = control_engine.build_control_prompt(
        _control_result(), "anything", repo_path=str(lessons_repo)
    )

    assert "[ACTIVE LESSONS" not in prompt
    assert "[USER]" in prompt
    assert "anything" in prompt


# --- 5. import isolation --------------------------------------------------


def test_control_engine_uses_only_lesson_retrieval():
    """The lesson-injection path must go through core.lesson_retrieval,
    not directly through core.lesson_store. This protects the bucket-level
    safety invariants (candidate / blocked never leaked) defined in 6.2.
    """
    src = inspect.getsource(control_engine._lessons_prompt_block)
    assert "lesson_retrieval" in src
    assert "lesson_store" not in src

    # Module-level: control_engine should never have lesson_store bound.
    # (lazy-importing lesson_retrieval inside the helper is fine.)
    assert not hasattr(control_engine, "lesson_store")
