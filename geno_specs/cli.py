"""geno-specs — click CLI."""

from __future__ import annotations

import json
import sys

import click

from geno_specs import __version__, loader, templates
from geno_specs.models import InputFile, OutputFile, Check, AgentRequirements, VALID_STATUSES
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
@_scope_options
def create(
    title: tuple,
    tags: tuple,
    tpl_name: str | None,
    context: str,
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
    )
    click.echo(f"{spec.id}  (draft)")
    click.echo(f"  {loader.spec_path(scope, spec.id)}")


# ─── list ─────────────────────────────────────────────────────────────


@main.command("list")
@click.option("--status", "-s", default=None, help="Filter by status.")
@click.option("--tag", default=None, help="Filter by tag.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@_scope_options
def list_cmd(status: str | None, tag: str | None, as_json: bool, global_: bool, project_: bool):
    """List specs."""
    scope = _pick_scope(global_, project_)
    specs = loader.load_all(scope)

    if status:
        specs = [s for s in specs if s.status == status]
    if tag:
        specs = [s for s in specs if tag in s.tags]

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
@click.option("--add-step", multiple=True, help="Append a step.")
@click.option("--context", default=None, help="Set context text.")
@click.option("--agent-cap", multiple=True, help="Add agent capability.")
@click.option("--agent-model", default=None, help="Set preferred model.")
@_scope_options
def edit(
    spec_id: str,
    add_input: tuple,
    add_output: tuple,
    add_check: tuple,
    add_step: tuple,
    context: str | None,
    agent_cap: tuple,
    agent_model: str | None,
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
    for step in add_step:
        spec.steps.append(step.strip())
    if context is not None:
        spec.context = context
    for cap in agent_cap:
        if cap not in spec.agent.capabilities:
            spec.agent.capabilities.append(cap)
    if agent_model is not None:
        spec.agent.model = agent_model

    loader.save(scope, spec)
    click.echo(f"{spec.id}  updated")


# ─── status transitions ──────────────────────────────────────────────


@main.command()
@click.argument("spec_id")
@_scope_options
def ready(spec_id: str, global_: bool, project_: bool):
    """Mark a spec as ready for execution."""
    scope = _pick_scope(global_, project_)
    spec = loader.transition(scope, spec_id, "ready")
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


@main.command()
@click.argument("spec_id")
@_scope_options
def validate(spec_id: str, global_: bool, project_: bool):
    """Check a spec's completion criteria (output checks + validation commands)."""
    import subprocess
    from pathlib import Path

    scope = _pick_scope(global_, project_)
    try:
        spec = loader.load(scope, spec_id)
    except FileNotFoundError:
        click.echo(f"error: spec {spec_id!r} not found", err=True)
        sys.exit(1)

    passed = 0
    failed = 0

    for out in spec.outputs:
        p = Path(out.path)
        if not p.exists():
            click.echo(f"  FAIL  output missing: {out.path}")
            failed += 1
            continue
        if out.check:
            content = p.read_text(encoding="utf-8", errors="replace")
            if out.check.startswith("contains "):
                needle = out.check[9:].strip().strip('"').strip("'")
                if needle in content:
                    click.echo(f"  PASS  {out.path}: contains {needle!r}")
                    passed += 1
                else:
                    click.echo(f"  FAIL  {out.path}: missing {needle!r}")
                    failed += 1
            else:
                click.echo(f"  SKIP  {out.path}: unknown check syntax {out.check!r}")
        else:
            click.echo(f"  PASS  {out.path}: exists")
            passed += 1

    for chk in spec.checks:
        try:
            result = subprocess.run(
                chk.run, shell=True, capture_output=True, text=True, timeout=120,
            )
            expect_code = 0
            if chk.expect.startswith("exit "):
                expect_code = int(chk.expect.split()[1])
            if result.returncode == expect_code:
                click.echo(f"  PASS  `{chk.run}` → exit {result.returncode}")
                passed += 1
            else:
                click.echo(f"  FAIL  `{chk.run}` → exit {result.returncode} (expected {expect_code})")
                if result.stderr.strip():
                    for line in result.stderr.strip().splitlines()[:5]:
                        click.echo(f"         {line}")
                failed += 1
        except subprocess.TimeoutExpired:
            click.echo(f"  FAIL  `{chk.run}` → timeout")
            failed += 1

    click.echo(f"\n{passed} passed, {failed} failed")
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
@click.option(
    "--fill", is_flag=True,
    help="Draft real content into VISION/TENETS/GOALS from README.md and git log "
         "instead of leaving bare placeholders.",
)
@_scope_options
def init(name: str, description: str, fill: bool, global_: bool, project_: bool):
    """Initialize .specs/ with VISION.md, TENETS.md, GOALS.md, features/."""
    from pathlib import Path
    from geno_specs import scaffold

    repo_root = Path.cwd()
    if not name:
        name = repo_root.name

    root = scaffold.scaffold(repo_root, name=name, description=description, fill=fill)
    click.echo(f"Initialized {root}")
    if fill:
        click.echo(f"  VISION.md  TENETS.md  GOALS.md  features/  (drafted from README + git log — review before trusting)")
    else:
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
