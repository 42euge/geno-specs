"""CRUD + lifecycle transitions + in-place mutation persistence."""

from __future__ import annotations

import pytest

from geno_specs import loader
from geno_specs.models import Check, InputFile, OutputFile
from geno_specs.paths import Scope


def _scope(tmp_path):
    s = Scope("project", tmp_path)
    (tmp_path / "specs").mkdir()
    (tmp_path / ".geno-specs" / "locks").mkdir(parents=True)
    return s


def test_create_load_save(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "fix login bug", tags=["auth"], template="bug-fix")
    assert spec.id.endswith("-fix-login-bug")
    assert spec.status == "draft"
    reloaded = loader.load(scope, spec.id)
    assert reloaded.title == "fix login bug"
    assert reloaded.tags == ["auth"]


def test_lifecycle_transitions(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    loader.transition(scope, spec.id, "ready")
    loader.transition(scope, spec.id, "running")
    loader.transition(scope, spec.id, "done")
    assert loader.load(scope, spec.id).status == "done"


def test_illegal_transition_rejected(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")  # draft
    with pytest.raises(ValueError):
        loader.transition(scope, spec.id, "done")  # draft -> done not allowed


def test_failed_can_retry(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    for st in ("ready", "running", "failed", "ready"):
        loader.transition(scope, spec.id, st)
    assert loader.load(scope, spec.id).status == "ready"


def test_inplace_mutation_persists(tmp_path):
    """Mirrors cli.py edit: append to flat lists, then save."""
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    spec.inputs.append(InputFile(path="a.py", role="src"))
    spec.outputs.append(OutputFile(path="out.txt", check="contains X"))
    spec.checks.append(Check(run="pytest", expect="exit 0"))
    spec.steps.append("do it")
    spec.agent.capabilities.append("python")
    spec.agent.model = "opus"
    loader.save(scope, spec)

    r = loader.load(scope, spec.id)
    assert r.inputs[0].path == "a.py" and r.inputs[0].role == "src"
    assert r.outputs[0].check == "contains X"
    assert r.checks[0].run == "pytest"
    assert "do it" in r.steps
    assert r.agent.capabilities == ["python"] and r.agent.model == "opus"


def test_load_missing_raises(tmp_path):
    scope = _scope(tmp_path)
    with pytest.raises(FileNotFoundError):
        loader.load(scope, "nope")
