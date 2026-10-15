---
name: correct
description: "Find the mistakes agents keep repeating in a repo and make each one impossible: architecture first, then types, then a lint or CI check whose error names the fix, then tests, docs last."
source: https://github.com/cursor/plugins/blob/main/pstack/skills/correct/SKILL.md
disable-model-invocation: true
---

# Correct

The user keeps correcting agents in this repo for the same mistakes. Change the repo so the next agent cannot make them.

Assume every contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that passes the gate. Design the repo so a change that looks right from one file is right for the whole repo.

## 1. Find the mistake classes

Read recent commits and reverts, ADO PR review threads (`ado-pr-review`), `AGENTS.md` / `CLAUDE.md` / other agent instruction files, comments explaining workarounds, and Mnemon memory entries about this repo (`mnemon_recall`). Group the mistakes into classes. A class counts once it has happened twice. Done when every class has at least two cited occurrences.

## 2. Fix each class at the highest level that works

1. **Architecture: eliminate it.** One owner per piece of state, one supported way per task. Hide internals so the wrong import fails (`_private` modules, narrow `__all__`). Replace hand-synced lists with one source of truth (e.g. config in the pydantic `Settings` class, not module constants). Delete old ways and dead code an agent would copy.
2. **Types: make the bad state unwritable.** Pydantic models, `Literal`/enums, `NewType`, `assert_never` on exhaustive matches, checked by the repo's type checker (ty, pyright, mypy).
3. **Lint / CI check whose error names the fix.** When bad code still type-checks: a ruff rule (`banned-api`, `flake8-tidy-imports`), an import-linter contract, or a small script in pre-commit and the ADO pipeline. The error message names the file, type or function to use instead. If the pattern is already common, fail only when a change adds more.
4. **Tests: assert behavior.** Fix or delete any test that still passes when its behavior breaks, or fails when only internals change.
5. **Docs or agent rules last**, only for judgment calls. Nothing fails when an agent skips them.

Done when each class has a chosen level and a one-line reason a higher level did not work.

## 3. Fix and prove

Fix the most frequent classes now, one commit each (`commit` skill). Prove each new check fails on a real past mistake: check out or re-apply the old offending code in a throwaway branch or `/tmp` copy and show the red output. Run the same command locally and in CI. Exceptions go on the offending line with a reason, an expiry date and the user's approval (`# noqa: XXX  reason, expires 2026-12-31`).

## 4. Keep the rule table

Keep a table in the repo's agent instruction file pairing each rule with what enforces it (`architecture`, `type`, `ruff TID251`, `scripts/check_x.py`, `test_y`, `doc only`). When the user corrects you, fix the mistake and add the rule. If the rule was already there and nothing enforces it, it is a repeat: fix it at a higher level in the same change. Drop a rule once its mistake can no longer happen.

Prefer this over a Mnemon memory entry for anything a check can enforce; memory is for judgment calls and environment quirks.

## Report

Each class with its evidence, the level you picked, why a higher level did not work, and the red-then-green proof.
