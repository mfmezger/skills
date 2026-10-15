"""Shared SonarQube Server Web API helpers (read-only).

Config: SONAR_HOST_URL and SONAR_TOKEN env vars; the token is sent as a Bearer header.
TLS goes through the OS trust store (truststore) so corporate proxies like Zscaler work.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import truststore


@dataclass
class SonarClient:
    host: str
    http: httpx.Client

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        clean = {k: _param(v) for k, v in (params or {}).items() if v is not None and v != []}
        r = self.http.get(f"{self.host}{path}", params=clean)
        _raise(r)
        ct = r.headers.get("content-type", "")
        return r.json() if "json" in ct else r.text

    def paged(self, path: str, key: str, params: dict[str, Any], limit: int) -> tuple[list[Any], dict[str, Any]]:
        """Collect `key` items across pages up to `limit`; also return the first page body."""
        items: list[Any] = []
        page = 1
        first: dict[str, Any] = {}
        page_size = min(max(limit, 1), 500)
        while len(items) < limit:
            data = self.get(path, {**params, "p": page, "ps": page_size})
            if page == 1:
                first = data
            batch = data.get(key, [])
            items.extend(batch)
            total = (data.get("paging") or {}).get("total", len(items))
            if not batch or len(items) >= total:
                break
            page += 1
        return items[:limit], first


def _param(v: Any) -> Any:
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (list, tuple)):
        return ",".join(str(x) for x in v)
    return v


class SonarApiError(SystemExit):
    def __init__(self, status: int, body: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _raise(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    hint = ""
    if r.status_code == 401:
        hint = "\nHint: SONAR_TOKEN is missing, expired or not a user token (squ_...)."
    elif r.status_code == 403:
        hint = "\nHint: the token's user lacks 'Browse' permission on this project."
    msg = f"SonarQube API error {r.status_code} on GET {r.request.url}\n{r.text[:2000]}{hint}"
    raise SonarApiError(r.status_code, r.text, msg)


def make_client(timeout: float = 30.0) -> SonarClient:
    host = os.environ.get("SONAR_HOST_URL", "").rstrip("/")
    token = os.environ.get("SONAR_TOKEN")
    missing = [n for n, v in (("SONAR_HOST_URL", host), ("SONAR_TOKEN", token)) if not v]
    if missing:
        raise SystemExit(
            f"Not set: {', '.join(missing)}.\n"
            "  export SONAR_HOST_URL=https://sonarqube.schwarz\n"
            "  export SONAR_TOKEN=squ_...   # My Account > Security > Generate Tokens (type: User)"
        )
    if not host.startswith("http"):
        host = f"https://{host}"
    http = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        headers={"Authorization": f"Bearer {token}"},
    )
    return SonarClient(host=host, http=http)


def resolve_project(cli_project: str | None) -> str:
    """--project > SONAR_PROJECT_KEY > sonar-project.properties / pyproject [tool.sonar] in cwd or git root."""
    if cli_project:
        return cli_project
    if env := os.environ.get("SONAR_PROJECT_KEY"):
        return env
    for d in _search_dirs():
        props = d / "sonar-project.properties"
        if props.is_file():
            m = re.search(r"^\s*sonar\.projectKey\s*[=:]\s*(\S+)", props.read_text(), re.MULTILINE)
            if m:
                return m.group(1)
        pyproject = d / "pyproject.toml"
        if pyproject.is_file():
            sonar = tomllib.loads(pyproject.read_text()).get("tool", {}).get("sonar", {})
            if key := sonar.get("projectKey") or sonar.get("sonar.projectKey"):
                return key
    raise SystemExit(
        "No project key. Pass --project, set SONAR_PROJECT_KEY, or add sonar.projectKey to "
        "sonar-project.properties. Find keys with: sonar.py projects --query <name>"
    )


def _search_dirs() -> list[Path]:
    """cwd and its parents up to (and including) the git root."""
    d = Path.cwd()
    dirs = [d]
    while not (d / ".git").exists() and d.parent != d and d != Path.home():
        d = d.parent
        dirs.append(d)
    return dirs


def emit(obj: Any) -> None:
    json.dump(obj, sys.stdout, indent=2, default=str, ensure_ascii=False)
    sys.stdout.write("\n")
