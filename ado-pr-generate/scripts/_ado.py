"""Shared Azure DevOps REST helpers.

Auth: `AZURE_DEVOPS_PAT` env var (basic auth, blank user). PAT-only by
choice — it works regardless of corporate AAD / proxy quirks and avoids
the Azure CLI dependency.

Org resolution: --org flag > AZURE_DEVOPS_ORG env > error.

This module is intentionally dependency-light: stdlib + httpx (declared in
each script's PEP 723 inline metadata).
"""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_API_VERSION = "7.1"


@dataclass
class AdoClient:
    org: str
    auth_header: str
    client: httpx.Client

    @property
    def base_url(self) -> str:
        return f"https://dev.azure.com/{self.org}"

    def _full_url(self, path: str, project: str | None = None) -> str:
        if path.startswith("http"):
            return path
        prefix = f"/{project}" if project else ""
        return f"{self.base_url}{prefix}{path}"

    def get(
        self,
        path: str,
        *,
        project: str | None = None,
        params: dict[str, Any] | None = None,
        api_version: str = DEFAULT_API_VERSION,
    ) -> Any:
        params = dict(params or {})
        params.setdefault("api-version", api_version)
        url = self._full_url(path, project)
        r = self.client.get(url, params=params, headers={"Authorization": self.auth_header})
        _raise(r)
        if not r.content:
            return None
        # ADO occasionally returns text/plain (e.g. raw log content).
        ct = r.headers.get("content-type", "")
        return r.json() if "json" in ct else r.text

    def post(
        self,
        path: str,
        *,
        project: str | None = None,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        api_version: str = DEFAULT_API_VERSION,
    ) -> Any:
        params = dict(params or {})
        params.setdefault("api-version", api_version)
        url = self._full_url(path, project)
        r = self.client.post(
            url,
            params=params,
            json=json_body,
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
            },
        )
        _raise(r)
        return r.json() if r.content else None

    def patch(
        self,
        path: str,
        *,
        project: str | None = None,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        api_version: str = DEFAULT_API_VERSION,
    ) -> Any:
        params = dict(params or {})
        params.setdefault("api-version", api_version)
        url = self._full_url(path, project)
        r = self.client.patch(
            url,
            params=params,
            json=json_body,
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
            },
        )
        _raise(r)
        return r.json() if r.content else None

    def paged_get(
        self,
        path: str,
        *,
        project: str | None = None,
        params: dict[str, Any] | None = None,
        api_version: str = DEFAULT_API_VERSION,
        max_items: int | None = None,
    ) -> list[Any]:
        """Iterate `value` arrays across continuation tokens."""
        items: list[Any] = []
        params = dict(params or {})
        while True:
            data = self.get(path, project=project, params=params, api_version=api_version)
            if not isinstance(data, dict):
                break
            items.extend(data.get("value", []) or [])
            if max_items is not None and len(items) >= max_items:
                return items[:max_items]
            # ADO uses different continuation mechanisms; this handles the
            # standard `x-ms-continuationtoken` style by re-issuing with the
            # same params plus the token. Most endpoints we touch don't need
            # this, but it's harmless when absent.
            cont = None
            for k, v in data.items():
                if k.lower() == "continuationtoken":
                    cont = v
                    break
            if not cont:
                break
            params["continuationToken"] = cont
        return items


def _raise(r: httpx.Response) -> None:
    if r.status_code >= 400:
        body = r.text[:2000]
        # 401/403 with PAT auth almost always means the token is missing
        # the required scope or has expired — give an actionable hint.
        hint = ""
        if r.status_code in (401, 403) and os.environ.get("AZURE_DEVOPS_PAT"):
            hint = (
                "\n\nHint: PAT may lack the required scope or has expired.\n"
                "  - Pipelines: Build (Read)\n"
                "  - PR generate: Code (Read & Write), Work Items (Read & Write) if linking\n"
                "  - PR review: Code (Read & Write)\n"
                "Create / refresh at: https://dev.azure.com/<org>/_usersSettings/tokens"
            )
        raise SystemExit(
            f"Azure DevOps API error {r.status_code} on {r.request.method} "
            f"{r.request.url}\n{body}{hint}"
        )


def resolve_org(cli_org: str | None) -> str:
    org = cli_org or os.environ.get("AZURE_DEVOPS_ORG")
    if not org:
        raise SystemExit(
            "Azure DevOps organization not set. Pass --org or set AZURE_DEVOPS_ORG."
        )
    return org


def get_auth_header() -> str:
    """Return Authorization header value from `AZURE_DEVOPS_PAT`."""
    pat = os.environ.get("AZURE_DEVOPS_PAT")
    if not pat:
        raise SystemExit(
            "AZURE_DEVOPS_PAT is not set.\n"
            "Create a Personal Access Token at:\n"
            "  https://dev.azure.com/<org>/_usersSettings/tokens\n"
            "then export it, e.g.:\n"
            "  export AZURE_DEVOPS_PAT=..."
        )
    encoded = base64.b64encode(f":{pat}".encode()).decode()
    return f"Basic {encoded}"


def make_client(cli_org: str | None, *, timeout: float = 30.0) -> AdoClient:
    org = resolve_org(cli_org)
    auth = get_auth_header()
    http = httpx.Client(timeout=timeout, follow_redirects=True)
    return AdoClient(org=org, auth_header=auth, client=http)


def emit(obj: Any) -> None:
    """Print as JSON to stdout. All scripts use JSON output so the calling
    LLM can parse reliably."""
    json.dump(obj, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
