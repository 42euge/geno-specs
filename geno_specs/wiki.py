"""LLM-wiki generation for specs.

Turns a set of specs into a linked markdown "wiki" that dives deep per feature:
one page per spec, expanding behaviour, UI, data flow, inputs/outputs, checks,
conventions and open questions into prose an agent (or human) can read to
understand *how the feature should work* — not just the terse spec fields.

Design: pure-stdlib, no LLM call required. It restructures the spec's own
content (including the free-form `children_extra` sections like `architecture`,
`geno_additions`, `critical_conventions`, `ui`, `acceptance`) into a readable
per-feature page, plus an index that cross-links features by shared tags and by
`depends_on` / `composes` references. The output drops straight into an MkDocs
`docs/` tree (or any markdown wiki).

If the spec carries rich nested sections (as the geno-desktop / bluegpt-desktop
specs do), each becomes its own titled wiki section with its sub-keys rendered
as definition lists — so "how the UI should work", "how routing works", etc.
surface as first-class, linkable content.
"""

from __future__ import annotations

import re
from typing import Any

from geno_specs.models import Spec, to_dict

# Sections we know how to title nicely; anything else is title-cased.
_SECTION_TITLES = {
    "context": "Overview",
    "architecture": "Architecture",
    "geno_additions": "Features & Surfaces",
    "critical_conventions": "Conventions & Gotchas",
    "ui": "How the UI Works",
    "behavior": "How It Should Behave",
    "data": "Data & State",
    "build": "Build & Run",
    "steps": "Implementation Steps",
    "iteration_plan": "Iteration Plan",
    "acceptance": "Acceptance Criteria",
    "checks": "Automated Checks",
    "inputs": "Inputs",
    "outputs": "Outputs",
    "open_questions": "Open Questions",
    "deferred": "Deferred / Out of Scope",
    "depends_on": "Depends On",
    "composes": "Composes",
    "lineage": "Lineage",
    "technologies": "Technologies",
    "white_label_todo": "White-label TODO",
}

# Section render order — the "deep dive" reads top-down like a design doc.
_ORDER = [
    "context", "lineage", "architecture", "technologies",
    "geno_additions", "ui", "behavior", "data",
    "steps", "iteration_plan",
    "critical_conventions", "build",
    "inputs", "outputs", "checks", "acceptance",
    "open_questions", "deferred", "depends_on", "composes",
]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _title_for(key: str) -> str:
    return _SECTION_TITLES.get(key, key.replace("_", " ").title())


def _render_value(value: Any, depth: int = 0) -> str:
    """Render an arbitrary spec value as readable markdown (recursive)."""
    pad = ""
    if isinstance(value, dict):
        lines: list[str] = []
        for k, v in value.items():
            label = f"**{k.replace('_', ' ')}**"
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}- {label}:")
                lines.append(_indent(_render_value(v, depth + 1), 2))
            else:
                lines.append(f"{pad}- {label}: {_scalar(v)}")
        return "\n".join(lines)
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                out.append(_indent(_render_value(item, depth + 1), 0))
                out.append("")
            else:
                out.append(f"- {_scalar(item)}")
        return "\n".join(out).rstrip()
    return _scalar(value)


def _scalar(v: Any) -> str:
    s = str(v)
    # Multi-line scalar (block text) -> keep line breaks as soft prose.
    if "\n" in s:
        return "  \n  ".join(s.splitlines())
    return s


def _indent(text: str, n: int) -> str:
    prefix = " " * n
    return "\n".join(prefix + ln if ln else ln for ln in text.split("\n"))


