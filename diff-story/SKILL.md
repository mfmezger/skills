---
name: diff-story
description: "Tell the story of a git diff as an annotated, chapter-ordered HTML page. Use when the user wants a branch, PR or diff explained hunk by hunk."
author: Marc Fabian Mezger <57255687+mfmezger@users.noreply.github.com>
---

# Diff story

One model call turns `BASE...HEAD` into a **story**: chapters in reading order, each with up to three sentences on *why*, and a note of at most 15 words next to every hunk that carries a decision or a risk. Test hunks hang, collapsed, under the chapter they verify; every other hunk lands in a collapsed "Mechanical" chapter, so nothing is hidden. The model only references hunk ids, so it cannot cite lines that do not exist.

Without the model, the script also marks code moved between hunks, warns about removed module-level Python names that HEAD still imports, highlights Python (from the real file versions), highlights the changed part of each line, folds long runs, switches between unified and side-by-side diffs (button or `s`) and keeps per-chapter "reviewed" ticks in the browser (`j`/`k`, `n` for the next unreviewed chapter).

Script: `scripts/diff_story.py`, relative to this skill's directory (stdlib only, run with `uv run` or `python3`).

## Steps

1. **Pick the range.** Run from inside the repository on the branch to explain. The base is the PR's target, usually `origin/main`; fetch first (`git fetch origin`). Done when `git diff --stat <base>...HEAD` shows only this branch's changes.
2. **Point it at a model.** It calls an Anthropic-compatible Messages API: `ANTHROPIC_BASE_URL` (default `https://api.anthropic.com`) and `ANTHROPIC_API_KEY`. A LiteLLM proxy works by setting the base URL to it. Default model `claude-opus-5-5`; `--model` and `--effort low|medium|high` override.
3. **Run it.**
   ```bash
   uv run <this skill's directory>/scripts/diff_story.py origin/main --output /tmp/story.html
   ```
   It prints the HTML path. Done when the file exists and its header shows the expected range, file and hunk counts.
4. **Show it.** Hand the user the HTML file, and summarise the title, the chapter list and the checks in a few lines. Do not paste the hunks.

## Limits

- Diffs above 600,000 characters are refused; pick a closer base or split the branch.
- The model sees only the diff and the commit messages, not the rest of the repository; its notes say what changed and why, not whether callers elsewhere still work.
- The diff goes to the configured endpoint; respect the repository's data rules.
