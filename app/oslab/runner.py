"""Runs security cases against sandboxes and scores the result."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .cases import Case
from .executors import Executor


@dataclass
class StepResult:
    command: str | None
    expect: str | None
    rc: int | None
    ok: bool
    seconds: float = 0.0
    output: str = ""
    action: str = "exec"


@dataclass
class CaseResult:
    id: str
    title: str
    policy: str
    severity: str
    threat: str
    status: str  # pass | fail | skip | error
    steps: list[StepResult] = field(default_factory=list)
    note: str = ""


def _run_case(ex: Executor, sandbox: str, case: Case) -> CaseResult:
    res = CaseResult(case.id, case.title, case.policy, case.severity, case.threat, "pass")
    for binary in case.requires:
        probe = ex.exec(sandbox, f"command -v {binary} >/dev/null")
        if probe.rc != 0:
            res.status, res.note = "skip", f"sandbox image lacks {binary}"
            return res
    for step in case.steps:
        if step.policy_update:
            pu = step.policy_update
            try:
                ex.policy_update(sandbox, pu.rule_name, pu.binary, pu.endpoint)
                res.steps.append(StepResult(None, None, 0, True, action=f"policy_update {pu.rule_name} {pu.endpoint}"))
            except Exception as e:  # a failed policy update is a failed case, not a crash
                res.steps.append(StepResult(None, None, None, False, output=str(e)[-1000:], action="policy_update"))
                res.status = "error"
                return res
            continue
        r = ex.exec(sandbox, step.command)
        ok = (r.rc == 0) if step.expect == "success" else (r.rc != 0)
        res.steps.append(StepResult(step.command, step.expect, r.rc, ok, round(r.seconds, 3), r.output[-600:]))
        if not ok:
            res.status = "fail"
    return res


MAX_SANDBOX_NAME = 19  # OpenShell v0.1.9 MAX_ROUTABLE_NAME_LEN (grpc/validation.rs)


def sandbox_name(prefix: str, policy: str) -> str:
    """Short, unique, DNS-safe: e.g. 'os-research-1a2b3c' (<= 19 chars)."""
    room = MAX_SANDBOX_NAME - len(prefix) - 8  # two dashes + 6 hex
    short = policy[:max(room, 1)].rstrip("-")
    return f"{prefix}-{short}-{uuid.uuid4().hex[:6]}"


def run_suite(ex: Executor, cases: list[Case], policies_dir: str | Path, prefix: str = "os") -> dict:
    policies_dir = Path(policies_dir)
    groups: dict[str, list[Case]] = defaultdict(list)
    for c in cases:
        key = f"{c.policy}::{c.id}" if c.isolated else c.policy
        groups[key].append(c)

    started = time.time()
    results: list[CaseResult] = []
    for key, group in groups.items():
        policy = group[0].policy
        policy_path = policies_dir / f"{policy}.yaml"
        name = sandbox_name(prefix, policy)
        try:
            ex.create(name, str(policy_path))
        except Exception as e:
            for c in group:
                results.append(CaseResult(c.id, c.title, c.policy, c.severity, c.threat, "error", note=f"sandbox create failed: {str(e)[-500:]}"))
            continue
        try:
            for c in group:
                results.append(_run_case(ex, name, c))
        finally:
            ex.delete(name)

    order = {c.id: i for i, c in enumerate(cases)}
    results.sort(key=lambda r: order[r.id])
    return summarize(results, started)


def summarize(results: list[CaseResult], started: float | None = None) -> dict:
    counts = {s: sum(r.status == s for r in results) for s in ("pass", "fail", "skip", "error")}
    scored = counts["pass"] + counts["fail"] + counts["error"]
    blocking = [r.id for r in results if r.status in ("fail", "error") and r.severity in ("critical", "high")]
    return {
        "started_at": started or time.time(),
        "finished_at": time.time(),
        "counts": counts,
        "pass_rate": round(counts["pass"] / scored, 4) if scored else 0.0,
        "blocking_failures": blocking,
        "gate": "pass" if not blocking and counts["pass"] > 0 else "fail",
        "results": [asdict(r) for r in results],
    }
