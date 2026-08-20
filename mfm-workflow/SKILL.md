---
name: "mfm-workflow"
description: "Matt's end-to-end coding workflow: how the agent and user work together on a task from problem to merged PR. Invoke at the start of any coding task. Chains understand-codebase, capy, grill-me, loop, independent review, commit, push, ado-pr-generate, and ado-pipeline-analysis, scaling ceremony to the size of the change."
---
## When to Use
Invoke at the START of essentially any coding task in Matt's projects — 'follow mfm-workflow', 'let's build X', or just when a coding task begins. It defines HOW we work together across nine steps: Investigate → Plan → Grill → Loop → Review → Commit → Push → Open PR → Debug pipeline. It is ADAPTIVE: run the full flow for a feature; collapse the early steps for a small fix, but NEVER skip Review, Commit, and the PR. It is the orchestration layer — each step delegates to a focused skill; this skill's job is to run them in order, scale them to the change, and keep the user in the loop at the decision points.

## Procedure
1. SIZE THE CHANGE FIRST. Trivial (typo, one-liner, obvious fix in known code) → collapse to Loop → Review → Commit → Push → PR. Feature or anything touching unfamiliar code / contracts / data / auth → run all nine steps. State which mode you have chosen and why, in one line, before starting.
2. STEP 1 — Investigate problem. Use the `understand-codebase` skill: dispatch a scout subagent to map the area, and IMMEDIATELY keep talking to the user about the feature while it runs. Do not block. For a whole-system question, use graphify instead. Skip only for a trivial change in code you already know.
3. STEP 2 — Formulate plan. Use the `capy` skill (company standards / conventions / approved-way questions) to ground the plan in house rules BEFORE inferring conventions from local code. Produce a concrete plan: what changes, which files (from the scout's extension-point map), what the tests will assert, and the rollback/PR granularity (one PR or a stack).
4. STEP 3 — Grill me. Use the `grill-me` / `grilling` skill: interview the user one question at a time, ALWAYS offering your recommended answer, resolving the plan's open decisions in dependency order. Answer from the codebase whatever the codebase can answer instead of asking. Do not proceed to Loop until the plan is shared and the unknowns are closed.
5. STEP 4 — Loop. Implement in the discover → change → verify cycle. Write or run a failing test first where it makes sense (red-before-green), reuse the abstractions the scout found rather than reinventing them, and keep the gate (type-check / lint / tests) green as you go. This is the one step with no sub-skill — it is just disciplined implementation.
6. STEP 5 — Review. Dispatch a FRESH, independent reviewer subagent with no implementation context (the pattern from `parallel-agent-fanout-with-independent-review`, judged against `thermo-nuclear-code-quality-review`). It reproduces the bug/fix itself, proves the tests are non-vacuous, runs the gate, and returns GO or REWORK. On REWORK, loop back to step 4 with its findings. Do NOT self-approve non-trivial work. For a genuinely trivial change, an inline self-review against the standard is acceptable.
7. STEP 6 — Commit. Use the `commit` skill: Conventional Commits, required type+scope, imperative <=72-char subject, body only if it earns its place. One focused commit per logical change.
8. STEP 7 — Push. Push the branch (git push -u origin <branch>). Never --force; use --force-with-lease if a rebase requires it.
9. STEP 8 — Open PR. Use the `ado-pr-generate` skill against Azure DevOps (pass the org explicitly — confirm it from the git remote; verify the PAT by probing for a 200, not by trusting the env var name). Active not draft unless asked. Put long evidence in a PR comment (ADO caps descriptions at 4000 chars).
10. STEP 9 — Debug pipeline. After the PR opens CI, use the `ado-pipeline-analysis` skill to check the build and read failing-step logs. Reproduce failures locally (the gate must pass on the real post-merge state, not just the branch) and push fixes until green.
11. Keep the user at the decision points: which plan (step 2/3), GO/REWORK outcomes (step 5), and merge (step 8) are theirs to confirm. Do the mechanical steps autonomously; surface the judgement calls.

## Pitfalls
- Do not skip straight to coding. The most expensive mistakes in this workflow happen because Investigate (step 1) and Grill (step 3) were skipped — you reinvent an existing abstraction, or you build the wrong thing well.
- Adaptive is not an excuse to drop Review/Commit/PR. Ceremony scales DOWN for small changes but those three are the floor — a 'trivial' change that skips review is how silent regressions ship.
- Do not self-approve non-trivial work in step 5. A fresh reviewer with no implementation context catches things the author literally cannot see (a fix whose own test asserts against the wrong config; a fix that creates the next instance of the bug it fixed). Dispatch the independent reviewer.
- Do not block waiting for the step-1 scout. Dispatch it and keep grilling the user about the feature — the two run in parallel by design.
- Grill one question at a time and always recommend an answer. Batching questions is bewildering; asking what the codebase already answers wastes the user's attention.
- capy (step 2) is the FIRST stop for 'what's our standard / approved way' — consult it BEFORE inferring conventions from local code, or you will encode drift as if it were policy.
- The gate passing on your branch is not proof; step 9 requires the gate green on the real post-merge state. Bases move under branches (a merged sibling PR can break yours with zero textual conflict).
- Several referenced skills are installed via symlink and can go dangling (grilling, code-review, diagnosing-bugs have all been seen empty). If a step's skill resolves to nothing, check `readlink -f` and restore it before assuming the step is optional.
- Do not resume a completed subagent session (scout or reviewer) — it exits with no output. Spawn a fresh one with the context pasted in.

## Verification
1. Mode was declared up front (full flow vs collapsed) and matched the size of the change.
2. For non-trivial work: a scout ran in step 1, a plan was grounded in house rules (capy) and shared via grilling before any code, and a fresh independent reviewer returned GO before commit.
3. Every change is behind a Conventional Commit and an Azure DevOps PR — no direct-to-main work.
4. The gate is green on the real post-merge state, not just the branch, and any pipeline failure was read via ado-pipeline-analysis and fixed.
5. The user confirmed the plan, the GO/REWORK outcome, and the merge — the judgement calls were surfaced, the mechanical steps were done autonomously.