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



def test_create_with_depends_on(tmp_path):
    scope = _scope(tmp_path)
    a = loader.create(scope, "task a")
    b = loader.create(scope, "task b", depends_on=[a.id])
    reloaded = loader.load(scope, b.id)
    assert reloaded.depends_on == [a.id]


def test_ready_blocked_on_unmet_dependency(tmp_path):
    scope = _scope(tmp_path)
    a = loader.create(scope, "task a")  # still draft
    b = loader.create(scope, "task b", depends_on=[a.id])
    with pytest.raises(ValueError, match=a.id):
        loader.transition(scope, b.id, "ready")
    # a is unaffected, still draft
    assert loader.load(scope, a.id).status == "draft"


def test_ready_allowed_once_dependency_done(tmp_path):
    scope = _scope(tmp_path)
    a = loader.create(scope, "task a")
    b = loader.create(scope, "task b", depends_on=[a.id])
    loader.transition(scope, a.id, "ready")
    loader.transition(scope, a.id, "running")
    loader.transition(scope, a.id, "done")
    loader.transition(scope, b.id, "ready")
    assert loader.load(scope, b.id).status == "ready"


def test_unmet_dependencies_reports_missing_spec(tmp_path):
    scope = _scope(tmp_path)
    b = loader.create(scope, "task b", depends_on=["nonexistent-spec"])
    unmet = loader.unmet_dependencies(scope, b)
    assert unmet == ["nonexistent-spec"]


def test_find_cycle_detects_direct_cycle(tmp_path):
    scope = _scope(tmp_path)
    a = loader.create(scope, "task a")
    b = loader.create(scope, "task b", depends_on=[a.id])
    # a -> b would close the loop b -> a -> b
    cycle = loader.find_cycle(scope, a.id, [b.id])
    assert cycle is not None
    assert cycle[0] == a.id and cycle[-1] == a.id


def test_find_cycle_none_for_acyclic_graph(tmp_path):
    scope = _scope(tmp_path)
    a = loader.create(scope, "task a")
    b = loader.create(scope, "task b")
    c = loader.create(scope, "task c", depends_on=[a.id, b.id])
    assert loader.find_cycle(scope, c.id, [a.id, b.id]) is None
