"""Golden fixture: the real ADW-layer spec must parse, render, round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from geno_specs import loader, nodes, renderer

ADW = (
    Path.home()
    / "code/side/geno/adw-layer.2026.q3/.specs/features/adw-layer.genospecs.yaml"
)

pytestmark = pytest.mark.skipif(not ADW.exists(), reason="ADW spec fixture not present")


def _items(root, type_name):
    for c in root.children:
        if c.type == type_name:
            return c.data.get("items", [])
    return []


def test_adw_parses_with_expected_counts():
    root = nodes._parse(ADW.read_text())
    assert root.data["title"] == "adw-layer"
    assert len(_items(root, "composes")) == 9
    assert len(_items(root, "phases")) == 5
    assert len(_items(root, "open_questions")) == 8
    assert len(_items(root, "deferred")) == 2


def test_adw_renders_and_json():
    spec = loader.node_to_spec(nodes._parse(ADW.read_text()))
    assert renderer.render_prompt(spec)
    j = renderer.render_json(spec)
    assert j["title"] == "adw-layer" and "tree" in j


def test_adw_roundtrip_structural():
    root = nodes._parse(ADW.read_text())
    again = nodes._parse(nodes._dump(root))
    assert len(root.children) == len(again.children)
    assert {c.type for c in root.children} == {c.type for c in again.children}
