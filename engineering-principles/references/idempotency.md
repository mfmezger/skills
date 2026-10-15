# Idempotency

Operations converge to the correct state regardless of how often they run or where the previous run stopped. CronJobs, queue consumers, retries, migrations, backfills and eval runs restart all the time; if partial state changes the next run's outcome, every restart becomes a debugging session.

**The idea:** derive each step from the state that exists, not from what the previous run meant to do. Read the current state, compare it to the goal, apply only the difference. A repeat then finds nothing left to do.

- Writes: upsert by a natural key instead of insert; `INSERT ... ON CONFLICT`; deterministic object keys in buckets (content hash or source id, not a timestamp).
- Files and objects: write to a temporary key or path and rename or copy into place; compare by content, not by creation order.
- External side effects (emails, tickets, PR comments, paid LLM calls): record an idempotency key or check for an existing result before acting.
- Anything a run leaves behind (a lock, a temp file, a half-written record, a claimed job) must be recognizable as stale by the next run, by evidence that holds wherever the previous run could have stopped, e.g. a lease with an expiry instead of a bare lock file.
- Batch jobs process a deterministic set and skip items whose output already exists and is valid, so a rerun resumes instead of duplicating.

**The test:**

1. What happens if this runs twice in a row?
2. What happens if the previous run crashed at every possible point?
3. Does re-execution converge to the same end state?

If any answer is "it depends on what state was left behind", add a reconciliation step.
