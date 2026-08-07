#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "typer>=0.12"]
# ///
"""Azure DevOps Pull Request review CLI.

Subcommands:
  list           List PRs (mine | assigned-to-me | all-active) in a project/repo.
  summary        Summary of a single PR: metadata, reviewers, file stats, threads.
  diff           Diff of a PR (file list + unified diff per file) for AI review.
  ci             Build/status checks + policy evaluations for a PR.
  comment        Post a top-level comment to a PR.
  inline         Post an inline review comment on a file/line.
  vote           Set the current user's vote on a PR (approve / approve-with-suggestions /
                 wait-for-author / reject / reset).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import typer

sys.path.insert(0, str(Path(__file__).parent))
from _ado import DEFAULT_API_VERSION, emit, make_client  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)

VOTE_MAP = {
    "approve": 10,
    "approve-with-suggestions": 5,
    "reset": 0,
    "wait-for-author": -5,
    "reject": -10,
}


def _resolve_repo(c, project: str, repo_name: str) -> str:
    data = c.get("/_apis/git/repositories", project=project)
    for r in (data or {}).get("value", []):
        if r.get("name", "").lower() == repo_name.lower():
            return r["id"]
    raise SystemExit(f"Repository '{repo_name}' not found in project '{project}'.")


def _get_self_id(c) -> str:
    """Resolve the current authenticated user's descriptor for vote ops."""
    # The connectionData endpoint is the cheapest way to get the caller's id.
    r = c.client.get(
        f"{c.base_url}/_apis/connectionData",
        headers={"Authorization": c.auth_header},
    )
    if r.status_code >= 400:
        raise SystemExit(f"connectionData failed ({r.status_code}): {r.text[:300]}")
    data = r.json()
    return data["authenticatedUser"]["id"]


@app.command("list")
def list_prs(
    project: str = typer.Option(..., "--project", "-p"),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
    scope: str = typer.Option("all-active", "--scope", help="all-active | mine | assigned-to-me"),
    top: int = typer.Option(50, "--top"),
) -> None:
    """List PRs in a project (optionally one repo)."""
    c = make_client(org)
    params: dict[str, Any] = {
        "searchCriteria.status": "active",
        "$top": top,
    }
    if scope in {"mine", "assigned-to-me"}:
        self_id = _get_self_id(c)
        if scope == "mine":
            params["searchCriteria.creatorId"] = self_id
        else:
            params["searchCriteria.reviewerId"] = self_id

    if repo:
        repo_id = _resolve_repo(c, project, repo)
        path = f"/_apis/git/repositories/{repo_id}/pullrequests"
    else:
        path = "/_apis/git/pullrequests"

    data = c.get(path, project=project, params=params)
    prs = (data or {}).get("value", [])
    emit(
        [
            {
                "pullRequestId": p.get("pullRequestId"),
                "title": p.get("title"),
                "status": p.get("status"),
                "isDraft": p.get("isDraft"),
                "createdBy": (p.get("createdBy") or {}).get("displayName"),
                "creationDate": p.get("creationDate"),
                "sourceRefName": p.get("sourceRefName"),
                "targetRefName": p.get("targetRefName"),
                "repository": (p.get("repository") or {}).get("name"),
                "url": (
                    f"https://dev.azure.com/{c.org}/{project}/_git/"
                    f"{(p.get('repository') or {}).get('name')}/pullrequest/{p.get('pullRequestId')}"
                ),
            }
            for p in prs
        ]
    )


