"""Built-in spec templates — seed steps/acceptance/tags/context on create.

Pure data + lookup free functions (house style). Six built-ins matching the
README/skills: bug-fix, feature, refactor, migration, test, review.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Template:
    name: str
    description: str
    steps: list[str] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    context_hint: str = ""


_TEMPLATES: dict[str, Template] = {
    "bug-fix": Template(
        name="bug-fix",
        description="Reproduce, fix, and regression-test a bug.",
        steps=[
            "Reproduce the bug with a failing test",
            "Locate the root cause",
            "Implement the fix",
            "Confirm the test passes and add a regression test",
        ],
        acceptance=["Bug no longer reproduces", "Regression test added", "No new failures"],
        tags=["bug"],
        context_hint="Describe the observed vs. expected behavior and repro steps.",
    ),
    "feature": Template(
        name="feature",
        description="Design, implement, test, and document a new feature.",
        steps=[
            "Explore the relevant code",
            "Implement the feature",
            "Add tests",
            "Update documentation",
        ],
        acceptance=["Feature works as described", "Tests pass", "No regressions"],
        tags=["feature"],
        context_hint="Describe the feature and its user-facing behavior.",
    ),
    "refactor": Template(
        name="refactor",
        description="Restructure code without changing behavior.",
        steps=[
            "Characterize current behavior with tests",
            "Refactor incrementally",
            "Keep tests green at each step",
        ],
        acceptance=["Behavior unchanged", "Tests still pass", "Complexity reduced"],
        tags=["refactor"],
        context_hint="Describe the smell and the target structure.",
    ),
    "migration": Template(
        name="migration",
        description="Move data or code from one form/system to another.",
        steps=[
            "Inventory the source",
            "Write the migration",
            "Dry-run and verify",
            "Cut over and clean up",
        ],
        acceptance=["All items migrated", "Verified against source", "Rollback path documented"],
        tags=["migration"],
        context_hint="Describe source, target, and cutover constraints.",
    ),
    "test": Template(
        name="test",
        description="Add or improve test coverage.",
        steps=[
            "Identify untested paths",
            "Write tests",
            "Confirm they fail without the code / pass with it",
        ],
        acceptance=["Coverage increased", "Tests are deterministic", "CI green"],
        tags=["test"],
        context_hint="Describe what needs coverage and the risk it mitigates.",
    ),
    "review": Template(
        name="review",
        description="Review a change for correctness and quality.",
        steps=[
            "Read the diff and its context",
            "Check correctness, edge cases, and style",
            "Record findings",
        ],
        acceptance=["Findings recorded", "Blocking issues flagged", "Verdict given"],
        tags=["review"],
        context_hint="Point at the diff/PR and the review focus.",
    ),
}


def get(name: str) -> Template | None:
    return _TEMPLATES.get(name)


def list_templates() -> list[Template]:
    return list(_TEMPLATES.values())
