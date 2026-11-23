import copy
from pathlib import Path

import yaml

from oslab.cli import main
from oslab.policy_diff import diff

ROOT = Path(__file__).resolve().parents[2]
BASE = yaml.safe_load((ROOT / "policies/research-readonly.yaml").read_text())


def kinds(changes, widening=True):
    return {c.kind for c in changes if c.widening is widening}


def test_identical_policies_have_no_changes():
    assert diff(BASE, copy.deepcopy(BASE)) == []


def test_each_widening_is_caught():
    new = copy.deepcopy(BASE)
    rule = new["network_policies"]["pypi_readonly"]
    rule["endpoints"][0]["access"] = "read-write"
    rule["endpoints"][1]["enforcement"] = "audit"
    rule["endpoints"].append({"host": "api.github.com", "port": 443, "protocol": "rest", "enforcement": "enforce", "access": "read-only"})
    rule["binaries"].append({"path": "/usr/local/bin/python3"})
    new["filesystem_policy"]["read_write"].append("/opt")
    assert kinds(diff(BASE, new)) == {"host", "access", "enforcement", "binary", "filesystem"}


def test_narrowing_is_not_widening():
    new = copy.deepcopy(BASE)
    new["network_policies"]["pypi_readonly"]["endpoints"].pop()
    changes = diff(BASE, new)
    assert changes and not kinds(changes)


def test_cli_gate(tmp_path):
    new = copy.deepcopy(BASE)
    new["network_policies"]["pypi_readonly"]["endpoints"][0]["access"] = "full"
    cand = tmp_path / "cand.yaml"
    cand.write_text(yaml.safe_dump(new))
    approved = str(ROOT / "policies/research-readonly.yaml")
    assert main(["policy-diff", approved, str(cand)]) == 1
    assert main(["policy-diff", approved, str(cand), "--approved-by", "owner+security"]) == 0
    assert main(["policy-diff", approved, approved]) == 0
