---
name: capy
description: >-
  The first stop for "our company standards / guidelines / conventions / policy"
  questions — API & REST/OpenAPI design, language & framework rules, security,
  auth, cloud, and deployment practices. Consult BEFORE inferring conventions
  from local code or answering from the repo. Trigger on company
  standards/guidelines/conventions/policy/best-practices, "are we allowed to…",
  or "what's the approved way to…". Backed by company directives + Confluence RAG.
---

# Capy — Coding Agent Provisioning Yard Skill

This skill equips the agent to leverage the `capy` CLI companion tool to query local/remote
knowledge bases, list company development directives, and install skills.

## When to Use
**Consult capy FIRST**, before deriving any standard from the codebase. If the task
touches API design, conventions, security, auth, cloud/deployment, or approved tech,
query capy before grepping the repo — the repo may reflect one team's choices, not the
company directive.
* **Company standards & "approved way" questions**: standards, guidelines, conventions,
  policies, best practices, compliance, approved technologies — get the authoritative
  answer instead of guessing.
* **Before inferring from local code**: lint/format rules, API/REST/OpenAPI style,
  security & auth patterns, cloud/deploy practices, framework choices — gate on capy first.
* **Trigger phrases**: "our company standards/guidelines/conventions/policy",
  "are we allowed to…", "what's the approved way to…", "best practice for…".

## Core Commands

### 1. Hybrid Search
Query the company's indexed developer guidelines (offline-first via FTS5) or search Confluence RAG:
* **Local Guideline Search (Offline & Instant)**:
  ```bash
  uv run capy search "database"
  ```
* **Confluence RAG Search (Remote Fallback)**:
  ```bash
  uv run capy search "how to configure database secrets in GCP" --rag
  ```

### 2. Browse & Discover
Search finds the *most relevant few* sections (top 5 by default). To enumerate
*everything* in an area, browse instead — browse has no result cap:
* **List categories (with counts)**: `uv run capy search --list-categories`
* **List every directive in a category**: `uv run capy search --category myapi-docs`
* **List all topics (with counts)**: `uv run capy search --list-topics`
* **List the topics used within a category**: `uv run capy search --topics-in principles`
* **List directives for a topic**: `uv run capy search --topic security`
* **Nested overview (categories -> topics)**: `uv run capy search --tree`
* **Filter principles by stance**: `uv run capy search --usage DO` (or `--usage DONT`)
* **Filter by state**: `uv run capy search --state PUBLISHED`
* **Pull more search results**: `uv run capy search "api versioning" -n 15`

Rule of thumb: use **search** for "find guidance about X"; use **browse**
(`--category` / `--topic` / `--topics-in`) for "give me *all* of X".

### 3. Read a Directive by Path
Read the full content of a known directive straight to stdout (no install needed):
```bash
uv run capy get "myapi-docs/.../3-SOAP_apis.md"
```
Accepts an exact path, with/without `.md`/`.mdx`, or a unique path tail.

### 4. List Available Guidelines
Check the local/remote store for all published company technical guidelines and directives:
```bash
uv run capy skill list
```

### 5. Install a Specific Skill/Guideline
Download and extract a single development directive globally into all active
auto-detected agent skills stores (Gemini, Claude, OpenCode, Pi):
```bash
uv run capy skill install myapi
```
To install specifically for a target coding agent, use the `--agent / -a` option:
```bash
uv run capy skill install myapi --agent claude
```

### 6. Fully Provision the Environment
Register and install all corporate guidelines and helper skills globally into
all active auto-detected coding agent environments in one step:
```bash
uv run capy install
```
