---
name: engineering-principles
description: "Engineering principles for Python services: root causes, verification, boundaries and types, domain model, idempotency, shared state, migrations. Use when choosing data shapes, debugging after failed fixes, writing tests, designing retries, CronJobs or migrations, or as a review lens."
source: https://github.com/cursor/plugins/tree/main/pstack/skills
---

# Engineering principles

Seven principles, consolidated from pstack's `principle-*` skills. Each line says when it applies and the rule. Read the linked file in full before you apply a principle, and name the principle and the choice it changed when you report the decision.

| Principle | Applies when | Rule |
|---|---|---|
| [Root causes](references/root-causes.md) | Debugging; two fixes on one premise have failed | Fix the first place the system went wrong, not where it surfaced. After two failed fixes, write the shared premise down and test it before the third. |
| [Verification](references/verification.md) | Before declaring done; writing, changing or keeping a test | Check the real artifact, not a proxy or self-report. A test must fail when the behavior breaks and survive when only internals change. |
| [Boundaries and types](references/boundaries-and-types.md) | Wiring validation, config, external APIs, LLM output; designing a signature | Parse external data into typed models once at the boundary, trust it inside. Make illegal states unrepresentable; no `cast` or `Any` to silence the checker. |
| [Domain model](references/domain-model.md) | Before writing logic; code that branches a lot or repeats a shape assumption | Name the data shape first. Encode the domain in a structure (enum, state machine, registry, typed model) instead of scattered conditionals. |
| [Idempotency](references/idempotency.md) | Commands, CronJobs, consumers, retries, migrations | Derive each step from observed state, so a rerun or a crash at any point converges to the same end state. |
| [Shared state](references/shared-state.md) | Concurrent actors (asyncio tasks, workers, subagents, worktrees) might write the same thing | Eliminate the shared write target first; serialize structurally only for a real invariant. |
| [Migrations](references/migrations.md) | Replacing an internal API; planned rewrites with phases | Migrate internal callers and delete the old path in the same wave. External consumers get explicit versioning instead. |

Measured numbers (speedups, latencies, eval scores) are vetted with the `benchmark-checklist` skill. Simplicity and diff size are covered by `karpathy-guidelines`.
