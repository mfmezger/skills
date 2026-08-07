#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "typer>=0.12", "rich>=13"]
# ///
"""Azure DevOps pipeline analysis CLI.

Subcommands:
  list-defs       List pipeline/build definitions for a project.
  list-builds     List recent builds (filter by definition, branch, status, result).
  build-status    Get status/details of a specific build.
  build-changes   List commits associated with a build.
  failed-logs     Fetch logs for failed/errored steps of a build.
  duration-trend  Show duration trend over the last N builds of a definition.
  flaky           Compute pass/fail churn over the last N runs to flag flaky pipelines.

All output is JSON for predictable downstream parsing by an LLM.
"""

from __future__ import annotations

import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

sys.path.insert(0, str(Path(__file__).parent))
from _ado import emit, make_client  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


@app.command("list-defs")
def list_defs(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    name: str | None = typer.Option(None, "--name", help="Optional name filter (wildcards allowed)."),
) -> None:
    """List pipeline definitions for a project."""
    c = make_client(org)
    params: dict[str, Any] = {}
    if name:
        params["name"] = name
    data = c.paged_get("/_apis/build/definitions", project=project, params=params)
    emit(
        [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "path": d.get("path"),
                "type": d.get("type"),
                "queue": (d.get("queue") or {}).get("name"),
                "url": f"https://dev.azure.com/{c.org}/{project}/_build?definitionId={d.get('id')}",
            }
            for d in data
        ]
    )


@app.command("list-builds")
def list_builds(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    definition_id: int | None = typer.Option(None, "--definition-id"),
    definition_name: str | None = typer.Option(None, "--definition-name"),
    branch: str | None = typer.Option(None, "--branch", help="e.g. refs/heads/main or main"),
    status: str | None = typer.Option(None, "--status", help="inProgress|completed|cancelling|notStarted|all"),
    result: str | None = typer.Option(None, "--result", help="succeeded|failed|canceled|partiallySucceeded"),
    top: int = typer.Option(20, "--top"),
) -> None:
    """List recent builds with optional filters."""
    c = make_client(org)

    # Resolve definition by name if needed.
    if definition_name and not definition_id:
        defs = c.paged_get(
            "/_apis/build/definitions",
            project=project,
            params={"name": definition_name},
        )
        if not defs:
            raise SystemExit(f"No pipeline definition matched name: {definition_name}")
        if len(defs) > 1:
            emit({"error": "ambiguous_definition", "matches": [{"id": d["id"], "name": d["name"]} for d in defs]})
            raise typer.Exit(2)
        definition_id = defs[0]["id"]

    params: dict[str, Any] = {"$top": top, "queryOrder": "queueTimeDescending"}
    if definition_id:
        params["definitions"] = definition_id
    if branch:
        params["branchName"] = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    if status:
        params["statusFilter"] = status
    if result:
        params["resultFilter"] = result

    data = c.get("/_apis/build/builds", project=project, params=params)
    builds = (data or {}).get("value", [])
    emit(
        [
            {
                "id": b.get("id"),
                "buildNumber": b.get("buildNumber"),
                "definition": (b.get("definition") or {}).get("name"),
                "status": b.get("status"),
                "result": b.get("result"),
                "sourceBranch": b.get("sourceBranch"),
                "sourceVersion": b.get("sourceVersion"),
                "requestedFor": (b.get("requestedFor") or {}).get("displayName"),
                "queueTime": b.get("queueTime"),
                "startTime": b.get("startTime"),
                "finishTime": b.get("finishTime"),
                "url": f"https://dev.azure.com/{c.org}/{project}/_build/results?buildId={b.get('id')}",
            }
            for b in builds
        ]
    )


