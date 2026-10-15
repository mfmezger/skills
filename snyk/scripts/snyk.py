#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "typer>=0.12", "truststore>=0.10"]
# ///
"""Read-only Snyk CLI: orgs, projects, issues via the REST API, plus a local `snyk test` summary. Emits JSON."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import typer

sys.path.insert(0, str(Path(__file__).parent))
from _snyk import emit, make_client, resolve_org

app = typer.Typer(add_completion=False, no_args_is_help=True)

OrgOpt = typer.Option(None, "--org", help="Org id (default: SNYK_ORG_ID).")
ProjectIdsOpt = typer.Option([], "--project", "-p", help="Project id; repeatable.")
PathArg = typer.Argument(Path("."), help="Project directory to scan locally.")
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
SARIF_LEVEL = {"error": "high", "warning": "medium", "note": "low"}


def _csv(value: str | None) -> list[str] | None:
    return [v.strip().lower() for v in value.split(",") if v.strip()] if value else None


@app.command()
def whoami() -> None:
    """Check the token and show the user's default org."""
    c = make_client()
    attrs = c.get("/self")["data"].get("attributes", {})
    emit(
        {
            "api": c.base,
            "username": attrs.get("username"),
            "name": attrs.get("name"),
            "email": attrs.get("email"),
            "default_org": attrs.get("default_org_context"),
            "SNYK_ORG_ID": os.environ.get("SNYK_ORG_ID"),
        }
    )


@app.command()
def orgs(name: str | None = typer.Option(None, "--name", help="Name substring filter.")) -> None:
    """Orgs the token can access, with ids for SNYK_ORG_ID / --org."""
    c = make_client()
    items, _ = c.paged("/orgs", {"name": name}, 500)
    emit([{"id": o["id"], "name": o["attributes"].get("name"), "slug": o["attributes"].get("slug")} for o in items])


def _find_projects(c: Any, org: str, repo: str | None, limit: int) -> list[dict[str, Any]]:
    params = {"expand": "target", "meta.latest_issue_counts": True}
    items, _ = c.paged(f"/orgs/{org}/projects", params, 5000)
    if repo:
        needle = repo.lower()
        items = [p for p in items if needle in f"{p['attributes'].get('name', '')} {_target(p)}".lower()]
    return items[:limit]


def _target(project: dict[str, Any]) -> str:
    """Display name of the expanded target, e.g. the ADO repo path."""
    data = ((project.get("relationships") or {}).get("target") or {}).get("data") or {}
    return (data.get("attributes") or {}).get("display_name") or ""


@app.command()
def projects(
    org: str | None = OrgOpt,
    repo: str | None = typer.Option(
        None, "--repo", "-r", help="Case-insensitive substring of project name or target (repo path)."
    ),
    limit: int = typer.Option(100, "--limit"),
) -> None:
    """Projects (one per manifest / code scan) with latest issue counts."""
    c = make_client()
    org_id = resolve_org(org)
    out = []
    for p in _find_projects(c, org_id, repo, limit):
        a = p["attributes"]
        counts = (p.get("meta") or {}).get("latest_issue_counts") or {}
        out.append(
            {
                "id": p["id"],
                "name": a.get("name"),
                "type": a.get("type"),
                "target_file": a.get("target_file") or None,
                "branch": a.get("target_reference"),
                "origin": a.get("origin"),
                "status": a.get("status"),
                "target": _target(p) or None,
                "issues": {k: counts.get(k) for k in ("critical", "high", "medium", "low")},
            }
        )
    emit(out)


def _location(coords: list[dict[str, Any]]) -> str | None:
    for coord in coords:
        for rep in coord.get("representations", []):
            if dep := rep.get("dependency"):
                return f"{dep.get('package_name')}@{dep.get('package_version')}"
            if src := rep.get("sourceLocation"):
                line = ((src.get("region") or {}).get("start") or {}).get("line")
                return f"{src.get('file')}:{line}" if line else src.get("file")
            if path := rep.get("resourcePath"):
                return path
    return None


def _fix(coords: list[dict[str, Any]]) -> list[str]:
    flags = ("is_upgradeable", "is_patchable", "is_pinnable", "is_fixable_snyk", "is_fixable_manually")
    return sorted({f.removeprefix("is_") for c in coords for f in flags if c.get(f)})


