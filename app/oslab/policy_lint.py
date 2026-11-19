"""Policy-as-code checks for OpenShell sandbox policies.

OpenShell validates that a policy is well-formed. These checks add the
organisation's rules on top: what a *safe* policy looks like. Run them in CI
before a policy can be merged, so a risky rule never reaches a gateway.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

# Paths an agent must never be able to write.
PROTECTED_WRITE_PATHS = {"/", "/bin", "/usr", "/lib", "/etc", "/proc", "/sys", "/boot", "/root", "/var/run"}
# Hosts that point back into the platform instead of out to the internet.
INTERNAL_HOST_SUFFIXES = (".svc", ".svc.cluster.local", ".cluster.local", ".internal", "localhost")
# Interpreters that can run arbitrary code: allowing one is allowing everything.
SHELL_BINARIES = {"/bin/sh", "/bin/bash", "/usr/bin/bash", "/usr/bin/sh", "/usr/bin/env"}
VALID_ACCESS = {"read-only", "read-write", "full"}


@dataclass(frozen=True)
class Finding:
    file: str
    rule: str
    level: str  # "error" blocks the merge, "warn" is advisory
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():5} {self.rule} {self.file}: {self.message}"


def _is_internal(host: str) -> bool:
    h = host.strip().lower().rstrip(".")
    if h.endswith(INTERNAL_HOST_SUFFIXES) or h == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified


def lint_policy(doc: dict, file: str = "<policy>") -> list[Finding]:
    out: list[Finding] = []

    def add(rule: str, level: str, msg: str) -> None:
        out.append(Finding(file, rule, level, msg))

    if not isinstance(doc, dict):
        return [Finding(file, "P000", "error", "policy is not a YAML mapping")]
    if doc.get("version") != 1:
        add("P001", "error", "version must be 1")

    fs = doc.get("filesystem_policy") or {}
    if not fs:
        add("P002", "error", "filesystem_policy is required (no implicit defaults in this repo)")
    for p in fs.get("read_write", []) or []:
        norm = "/" + str(p).strip("/")
        if norm in PROTECTED_WRITE_PATHS or any(norm == x or norm.startswith(x + "/") for x in PROTECTED_WRITE_PATHS - {"/"}):
            add("P003", "error", f"read_write includes protected path {p}")

    nps = doc.get("network_policies") or {}
    if not isinstance(nps, dict):
        add("P010", "error", "network_policies must be a mapping of rule name -> rule")
        nps = {}
    for rname, rule in nps.items():
        where = f"network_policies.{rname}"
        rule = rule or {}
        endpoints = rule.get("endpoints") or []
        binaries = rule.get("binaries") or []
        if not endpoints:
            add("P011", "error", f"{where} has no endpoints")
        if not binaries:
            add("P012", "error", f"{where} has no binaries: every rule must name the programs it allows")
        for b in binaries:
            path = (b or {}).get("path", "") if isinstance(b, dict) else str(b)
            if not path.startswith("/"):
                add("P013", "error", f"{where} binary '{path}' must be an absolute path")
            if path in SHELL_BINARIES:
                add("P014", "error", f"{where} allows shell/interpreter launcher {path}: that allows any program")
        for i, ep in enumerate(endpoints):
            ep = ep or {}
            loc = f"{where}.endpoints[{i}]"
            host = str(ep.get("host", ""))
            if not host:
                add("P020", "error", f"{loc} has no host")
                continue
            if host == "*" or host.startswith("*") and host.count(".") < 2:
                add("P021", "error", f"{loc} host '{host}' is a wildcard over a whole domain or the internet")
            elif "*" in host:
                add("P022", "warn", f"{loc} host '{host}' uses a wildcard; prefer exact hosts")
            if _is_internal(host):
                add("P023", "error", f"{loc} host '{host}' is internal/private/metadata: agents must not reach the platform")
            if ep.get("enforcement") != "enforce":
                add("P024", "error", f"{loc} enforcement must be 'enforce' (got {ep.get('enforcement')!r})")
            if ep.get("protocol") != "rest":
                add("P025", "warn", f"{loc} is not L7-inspected (protocol: rest); method/path rules cannot apply")
            access = ep.get("access")
            if access is not None and access not in VALID_ACCESS:
                add("P026", "error", f"{loc} access '{access}' is not one of {sorted(VALID_ACCESS)}")
            if access == "full":
                add("P027", "error", f"{loc} access 'full' allows every method; use read-only or read-write")
            port = ep.get("port")
            if port not in (443, None):
                add("P028", "warn", f"{loc} port {port}: only 443 is expected for agent egress")
    return out


def lint_files(paths: Iterable[str | Path]) -> list[Finding]:
    findings: list[Finding] = []
    for p in paths:
        p = Path(p)
        try:
            doc = yaml.safe_load(p.read_text())
        except yaml.YAMLError as e:
            findings.append(Finding(str(p), "P000", "error", f"invalid YAML: {e}"))
            continue
        findings.extend(lint_policy(doc, str(p)))
    return findings
