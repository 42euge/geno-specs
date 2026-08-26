"""geno-specs — click CLI."""

from __future__ import annotations

import json
import sys

import click

from geno_specs import __version__, loader, templates
from geno_specs.models import (
    InputFile,
    OutputFile,
    Check,
    AgentRequirements,
    Failure,
    FailureCheck,
    VALID_STATUSES,
)
from geno_specs.paths import Scope, ensure_structure, resolve_scope
from geno_specs.renderer import render_json, render_prompt


# ─── scope plumbing ───────────────────────────────────────────────────


def _scope_options(f):
    f = click.option("--global", "global_", is_flag=True, help="Force global scope.")(f)
    f = click.option("--project", "project_", is_flag=True, help="Force project scope.")(f)
    return f


def _pick_scope(global_: bool, project_: bool) -> Scope:
    if global_ and project_:
        click.echo("error: --global and --project are mutually exclusive", err=True)
        sys.exit(2)
    override = "global" if global_ else "project" if project_ else None
    scope = resolve_scope(override=override)
    ensure_structure(scope)
    return scope


# ─── root ─────────────────────────────────────────────────────────────


@click.group()
@click.version_option(__version__, prog_name="geno-specs")
def main():
    """geno-specs — structured execution specs for agents and dev loops."""


# ─── create ───────────────────────────────────────────────────────────


@main.command()
@click.argument("title", nargs=-1, required=True)
@click.option("--tag", "-t", "tags", multiple=True, help="Tag (repeatable).")
@click.option("--template", "tpl_name", default=None, help="Use a built-in template.")
@click.option("--context", default="", help="Context/description text.")
@click.option("--depends-on", "depends_on", multiple=True, help="Spec id this spec is blocked on (repeatable).")
@_scope_options
def create(
    title: tuple,
    tags: tuple,
    tpl_name: str | None,
    context: str,
    depends_on: tuple,
    global_: bool,
    project_: bool,
):
    """Create a new spec (status: draft)."""
    scope = _pick_scope(global_, project_)
    full_title = " ".join(title).strip()

    steps: list[str] = []
    acceptance: list[str] = []
    merged_tags = list(tags)

    if tpl_name:
        tpl = templates.get(tpl_name)
        if not tpl:
            avail = ", ".join(t.name for t in templates.list_templates())
            click.echo(f"error: unknown template {tpl_name!r}. Available: {avail}", err=True)
            sys.exit(1)
        steps = list(tpl.steps)
        acceptance = list(tpl.acceptance)
        merged_tags = list(dict.fromkeys(list(tags) + tpl.tags))
        if not context:
            context = tpl.context_hint

    spec = loader.create(
        scope,
        full_title,
        tags=merged_tags,
        template=tpl_name,
        context=context,
        steps=steps,
        acceptance=acceptance,
        depends_on=list(depends_on),
    )
    click.echo(f"{spec.id}  (draft)")
    click.echo(f"  {loader.spec_path(scope, spec.id)}")


# ─── list ─────────────────────────────────────────────────────────────


