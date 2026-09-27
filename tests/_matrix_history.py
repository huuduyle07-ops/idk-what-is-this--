"""Test-only: run the product lifecycle against the five-case LIVE.5 oracle.

INDENT.SEMANTICS.1 appended three fixed preservation cases to every
``indentation_style`` matrix: Python continuation alignment, a Python multi-line
string interior, and tab-indented Go.  Under that eight-case oracle no candidate
the frozen ``safe_minimal`` gate admits is known to close the matrix: every body
known to read block structure imports ``tokenize``, which the gate refuses as a
novel import, and a raw-width body breaks the two Python cases.
``tests/test_indent_semantics1.py`` measures both facts.

Some suites are about what happens *after* a candidate is verified —
presentation coherence, revision recovery, the public runner's verified path.
Their subject is that lifecycle, not the oracle, and they still need a candidate
the gate admits and the matrix closes.  They declare the five-case oracle
DEFECT.PROBE.LIVE.5 shipped, through this one helper, rather than claiming that
the eight-case oracle accepts their candidate.  The product always runs every
case; production code never imports this module.
"""
from __future__ import annotations

from typing import Any

#: The three cases INDENT.SEMANTICS.1 appended.  Their ids are fixed for every
#: indentation fact, so filtering them out leaves exactly LIVE.5's case set.
INDENT_SEMANTICS_1_CASE_IDS = frozenset(
    {
        "indentation_style.preserve.4space.continuation",
        "indentation_style.preserve.4space.multiline_string",
        "indentation_style.preserve.tab.go",
    }
)


def live5_cases(cases: Any) -> tuple:
    """The LIVE.5 cases of a production-built matrix, in their order."""

    return tuple(case for case in cases if case.case_id not in INDENT_SEMANTICS_1_CASE_IDS)


def pin_live5_indentation_matrix(monkeypatch) -> None:
    """Make every matrix the product builds in this test the LIVE.5 five."""

    import core.behavioral_matrix as matrix

    production_builder = matrix.build_behavioral_matrix

    def live5_matrix(*, probe_contract, behavior_fact):
        return live5_cases(
            production_builder(probe_contract=probe_contract, behavior_fact=behavior_fact)
        )

    monkeypatch.setattr(matrix, "build_behavioral_matrix", live5_matrix)