@app.command("build-status")
def build_status(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    build_id: int = typer.Option(..., "--build-id"),
) -> None:
    """Get full status of a single build, including timeline of failed steps."""
    c = make_client(org)
    b = c.get(f"/_apis/build/builds/{build_id}", project=project)
    timeline = c.get(f"/_apis/build/builds/{build_id}/timeline", project=project) or {}
    records = timeline.get("records", []) or []

    failed = [
        {
            "id": r.get("id"),
            "parentId": r.get("parentId"),
            "name": r.get("name"),
            "type": r.get("type"),
            "result": r.get("result"),
            "logId": (r.get("log") or {}).get("id"),
            "errorCount": r.get("errorCount"),
            "warningCount": r.get("warningCount"),
            "startTime": r.get("startTime"),
            "finishTime": r.get("finishTime"),
        }
        for r in records
        if r.get("result") in {"failed", "canceled"}
    ]

    start = _parse_dt(b.get("startTime"))
    finish = _parse_dt(b.get("finishTime"))
    duration_s = (finish - start).total_seconds() if start and finish else None

    emit(
        {
            "id": b.get("id"),
            "buildNumber": b.get("buildNumber"),
            "definition": (b.get("definition") or {}).get("name"),
            "status": b.get("status"),
            "result": b.get("result"),
            "sourceBranch": b.get("sourceBranch"),
            "sourceVersion": b.get("sourceVersion"),
            "requestedFor": (b.get("requestedFor") or {}).get("displayName"),
            "reason": b.get("reason"),
            "queueTime": b.get("queueTime"),
            "startTime": b.get("startTime"),
            "finishTime": b.get("finishTime"),
            "durationSeconds": duration_s,
            "url": f"https://dev.azure.com/{c.org}/{project}/_build/results?buildId={b.get('id')}",
            "failedRecords": failed,
        }
    )


@app.command("build-changes")
def build_changes(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    build_id: int = typer.Option(..., "--build-id"),
    top: int = typer.Option(50, "--top"),
) -> None:
    """List commits associated with a build."""
    c = make_client(org)
    data = c.get(
        f"/_apis/build/builds/{build_id}/changes",
        project=project,
        params={"$top": top},
    )
    changes = (data or {}).get("value", [])
    emit(
        [
            {
                "id": ch.get("id"),
                "shortId": (ch.get("id") or "")[:8],
                "message": (ch.get("message") or "").splitlines()[0] if ch.get("message") else None,
                "author": (ch.get("author") or {}).get("displayName"),
                "timestamp": ch.get("timestamp"),
                "displayUri": ch.get("displayUri"),
            }
            for ch in changes
        ]
    )


@app.command("failed-logs")
def failed_logs(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    build_id: int = typer.Option(..., "--build-id"),
    tail: int = typer.Option(200, "--tail", help="Lines of tail per failed step log."),
    max_steps: int = typer.Option(10, "--max-steps"),
) -> None:
    """Fetch the tail of logs for each failed step. JSON: list of {step, log}."""
    c = make_client(org)
    timeline = c.get(f"/_apis/build/builds/{build_id}/timeline", project=project) or {}
    records = timeline.get("records", []) or []
    failed = [r for r in records if r.get("result") == "failed" and (r.get("log") or {}).get("id")]
    # Prefer leaf failures (tasks) over their parent jobs.
    failed_ids = {r["id"] for r in failed}
    leaves = [r for r in failed if r.get("parentId") not in failed_ids] or failed
    leaves = leaves[:max_steps]

    out = []
    for r in leaves:
        log_id = (r.get("log") or {}).get("id")
        content = c.get(f"/_apis/build/builds/{build_id}/logs/{log_id}", project=project)
        text = content if isinstance(content, str) else (content or {}).get("value", "")
        lines = text.splitlines() if isinstance(text, str) else []
        out.append(
            {
                "stepId": r.get("id"),
                "stepName": r.get("name"),
                "stepType": r.get("type"),
                "errorCount": r.get("errorCount"),
                "logId": log_id,
                "lineCount": len(lines),
                "tail": "\n".join(lines[-tail:]),
            }
        )
    emit({"buildId": build_id, "failedSteps": out})


