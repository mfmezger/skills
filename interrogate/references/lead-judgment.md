# Lead judgment

The reviewers have produced findings. Don't aggregate: filter, contextualize, decide.

## Why this step matters

Adversarial reviewers are useful because they are aggressive, and aggression without context is noise. They saw a diff and one intent paragraph. They don't know what was already tried and rejected, the constraints outside the code, which parts are scaffolding, what the grilling decided, or what the next PR will address. You have that context. Use it.

## Filters

- **Nitpick gravity.** Reviewers fill their review. If a reviewer's findings are all nits and style, the code is probably fine. Say so.
- **Hypothetical vs. actual.** "What if this is `None`?" is a finding only if a caller can actually pass `None`. Trace the call site. If upstream validation or the types prevent it, dismiss it.
- **Premature abstraction.** Suggestions to extract, add interfaces or generalize: does this code need to change in a second way? If not, dismiss.
- **"I would have done it differently."** The most common false positive. Without a concrete problem with the current approach, dismiss and say why.
- **Missing context.** Findings about code the change didn't touch, patterns consistent with the rest of the codebase, or advice that conflicts with known constraints or grilling decisions. Dismiss gracefully.
- **Unverified claims.** A reviewer's "the gate fails" or "the test is vacuous" is evidence only with the command and output. Rerun it if it decides the verdict.

## When reviewers are right

Don't dismiss findings because they are uncomfortable. Signs a finding deserves attention:

- Both model families raised it independently.
- It names a concrete execution path, not a hypothetical.
- It reveals a gap in your own mental model of the code.
- You read it and think "...yeah, actually".

Be especially careful dismissing security, data-handling and correctness findings, even from one reviewer.

## Calibration

The verdict should be useful, not comprehensive: the user reads Act on, fixes it, and ships with confidence. More than five Act on items usually means weak filtering. Showing what you dismissed and why lets the user override you; keep that section honest.