@main.command("list")
@click.option("--status", "-s", default=None, help="Filter by status.")
@click.option("--tag", default=None, help="Filter by tag.")
@click.option("--unblocked", is_flag=True, help="Only specs that are status=ready AND all dependencies are done.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@_scope_options
def list_cmd(status: str | None, tag: str | None, unblocked: bool, as_json: bool, global_: bool, project_: bool):
    """List specs."""
    scope = _pick_scope(global_, project_)
    specs = loader.load_all(scope)

    if status:
        specs = [s for s in specs if s.status == status]
    if tag:
        specs = [s for s in specs if tag in s.tags]
    if unblocked:
        specs = [
            s for s in specs
            if s.status == "ready" and not loader.unmet_dependencies(scope, s)
        ]

    if as_json:
        rows = [render_json(s) for s in specs]
        click.echo(json.dumps(rows, indent=2))
        return

    if not specs:
        click.echo("(no specs)")
        return
    for s in specs:
        tags_str = f"  [{', '.join(s.tags)}]" if s.tags else ""
        click.echo(f"  [{s.status:<9}] {s.id:<28} {s.title}{tags_str}")


# ─── show ─────────────────────────────────────────────────────────────


@main.command()
@click.argument("spec_id")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.option("--prompt", "as_prompt", is_flag=True, help="Render as agent prompt.")
@_scope_options
def show(spec_id: str, as_json: bool, as_prompt: bool, global_: bool, project_: bool):
    """Show a spec."""
    scope = _pick_scope(global_, project_)
    try:
        spec = loader.load(scope, spec_id)
    except FileNotFoundError:
        click.echo(f"error: spec {spec_id!r} not found", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(render_json(spec), indent=2))
    elif as_prompt:
        click.echo(render_prompt(spec))
    else:
        path = loader.spec_path(scope, spec.id)
        click.echo(f"# {path}")
        click.echo(path.read_text(encoding="utf-8"))


# ─── edit (update fields without opening an editor) ───────────────────


@main.command()
@click.argument("spec_id")
@click.option("--add-input", multiple=True, help="Add input: path[:role]")
@click.option("--add-output", multiple=True, help="Add output: path[:check]")
@click.option("--add-check", multiple=True, help="Add check: command[:expect]")
@click.option(
    "--add-must-not-regress", multiple=True,
    help="Add a must-not-regress check: command[:expect]",
)
@click.option("--add-step", multiple=True, help="Append a step.")
@click.option("--context", default=None, help="Set context text.")
@click.option("--agent-cap", multiple=True, help="Add agent capability.")
@click.option("--agent-model", default=None, help="Set preferred model.")
@click.option("--depends-on", "depends_on", multiple=True, help="Add a spec id this spec is blocked on (repeatable).")
@_scope_options
def edit(
    spec_id: str,
    add_input: tuple,
    add_output: tuple,
    add_check: tuple,
    add_must_not_regress: tuple,
    add_step: tuple,
    context: str | None,
    agent_cap: tuple,
    agent_model: str | None,
    depends_on: tuple,
    global_: bool,
    project_: bool,
):
    """Add inputs, outputs, checks, steps to an existing spec."""
    scope = _pick_scope(global_, project_)
    try:
        spec = loader.load(scope, spec_id)
    except FileNotFoundError:
        click.echo(f"error: spec {spec_id!r} not found", err=True)
        sys.exit(1)

    for raw in add_input:
        path, _, role = raw.partition(":")
        spec.inputs.append(InputFile(path=path.strip(), role=role.strip()))
    for raw in add_output:
        path, _, check = raw.partition(":")
        spec.outputs.append(OutputFile(path=path.strip(), check=check.strip()))
    for raw in add_check:
        cmd, _, expect = raw.partition(":")
        spec.checks.append(Check(run=cmd.strip(), expect=expect.strip() or "exit 0"))
    for raw in add_must_not_regress:
        cmd, _, expect = raw.partition(":")
        spec.must_not_regress.append(
            Check(run=cmd.strip(), expect=expect.strip() or "exit 0")
        )
    for step in add_step:
        spec.steps.append(step.strip())
    if context is not None:
        spec.context = context
    for cap in agent_cap:
        if cap not in spec.agent.capabilities:
            spec.agent.capabilities.append(cap)
    if agent_model is not None:
        spec.agent.model = agent_model

    if depends_on:
        proposed = list(spec.depends_on)
        for dep_id in depends_on:
            dep_id = dep_id.strip()
            if dep_id and dep_id not in proposed:
                proposed.append(dep_id)
        if spec.id in proposed:
            click.echo(f"error: spec {spec.id!r} cannot depend on itself", err=True)
            sys.exit(1)
        cycle = loader.find_cycle(scope, spec.id, proposed)
        if cycle is not None:
            click.echo(
                f"error: adding this dependency would create a cycle: "
                f"{' -> '.join(cycle)}",
                err=True,
            )
            sys.exit(1)
        spec.depends_on = proposed

    loader.save(scope, spec)
    click.echo(f"{spec.id}  updated")


# ─── status transitions ──────────────────────────────────────────────


@main.command()
@click.argument("spec_id")
@_scope_options
def ready(spec_id: str, global_: bool, project_: bool):
    """Mark a spec as ready for execution."""
    scope = _pick_scope(global_, project_)
    try:
        spec = loader.transition(scope, spec_id, "ready")
    except ValueError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)
    click.echo(f"{spec.id}  ready")


@main.command()
@click.argument("spec_id")
@_scope_options
def run(spec_id: str, global_: bool, project_: bool):
    """Mark a spec as running and print the agent prompt."""
    scope = _pick_scope(global_, project_)
    spec = loader.transition(scope, spec_id, "running")
    click.echo(render_prompt(spec))


