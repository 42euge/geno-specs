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


FEATURE_TEMPLATE = """\
name: {name}
status: draft
description: >-
  {description}

inputs:
  # - path: src/module.py
  #   role: Target module

outputs:
  # - path: src/module.py
  #   check: "contains 'class NewFeature'"

steps:
  - Explore the relevant code
  - Implement the feature
  - Add tests
  - Update documentation

acceptance:
  - Feature works as described
  - Tests pass
  - No regressions

checks:
  # - run: pytest tests/
  #   expect: exit 0
"""


def create_feature_spec(
    repo_root: Path | None,
    name: str,
    description: str = "",
) -> Path:
    """Create a feature spec YAML file."""
    path = feature_spec_path(repo_root, name)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise FileExistsError(f"Feature spec already exists: {path}")

    content = FEATURE_TEMPLATE.format(
        name=name,
        description=description or "Describe this feature.",
    )
    path.write_text(content, encoding="utf-8")
    return path
