---
name: sonarqube
description: "Read SonarQube Server results for a project, branch or pull request — quality gate status and failing conditions, issues with file:line, security hotspots, coverage/duplication measures, and rule explanations. Use when the user asks about SonarQube or Sonar findings, a failing quality gate, code smells, coverage on SonarQube, or wants to fix Sonar issues in the current repo."
author: Marc Fabian Mezger <57255687+mfmezger@users.noreply.github.com>
---

# SonarQube — read-only analysis

A self-contained Python CLI against the SonarQube Server Web API. Every command prints JSON;
summarise it for the user (tables for lists, the failing conditions first for gates).

**Read-only.** The CLI has no write commands. Never mark issues or hotspots, change statuses,
or trigger a scan on the server, even if asked to "fix it in Sonar" — fix the code instead and
say that a new analysis (CI) will update SonarQube.

## Setup

- `uv` installed; the script declares its deps inline (PEP 723). Behind Zscaler, set
  `UV_SYSTEM_CERTS=1` so uv can download them. HTTPS calls use the OS trust store.
- `SONAR_HOST_URL` — e.g. `https://sonarqube.schwarz`
- `SONAR_TOKEN` — a **user** token (`squ_…`), My Account → Security.
- Optional `SONAR_PROJECT_KEY`. Otherwise the key comes from `--project`, then from
  `sonar.projectKey` in `sonar-project.properties` or `[tool.sonar]` in `pyproject.toml`
  (cwd up to the git root).

Run `whoami` first when anything fails; a 401 means a bad token, a 403 missing Browse permission.

## CLI

```bash
uv run --script ~/.agents/skills/sonarqube/scripts/sonar.py <command> [options]
```

| Command | Purpose |
|---|---|
| `whoami` | Server version, token validity, login. |
| `projects -q <text>` | Find project keys by name/key substring. |
| `branches` / `prs` | Analysed branches / pull requests with gate status. |
| `quality-gate` | Gate status; `failing` = conditions breaking it. |
| `issues` | Issues with `file`, `line`, `rule`, `impacts`; `by_severity` / `by_quality` totals. Filters: `--new-code`, `--severity BLOCKER,HIGH`, `--quality SECURITY`, `--status`, `--file <path>` (repeatable), `--limit`. |
| `hotspots` | Security hotspots (`--status TO_REVIEW` default), highest probability first. |
| `measures` | Coverage, duplication, issue counts, ratings (A–E). `--metrics` overrides the set. |
| `rule <key>` | Rule rationale and fix guidance as plain text. |

`quality-gate`, `issues`, `hotspots` and `measures` take `-p <project>` plus either
`--branch <name>` or `--pr <key>` (default: main branch). For Azure DevOps repos the PR key is
the ADO pull request id.

## Finding the project

If the repo has no key configured, run `projects -q <repo name>`. One match: use it. Several:
ask the user once which one. None: say so and stop — do not guess keys.

## Fixing issues in the current repo

1. `quality-gate --pr <id>` (or `--branch`) — what blocks.
2. `issues --pr <id> --new-code` — the findings in scope; `--file` to narrow.
3. `rule <key>` for each distinct rule before changing code.
4. Fix in the code, run the project's tests. Report which issue keys the change addresses;
   they close on the next analysis.
