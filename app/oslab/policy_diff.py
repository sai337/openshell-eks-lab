"""G2 promotion gate: what does the candidate policy allow that the approved one did not?

Any widening (new host, stronger access, new binary, audit instead of enforce,
new writable path) blocks promotion unless the promotion PR carries approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ACCESS_RANK = {None: 1, "read-only": 1, "read-write": 2, "full": 3}


@dataclass(frozen=True)
class Change:
    kind: str
    detail: str
    widening: bool

    def __str__(self) -> str:
        return f"{'WIDEN ' if self.widening else 'narrow'} {self.kind:12} {self.detail}"


def _endpoints(doc: dict) -> dict[tuple[str, int], dict]:
    out = {}
    for rule in (doc.get("network_policies") or {}).values():
        bins = tuple(sorted((b or {}).get("path", "") for b in (rule or {}).get("binaries") or []))
        for ep in (rule or {}).get("endpoints") or []:
            out[(str(ep.get("host")), int(ep.get("port") or 443))] = {**ep, "_bins": bins}
    return out


def diff(old: dict, new: dict) -> list[Change]:
    changes: list[Change] = []
    o, n = _endpoints(old or {}), _endpoints(new or {})
    for key in sorted(n.keys() - o.keys()):
        changes.append(Change("host", f"+ {key[0]}:{key[1]} ({n[key].get('access', 'read-only')}, binaries {list(n[key]['_bins'])})", True))
    for key in sorted(o.keys() - n.keys()):
        changes.append(Change("host", f"- {key[0]}:{key[1]}", False))
    for key in sorted(o.keys() & n.keys()):
        a, b = o[key], n[key]
        if ACCESS_RANK.get(b.get("access"), 3) > ACCESS_RANK.get(a.get("access"), 3):
            changes.append(Change("access", f"{key[0]}: {a.get('access')} -> {b.get('access')}", True))
        elif ACCESS_RANK.get(b.get("access"), 3) < ACCESS_RANK.get(a.get("access"), 3):
            changes.append(Change("access", f"{key[0]}: {a.get('access')} -> {b.get('access')}", False))
        if a.get("enforcement") == "enforce" and b.get("enforcement") != "enforce":
            changes.append(Change("enforcement", f"{key[0]}: enforce -> {b.get('enforcement')}", True))
        added = sorted(set(b["_bins"]) - set(a["_bins"]))
        if added:
            changes.append(Change("binary", f"{key[0]}: + {', '.join(added)}", True))
    rw_old = set(((old or {}).get("filesystem_policy") or {}).get("read_write") or [])
    rw_new = set(((new or {}).get("filesystem_policy") or {}).get("read_write") or [])
    for p in sorted(rw_new - rw_old):
        changes.append(Change("filesystem", f"+ writable {p}", True))
    return changes


def diff_files(old: str | Path, new: str | Path) -> list[Change]:
    load = lambda p: yaml.safe_load(Path(p).read_text()) or {}  # noqa: E731
    return diff(load(old), load(new))
