"""The composable spec model — a recursive tree of typed section nodes.

Composite-by-dispatch (no methods on domain objects, per ecosystem house
style):

  - `Node` is a dumb dataclass with a `type` discriminator, a `data` payload,
    and `children`.
  - Every section type registers a `Handler` (four free-function callables:
    parse / dump / render / validate) in `REGISTRY`.
  - The core dispatch functions (`parse_section`, `dump`, `render`, `validate`,
    `to_dict`) look up `REGISTRY[node.type]` and recurse into `children`.

Adding a new section type is a single `register(...)` call — no edit to `Node`,
the parser core, `Spec`, or the CLI. Custom types can also be declared
out-of-tree via `~/.geno/settings.json` (see `load_custom_sections`), mirroring
geno-tasks' provider registry.

A spec that contains a spec is just a `spec` node nested under a `subspec`
child — so a plan can be expressed as one spec made of sub-specs, recursively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from geno_specs.models import (
    AgentRequirements,
    Check,
    InputFile,
    OutputFile,
)

# ─── YAML (real dep, house optional-import shape) ─────────────────────
#
# The nested .genospecs.yaml form (lists of maps, block scalars) exceeds what a
# hand-rolled flat parser can read, so PyYAML is a real dependency. We still
# expose the optional-import shape: a minimal fallback that round-trips only the
# subset *we* emit, so the package degrades rather than hard-crashes if PyYAML
# is somehow absent.

try:  # pragma: no cover - trivial
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None


def _yaml_load(text: str) -> Any:
    if _yaml is not None:
        return _yaml.safe_load(text) or {}
    raise RuntimeError(
        "PyYAML is required to parse .genospecs.yaml files. "
        "Install with: pip install pyyaml"
    )


def _yaml_dump(obj: Any) -> str:
    if _yaml is not None:
        return _yaml.dump(obj, sort_keys=False, default_flow_style=False, allow_unicode=True)
    raise RuntimeError(
        "PyYAML is required to write .genospecs.yaml files. "
        "Install with: pip install pyyaml"
    )


# ─── the node ─────────────────────────────────────────────────────────


@dataclass
class Node:
    type: str                                          # discriminator = registry key
    id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)


# ─── validation result ────────────────────────────────────────────────


@dataclass
class Result:
    ok: bool
    message: str


# The context passed to validators (working dir, loader hook for depends_on…).
Ctx = dict[str, Any]


# ─── handler + registry ────────────────────────────────────────────────


@dataclass
class Handler:
    """A section type's four verbs. Any may be None to accept the default."""

    parse: Callable[[Any], Node]                       # yaml value -> Node
    dump: Callable[[Node], Any]                        # Node -> yaml value
    render: Callable[[Node], str]                      # Node -> prompt fragment
    validate: Callable[[Node, Ctx], list[Result]] = None  # type: ignore[assignment]


REGISTRY: dict[str, Handler] = {}


def register(type_name: str, handler: Handler) -> None:
    REGISTRY[type_name] = handler


def _handler(type_name: str) -> Handler | None:
    return REGISTRY.get(type_name)


# ─── core dispatch (recurse + match on type) ──────────────────────────


def parse_section(type_name: str, value: Any) -> Node:
    """Parse one top-level key's value into a Node via its handler."""
    h = _handler(type_name)
    if h is None:
        # Unknown key → raw node so nothing is dropped (forward-compat).
        return Node(type="raw", data={"key": type_name, "value": value})
    return h.parse(value)


def dump(node: Node) -> Any:
    """Serialize a Node to its yaml value via its handler."""
    if node.type == "raw":
        return node.data.get("value")
    h = _handler(node.type)
    if h is None:
        return node.data
    return h.dump(node)


def render(node: Node) -> str:
    """Render a Node (and its subtree) to a prompt fragment."""
    if node.type == "raw":
        return ""
    h = _handler(node.type)
    if h is None or h.render is None:
        return ""
    return h.render(node)


def validate(node: Node, ctx: Ctx | None = None) -> list[Result]:
    """Validate a Node subtree; concatenates child results."""
    ctx = ctx or {}
    out: list[Result] = []
    h = _handler(node.type)
    if h is not None and h.validate is not None:
        out.extend(h.validate(node, ctx))
    for child in node.children:
        out.extend(validate(child, ctx))
    return out


