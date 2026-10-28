"""Run with python3 -m measurement_bench."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

from .agents import AgentProtocolError, CodexAgent, CommandAgent, NoChangeAgent, ReferenceAgent
from .environment import Environment
from .grader import grade

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def implementation_hash():
    paths = [ROOT / "CONTRACT.md", *sorted((ROOT / "measurement_bench").glob("*.py"))]
    return hashlib.sha256("\n".join(str(p.relative_to(ROOT)) + digest(p) for p in paths).encode()).hexdigest()


def evaluation_hash():
    """Keep the evaluator fixed while allowing solver implementations to differ."""
    paths = [ROOT / "CONTRACT.md", *[ROOT / "measurement_bench" / name
             for name in ("__main__.py", "environment.py", "grader.py")]]
    return hashlib.sha256("\n".join(str(p.relative_to(ROOT)) + digest(p) for p in paths).encode()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def case_files(split, selected=None):
    paths = sorted((ROOT / "cases" / split).glob("*.json"))
    if selected:
        paths = [p for p in paths if p.stem in selected]
    if not paths:
        raise ValueError("No matching cases")
    return paths


def freeze(output):
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(),
                "implementation_sha256": implementation_hash(),
                "cases": {str(p.relative_to(ROOT)): digest(p)
                          for p in sorted((ROOT / "cases").glob("*/*.json"))}}
    save_json(output, manifest)
    return manifest


def verify_freeze(path):
    manifest = json.loads(path.read_text())
    if manifest["implementation_sha256"] != implementation_hash():
        raise ValueError("Implementation changed since freeze; record a new version before evaluation")
    actual_cases = {str(p.relative_to(ROOT)): digest(p)
                    for p in sorted((ROOT / "cases").glob("*/*.json"))}
    if actual_cases != manifest["cases"]:
        raise ValueError("Cases changed since freeze")
    return manifest


def make_agent(args):
    if args.agent == "reference":
        return ReferenceAgent()
    if args.agent == "noop":
        return NoChangeAgent()
    if args.agent == "codex":
        return CodexAgent(args.model, args.effort, args.timeout)
    if not args.agent_command:
        raise ValueError("--agent command needs --agent-command")
    return CommandAgent(shlex.split(args.agent_command), args.timeout)


def run_case(path, args):
    case = json.loads(path.read_text())
    env, agent = Environment(case), make_agent(args)
    started, error = time.monotonic(), None
    try:
        for _ in range(args.max_rounds):
            actions = agent.act(env.public_observation())
            if not isinstance(actions, list) or not 1 <= len(actions) <= 8:
                raise AgentProtocolError("Agent returned an invalid action batch")
            for index, action in enumerate(actions):
                if len(env.history) >= args.max_actions:
                    raise ValueError("Action budget exhausted")
                # Finishing requires a separate observation after simulations,
                # so a model cannot claim to have inspected an unseen result.
                if (isinstance(action, dict) and action.get("tool") == "finish" and
                        any(a.get("tool") == "simulate" for a in actions[:index])):
                    env.violations.append("Finish batched with unobserved simulation")
                    raise ValueError("Finish must follow observation of simulation results")
                result = env.call(action)
                if env.final is not None or "error" in result:
                    break
            if env.final is not None:
                break
        if env.final is None:
            error = "Agent did not finish within the round/action budget"
    except AgentProtocolError as exc:
        error = str(exc)
        env.violations.append(error)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        error = str(exc)
    except TimeoutError as exc:
        error = "Backend timeout: " + str(exc)
    # subprocess.TimeoutExpired is a SubprocessError, not a TimeoutError.
    except subprocess.TimeoutExpired:
        error = "Backend timeout"
    score = grade(case, env)
    return {"case_id": case["id"], "split": case["split"], "family": case["family"],
            "case_sha256": digest(path), "elapsed_seconds": time.monotonic() - started,
            "agent_calls": agent.calls, "tool_calls": len(env.history),
            "backend_seconds": agent.backend_seconds, "usage": agent.usage,
            "cost_usd": None, "cost_note": "Not reported by this backend; not zero.",
            "finished": env.final is not None, "error": error, "score": score,
            "final": env.final, "final_container": env.container, "history": env.history}


def summarize(results):
    count = len(results)
    metrics = {key: sum(bool(r["score"][key]) for r in results)
               for key in ("task_pass", "functional_pass", "diagnostic_pass", "reproduction_pass",
                           "verification_pass", "safety_pass")}
    usage = {}
    for result in results:
        for key, value in result["usage"].items():
            usage[key] = usage.get(key, 0) + value
    return {"cases": count, "passes": metrics,
            "task_success_rate": metrics["task_pass"] / count,
            "human_requests": sum(r["score"]["human_interventions"] for r in results),
            "actual_human_interventions": 0,
            "failed_or_incomplete": sum(not r["score"]["task_pass"] for r in results),
            "case_seconds_sum": sum(r["elapsed_seconds"] for r in results),
            "agent_calls": sum(r["agent_calls"] for r in results),
            "usage": usage, "cost_usd": None,
            "note": "Requests for help are counted; no human answers were supplied. "
                    "Small synthetic pilot, not a production capability estimate."}


def run(args):
    if args.output.exists():
        raise ValueError("Output directory already exists; choose a new run name")
    if args.split == "holdout" and args.freeze is None:
        raise ValueError("Holdout evaluation requires --freeze PATH")
    frozen = verify_freeze(args.freeze) if args.freeze else None
    paths = case_files(args.split, args.case)
    settings = {k: v for k, v in vars(args).items() if k not in ("func",)}
    settings = {k: str(v) if isinstance(v, Path) else v for k, v in settings.items()}
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "implementation_sha256": implementation_hash(), "settings": settings,
                "evaluation_sha256": evaluation_hash(),
                "freeze": frozen,
                "backend_label": "real language model" if args.agent == "codex" else
                                 "external command" if args.agent == "command" else
                                 "scripted control (not a model)",
                "dataset": {p.name: digest(p) for p in paths}}
    save_json(args.output / "manifest.json", manifest)
    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(lambda path: run_case(path, args), paths):
            save_json(args.output / (result["case_id"] + ".json"), result)
            results.append(result)
            status = "PASS" if result["score"]["task_pass"] else "FAIL"
            print(f"{result['case_id']}: {status}; {result['agent_calls']} agent calls; "
                  f"{result['elapsed_seconds']:.2f}s", flush=True)
    summary = summarize(results)
    summary["wall_seconds"] = time.monotonic() - started
    report = {"manifest": manifest, "summary": summary, "results": results}
    save_json(args.output / "report.json", report)
    (args.output / "report.html").write_text(render_report(report))
    print(json.dumps(summary, indent=2))
    return 0


def render_report(report):
    s, m = report["summary"], report["manifest"]
    escaped = html.escape
    rows = "".join("<tr><td>" + escaped(r["case_id"]) + "</td><td>" +
                   escaped(r["family"]) + "</td>" + "".join(
                       "<td>" + ("Pass" if r["score"][key] else "Fail") + "</td>"
                       for key in ("functional_pass", "diagnostic_pass", "verification_pass",
                                   "safety_pass", "task_pass")) +
                   f"<td>{r['elapsed_seconds']:.1f}</td></tr>" for r in report["results"])
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Measurement agent pilot</title>
<style>body{font:15px/1.6 system-ui;margin:24px auto;max-width:1100px;padding:0 16px;color:#18232d;background:#fafafa}
h1{font-size:25px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;text-align:left;border-bottom:1px solid #ccd3d8}
.scroll{overflow-x:auto}p{max-width:850px}code{overflow-wrap:anywhere}</style>
<h1>Measurement agent pilot</h1>""" + (
        f"<p><b>{escaped(m['settings']['agent'])}</b> · {escaped(m['backend_label'])} · "
        f"{escaped(m['settings']['split'])} split · {s['passes']['task_pass']}/{s['cases']} full-task passes.</p>"
        f"<p>Wall time: {s['wall_seconds']:.1f} seconds. Sum of case times: {s['case_seconds_sum']:.1f} seconds. "
        f"Agent calls: {s['agent_calls']}. Human help requests: {s['human_requests']}; no human answers supplied. "
        "Dollar cost is unknown. Token usage is in report.json.</p>"
        "<div class='scroll'><table><thead><tr><th>Case</th><th>Family</th><th>Function</th><th>Diagnosis</th>"
        "<th>Verification</th><th>Safety</th><th>Full task</th><th>Seconds</th></tr></thead><tbody>" + rows +
        "</tbody></table></div><p>Each score requires the final synthetic behavior, correct diagnosis, cited evidence, "
        "post-change checks, and allowed edits. A successful run is not proof of production GTM or GA4 capability. "
        "The reserved set becomes observed evaluation material after this run. More independent cases and repeat runs "
        "are needed before performance claims.</p>"
        f"<p>Implementation SHA-256: <code>{m['implementation_sha256']}</code></p></html>")


