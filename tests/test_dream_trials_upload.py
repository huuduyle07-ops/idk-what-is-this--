"""Phase 4.7e-c — Dream trial markdown upload route.

Browsers don't expose full filesystem paths from a file picker, so the
Dream UI was effectively broken whenever the user picked / dropped a
markdown file that lived outside the repo: the backend would receive only
the bare filename, fail to resolve it, and mark every reference as
`missing`. This route lets the frontend pre-upload the file to a sandboxed
spot under `.agent/<tag>/dream_trials_uploads/` so the trial creator can
load its content like any other in-repo markdown reference.

Hard rules for this slice:
- Only `.md` / `.markdown` files are accepted.
- Filename is sanitized; no traversal, no directory parts.
- Upload size capped (5 MiB).
- No model API calls. No subprocess. No URL fetching.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from core import dream_trials


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    # Clear any prior uploads under the shared `repo-<empty-hash>` project tag.
    uploads_root = dream_trials._uploads_root(str(r))
    if uploads_root.exists():
        for f in uploads_root.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            uploads_root.rmdir()
        except OSError:
            pass
    yield r


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_upload_route_saves_markdown_and_returns_path(client, repo):
    resp = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(repo),
            "file": (io.BytesIO(b"# pilot notes\n\nlatency dropped 40%."), "pilot.md"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    saved = Path(body["path"])
    assert saved.is_file(), saved
    assert saved.read_text(encoding="utf-8") == "# pilot notes\n\nlatency dropped 40%."
    # The saved name preserves the user's filename stem.
    assert "pilot" in saved.name
    assert saved.suffix == ".md"


def test_upload_returned_path_is_loadable_by_trial(client, repo):
    """The saved path must round-trip through create_structured_dream_trial:
    when used as a markdown_files entry, the file content lands in evidence.
    """
    upload_resp = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(repo),
            "file": (io.BytesIO(b"NEEDLE_FROM_UPLOAD_X42"), "evidence.md"),
        },
        content_type="multipart/form-data",
    )
    saved_path = upload_resp.get_json()["path"]

    result = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="reference_study",
        action_level="report_only",
        title="upload round-trip",
        markdown_files=[saved_path],
    )
    data = json.loads(Path(result.trial_path).read_text(encoding="utf-8"))
    details = data["markdown_file_details"]
    assert details[0]["status"] == "loaded", details
    evidence_blob = "\n".join(data["reference_study"]["evidence"])
    assert "NEEDLE_FROM_UPLOAD_X42" in evidence_blob


def test_two_uploads_with_same_name_get_distinct_saved_names(client, repo):
    """Repeated uploads of the same filename must not clobber each other —
    each upload gets a fresh saved path so older trials keep working."""
    first = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(repo),
            "file": (io.BytesIO(b"first"), "notes.md"),
        },
        content_type="multipart/form-data",
    ).get_json()
    second = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(repo),
            "file": (io.BytesIO(b"second"), "notes.md"),
        },
        content_type="multipart/form-data",
    ).get_json()
    assert first["path"] != second["path"]
    assert Path(first["path"]).read_text(encoding="utf-8") == "first"
    assert Path(second["path"]).read_text(encoding="utf-8") == "second"


# ---------------------------------------------------------------------------
# Validation / rejection
# ---------------------------------------------------------------------------

def test_upload_rejects_missing_repo_path(client, repo):
    resp = client.post(
        "/dream/trials/upload-markdown",
        data={"file": (io.BytesIO(b"x"), "x.md")},
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert body["ok"] is False
    assert "repo_path" in body["error"]


def test_upload_rejects_missing_file(client, repo):
    resp = client.post(
        "/dream/trials/upload-markdown",
        data={"repo_path": str(repo)},
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert body["ok"] is False
    assert "file" in body["error"].lower()


def test_upload_rejects_non_markdown_extension(client, repo):
    resp = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(repo),
            "file": (io.BytesIO(b"executable"), "evil.exe"),
        },
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert body["ok"] is False
    # The error message names the accepted extensions.
    assert ".md" in body["error"]


@pytest.mark.parametrize("traversal_name", [
    "../etc/passwd.md",
    "..\\windows\\system32.md",
    "sub/dir/notes.md",
    "/absolute/path/notes.md",
])
def test_upload_strips_path_components_from_filename(client, repo, traversal_name):
    resp = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(repo),
            "file": (io.BytesIO(b"x"), traversal_name),
        },
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    # Either rejected outright OR sanitized — but the saved path must stay
    # inside the uploads root.
    if body.get("ok"):
        saved = Path(body["path"])
        uploads_root = dream_trials._uploads_root(str(repo)).resolve()
        saved.resolve().relative_to(uploads_root)  # raises if escapes
        # And the saved name carries no traversal sequences.
        assert ".." not in saved.name
        assert "/" not in saved.name
        assert "\\" not in saved.name


def test_upload_rejects_file_above_size_cap(client, repo):
    # 6 MiB > 5 MiB cap.
    big = b"x" * (6 * 1024 * 1024)
    resp = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(repo),
            "file": (io.BytesIO(big), "big.md"),
        },
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert body["ok"] is False
    assert "too large" in body["error"].lower() or "size" in body["error"].lower()


def test_upload_rejects_bad_repo_path(client, tmp_path):
    resp = client.post(
        "/dream/trials/upload-markdown",
        data={
            "repo_path": str(tmp_path / "does-not-exist"),
            "file": (io.BytesIO(b"x"), "x.md"),
        },
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    assert body["ok"] is False


# ---------------------------------------------------------------------------
# Import purity
# ---------------------------------------------------------------------------

def test_upload_route_module_has_no_forbidden_imports():
    from web.routes import dream_trials_routes
    src = Path(dream_trials_routes.__file__).read_text(encoding="utf-8").lower()
    for needle in (
        "subprocess",
        "patch_engine",
        "patch_plan_executor",
        "run_patch_plan",
        "run_benchmarks",
        "anthropic",
        "openai",
        "google.genai",
        "litellm",
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "run_gemini_request",
    ):
        assert needle.lower() not in src, f"forbidden import leaked: {needle}"
