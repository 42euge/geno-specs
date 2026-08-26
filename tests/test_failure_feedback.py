"""Structured failure feedback for the failed -> ready retry loop.

Covers:
  - a failing `validate` populates `last_failure` with per-check stdout/
    stderr/exit code and flips the spec to `failed`
  - `render_prompt` surfaces `last_failure` on the next `run` after retry
  - `done` clears `last_failure`
  - a clean `validate` pass clears a stale `last_failure`
"""

from __future__ import annotations

from click.testing import CliRunner

from geno_specs import loader
from geno_specs.cli import main
from geno_specs.models import Check, Failure, FailureCheck, OutputFile
from geno_specs.paths import Scope
from geno_specs.renderer import render_prompt


def _scope(tmp_path):
    s = Scope("project", tmp_path)
    (tmp_path / "specs").mkdir()
    (tmp_path / ".geno-specs" / "locks").mkdir(parents=True)
    return s


# ─── loader-level: set_failure / clear-on-done ─────────────────────────


def test_set_failure_persists_structured_record(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    loader.transition(scope, spec.id, "ready")
    loader.transition(scope, spec.id, "running")

    failure = Failure(
        timestamp="2026-08-26T00:00:00+00:00",
        checks=[
            FailureCheck(
                kind="check", target="pytest", message="exit 1 (expected 0)",
                stdout="1 failed", stderr="AssertionError: boom", exit_code=1,
            )
        ],
    )
    spec = loader.set_failure(scope, spec.id, failure)
    assert spec.status == "failed"
    assert spec.last_failure is not None

    reloaded = loader.load(scope, spec.id)
    assert reloaded.status == "failed"
    assert reloaded.last_failure is not None
    assert reloaded.last_failure.timestamp == "2026-08-26T00:00:00+00:00"
    c = reloaded.last_failure.checks[0]
    assert c.kind == "check" and c.target == "pytest"
    assert c.stderr == "AssertionError: boom" and c.exit_code == 1


def test_render_prompt_includes_last_failure_on_retry(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    loader.transition(scope, spec.id, "ready")
    loader.transition(scope, spec.id, "running")

    failure = Failure(
        timestamp="2026-08-26T00:00:00+00:00",
        checks=[
            FailureCheck(
                kind="check", target="pytest", message="exit 1 (expected 0)",
                stdout="1 failed", stderr="AssertionError: boom", exit_code=1,
            )
        ],
    )
    loader.set_failure(scope, spec.id, failure)

    # retry: failed -> ready -> running
    loader.transition(scope, spec.id, "ready")
    retry_spec = loader.transition(scope, spec.id, "running")

    prompt = render_prompt(retry_spec)
    assert "Last failure" in prompt
    assert "pytest" in prompt
    assert "AssertionError: boom" in prompt


def test_done_clears_last_failure(tmp_path):
    scope = _scope(tmp_path)
    spec = loader.create(scope, "thing")
    loader.transition(scope, spec.id, "ready")
    loader.transition(scope, spec.id, "running")
    loader.set_failure(scope, spec.id, Failure(timestamp="t", checks=[
        FailureCheck(kind="check", target="pytest", message="boom"),
    ]))

    loader.transition(scope, spec.id, "ready")
    loader.transition(scope, spec.id, "running")
    done_spec = loader.transition(scope, spec.id, "done")

    assert done_spec.last_failure is None
    assert loader.load(scope, spec.id).last_failure is None


# ─── CLI-level: validate captures full output ──────────────────────────


def test_validate_cli_populates_last_failure_with_output(tmp_path, monkeypatch):
    proj = tmp_path / ".geno" / "geno-specs"
    proj.mkdir(parents=True)
    monkeypatch.setenv("GENO_SPECS_DIR", str(proj))
    monkeypatch.chdir(tmp_path)

    scope = Scope("project", proj)
    spec = loader.create(scope, "thing")
    spec.checks.append(Check(run="exit 1", expect="exit 0"))
    loader.save(scope, spec)

    r = CliRunner().invoke(main, ["validate", spec.id])
    assert r.exit_code == 1
    assert "why validation failed" in r.output
    assert "exit 1" in r.output.lower() or "1 failed" in r.output

    reloaded = loader.load(scope, spec.id)
    assert reloaded.last_failure is not None
    c = reloaded.last_failure.checks[0]
    assert c.kind == "check"
    assert c.target == "exit 1"
    assert c.exit_code == 1


def test_validate_cli_clears_stale_failure_on_pass(tmp_path, monkeypatch):
    proj = tmp_path / ".geno" / "geno-specs"
    proj.mkdir(parents=True)
    monkeypatch.setenv("GENO_SPECS_DIR", str(proj))
    monkeypatch.chdir(tmp_path)

    scope = Scope("project", proj)
    spec = loader.create(scope, "thing")
    spec.last_failure = Failure(timestamp="t", checks=[
        FailureCheck(kind="check", target="old", message="stale"),
    ])
    loader.save(scope, spec)

    r = CliRunner().invoke(main, ["validate", spec.id])
    assert r.exit_code == 0

    reloaded = loader.load(scope, spec.id)
    assert reloaded.last_failure is None


def test_validate_cli_missing_output_captured(tmp_path, monkeypatch):
    proj = tmp_path / ".geno" / "geno-specs"
    proj.mkdir(parents=True)
    monkeypatch.setenv("GENO_SPECS_DIR", str(proj))
    monkeypatch.chdir(tmp_path)

    scope = Scope("project", proj)
    spec = loader.create(scope, "thing")
    spec.outputs.append(OutputFile(path=str(tmp_path / "nope.txt")))
    loader.save(scope, spec)

    r = CliRunner().invoke(main, ["validate", spec.id])
    assert r.exit_code == 1

    reloaded = loader.load(scope, spec.id)
    assert reloaded.last_failure is not None
    c = reloaded.last_failure.checks[0]
    assert c.kind == "output"
    assert "missing" in c.message
