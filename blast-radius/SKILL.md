---
name: blast-radius
description: "Find what a change could break outside its diff and prove the one fact it is safe because of by running real code. Use for 'blast radius of X', 'what could this break', a small diff you don't trust, or as part of an independent review."
source: https://github.com/cursor/plugins/blob/main/pstack/skills/blast-radius/SKILL.md
---

# Blast radius

Find what a change breaks somewhere else, before it ships. Listing the callers is not the job; grep does that in a second. The job is the breakage grep won't show you.

## Don't trust your own writeup

A blast-radius writeup that sounds right is worthless: it reads as convincing whether or not it is true. Find the one or two facts the change's safety depends on and prove them by running code.

### Evidence ladder

Push each fact as far down this ladder as is cheap, and say where it stopped.

1. You said so. Worthless on its own.
2. You pointed at the line: a real `file:line`, or the installed library's source.
3. You walked the failure case step by step and showed it cannot be reached.
4. You ran it: a script or test that calls the real code and fails loud if you are wrong.
5. You reproduced it in the running service (local server, real request).

Rung 4 is usually one small script in a throwaway `/tmp` file that imports the same package version the app ships (`uv run python /tmp/check_x.py`) and calls the exact function you are worried about. Never put it in the worktree unless it becomes a real test.

## Steps

1. **Read the change.** The diff, the symbols it adds, changes and deletes, and what now behaves differently, including what the diff does not spell out. Pull context with `git log -p`, `git blame`, and the PR thread (`ado-pr-review`) when one exists. Done when you can state the behavior change in one sentence.
2. **Find the one fact it is safe because of.** Most risky-looking changes are safe because of a single fact ("this only drops cache entries that are already expired"). If it holds, most risky cases clear at once. Spend your time here, not on a long list of maybes.
3. **Look where grep stops.** Done when you have checked every channel below that the change touches:
   - Installed library source at the pinned version (`uv.lock`, `.venv/lib/.../site-packages`), plus any local patch or monkeypatch.
   - Timing and lifecycle: FastAPI lifespan startup/shutdown, dependency teardown (`yield` deps), background tasks, `asyncio` cancellation, event-loop vs thread-pool execution, import-time side effects.
   - Data contracts: response JSON and `response_model` fields, Pydantic validators and aliases, DB columns and migrations, serialized payloads on queues or in buckets, recorded fixtures (VCR cassettes), another service or language reading the same bytes.
   - Configuration: `Settings` fields and env vars, feature flags, defaults that differ between local, test stage and prod.
   - Code three hops downstream: consumers of the return value, not just callers of the function.
4. **Rate each risk honestly.** Give it a real likelihood and a real cost. Keep confirmed risks; list the ones you checked and cleared separately. Cite real `file:line`. A search that finds nothing is still an answer. Never invent a caller or an API.
5. **Prove the one fact.** Write the rung-4 script or test, run it, and paste the output.
6. **Wide or high-stakes change:** run steps 2–5 as two independent subagents on different model families (`list_subagent_models`, e.g. a Claude model and a Gemini model) with the same brief, then merge. Different models catch different real bugs; a risk both raise is high signal.

## Report

- **What it does.** What changed, including the non-obvious part.
- **The one fact it is safe because of.** State it, name the ladder rung reached, show the proof. If you could not prove it, write `unproven`.
- **Risks.** Each with how it breaks, `file:line`, likelihood and cost, and how to check. Paste proof for the ones that matter.
- **Cleared.** What you checked and why it is fine.
- **Before you merge.** The cheapest test or repro that catches the real bug, including the script you wrote.

Strip customer or product data before anything goes into a PR or ticket.