def _get_pr_repo(c, project: str, pr_id: int, repo: str | None) -> tuple[str, dict]:
    """Resolve repo id by either the --repo name or by fetching the PR
    org-wide first."""
    if repo:
        return _resolve_repo(c, project, repo), {}
    # Direct org-level fetch by PR id — one call, returns the PR with its
    # repository embedded. This is the documented endpoint and avoids the
    # N-request repo scan below for the common case.
    try:
        pr = c.get(f"/_apis/git/pullrequests/{pr_id}", project=project)
        if isinstance(pr, dict) and pr.get("repository", {}).get("id"):
            return pr["repository"]["id"], pr
    except SystemExit:
        pass
    # Fallback: search each repo (older ADO versions / edge cases).
    repos = c.get("/_apis/git/repositories", project=project) or {}
    for r in repos.get("value", []):
        try:
            pr = c.get(
                f"/_apis/git/repositories/{r['id']}/pullrequests/{pr_id}",
                project=project,
            )
            if pr:
                return r["id"], pr
        except SystemExit:
            continue
    raise SystemExit(f"PR {pr_id} not found in project {project}.")


@app.command()
def summary(
    project: str = typer.Option(..., "--project", "-p"),
    pr_id: int = typer.Option(..., "--pr-id"),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
) -> None:
    """Summary of a PR: metadata + reviewers + file stats + comment threads."""
    c = make_client(org)
    repo_id, pr = _get_pr_repo(c, project, pr_id, repo)
    if not pr:
        pr = c.get(f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}", project=project)

    # Iterations → use last iteration to get changed files.
    iters = c.get(
        f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}/iterations",
        project=project,
    )
    iter_values = (iters or {}).get("value", []) or []
    last_iter = iter_values[-1]["id"] if iter_values else None
    files: list[dict[str, Any]] = []
    if last_iter:
        changes = c.get(
            f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}/iterations/{last_iter}/changes",
            project=project,
        )
        for ce in (changes or {}).get("changeEntries", []) or []:
            item = ce.get("item") or {}
            files.append(
                {
                    "path": item.get("path"),
                    "changeType": ce.get("changeType"),
                }
            )

    threads = c.get(
        f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}/threads",
        project=project,
    )
    thread_summary = []
    for t in (threads or {}).get("value", []) or []:
        if t.get("isDeleted"):
            continue
        ctx = t.get("threadContext") or {}
        thread_summary.append(
            {
                "id": t.get("id"),
                "status": t.get("status"),
                "filePath": ctx.get("filePath"),
                "rightFileStart": ctx.get("rightFileStart"),
                "commentCount": len(t.get("comments") or []),
                "lastComment": (
                    (t.get("comments") or [{}])[-1].get("content", "")[:300]
                ),
            }
        )

    emit(
        {
            "pullRequestId": pr.get("pullRequestId"),
            "title": pr.get("title"),
            "description": pr.get("description"),
            "status": pr.get("status"),
            "isDraft": pr.get("isDraft"),
            "mergeStatus": pr.get("mergeStatus"),
            "createdBy": (pr.get("createdBy") or {}).get("displayName"),
            "creationDate": pr.get("creationDate"),
            "sourceRefName": pr.get("sourceRefName"),
            "targetRefName": pr.get("targetRefName"),
            "reviewers": [
                {
                    "displayName": rv.get("displayName"),
                    "vote": rv.get("vote"),
                    "isRequired": rv.get("isRequired"),
                }
                for rv in pr.get("reviewers", []) or []
            ],
            "fileCount": len(files),
            "files": files,
            "threadCount": len(thread_summary),
            "threads": thread_summary,
            "url": (
                f"https://dev.azure.com/{c.org}/{project}/_git/"
                f"{(pr.get('repository') or {}).get('name')}/pullrequest/{pr.get('pullRequestId')}"
            ),
        }
    )


# Extensions we never try to diff. Cheaper and more reliable than
# null-byte sniffing for well-known formats, and avoids fetching the
# file at all.
_BINARY_EXTS = frozenset({
    # images
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif",
    ".ico", ".heic", ".avif", ".psd",
    # audio / video
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".mp4", ".mov", ".avi",
    ".mkv", ".webm",
    # archives / packages
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
    ".jar", ".war", ".ear", ".whl", ".egg", ".nupkg",
    # docs / fonts
    ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # databases / data
    ".db", ".sqlite", ".sqlite3", ".mdb", ".parquet", ".arrow",
    ".feather", ".h5", ".hdf5", ".npy", ".npz", ".pkl", ".pickle",
    # compiled / binaries
    ".so", ".dylib", ".dll", ".exe", ".o", ".a", ".class", ".pyc",
    ".pyo", ".wasm", ".bin", ".dat",
    # ML model weights
    ".pt", ".pth", ".safetensors", ".onnx", ".pb", ".tflite", ".gguf",
    # disk / container images
    ".iso", ".img", ".dmg", ".vmdk", ".qcow2",
})

