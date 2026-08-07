---
name: ado-pipeline-analysis
description: "Analyze Azure DevOps pipelines for a specific project — list pipeline definitions, list recent builds with filters, inspect a build's status, fetch logs of failed steps, list commits in a build, and compute duration trends or flaky-pipeline metrics. Use when the user asks about Azure DevOps builds, pipelines, CI status, failing builds, or build logs (e.g. 'why did pipeline X fail', 'show recent builds for Foo in project Bar', 'is the deploy pipeline flaky')."
author: Marc Fabian Mezger <57255687+mfmezger@users.noreply.github.com>
---

# Azure DevOps — Pipeline Analysis

This skill runs a self-contained Python CLI against the Azure DevOps REST API
to analyze pipelines for a project. All commands emit JSON to stdout — parse
it and present the results to the user as a markdown table.

## Prerequisites

- `uv` is installed (the script uses PEP 723 inline metadata; deps install
  automatically on first run).
- **Auth:** `AZURE_DEVOPS_PAT` env var holding a Personal Access Token with
  at minimum **Build (Read)** scope. Create at
  `https://dev.azure.com/<org>/_usersSettings/tokens`.
- `AZURE_DEVOPS_ORG` env var sets the default organization. Override with
  `--org` per call. The user's default is `schwarzit-chicago`.

## Project handling

- If the user **provides a project name**, use it directly.
- If not, ask **once**. If still not provided, error out clearly — do not
  guess.

## Pipeline definition handling

- If the user gives a definition name but no ID, prefer
  `list-defs --name "<pattern>"` first, then re-run the requested command
  with `--definition-id`.
- If the user gives a pipeline ID, use it directly.

## CLI

Invoke from the skill's `scripts/` directory:

```bash
uv run ./pipelines.py <subcommand> [options]
```

Or by absolute path:

```bash
uv run /path/to/ado-pipeline-analysis/scripts/pipelines.py <subcommand> ...
```

### Subcommands

| Command          | Purpose |
|------------------|---------|
| `list-defs`      | List pipeline/build definitions. `--name` filters. |
| `list-builds`    | Recent builds. Filters: `--definition-id`, `--definition-name`, `--branch`, `--status`, `--result`, `--top`. |
| `build-status`   | Full status of a single build + the list of failed timeline records. |
| `build-changes`  | Commits associated with a build. |
| `failed-logs`    | Tail of logs for each failed step (defaults: 200 lines, max 10 steps). |
| `duration-trend` | Min/mean/median/p-stdev duration over the last N builds + recent-vs-prior delta. |
| `flaky`          | Pass/fail flip count + verdict (`flaky`/`stable`/`insufficient_data`). |

## Workflows

### 1. "Show recent builds for pipeline X in project Foo"

```bash
uv run ./pipelines.py list-builds -p Foo --definition-name "X" --top 20
```

Render as a table: Build ID (link to `https://dev.azure.com/{org}/{project}/_build/results?buildId={id}`),
definition, status, result (emoji: ✅ succeeded, ❌ failed, ⚠️ partiallySucceeded, ⛔ canceled),
source branch, requestedFor, startTime.

### 2. "Why did build 12345 fail?"

1. `build-status --build-id 12345 -p Foo` → identify failed steps in
   `failedRecords`.
2. `failed-logs --build-id 12345 -p Foo` → for each failed step, summarize
   the **last 20–40 lines of the tail** in plain language. Quote only the
   relevant error lines in a code block — do **not** dump full logs.
3. If there are obvious infra/transient signals (timeout, agent lost,
   network reset), call them out as candidates for a retry vs. real failure.

### 3. "List changes in build 12345"

```bash
uv run ./pipelines.py build-changes -p Foo --build-id 12345
```

Table: short commit (first 8 chars, link to `displayUri`), author, message.

### 4. "Is pipeline X flaky?" / "How long does it usually take?"

- For flakiness: `flaky --definition-id <id> -p Foo --top 50 [--branch main]`.
  Report verdict, fail rate, flip count, and current streak.
- For duration: `duration-trend --definition-id <id> -p Foo --top 30`.
  If `recentVsPriorPct` is > +20%, flag a regression.

## Guardrails

- **Read-only skill.** Never trigger or cancel builds.
- Do **not** dump full log content — always tail and summarize.
- For ambiguous pipeline name matches, the script returns
  `{"error": "ambiguous_definition", "matches": [...]}` with exit code 2;
  ask the user to disambiguate.
- If both `az` and `AZURE_DEVOPS_PAT` are missing, the script exits with an
  actionable message — surface it verbatim, don't paper over it.
