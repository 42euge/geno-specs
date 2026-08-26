"""Named pass-lists: must_pass / must_not_regress, with backward compat.

`checks` (the original flat list) is kept as the on-disk key and is treated
as `must_pass`. `must_not_regress` is new and optional. Old spec files with
only `checks:` must keep loading and validating exactly as before.
"""

from __future__ import annotations

from click.testing import CliRunner

from geno_specs import loader, nodes
from geno_specs.cli import main
from geno_specs.models import Check
from geno_specs.paths import Scope


def _scope(tmp_path):
    s = Scope("project", tmp_path)
    (tmp_path / "specs").mkdir()
    (tmp_path / ".geno-specs" / "locks").mkdir(parents=True)
    return s


# ─── models/loader: backward compat ────────────────────────────────────


def test_old_flat_checks_file_still_loads(tmp_path):
    """A spec file written before must_not_regress existed loads unchanged."""
    scope = _scope(tmp_path)
    spec = loader.create(scope, "legacy thing")
    spec.checks.append(Check(run="pytest tests/test_auth.py", expect="exit 0"))
    loader.save(scope, spec)

    # On-disk shape is untouched — still the flat `checks:` key, no
    # must_not_regress key at all.
    text = loader.spec_path(scope, spec.id).read_text()
    assert "checks:" in text
    assert "must_not_regress:" not in text

    reloaded = loader.load(scope, spec.id)
    assert reloaded.checks[0].run == "pytest tests/test_auth.py"
    # must_pass is an alias for checks (backward compat category mapping).
    assert reloaded.must_pass == reloaded.checks
    assert reloaded.must_not_regress == []


def test_must_not_regress_roundtrips(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    spec.checks.append(Check(run="pytest tests/new_feature.py", expect="exit 0"))
    spec.must_not_regress.append(Check(run="pytest tests/test_existing.py", expect="exit 0"))
    loader.save(scope, spec)

    text = loader.spec_path(scope, spec.id).read_text()
    assert "must_not_regress:" in text

    reloaded = loader.load(scope, spec.id)
    assert reloaded.checks[0].run == "pytest tests/new_feature.py"
    assert reloaded.must_pass[0].run == "pytest tests/new_feature.py"
    assert reloaded.must_not_regress[0].run == "pytest tests/test_existing.py"


def test_must_pass_setter_writes_through_to_checks(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    spec.must_pass = [Check(run="pytest", expect="exit 0")]
    assert spec.checks[0].run == "pytest"


def test_node_roundtrip_preserves_must_not_regress():
    text = """\
name: fix login
status: draft
checks:
  - run: pytest tests/new.py
    expect: exit 0
must_not_regress:
  - run: pytest tests/existing.py
    expect: exit 0
"""
    root = nodes._parse(text)
    types = {c.type for c in root.children}
    assert "checks" in types and "must_not_regress" in types
    again = nodes._parse(nodes._dump(root))
    assert {c.type for c in again.children} == types


# ─── cli edit: --add-must-not-regress ──────────────────────────────────


def _project(tmp_path, monkeypatch):
    proj = tmp_path / ".geno" / "geno-specs"
    proj.mkdir(parents=True)
    monkeypatch.setenv("GENO_SPECS_DIR", str(proj))
    monkeypatch.chdir(tmp_path)
    return proj


def test_edit_add_must_not_regress(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch)
    run = CliRunner().invoke
    spec_id = run(main, ["create", "thing"]).output.split()[0]
    r = run(main, [
        "edit", spec_id,
        "--add-check", "pytest tests/new.py:exit 0",
        "--add-must-not-regress", "pytest tests/existing.py:exit 0",
    ])
    assert r.exit_code == 0, r.output

    j = run(main, ["show", spec_id, "--json"]).output
    assert "pytest tests/new.py" in j
    assert "pytest tests/existing.py" in j


def test_edit_add_check_still_works_for_backward_compat(tmp_path, monkeypatch):
    """--add-check (the pre-existing flag) keeps working unchanged."""
    _project(tmp_path, monkeypatch)
    run = CliRunner().invoke
    spec_id = run(main, ["create", "thing"]).output.split()[0]
    r = run(main, ["edit", spec_id, "--add-check", "pytest:exit 0"])
    assert r.exit_code == 0, r.output
    j = run(main, ["show", spec_id, "--json"]).output
    assert '"checks"' in j and "pytest" in j


# ─── cli validate: categorized breakdown ───────────────────────────────


def test_validate_reports_must_pass_and_must_not_regress_categories(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch)
    run = CliRunner().invoke
    spec_id = run(main, ["create", "thing"]).output.split()[0]
    run(main, [
        "edit", spec_id,
        "--add-check", "true:exit 0",
        "--add-must-not-regress", "false:exit 0",
    ])

    r = run(main, ["validate", spec_id])
    assert r.exit_code == 1  # the must_not_regress check fails -> overall fail
    assert "[must_pass]" in r.output
    assert "[must_not_regress]" in r.output
    assert "REGRESSION" in r.output
    assert "1 must_pass failures" not in r.output  # must_pass check passed
    assert "1 regressions" in r.output


def test_validate_json_breakdown_by_category(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch)
    run = CliRunner().invoke
    spec_id = run(main, ["create", "thing"]).output.split()[0]
    run(main, [
        "edit", spec_id,
        "--add-check", "true:exit 0",
        "--add-must-not-regress", "false:exit 0",
    ])

    r = run(main, ["validate", spec_id, "--json"])
    assert r.exit_code == 1
    import json

    # json output is interleaved with human lines in stdout; parse the
    # trailing JSON object.
    start = r.output.index("{")
    data = json.loads(r.output[start:])
    assert data["must_pass:true"] == {
        "category": "must_pass", "passed": True, "output": "exit 0",
    }
    assert data["must_not_regress:false"]["category"] == "must_not_regress"
    assert data["must_not_regress:false"]["passed"] is False


def test_validate_old_style_flat_checks_spec_still_validates(tmp_path, monkeypatch):
    """A regression test for pure backward compat: a spec with only the
    legacy flat `checks` field (no must_not_regress at all) validates
    exactly as it did before this feature existed."""
    proj = _project(tmp_path, monkeypatch)
    scope = Scope("project", proj)
    spec = loader.create(scope, "legacy thing")
    spec.checks.append(Check(run="true", expect="exit 0"))
    loader.save(scope, spec)

    run = CliRunner().invoke
    r = run(main, ["validate", spec.id])
    assert r.exit_code == 0, r.output
    assert "[must_pass]" in r.output
    assert "1 passed, 0 failed" in r.output