# Generated text files that are technically text but produce diffs no
# human (or LLM) wants to wade through. Detected by basename, not extension.
_NOISY_BASENAMES = frozenset({
    "uv.lock", "poetry.lock", "Pipfile.lock", "requirements.txt.lock",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum",
})

# 1 MiB. Bigger than any sane source file. Diffing larger files blows
# up the JSON output and adds nothing of review value.
_MAX_TEXT_BYTES = 1 * 1024 * 1024

# git's own heuristic: scan the first 8 KiB for NUL bytes.
_BINARY_SNIFF_BYTES = 8 * 1024


def _looks_binary(raw: bytes) -> bool:
    """Return True if `raw` looks binary (contains a NUL in the first 8 KiB).

    This is the same heuristic git uses. False positives on UTF-16 text
    are theoretically possible but vanishingly rare in code repos.
    """
    return b"\x00" in raw[:_BINARY_SNIFF_BYTES]


@app.command()
def diff(
    project: str = typer.Option(..., "--project", "-p"),
    pr_id: int = typer.Option(..., "--pr-id"),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
    max_files: int = typer.Option(40, "--max-files"),
    context: int = typer.Option(3, "--context"),
    path_filter: list[str] = typer.Option([], "--path", help="Only diff these paths. Repeatable."),
    max_file_bytes: int = typer.Option(_MAX_TEXT_BYTES, "--max-file-bytes",
                                       help="Skip files larger than this on either side."),
    include_lockfiles: bool = typer.Option(False, "--include-lockfiles",
                                           help="By default, lockfiles (uv.lock, package-lock.json, etc.) are summarized instead of diffed."),
) -> None:
    """Emit per-file unified diffs of a PR. Use this output to do an AI code review.

    Strategy: get last iteration → diff source vs target commit using the
    Git Items + Diffs API. To stay reliable across ADO versions, we use the
    base→target commit comparison and fetch file contents at each side, then
    produce a unified diff client-side.

    Binary files are detected via (1) extension blocklist, (2) a size cap,
    and (3) NUL-byte sniffing of the raw response — in that order, cheapest
    first. Skipped files are reported with a reason so the reviewer knows
    what wasn't diffed.
    """
    import difflib
    from pathlib import PurePosixPath

    c = make_client(org)
    repo_id, pr = _get_pr_repo(c, project, pr_id, repo)
    if not pr:
        pr = c.get(f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}", project=project)

    iters = c.get(
        f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}/iterations",
        project=project,
    )
    iter_values = (iters or {}).get("value", []) or []
    if not iter_values:
        emit({"pullRequestId": pr_id, "files": []})
        return
    last = iter_values[-1]
    last_id = last["id"]
    base_commit = (last.get("commonRefCommit") or {}).get("commitId")
    target_commit = (last.get("sourceRefCommit") or {}).get("commitId")

    changes = c.get(
        f"/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}/iterations/{last_id}/changes",
        project=project,
    )
    entries = (changes or {}).get("changeEntries", []) or []

    def fetch_blob(commit_id: str, path: str) -> tuple[bytes | None, str | None]:
        """Fetch a blob as raw bytes. Returns (bytes, skip_reason).

        Returns (None, reason) when fetch failed or the blob shouldn't be
        diffed. Returns (bytes, None) on success.
        """
        if not commit_id or not path:
            return None, None
        url = f"{c.base_url}/{project}/_apis/git/repositories/{repo_id}/items"
        try:
            r = c.client.get(
                url,
                params={
                    "path": path,
                    "versionDescriptor.version": commit_id,
                    "versionDescriptor.versionType": "commit",
                    "includeContent": "true",
                    "api-version": DEFAULT_API_VERSION,
                },
                # Don't claim text/plain — ADO ignores it for binaries
                # anyway and it adds a false signal.
                headers={"Authorization": c.auth_header},
            )
        except httpx.HTTPError:
            return None, "fetch_error"
        if r.status_code == 404:
            return None, None  # file didn't exist on that side
        if r.status_code >= 400:
            return None, f"http_{r.status_code}"
        raw = r.content
        if len(raw) > max_file_bytes:
            return None, f"too_large ({len(raw)} bytes)"
        if _looks_binary(raw):
            return None, "binary (NUL byte detected)"
        return raw, None

    out_files: list[dict[str, Any]] = []
    for ce in entries[:max_files]:
        item = ce.get("item") or {}
        path = item.get("path")
        if not path:
            continue
        if path_filter and not any(path == p or path.startswith(p) for p in path_filter):
            continue
        change_type = (ce.get("changeType") or "").lower()

        # Cheap filter 1: non-blob git objects (submodules, trees).
        if (item.get("gitObjectType") or "").lower() not in {"", "blob"}:
            out_files.append({"path": path, "changeType": change_type,
                              "diff": "", "skipped": "non-blob object"})
            continue

        # Cheap filter 2: extension blocklist. Don't even fetch.
        suffix = PurePosixPath(path).suffix.lower()
        if suffix in _BINARY_EXTS:
            out_files.append({"path": path, "changeType": change_type,
                              "diff": "", "skipped": f"binary extension ({suffix})"})
            continue

        # Cheap filter 3: known noisy lockfiles.
        basename = PurePosixPath(path).name
        if not include_lockfiles and basename in _NOISY_BASENAMES:
            out_files.append({"path": path, "changeType": change_type,
                              "diff": "", "skipped": f"lockfile ({basename}); pass --include-lockfiles to diff"})
            continue

        before_bytes, before_skip = (None, None) if "add" in change_type else fetch_blob(base_commit, path)
        after_bytes, after_skip = (None, None) if "delete" in change_type else fetch_blob(target_commit, path)

        # Bubble up a skip reason from either side.
        skip_reason = before_skip or after_skip
        if skip_reason:
            out_files.append({"path": path, "changeType": change_type,
                              "diff": "", "skipped": skip_reason})
            continue

        # Decode — by this point we've sniffed for NULs so utf-8 should
        # almost always work; replace errors rather than blowing up.
        before = before_bytes.decode("utf-8", errors="replace") if before_bytes else ""
        after = after_bytes.decode("utf-8", errors="replace") if after_bytes else ""

        if before == after:
            out_files.append(
                {"path": path, "changeType": change_type, "diff": "", "note": "no textual diff"}
            )
            continue

        diff_text = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                n=context,
            )
        )
        out_files.append({"path": path, "changeType": change_type, "diff": diff_text})

    emit(
        {
            "pullRequestId": pr_id,
            "baseCommit": base_commit,
            "targetCommit": target_commit,
            "fileCount": len(entries),
            "files": out_files,
            "truncated": len(entries) > max_files,
        }
    )


