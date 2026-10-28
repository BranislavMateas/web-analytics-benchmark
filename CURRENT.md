# Current state

Last verified: 26 October 2026. Version: 0.1.0 pilot.

## What exists

- Twelve synthetic fixtures: six development and six reserved test cases.
- A deterministic interpreter and five bounded in-memory agent tools.
- Objective functional, diagnostic, reproduction, verification, and safety checks.
- A scripted reference, a no-change control, a real Codex CLI adapter, and a
  provider-neutral command adapter.
- Frozen source/data hashes and paired-result comparison.
- Twenty-four passing unit tests.

## Authoritative recorded runs

The frozen protocol is [protocol-lock.json](protocol-lock.json). The following
three reserved-set runs use the same cases and evaluator version:

- [No-change control](runs/noop-holdout-final/report.html): **1/6 full-task passes**.
- [Scripted reference](runs/reference-holdout-final/report.html): **6/6 full-task passes**.
- [Real-model baseline](runs/codex-holdout-v1/report.html): **4/6 full-task passes**.

The real model was `gpt-6.1-sol`, low effort, one concurrent case, a 120-second
per-call limit, six-round limit, and 24-action limit. It used 12 backend calls
and took 373.3 seconds of wall time. Two cases timed out before returning their
first action. They count as failures. The four other cases passed all criteria.
No human help requests or supplied human answers were recorded. This does not
estimate how much human work a production system would need.

Reported completed-call usage: 143,521 input tokens, including 11,008 cached
input tokens; 1,149 output tokens; 37 reasoning output tokens. Token fields are
preserved as reported by the CLI. Usage for timed-out calls may be missing.
Dollar billing cost was not reported and remains unknown.

Machine-readable evidence:

- [Real-model report and complete synthetic traces](runs/codex-holdout-v1/report.json).
- [No-change versus real model](runs/noop-vs-codex.json).
- [Scripted reference versus real model](runs/reference-vs-codex.json).

## Interpretation

This establishes a working pilot and one real-model baseline. It does not show
that one agent design is better than another. The no-change and reference
solvers are scripted controls, not alternative language models.

The reserved set is now observed evaluation material. Do not tune on its
failures and then describe a later score on it as unseen-task performance.
Future agent-design comparisons need predeclared variants, fixed budgets,
repeat trials, and fresh independently authored cases.

## Preliminary runs retained for provenance

`runs/codex-dev-pilot` completed 2/6 development cases; four timed out. That run
started before the final grading review and is not scored under this frozen
protocol. A later isolated development connectivity check completed 1/1 case.
Intermediate reference/control runs are also retained. Use the authoritative
paths above, not those preliminary folders, for the current pilot results.

## Known limits

- The interpreter is not a GTM browser runtime or full GA4 attribution engine.
- Six reserved cases and a single real-model run do not support broad claims.
- The case author and solver use the same model family, which can bias results.
- CLI tool restrictions are application-level controls, not an OS boundary.
- Timeouts demonstrate execution failures; they do not establish a wrong diagnosis.
- Free-form explanation quality and production deployment behavior are not graded.

Start with [README.md](README.md) for commands and [CONTRACT.md](CONTRACT.md)
for the exact public environment semantics.
