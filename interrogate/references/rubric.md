# Review rubric

Apply the lenses that are relevant. A simple bug fix does not need paragraphs on architecture.

## Correctness

Does the code do what the intent says?

- Edge cases: empty inputs, `None`, boundary values, unicode, timezones (naive vs aware datetimes).
- Errors: caught, propagated, or silently swallowed (bare `except`, `except Exception: pass`, a logged-and-ignored failure)?
- Async: un-awaited coroutines, blocking calls inside `async def`, cancellation leaving state half-written, shared mutable state across requests.
- Happy and sad path both work.
- Idempotency: what if this runs twice, or a previous run crashed halfway (CronJobs, retries, migrations)? "It depends on what state was left behind" means a reconciliation step is missing.
- Concurrency: if several actors can write the same file, row, key, bucket object or branch, is access serialized structurally, or only by convention?

When you suspect a bug, trace the execution path and show the call chain that triggers it.

## Root causes vs. symptoms

Is the change fixing the problem or papering over a symptom? Read beyond the changed files.

- Guard clauses or `or default` fallbacks masking a broken invariant.
- Retries hiding a broken contract.
- `cast()`, `# type: ignore`, `Any` silencing a modeling error.
- A fix in module A that belongs in module B's contract.
- A comment saying "don't do X" where a type, validator, lint or runtime check could make X impossible.

## Structural integrity

- Boundary discipline: external data (requests, env, LLM output, files, third-party APIs) validated once at the boundary with Pydantic, then trusted internally. Not re-validated or re-parsed deep inside business logic.
- Configuration lives in the pydantic `Settings` class, not as module-level constants scattered in code.
- Model-facing text (prompts, retry messages) lives where the project keeps prompts, versioned, not as an inline constant.
- Abstraction level: orchestration mixed with low-level detail?
- Coupling: new dependencies that make future changes harder?
- Bolted-on vs. integrated: had the requirement been known from the start, would the code look like this?
- Legacy dual paths: a new internal API while the old one stays alive. Without external consumers, migrate callers and delete the old path in the same change. With external consumers (deployed clients, other services), require an explicit versioning or deprecation plan.

Don't penalize simple code for lacking abstraction. Premature abstraction is worse than duplication.

## Verification

- Tests exist and assert behavior a user of the code can observe, not internals or mock call counts.
- A bug fix has a test that fails without the fix.
- Tests run against the configuration that actually ships, not a test-only setup that cannot catch the bug.
- Integration boundaries are tested along the full path (a real request through the router, a real DB migration).
- Changed external call sequences re-record only the affected fixtures (VCR cassettes), and the cassettes contain no secrets.
- Delegated or async work verifies output artifacts instead of trusting self-reports.

## Complexity budget

- Could be simpler without losing correctness or clarity.
- Abstractions with one call site; config or parameters for cases that do not exist.
- Dead code, unused imports, vestigial parameters, "just in case" paths.
- Obsolete compatibility scaffolding after a finished migration.

Simpler is better unless simpler is wrong.

## Security and data handling

For each finding, trace the input path and show it.

- User or model input reaching dangerous sinks: SQL via f-strings, `subprocess(..., shell=True)`, `eval`/`exec`, `pickle`/`yaml.load` on untrusted data, path traversal, SSRF via user-supplied URLs.
- Prompt injection: untrusted text concatenated into prompts or tool arguments without separation; model output used as a command, query or URL without validation.
- AuthN/AuthZ gaps on new endpoints or dependencies.
- Secrets in code, logs, error messages, traces, fixtures or cassettes.
- Customer or product data committed (reports, fixtures, datasets, snapshots) against the data-handling rule.
- TOCTOU in security-relevant paths.