@main.command()
@click.argument("spec_id")
@_scope_options
def done(spec_id: str, global_: bool, project_: bool):
    """Mark a spec as done."""
    scope = _pick_scope(global_, project_)
    spec = loader.transition(scope, spec_id, "done")
    click.echo(f"{spec.id}  done")


@main.command()
@click.argument("spec_id")
@_scope_options
def fail(spec_id: str, global_: bool, project_: bool):
    """Mark a spec as failed (can be retried via ready)."""
    scope = _pick_scope(global_, project_)
    spec = loader.transition(scope, spec_id, "failed")
    click.echo(f"{spec.id}  failed")


@main.command()
@click.argument("spec_id")
@_scope_options
def abandon(spec_id: str, global_: bool, project_: bool):
    """Abandon a spec."""
    scope = _pick_scope(global_, project_)
    spec = loader.transition(scope, spec_id, "abandoned")
    click.echo(f"{spec.id}  abandoned")


# ─── validate ─────────────────────────────────────────────────────────


def _run_check_detailed(chk):
    """Run one Check, returning (passed, detail, (stdout, stderr, exit_code, message)).

    `detail` is the short human-readable line printed to stdout; the trailing
    tuple carries the full captured output for `FailureCheck` records so a
    failed `validate` leaves the next agent an exact trail (stdout/stderr/exit
    code), not just a pass/fail line.
    """
    import subprocess

    try:
        result = subprocess.run(
            chk.run, shell=True, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else ""
        stderr = (e.stderr or "") if isinstance(e.stderr, str) else ""
        return False, "timeout", (stdout, stderr, None, "timed out after 120s")

    expect_code = 0
    if chk.expect.startswith("exit "):
        expect_code = int(chk.expect.split()[1])
    if result.returncode == expect_code:
        return True, f"exit {result.returncode}", (result.stdout, result.stderr, result.returncode, "")
    detail = f"exit {result.returncode} (expected {expect_code})"
    if result.stderr.strip():
        detail += "\n" + "\n".join(
            f"    {line}" for line in result.stderr.strip().splitlines()[:5]
        )
    message = f"exit {result.returncode} (expected {expect_code})"
    return False, detail, (result.stdout, result.stderr, result.returncode, message)


@main.command()
@click.argument("spec_id")
@click.option("--json", "as_json", is_flag=True, help="Emit a structured JSON breakdown.")
@_scope_options
def validate(spec_id: str, as_json: bool, global_: bool, project_: bool):
    """Check a spec's completion criteria: outputs, must_pass, and must_not_regress.

    `must_pass` (aka the legacy flat `checks` field) are checks that must
    newly succeed. `must_not_regress` are checks that were passing before
    this change and must still pass after it — a regression contract
    (SWE-bench's FAIL_TO_PASS / PASS_TO_PASS split). Output is a structured
    breakdown per category so failures are unambiguous about which contract
    they broke.

    On failure, the full stdout/stderr/exit code of every failing check is
    captured into ``spec.last_failure`` (not just pass/fail) so the next
    ``run`` after a failed → ready retry sees exactly what broke. A clean
    pass clears any stale ``last_failure`` from a previous attempt.
    """
    from datetime import datetime, timezone
    from pathlib import Path

    scope = _pick_scope(global_, project_)
    try:
        spec = loader.load(scope, spec_id)
    except FileNotFoundError:
        click.echo(f"error: spec {spec_id!r} not found", err=True)
        sys.exit(1)

    # results: check/output label -> {category, passed, output}
    results: dict[str, dict] = {}
    passed = 0
    failed = 0
    failure_checks: list[FailureCheck] = []

    for out in spec.outputs:
        label = f"output:{out.path}"
        p = Path(out.path)
        if not p.exists():
            results[label] = {
                "category": "output", "passed": False, "output": "missing",
            }
            click.echo(f"  FAIL  [output]  output missing: {out.path}")
            failed += 1
            failure_checks.append(FailureCheck(
                kind="output", target=out.path, message="output file missing",
            ))
            continue
        if out.check:
            content = p.read_text(encoding="utf-8", errors="replace")
            if out.check.startswith("contains "):
                needle = out.check[9:].strip().strip('"').strip("'")
                if needle in content:
                    results[label] = {
                        "category": "output", "passed": True,
                        "output": f"contains {needle!r}",
                    }
                    click.echo(f"  PASS  [output]  {out.path}: contains {needle!r}")
                    passed += 1
                else:
                    results[label] = {
                        "category": "output", "passed": False,
                        "output": f"missing {needle!r}",
                    }
                    click.echo(f"  FAIL  [output]  {out.path}: missing {needle!r}")
                    failed += 1
                    failure_checks.append(FailureCheck(
                        kind="output", target=out.path,
                        message=f"expected to contain {needle!r} but did not",
                        stdout=content[:2000],
                    ))
            else:
                click.echo(f"  SKIP  [output]  {out.path}: unknown check syntax {out.check!r}")
        else:
            results[label] = {"category": "output", "passed": True, "output": "exists"}
            click.echo(f"  PASS  [output]  {out.path}: exists")
            passed += 1

    def _run_category(checks, category: str, *, regression: bool = False) -> None:
        nonlocal passed, failed
        for chk in checks:
            label = f"{category}:{chk.run}"
            ok, detail, run_result = _run_check_detailed(chk)
            results[label] = {"category": category, "passed": ok, "output": detail}
            if ok:
                click.echo(f"  PASS  [{category}]  `{chk.run}` → {detail}")
                passed += 1
            else:
                prefix = "REGRESSION: " if regression else ""
                click.echo(f"  FAIL  [{category}]  `{chk.run}` → {prefix}{detail}")
                failed += 1
                stdout, stderr, exit_code, message = run_result
                failure_checks.append(FailureCheck(
                    kind="check", target=chk.run, message=message,
                    stdout=stdout, stderr=stderr, exit_code=exit_code,
                ))

    _run_category(spec.must_pass, "must_pass")
    _run_category(spec.must_not_regress, "must_not_regress", regression=True)

    if as_json:
        click.echo(json.dumps(results, indent=2))
    else:
        must_pass_failed = sum(
            1 for r in results.values() if r["category"] == "must_pass" and not r["passed"]
        )
        regressions = sum(
            1 for r in results.values()
            if r["category"] == "must_not_regress" and not r["passed"]
        )
        click.echo(f"\n{passed} passed, {failed} failed"
                   f" ({must_pass_failed} must_pass failures, {regressions} regressions)")

    if failed:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        spec.last_failure = Failure(timestamp=now, checks=failure_checks)
        loader.save(scope, spec)

        click.echo("\nwhy validation failed:")
        for c in failure_checks:
            detail = f"  - [{c.kind}] {c.target}: {c.message}"
            if c.exit_code is not None:
                detail += f" (exit {c.exit_code})"
            click.echo(detail)
    elif spec.last_failure is not None:
        # Clean pass — drop the stale record from a previous attempt.
        spec.last_failure = None
        loader.save(scope, spec)

    sys.exit(1 if failed else 0)


# ─── templates ────────────────────────────────────────────────────────


@main.command("templates")
def list_templates():
    """List available spec templates."""
    for tpl in templates.list_templates():
        click.echo(f"  {tpl.name:<14} {tpl.description}")


# ─── init ─────────────────────────────────────────────────────────────


@main.command()
@click.option("--name", default="", help="Project name (defaults to directory name).")
@click.option("--description", default="", help="One-line project description.")
@_scope_options
def init(name: str, description: str, global_: bool, project_: bool):
    """Initialize .specs/ with VISION.md, TENETS.md, GOALS.md, features/."""
    from pathlib import Path
    from geno_specs import scaffold

    repo_root = Path.cwd()
    if not name:
        name = repo_root.name

    root = scaffold.scaffold(repo_root, name=name, description=description)
    click.echo(f"Initialized {root}")
    click.echo(f"  VISION.md  TENETS.md  GOALS.md  features/")

    if project_:
        target_dir = repo_root / "geno" / "geno-specs"
        target = Scope("project", target_dir)
        ensure_structure(target)
        click.echo(f"Also initialized execution scope at {target.dir}")
    elif global_:
        from geno_specs.paths import GLOBAL_DIR
        target = Scope("global", GLOBAL_DIR)
        ensure_structure(target)
        click.echo(f"Also initialized execution scope at {target.dir}")


@main.command()
@click.argument("name", nargs=-1, required=True)
@click.option("--description", "-d", default="", help="Feature description.")
def feature(name: tuple, description: str):
    """Create a feature spec in .specs/features/."""
    from pathlib import Path
    from geno_specs import scaffold

    feature_name = " ".join(name).strip()
    try:
        path = scaffold.create_feature_spec(Path.cwd(), feature_name, description)
        click.echo(f"Created {path}")
    except FileExistsError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
