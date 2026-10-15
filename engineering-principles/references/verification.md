# Verification

## Prove it works

Verify every output by checking the real thing, not a proxy, self-report or "it type-checks".

- Read the actual value: the response body from a real request, the row in the DB, the object in the bucket, the log line. Not a cached or derived representation.
- Check process liveness directly (the endpoint answers), not via derived state.
- A subagent's "done, tests green" is a claim. Check `git diff` and rerun the gate.
- When verification fails, suspect the observation method before the system.
- Script the check when you can: a deterministic script that reruns the comparison beats a one-time eyeball, and its output is an artifact a reviewer can rerun.

## Test behavior, not implementation

A test is a claim about what the code does for its users: a caller, an end user, another service. Behavior is what they can observe: return values, raised exception types they branch on, HTTP status and body, state they can read back, effects on external systems (a request sent, a row written, a message published). Implementation is what they cannot: private helpers, internal call order, intermediate data, which collaborator did the work.

Judge each test against two imagined edits:

- **Break the behavior** (wrong value, skipped effect, effect twice). If the test still passes, it proves nothing. Usual causes: an assertion looser than the contract, an expected value computed by the code under test, a restated constant or prompt string that never runs the code reading it, an assertion on data the test built itself.
- **Change the internals** with identical observable results. If the test fails, it is pinned to the implementation: it breaks on every refactor and catches no bug.

Keep tests that catch the first edit and survive the second; rewrite or delete the rest. Drive the code through its public interface (e.g. FastAPI `TestClient`/`httpx.AsyncClient` against the app, not the handler function's internals) with a concrete input, and derive the expected value from the requirement, not from a run of the code.

The contract decides, not the assertion's shape:

- The payload a mocked external service (LLM API, S3, another service) receives is behavior, because that service observes it. A call to an internal helper is implementation.
- "Never charges on an empty cart": asserting the payment client got no call is behavior. Pair it with a case where the call happens, so the test shows it can see one.
- An exact error message pins wording no caller reads; the exception type or error code callers branch on is the contract.
- A test can pin an invariant instead of a call (a key that must exist in two tables, a `Settings` field every stage defines).
- Tests must run against the configuration that ships; a test-only setup that differs from production cannot catch the production bug.