def _section_map(spec: Spec) -> dict[str, Any]:
    """Collect all renderable sections keyed by name.

    Merges the flat Spec fields with the free-form `children_extra` sections.
    Unknown top-level YAML keys are stored by the loader as `raw` nodes shaped
    `{key: <name>, value: <content>}`; unwrap those so `architecture`,
    `geno_additions`, `critical_conventions`, `build`, etc. become real,
    titled sections instead of an undifferentiated "Raw" dump.
    """
    sections: dict[str, Any] = {}
    if spec.context:
        sections["context"] = spec.context
    if spec.steps:
        sections["steps"] = list(spec.steps)
    if spec.acceptance:
        sections["acceptance"] = list(spec.acceptance)
    if spec.inputs:
        sections["inputs"] = [{"path": i.path, "role": i.role} for i in spec.inputs]
    if spec.outputs:
        sections["outputs"] = [{"path": o.path, "check": o.check} for o in spec.outputs]
    if spec.checks:
        # Only surface checks that actually carry a command — a spec using the
        # `command:`/`expect_exit:` shape (vs the model's `run`/`expect`) loads
        # as empty Check objects; skip those rather than print blank entries.
        rich = [{"run": c.run, "expect": c.expect} for c in spec.checks if c.run]
        if rich:
            sections["checks"] = rich

    for node in spec.children_extra:
        if node.type == "raw":
            key = node.data.get("key")
            val = node.data.get("value")
            if key:
                sections[str(key)] = val
        else:
            sections.setdefault(node.type, node.data.get("items", node.data))
    return sections


def render_feature_page(spec: Spec, *, all_ids: set[str] | None = None) -> str:
    """A deep, linked per-feature wiki page for one spec."""
    all_ids = all_ids or set()
    d = _section_map(spec)
    parts: list[str] = []

    parts.append(f"# {spec.title}")
    meta = f"`{spec.id}` · status: **{spec.status}**"
    if spec.tags:
        meta += " · tags: " + ", ".join(f"`{t}`" for t in spec.tags)
    parts.append(meta)
    parts.append("")

    seen: set[str] = set()

    def emit(key: str) -> None:
        if key in seen or key not in d:
            return
        val = d[key]
        if val in (None, "", [], {}):
            return
        seen.add(key)
        parts.append(f"## {_title_for(key)}")
        parts.append("")
        parts.append(_render_value(val))
        parts.append("")

    for key in _ORDER:
        emit(key)
    # Anything else the spec carries that we didn't order explicitly.
    for key in list(d):
        if key not in seen:
            emit(key)

    # Cross-links: any other spec id mentioned in this spec's text.
    linked = sorted(i for i in all_ids if i != spec.id and i in _flatten_text(d))
    if linked:
        parts.append("## Related Features")
        parts.append("")
        for i in linked:
            parts.append(f"- [{i}]({_slug(i)}.md)")
        parts.append("")

    parts.append("---")
    parts.append(f"_Generated from `{spec.id}.genospecs.yaml` by `geno-specs wiki`._")
    return "\n".join(parts).rstrip() + "\n"


def _flatten_text(d: dict[str, Any]) -> str:
    return " ".join(str(v) for v in _walk(d))


def _walk(v: Any):
    if isinstance(v, dict):
        for x in v.values():
            yield from _walk(x)
    elif isinstance(v, list):
        for x in v:
            yield from _walk(x)
    else:
        yield v


def render_index(specs: list[Spec]) -> str:
    """The wiki landing page: features grouped by tag, each linking to its page."""
    parts: list[str] = ["# Feature Wiki", ""]
    parts.append(
        "Deep-dive pages generated from specs — one per feature, expanding how "
        "each should work (behaviour, UI, data, conventions, acceptance)."
    )
    parts.append("")

    # Group by first tag (fallback: "untagged"), stable ordering.
    groups: dict[str, list[Spec]] = {}
    for s in specs:
        key = s.tags[0] if s.tags else "untagged"
        groups.setdefault(key, []).append(s)

    for tag in sorted(groups):
        parts.append(f"## {tag}")
        parts.append("")
        for s in sorted(groups[tag], key=lambda x: x.title):
            desc = (s.context or "").strip().splitlines()[0] if s.context else ""
            line = f"- [{s.title}]({_slug(s.id)}.md) — `{s.status}`"
            if desc:
                line += f" · {desc}"
            parts.append(line)
        parts.append("")

    parts.append("---")
    parts.append("_Generated by `geno-specs wiki`._")
    return "\n".join(parts).rstrip() + "\n"


def render_wiki(specs: list[Spec]) -> dict[str, str]:
    """Return {relative_path: markdown} for the whole wiki (index + one per spec)."""
    ids = {s.id for s in specs}
    out: dict[str, str] = {"index.md": render_index(specs)}
    for s in specs:
        out[f"{_slug(s.id)}.md"] = render_feature_page(s, all_ids=ids)
    return out
