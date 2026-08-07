#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""Discover lab-report inputs in a repo and emit a JSON manifest.

Scans (relative to --root, default = cwd):
  - CSV / TSV  → candidate data tables and chart sources
  - PNG / JPG / SVG → existing figures to embed
  - .ipynb     → notebooks to reference in Experiment Setup
  - metrics.json / results.json → key/value metrics
  - README.md  → optional snippet to seed Abstract / Goals

Also pulls git context (remote, branch, current user) so the LLM doesn't
have to shell out separately.

Output is JSON to stdout — the calling LLM is expected to read it, decide
which items belong in the report, and pass selections to render.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(add_completion=False, no_args_is_help=False)

# Directories we never want to recurse into.
SKIP_DIRS = {
    ".git", ".venv", "venv", "env", ".env",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", "dist", "build", ".idea", ".vscode",
    "site-packages", ".next", "target",
}

DATA_EXTS = {".csv", ".tsv"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
NB_EXTS = {".ipynb"}


def _git(cwd: Path, *args: str) -> str | None:
    r = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    return r.stdout.strip() if r.returncode == 0 else None


def _git_context(root: Path) -> dict[str, Any]:
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    remote = _git(root, "remote", "get-url", "origin")
    user_name = _git(root, "config", "user.name")
    repo_branch = None
    if remote and branch:
        # Normalize common URL shapes into "<host>/<owner>/<repo>@<branch>".
        m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
        slug = m.group(1) if m else remote
        repo_branch = f"{slug}@{branch}"
    # Try to extract a story/ticket id from the branch (AB#123, ABC-456, #789).
    story = None
    if branch:
        m = re.search(r"(?:AB#|#)(\d{2,7})", branch) or re.search(r"\b([A-Z]{2,6}-\d{2,6})\b", branch)
        if m:
            story = m.group(0)
    return {
        "branch": branch,
        "remote": remote,
        "userName": user_name,
        "repoBranch": repo_branch,
        "story": story,
        "today": date.today().isoformat(),
    }


def _scan(root: Path, max_size_mb: float) -> dict[str, list[dict[str, Any]]]:
    data_files: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    notebooks: list[dict[str, Any]] = []
    metrics_files: list[dict[str, Any]] = []
    readme: dict[str, Any] | None = None
    max_bytes = int(max_size_mb * 1024 * 1024)

    for p in sorted(root.rglob("*")):
        # Skip dirs we don't recurse into.
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > max_bytes:
            continue
        rel = p.relative_to(root).as_posix()
        ext = p.suffix.lower()
        if ext in DATA_EXTS:
            data_files.append({"path": rel, "sizeBytes": size, "ext": ext.lstrip(".")})
        elif ext in IMG_EXTS:
            images.append({"path": rel, "sizeBytes": size, "ext": ext.lstrip(".")})
        elif ext in NB_EXTS:
            notebooks.append({"path": rel, "sizeBytes": size})
        elif p.name in {"metrics.json", "results.json"}:
            try:
                with p.open() as f:
                    payload = json.load(f)
                # Only accept flat-ish dicts of scalars for the summary table.
                if isinstance(payload, dict):
                    flat = {
                        k: v for k, v in payload.items()
                        if isinstance(v, (int, float, str, bool)) or v is None
                    }
                    metrics_files.append({"path": rel, "metrics": flat})
            except (OSError, json.JSONDecodeError):
                pass
        elif p.name.lower() == "readme.md" and readme is None and p.parent == root:
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:2000]
                readme = {"path": rel, "head": head}
            except OSError:
                pass

    return {
        "dataFiles": data_files,
        "images": images,
        "notebooks": notebooks,
        "metricsFiles": metrics_files,
        "readme": readme,
    }


@app.command()
def main(
    root: Path = typer.Option(Path("."), "--root", help="Directory to scan."),
    max_file_mb: float = typer.Option(50.0, "--max-file-mb", help="Skip files larger than this."),
) -> None:
    """Scan the repo and emit a JSON manifest of report inputs."""
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"--root {root} is not a directory")
    manifest = {
        "root": str(root),
        "git": _git_context(root),
        **_scan(root, max_file_mb),
    }
    json.dump(manifest, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    app()
