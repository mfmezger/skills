---
name: "understand-codebase"
description: "Investigate an unfamiliar codebase or feature area before planning work — dispatch a scout subagent to map it while you keep talking to the user, and get back a tight architecture brief plus a 'how to add X here' map."
---
## When to Use
Use at the START of any non-trivial coding task, before formulating a plan (step 1 of the dev workflow): a new feature, a change in an area you have not touched recently, a bug in unfamiliar code, or onboarding to a repo. The whole point is to run reconnaissance ASYNCHRONOUSLY: dispatch the scout, then immediately keep discussing the feature with the user — do not sit idle waiting for it. Skip it for a one-line change in a file you already understand, or when the user has already given you the exact files and context.

## Procedure
1. Decide the scope: a single feature AREA (dispatch a scout with a targeted brief) or a whole-repo mental model (consider the graphify_* knowledge-graph tools instead: graphify_build then graphify_query). For most feature work, an area scout is the right call.
2. Spin up the scout as a BACKGROUND AGENT so you keep working while it reads. Dispatch it, tell the user in the same turn that reconnaissance is running, and go straight back to discussing the feature. This is the whole point: the map is built in parallel with the conversation that decides what to build. Do not block, do not poll; the harness wakes you with the result.
3. Insist the scout works from PRIMARY SOURCES: the actual code, migrations, tests, and the repo's own docs/CLAUDE.md/readme, not its assumptions or a summary of them. Every claim in the brief should be traceable to a real path it read.
4. Have the scout WRITE its findings to a Markdown file in the repo (matching wherever the repo already keeps such notes, or a sensible default it names), not only into its chat reply. A cited artifact survives the session, can be handed to the planning step, and can be re-read by later agents. The brief should cite real paths throughout.
5. Shape the brief to demand a BRIEF, not a dump: (1) the layering/architecture of the relevant area, (2) how auth/data-flow/state work where it matters, (3) the conventions to know before writing code (commit style, PR flow, test expectations, house rules quoted briefly), (4) an ordered 'to add feature X you touch these files, in this order, copy this existing example per layer' map, and (5) anything fragile or surprising. Cap ~2 pages, read-only, no modifications.
6. Point the scout at the concrete task if you have one ('planning a feature that does Y') so the extension map is specific. If the feature is still undecided, ask for breadth and the extension-point map over deep dives.
7. When the brief returns, reconcile it with what the user told you in parallel: the brief is ground truth about the code, the user is ground truth about intent. Where they conflict, surface it. Feed the extension-point map straight into planning.
8. If the area spans multiple repos or the question is really 'how does this whole system fit together', prefer graphify: graphify_build on the root, then graphify_query / graphify_explain for concepts, graphify_path to trace how two connect.
## Pitfalls
- Do not wait idly for the scout. The entire value is that it runs while you talk to the user. Dispatch, acknowledge, keep going.
- Do not let the scout modify code — it is read-only reconnaissance. Say so in the brief.
- A scout that returns a file-by-file inventory is a failed scout. Demand the architecture and the 'how to add X' map; a wall of file names does not help you plan.
- Do not skip this and then discover mid-implementation that the abstraction you needed already exists (a recurring failure — a good codebase usually already has the createResource / apply_edit_policy / shared helper you were about to reinvent). The scout's extension-point map is what prevents that.
- The scout sees the code as it is NOW; if the user is mid-refactor or there are open PRs changing the area, tell the scout so, and treat its map as a snapshot.
- graphify tools require graphify_build to have run first — do not call graphify_query/explain/path against a graph that does not exist yet.

## Verification
1. You dispatched the scout as a background agent and continued the conversation in the same turn, rather than blocking on it.
2. The scout worked from primary sources (real code/tests/docs it read), and every claim in the brief traces to a cited path.
3. The brief was written to a Markdown file in the repo, not only into the chat reply, so it survives the session and can be handed to planning.
4. The brief includes an ordered extension-point map ('to add X, touch these files in this order') with a copy-from example per layer, not a file-by-file inventory.
5. You reconciled the brief against the user's stated intent and surfaced any conflict before planning.
6. The plan you formulate next reuses existing abstractions the scout found, instead of reinventing them.