# Web Analytics Benchmark

A small, runnable benchmark for agents that diagnose and repair synthetic
measurement implementations. It includes an in-memory environment, bounded
tools, an objective grader, a scripted reference, and a real Codex adapter.

This is a **pilot benchmark**, not a GTM emulator, a production repair service,
or evidence that an agent can fix a real client's implementation.

## Quick start

Python 3.11 or later is required. The project has no third-party dependencies.
Run these commands from this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m measurement_bench run --agent reference --split dev --output runs/reference-dev
```

Each run creates a new directory. Existing runs are never overwritten. Open
`report.html` to inspect results. `report.json` contains the scores, timing,
token usage, final state, and complete synthetic tool traces. `manifest.json`
records the settings and source/data hashes.

## What the cases cover

There are six development cases and six reserved test cases. Both sets cover:

- Duplicate purchase events.
- Lost consent updates.
- Campaign information lost through URL handling.
- Different setup requirements across architectures.
- Historical notes contradicting current state.
- A healthy implementation that must remain unchanged.

Each case includes consented checkout, denied-consent checkout, and two distinct
orders on one page. The grader checks both visit and purchase signals. Disabling
all tags, bypassing consent, or hiding valid orders cannot count as a repair.

The case-author subagent created the fixtures separately from the runner. The
public interpreter is specified in [CONTRACT.md](CONTRACT.md). Dataset limits
are described in [DATASET.md](DATASET.md).

## Agent workflow

The agent receives a task, the public tool contract, and scenario descriptions.
It uses five tools:

1. `inspect_container`: read authoritative current state.
2. `read_documents`: read dated historical context.
3. `simulate`: reproduce or verify a scenario.
4. `apply_patch`: apply allowed changes atomically, in memory.
5. `finish`: return diagnosis, evidence, help request, and summary.

The agent can batch independent calls. It must observe simulation results before
finishing. Its observations contain no oracle checks, split labels, case family,
or private expected answers. The grader never feeds its answers back to a solver.

All state resets between cases. Tool history identifies the state revision.
This keeps current state, old documents, and verification evidence separate.

## Real-model run

The Codex CLI must be installed and signed in. The adapter uses that existing
login; this project does not read or copy its credentials. Model calls consume
the current account's usage. The default model is `gpt-6.1-sol`, at low effort.

```bash
python3 -m measurement_bench run --agent codex --split dev --workers 1 --output runs/codex-dev
```

Each model call runs `codex exec` in an empty temporary directory. User config,
rules, project instructions, memories, plugins, hooks, shell execution, browser
access, and multi-agent tools are disabled for the evaluation process. An output
schema restricts the action transport. Unexpected completed built-in tool events
are rejected. The solver can use only the synthetic action interface.

These are application-level controls, not an OS-level confidentiality boundary.
Use a separate machine or container if evaluating adversarial agent executables.
The provider-neutral command adapter is a **trusted executable** with local
process permissions; it is not a sandbox.

The default limits are six model rounds, 24 synthetic actions, and 120 seconds
per backend call. Use `--timeout`, `--max-rounds`, and `--max-actions` to change
them before an experiment. `--workers` supports one to four concurrent cases.
Timeouts and incomplete runs count as task failures. No retry silently replaces
a failed trial.

The CLI reports token usage for completed model calls. Timed-out calls may have
unreported usage. Dollar cost is recorded as `null`, not zero, because the CLI
does not report a billing charge. Human help requests are counted separately
from actual interventions; this runner does not provide human answers.

The adapter follows the official [non-interactive Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## Evaluate reserved cases

Develop on `cases/dev`. Leave `cases/holdout` and its private answers out of
agent development. Freeze the implementation and fixtures before evaluation:

```bash
python3 -m measurement_bench freeze --output protocol-lock.json
python3 -m measurement_bench run --agent codex --split holdout --freeze protocol-lock.json --output runs/codex-holdout
```

A reserved-set run refuses to start if its code or cases differ from the freeze.
Source changes during a run are outside this prototype's guarantees; do not
edit the implementation during a recorded experiment.

Once you inspect these results, the cases are observed test material. Use a new,
independently authored set for the next claim of unseen-task generalization.
Shipping the fixtures publicly also makes them unsuitable as a permanent secret
test set. Six cases and one run per case are not enough for broad capability
claims.

## How scoring works

Each result reports separate criteria:

- **Functional:** final hits match exact count and field checks.
- **Diagnostic:** the diagnosis set matches the case contract.
- **Reproduction:** every scenario was observed before any change.
- **Verification:** every scenario was observed at the final state revision.
- **Safety:** no forbidden/malformed actions, immutable changes, or excess edits.
- **Full task:** all criteria pass, a valid finish exists, and the help decision
  matches the case. Stale-context diagnoses require document evidence.

The grader checks resulting behavior, not an exact patch string. Equivalent
allowed repairs can pass. The simplified code-to-diagnosis mapping is explicit
and narrow; free-form explanation quality is not independently judged.

## How to measure an improvement

First run the no-change control and the scripted reference on the same cases:

```bash
python3 -m measurement_bench run --agent noop --split holdout --freeze protocol-lock.json --output runs/noop-holdout
python3 -m measurement_bench run --agent reference --split holdout --freeze protocol-lock.json --output runs/reference-holdout
```

These check that the benchmark rejects doing nothing and accepts the known
repair procedure. **The reference is scripted. It is not a competing LLM.**

For a real agent-design comparison, define baseline and candidate variants
before running them. Keep cases, evaluator, model, effort, time/action budgets,
and retry policy fixed. Run multiple independent trials. Change one design
factor, such as context selection or a review step. Report all failures and
regressions, including infrastructure failures.

Use the provider-neutral adapter for versioned solver programs. It runs the
specified argument list without shell expansion. On each call, it sends one
public observation JSON object to stdin. The program returns one JSON object:

```json
{"actions":[{"tool":"inspect_container","arguments_json":"{}"}]}
```

The entire public history is included on the next call, so the program need not
persist state. Use absolute paths for executable and script arguments.

```bash
python3 -m measurement_bench run --agent command --agent-command 'python3 /absolute/path/solver-v1.py' --split dev --output runs/v1-dev
python3 -m measurement_bench run --agent command --agent-command 'python3 /absolute/path/solver-v2.py' --split dev --output runs/v2-dev
python3 -m measurement_bench compare runs/v1-dev/report.json runs/v2-dev/report.json --output runs/comparison.json
```

`compare` requires identical case hashes and evaluator hashes. Solver programs
may differ. It reports paired improvements and regressions; it does not perform
a significance test. Source hashes and frozen protocol settings support review.

## Scope and next useful extension

The simulator deliberately omits browser execution, real GTM compilation,
Advanced Consent Mode, full GA4 session attribution, downstream vendor
deduplication, asynchronous delivery, and delayed reporting. Every deployment is
local and synthetic. Nothing is sent to GTM, GA4, client websites, or Notion.

The next useful extension is independently authored browser fixtures with
recorded outgoing requests and mutation tests. Add them after this small runner
has proved useful. Avoid increasing agent count until a controlled comparison
shows a benefit.

See [CURRENT.md](CURRENT.md) for the latest measured runs and known limits.

## License

[ISC](LICENSE)
