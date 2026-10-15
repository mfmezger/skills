---
name: benchmark-checklist
description: "Vet a measured number before reporting or acting on it: a speedup, regression, latency, throughput, cost, or eval score. Use after running a benchmark, load test or eval, or in the mfm-workflow Measure step."
source: https://github.com/cursor/plugins/blob/main/pstack/skills/benchmark-checklist/SKILL.md
---

# Benchmark checklist

Use this when you produce a number: a PR's before/after, a regression claim, a library or config choice, a model/prompt eval score, a latency or cost estimate. Answer each question with evidence from a run, not a guess about the code.

For a quick ballpark the user asked for, one run is enough. Still check questions 4 and 7 and say it is one run. A choice between options is never a ballpark.

## Before you run anything

- Write down the claim you expect to make, in the words you would ship ("p50 latency drops 30% on the 60k-row dataset", "F1 0.81 → 0.86 on the golden set"). The questions test that sentence.
- Read the measurement script. Note what it times, counts and ignores.
- Check machine load (`uptime`, cores via `sysctl -n hw.ncpu` on macOS / `nproc` on Linux). If the machine is busy and you cannot stop it, interleave the sides so both see the same noise, and say so. Remote LLM APIs add their own noise: interleave and repeat.

## The questions

1. **Why not double?** Name the limiter. Profile in a run you do not report (profilers slow the work). Use `py-spy record`/`py-spy top`, `cProfile`, CPU per process (`top`), I/O wait, DB query counts, and map the hot spot to source. Watch the load generator: if it saturates first, you measured the load generator. For LLM calls the limiter is often provider latency, rate limits or concurrency caps (`-j`). If a change did not move the number, the limiter explains why.
2. **Was it tuned?** Run every side the way production runs it: same env and `Settings`, connection pools, batch sizes, caches as warm or cold as production, same versions and data, same model, temperature and judge. If one side runs on defaults, you compared configurations, not implementations. If you cannot tune it, do not pick a winner from that run.
3. **Did it break limits?** Do the arithmetic: bytes/s against disk and network, ops/s × cost per op against cores, time saved against the time the changed piece took. Removing a piece that takes 10% of the run makes it at most ~11% faster. A result past a limit measured a cache, a no-op or a bug.
4. **Did it error?** Count failures, non-2xx responses, timeouts, retries, transport errors, refusals and parse failures, and check outputs are correct, not just present. Rejections are fast; timeouts and retries are slow. Report the error rate next to the metric. If the script does not count errors, add the count.
5. **Does it reproduce?** Run each side at least 5 times, alternating (A, B, A, B) so warmup, caches and drift favor neither. Report median and range. For evals, report run-to-run spread; a gap smaller than the spread is no measurable difference. For close calls use a rank-sum test or bootstrap CI.
6. **Does it matter?** Next to any micro result, measure the end-to-end path a user waits on, with realistic sizes and concurrency, and report the micro result as a share of the whole. A helper that takes 1% of a request can make it at most 1% faster.
7. **Did it even happen?** Confirm the work ran inside the timed region: the request reached the server, rows were written, the model was actually called (not served from a cache, VCR cassette or memoized result), and the code used the result. Un-awaited coroutines, unconsumed generators and swallowed exceptions produce numbers for work that never happened.

## Report

- Lead with the verdict: faster, slower, better, worse, no measurable difference, or inconclusive.
- Give the number with unit, run count, range and limiter: "p50 41 ms → 33 ms, median of 7 runs per side, range 32–35 ms after, bound by JSON parsing on one core."
- Call it inconclusive when you cannot name the limiter, a side ran untuned, or you could not check questions 4 and 7. Name the gap.
- In an ADO PR description keep one primary number (the description caps at 4000 chars); put runs, range and limiter evidence in a PR comment or local notes file.