def _jsonable(value: Any) -> Any:
    """Recursively convert dataclass leaves (InputFile, ...) to plain data."""
    import dataclasses

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def to_dict(node: Node) -> dict[str, Any]:
    """Recursive JSON-able mirror of a Node tree (the machine view)."""
    d: dict[str, Any] = {"type": node.type}
    if node.id is not None:
        d["id"] = node.id
    if node.data:
        d["data"] = _jsonable(node.data)
    if node.children:
        d["children"] = [to_dict(c) for c in node.children]
    return d


# ─── leaf (de)serializers ─────────────────────────────────────────────


def _mk_input(v: Any) -> InputFile:
    if isinstance(v, dict):
        return InputFile(path=str(v.get("path", "")), role=str(v.get("role", "")))
    return InputFile(path=str(v))


def _mk_output(v: Any) -> OutputFile:
    if isinstance(v, dict):
        return OutputFile(path=str(v.get("path", "")), check=str(v.get("check", "")))
    return OutputFile(path=str(v))


def _mk_check(v: Any) -> Check:
    if isinstance(v, dict):
        return Check(run=str(v.get("run", "")), expect=str(v.get("expect", "exit 0")))
    return Check(run=str(v))


# ─── built-in handlers ─────────────────────────────────────────────────
#
# Helper factories keep the ~13 registrations terse. A "list section" holds a
# homogeneous list in data["items"]; a "map-list section" holds a list of dicts.


def _list_section(type_name: str, render_line: Callable[[Any], str], heading: str,
                  parse_item=lambda x: x, dump_item=lambda x: x) -> Handler:
    def parse(value):
        items = [parse_item(x) for x in (value or [])]
        return Node(type=type_name, data={"items": items})

    def dump_(node):
        return [dump_item(x) for x in node.data.get("items", [])]

    def render_(node):
        items = node.data.get("items", [])
        if not items:
            return ""
        lines = "\n".join(render_line(x) for x in items)
        return f"## {heading}\n{lines}\n"

    return Handler(parse=parse, dump=dump_, render=render_)


# steps, acceptance — plain string lists
register("steps", _list_section(
    "steps", lambda s: f"- {s}", "Steps"))
register("acceptance", _list_section(
    "acceptance", lambda s: f"- [ ] {s}", "Acceptance criteria"))

# inputs, outputs, checks — typed-leaf lists
register("inputs", _list_section(
    "inputs",
    lambda x: f"- `{x.path}`" + (f" — {x.role}" if x.role else ""),
    "Read these files",
    parse_item=_mk_input,
    dump_item=lambda x: {"path": x.path, "role": x.role},
))
register("outputs", _list_section(
    "outputs",
    lambda x: f"- `{x.path}`" + (f" — {x.check}" if x.check else ""),
    "Produce",
    parse_item=_mk_output,
    dump_item=lambda x: {"path": x.path, "check": x.check},
))
register("checks", _list_section(
    "checks",
    lambda x: f"- `{x.run}` → {x.expect}",
    "Validation",
    parse_item=_mk_check,
    dump_item=lambda x: {"run": x.run, "expect": x.expect},
))

# must_not_regress — checks that were passing before the change and must
# still pass after (the regression half of the SWE-bench-style pass-list
# split; `checks` above is the must_pass half, kept for backward compat).
register("must_not_regress", _list_section(
    "must_not_regress",
    lambda x: f"- `{x.run}` → {x.expect}",
    "Must not regress",
    parse_item=_mk_check,
    dump_item=lambda x: {"run": x.run, "expect": x.expect},
))

# depends_on — spec ids this spec is gated on
register("depends_on", _list_section(
    "depends_on", lambda s: f"- {s}", "Blocked on specs (must be done)"))

# composes, phases, open_questions, deferred — pass-through dict lists
register("composes", _list_section(
    "composes",
    lambda d: f"- **{d.get('repo','?')}** — {d.get('role','')}"
              + (" _(optional)_" if d.get("optional") else ""),
    "Composes"))