@app.command()
def ci(
    project: str = typer.Option(..., "--project", "-p"),
    pr_id: int = typer.Option(..., "--pr-id"),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
) -> None:
    """Show status checks + policy evaluations on the PR."""
    c = make_client(org)
    repo_id, pr = _get_pr_repo(c, project, pr_id, repo)

    # PR statuses (commit-status style checks).
    statuses = c.get(
        f"/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/statuses",
        project=project,
    )

    # Policy evaluations require the PR's artifact URI.
    artifact_uri = f"vstfs:///CodeReview/CodeReviewId/{c.org}/{pr_id}"
    # The policy endpoint sits at the org level (no project prefix).
    pol = c.get(
        f"/{project}/_apis/policy/evaluations",
        params={"artifactId": artifact_uri},
    )

    emit(
        {
            "pullRequestId": pr_id,
            "statuses": [
                {
                    "name": (s.get("context") or {}).get("name"),
                    "genre": (s.get("context") or {}).get("genre"),
                    "state": s.get("state"),
                    "description": s.get("description"),
                    "targetUrl": s.get("targetUrl"),
                }
                for s in (statuses or {}).get("value", []) or []
            ],
            "policyEvaluations": [
                {
                    "displayName": ((p.get("configuration") or {}).get("type") or {}).get("displayName"),
                    "status": p.get("status"),
                    "isBlocking": (p.get("configuration") or {}).get("isBlocking"),
                    "settings": ((p.get("configuration") or {}).get("settings") or {}).get("displayName")
                    or (p.get("configuration") or {}).get("settings", {}).get("buildDefinitionId"),
                }
                for p in (pol or {}).get("value", []) or []
            ],
        }
    )