@app.command()
def issues(
    org: str | None = OrgOpt,
    project: list[str] = ProjectIdsOpt,
    repo: str | None = typer.Option(None, "--repo", "-r", help="Use all projects whose name or target contains this."),
    severity: str | None = typer.Option(None, "--severity", help="Comma list: critical,high,medium,low."),
    issue_type: str | None = typer.Option(
        None, "--type", help="package_vulnerability, license, code, config, secrets, cloud, custom."
    ),
    include_ignored: bool = typer.Option(False, "--include-ignored"),
    limit: int = typer.Option(100, "--limit", help="Max issues per project."),
) -> None:
    """Open issues for projects, worst first, with package@version or file:line and fix options."""
    if not project and not repo:
        raise typer.BadParameter("Pass --project <id> or --repo <name>.")
    c = make_client()
    org_id = resolve_org(org)
    names = {p["id"]: p["attributes"].get("name") for p in _find_projects(c, org_id, repo, 200)} if repo else {}
    ids = list(project) or list(names)
    if not ids:
        raise SystemExit(f"No Snyk project name or target contains {repo!r}. Try: snyk.py projects")
    rows = []
    for pid in ids:
        params = {
            "scan_item.id": pid,
            "scan_item.type": "project",
            "status": "open",
            "ignored": None if include_ignored else False,
            "effective_severity_level": _csv(severity),
            "type": issue_type,
        }
        items, _ = c.paged(f"/orgs/{org_id}/issues", params, limit)
        for i in items:
            a = i.get("attributes", {})
            coords = a.get("coordinates") or []
            rows.append(
                {
                    "project": names.get(pid, pid),
                    "title": a.get("title"),
                    "severity": a.get("effective_severity_level"),
                    "type": a.get("type"),
                    "location": _location(coords),
                    "ids": [p.get("id") for p in a.get("problems", [])],
                    "fix": _fix(coords),
                    "risk_score": ((a.get("risk") or {}).get("score") or {}).get("value"),
                    "ignored": a.get("ignored"),
                    "issue_id": i.get("id"),
                }
            )
    rows.sort(key=lambda r: (SEVERITY_ORDER.get(r["severity"], 9), -(r["risk_score"] or 0)))
    emit(
        {
            "projects": len(ids),
            "returned": len(rows),
            "by_severity": dict(Counter(r["severity"] for r in rows)),
            "by_type": dict(Counter(r["type"] for r in rows)),
            "issues": rows,
        }
    )


@app.command()
def test(
    path: Path = PathArg,
    code: bool = typer.Option(False, "--code", help="Run Snyk Code (SAST) instead of open-source deps."),
    org: str | None = OrgOpt,
    all_projects: bool = typer.Option(False, "--all-projects", help="Scan every manifest under path."),
) -> None:
    """Local scan with the Snyk CLI (`snyk test` / `snyk code test`); nothing is uploaded."""
    exe = shutil.which("snyk")
    if not exe:
        raise SystemExit("Snyk CLI not found. Install: brew tap snyk/tap && brew install snyk  (or npm i -g snyk)")
    cmd = [exe, "code", "test", "--json"] if code else [exe, "test", "--json"]
    if all_projects and not code:
        cmd.append("--all-projects")
    if org_id := org or os.environ.get("SNYK_ORG_ID"):
        cmd.append(f"--org={org_id}")
    env = dict(os.environ)
    if "SNYK_API_URL" in env:
        env.setdefault("SNYK_API", env["SNYK_API_URL"])
    proc = subprocess.run([*cmd, str(path)], capture_output=True, text=True, env=env, check=False)
    # Exit codes: 0 clean, 1 issues found, 2 failure, 3 no supported project.
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"snyk exited {proc.returncode}:\n{(proc.stdout or proc.stderr)[-3000:]}") from None
    if isinstance(data, dict) and data.get("error") and proc.returncode >= 2:
        raise SystemExit(f"snyk exited {proc.returncode}: {data.get('error')}")
    emit({"exit_code": proc.returncode, **(summarize_code(data) if code else summarize_deps(data))})


def summarize_deps(data: Any) -> dict[str, Any]:
    """Collapse `snyk test --json` (object or list per manifest) to unique vulns per manifest."""
    results = data if isinstance(data, list) else [data]
    manifests = []
    for res in results:
        vulns: dict[tuple[str, str], dict[str, Any]] = {}
        for v in res.get("vulnerabilities", []):
            pkg = f"{v.get('packageName')}@{v.get('version')}"
            entry = vulns.setdefault(
                (v.get("id"), pkg),
                {
                    "id": v.get("id"),
                    "title": v.get("title"),
                    "severity": v.get("severity"),
                    "package": pkg,
                    "cves": (v.get("identifiers") or {}).get("CVE") or None,
                    "fixed_in": v.get("fixedIn") or None,
                    "upgrade_to": next((u for u in reversed(v.get("upgradePath") or []) if u), None),
                    "paths": 0,
                    "example_path": " > ".join((v.get("from") or [])[1:]),
                },
            )
            entry["paths"] += 1
        rows = sorted(vulns.values(), key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))
        manifests.append(
            {
                "manifest": res.get("displayTargetFile") or res.get("targetFile"),
                "package_manager": res.get("packageManager"),
                "dependencies": res.get("dependencyCount"),
                "by_severity": dict(Counter(r["severity"] for r in rows)),
                "vulnerabilities": rows,
            }
        )
    return {"manifests": manifests}


def summarize_code(sarif: dict[str, Any]) -> dict[str, Any]:
    """Collapse `snyk code test --json` SARIF to file:line findings."""
    rows = []
    for run in sarif.get("runs", []):
        rules = {r.get("id"): r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}
        for res in run.get("results", []):
            loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
            line = (loc.get("region") or {}).get("startLine")
            rule = rules.get(res.get("ruleId"), {})
            rows.append(
                {
                    "rule": res.get("ruleId"),
                    "title": (rule.get("shortDescription") or {}).get("text"),
                    "severity": SARIF_LEVEL.get(res.get("level", ""), res.get("level")),
                    "location": f"{loc.get('artifactLocation', {}).get('uri')}:{line}",
                    "message": (res.get("message") or {}).get("text"),
                }
            )
    rows.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))
    return {"by_severity": dict(Counter(r["severity"] for r in rows)), "findings": rows}


if __name__ == "__main__":
    app()
