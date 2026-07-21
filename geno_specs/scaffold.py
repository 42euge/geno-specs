"""Scaffold a .specs/ directory in a repo.

Creates the standard project specification structure:
  .specs/
  ├── VISION.md
  ├── TENETS.md
  ├── GOALS.md
  └── features/
      └── (feature-name.genospecs.yaml files)
"""

from __future__ import annotations

from pathlib import Path


SPECS_DIR = ".specs"
FEATURES_DIR = "features"


def specs_root(repo_root: Path | None = None) -> Path:
    return (repo_root or Path.cwd()) / SPECS_DIR


def features_dir(repo_root: Path | None = None) -> Path:
    return specs_root(repo_root) / FEATURES_DIR


def scaffold(
    repo_root: Path | None = None,
    *,
    name: str = "",
    description: str = "",
) -> Path:
    """Create .specs/ with VISION.md, TENETS.md, GOALS.md, features/."""
    root = specs_root(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / FEATURES_DIR).mkdir(exist_ok=True)

    _seed(root / "VISION.md", _vision_template(name, description))
    _seed(root / "TENETS.md", _tenets_template(name))
    _seed(root / "GOALS.md", _goals_template(name))

    return root


def _seed(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _vision_template(name: str, description: str) -> str:
    title = name or "Project"
    desc = description or "Describe the long-term vision for this project."
    return f"""# Vision

{desc}

## Why this exists

<!-- What problem does {title} solve? Who benefits? -->

## Where we're headed

<!-- What does the world look like when {title} succeeds? -->
"""


def _tenets_template(name: str) -> str:
    title = name or "Project"
    return f"""# Tenets

Architectural principles that guide development decisions in {title}. When tenets conflict, earlier entries take precedence.

1. **<!-- Tenet 1 -->** — <!-- Description -->
2. **<!-- Tenet 2 -->** — <!-- Description -->
3. **<!-- Tenet 3 -->** — <!-- Description -->
"""


def _goals_template(name: str) -> str:
    title = name or "Project"
    return f"""# Goals

Current goals for {title}. Review and update regularly.

## Active

- <!-- Goal 1: description, target date -->

## Completed

- <!-- Moved here when done -->

## Deferred

- <!-- Moved here when deprioritized -->
"""


def feature_spec_path(repo_root: Path | None, feature_name: str) -> Path:
    slug = feature_name.lower().replace(" ", "-").replace("_", "-")
    return features_dir(repo_root) / f"{slug}.genospecs.yaml"


# Guidance for the optional multi-repo / phased / architecture fields. Appended
# as a trailing comment block — comments are documentation only (not modeled by
# the parser), so they never affect round-tripping.
_OPTIONAL_FIELDS_GUIDE = """\

# ─── optional: multi-repo / phased / architecture specs ───────────────
# Omit these for a simple feature; use them for an ecosystem-layer design.
#
# composes:        # repos this spec composes (not reimplements)
#   - repo: geno-loops
#     role: loop edges
#     optional: false
# phases:          # ordered delivery phases; each may gate the next
#   - id: p0
#     title: Foundation
#     goal: Define the IR
#     gates: [p1]
#     done: false
# open_questions:  # design decisions shaping the work
#   - id: q1
#     question: What is the definition format?
#     options: [a, b, c]
#     lean: ""
#     decision: ""
#     status: open
# depends_on:      # spec ids that must be `done` first
#   - 20260101-some-other-spec
# deferred:        # explicitly out-of-scope-for-now
#   - title: geno-meta as an instance of this system
#     why: proof-of-generality, not a v1 dependency
# subspecs:        # nest sub-specs (a spec inside a spec), recursively
#   - name: sub-feature
#     status: draft
#     steps: [do the thing]
"""


def _feature_template_node(name: str, description: str) -> "Node":
    """Build the default `feature` spec as a Node tree.

    Generating the on-disk YAML from the same Node model the parser reads means
    the emitted file and the parser can never drift.
    """
    from geno_specs.nodes import Node

    return Node(type="spec", data={
        "title": name,
        "status": "draft",
        "context": description or "Describe this feature.",
    }, children=[
        Node("steps", data={"items": [
            "Explore the relevant code",
            "Implement the feature",
            "Add tests",
            "Update documentation",
        ]}),
        Node("acceptance", data={"items": [
            "Feature works as described",
            "Tests pass",
            "No regressions",
        ]}),
    ])


def create_feature_spec(
    repo_root: Path | None,
    name: str,
    description: str = "",
) -> Path:
    """Create a feature spec YAML file (generated from the Node model)."""
    from geno_specs import nodes

    path = feature_spec_path(repo_root, name)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise FileExistsError(f"Feature spec already exists: {path}")

    body = nodes._dump(_feature_template_node(name, description))
    path.write_text(body + _OPTIONAL_FIELDS_GUIDE, encoding="utf-8")
    return path