@app.command()
def comment(
    project: str = typer.Option(..., "--project", "-p"),
    pr_id: int = typer.Option(..., "--pr-id"),
    text: str = typer.Option(..., "--text"),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
) -> None:
    """Post a single top-level comment thread."""
    c = make_client(org)
    repo_id, _ = _get_pr_repo(c, project, pr_id, repo)
    body = {
        "comments": [{"parentCommentId": 0, "content": text, "commentType": 1}],
        "status": 1,
    }
    res = c.post(
        f"/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads",
        project=project,
        json_body=body,
    )
    emit({"threadId": res.get("id"), "pullRequestId": pr_id})


@app.command()
def inline(
    project: str = typer.Option(..., "--project", "-p"),
    pr_id: int = typer.Option(..., "--pr-id"),
    file_path: str = typer.Option(..., "--file"),
    line: int = typer.Option(..., "--line"),
    text: str = typer.Option(..., "--text"),
    side: str = typer.Option("right", "--side", help="right (new) | left (old)"),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
) -> None:
    """Post an inline review comment anchored to a file + line."""
    c = make_client(org)
    repo_id, _ = _get_pr_repo(c, project, pr_id, repo)
    ctx_key = "rightFileStart" if side == "right" else "leftFileStart"
    end_key = "rightFileEnd" if side == "right" else "leftFileEnd"
    body = {
        "comments": [{"parentCommentId": 0, "content": text, "commentType": 1}],
        "status": 1,
        "threadContext": {
            "filePath": file_path if file_path.startswith("/") else f"/{file_path}",
            ctx_key: {"line": line, "offset": 1},
            end_key: {"line": line, "offset": 1},
        },
    }
    res = c.post(
        f"/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads",
        project=project,
        json_body=body,
    )
    emit({"threadId": res.get("id"), "pullRequestId": pr_id, "file": file_path, "line": line})


@app.command()
def vote(
    project: str = typer.Option(..., "--project", "-p"),
    pr_id: int = typer.Option(..., "--pr-id"),
    decision: str = typer.Option(..., "--decision", help=", ".join(VOTE_MAP)),
    org: str | None = typer.Option(None, "--org"),
    repo: str | None = typer.Option(None, "--repo"),
) -> None:
    """Cast the current user's vote on the PR."""
    if decision not in VOTE_MAP:
        raise SystemExit(f"Unknown decision '{decision}'. Use one of: {', '.join(VOTE_MAP)}")
    c = make_client(org)
    repo_id, _ = _get_pr_repo(c, project, pr_id, repo)
    self_id = _get_self_id(c)
    url = (
        f"{c.base_url}/{project}/_apis/git/repositories/{repo_id}/"
        f"pullRequests/{pr_id}/reviewers/{self_id}"
    )
    r = c.client.put(
        url,
        params={"api-version": DEFAULT_API_VERSION},
        json={"vote": VOTE_MAP[decision]},
        headers={"Authorization": c.auth_header, "Content-Type": "application/json"},
    )
    if r.status_code >= 400:
        raise SystemExit(f"vote failed ({r.status_code}): {r.text[:500]}")
    emit({"pullRequestId": pr_id, "decision": decision, "vote": VOTE_MAP[decision]})


if __name__ == "__main__":
    app()