@app.command("duration-trend")
def duration_trend(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    definition_id: int = typer.Option(..., "--definition-id"),
    branch: str | None = typer.Option(None, "--branch"),
    top: int = typer.Option(30, "--top"),
) -> None:
    """Show duration trend stats for the most recent N builds of a definition."""
    c = make_client(org)
    params: dict[str, Any] = {
        "definitions": definition_id,
        "$top": top,
        "queryOrder": "finishTimeDescending",
        "statusFilter": "completed",
    }
    if branch:
        params["branchName"] = branch if branch.startswith("refs/") else f"refs/heads/{branch}"

    data = c.get("/_apis/build/builds", project=project, params=params)
    builds = (data or {}).get("value", [])

    rows = []
    durations: list[float] = []
    for b in builds:
        start = _parse_dt(b.get("startTime"))
        finish = _parse_dt(b.get("finishTime"))
        dur = (finish - start).total_seconds() if start and finish else None
        if dur is not None:
            durations.append(dur)
        rows.append(
            {
                "id": b.get("id"),
                "buildNumber": b.get("buildNumber"),
                "result": b.get("result"),
                "sourceBranch": b.get("sourceBranch"),
                "finishTime": b.get("finishTime"),
                "durationSeconds": dur,
            }
        )

    stats = {}
    if durations:
        stats = {
            "count": len(durations),
            "minSeconds": min(durations),
            "maxSeconds": max(durations),
            "meanSeconds": statistics.mean(durations),
            "medianSeconds": statistics.median(durations),
            "stdevSeconds": statistics.stdev(durations) if len(durations) > 1 else 0.0,
        }
        # Simple regression: compare last 5 vs prior 5. Builds were fetched
        # finishTimeDescending, so durations[:5] is the most recent 5 and
        # durations[5:10] the 5 immediately before them.
        if len(durations) >= 10:
            recent = statistics.mean(durations[:5])
            prior = statistics.mean(durations[5:10])
            stats["recent5MeanSeconds"] = recent
            stats["prior5MeanSeconds"] = prior
            stats["recentVsPriorPct"] = round(((recent - prior) / prior) * 100, 1) if prior else None

    emit({"definitionId": definition_id, "stats": stats, "builds": rows})


@app.command("flaky")
def flaky(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    definition_id: int = typer.Option(..., "--definition-id"),
    branch: str | None = typer.Option(None, "--branch"),
    top: int = typer.Option(50, "--top"),
) -> None:
    """Detect pass/fail churn for a pipeline. Emits flip count, fail rate, streaks."""
    c = make_client(org)
    params: dict[str, Any] = {
        "definitions": definition_id,
        "$top": top,
        "queryOrder": "finishTimeDescending",
        "statusFilter": "completed",
    }
    if branch:
        params["branchName"] = branch if branch.startswith("refs/") else f"refs/heads/{branch}"

    data = c.get("/_apis/build/builds", project=project, params=params)
    builds = (data or {}).get("value", [])
    # Oldest -> newest for streak calc.
    builds_ordered = list(reversed(builds))
    results = [b.get("result") for b in builds_ordered]

    flips = sum(1 for i in range(1, len(results)) if results[i] != results[i - 1])
    fails = sum(1 for r in results if r == "failed")
    total = len(results)
    fail_rate = round(fails / total, 3) if total else None

    # Current streak.
    streak_kind = results[-1] if results else None
    streak_len = 0
    for r in reversed(results):
        if r == streak_kind:
            streak_len += 1
        else:
            break

    emit(
        {
            "definitionId": definition_id,
            "windowSize": total,
            "flips": flips,
            "failCount": fails,
            "failRate": fail_rate,
            "currentStreak": {"result": streak_kind, "length": streak_len},
            "verdict": (
                "flaky"
                if total >= 10 and flips >= max(3, total // 5) and 0.1 < (fail_rate or 0) < 0.9
                else ("stable" if total >= 5 else "insufficient_data")
            ),
            "recent": [
                {"id": b.get("id"), "result": b.get("result"), "finishTime": b.get("finishTime")}
                for b in builds[:10]
            ],
        }
    )


if __name__ == "__main__":
    app()
