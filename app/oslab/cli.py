"""oslab: lint OpenShell policies and run the sandbox security suite.

    oslab lint policies/*.yaml
    oslab run --cases evals/datasets/security-cases.yaml --policies policies --out evals/results/2026-11-19
"""
from __future__ import annotations

import argparse
import glob
import sys
from datetime import date

from . import report
from .cases import load_cases
from .executors import OpenShellExecutor
from .policy_lint import lint_files
from .runner import run_suite


def cmd_lint(args: argparse.Namespace) -> int:
    files = sorted({f for pattern in args.files for f in glob.glob(pattern)})
    if not files:
        print("no policy files matched", file=sys.stderr)
        return 2
    findings = lint_files(files)
    for f in findings:
        print(f)
    errors = [f for f in findings if f.level == "error"]
    print(f"{len(files)} files, {len(errors)} errors, {len(findings) - len(errors)} warnings")
    return 1 if errors else 0


def cmd_run(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c.id in wanted]
    lint_errors = [f for f in lint_files(sorted({f"{args.policies}/{c.policy}.yaml" for c in cases})) if f.level == "error"]
    if lint_errors and not args.allow_lint_errors:
        for f in lint_errors:
            print(f, file=sys.stderr)
        return 1
    ex = OpenShellExecutor(image=args.image)
    summary = run_suite(ex, cases, args.policies)
    summary["meta"] = {"target": args.target}
    out = report.write(summary, args.out or f"evals/results/{date.today().isoformat()}-{args.target}", args.title)
    print(report.to_markdown(summary, args.title))
    print(f"results written to {out}")
    return 0 if summary["gate"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="oslab")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("lint", help="check policies against the repo's safety rules")
    pl.add_argument("files", nargs="+")
    pl.set_defaults(fn=cmd_lint)
    pr = sub.add_parser("run", help="run the security suite against a live gateway")
    pr.add_argument("--cases", default="evals/datasets/security-cases.yaml")
    pr.add_argument("--policies", default="policies")
    pr.add_argument("--out")
    pr.add_argument("--image", help="sandbox image (default: $OSLAB_SANDBOX_IMAGE)")
    pr.add_argument("--target", default="kind", help="label for the report: kind | eks")
    pr.add_argument("--only", help="comma-separated case ids")
    pr.add_argument("--title", default="OpenShell sandbox security suite")
    pr.add_argument("--allow-lint-errors", action="store_true")
    pr.set_defaults(fn=cmd_run)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
