---
name: ado-pipeline-speedup
description: "Make a slow Azure DevOps CI pipeline faster, especially ODJ-template Python pipelines (uv, pre-commit, Sonar, Snyk, Docker). Use when the user wants faster CI/builds/pipelines, asks why a pipeline is slow, or wants a speedup ported to another repo."
author: Marc Fabian Mezger <57255687+mfmezger@users.noreply.github.com>
---

# Azure DevOps pipeline speedup

Measure first, change the levers that the measurement points at, and keep only what a real CI run proves. Work per repo, one PR each; run it inside `mfm-workflow` (collapsed mode is fine: Loop → Review → Commit → Push → PR → Debug pipeline).

## Steps

1. **Baseline.** Find the definition (`ado-pipeline-analysis list-defs`), get `duration-trend --top 30`, then print the step tree of one recent PR build and one main build with [`scripts/timeline.py`](scripts/timeline.py):
   `curl -s -u ":$AZURE_DEVOPS_PAT" "https://dev.azure.com/<org>/<project>/_apis/build/builds/<id>/timeline?api-version=7.1" | python3 scripts/timeline.py`
   Write down the **critical path**: which jobs run in sequence, the gap between one job's finish and the next one's start (waiting for a free hosted agent), and the top steps by seconds. Fetch step logs (`.../builds/<id>/logs/<logId>`) for the big ones: artifact size, which pre-commit hook installs slowly, test count, Sonar plugin download. Done when every step over ~10 s has a cause.
2. **Read the template.** Clone it (`git clone --depth 1 https://pat:$AZURE_DEVOPS_PAT@dev.azure.com/schwarzit/schwarzit.odj-pipeline-templates/_git/odj-deliver-templates`) and check the knobs below exist in `templates/technologies/<tech>/v2/` and `generic/v2/`. Parameters marked "Managed by ODJ" stay untouched.
3. **Apply the levers** that the baseline justifies (table below). Check each lever's precondition in the repo before using it.
4. **Verify locally** with the CI versions: YAML parses, `uvx prek@<pin> run --all-files`, ty at the pinned rev, deptry, tests. For the install-step change, install the exported `requirements.txt` into a scratch venv with the extra index URL and confirm the private packages resolve. For xdist, compare coverage serial vs `-n auto` and run it 3×.
5. **Measure in CI.** Push and wait for the PR build. A push to an existing PR may not trigger one; then queue a manual run without deploy: `POST .../_apis/pipelines/<defId>/runs?api-version=7.1` with `{"resources":{"repositories":{"self":{"refName":"refs/heads/<branch>"}}},"templateParameters":{"stage":"none"}}` (check the pipeline's `stage` parameter first). Compare step by step with the baseline. When experimenting, one lever per commit; revert any lever whose run shows a net loss. Vet the numbers with `benchmark-checklist`. Done when the PR build is green and every kept lever shows its saving in the timeline.
6. **Report.** PR description: one line with before → after of the CI Build stage. PR comment: a before/after table per step with build ids, plus what was tried and dropped and why.

## Levers (ODJ Python template)

| Lever | Precondition | Typical saving |
|---|---|---|
| `copy_build_artifacts: false` (with the template's default `run_build_jobs_parallel: true`) — the container job no longer waits for the sourcecode job and the workspace artifact (incl. `.venv`, often 400 MB) is neither uploaded nor downloaded | The Dockerfile copies only checked-in files (`git ls-files` every COPY source); nothing in the container job reads generated files (OpenAPI file committed) | 2–4 min: upload ~35–45 s + download ~20–27 s + agent wait (up to 1.5 min) + the whole container job leaves the critical path |
| pre-commit → `uvx prek@<pin> run --all-files --show-diff-on-failure` (same `.pre-commit-config.yaml`), pin a release older than the uv cooldown | Hooks pass under prek locally | 20–30 s (hook install ~6 s instead of ~25 s) |
| `SKIP: gitleaks` on the hook step | The ODJ template runs its own GitLeaks job | ~55 s (the hook builds a Go toolchain) |
| `python_install_command: uv pip install --system --extra-index-url "$PIP_EXTRA_INDEX_URL" -r requirements.txt` and `build_cache_enabled: false` | `requirements.txt` exported from `uv.lock`; `python_env` provides `PIP_EXTRA_INDEX_URL` | 25–40 s. The install can't be dropped: Snyk's pip scan reads the installed packages from the system Python |
| `sonar.plugins.downloadOnlyRequired=true` in `sonar-project.properties` | — | ~7 s |
| pytest-xdist (`-n auto` in `python_test_command` and `make test`, dependency in the `test` group) | Serial local run > ~15 s; tests don't share files or ordering | Small in CI: hosted agents have 2 vCPUs (47 → 43 s). Locally ~2×. Set `asyncio_default_fixture_loop_scope` explicitly, or pytest-asyncio warns once per worker |

## Not worth it (measured)

- Caching prek/pre-commit envs: the cache is ~180 MB, restoring it costs about what a fresh prek install takes.
- `uv sync --compile-bytecode`: uv sync +11.7 s, pytest only −7 s.
- Docker layer caching on Microsoft-hosted agents: no persistent cache; the build is ~35–45 s anyway.
- xdist for a suite that already runs in < 10 s: no gain, 14 warnings.
- ODJ-managed steps (job init ~20 s, Sonar analysis ~40 s, coverage publish ~10 s, deploy trigger ~2.5 min): leave them.

## Trade-off to state in the PR

With `copy_build_artifacts: false` the image builds even when tests fail (on PRs) and is pushed on main even when tests fail; the deploy stage still needs the whole CI stage green, so nothing broken deploys. A build uses one more hosted agent at once.

## Reference result

Prism (2026-11): API PR build 509 s → 164–170 s, eval 379–416 s → 172 s.