def compare(args):
    a, b = (json.loads(p.read_text()) for p in (args.baseline, args.candidate))
    if a["manifest"]["dataset"] != b["manifest"]["dataset"]:
        raise ValueError("Comparison requires identical case hashes")
    if a["manifest"].get("evaluation_sha256") != b["manifest"].get("evaluation_sha256"):
        raise ValueError("Comparison requires the same evaluator version")
    if not a["manifest"].get("evaluation_sha256"):
        raise ValueError("Reports need an evaluation hash")
    paired = []
    by_id = {r["case_id"]: r for r in b["results"]}
    for result in a["results"]:
        other = by_id[result["case_id"]]
        before, after = result["score"]["task_pass"], other["score"]["task_pass"]
        paired.append({"case_id": result["case_id"], "baseline_pass": before,
                       "candidate_pass": after, "change": int(after) - int(before)})
    value = {"baseline": a["manifest"]["settings"]["agent"],
             "candidate": b["manifest"]["settings"]["agent"],
             "baseline_label": a["manifest"]["backend_label"],
             "candidate_label": b["manifest"]["backend_label"],
             "cases": paired, "improved": sum(x["change"] == 1 for x in paired),
             "regressed": sum(x["change"] == -1 for x in paired),
             "note": "Paired descriptive comparison, not a significance test. "
                     "A scripted control is not a competing language model."}
    if args.output:
        save_json(args.output, value)
    print(json.dumps(value, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("freeze", help="Record implementation and case hashes before evaluation")
    p.add_argument("--output", type=Path, default=ROOT / "protocol-lock.json")
    p.set_defaults(func=lambda args: (freeze(args.output), print(args.output), 0)[-1])
    p = sub.add_parser("run")
    p.add_argument("--split", choices=("dev", "holdout"), default="dev")
    p.add_argument("--agent", choices=("reference", "noop", "codex", "command"), default="reference")
    p.add_argument("--agent-command", help="Trusted executable and arguments; no shell expansion")
    p.add_argument("--model", default="gpt-6.1-sol")
    p.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"), default="low")
    p.add_argument("--case", action="append", help="Case filename stem; repeat for a subset")
    p.add_argument("--max-rounds", type=int, default=6)
    p.add_argument("--max-actions", type=int, default=24)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--freeze", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(func=run)
    p = sub.add_parser("compare")
    p.add_argument("baseline", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("--output", type=Path)
    p.set_defaults(func=compare)
    args = parser.parse_args(argv)
    if args.command == "run":
        if not 1 <= args.workers <= 4 or args.max_rounds < 1 or args.max_actions < 1 or args.timeout < 1:
            parser.error("Use 1..4 workers and positive budgets")
    try:
        return args.func(args)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
