"""Render a Spec to an agent prompt (recursive) or a JSON mirror.

Both delegate to the Node tree: `render_prompt` recurses via `nodes.render`, so
a self-contained prompt for an arbitrarily nested spec (sub-specs and all)
falls out with no special-casing.
"""

from __future__ import annotations

from typing import Any

from geno_specs import loader, nodes
from geno_specs.models import Spec, to_dict


def render_prompt(spec: Spec) -> str:
    """A self-contained agent prompt built by recursing the node tree."""
    root = loader.spec_to_node(spec)
    return nodes.render(root)


def render_json(spec: Spec) -> dict[str, Any]:
    """Flat machine mirror + a nested ``tree`` view of the same spec."""
    d = to_dict(spec)
    d["tree"] = nodes.to_dict(loader.spec_to_node(spec))
    return d
