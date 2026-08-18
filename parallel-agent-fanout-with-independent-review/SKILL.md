---
name: parallel-agent-fanout-with-independent-review
description: "Fan out an audit's findings to parallel worker subagents (one worktree/branch/PR each), then gate every PR through a fresh reviewer that returns GO or REWORK. Covers the semantic-conflict failure mode that clean merges hide."
---
## When to Use
Use when a review/audit produced several independent findings and you want them implemented concurrently with real verification — typically 3+ fixes across one or two repos, each small enough for its own PR. Also use whenever agent-authored code will be merged: the independent-reviewer node is the highest-value part and is worth running even for a single fix. Do NOT use for one small change (a plain loop is cheaper), for exploratory work with no clear finish line per node, or when the findings are actually one entangled change — splitting coupled work into parallel PRs manufactures the conflicts this skill then has to clean up.

## Procedure
1. GRILL THE SCOPE BEFORE SPAWNING ANYTHING. Run a grilling pass (the `grilling` skill) over the findings you intend to fan out. Its rules apply literally: walk each branch of the decision tree resolving dependencies one at a time, ALWAYS give your recommended answer with the question, and if a question can be answered by reading the codebase then read the codebase instead of asking. A wrong scope decision here is multiplied by every node you spawn — this is the cheapest possible place to be rigorous.
2. Grill the codebase first, then the user. Before asking anything, verify the finding's own claims: does the component/module named in the audit still exist, are the line numbers current, is the duplication really byte-identical, do the tests couple to implementation details you are about to change? Audits go stale and are sometimes wrong. In one case a finding referenced a molecule that did not exist yet, and three 'identical' duplicates had already drifted — both discovered by grepping, not by asking.
3. Ask the questions that change the plan, in dependency order. Grill at minimum: exact scope per node (which findings, which explicitly excluded); the blast radius (how many files, how many other consumers); whether the work is behaviour-preserving or behaviour-changing, and if changing, what the user-visible diff is; what constitutes proof for this kind of change (unit tests? visual diff? live reproduction? real-Postgres migration test?); test coupling (are specs asserting on class names/selectors you plan to rename?); and rollback granularity (one PR or a stack).
4. Push back when the requested scope is wrong, with evidence. If the user asks for four findings in one PR and grepping shows two of them touch 6+ shared files, say so with the file counts and propose a sequenced stack instead. Present it as a recommendation with the numbers, not a refusal. Getting this right converts a likely REWORK into a clean GO.
5. Declare the dependency graph explicitly, as the output of the grilling. Sketch which nodes are genuinely independent and which share a foundation. Sequence known-shared work (foundation PR first, dependents fan out off it) instead of fanning out everything and discovering the edge at merge time.
6. Hunt for SEMANTIC edges before spawning, not just file overlap. Two nodes conflict if they touch the same endpoint contract, auth dependency, DB column, schema field, or test helper — even with zero overlapping lines. List these edges in each worker's brief so it knows what a sibling is changing.
7. Create one git worktree + branch per node from a freshly fetched base: git worktree add -b fix/<slug> /tmp/worktrees/<slug> origin/main. Isolation is what makes parallel execution safe.
8. Verify credentials ONCE in the parent before spawning, and pass the exact working incantation into every brief. Probe the API for a 200 rather than trusting an env var name (see pitfalls).
9. Spawn all independent workers in a single tool block so they run concurrently. Give each: the finding to read (file + anchor), the review standard it will be judged against, the scope boundary ('ONLY C1, do not fix C2/C3 — other agents own those'), the sibling-overlap warning, the answers from the grilling pass, the gate command, and the exact PR/auth setup.
10. Require red-before-green from every worker: write or run a test that fails without the fix, then passes with it. A worker claiming a fix without demonstrating the failure has not verified anything.
11. When a worker reports, verify its claims cheaply in the parent before spawning the reviewer: git log/diff --stat against origin/main, clean git status, and the branch actually pushed. Cheap and catches nonsense early.
12. Spawn a FRESH reviewer per PR with no implementation context — never resume the worker's session. Instruct it: treat every claim in the PR description as unverified marketing; reproduce the bug and the fix yourself; verify the tests are non-vacuous by reintroducing the bug and watching them fail, then restore; run the gate yourself and report real observed numbers; leave the worktree clean; do not push or vote.
13. Point the reviewer at the specific risks the grilling surfaced, phrased as questions rather than conclusions ('is the migration safe if the server TZ is not UTC?', 'does the fix's own test assert against production config?'). Also tell it plainly not to manufacture findings — 'small and correct' is a legitimate GO.
14. On REWORK, resume the ORIGINAL worker's session (subagent_resume with its sessionPath) so it keeps its context, and paste the reviewer's findings verbatim with blockers separated from follow-ups. On GO, proceed to merge.
15. Re-review after any rebase or conflict resolution: the resolution is new code nobody has reviewed. Scope the re-review to the resolution and tell it the original content already passed, so it doesn't re-litigate.
16. MERGE ONE AT A TIME AND RE-RUN THE GATE ON THE POST-MERGE RESULT. Clone or check out the real merged base and run the full suite after each merge. This is the step that catches semantic conflicts; per-branch green is not evidence.
17. Add a cross-cutting regression test that no single node could have written (e.g. asserting node A's property still holds under node B's new precondition). Prove it is load-bearing by porting it onto the unfixed base and watching it fail.
18. Close the loop on artifacts: update the source audit/report with resolution status per finding, keep the original verdicts visible rather than rewriting them, and record what remediation itself revealed.
## Pitfalls
- THE BIG ONE — semantic conflicts merge cleanly. Real case: PR A added an auth dependency to an endpoint and moved the actor to the token; PR B's test helper still POSTed to that endpoint unauthenticated with the old body field. Zero overlapping lines, zero git conflict, three tests red on main at runtime. Git's conflict detection is syntactic; the dangerous edges are semantic. Only a post-merge gate run finds these.
- Shared state is the #1 way a fan-out rots. Your shared state is the base branch, and unlike a designed state object you cannot validate it on write. Every node reads a snapshot at fan-out and writes back in an unspecified order. Treat 'which branch did this node actually read?' as a first-class question.
- Skipping the grilling pass is the most expensive mistake available, because scope errors are multiplied by every node. Batching a one-file behaviour-preserving split together with a repo-wide visual refactor produces a diff no reviewer can hold in their head, and a CSS regression that unit tests cannot see. Grill first, sequence second, spawn last.
- Do not ask the user what the codebase can answer. Grilling's own rule. Asking 'how many files use this?' when a grep answers it in two seconds wastes the user's attention and makes them arbitrate a question you should have resolved. Reserve questions for genuine judgement calls: risk appetite, scope boundaries, unverifiable production facts.
- Do not batch grilling questions into one giant form when the answers depend on each other. Sequence matters: the answer to 'which findings?' determines whether 'one PR or a stack?' is even a question. Batch only genuinely independent questions.
- Audits go stale — verify the finding before fanning it out. A finding referenced a shared molecule that did not exist yet (it had to be created), and separately, three keyframes described as identical duplicates had already drifted. Both were caught by grepping during the grilling pass, not by reading the report.
- A worker's green gate proves nothing about the combination. Every branch was green against the OLD base. Coverage percentages are especially misleading: one case had 271 tests passing with a 13-column migration that had zero coverage — reverting the entire schema change left the suite green.
- Fixes introduce new defects that the fix's own tests hide. A CORS/logging fix closed a client-side leak but introduced a worse one (the log sink dumped DSN password + API keys), and its own test configured the sink differently from production so it could never catch it. Always ask a reviewer: does this test assert against the configuration that actually ships?
- Do not resume a completed reviewer session for a re-review — it may exit immediately with no output. Spawn a fresh reviewer instead; it is also better, since it will not be anchored on its own earlier findings.
- Never symlink or reuse another worktree's virtualenv to check whether a test fails on the base branch. An editable install resolves the package back to the original worktree's source, the test passes, and you get a false negative. Build a real isolated env in the base worktree.
- Verify credentials by probing for a 200 rather than trusting the env var name. A project-named token (AZURE_DEVOPS_PAT_<ORG>) can belong to a DIFFERENT org than the one in the git remote, while the generic AZURE_DEVOPS_PAT is the one that works. Test each candidate token against each candidate org before spawning anything.
- ADO caps PR descriptions at 4000 characters — briefs that demand extensive evidence in the description will get silently truncated prose. Put decisive reproductions in a PR comment instead.
- Do not poll for subagent completion. The harness delivers results as steer messages; sleep/tail/watch loops and repeated status checks are wasted work.
- Beware fixes whose correctness depends on an unverifiable production fact (a DB server timezone, an unset deployment variable). Grill the user for it explicitly; if they do not know, do not let an agent assume the convenient value — require a runtime-derived answer or a loud refusal to proceed. Silent corruption of historical data is not an acceptable failure mode for an assumption.
- A fail-closed default must land together with the config that keeps working environments working, or the merge dark-fails an environment with nothing to page on.
- Skills can rot when installed via symlink: a dangling link makes a dependent skill silently resolve to nothing (a `grill-me` skill that only says "run a /grilling session" is useless if `grilling` is missing). If a referenced skill looks empty, check `readlink -f` on it before assuming the instruction is wrong.
## Verification
1. Every node: red-before-green demonstrated (test fails without the fix, passes with it), reported by the worker and independently reproduced by the reviewer.
2. Every fix answered the question 'does this test assert against the configuration that actually ships?' — compare the test's setup against production wiring (log sinks, env defaults, middleware order, DI overrides). This one question caught a secrets-into-logs regression that a 271-test green suite could not.
3. Every PR: a fresh reviewer with no implementation context returned an explicit GO or REWORK, having run the gate itself and reported observed numbers rather than quoting the author's.
4. Reviewer left each worktree clean (git status empty, HEAD unchanged) and started no lingering containers or processes.
5. After EACH merge: the full gate passes on a fresh clone/checkout of the real merged base — not on any branch. Non-negotiable; this is the step that catches semantic conflicts.
6. At least one cross-cutting test exists covering an interaction between two nodes, proven load-bearing by failing on the unfixed base in a properly isolated environment.
7. Fan-out width stayed at or below ~5 concurrent nodes; beyond that, coordination and rework-tracking cost grows faster than parallelism saves.
8. Redundant PRs (superseded by a sibling that merged first) are abandoned with a comment explaining what superseded them, rather than left open to conflict.
9. Worktrees removed, local branches pruned, and the source audit/report updated with per-finding resolution status.
## Reviewer Brief Template

Reuse verbatim per PR; fill the `<>` slots. The recurring instructions matter more than the
PR-specific ones — they are what turn a rubber stamp into a real gate.

```
Review <PR-ID> in repo <repo> and return GO or REWORK.

You are a fresh, independent reviewer. You did NOT write this code and have no prior
context — treat every claim in the PR description as unverified until you reproduce it.

REVIEW STANDARD — read and apply literally (tone, prioritization, approval bar):
  the `thermo-nuclear-code-quality-review` skill

THE DIFF: branch <branch>, read-only worktree at <path>.
  git -C <path> diff origin/main...HEAD

WHAT IT CLAIMS TO FIX: <finding + the audit's reproduction>

VERIFY INDEPENDENTLY:
1. Reproduce the bug on the BASE first, so you know the fix targets something real.
2. Prove the tests are non-vacuous: reintroduce the bug, watch them fail, restore.
   `git status` must be clean when you finish.
3. Does the test assert against the configuration that actually SHIPS? Check sinks,
   env defaults, middleware order, DI overrides. A test configured differently from
   production cannot catch a production bug.
4. <PR-specific risks, phrased as questions, not conclusions>
5. Scope creep: <what belongs to sibling PRs>

RUN THE GATE YOURSELF (<commands>). Report real observed numbers, not the author's.
Clean up any container you start. Do not modify source, do not push, do not vote.

DELIVERABLE:
- VERDICT: GO or REWORK as the first line.
- If REWORK: numbered, file:line, severity-ordered, blockers separated from follow-ups.
- If GO: what you reproduced, plus acceptable deferred follow-ups.
Apply the approval bar — passing tests are not approval. But do not manufacture findings:
a correct, well-scoped fix deserves a clean GO.
```

## Worked Example

One session, two repos, five findings from a prior audit:

- Fan-out: 5 workers in parallel, one worktree/branch/PR each, all from clean `origin/main`.
- Review: 5 fresh reviewers. **2 returned REWORK** — a fix that introduced a secrets-into-logs
  regression its own test hid, and a migration whose correctness depended on an unverified
  production timezone (would have shifted every historical row on a non-UTC server) plus an
  undisclosed full-table rewrite under `ACCESS EXCLUSIVE`.
- Failures all lived in combinations: two PRs merged with **zero textual conflict** and broke
  `main` at runtime; another pair produced a conflict where **both naive resolutions were wrong**
  (one crashed, the other reinstated the bug being fixed); a third pair collided on the same
  test helper.
- Net: 5 real defects fixed (auth hole, CORS credentials echo, two silent data-loss bugs, plus
  the log leak caught in review), 2 reworks, 1 PR abandoned as superseded.

The through-line: **every serious problem lived in an interaction, not in any single node.**
Each PR was green, reviewed, and correct in isolation.
