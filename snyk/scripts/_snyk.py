"""Shared Snyk REST API helpers (read-only).

Config: SNYK_TOKEN (personal API token), optional SNYK_ORG_ID and SNYK_API_URL (EU tenants: https://api.eu.snyk.io).
TLS goes through the OS trust store (truststore) so corporate proxies like Zscaler work.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
from dataclasses import dataclass
from typing import Any

import httpx
import truststore

API_VERSION = "2025-11-05"


@dataclass
class SnykClient:
    base: str
    http: httpx.Client

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        clean = {k: _param(v) for k, v in (params or {}).items() if v is not None and v != []}
        clean.setdefault("version", API_VERSION)
        r = self.http.get(f"{self.base}/rest{path}", params=clean)
        _raise(r)
        return r.json()

    def paged(self, path: str, params: dict[str, Any], limit: int) -> tuple[list[Any], dict[str, Any]]:
        """Follow JSON:API `links.next` up to `limit` items; also return the first page body."""
        items: list[Any] = []
        data = self.get(path, {**params, "limit": min(max(limit, 10), 100)})
        first = data
        while True:
            items.extend(data.get("data", []))
            nxt = (data.get("links") or {}).get("next")
            if isinstance(nxt, dict):
                nxt = nxt.get("href")
            if not nxt or len(items) >= limit:
                return items[:limit], first
            r = self.http.get(self._absolute(nxt))
            _raise(r)
            data = r.json()

    def _absolute(self, link: str) -> str:
        if link.startswith("http"):
            return link
        return f"{self.base}{link}" if link.startswith("/rest/") else f"{self.base}/rest{link}"


def _param(v: Any) -> Any:
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, (list, tuple)):
        return ",".join(str(x) for x in v)
    return v


def _raise(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    hint = ""
    if r.status_code == 401:
        hint = (
            "\nHint: SNYK_TOKEN is missing or expired, or the tenant is regional "
            "(set SNYK_API_URL, e.g. https://api.eu.snyk.io)."
        )
    elif r.status_code in (403, 404):
        hint = "\nHint: check the org id (snyk.py orgs) and that your user is a member of that org."
    raise SystemExit(f"Snyk API error {r.status_code} on GET {r.request.url}\n{r.text[:2000]}{hint}")


def make_client(timeout: float = 30.0) -> SnykClient:
    token = os.environ.get("SNYK_TOKEN")
    if not token:
        raise SystemExit(
            "SNYK_TOKEN is not set.\n"
            "Create a personal API token at https://app.snyk.io/account (or app.eu.snyk.io), then:\n"
            "  export SNYK_TOKEN=..."
        )
    base = os.environ.get("SNYK_API_URL", "https://api.snyk.io").rstrip("/").removesuffix("/rest")
    http = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.api+json"},
    )
    return SnykClient(base=base, http=http)


def resolve_org(cli_org: str | None) -> str:
    org = cli_org or os.environ.get("SNYK_ORG_ID")
    if not org:
        raise SystemExit("No org. Pass --org or set SNYK_ORG_ID. List your orgs with: snyk.py orgs")
    return org


def emit(obj: Any) -> None:
    json.dump(obj, sys.stdout, indent=2, default=str, ensure_ascii=False)
    sys.stdout.write("\n")
