"""CRUD, lifecycle transitions, and the Spec <-> Node bridge.

The Node tree (`nodes.py`) is the canonical form on disk and for
render/validate. `Spec` (`models.py`) is the flat, mutable surface the CLI
uses. This module owns the two bridge functions plus persistence (atomic write
under flock, per house style).
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import date
from pathlib import Path

from geno_specs import nodes
from geno_specs.locks import file_lock
from geno_specs.models import (
    AgentRequirements,
    Check,
    Failure,
    InputFile,
    OutputFile,
    Spec,
    VALID_STATUSES,
)
from geno_specs.nodes import Node
from geno_specs.paths import Scope

# Allowed lifecycle transitions (draft→ready→running→done, →failed→ready,
# any→abandoned).
_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "abandoned"},
    "ready": {"running", "abandoned"},
    "running": {"done", "failed", "abandoned"},
    "failed": {"ready", "abandoned"},
    "done": {"abandoned"},
    "abandoned": set(),
}

# Flat-attr section types Spec carries directly; everything else → children_extra.
_FLAT_SECTIONS = {"inputs", "outputs", "steps", "acceptance", "checks", "agent"}


# ─── ids + paths ──────────────────────────────────────────────────────


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "spec"


def make_id(title: str, *, today: str | None = None) -> str:
    stamp = today or date.today().strftime("%Y%m%d")
    return f"{stamp}-{_slug(title)}"


def specs_dir(scope: Scope) -> Path:
    return scope.dir / "specs"


def spec_path(scope: Scope, spec_id: str) -> Path:
    return specs_dir(scope) / f"{spec_id}.genospecs.yaml"


def lock_path(scope: Scope, spec_id: str) -> Path:
    return scope.dir / ".geno-specs" / "locks" / spec_id


# ─── Spec <-> Node bridge ─────────────────────────────────────────────


def spec_to_node(spec: Spec) -> Node:
    """Build the canonical root `spec` Node from a flat Spec."""
    node = Node(type="spec", id=spec.id, data={
        "title": spec.title,
        "status": spec.status,
        "tags": list(spec.tags),
        "context": spec.context,
        "template": spec.template,
    })
    # Surface the last failure first so a retrying agent sees it immediately.
    if spec.last_failure is not None:
        node.children.append(Node("last_failure", data={"value": spec.last_failure}))
    # Flat sections → section nodes (only when non-empty, to keep files clean).
    if spec.inputs:
        node.children.append(Node("inputs", data={"items": list(spec.inputs)}))
    if spec.outputs:
        node.children.append(Node("outputs", data={"items": list(spec.outputs)}))
    if spec.steps:
        node.children.append(Node("steps", data={"items": list(spec.steps)}))
    if spec.acceptance:
        node.children.append(Node("acceptance", data={"items": list(spec.acceptance)}))
    if spec.checks:
        node.children.append(Node("checks", data={"items": list(spec.checks)}))
    if spec.agent.capabilities or spec.agent.model:
        node.children.append(Node("agent", data={"value": spec.agent}))
    # Extra sections preserved verbatim.
    node.children.extend(spec.children_extra)
    return node


def node_to_spec(node: Node) -> Spec:
    """Project a canonical `spec` Node down to the flat Spec surface."""
    if node.type != "spec":
        raise ValueError(f"expected a spec node, got {node.type!r}")

    spec = Spec(
        id=node.id or make_id(node.data.get("title", "")),
        title=node.data.get("title", ""),
        status=node.data.get("status", "draft"),
        tags=list(node.data.get("tags", [])),
        context=node.data.get("context", ""),
        template=node.data.get("template"),
    )
    for child in node.children:
        if child.type == "last_failure":
            spec.last_failure = child.data.get("value")
        elif child.type == "inputs":
            spec.inputs = list(child.data.get("items", []))
        elif child.type == "outputs":
            spec.outputs = list(child.data.get("items", []))
        elif child.type == "steps":
            spec.steps = list(child.data.get("items", []))
        elif child.type == "acceptance":
            spec.acceptance = list(child.data.get("items", []))
        elif child.type == "checks":
            spec.checks = list(child.data.get("items", []))
        elif child.type == "agent":
            spec.agent = child.data.get("value", AgentRequirements())
        else:
            spec.children_extra.append(child)
    return spec


# ─── persistence ──────────────────────────────────────────────────────


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", suffix=".yaml", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def save(scope: Scope, spec: Spec) -> None:
    path = spec_path(scope, spec.id)
    with file_lock(lock_path(scope, spec.id)):
        _atomic_write(path, nodes._dump(spec_to_node(spec)))


def load(scope: Scope, spec_id: str) -> Spec:
    path = spec_path(scope, spec_id)
    if not path.exists():
        raise FileNotFoundError(f"spec {spec_id!r} not found at {path}")
    return node_to_spec(nodes._parse(path.read_text(encoding="utf-8")))


def load_all(scope: Scope) -> list[Spec]:
    d = specs_dir(scope)
    if not d.is_dir():
        return []
    out: list[Spec] = []
    for p in sorted(d.glob("*.genospecs.yaml")):
        try:
            out.append(node_to_spec(nodes._parse(p.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return out


def create(
    scope: Scope,
    title: str,
    *,
    tags: list[str] | None = None,
    template: str | None = None,
    context: str = "",
    steps: list[str] | None = None,
    acceptance: list[str] | None = None,
) -> Spec:
    spec = Spec(
        id=make_id(title),
        title=title,
        status="draft",
        tags=list(tags or []),
        template=template,
        context=context,
        steps=list(steps or []),
        acceptance=list(acceptance or []),
    )
    save(scope, spec)
    return spec


def transition(scope: Scope, spec_id: str, new_status: str) -> Spec:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"invalid status {new_status!r}")
    spec = load(scope, spec_id)
    allowed = _TRANSITIONS.get(spec.status, set())
    if new_status != spec.status and new_status not in allowed:
        raise ValueError(
            f"cannot transition {spec.status!r} → {new_status!r} "
            f"(allowed: {sorted(allowed) or 'none'})"
        )
    spec.status = new_status
    # `done` means the retry loop is over — drop the stale failure record so
    # a future failure on the *next* run doesn't get confused with this one.
    if new_status == "done":
        spec.last_failure = None
    save(scope, spec)
    return spec


def set_failure(scope: Scope, spec_id: str, failure: Failure) -> Spec:
    """Transition a spec to `failed` and persist its structured failure record.

    Used by `cli.validate` in place of a bare `transition(..., "failed")` so
    the *why* survives into the next `run` after a failed → ready retry.
    """
    spec = transition(scope, spec_id, "failed")
    spec.last_failure = failure
    save(scope, spec)
    return spec
