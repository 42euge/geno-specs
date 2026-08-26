"""geno-specs — MCP server.

Exposes geno-specs's core lifecycle commands as MCP tools over stdio, so any
MCP-aware agent client (Cursor, Codex, Claude Code, etc.) can create, list,
inspect, and drive specs through the same underlying `loader`/`renderer`/
`validator` functions the CLI (`cli.py`) calls — no business logic is
duplicated here, this module is a thin adapter.
"""

from __future__ import annotations


from mcp.server.fastmcp import FastMCP

from geno_specs import loader, templates, validator
from geno_specs.paths import ensure_structure, resolve_scope
from geno_specs.renderer import render_json, render_prompt

mcp = FastMCP("geno-specs")


def _scope(scope: str | None = None):
    """Resolve a Scope from an optional "global"|"project" override string."""
    resolved = resolve_scope(override=scope)
    ensure_structure(resolved)
    return resolved


@mcp.tool()
def create_spec(
    title: str,
    template: str | None = None,
    tags: list[str] | None = None,
    context: str = "",
    scope: str | None = None,
) -> dict:
    """Create a new spec (status: draft).

    Args:
        title: Spec title.
        template: Optional built-in template name (see `templates` list).
        tags: Optional list of tags.
        context: Optional context/description text.
        scope: Optional scope override, "global" or "project".
    """
    sc = _scope(scope)

    steps: list[str] = []
    acceptance: list[str] = []
    merged_tags = list(tags or [])

    if template:
        tpl = templates.get(template)
        if not tpl:
            avail = ", ".join(t.name for t in templates.list_templates())
            raise ValueError(f"unknown template {template!r}. Available: {avail}")
        steps = list(tpl.steps)
        acceptance = list(tpl.acceptance)
        merged_tags = list(dict.fromkeys(merged_tags + tpl.tags))
        if not context:
            context = tpl.context_hint

    spec = loader.create(
        sc,
        title.strip(),
        tags=merged_tags,
        template=template,
        context=context,
        steps=steps,
        acceptance=acceptance,
    )
    return {"id": spec.id, "status": spec.status, "path": str(loader.spec_path(sc, spec.id))}


@mcp.tool()
def list_specs(
    status: str | None = None,
    tag: str | None = None,
    scope: str | None = None,
) -> list:
    """List specs, optionally filtered by status and/or tag.

    Args:
        status: Optional status filter (draft/ready/running/done/failed/abandoned).
        tag: Optional tag filter.
        scope: Optional scope override, "global" or "project".
    """
    sc = _scope(scope)
    specs = loader.load_all(sc)
    if status:
        specs = [s for s in specs if s.status == status]
    if tag:
        specs = [s for s in specs if tag in s.tags]
    return [render_json(s) for s in specs]


@mcp.tool()
def show_spec(spec_id: str, scope: str | None = None) -> dict:
    """Show a spec's full contents as JSON.

    Args:
        spec_id: The spec id, e.g. "20260426-fix-token-refresh".
        scope: Optional scope override, "global" or "project".
    """
    sc = _scope(scope)
    spec = loader.load(sc, spec_id)
    return render_json(spec)


@mcp.tool()
def mark_ready(spec_id: str, scope: str | None = None) -> dict:
    """Mark a spec as ready for execution (draft -> ready).

    Args:
        spec_id: The spec id.
        scope: Optional scope override, "global" or "project".
    """
    sc = _scope(scope)
    spec = loader.transition(sc, spec_id, "ready")
    return {"id": spec.id, "status": spec.status}


@mcp.tool()
def run_spec(spec_id: str, scope: str | None = None) -> dict:
    """Transition a spec to running and render its agent prompt.

    Args:
        spec_id: The spec id.
        scope: Optional scope override, "global" or "project".
    """
    sc = _scope(scope)
    spec = loader.transition(sc, spec_id, "running")
    return {"id": spec.id, "status": spec.status, "prompt": render_prompt(spec)}


@mcp.tool()
def validate_spec(spec_id: str, scope: str | None = None) -> dict:
    """Run a spec's completion checks and transition it to done/failed.

    Args:
        spec_id: The spec id.
        scope: Optional scope override, "global" or "project".
    """
    sc = _scope(scope)
    spec = loader.load(sc, spec_id)
    passed, failed, lines = validator.run_checks(spec)
    new_status = "failed" if failed else "done"
    try:
        spec = loader.transition(sc, spec_id, new_status)
    except ValueError:
        # Not in a state that can transition (e.g. still draft); report
        # results without forcing a status change.
        pass
    return {
        "id": spec.id,
        "status": spec.status,
        "passed": passed,
        "failed": failed,
        "report": lines,
    }


def main() -> None:
    """Console entry point — run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
