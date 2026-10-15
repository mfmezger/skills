# Shared state

When concurrent actors might share mutable state, first ask whether they need the same mutable object. If not, eliminate the sharing. When sharing is real, enforce serialization structurally. Instructions and conventions are not concurrency control. Before sharing anything, ask: "what happens if another actor modifies this concurrently?" If the answer is not "nothing", isolate.

1. **Identify shared mutable state**: module-level dicts or clients mutated per request, files or bucket objects several jobs read and write, DB rows updated by several workers, branches or worktrees several agents push to, one `state.json` several tasks update.
2. **Default: eliminate the shared write target.** Do these actors need one canonical object, or are they publishing independent facts? Give each its own file, key, row, branch or worktree, and merge only at the read or reporting boundary. Two workers writing their own field into one `state.json` is still shared mutation; `indexer-state.json` and `metrics-state.json` are not. Per-request state belongs in the request scope (dependencies, `contextvars`), not in module globals.
3. **Only when one shared target is a real invariant, serialize structurally**: a single-writer task fed by an `asyncio.Queue`, sequential phases, a DB transaction with the right isolation or `SELECT ... FOR UPDATE`, optimistic concurrency (version column, ETag, compare-and-swap), a lease. Treat "we need a lock" as a design smell to check, not the default answer.

The same applies to agent work: parallel subagents get disjoint worktrees and write scopes; they never share a checkout or branch.
