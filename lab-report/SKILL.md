---
name: lab-report
description: "Generate a structured lab/experiment report in Markdown from an experiment repository. Discovers CSV data files, existing plot images, Jupyter notebooks, and metrics.json automatically, then renders a report following the standard Lab Report template (Abstract → Goals → Assumptions → Setup → Results → Conclusion → Next Steps) with embedded tables, auto-generated charts (matplotlib), and figures. Use when the user asks to 'write a lab report', 'create an experiment report', 'document this analysis', or 'turn these results into a report'."
author: Marc Fabian Mezger <57255687+mfmezger@users.noreply.github.com>
---

# Lab Report Skill

Generates a Markdown lab report from an experiment repository. Output is
**Markdown only** — no Word / PDF conversion.

## Output

A self-contained directory:

```
reports/<slug>/
├── report.md         # the report
└── assets/           # generated charts + copied figures
    ├── f1-by-model.png
    └── loss_curve.png
```

`report.md` references everything via relative paths in `assets/`, so the
whole directory can be moved or zipped without breaking links.

## Prerequisites

- `uv` installed (scripts use PEP 723 inline metadata; deps install on
  first run — `jinja2`, `pandas`, `matplotlib`, `tabulate`).
- Run from inside the experiment repository so `git` context (remote,
  branch, story id) gets picked up.

## Template

The report follows this structure (`templates/lab-report.md.j2`):

```
# Lab Report <Nummer>: <Titel>

| Document Status | Author | Date | Reviewer | Story | Repository/Branch |

## Abstract
## Goals & Problem Description
## Assumptions & Limitations
## Experiment Setup
  (optional code snippets)
## Results
  (optional key-metrics table)
  (optional CSV-rendered tables)
  (optional auto-generated charts)
  (optional embedded figures)
## Conclusion
## Improvements / Possible Next Steps
```

## Workflow

### Step 1 — Discover

Always start by scanning the repo so you know what data exists. Do **not**
invent inputs.

```bash
uv run scripts/discover.py --root .
```

Output is a JSON manifest of: git context (branch, remote, story id
parsed from branch), CSV/TSV files, images, notebooks, any
`metrics.json` / `results.json` it found, and the top of the README.

If the user is running from outside the experiment repo, ask once for the
path and pass `--root <path>`.

### Step 2 — Compose the spec

Build a JSON spec for `render.py`. The spec is the contract; everything
below it is deterministic. Compose it from:

1. **The discover output** — use it to pick which CSVs become tables,
   which become charts, and which images to embed. Don't include
   everything blindly; pick what's actually relevant to the analysis.
2. **The user's prose** — for each section (Abstract, Goals,
   Assumptions, Setup, Results, Conclusion, Next steps). If a section is
   missing, ask the user before filling it with `_TBD_`.

Minimal example:

```json
{
  "out_dir": "reports/2026-05-28-hello-image-upgrade",
  "title": "Terminal image rendering with Rich half-blocks",
  "status": "Draft",
  "author": "Marc Fabian Mezger",
  "repo_branch": "capy@feat/hello-image-upgrade",
  "abstract": "...",
  "goals": "...",
  "assumptions": "...",
  "setup": "...",
  "results": "Tabular results below; F1 chart compares the three rendering modes.",
  "conclusion": "...",
  "next_steps": "...",
  "metrics": {"accuracy": 0.91, "latency_p95_ms": 140, "dataset_size": 12345},
  "tables": [
    {"source": "data/eval.csv", "title": "Per-model evaluation", "max_rows": 20}
  ],
  "charts": [
    {"source": "data/eval.csv", "kind": "bar", "x": "model",
     "y": ["f1", "precision"], "title": "F1 + Precision by model"}
  ],
  "images": [
    {"path": "figs/loss_curve.png", "caption": "Training loss"}
  ]
}
```

**Show the spec to the user before rendering** — it's the single point
where they can sanity-check what's going in.

### Step 3 — Render

Pipe the spec to `render.py`:

```bash
cat spec.json | uv run scripts/render.py --repo-root .
# or:
uv run scripts/render.py --spec-file spec.json --repo-root .
```

It writes `report.md` plus any generated chart PNGs into
`<out_dir>/assets/`, and emits a JSON summary to stdout
(counts of metrics / tables / charts / images / snippets).

### Step 4 — Review

After rendering, **always read the report back** (`cat report.md`) and
present the user with:
- A short summary of what landed in each section.
- Any `_TBD_` placeholders that still need filling.
- The list of generated assets.

Offer to iterate: tweak prose, add/remove tables/charts, regenerate.

## Spec reference

See the docstring at the top of `scripts/render.py` for the full schema.
Highlights:

| Field          | Meaning |
|----------------|---------|
| `out_dir`      | **Required.** Where `report.md` + `assets/` go. Conventionally `reports/<YYYY-MM-DD>-<slug>/`. |
| `title`        | **Required.** Fills `<Titel der Analyse>`. |
| `number`       | Optional. Left as `<Nummer>` if omitted (user can fill manually). |
| `date`         | Free-form string. Defaults to today's ISO date. Use `"28. May 2026"` or `"18. Dez. 2025"` to match the German style of the original template. |
| `metrics`      | Flat dict of scalars. Rendered as a 2-col table at the top of Results. |
| `tables[]`     | `{source, title?, max_rows?, columns?}` — CSV/TSV → markdown table. |
| `charts[]`     | `{source, kind, x?, y, title?, caption?, bins?}` — `kind` ∈ `bar`/`line`/`scatter`/`hist`. Saved as PNG into `assets/`. |
| `images[]`     | `{path, caption?, alt?}` — existing PNG/JPG/SVG copied into `assets/`. |
| `code_snippets[]` | `{path, lang?, lines?}` — `lines: [start, end]` (1-indexed, inclusive). |

## Guardrails

- **No hallucinated data.** Never invent metric values, table rows, or
  result numbers. Every number must come from a CSV, `metrics.json`, or
  text the user provided.
- **Never blow past placeholders silently.** If `abstract`/`goals`/etc.
  are missing, the renderer writes `_TBD_` and you must flag those to
  the user explicitly.
- **Respect existing reports.** If `out_dir` already contains a
  `report.md`, ask before overwriting.
- **Markdown only.** This skill does not produce .docx or .pdf. If the
  user asks for those, suggest pandoc as a manual follow-up
  (`pandoc report.md -o report.docx --resource-path=.`) but do not
  automate it.
- **No AI attribution** anywhere in the report body, metadata, or
  filenames. The Author field is for the human running the experiment.
