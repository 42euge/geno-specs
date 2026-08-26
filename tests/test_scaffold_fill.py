"""Tests for `geno-specs init --fill` (heuristic draft content)."""

from __future__ import annotations

import subprocess

from click.testing import CliRunner

from geno_specs import scaffold
from geno_specs.cli import main


def _git_repo_with_history(tmp_path):
    repo = tmp_path / "widgetizer"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text(
        "# Widgetizer\n\n"
        "Widgetizer turns raw sensor logs into clean, queryable event streams.\n\n"
        "It exists because our sensor logs were unstructured JSON blobs nobody\n"
        "could query without writing a one-off parser.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Add initial README"], cwd=repo, check=True)
    for msg in ("Add sensor log parser", "Fix timestamp parsing bug", "Add CLI entrypoint"):
        f = repo / f"{msg[:6].replace(' ', '_')}.py"
        f.write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", f.name], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)
    return repo


def test_scaffold_without_fill_leaves_placeholders(tmp_path):
    root = scaffold.scaffold(tmp_path, name="Proj")
    vision = (root / "VISION.md").read_text(encoding="utf-8")
    tenets = (root / "TENETS.md").read_text(encoding="utf-8")
    assert "<!-- What problem does Proj solve?" in vision
    assert "<!-- Tenet 1 -->" in tenets
    assert "DRAFT" not in vision


def test_scaffold_fill_drafts_from_readme_and_git_log(tmp_path):
    repo = _git_repo_with_history(tmp_path)
    root = scaffold.scaffold(repo, name="Widgetizer", fill=True)

    vision = (root / "VISION.md").read_text(encoding="utf-8")
    tenets = (root / "TENETS.md").read_text(encoding="utf-8")
    goals = (root / "GOALS.md").read_text(encoding="utf-8")

    # Pulled real content from README, not left as HTML-comment placeholders.
    assert "sensor logs" in vision
    assert "<!-- What problem does" not in vision
    assert "DRAFT" in vision

    # Tenets get generic starter principles, clearly marked as draft.
    assert "Prefer explicit over implicit" in tenets
    assert "DRAFT" in tenets

    # Goals summarize recent commit subjects.
    assert "Add sensor log parser" in goals
    assert "Fix timestamp parsing bug" in goals
    assert "Add CLI entrypoint" in goals
    assert "DRAFT" in goals


def test_scaffold_fill_no_git_history_falls_back_gracefully(tmp_path):
    # Not a git repo at all — should not crash, just skip the git-log section.
    root = scaffold.scaffold(tmp_path, name="Proj", fill=True)
    goals = (root / "GOALS.md").read_text(encoding="utf-8")
    assert "No git history found" in goals


def test_scaffold_never_overwrites_existing_files(tmp_path):
    root = scaffold.scaffold(tmp_path, name="Proj")
    (root / "VISION.md").write_text("custom content", encoding="utf-8")
    scaffold.scaffold(tmp_path, name="Proj", fill=True)
    assert (root / "VISION.md").read_text(encoding="utf-8") == "custom content"


def test_cli_init_fill_flag(tmp_path, monkeypatch):
    repo = _git_repo_with_history(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GENO_SPECS_DIR", str(tmp_path / "scope"))

    r = CliRunner().invoke(main, ["init", "--fill"])
    assert r.exit_code == 0, r.output
    assert "drafted from README" in r.output

    vision = (repo / ".specs" / "VISION.md").read_text(encoding="utf-8")
    assert "sensor logs" in vision


def test_cli_init_without_fill_unchanged(tmp_path, monkeypatch):
    repo = tmp_path / "plainrepo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("GENO_SPECS_DIR", str(tmp_path / "scope"))

    r = CliRunner().invoke(main, ["init"])
    assert r.exit_code == 0, r.output
    assert "drafted from README" not in r.output

    vision = (repo / ".specs" / "VISION.md").read_text(encoding="utf-8")
    assert "<!-- What problem does" in vision
