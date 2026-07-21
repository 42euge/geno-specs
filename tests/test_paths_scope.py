"""Scope resolution precedence."""

from __future__ import annotations

from geno_specs import paths
from geno_specs.paths import Scope


def test_override_global():
    s = paths.resolve_scope(override="global")
    assert s.name == "global" and s.dir == paths.GLOBAL_DIR


def test_env_dir(tmp_path, monkeypatch):
    d = tmp_path / "geno" / "geno-specs"
    d.mkdir(parents=True)
    monkeypatch.setenv("GENO_SPECS_DIR", str(d))
    s = paths.resolve_scope()
    assert s.dir == d.resolve() or s.dir == d


def test_project_ancestor_walk(tmp_path, monkeypatch):
    proj = tmp_path / ".geno" / "geno-specs"
    proj.mkdir(parents=True)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.delenv("GENO_SPECS_DIR", raising=False)
    monkeypatch.delenv("GENO_SPECS_SCOPE", raising=False)
    s = paths.resolve_scope(cwd=nested)
    assert s.name == "project" and s.dir == proj


def test_scope_positional_and_dir():
    # cli.py constructs Scope("project", dir) positionally and reads .dir.
    s = Scope("project", paths.GLOBAL_DIR)
    assert s.name == "project" and s.dir == paths.GLOBAL_DIR


def test_ensure_structure(tmp_path):
    s = Scope("project", tmp_path / "ws")
    paths.ensure_structure(s)
    assert (tmp_path / "ws" / "specs").is_dir()
    assert (tmp_path / "ws" / ".geno-specs" / "locks").is_dir()
