---
name: "understand-codebase"
description: "Investigate an unfamiliar codebase or feature area before planning work — dispatch a scout subagent to map it while you keep talking to the user, and get back a tight architecture brief plus a 'how to add X here' map."
---
## When to Use
Use at the START of any non-trivial coding task, before formulating a plan (step 1 of the dev workflow): a new feature, a change in an area you have not touched recently, a bug in unfamiliar code, or onboarding to a repo. The whole point is to run reconnaissance ASYNCHRONOUSLY: dispatch the scout, then immediately keep discussing the feature with the user — do not sit idle waiting for it. Skip it for a one-line change in a file you already understand, or when the user has already given you the exact files and context.

## Procedure
1. Decide the scope: a single feature AREA (dispatch a scout with a targeted brief) or a whole-repo mental model (consider the graphify_* knowledge-graph tools instead — graphify_build then graphify_query). For most feature work, an area scout is the right call.
2. Dispatch a scout subagent IMMEDIATELY and in the same turn tell the user you have done so, then continue the conversation about the feature. This is the key move: reconnaissance runs in the background while you and the user refine WHAT to build. Do not block on it, do not poll it — the harness wakes you with the result.
3. Write the scout brief to demand a BRIEF, not a dump. Ask for: (1) the layering/architecture of the relevant area, (2) how auth/data-flow/state work where it matters, (3) the conventions worth knowing before writing code (commit style, PR flow, test expectations, any CLAUDE.md / docs / readme house rules — quoted briefly), (4) an ordered 'to add feature X you touch these files, in this order, copy this existing example per layer' map, and (5) anything fragile or surprising. Cap it at ~2 pages, cite real paths, no modifications.
4. Point the scout at the concrete task if you have one ('planning a feature that does Y') so the 'how to add X' map is specific, not generic. If the feature is still undecided, ask for breadth and the extension-point map over deep dives.
5. When the brief returns, reconcile it with what the user told you in parallel: the brief is ground truth about the code, the user is ground truth about intent. Where they conflict, surface it. Feed the brief's extension-point map straight into the planning step.
6. If the area spans multiple repos or the question is really 'how does this whole system fit together', prefer graphify: graphify_build on the root, then graphify_query / graphify_explain for specific concepts, and graphify_path to trace how two concepts connect.

## Pitfalls
- Do not wait idly for the scout. The entire value is that it runs while you talk to the user. Dispatch, acknowledge, keep going.
- Do not let the scout modify code — it is read-only reconnaissance. Say so in the brief.
- A scout that returns a file-by-file inventory is a failed scout. Demand the architecture and the 'how to add X' map; a wall of file names does not help you plan.
- Do not skip this and then discover mid-implementation that the abstraction you needed already exists (a recurring failure — a good codebase usually already has the createResource / apply_edit_policy / shared helper you were about to reinvent). The scout's extension-point map is what prevents that.
- The scout sees the code as it is NOW; if the user is mid-refactor or there are open PRs changing the area, tell the scout so, and treat its map as a snapshot.
- graphify tools require graphify_build to have run first — do not call graphify_query/explain/path against a graph that does not exist yet.

## Verification
1. You dispatched the scout and continued the conversation in the same turn, rather than blocking on it.
2. The returned brief cites real paths, states the conventions/house-rules, and includes an ordered extension-point map ('to add X, touch these files in this order').
3. You reconciled the brief against the user's stated intent and surfaced any conflict before planning.
4. The plan you formulate next reuses existing abstractions the scout found, instead of reinventing them.