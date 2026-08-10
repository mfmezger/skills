---
name: ado-pr-review
description: "Review Azure DevOps Pull Requests — list open/mine/assigned PRs in a project, summarize a specific PR (metadata, reviewers, files, comment threads), pull the unified diff for an AI code review, check CI/build statuses and branch policies, and post review comments (top-level or inline) or cast a vote (approve / approve-with-suggestions / wait-for-author / reject). Use when the user asks to 'review PR <id>', 'show open PRs in <project>', or 'what's blocking PR <id>' against Azure DevOps."
author: Marc Fabian Mezger <57255687+mfmezger@users.noreply.github.com>
---

# Azure DevOps — Pull Request Review

This skill drives a Python CLI for inspecting and reviewing Azure DevOps
PRs. Read steps are non-destructive; write steps (`comment`, `inline`,
`vote`) require explicit user confirmation.

## Prerequisites

- `uv` installed (PEP 723 inline metadata).
- **Auth:** `AZURE_DEVOPS_PAT` env var with **Code (Read)** for read
  commands and **Code (Read & Write)** for `comment`/`inline`/`vote`.
  Create at `https://dev.azure.com/<org>/_usersSettings/tokens`.
- `AZURE_DEVOPS_ORG` (user default: `schwarzit-chicago`); override with `--org`.

Script: `scripts/pr_review.py` (relative to this skill's directory)

## Commands

| Command   | Purpose | Side-effects |
|-----------|---------|--------------|
| `list`    | List active PRs. `--scope` = `all-active` (default) / `mine` / `assigned-to-me`. `--repo` optional. | None |
| `summary` | Metadata, reviewers, file list, comment threads for a PR. | None |
| `diff`    | Per-file unified diff (`--max-files`, `--context`, `--path` repeatable, `--max-file-bytes`, `--include-lockfiles`). Binary files + lockfiles are skipped with a reason. | None |
| `ci`      | Status checks + policy evaluations. | None |
| `comment` | Post a top-level comment thread. | Writes |
| `inline`  | Post an inline comment on a file/line. | Writes |
| `vote`    | Approve / approve-with-suggestions / wait-for-author / reject / reset. | Writes |

`--repo` is optional everywhere; if omitted, the script resolves it by
searching the project's repos for the given PR id.

## Workflows

### 1. "Show me open PRs in project Foo (or just mine)"

```bash
uv run scripts/pr_review.py list -p Foo                       # all active
uv run scripts/pr_review.py list -p Foo --scope mine          # I created
uv run scripts/pr_review.py list -p Foo --scope assigned-to-me
uv run scripts/pr_review.py list -p Foo --repo my-svc         # limit to one repo
```

Render as a table: PR id (linked to the `url` field), title, createdBy,
draft (✏️ if true), source→target, age. Group by repository when scope is
`all-active`.

### 2. "Summarize PR 42 in project Foo"

```bash
uv run scripts/pr_review.py summary -p Foo --pr-id 42
```

Present:
- Header line with title + PR id link + status + draft indicator.
- Source → target branch, author, creation date, mergeStatus.
- Reviewers table: name, required, vote (translate vote int:
  `10` ✅ approved, `5` ☑️ approved with suggestions, `0` ⏳ no vote,
  `-5` 💬 waiting for author, `-10` ❌ rejected).
- File list grouped by changeType (add / edit / delete / rename).
- Thread summary: count, plus any **active** threads (`status: 1`) with
  their file/line and last comment snippet.
- Plain-language summary of the PR description.

### 3. "Review PR 42 — give me feedback" (AI code review)

1. Run `summary` to get context (intent, scope, reviewers).
2. Run `diff -p Foo --pr-id 42`. Mind `--max-files` if the PR is large; you
   can use `--path src/` repeatedly to narrow scope.
3. Produce a **structured review** in markdown:
   - **Overall** — 2–4 sentence verdict (approve / suggestions / blockers).
   - **Blocking issues** — bullets, each with `file:line` and concrete fix.
   - **Suggestions** — non-blocking improvements.
   - **Nits** — style / typos.
   - **Tests** — explicit note on whether testing looks adequate.
4. Show the review to the user. **Do not auto-post.** Ask whether to:
   - Post the whole thing as one top-level comment (`comment`), or
   - Post each finding inline (`inline` per file/line), or
   - Just keep it as chat.
5. If the user says approve / reject, cast a `vote` only after confirmation.

### 4. "What's blocking PR 42 from merging?"

```bash
uv run scripts/pr_review.py ci -p Foo --pr-id 42
uv run scripts/pr_review.py summary -p Foo --pr-id 42
```

Cross-reference:
- Any policy evaluation with `status != "approved"` and `isBlocking: true`
  is a blocker — call it out by name.
- Any required reviewer with vote ≤ 0 is a blocker.
- `mergeStatus` of `conflicts` means merge conflicts.
- Any failed `statuses` entry (e.g. failed build) is a blocker.

### 5. Posting feedback

```bash
# Top-level comment thread
uv run scripts/pr_review.py comment -p Foo --pr-id 42 --text "<markdown>"

# Inline comment anchored to a line
uv run scripts/pr_review.py inline -p Foo --pr-id 42 \
  --file src/api/handler.py --line 87 \
  --text "This branch can throw — wrap in try/except." \
  [--side right]   # right = new file (default), left = old file
```

For batched inline comments, run `inline` once per finding. Keep each
comment text crisp; no AI-attribution preambles.

### 6. Voting

```bash
uv run scripts/pr_review.py vote -p Foo --pr-id 42 --decision approve
# or: approve-with-suggestions | wait-for-author | reject | reset
```

**Never vote without explicit user confirmation** in the same turn. The
user must say "approve", "reject", etc. — do not infer it from "looks good"
in chat.

## Guardrails

- **Read commands are safe to run freely.** Write commands (`comment`,
  `inline`, `vote`) require the user to have explicitly asked.
- Never include AI attribution (`Generated by`, `Co-authored-by:`) in
  comment text.
- The `diff` command renders text diffs only. Skipped files appear in the
  output with a `"skipped"` field (e.g. `"binary extension (.png)"`,
  `"lockfile (uv.lock); pass --include-lockfiles to diff"`,
  `"too_large (...)"`, `"binary (NUL byte detected)"`). When reporting the
  review to the user, list those paths explicitly so they know what was
  not analyzed.
- For very large PRs (`fileCount > max-files`), the output sets
  `truncated: true`. Tell the user and offer `--path` filtering rather
  than silently reviewing a partial diff.
- Policy/status endpoints occasionally return different shapes across
  Azure DevOps Services vs Server versions. If a field is missing, fall
  back to "Unknown" — don't fabricate.
