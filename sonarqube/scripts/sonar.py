#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "typer>=0.12", "truststore>=0.10"]
# ///
"""Read-only SonarQube Server CLI: quality gate, issues, hotspots, measures. Emits JSON."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from typing import Any

import typer

sys.path.insert(0, str(Path(__file__).parent))
from _sonar import SonarApiError, emit, make_client, resolve_project

app = typer.Typer(add_completion=False, no_args_is_help=True)

ProjectOpt = typer.Option(None, "--project", "-p", help="Project key (default: SONAR_PROJECT_KEY or sonar config).")
BranchOpt = typer.Option(None, "--branch", "-b", help="Branch name (default: main branch).")
PrOpt = typer.Option(None, "--pr", help="Pull request key, e.g. the ADO PR id.")
FileOpt = typer.Option([], "--file", "-f", help="Repo-relative path; repeatable.")

DEFAULT_METRICS = [
    "alert_status",
    "ncloc",
    "coverage",
    "new_coverage",
    "duplicated_lines_density",
    "new_duplicated_lines_density",
    "violations",
    "new_violations",
    "software_quality_security_issues",
    "software_quality_reliability_issues",
    "software_quality_maintainability_issues",
    "security_hotspots",
    "security_hotspots_reviewed",
    "software_quality_security_rating",
    "software_quality_reliability_rating",
    "software_quality_maintainability_rating",
    "security_rating",
    "reliability_rating",
    "sqale_rating",
]
RATING_LETTERS = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}


def _scope(branch: str | None, pr: str | None) -> dict[str, Any]:
    if branch and pr:
        raise typer.BadParameter("Use either --branch or --pr, not both.")
    return {"branch": branch, "pullRequest": pr}


def _file(component: str | None, key: str) -> str | None:
    """'<key>:src/a.py' -> 'src/a.py'; keys may contain ':' themselves."""
    return component.removeprefix(f"{key}:") if component else component


def _csv(value: str | None) -> list[str] | None:
    return [v.strip().upper() for v in value.split(",") if v.strip()] if value else None


@app.command()
def whoami() -> None:
    """Check host, server version and that the token is valid."""
    c = make_client()
    user = c.get("/api/users/current")
    emit(
        {
            "host": c.host,
            "version": c.get("/api/server/version"),
            "token_valid": c.get("/api/authentication/validate").get("valid"),
            "logged_in": user.get("isLoggedIn"),
            "login": user.get("login"),
            "name": user.get("name"),
        }
    )


@app.command()
def projects(
    query: str | None = typer.Option(None, "--query", "-q", help="Name or key substring (min. 2 chars)."),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    """Find project keys the token can browse."""
    c = make_client()
    items, first = c.paged("/api/components/search", "components", {"qualifiers": "TRK", "q": query}, limit)
    emit(
        {
            "total": (first.get("paging") or {}).get("total"),
            "projects": [{"key": p.get("key"), "name": p.get("name")} for p in items],
        }
    )


@app.command()
def branches(project: str | None = ProjectOpt) -> None:
    """List analysed branches with their quality gate status."""
    c = make_client()
    key = resolve_project(project)
    data = c.get("/api/project_branches/list", {"project": key})
    emit(
        {
            "project": key,
            "branches": [
                {
                    "name": b.get("name"),
                    "is_main": b.get("isMain"),
                    "quality_gate": (b.get("status") or {}).get("qualityGateStatus"),
                    "analysis_date": b.get("analysisDate"),
                }
                for b in data.get("branches", [])
            ],
        }
    )


@app.command()
def prs(project: str | None = ProjectOpt) -> None:
    """List analysed pull requests with their quality gate status."""
    c = make_client()
    key = resolve_project(project)
    data = c.get("/api/project_pull_requests/list", {"project": key})
    emit(
        {
            "project": key,
            "pull_requests": [
                {
                    "key": p.get("key"),
                    "title": p.get("title"),
                    "branch": p.get("branch"),
                    "base": p.get("base"),
                    "quality_gate": (p.get("status") or {}).get("qualityGateStatus"),
                    "analysis_date": p.get("analysisDate"),
                    "url": p.get("url"),
                }
                for p in data.get("pullRequests", [])
            ],
        }
    )


@app.command("quality-gate")
def quality_gate(project: str | None = ProjectOpt, branch: str | None = BranchOpt, pr: str | None = PrOpt) -> None:
    """Quality gate status; `failing` lists the conditions that break it."""
    c = make_client()
    key = resolve_project(project)
    status = c.get("/api/qualitygates/project_status", {"projectKey": key, **_scope(branch, pr)})["projectStatus"]
    conditions = [
        {
            "metric": cond.get("metricKey"),
            "status": cond.get("status"),
            "actual": cond.get("actualValue"),
            "comparator": cond.get("comparator"),
            "threshold": cond.get("errorThreshold"),
        }
        for cond in status.get("conditions", [])
    ]
    emit(
        {
            "project": key,
            "branch": branch,
            "pull_request": pr,
            "status": status.get("status"),
            "failing": [x for x in conditions if x["status"] == "ERROR"],
            "conditions": conditions,
        }
    )


@app.command()
def issues(
    project: str | None = ProjectOpt,
    branch: str | None = BranchOpt,
    pr: str | None = PrOpt,
    new_code: bool = typer.Option(False, "--new-code", help="Only issues in the new code period."),
    severity: str | None = typer.Option(None, "--severity", help="Comma list: BLOCKER,HIGH,MEDIUM,LOW,INFO."),
    quality: str | None = typer.Option(None, "--quality", help="Comma list: SECURITY,RELIABILITY,MAINTAINABILITY."),
    status: str = typer.Option("OPEN,CONFIRMED", "--status", help="Comma list of issue statuses."),
    file: list[str] = FileOpt,
    limit: int = typer.Option(100, "--limit"),
) -> None:
    """Issues with file:line, rule and impacts, plus totals by severity and quality."""
    c = make_client()
    key = resolve_project(project)
    params = {
        "components": [f"{key}:{f}" for f in file] if file else key,
        **_scope(branch, pr),
        "inNewCodePeriod": True if new_code else None,
        "impactSeverities": _csv(severity),
        "impactSoftwareQualities": _csv(quality),
        "issueStatuses": _csv(status),
        "facets": "impactSeverities,impactSoftwareQualities",
        "s": "SEVERITY",
        "asc": False,
    }
    items, first = c.paged("/api/issues/search", "issues", params, limit)
    facets = {
        f["property"]: {v["val"]: v["count"] for v in f.get("values", []) if v.get("count")}
        for f in first.get("facets", [])
    }
    emit(
        {
            "project": key,
            "total": (first.get("paging") or {}).get("total"),
            "returned": len(items),
            "by_severity": facets.get("impactSeverities"),
            "by_quality": facets.get("impactSoftwareQualities"),
            "issues": [
                {
                    "key": i.get("key"),
                    "file": _file(i.get("component"), key),
                    "line": i.get("line"),
                    "message": i.get("message"),
                    "rule": i.get("rule"),
                    "impacts": [f"{x.get('softwareQuality')}:{x.get('severity')}" for x in i.get("impacts", [])],
                    "status": i.get("issueStatus") or i.get("status"),
                    "effort": i.get("effort"),
                    "tags": i.get("tags") or None,
                }
                for i in items
            ],
        }
    )


@app.command()
def hotspots(
    project: str | None = ProjectOpt,
    branch: str | None = BranchOpt,
    pr: str | None = PrOpt,
    new_code: bool = typer.Option(False, "--new-code", help="Only hotspots in the new code period."),
    status: str = typer.Option("TO_REVIEW", "--status", help="TO_REVIEW or REVIEWED."),
    limit: int = typer.Option(100, "--limit"),
) -> None:
    """Security hotspots, highest vulnerability probability first."""
    c = make_client()
    key = resolve_project(project)
    params = {
        "projectKey": key,
        **_scope(branch, pr),
        "status": status.upper(),
        "sinceLeakPeriod": True if new_code else None,
    }
    items, first = c.paged("/api/hotspots/search", "hotspots", params, limit)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda h: order.get(h.get("vulnerabilityProbability", ""), 3))
    emit(
        {
            "project": key,
            "total": (first.get("paging") or {}).get("total"),
            "returned": len(items),
            "hotspots": [
                {
                    "key": h.get("key"),
                    "file": _file(h.get("component"), key),
                    "line": h.get("line"),
                    "message": h.get("message"),
                    "category": h.get("securityCategory"),
                    "probability": h.get("vulnerabilityProbability"),
                    "rule": h.get("ruleKey"),
                    "status": h.get("status"),
                }
                for h in items
            ],
        }
    )


@app.command()
def measures(
    project: str | None = ProjectOpt,
    branch: str | None = BranchOpt,
    pr: str | None = PrOpt,
    metrics: str | None = typer.Option(None, "--metrics", help="Comma list of metric keys (default: a summary set)."),
) -> None:
    """Coverage, duplication, issue counts and ratings; new_* metrics hold new-code values."""
    c = make_client()
    key = resolve_project(project)
    wanted = [m.strip() for m in metrics.split(",")] if metrics else list(DEFAULT_METRICS)
    while True:
        try:
            data = c.get("/api/measures/component", {"component": key, "metricKeys": wanted, **_scope(branch, pr)})
            break
        except SonarApiError as e:
            # Metric sets differ between Standard and MQR mode; drop unknown keys and retry.
            m = re.search(r"metric keys are not found: ([^\"]+)", e.body)
            unknown = {k.strip() for k in m.group(1).split(",")} if m else set()
            if e.status != 404 or not unknown or not (wanted := [k for k in wanted if k not in unknown]):
                raise
    out: dict[str, Any] = {}
    for meas in data.get("component", {}).get("measures", []):
        period = meas.get("period") or next(iter(meas.get("periods") or []), None)
        value = meas.get("value", period.get("value") if period else None)
        if meas["metric"].endswith("_rating"):
            value = RATING_LETTERS.get(str(value), value)
        out[meas["metric"]] = value
    emit({"project": key, "branch": branch, "pull_request": pr, "measures": out})


@app.command()
def rule(key: str = typer.Argument(..., help="Rule key, e.g. python:S1192.")) -> None:
    """Explain a rule: why it matters and how to fix, as plain text."""
    c = make_client()
    r = c.get("/api/rules/show", {"key": key})["rule"]
    sections = r.get("descriptionSections") or [{"key": "default", "content": r.get("htmlDesc", "")}]
    emit(
        {
            "key": r.get("key"),
            "name": r.get("name"),
            "language": r.get("langName"),
            "impacts": [f"{x.get('softwareQuality')}:{x.get('severity')}" for x in r.get("impacts", [])],
            "sections": {s.get("key"): _text(s.get("content", "")) for s in sections},
        }
    )


def _text(markup: str) -> str:
    markup = re.sub(r"<(br|/p|/li|/h\d|/pre)\s*/?>", "\n", markup, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", markup))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


if __name__ == "__main__":
    app()
