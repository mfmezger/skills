---
name: snyk
description: "Read Snyk findings — open-source dependency vulnerabilities, license issues, Snyk Code (SAST) findings — for the projects of a repo via the Snyk REST API, or run a local `snyk test` / `snyk code test` and summarise it. Use when the user asks about Snyk, vulnerable dependencies or CVEs flagged by Snyk, or wants to fix Snyk issues in the current repo."
author: Marc Fabian Mezger <57255687+mfmezger@users.noreply.github.com>
---

# Snyk — read-only analysis

A self-contained Python CLI against the Snyk REST API. Every command prints JSON; summarise it
for the user (tables for lists, critical/high first).

**Read-only.** No ignores, no `snyk monitor`, no fix PRs, no project settings changes. Fix the
code or dependency instead; Snyk picks it up on its next test.

## Setup

- `uv` installed; the script declares its deps inline (PEP 723). Behind Zscaler, set
  `UV_SYSTEM_CERTS=1` so uv can download them. HTTPS calls use the OS trust store.
- `SNYK_TOKEN` — personal API token (Account settings → Auth Token).
- `SNYK_ORG_ID` — default org id; `orgs` lists the ids. `--org` overrides it.
- Optional `SNYK_API_URL` for regional tenants, e.g. `https://api.eu.snyk.io` (default
  `https://api.snyk.io`).
- `test` needs the Snyk CLI (`snyk` on PATH); the API commands do not.

Run `whoami` first when anything fails; a 401 usually means a bad token or the wrong region.

## CLI

```bash
uv run --script ~/.agents/skills/snyk/scripts/snyk.py <command> [options]
```

| Command | Purpose |
|---|---|
| `whoami` | Token check, user, default org. |
| `orgs [--name]` | Org ids and slugs. |
| `projects [-r <repo>]` | Projects (one per manifest or code scan) with branch and latest critical/high/medium/low counts. |
| `issues -r <repo>` / `-p <id>` | Open issues, worst first: `location` (`pkg@version` or `file:line`), `ids` (SNYK-/CVE-), `fix` options. Filters: `--severity critical,high`, `--type package_vulnerability\|license\|code\|…`, `--include-ignored`, `--limit` (per project). |
| `test [path] [--code] [--all-projects]` | Local scan with the Snyk CLI, deduplicated per manifest; nothing is uploaded. |

## Finding the projects

Snyk project names look like `<org>/<repo>(<branch>):<manifest>`; one repo has several projects
(one per manifest plus one for code). Use `projects -r <repo name>` and check the `branch`.
If nothing matches, say so — the repo may not be imported into Snyk; offer `test` instead.

## Fixing issues in the current repo

1. `issues -r <repo> --severity critical,high`.
2. Dependencies: prefer the smallest upgrade that clears the issue (`fix` contains
   `upgradeable`); update the lockfile with the project's tool (`uv lock --upgrade-package …`).
   Code findings: fix at `location`.
3. Verify locally with `test` (or `test --code`) when the CLI is installed, and run the tests.
