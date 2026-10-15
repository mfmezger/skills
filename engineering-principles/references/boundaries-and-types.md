# Boundaries and types

## Boundary discipline

Validation, narrowing and error handling sit at system boundaries. Inside, trust the types. Business logic lives in pure functions; the framework shell is thin.

- **Boundaries**: HTTP requests and responses, env and config (`Settings`), external APIs, LLM output, files and buckets, queue messages, DB rows, CLI args. Parse raw data into Pydantic models there, return clear errors, handle defensively.
- **Inside**: typed data, propagate errors, no re-validation, no `if x is None` deep in a call chain the boundary already guaranteed.
- **Across the boundary**: expose domain concepts, not the transport's representation. Don't leak ORM rows, raw `dict`s from an SDK, or `httpx.Response` through your public functions.
- Configuration is parsed once into the pydantic `Settings` class, not read via `os.environ` or kept as module-level constants scattered in code.
- Pure-function candidates: parsing (bytes → typed model), prompt construction (typed state → string), scoring (state → result). The router or CLI just calls them.

Tests: "Is this data crossing a boundary right now?" If not, validation is redundant. "Can this be a pure function the shell calls?" If yes, extract it.

## Type discipline (Python)

Make the type checker (ty, pyright, mypy) reject impossible states, mixed-up primitives and unhandled variants.

- **Illegal states unrepresentable.** Model variants as a discriminated union, not a bag of optional fields. `completed: bool; completed_at: datetime | None` admits `completed=True` with no date. Derive the bool from `completed_at`, or use `Open | Done(at: datetime)` with a `Literal` discriminator (`Field(discriminator="kind")`). If you need a comment explaining which field combinations are valid, split it into a union.
- **Constructions, not restrictions.** Build the type from the values you want instead of carving them out with checks (a non-empty list as `head` + `rest`, a range as `start` + `duration`), or enforce it once with a validator.
- **Distinguish semantic primitives.** `UserId` and `OrderId` are both `str` but must not be interchangeable: `NewType` or a constrained Pydantic type. Validate once at creation.
- **External data is untyped until parsed**: JSON, LLM output (use structured output plus a Pydantic model, never `json.loads` into a dict that flows inward), env vars, DB rows, queue payloads.
- **Don't lie to the checker.** `cast()`, `# type: ignore`, `Any`, `assert x is not None` to appease it are latent runtime crashes. Prove the fact (validate, narrow, refine the model) at the boundary.
- **Exhaustive matching.** `match` on an enum or union ends with `case _: assert_never(x)` (`typing.assert_never`), so adding a variant fails type-checking where a case is missing.
- **Derive from authoritative schemas.** When an OpenAPI spec, DB migration, or upstream model owns a shape, derive from it instead of hand-rolling a parallel type.
- **Strengthen only where partiality appears.** A runtime assertion or "should never happen" raise marks a type that is too weak; push that check into the type, then stop. Don't model data more precisely than its use sites need.
