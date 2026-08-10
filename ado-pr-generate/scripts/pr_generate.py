#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "typer>=0.12"]
# ///
"""Create or update an Azure DevOps Pull Request from the current branch.

Subcommands:
  detect       Inspect the current git checkout and report repo/branch/commits.
               Use this first to gather context for title/description generation.
  create       Create a new PR (or update existing if --pr-id given) from the
               current branch to a target branch.
  update       Update an existing PR (title/description/draft/work items).
  link-wi      Link work items to an existing PR.
  comment      Add a single top-level comment thread to a PR.

The "create" command is intentionally deterministic: the caller (LLM) is
expected to compute the title and description from `detect` output and pass
them in, rather than this script trying to summarize commits itself.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer

sys.path.insert(0, str(Path(__file__).parent))
from _ado import DEFAULT_API_VERSION, emit, make_client  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

WI_PATTERN = re.compile(r"(?:AB#|#)(\d{2,7})")


def _git(*args: str, cwd: str | None = None) -> str:
    r = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=cwd, check=False
    )
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.rstrip("\n")


def _parse_remote(url: str) -> tuple[str, str, str] | None:
    """Return (org, project, repo) for an Azure DevOps remote, else None.

    Handles:
      https://dev.azure.com/{org}/{project}/_git/{repo}
      https://{org}@dev.azure.com/{org}/{project}/_git/{repo}
      git@ssh.dev.azure.com:v3/{org}/{project}/{repo}
      https://{org}.visualstudio.com/{project}/_git/{repo}
    """
    if url.startswith("git@ssh.dev.azure.com:"):
        rest = url.split(":", 1)[1]  # v3/org/project/repo
        parts = rest.split("/")
        if len(parts) >= 4 and parts[0] == "v3":
            return parts[1], parts[2], parts[3]
        return None

    p = urlparse(url)
    host = p.hostname or ""
    parts = [s for s in p.path.split("/") if s]

    if host.endswith("dev.azure.com"):
        # /{org}/{project}/_git/{repo}
        if len(parts) >= 4 and parts[2] == "_git":
            return parts[0], parts[1], parts[3]
    if host.endswith("visualstudio.com"):
        org = host.split(".")[0]
        # /{project}/_git/{repo}
        if len(parts) >= 3 and parts[1] == "_git":
            return org, parts[0], parts[2]
    return None


def _detect_context(repo_path: str) -> dict[str, Any]:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_path)
    if branch == "HEAD":
        raise SystemExit("Detached HEAD — checkout a branch before creating a PR.")

    remotes_raw = _git("remote", "-v", cwd=repo_path).splitlines()
    remotes: dict[str, str] = {}
    for line in remotes_raw:
        parts = line.split()
        if len(parts) >= 2:
            remotes[parts[0]] = parts[1]
    remote_url = remotes.get("origin") or next(iter(remotes.values()), "")
    parsed = _parse_remote(remote_url) if remote_url else None

    # Default branch from origin/HEAD if available.
    default_branch = None
    try:
        ref = _git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=repo_path)
        default_branch = ref.rsplit("/", 1)[-1]
    except SystemExit:
        for cand in ("main", "master"):
            r = subprocess.run(
                ["git", "rev-parse", "--verify", f"origin/{cand}"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                check=False,
            )
            if r.returncode == 0:
                default_branch = cand
                break

    return {
        "branch": branch,
        "defaultBranch": default_branch,
        "remoteUrl": remote_url,
        "org": parsed[0] if parsed else None,
        "project": parsed[1] if parsed else None,
        "repo": parsed[2] if parsed else None,
    }


@app.command()
def detect(
    repo_path: str = typer.Option(".", "--repo-path"),
    base: str | None = typer.Option(None, "--base", help="Override target branch for diff context."),
    log_limit: int = typer.Option(20, "--log-limit"),
) -> None:
    """Report git context + recent commits + diff stats vs the target branch.

    Output is intended as input for an LLM to generate a PR title + description.
    """
    ctx = _detect_context(repo_path)
    target = base or ctx["defaultBranch"] or "main"

    # Ensure target ref exists locally; if not, skip diff stats gracefully.
    target_ref = f"origin/{target}"
    has_target = subprocess.run(
        ["git", "rev-parse", "--verify", target_ref],
        capture_output=True,
        cwd=repo_path,
        check=False,
    ).returncode == 0

    commits: list[dict[str, str]] = []
    diff_stat = None
    files: list[str] = []
    wi_ids: set[str] = set()

    if has_target:
        log_raw = _git(
            "log",
            f"{target_ref}..HEAD",
            f"-n{log_limit}",
            "--pretty=format:%H%x1f%s%x1f%an%x1f%ae",
            cwd=repo_path,
        )
        for line in log_raw.splitlines():
            if not line:
                continue
            sha, subject, name, email = line.split("\x1f")
            commits.append({"sha": sha, "subject": subject, "author": name, "email": email})
            for m in WI_PATTERN.finditer(subject):
                wi_ids.add(m.group(1))
        diff_stat = _git("diff", "--shortstat", f"{target_ref}...HEAD", cwd=repo_path)
        files = _git("diff", "--name-only", f"{target_ref}...HEAD", cwd=repo_path).splitlines()

    # Also scan the branch name itself for work item refs.
    for m in WI_PATTERN.finditer(ctx["branch"]):
        wi_ids.add(m.group(1))

    emit(
        {
            **ctx,
            "targetBranch": target,
            "commits": commits,
            "diffShortstat": diff_stat,
            "changedFiles": files,
            "workItemIds": sorted(wi_ids, key=int),
        }
    )


def _push_branch(branch: str, repo_path: str) -> None:
    subprocess.run(
        ["git", "push", "--set-upstream", "origin", branch],
        cwd=repo_path,
        check=True,
    )


def _resolve_repo(c, project: str, repo_name: str) -> str:
    """Return repo ID for a repo name within a project."""
    data = c.get("/_apis/git/repositories", project=project)
    for r in (data or {}).get("value", []):
        if r.get("name", "").lower() == repo_name.lower():
            return r["id"]
    raise SystemExit(f"Repository '{repo_name}' not found in project '{project}'.")


@app.command()
def create(
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option("", "--description"),
    project: str | None = typer.Option(None, "--project"),
    repo: str | None = typer.Option(None, "--repo"),
    org: str | None = typer.Option(None, "--org"),
    source_branch: str | None = typer.Option(None, "--source-branch"),
    target_branch: str | None = typer.Option(None, "--target-branch"),
    draft: bool = typer.Option(False, "--draft/--no-draft"),
    work_item: list[int] = typer.Option([], "--work-item", help="Work item ID. Repeatable."),
    push: bool = typer.Option(True, "--push/--no-push"),
    repo_path: str = typer.Option(".", "--repo-path"),
) -> None:
    """Create a PR. Auto-detects project/repo/source/target from git remote
    + current branch when not provided. Pushes the source branch first
    unless --no-push."""
    ctx = _detect_context(repo_path)
    project = project or ctx["project"]
    repo = repo or ctx["repo"]
    source_branch = source_branch or ctx["branch"]
    target_branch = target_branch or ctx["defaultBranch"] or "main"

    if not project or not repo:
        raise SystemExit(
            "Could not infer project/repo from git remote. "
            "Pass --project and --repo explicitly."
        )

    if push:
        _push_branch(source_branch, repo_path)

    c = make_client(org)
    repo_id = _resolve_repo(c, project, repo)

    body: dict[str, Any] = {
        "sourceRefName": f"refs/heads/{source_branch}",
        "targetRefName": f"refs/heads/{target_branch}",
        "title": title,
        "description": description,
        "isDraft": draft,
    }
    if work_item:
        body["workItemRefs"] = [{"id": str(wid)} for wid in work_item]

    pr = c.post(
        f"/_apis/git/repositories/{repo_id}/pullrequests",
        project=project,
        json_body=body,
    )
    pr_id = pr.get("pullRequestId")
    emit(
        {
            "pullRequestId": pr_id,
            "title": pr.get("title"),
            "status": pr.get("status"),
            "isDraft": pr.get("isDraft"),
            "sourceRefName": pr.get("sourceRefName"),
            "targetRefName": pr.get("targetRefName"),
            "url": f"https://dev.azure.com/{c.org}/{project}/_git/{repo}/pullrequest/{pr_id}",
        }
    )


@app.command()
def update(
    pr_id: int = typer.Option(..., "--pr-id"),
    project: str | None = typer.Option(None, "--project"),
    repo: str | None = typer.Option(None, "--repo"),
    org: str | None = typer.Option(None, "--org"),
    title: str | None = typer.Option(None, "--title"),
    description: str | None = typer.Option(None, "--description"),
    draft: bool | None = typer.Option(None, "--draft/--no-draft"),
    target_branch: str | None = typer.Option(None, "--target-branch"),
    repo_path: str = typer.Option(".", "--repo-path"),
) -> None:
    """Patch an existing PR's metadata."""
    ctx = _detect_context(repo_path)
    project = project or ctx["project"]
    repo = repo or ctx["repo"]
    if not project or not repo:
        raise SystemExit("Could not infer project/repo. Pass --project and --repo.")

    c = make_client(org)
    repo_id = _resolve_repo(c, project, repo)
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if draft is not None:
        body["isDraft"] = draft
    if target_branch is not None:
        body["targetRefName"] = f"refs/heads/{target_branch}"
    if not body:
        raise SystemExit("Nothing to update — pass at least one of --title/--description/--draft/--target-branch.")

    pr = c.patch(
        f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}",
        project=project,
        json_body=body,
    )
    emit({"pullRequestId": pr.get("pullRequestId"), "updated": list(body.keys())})


