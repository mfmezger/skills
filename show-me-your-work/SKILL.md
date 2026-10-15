---
name: show-me-your-work
description: "Keep a reviewable decision trail (Markdown, one entry per decision: what, why, evidence, result) and end with a cross-model review of it. Use for long-running, autonomous or multi-phase work, overnight runs, or work the user reviews after stepping away."
source: https://github.com/cursor/plugins/blob/main/pstack/skills/show-me-your-work/SKILL.md
---

# Show me your work

Keep one canonical decision log per task.

## Format

One Markdown file per task, one entry per decision. The heading carries the UTC timestamp and the phase; four one-line fields follow; an optional fenced `text` block holds multi-line evidence (a short error, a test summary).

- **Decision**: what was chosen or done.
- **Why**: the reason in plain words.
- **Evidence**: a pointer that proves it: commit SHA, PR id, `file:line`, artifact or log path, command. Never a paragraph.
- **Result**: outcome or predicate state: `tests green`, `reverted`, `GO`, `REWORK`, `INCONCLUSIVE`, `open`.

````markdown
# Decision log: migrate-client

## 2026-05-24T11:15:00Z · migrate

- **Decision:** moved the client to async without changing responses
- **Why:** keep the change small and behavior identical
- **Evidence:** commit 7c21e0a
- **Result:** tests green, cassettes unchanged

## 2026-05-24T12:30:00Z · migrate

- **Decision:** threw out a worker's diff because its tests were skipped
- **Why:** checked the real pytest output instead of its summary
- **Evidence:** worktree reset
- **Result:** reverted, brief tightened

```text
SKIPPED tests/test_client.py::test_retry (no network)
41 passed, 1 skipped
```
````

## Logging an entry

Use the helper: `scripts/log.sh <logfile.md> <phase> <decision> <why> <evidence> <result> [details]` (path relative to this skill's folder). It writes the title on first use, stamps the timestamp, collapses newlines in the four fields, and fences the optional details block (switching to `~~~~` if the details contain a backtick fence).

Write entries the way you'd tell a teammate what you did. Log decision points and checkpoints, not every action: a fork chosen, a unit completed with its verification result, a pivot or revert with its trigger, a blocker, a gate fixed, a subagent's result accepted or rejected. For loop runs, one entry per iteration. Keep details short; link long output by path instead of pasting it.

A run is one agent session. When a run appends to a log that already has entries, its first entry has phase `start`, names the timestamp range of earlier entries it did not write, and its evidence names this session. Before appending in a later turn, read the last entries to see whether another run wrote since. Use phase `start` for nothing else.

## Where it lives

Default: `.audit/<task-slug>.md` in the worktree, gitignored (add `.audit/` to `.git/info/exclude` if the repo's `.gitignore` lacks it). It is a working artifact. Commit it only when the user asks or a reviewer needs the trail to trust the result. Never put customer or product data in it.

## Rules

- Append-only. A wrong call gets a new entry that supersedes it and names the timestamp of the entry it replaces. Never edit or delete history.
- Prefer evidence produced by committed scripts over hand-made one-offs.

## Close-out

Both steps run before handing back.

1. **Self-audit.** Walk this run's entries against what you actually did in this session. Every entry maps to a real decision or action; every evidence pointer resolves (`git show <sha>`, the file exists, the command reproduces). A fork, pivot or abandoned approach that shaped the work but is not logged is a gap: add it. Correct the log, not the story: supersede wrong entries with new ones, never edit them.
2. **Cross-model review.** Spawn a fresh subagent on a different model family from the one that did the work (`list_subagent_models`; e.g. Gemini when the work ran on Claude). Give it the log path, the branch and base, and the task's done-criterion. Do not let it read other sessions under `~/.dsh/sessions`. It does not redo the work; it flags:
   - decisions with weak or absent evidence,
   - verification claimed but not reproducible from the evidence,
   - choices that look risky in hindsight (premature, scope-creeping, papering over a symptom),
   - gaps the user would miss on a casual skim.

The final reply ends with an **Attention** section: first line `reviewed by <provider/model>`, then each flag pointing at specific entries by timestamp. "No flags" is a valid value; the model name is not optional.

## Reading the trail

Open the file in any Markdown preview (VS Code, the DSH GUI, GitHub, ADO). `grep '^## ' .audit/<task>.md` gives the timeline at a glance. Whole entries can be pasted into a PR comment as they are. Other skills that need an audit trail point here and do not restate the format.
