"""Writes suite results as JSON (for machines) and Markdown (for people)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ICON = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP", "error": "ERROR"}


def to_markdown(summary: dict, title: str = "Sandbox security suite") -> str:
    c = summary["counts"]
    when = datetime.fromtimestamp(summary["finished_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = summary.get("meta", {})
    lines = [
        f"# {title}",
        "",
        f"Run: {when}" + (f" · target: `{meta['target']}`" if meta.get("target") else ""),
        "",
        f"**Gate: {summary['gate'].upper()}** · pass {c['pass']} · fail {c['fail']} · error {c['error']} · skip {c['skip']} · pass rate {summary['pass_rate']:.0%}",
        "",
    ]
    if summary["blocking_failures"]:
        lines += [f"Blocking (critical/high) failures: {', '.join(summary['blocking_failures'])}", ""]
    lines += ["| Case | Result | Severity | Policy | What it checks |", "|---|---|---|---|---|"]
    for r in summary["results"]:
        lines.append(f"| {r['id']} | {ICON[r['status']]} | {r['severity']} | `{r['policy']}` | {r['title']} |")
    failed = [r for r in summary["results"] if r["status"] in ("fail", "error")]
    if failed:
        lines += ["", "## Failures", ""]
        for r in failed:
            lines.append(f"### {r['id']} {r['title']}")
            if r.get("note"):
                lines.append(r["note"])
            for s in r["steps"]:
                if not s["ok"]:
                    lines += [f"- `{s['command'] or s['action']}` expected {s['expect']}, rc={s['rc']}", "", "```", (s["output"] or "").strip()[-400:], "```"]
    return "\n".join(lines) + "\n"


def write(summary: dict, out_dir: str | Path, title: str = "Sandbox security suite") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(summary, indent=2))
    (out / "summary.md").write_text(to_markdown(summary, title))
    return out
