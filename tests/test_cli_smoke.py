"""CLI smoke tests via click's CliRunner, using a temp project scope."""

from __future__ import annotations

import os

import pytest
from click.testing import CliRunner

from geno_specs.cli import main


@pytest.fixture
def project(tmp_path, monkeypatch):
    # Point scope resolution at an isolated project dir.
    proj = tmp_path / ".geno" / "geno-specs"
    proj.mkdir(parents=True)
    monkeypatch.setenv("GENO_SPECS_DIR", str(proj))
    monkeypatch.chdir(tmp_path)
    return proj


def test_templates_lists_six(project):
    r = CliRunner().invoke(main, ["templates"])
    assert r.exit_code == 0
    for name in ("bug-fix", "feature", "refactor", "migration", "test", "review"):
        assert name in r.output


def test_create_list_show(project):
    run = CliRunner().invoke
    r = run(main, ["create", "fix", "login", "bug", "--template", "bug-fix", "-t", "auth"])
    assert r.exit_code == 0, r.output
    spec_id = r.output.split()[0]

    r = run(main, ["list"])
    assert spec_id in r.output

    r = run(main, ["show", spec_id, "--json"])
    assert r.exit_code == 0 and '"id"' in r.output

    r = run(main, ["show", spec_id, "--prompt"])
    assert r.exit_code == 0 and "fix login bug" in r.output.lower()


def test_lifecycle_via_cli(project):
    run = CliRunner().invoke
    spec_id = run(main, ["create", "thing"]).output.split()[0]
    assert run(main, ["ready", spec_id]).exit_code == 0
    r = run(main, ["run", spec_id])
    assert r.exit_code == 0 and "thing" in r.output.lower()  # run prints the prompt
    assert run(main, ["done", spec_id]).exit_code == 0


def test_edit_appends(project):
    run = CliRunner().invoke
    spec_id = run(main, ["create", "thing"]).output.split()[0]
    r = run(main, [
        "edit", spec_id,
        "--add-input", "a.py:src",
        "--add-output", "out.txt:contains X",
        "--add-check", "pytest:exit 0",
        "--add-step", "do it",
        "--agent-cap", "python",
        "--agent-model", "opus",
    ])
    assert r.exit_code == 0, r.output
    j = run(main, ["show", spec_id, "--json"]).output
    assert "a.py" in j and "out.txt" in j and "pytest" in j and "python" in j



def test_create_with_depends_on_and_ready_blocked(project):
    run = CliRunner().invoke
    a_id = run(main, ["create", "task", "a"]).output.split()[0]
    b_id = run(main, ["create", "task", "b", "--depends-on", a_id]).output.split()[0]

    r = run(main, ["ready", b_id])
    assert r.exit_code != 0
    assert a_id in r.output

    # unblock: finish a, then b can go ready
    run(main, ["ready", a_id])
    run(main, ["run", a_id])
    run(main, ["done", a_id])
    r = run(main, ["ready", b_id])
    assert r.exit_code == 0, r.output


def test_edit_depends_on_rejects_cycle(project):
    run = CliRunner().invoke
    a_id = run(main, ["create", "task", "a"]).output.split()[0]
    b_id = run(main, ["create", "task", "b", "--depends-on", a_id]).output.split()[0]

    r = run(main, ["edit", a_id, "--depends-on", b_id])
    assert r.exit_code != 0
    assert "cycle" in r.output.lower()


def test_edit_depends_on_rejects_self(project):
    run = CliRunner().invoke
    a_id = run(main, ["create", "task", "a"]).output.split()[0]
    r = run(main, ["edit", a_id, "--depends-on", a_id])
    assert r.exit_code != 0


def test_list_unblocked_filter(project):
    run = CliRunner().invoke
    a_id = run(main, ["create", "task", "a"]).output.split()[0]
    b_id = run(main, ["create", "task", "b", "--depends-on", a_id]).output.split()[0]

    run(main, ["ready", a_id])  # a: ready, no deps -> unblocked
    # b still draft, can't even be readied yet

    r = run(main, ["list", "--unblocked"])
    assert a_id in r.output
    assert b_id not in r.output

    # finish a, ready b -> now b should also show unblocked
    run(main, ["run", a_id])
    run(main, ["done", a_id])
    run(main, ["ready", b_id])
    r = run(main, ["list", "--unblocked"])
    assert b_id in r.output

def test_demo_seeds_and_shows(project):
    run = CliRunner().invoke
    r = run(main, ["demo"])
    assert r.exit_code == 0, r.output
    assert "demo-http-retry-backoff" in r.output
    assert "(created)" in r.output

    r = run(main, ["list"])
    assert "demo-http-retry-backoff" in r.output
    assert "demo" in r.output

    r = run(main, ["show", "demo-http-retry-backoff"])
    assert r.exit_code == 0
    assert "retry" in r.output.lower()
    assert "src/http_client.py" in r.output


def test_demo_is_idempotent_not_duplicated(project):
    run = CliRunner().invoke
    run(main, ["demo"])
    r = run(main, ["demo"])
    assert r.exit_code == 0
    assert "(overwritten)" in r.output

    r = run(main, ["list"])
    assert r.output.count("demo-http-retry-backoff") == 1


def test_demo_remove(project):
    run = CliRunner().invoke
    run(main, ["demo"])
    r = run(main, ["demo", "--remove"])
    assert r.exit_code == 0
    assert "removed" in r.output

    r = run(main, ["list"])
    assert "demo-http-retry-backoff" not in r.output


def test_demo_remove_when_absent(project):
    run = CliRunner().invoke
    r = run(main, ["demo", "--remove"])
    assert r.exit_code == 0
    assert "not found" in r.output

