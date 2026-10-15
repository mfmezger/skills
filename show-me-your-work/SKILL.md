---
name: show-me-your-work
description: "Keep a reviewable decision trail (TSV, one row per decision: what, why, evidence, result) and end with a cross-model review of it. Use for long-running, autonomous or multi-phase work, overnight runs, or work the user reviews after stepping away."
source: https://github.com/cursor/plugins/blob/main/pstack/skills/show-me-your-work/SKILL.md
---

# Show me your work

Keep one canonical decision log per task.

## Format

One TSV file, one row per decision. Cells stay single-line. Evidence is a pointer, not prose. Columns (header in `references/decision-log-template.tsv`):

- **ts**: ISO8601 UTC timestamp.
- **phase**: phase or workstream.
- **decision**: what was chosen or done, one line.
- **why**: the reason in plain words.
- **evidence**: something that proves it: commit SHA, PR id, `file:line`, artifact or log path, command. Never a paragraph.
- **result**: outcome or predicate state: `tests green`, `reverted`, `GO`, `REWORK`, `INCONCLUSIVE`, `open`.

```
ts	phase	decision	why	evidence	result
2026-05-24T09:02:00Z	frame	counted the call sites first, 41 across 9 modules	wanted the size before starting a long run	rg output in /tmp/callsites.txt	5 open questions found
2026-05-24T11:15:00Z	migrate	moved the client to async without changing responses	keep the change small and behavior identical	commit 7c21e0a	tests green, cassettes unchanged
2026-05-24T12:30:00Z	migrate	threw out a worker's diff because its tests were skipped	checked the real pytest output instead of its summary	worktree reset	reverted, brief tightened
```

## Logging a row

Use the helper: `scripts/log.sh <logfile> <phase> <decision> <why> <evidence> <result>` (path relative to this skill's folder). It stamps `ts`, writes the header on first use, strips tabs/newlines, and quotes cells starting with `=`, `+`, `-`, `@` so spreadsheets don't execute them.

Write rows the way you'd tell a teammate what you did. Log decision points and checkpoints, not every action: a fork chosen, a unit completed with its verification result, a pivot or revert with its trigger, a blocker, a gate fixed, a subagent's result accepted or rejected. For loop runs, one row per iteration.

A run is one agent session. When a run appends to a log that already has rows, its first row has phase `start`, names the `ts` range of earlier rows it did not write, and its evidence names this session. Before appending in a later turn, read the last rows to see whether another run wrote since. Use phase `start` for nothing else.

## Where it lives

Default: `.audit/<task-slug>.tsv` in the worktree, gitignored (add `.audit/` to `.git/info/exclude` if the repo's `.gitignore` lacks it). It is a working artifact. Commit it only when the user asks or a reviewer needs the trail to trust the result. Never put customer or product data in it.

## Rules

- Append-only. A wrong call gets a new row that supersedes it. Never edit or delete history.
- Prefer evidence produced by committed scripts over hand-made one-offs.

## Close-out

Both steps run before handing back.

1. **Self-audit.** Walk this run's rows against what you actually did in this session. Every row maps to a real decision or action; every evidence pointer resolves (`git show <sha>`, the file exists, the command reproduces). A fork, pivot or abandoned approach that shaped the work but is not logged is a gap: add it. Correct the log, not the story: supersede wrong rows with new rows, never edit them.
2. **Cross-model review.** Spawn a fresh subagent on a different model family from the one that did the work (`list_subagent_models`; e.g. Gemini when the work ran on Claude). Give it the log path, the branch and base, and the task's done-criterion. Do not let it read other sessions under `~/.dsh/sessions`. It does not redo the work; it flags:
   - decisions with weak or absent evidence,
   - verification claimed but not reproducible from the evidence,
   - choices that look risky in hindsight (premature, scope-creeping, papering over a symptom),
   - gaps the user would miss on a casual skim.

The final reply ends with an **Attention** section: first line `reviewed by <provider/model>`, then each flag pointing at specific rows. "No flags" is a valid value; the model name is not optional.

## Reading the trail

`column -s$'\t' -t .audit/<task>.tsv | less -S` renders it in a terminal. Other skills that need an audit trail point here and do not restate the columns.
