"""Security test cases: what a sandbox must allow and what it must block."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SEVERITIES = ("critical", "high", "medium")
EXPECTS = ("success", "failure")


@dataclass(frozen=True)
class PolicyUpdate:
    rule_name: str
    binary: str
    endpoint: str  # host:port:access:protocol:enforcement, the `openshell policy update` format


@dataclass(frozen=True)
class Step:
    command: str | None = None
    expect: str | None = None  # "success" = exit 0 is the secure outcome
    policy_update: PolicyUpdate | None = None


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    policy: str
    severity: str
    threat: str
    steps: tuple[Step, ...]
    requires: tuple[str, ...] = field(default=())
    isolated: bool = False  # True: gets its own sandbox (it changes policy)


class CaseError(ValueError):
    pass


def _step(raw: dict, cid: str) -> Step:
    if "policy_update" in raw:
        pu = raw["policy_update"] or {}
        missing = {"rule_name", "binary", "endpoint"} - set(pu)
        if missing:
            raise CaseError(f"{cid}: policy_update missing {sorted(missing)}")
        if len(str(pu["endpoint"]).split(":")) != 5:
            raise CaseError(f"{cid}: endpoint must be host:port:access:protocol:enforcement")
        return Step(policy_update=PolicyUpdate(str(pu["rule_name"]), str(pu["binary"]), str(pu["endpoint"])))
    if raw.get("expect") not in EXPECTS:
        raise CaseError(f"{cid}: expect must be one of {EXPECTS}")
    if not raw.get("command"):
        raise CaseError(f"{cid}: step needs a command")
    return Step(command=str(raw["command"]), expect=str(raw["expect"]))


def load_cases(path: str | Path) -> list[Case]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    cases: list[Case] = []
    seen: set[str] = set()
    for raw in data.get("cases", []):
        cid = raw.get("id")
        if not cid or cid in seen:
            raise CaseError(f"missing or duplicate case id: {cid!r}")
        seen.add(cid)
        if raw.get("severity") not in SEVERITIES:
            raise CaseError(f"{cid}: severity must be one of {SEVERITIES}")
        if "steps" in raw:
            steps = tuple(_step(s, cid) for s in raw["steps"])
        else:
            steps = (_step(raw, cid),)
        if not any(s.command for s in steps):
            raise CaseError(f"{cid}: needs at least one command step")
        cases.append(
            Case(
                id=cid,
                title=str(raw.get("title", cid)),
                policy=str(raw["policy"]),
                severity=raw["severity"],
                threat=str(raw.get("threat", "")),
                steps=steps,
                requires=tuple(raw.get("requires", ())),
                isolated=bool(raw.get("isolated", False)),
            )
        )
    return cases
