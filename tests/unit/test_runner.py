import re
from pathlib import Path

import pytest

from oslab.cases import CaseError, load_cases
from oslab.executors import FakeExecutor
from oslab.report import to_markdown, write
from oslab.runner import run_suite

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals" / "datasets" / "security-cases.yaml"
POLICIES = ROOT / "policies"


def secure_sandbox(policy: str, cmd: str, state: dict) -> int:
    """A tiny model of a correctly configured OpenShell sandbox."""
    if cmd.startswith("command -v"):
        return 0
    allowed_hosts = {"pypi.org"} if policy == "research-readonly" else set()
    allowed_hosts |= {e.split(":")[0] for _, b, e in state["rules"] if b == "/usr/bin/curl"}
    if "policy_denied" in cmd:  # POST through an allowed host must come back as an L7 deny
        return 0 if "pypi.org" in allowed_hosts else 1
    if cmd.startswith("curl"):
        host = re.search(r"https?://([^/:]+)", cmd).group(1)
        return 0 if host in allowed_hosts else 1
    if cmd.startswith("python3 -c") and "urlopen" in cmd:
        return 1  # binary not in any rule
    secure_rc = {
        "timeout 8 bash": 1, "touch /usr/bin": 1, "echo ok >": 0, "echo '6.6.6.6": 1,
        "test ! -e": 0, 'test "$(id -u)"': 0, "python3 -c \"import os": 1, "! env": 0,
    }
    for prefix, rc in secure_rc.items():
        if cmd.startswith(prefix):
            return rc
    raise AssertionError(f"unmodelled command: {cmd}")


def leaky_sandbox(policy: str, cmd: str, state: dict) -> int:
    """Everything reachable, nothing enforced: what a missing CNI or bad policy looks like."""
    if "policy_denied" in cmd:
        return 1
    if cmd.startswith("test ! -e"):
        return 1  # token mounted
    return 0


def test_dataset_loads_and_is_well_formed():
    cases = load_cases(CASES)
    assert len(cases) >= 18
    assert {c.policy for c in cases} <= {p.stem for p in POLICIES.glob("*.yaml")}
    assert sum(c.severity == "critical" for c in cases) >= 8


def test_secure_sandbox_passes_the_gate():
    ex = FakeExecutor(secure_sandbox)
    summary = run_suite(ex, load_cases(CASES), POLICIES)
    assert summary["gate"] == "pass", [r for r in summary["results"] if r["status"] != "pass"]
    assert summary["counts"]["fail"] == 0
    assert summary["pass_rate"] == 1.0
    assert ex.sandboxes == {}, "every sandbox must be deleted"


def test_leaky_sandbox_fails_with_named_blockers():
    summary = run_suite(FakeExecutor(leaky_sandbox), load_cases(CASES), POLICIES)
    assert summary["gate"] == "fail"
    for cid in ("NET-01", "NET-05", "NET-07", "FS-01", "ID-01"):
        assert cid in summary["blocking_failures"]


def test_isolated_case_gets_own_sandbox_and_policy_update():
    ex = FakeExecutor(secure_sandbox)
    run_suite(ex, load_cases(CASES), POLICIES)
    creates = [e for e in ex.log if e[0] == "create"]
    assert len(creates) == 3  # deny-all, research-readonly, POL-01 alone
    assert any(e[0] == "policy_update" for e in ex.log)


def test_missing_binary_skips_not_fails():
    def no_python(policy, cmd, state):
        return 1 if cmd == "command -v python3 >/dev/null" else secure_sandbox(policy, cmd, state)

    summary = run_suite(FakeExecutor(no_python), load_cases(CASES), POLICIES)
    skipped = {r["id"] for r in summary["results"] if r["status"] == "skip"}
    assert skipped == {"NET-09", "ID-03"}
    assert summary["gate"] == "pass"


def test_create_failure_marks_group_error():
    class Broken(FakeExecutor):
        def create(self, name, policy_path):
            raise RuntimeError("gateway unreachable")

    summary = run_suite(Broken(secure_sandbox), load_cases(CASES), POLICIES)
    assert summary["counts"]["error"] == len(summary["results"])
    assert summary["gate"] == "fail"


def test_report_files(tmp_path):
    summary = run_suite(FakeExecutor(leaky_sandbox), load_cases(CASES), POLICIES)
    out = write(summary, tmp_path / "r")
    md = (out / "summary.md").read_text()
    assert "Gate: FAIL" in md and "NET-01" in md and "## Failures" in md
    assert (out / "results.json").stat().st_size > 100
    assert "Gate: PASS" in to_markdown(run_suite(FakeExecutor(secure_sandbox), load_cases(CASES), POLICIES))


@pytest.mark.parametrize(
    "body,msg",
    [
        ("cases: [{id: A, policy: p, severity: low, command: x, expect: success}]", "severity"),
        ("cases: [{id: A, policy: p, severity: high, command: x, expect: maybe}]", "expect"),
        ("cases: [{id: A, policy: p, severity: high, command: x, expect: success}, {id: A, policy: p, severity: high, command: x, expect: success}]", "duplicate"),
        ("cases: [{id: A, policy: p, severity: high, steps: [{policy_update: {rule_name: r, binary: /b, endpoint: 'h:443'}}]}]", "endpoint"),
    ],
)
def test_bad_datasets_rejected(tmp_path, body, msg):
    f = tmp_path / "c.yaml"
    f.write_text(body)
    with pytest.raises(CaseError, match=msg):
        load_cases(f)


def test_sandbox_names_fit_openshell_limit():
    from oslab.runner import MAX_SANDBOX_NAME, sandbox_name

    ex = FakeExecutor(secure_sandbox)
    run_suite(ex, load_cases(CASES), POLICIES)
    names = [e[1] for e in ex.log if e[0] == "create"]
    assert names and all(len(n) <= MAX_SANDBOX_NAME for n in names), names
    assert len({n for n in names}) == len(names)
    assert len(sandbox_name("os", "a-very-long-policy-name-here")) <= MAX_SANDBOX_NAME
