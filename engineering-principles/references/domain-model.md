# Domain model

## Data shape first

Get the data shape right before writing logic. Define the core types early, trace every access pattern, and pick structures that match the dominant paths. Downstream code then becomes obvious. DRY the structure, not every line: types and models should converge, but three similar statements still beat a premature abstraction.

Scaffold first: what helps every later phase (shared types, test fixtures, lint and type-check config, CI gate) goes first. Each increment should land a coherent abstraction or deepen an existing one, not spread a new capability across callers as special-case coordination.

## Encode the domain in a structure

Encode the domain in a data structure instead of scattering it across conditionals. Choosing it at write time is cheap; recovering it later reads as a refactor and gets deferred. Reach for:

- An `Enum` plus a transition table (state machine) instead of scattered booleans, phases or lifecycle checks.
- A Pydantic model or dataclass instead of loose parameters, `dict[str, Any]` or repeated shape assumptions.
- A mapping, registry or discriminated union instead of `if/elif` chains spread across files (e.g. a dict from classification label to handler).
- A command/event model or reducer instead of ad hoc mutations.
- A module organized around one body of domain knowledge, not around a sequence (`load.py`, `validate.py`, `transform.py`, `save.py`). Execution order is not ownership.
- The right collection for the access pattern: queue, cache, index, set, tree.

Don't force an abstraction. Prefer boring code if the current shape is clear, local and unlikely to grow. Be skeptical of an abstraction that adds indirection without removing branches, duplicated rules, invalid states or lifecycle risk.

Signs you skipped this: a new feature adds one more branch to an existing `if/elif` chain, a second boolean must stay in sync with the first, or phase-named modules repeat the same domain rules.
