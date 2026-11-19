import glob
from pathlib import Path

import pytest

from oslab.policy_lint import lint_files, lint_policy

ROOT = Path(__file__).resolve().parents[2]
FS = {"read_only": ["/usr"], "read_write": ["/sandbox"]}


def rules(doc):
    return {f.rule for f in lint_policy(doc) if f.level == "error"}


def ep(**kw):
    base = {"host": "pypi.org", "port": 443, "protocol": "rest", "enforcement": "enforce", "access": "read-only"}
    base.update(kw)
    return base


def pol(endpoint=None, binaries=None, fs=FS):
    return {
        "version": 1,
        "filesystem_policy": fs,
        "network_policies": {"r": {"endpoints": [endpoint or ep()], "binaries": binaries or [{"path": "/usr/bin/curl"}]}},
    }


def test_repo_policies_are_clean():
    files = sorted(glob.glob(str(ROOT / "policies" / "*.yaml")))
    assert len(files) >= 3
    errors = [f for f in lint_files(files) if f.level == "error"]
    assert errors == [], errors


def test_good_policy_has_no_errors():
    assert rules(pol()) == set()


@pytest.mark.parametrize(
    "doc,rule",
    [
        ({"filesystem_policy": FS}, "P001"),
        ({"version": 1}, "P002"),
        (pol(fs={"read_write": ["/etc"]}), "P003"),
        (pol(fs={"read_write": ["/usr/local/bin"]}), "P003"),
        (pol(binaries=[{"path": "curl"}]), "P013"),
        (pol(binaries=[{"path": "/bin/bash"}]), "P014"),
        (pol(endpoint=ep(host="*")), "P021"),
        (pol(endpoint=ep(host="*.com")), "P021"),
        (pol(endpoint=ep(host="169.254.169.254")), "P023"),
        (pol(endpoint=ep(host="10.0.0.5")), "P023"),
        (pol(endpoint=ep(host="kubernetes.default.svc")), "P023"),
        (pol(endpoint=ep(host="openshell.openshell.svc.cluster.local")), "P023"),
        (pol(endpoint=ep(enforcement="audit")), "P024"),
        (pol(endpoint=ep(access="everything")), "P026"),
        (pol(endpoint=ep(access="full")), "P027"),
    ],
)
def test_each_rule_fires(doc, rule):
    assert rule in rules(doc)


def test_missing_binaries_and_endpoints():
    doc = {"version": 1, "filesystem_policy": FS, "network_policies": {"r": {}}}
    assert {"P011", "P012"} <= rules(doc)


def test_warnings_do_not_block():
    findings = lint_policy(pol(endpoint=ep(host="*.github.com", protocol="tcp", port=8443)))
    levels = {f.rule: f.level for f in findings}
    assert levels == {"P022": "warn", "P025": "warn", "P028": "warn"}


def test_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: [1\n")
    assert [f.rule for f in lint_files([bad])] == ["P000"]