@app.command("link-wi")
def link_wi(
    pr_id: int = typer.Option(..., "--pr-id"),
    work_item: list[int] = typer.Option(..., "--work-item"),
    project: str | None = typer.Option(None, "--project"),
    repo: str | None = typer.Option(None, "--repo"),
    org: str | None = typer.Option(None, "--org"),
    repo_path: str = typer.Option(".", "--repo-path"),
) -> None:
    """Link one or more work items to a PR via the work item relations API."""
    ctx = _detect_context(repo_path)
    project = project or ctx["project"]
    repo = repo or ctx["repo"]
    if not project or not repo:
        raise SystemExit("Could not infer project/repo. Pass --project and --repo.")

    c = make_client(org)
    repo_id = _resolve_repo(c, project, repo)
    # vstfs artifact URI for a PR.
    artifact_id = f"{c.org}%2F{project}%2F{repo_id}%2F{pr_id}"
    artifact_uri = f"vstfs:///Git/PullRequestId/{artifact_id}"

    linked: list[int] = []
    for wid in work_item:
        patch_body = [
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "ArtifactLink",
                    "url": artifact_uri,
                    "attributes": {"name": "Pull Request"},
                },
            }
        ]
        # Work item PATCH requires application/json-patch+json — emulate via
        # explicit Content-Type by going through the raw client.
        url = f"{c.base_url}/{project}/_apis/wit/workitems/{wid}"
        r = c.client.patch(
            url,
            params={"api-version": DEFAULT_API_VERSION},
            json=patch_body,
            headers={
                "Authorization": c.auth_header,
                "Content-Type": "application/json-patch+json",
            },
        )
        if r.status_code >= 400:
            raise SystemExit(f"Linking work item {wid} failed ({r.status_code}): {r.text[:500]}")
        linked.append(wid)

    emit({"pullRequestId": pr_id, "linkedWorkItems": linked})


@app.command()
def comment(
    pr_id: int = typer.Option(..., "--pr-id"),
    text: str = typer.Option(..., "--text"),
    project: str | None = typer.Option(None, "--project"),
    repo: str | None = typer.Option(None, "--repo"),
    org: str | None = typer.Option(None, "--org"),
    repo_path: str = typer.Option(".", "--repo-path"),
) -> None:
    """Post a single top-level comment thread to a PR."""
    ctx = _detect_context(repo_path)
    project = project or ctx["project"]
    repo = repo or ctx["repo"]
    if not project or not repo:
        raise SystemExit("Could not infer project/repo. Pass --project and --repo.")

    c = make_client(org)
    repo_id = _resolve_repo(c, project, repo)
    body = {
        "comments": [{"parentCommentId": 0, "content": text, "commentType": 1}],
        "status": 1,  # active
    }
    res = c.post(
        f"/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads",
        project=project,
        json_body=body,
    )
    emit({"threadId": res.get("id"), "pullRequestId": pr_id})


if __name__ == "__main__":
    app()