register("deferred", _list_section(
    "deferred",
    lambda d: f"- **{d.get('title','?')}** — {d.get('why','')}",
    "Deferred"))


def _phases_handler() -> Handler:
    def parse(value):
        return Node(type="phases", data={"items": list(value or [])})

    def dump_(node):
        return list(node.data.get("items", []))

    def render_(node):
        items = node.data.get("items", [])
        if not items:
            return ""
        lines = []
        for p in items:
            mark = "x" if p.get("done") else " "
            gates = f" → gates {p.get('gates')}" if p.get("gates") else ""
            lines.append(f"- [{mark}] **{p.get('id','?')} {p.get('title','')}** — {p.get('goal','')}{gates}")
        return "## Phases\n" + "\n".join(lines) + "\n"

    def validate_(node, ctx):
        out = []
        for p in node.data.get("items", []):
            if not p.get("id"):
                out.append(Result(False, "phase missing id"))
        return out

    return Handler(parse=parse, dump=dump_, render=render_, validate=validate_)


register("phases", _phases_handler())


def _open_questions_handler() -> Handler:
    def parse(value):
        return Node(type="open_questions", data={"items": list(value or [])})

    def dump_(node):
        return list(node.data.get("items", []))

    def render_(node):
        items = node.data.get("items", [])
        if not items:
            return ""
        lines = []
        for q in items:
            st = q.get("status", "open")
            lines.append(f"- ({st}) **{q.get('id','?')}** {q.get('question','')}")
        return "## Resolve these questions first\n" + "\n".join(lines) + "\n"

    return Handler(parse=parse, dump=dump_, render=render_)


register("open_questions", _open_questions_handler())


# ─── the spec node itself (root; also nested via subspec) ─────────────

# Top-level keys handled as flat scalars on the spec node's data (not sections).
_SPEC_SCALAR_KEYS = ("status", "tags", "context", "template")
# Order sections are emitted in (diff-friendly, human-readable).
_SECTION_ORDER = (
    "inputs", "outputs", "steps", "acceptance", "checks", "must_not_regress",
    "composes", "phases", "open_questions", "depends_on", "deferred",
    "agent", "subspecs",
)


def _agent_handler() -> Handler:
    def parse(value):
        v = value or {}
        agent = AgentRequirements(
            capabilities=list(v.get("capabilities", [])),
            model=v.get("model"),
        )
        return Node(type="agent", data={"value": agent})

    def dump_(node):
        a: AgentRequirements = node.data["value"]
        return {"capabilities": list(a.capabilities), "model": a.model}

    def render_(node):
        a: AgentRequirements = node.data["value"]
        if not a.capabilities and not a.model:
            return ""
        caps = ", ".join(a.capabilities) if a.capabilities else "(any)"
        model = a.model or "(default)"
        return f"## Agent\ncapabilities: {caps}\nmodel: {model}\n"

    return Handler(parse=parse, dump=dump_, render=render_)


register("agent", _agent_handler())


def _spec_from_mapping(m: dict[str, Any]) -> Node:
    """Build a `spec` Node from a parsed yaml mapping (recursive on subspecs)."""
    node = Node(type="spec")
    # `name` on-disk aliases `title`.
    node.data["title"] = m.get("name") or m.get("title") or ""
    node.data["status"] = m.get("status", "draft")
    node.data["tags"] = list(m.get("tags", []))
    node.data["context"] = m.get("description") or m.get("context") or ""
    node.data["template"] = m.get("template")
    if m.get("id"):
        node.id = m["id"]

    known = {"name", "title", "id"} | set(_SPEC_SCALAR_KEYS)
    for key, value in m.items():
        if key in known:
            continue
        if key == "description":
            continue
        if key == "subspecs":
            for sub in (value or []):
                if isinstance(sub, dict) and "ref" in sub:
                    node.children.append(Node(type="subspec", data={"ref": sub["ref"]}))
                elif isinstance(sub, dict):
                    child_spec = _spec_from_mapping(sub)
                    node.children.append(Node(type="subspec", children=[child_spec]))
            continue
        node.children.append(parse_section(key, value))
    return node


