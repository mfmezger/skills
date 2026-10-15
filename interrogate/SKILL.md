---
name: interrogate
description: "Adversarial multi-model review of a change: two fresh reviewers on different model families, then lead judgment into Act on / Consider / Noted / Dismissed and a GO or REWORK verdict. Use for 'interrogate', 'adversarial review', 'multi-model review', 'tear this apart', or the mfm-workflow Review step."
source: https://github.com/cursor/plugins/blob/main/pstack/skills/interrogate/SKILL.md
---

# Interrogate

Two reviewers on different model families attack the same change with the same brief. The adversarial signal comes from model diversity, not personas. You are the lead reviewer: you filter, decide, and return one verdict. Never auto-apply findings.

## 1. Scope

Identify what to review: the files or diff the user points at, otherwise the branch diff against its target (`git diff origin/<target>...HEAD`). Note the worktree path, branch, target branch and the gate commands (with the versions CI pins). Done when the diff is fixed and the gate commands are known.

## 2. Intent

Write one paragraph stating what the change is meant to do, from the plan, the grilling decisions, commit messages and the PR description. Include the data-handling rule (what may be committed, what must stay local) and the specific risks the plan or grilling surfaced, phrased as questions. If the intent is unclear, ask the user before spawning.

## 3. Spawn the panel

Spawn both reviewers in one tool block, as fresh background subagents with no implementation context:

| Reviewer | Default route |
|---|---|
| A | `provider: litellm`, `model: claude-opus-5-5` |
| B | `provider: litellm`, `model: gemini-3-8-flash` |

If a route is rejected, pick another family from `list_subagent_models` and say so in the report. If only one family is available, run anyway and state that diversity is reduced.

Build both prompts from `references/reviewer-prompt.md`, identical except for the label, filled with the intent, the diff location, `references/rubric.md`, and the absolute path of the `thermo-nuclear-code-quality-review` skill as the code-quality standard. Done when both reviewers have returned (or one failed and you respawned it once; a second failure is recorded as a gap, not a pass).

## 4. Synthesize

Parse every finding. Merge findings that describe the same issue and note which reviewers raised each. Independent agreement across families is the highest signal. A lone finding is read on its merits; security and correctness findings get extra scrutiny even from one reviewer. Note explicit disagreements.

Before trusting a reviewer's claim that something passed or failed, spot-check it cheaply yourself (rerun the one command it quotes).

## 5. Lead judgment

Read `references/lead-judgment.md`. Put every merged finding in exactly one bucket with the reviewer(s) that raised it and a one-line rationale:

- **Act on**: real correctness, security, data-handling or maintainability problems given the actual goals; would block a real PR.
- **Consider**: legitimate, but unclear it outweighs the cost now. The user decides.
- **Noted**: valid but not actionable at this stage.
- **Dismissed**: wrong, nitpicky, or missing context, with the reason.

**Verdict:** `GO` when Act on is empty, otherwise `REWORK`. Done when every finding sits in a bucket and the verdict follows from Act on.

## 6. Re-review after REWORK

After the fixes, run a NEW panel (never resume an old reviewer). Give it the previous Act on list and ask it to verify each item is actually fixed, not just touched, in addition to a normal pass over the new diff. Re-review also after any rebase or conflict resolution, scoped to the resolution.

## Output

```
VERDICT: GO | REWORK

### Intent
> <paragraph from step 2>

### Panel
- Reviewer A: <provider/model>, <N findings>, gate <observed result>
- Reviewer B: <provider/model>, <N findings>, gate <observed result>

### Act on
<each: finding, file:line, raised by, why it blocks>

### Consider
<each: finding, raised by, the tradeoff>

### Noted
<brief list>

### Dismissed
<each with the reason>

### Agreement map
<where the families agreed and diverged, and what that says>
```

Keep Act on short; more than five items usually means you are not filtering hard enough. The Dismissed section is a trust mechanism: it lets the user override you.
