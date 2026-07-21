"""Scope resolution and directory scaffolding for execution-scope specs.

Two scopes coexist (mirrors geno-notes):
- global:   ~/.geno/geno-specs/
- project:  ./.geno/geno-specs/  or  ./geno/geno-specs/  (walking up from cwd)

Resolution order:
  1. explicit override ("global" | "project")
  2. $GENO_SPECS_SCOPE (global|project)
  3. $GENO_SPECS_DIR   (exact dir)
  4. ancestor-walk for ./.geno/geno-specs/ or ./geno/geno-specs/ → project
  5. otherwise → global (auto-created on first use)

Note: cli.py constructs Scope("project", dir) positionally and reads `.dir`,
so the first field stays positional.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

GLOBAL_DIR = Path.home() / ".geno" / "geno-specs"

# Two accepted project layouts: dotted (./.geno/geno-specs/) and the
# geno-notes-style plain (./geno/geno-specs/). Both are recognised on walk-up.
_PROJECT_LAYOUTS = (
    (".geno", "geno-specs"),
    ("geno", "geno-specs"),
)


@dataclass(frozen=True)
class Scope:
    name: str          # "global" | "project"
    dir: Path


def _find_project_dir(start: Path) -> Path | None:
    """Walk up from `start` looking for a recognised project specs dir."""
    cur = start.resolve()
    while True:
        for parent, sub in _PROJECT_LAYOUTS:
            candidate = cur / parent / sub
            if candidate.is_dir():
                return candidate
        if cur.parent == cur:
            return None
        cur = cur.parent


def resolve_scope(
    cwd: Path | None = None,
    override: str | None = None,  # "global" | "project" | None
) -> Scope:
    """Return the active scope (may create the global dir on first use)."""
    cwd = (cwd or Path.cwd()).resolve()

    # Explicit override wins.
    if override == "global":
        return Scope("global", GLOBAL_DIR)
    if override == "project":
        pdir = _find_project_dir(cwd)
        if not pdir:
            raise RuntimeError(
                "No project scope found. Run `geno-specs init --project` here "
                "first, or walk into a dir with ./.geno/geno-specs/."
            )
        return Scope("project", pdir)

    # Env var takes precedence over detection.
    env_scope = os.environ.get("GENO_SPECS_SCOPE", "").strip().lower()
    if env_scope in ("global", "project"):
        return resolve_scope(cwd, override=env_scope)

    env_dir = os.environ.get("GENO_SPECS_DIR", "").strip()
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
        scope_name = "project" if "geno-specs" in p.parts else "global"
        return Scope(scope_name, p)

    # Project detection via ancestor walk.
    pdir = _find_project_dir(cwd)
    if pdir:
        return Scope("project", pdir)

    # Fall through to global (auto-created).
    return Scope("global", GLOBAL_DIR)


def scope_for(name: str) -> Scope:
    """Return the scope struct for 'global' or 'project' without resolution rules."""
    if name == "global":
        return Scope("global", GLOBAL_DIR)
    if name == "project":
        pdir = _find_project_dir(Path.cwd())
        if not pdir:
            raise RuntimeError("No project scope found in cwd or ancestors.")
        return Scope("project", pdir)
    raise ValueError(f"Unknown scope: {name!r}")


def ensure_structure(scope: Scope) -> None:
    """Create the execution-scope directory layout. Idempotent."""
    d = scope.dir
    d.mkdir(parents=True, exist_ok=True)
    (d / "specs").mkdir(exist_ok=True)
    (d / ".geno-specs").mkdir(exist_ok=True)
    (d / ".geno-specs" / "locks").mkdir(exist_ok=True)


def list_all_scopes(cwd: Path | None = None) -> list[Scope]:
    """Return (project?, global) in that order — project first if discoverable."""
    cwd = (cwd or Path.cwd()).resolve()
    out: list[Scope] = []
    pdir = _find_project_dir(cwd)
    if pdir:
        out.append(Scope("project", pdir))
    if GLOBAL_DIR.is_dir():
        out.append(Scope("global", GLOBAL_DIR))
    return out
