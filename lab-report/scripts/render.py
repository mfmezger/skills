#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12",
#   "jinja2>=3.1",
#   "pandas>=2.2",
#   "matplotlib>=3.8",
#   "tabulate>=0.9",
# ]
# ///
"""Render a lab report from a JSON spec on stdin.

The spec is the single source of truth for the report's contents; the LLM
builds it by combining (a) the user's prose for each section with (b) the
discover.py manifest of available data inputs.

Spec schema (all fields optional unless noted):

{
  "out_dir": "reports/2026-05-28-hello-image-upgrade",  # required
  "title": "Rich half-block image rendering",            # required
  "number": "007",                                       # optional, blank \u2192 "<Nummer>"
  "status": "Draft",
  "author": "Marc Fabian Mezger",
  "date": "28. May 2026",      # rendered verbatim; defaults to today (ISO)
  "reviewer": "",
  "story": "",
  "repo_branch": "capy@feat/hello-image-upgrade",

  "abstract":    "...",
  "goals":       "...",
  "assumptions": "...",
  "setup":       "...",
  "results":     "...",
  "conclusion":  "...",
  "next_steps":  "...",

  "metrics": {"accuracy": 0.91, "latency_p95_ms": 140},

  "code_snippets": [
    {"path": "src/foo.py", "lang": "python", "lines": [10, 40]}
  ],

  "tables": [
    {
      "source": "data/eval.csv",       # path relative to --repo-root
      "title": "Evaluation per model",
      "max_rows": 20,                   # optional
      "columns": ["model", "f1", "p95"] # optional subset
    }
  ],

  "charts": [
    {
      "source": "data/eval.csv",
      "kind": "bar",                    # bar | line | scatter | hist
      "x": "model",
      "y": ["f1", "precision"],         # str or list of str
      "title": "F1 + Precision by model",
      "caption": "Higher is better."    # optional
    }
  ],

  "images": [
    {"path": "figs/loss_curve.png", "caption": "Training loss"}
  ]
}

Charts and copied source images are written to <out_dir>/assets/ and
referenced from the Markdown via relative paths so the .md remains
portable (you can move the whole reports/<x>/ directory and it still
renders).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any

import jinja2
import matplotlib
import pandas as pd
import typer

matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=False)

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "lab-report.md.j2"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip().lower()).strip("-")
    return s or "chart"


def _load_csv(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    return pd.read_csv(path, sep=sep)


def _render_table(spec: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    src = repo_root / spec["source"]
    if not src.is_file():
        raise SystemExit(f"table source not found: {src}")
    df = _load_csv(src)
    rows_total = len(df)
    if "columns" in spec and spec["columns"]:
        missing = [c for c in spec["columns"] if c not in df.columns]
        if missing:
            raise SystemExit(f"columns missing in {spec['source']}: {missing}")
        df = df[spec["columns"]]
    max_rows = int(spec.get("max_rows") or 50)
    truncated = rows_total > max_rows
    if truncated:
        df = df.head(max_rows)
    md = df.to_markdown(index=False)
    return {
        "title": spec.get("title") or src.name,
        "source": spec["source"],
        "markdown": md,
        "rows_total": rows_total,
        "rows_shown": len(df),
        "truncated": truncated,
    }


def _render_chart(spec: dict[str, Any], repo_root: Path, assets_dir: Path) -> dict[str, Any]:
    src = repo_root / spec["source"]
    if not src.is_file():
        raise SystemExit(f"chart source not found: {src}")
    df = _load_csv(src)

    kind = spec.get("kind", "bar")
    title = spec.get("title") or f"{kind} of {spec.get('y') or src.stem}"
    caption = spec.get("caption") or ""

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=140)

    if kind == "hist":
        col = spec.get("y") or spec.get("x")
        if isinstance(col, list):
            col = col[0]
        if not col or col not in df.columns:
            raise SystemExit(f"hist requires a valid 'y' or 'x' column; got {col!r}")
        df[col].plot(kind="hist", ax=ax, bins=int(spec.get("bins") or 20))
        ax.set_xlabel(col)
    else:
        x = spec.get("x")
        y = spec.get("y")
        if not x or not y:
            raise SystemExit(f"{kind} chart requires 'x' and 'y' in spec")
        ys = y if isinstance(y, list) else [y]
        missing = [c for c in [x, *ys] if c not in df.columns]
        if missing:
            raise SystemExit(f"chart columns missing in {spec['source']}: {missing}")
        if kind == "bar":
            df.plot.bar(x=x, y=ys, ax=ax)
        elif kind == "line":
            df.plot.line(x=x, y=ys, ax=ax, marker="o")
        elif kind == "scatter":
            if len(ys) != 1:
                raise SystemExit("scatter requires exactly one y column")
            df.plot.scatter(x=x, y=ys[0], ax=ax)
        else:
            raise SystemExit(f"unsupported chart kind: {kind}")

    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out_name = f"{_slug(title)}.png"
    out_path = assets_dir / out_name
    fig.savefig(out_path)
    plt.close(fig)

    return {
        "path": f"assets/{out_name}",  # relative to the .md file
        "alt": title,
        "caption": caption or title,
    }


def _copy_image(spec: dict[str, Any], repo_root: Path, assets_dir: Path) -> dict[str, Any]:
    src = repo_root / spec["path"]
    if not src.is_file():
        raise SystemExit(f"image not found: {src}")
    dest = assets_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return {
        "path": f"assets/{src.name}",
        "alt": spec.get("alt") or src.stem,
        "caption": spec.get("caption") or src.stem,
    }


def _load_snippet(spec: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    src = repo_root / spec["path"]
    if not src.is_file():
        raise SystemExit(f"code snippet source not found: {src}")
    text = src.read_text(encoding="utf-8", errors="replace")
    lines = spec.get("lines")
    if lines and isinstance(lines, list) and len(lines) == 2:
        start, end = int(lines[0]), int(lines[1])
        text = "\n".join(text.splitlines()[max(start - 1, 0):end])
    lang = spec.get("lang") or {
        ".py": "python", ".sh": "bash", ".ts": "typescript", ".js": "javascript",
        ".rs": "rust", ".go": "go", ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".md": "markdown",
    }.get(src.suffix.lower(), "")
    return {"path": spec["path"], "lang": lang, "content": text}


def _default_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    today = date.today().isoformat()
    return {
        "number": spec.get("number") or "",
        "title": spec.get("title") or "<Titel der Analyse>",
        "status": spec.get("status") or "Draft",
        "author": spec.get("author") or "",
        "date": spec.get("date") or today,
        "reviewer": spec.get("reviewer") or "",
        "story": spec.get("story") or "",
        "repo_branch": spec.get("repo_branch") or "",
        "abstract": spec.get("abstract") or "_TBD_",
        "goals": spec.get("goals") or "_TBD_",
        "assumptions": spec.get("assumptions") or "_TBD_",
        "setup": spec.get("setup") or "_TBD_",
        "results": spec.get("results") or "_TBD_",
        "conclusion": spec.get("conclusion") or "_TBD_",
        "next_steps": spec.get("next_steps") or "_TBD_",
    }


@app.command()
def main(
    out_dir: Path | None = typer.Option(None, "--out-dir", help="Output dir; overrides spec.out_dir."),
    repo_root: Path = typer.Option(Path("."), "--repo-root", help="Base for resolving source paths in the spec."),
    spec_file: Path | None = typer.Option(None, "--spec-file", help="Read spec JSON from file instead of stdin."),
) -> None:
    """Render a lab report from a JSON spec (stdin or --spec-file)."""
    if spec_file:
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
    else:
        spec = json.loads(sys.stdin.read())

    out = (out_dir or Path(spec.get("out_dir") or "")).resolve()
    if str(out) in {"", "/"}:
        raise SystemExit("out_dir is required (pass --out-dir or set spec.out_dir).")
    repo_root = repo_root.resolve()
    assets_dir = out / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    ctx = _default_metadata(spec)
    ctx["metrics"] = spec.get("metrics") or {}
    ctx["code_snippets"] = [_load_snippet(s, repo_root) for s in spec.get("code_snippets") or []]
    ctx["tables"] = [_render_table(t, repo_root) for t in spec.get("tables") or []]
    ctx["charts"] = [_render_chart(c, repo_root, assets_dir) for c in spec.get("charts") or []]
    ctx["images"] = [_copy_image(i, repo_root, assets_dir) for i in spec.get("images") or []]

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_PATH.parent),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    tmpl = env.get_template(TEMPLATE_PATH.name)
    rendered = tmpl.render(**ctx)

    out_md = out / "report.md"
    out_md.write_text(rendered, encoding="utf-8")

    summary = {
        "report": str(out_md),
        "assetsDir": str(assets_dir),
        "metricsCount": len(ctx["metrics"]),
        "tableCount": len(ctx["tables"]),
        "chartCount": len(ctx["charts"]),
        "imageCount": len(ctx["images"]),
        "snippetCount": len(ctx["code_snippets"]),
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    app()
