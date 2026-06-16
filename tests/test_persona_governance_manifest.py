"""GOV.1 Persona Governance Manifest docs guardrail.

Docs-only: this test reads documentation files and asserts required content.
It performs no execution — no imports of runtime modules, no model calls, no
subprocess, no patch/apply, no validation runs.
"""
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "docs" / "governance" / "persona_governance_manifest.md"
README_PATH = PROJECT_ROOT / "README.md"
ROADMAP_PATH = (
    PROJECT_ROOT / "docs" / "AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-07.md"
)


def _manifest_text() -> str:
    assert MANIFEST_PATH.exists(), f"missing manifest: {MANIFEST_PATH}"
    return MANIFEST_PATH.read_text(encoding="utf-8")


def test_manifest_exists_and_is_docs_only_gov1():
    text = _manifest_text()
    assert "Persona Governance Manifest (GOV.1)" in text
    # Core principle: GOV.1 limits and defines personas; it does not build them.
    assert "GOV.1 does not build new personas" in text
    assert "GOV.1 limits and defines personas" in text


def test_manifest_defines_four_architecture_layers_and_rule():
    text = _manifest_text()
    for layer in ("City", "District", "Persona", "Artifact"):
        assert layer in text, f"layer missing from manifest: {layer}"
    # A button/route/function is explicitly not a persona.
    assert "never adds a persona" in text
    assert (
        "District = profession. Persona = governance role. "
        "Artifact = transferable record. Button = user action." in text
    )


def test_manifest_defines_five_governance_personas():
    text = _manifest_text()
    for heading in ("### Explorer", "### Verifier", "### Arbiter", "### Courier", "### Human"):
        assert heading in text, f"persona heading missing: {heading}"
    # A few representative permissions / forbidden actions.
    assert "apply patches" in text          # Explorer cannot
    assert "spawn more couriers" in text     # Courier cannot
    assert "auto-approve" in text            # Verifier cannot
    assert "approve itself" in text          # Arbiter cannot


def test_manifest_includes_human_gate_phrase():
    text = _manifest_text()
    assert (
        "Human approval is the final activation gate, but evidence remains the judge."
        in text
    )


def test_manifest_has_anti_inflation_rules():
    text = _manifest_text()
    assert "Anti-inflation" in text
    assert "failure mode worth governing" in text
    assert "distinct responsibility" in text


def test_manifest_districts_reuse_roles():
    text = _manifest_text()
    assert "Coding District" in text
    assert "Admission Guidance District" in text
    assert "create unlimited new inner personas" in text


def test_manifest_parks_neural_lesson_graph_for_gov2():
    text = _manifest_text()
    assert "Lesson-as-neuron" in text
    assert "Anti-lesson-as-inhibition" in text
    assert "GOV.2 — Neural Lesson Graph Activation Preview" in text
    assert "No autonomous nano-agent execution is allowed by GOV.1." in text


def test_manifest_has_forbidden_and_allowed_transitions():
    text = _manifest_text()
    assert "Forbidden" in text and "Allowed" in text
    assert "create new persona without manifest update" in text
    assert "spawn courier" in text
    assert "convert an unsupported claim into truth" in text
    assert "update confidence" in text


def test_manifest_records_what_gov1_does_not_add():
    text = _manifest_text()
    for forbidden in (
        "nano-agent execution",
        "lesson promotion",
        "proposal import",
        "database migration",
        "new backend route",
        "new UI panel",
    ):
        assert forbidden in text, f"missing no-add item: {forbidden}"


def test_readme_links_to_manifest_with_gov1_section():
    readme = README_PATH.read_text(encoding="utf-8")
    assert "docs/governance/persona_governance_manifest.md" in readme
    assert "bounded roles, not autonomous personalities" in readme
    assert "Explorer / Verifier / Arbiter / Courier / Human" in readme
    assert "GOV.1 is docs-only and adds no execution power" in readme


def test_roadmap_records_gov1_complete_docs_only():
    roadmap = ROADMAP_PATH.read_text(encoding="utf-8")
    assert "GOV.1 — Persona Governance Manifest" in roadmap
    assert "Complete / docs-only" in roadmap
    # The roadmap parking-lot note points back to GOV.1.
    assert "Parked by:" in roadmap
