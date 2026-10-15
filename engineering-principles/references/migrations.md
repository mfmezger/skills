# Migrations

## Internal APIs: migrate callers, then delete

When a new internal API is the right design, migrate every caller and remove the old API in the same change or PR stack instead of keeping a compatibility layer.

- Don't keep a legacy path only because internal callers still exist. Inventory them (`rg`), migrate, delete.
- Temporary adapters are exceptional and time-boxed, not architecture.
- Update tests to assert the new contract; delete tests that only protect pre-refactor internals.

Keeping both creates dual-path complexity, slows cleanup and makes the codebase append-only.

## External consumers: version instead

This does not apply when someone outside the repo depends on the contract: a deployed frontend, another team's service, a public or partner API, a persisted data format, a bucket layout another job reads. There, use an explicit versioning or deprecation plan (new endpoint or field next to the old one, consumers migrated, old path removed on a date). Check `capy` for the company's API versioning rules.

## Planned rewrites: optimize for the end state

For planned rewrites with explicit phase boundaries, optimize for the verified end state rather than keeping every intermediate step perfectly stable. Smooth intermediate states often need throwaway compatibility code that becomes long-lived debt.

- Declare up front where temporary breakage is acceptable (e.g. inside a PR stack before it lands), and keep it scoped and reversible.
- Keep high-signal checks green for the areas actively touched while migrating.
- Require the full gate (type-check, lint, tests, and a real run) at plan completion, and on every commit that lands on the target branch. Nothing broken ever reaches a branch that auto-deploys.
