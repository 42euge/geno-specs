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

import re
import subprocess
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
    fill: bool = False,
) -> Path:
    """Create .specs/ with VISION.md, TENETS.md, GOALS.md, features/.

    If `fill` is True, draft real starter content into VISION/TENETS/GOALS by
    reading the repo README and recent git log, instead of leaving bare
    HTML-comment placeholders. Existing files are never overwritten either
    way (see `_seed`).
    """
    root = repo_root or Path.cwd()
    specs_dir = specs_root(root)
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / FEATURES_DIR).mkdir(exist_ok=True)

    if fill:
        readme_desc, readme_purpose = _read_readme(root)
        commit_subjects = _read_recent_commits(root)
        _seed(specs_dir / "VISION.md", _vision_filled(name, description or readme_desc, readme_purpose))
        _seed(specs_dir / "TENETS.md", _tenets_filled(name))
        _seed(specs_dir / "GOALS.md", _goals_filled(name, commit_subjects))
    else:
        _seed(specs_dir / "VISION.md", _vision_template(name, description))
        _seed(specs_dir / "TENETS.md", _tenets_template(name))
        _seed(specs_dir / "GOALS.md", _goals_template(name))

    return specs_dir


def _seed(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


# ─── placeholder templates (default, no --fill) ────────────────────────


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


# ─── --fill: heuristic draft content from README + git log ────────────


def _read_readme(repo_root: Path) -> tuple[str, str]:
    """Return (one-line description, purpose paragraph) scraped from README.

    No LLM call — just pulls the first non-heading line as a one-liner and
    the first substantial paragraph after it as a "purpose" blurb.
    """
    readme = None
    for candidate in ("README.md", "README.rst", "README.txt", "README"):
        p = repo_root / candidate
        if p.exists():
            readme = p
            break
    if readme is None:
        return "", ""

    try:
        text = readme.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", ""

    lines = [ln.rstrip() for ln in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith("#") or stripped.startswith("!["):
            continue
        if stripped.startswith(("```", "|", "<")):
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    one_liner = ""
    purpose = ""
    if paragraphs:
        one_liner = re.sub(r"[*_`]", "", paragraphs[0]).strip()
        if len(paragraphs) > 1:
            purpose = re.sub(r"[*_`]", "", paragraphs[1]).strip()
        else:
            purpose = one_liner

    return one_liner, purpose


def _read_recent_commits(repo_root: Path, limit: int = 25) -> list[str]:
    """Return recent commit subjects, newest first. Empty list if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--pretty=format:%s"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]


def _vision_filled(name: str, description: str, purpose: str) -> str:
    title = name or "Project"
    desc = description or f"{title} — describe the long-term vision for this project."
    why = purpose or (
        f"{title} exists to solve a problem worth automating or simplifying. "
        "Replace this paragraph with the real motivation: what breaks or is "
        "tedious without it, and who feels that pain."
    )
    return f"""# Vision

{desc}

> DRAFT — generated by `geno-specs init --fill` from README.md and git log.
> Read it, correct it, delete this line.

## Why this exists

{why}

## Where we're headed

<!-- DRAFT: no strong signal for this in README/git log. Fill in what
     "success" looks like for {title} — the state where the problem above
     is solved and nobody thinks about it anymore. -->
"""


def _tenets_filled(name: str) -> str:
    title = name or "Project"
    return f"""# Tenets

Architectural principles that guide development decisions in {title}. When tenets conflict, earlier entries take precedence.

> DRAFT — generated by `geno-specs init --fill`. These are generic starter
> principles, not project-specific ones. Replace or reorder them; they exist
> so this file isn't empty, not because they're definitely right for {title}.

1. **Prefer explicit over implicit** — Make behavior visible in code and config rather than inferred from convention; a reader shouldn't have to guess what will happen.
2. **Small, isolated units** — Keep functions, modules, and changes small enough to reason about and test independently; compose rather than entangle.
"""


def _goals_filled(name: str, commit_subjects: list[str]) -> str:
    title = name or "Project"
    if commit_subjects:
        bullets = "\n".join(f"- {subj}" for subj in commit_subjects[:15])
        active_note = (
            f"> DRAFT — generated by `geno-specs init --fill` from the last "
            f"{min(len(commit_subjects), 15)} commits. These are recent work, not "
            "necessarily open goals — prune finished items into Completed and turn "
            "the rest into real goal statements with target dates."
        )
        active = f"{active_note}\n\n{bullets}"
    else:
        active = (
            "> DRAFT — generated by `geno-specs init --fill`. No git history "
            "found to summarize; add your current goals here."
        )
    return f"""# Goals

Current goals for {title}. Review and update regularly.

## Active

{active}

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