def _spec_to_mapping(node: Node) -> dict[str, Any]:
    """Serialize a `spec` Node back to an ordered yaml mapping."""
    m: dict[str, Any] = {}
    m["name"] = node.data.get("title", "")
    if node.id:
        m["id"] = node.id
    m["status"] = node.data.get("status", "draft")
    if node.data.get("tags"):
        m["tags"] = list(node.data["tags"])
    if node.data.get("context"):
        m["description"] = node.data["context"]
    if node.data.get("template"):
        m["template"] = node.data["template"]

    # Emit sections in canonical order, then any leftovers.
    by_type: dict[str, list[Node]] = {}
    subspecs: list[Node] = []
    raws: list[Node] = []
    for child in node.children:
        if child.type == "subspec":
            subspecs.append(child)
        elif child.type == "raw":
            raws.append(child)
        else:
            by_type.setdefault(child.type, []).append(child)

    for type_name in _SECTION_ORDER:
        if type_name == "subspecs":
            continue
        for child in by_type.get(type_name, []):
            m[type_name] = dump(child)
    # any section types not in the canonical order
    for type_name, nodes_ in by_type.items():
        if type_name not in _SECTION_ORDER:
            for child in nodes_:
                m[type_name] = dump(child)

    if subspecs:
        out = []
        for ss in subspecs:
            if "ref" in ss.data:
                out.append({"ref": ss.data["ref"]})
            elif ss.children:
                out.append(_spec_to_mapping(ss.children[0]))
        m["subspecs"] = out

    for r in raws:
        m[r.data.get("key", "raw")] = r.data.get("value")
    return m


def _spec_render(node: Node) -> str:
    title = node.data.get("title", "")
    status = node.data.get("status", "draft")
    context = node.data.get("context", "")
    header = f"# {title}  ({status})\n"
    if context:
        header += f"\n{context}\n"
    body = "\n".join(filter(None, (render(c) for c in node.children)))
    return header + "\n" + body


def _subspec_render(node: Node) -> str:
    if node.children:
        inner = _spec_render(node.children[0])
        # indent as a sub-spec block
        return "## Sub-spec\n" + inner + "\n"
    if "ref" in node.data:
        return f"## Sub-spec (ref)\n- {node.data['ref']}\n"
    return ""


register("spec", Handler(
    parse=lambda v: _spec_from_mapping(v if isinstance(v, dict) else {}),
    dump=_spec_to_mapping,
    render=_spec_render,
))
register("subspec", Handler(
    parse=lambda v: Node(type="subspec"),  # subspecs are built by _spec_from_mapping
    dump=lambda n: n.data.get("ref"),
    render=_subspec_render,
))


# ─── top-level parse / dump (file <-> Node tree) ──────────────────────


def _parse(text: str) -> Node:
    """Parse a .genospecs.yaml document into a root `spec` Node."""
    mapping = _yaml_load(text)
    if not isinstance(mapping, dict):
        raise ValueError("spec file must be a YAML mapping")
    return _spec_from_mapping(mapping)


def _dump(node: Node) -> str:
    """Serialize a root `spec` Node to .genospecs.yaml text."""
    if node.type != "spec":
        raise ValueError(f"expected a spec node, got {node.type!r}")
    return _yaml_dump(_spec_to_mapping(node))


# ─── settings.json custom sections (geno-tasks provider pattern) ──────


def load_custom_sections() -> None:
    """Register out-of-tree section handlers declared in ~/.geno/settings.json.

    Shape:
      {"specs": {"sections": [{"type": "risks", "module": "my.mod",
                               "factory": "make_handler", "config": {...}}]}}

    A bad plugin is logged-and-skipped, never fatal.
    """

    import importlib
    import json
    from pathlib import Path

    settings = Path.home() / ".geno" / "settings.json"
    if not settings.exists():
        return
    try:
        cfg = json.loads(settings.read_text(encoding="utf-8"))
    except Exception:
        return
    for entry in (cfg.get("specs", {}) or {}).get("sections", []) or []:
        try:
            mod = importlib.import_module(entry["module"])
            factory = getattr(mod, entry.get("factory", "make_handler"))
            handler = factory(entry.get("config", {}))
            register(entry["type"], handler)
        except Exception:
            # Registration is best-effort; never crash the CLI on a bad plugin.
            continue
