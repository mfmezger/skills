# Root causes

## Fix the fault, not the symptom

The symptom is where a wrong state became visible. The root cause is the first place the system did something it should not do, or failed to handle a state it should handle. A symptom fix hides the evidence, leaves the fault free to surface elsewhere, and adds a workaround for a bug nobody named.

- Reproduce first.
- Ask "why" at each step until the answer is a wrong decision in the code, not a consequence of an earlier one.
- When stuck, instrument. Read the actual traceback, log line and state (debugger, `logging`, a printed repr). Do not guess.
- Is the triggering state legitimate? If the system may be in that state, the code that broke on it is the root cause and handling it there is the fix. If the state should never exist, a check where it broke hides the bug; find what produced it. Guards, retries, `except Exception: pass`, clamped values and `or default` fallbacks are the usual ways to hide a bug.
- Fails only after a restart or redeploy: suspect persisted state first (caches, files in a bucket, DB rows, lock files, env/config drift between stages).
- Fix the pattern, not just the instance: find every place with the same fault.
- A workaround that needs a paragraph-long comment means the code is wrong.
- If the deciding fact took a deep dig, propose the cheap, always-on signal (a log field, a metric, a validator error) that would have shown it at first look.

## Attack the premise

When two or more fixes that share one premise have failed the same gate, suspect the premise, not the fixes. Each failed fix is evidence against the belief it assumed.

1. **Write the premise down**: the one sentence every failed fix assumed.
2. **Test it before the next fix.** Find an observation that would come out differently if the premise were false, and make it rerunnable (a script, a test). Look at how the failures are distributed, not only at how large they are.
3. **Follow the evidence.** If it contradicts the premise, look for what the failures share that the premise did not predict. If it confirms it, ask the next "why": the earlier fixes may have treated a consequence.
4. **Remove the condition instead of compensating for it.** A mechanism that cleans up after the cause leaves it in place and adds work on every run.

Do not start the next fix before the premise is written down and tested.
