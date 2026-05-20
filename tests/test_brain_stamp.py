from pathlib import Path

from core import brain_stamp


def test_brain_stamp_id_ignores_timestamp():
    first = {
        "created_at": "2026-05-20T00:00:00+00:00",
        "git_sha": "abc123",
        "git_branch": "main",
        "git_dirty_summary": "clean",
        "prompt_config_hash": "prompt-a",
        "code_dna_hash": "dna-a",
    }
    second = {
        **first,
        "created_at": "2026-05-20T00:05:00+00:00",
    }

    assert brain_stamp.compute_brain_stamp_id(first) == brain_stamp.compute_brain_stamp_id(second)


def test_brain_stamp_id_changes_when_prompt_or_dna_changes():
    base = {
        "git_sha": "abc123",
        "git_branch": "main",
        "git_dirty_summary": "clean",
        "prompt_config_hash": "prompt-a",
        "code_dna_hash": "dna-a",
    }

    prompt_changed = {**base, "prompt_config_hash": "prompt-b"}
    dna_changed = {**base, "code_dna_hash": "dna-b"}

    assert brain_stamp.compute_brain_stamp_id(base) != brain_stamp.compute_brain_stamp_id(prompt_changed)
    assert brain_stamp.compute_brain_stamp_id(base) != brain_stamp.compute_brain_stamp_id(dna_changed)


def test_collect_brain_stamp_includes_schema_version_code_dna_hash_and_id(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "main.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    def fake_run_git(_repo: Path, args: list[str], timeout: int = 5) -> str | None:
        if args == ["rev-parse", "HEAD"]:
            return "abc123"
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "main"
        if args == ["status", "--porcelain"]:
            return ""
        if args == ["diff", "--stat", "HEAD"]:
            return ""
        return None

    monkeypatch.setattr(brain_stamp, "_run_git", fake_run_git)

    first = brain_stamp.collect_brain_stamp(repo)
    second = brain_stamp.collect_brain_stamp(repo)

    assert first["schema_version"] == 2
    assert first["code_dna_hash"]
    assert first["brain_stamp_id"]
    assert first["brain_stamp_id"] == second["brain_stamp_id"]
