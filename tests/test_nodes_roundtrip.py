"""Round-trip + nesting fidelity for the Node model."""

from __future__ import annotations

from geno_specs import nodes
from geno_specs.nodes import Node


def _structural(node: Node):
    """A comparable, comment-free shape of a node tree."""
    return (
        node.type,
        node.id,
        node.data,
        [_structural(c) for c in node.children],
    )


def test_flat_spec_roundtrip():
    text = """\
name: fix login
status: draft
description: broken token refresh
tags: [auth, bug]
inputs:
  - path: auth.py
    role: token module
outputs:
  - path: auth.py
    check: "contains refresh"
steps:
  - reproduce
  - fix
acceptance:
  - passes
checks:
  - run: pytest
    expect: exit 0
"""
    root = nodes._parse(text)
    assert root.type == "spec"
    assert root.data["title"] == "fix login"
    again = nodes._parse(nodes._dump(root))
    assert _structural(root) == _structural(again)


def test_nested_subspec_roundtrip():
    text = """\
name: adw-layer
status: draft
description: umbrella
phases:
  - id: p0
    title: Decide
    goal: resolve questions
    gates: [p1]
    done: false
subspecs:
  - name: geno-grams
    status: draft
    description: diagramming
    steps:
      - define IR
    subspecs:
      - name: rung-1
        status: draft
        steps: [ascii]
  - ref: ../other.genospecs.yaml
"""
    root = nodes._parse(text)
    subspecs = [c for c in root.children if c.type == "subspec"]
    assert len(subspecs) == 2
    # first subspec nests a spec with its own subspec
    inner = subspecs[0].children[0]
    assert inner.type == "spec" and inner.data["title"] == "geno-grams"
    assert any(c.type == "subspec" for c in inner.children)
    # second is a ref
    assert subspecs[1].data.get("ref") == "../other.genospecs.yaml"
    # round-trip stable
    again = nodes._parse(nodes._dump(root))
    assert _structural(root) == _structural(again)


def test_unknown_key_preserved_as_raw():
    text = "name: x\nstatus: draft\nweird_field:\n  - a\n  - b\n"
    root = nodes._parse(text)
    raws = [c for c in root.children if c.type == "raw"]
    assert raws and raws[0].data["key"] == "weird_field"
    # survives round-trip
    dumped = nodes._dump(root)
    assert "weird_field" in dumped


def test_new_section_type_needs_no_core_edit():
    """Registering a section = one call; parse/dump/render dispatch to it."""
    nodes.register("risks", nodes.Handler(
        parse=lambda v: Node("risks", data={"items": list(v or [])}),
        dump=lambda n: list(n.data.get("items", [])),
        render=lambda n: "## Risks\n" + "\n".join(f"- {r}" for r in n.data["items"]),
    ))
    try:
        text = "name: x\nstatus: draft\nrisks:\n  - data loss\n  - cost\n"
        root = nodes._parse(text)
        risks = [c for c in root.children if c.type == "risks"]
        assert risks and risks[0].data["items"] == ["data loss", "cost"]
        assert "Risks" in nodes.render(risks[0])
    finally:
        nodes.REGISTRY.pop("risks", None)
