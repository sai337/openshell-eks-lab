"""How the runner talks to sandboxes. The real one shells out to the
`openshell` CLI; the fake one lets unit tests run without a cluster."""
from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class ExecResult:
    rc: int
    output: str
    seconds: float


class Executor(Protocol):
    def create(self, name: str, policy_path: str) -> None: ...
    def exec(self, name: str, command: str) -> ExecResult: ...
    def policy_update(self, name: str, rule_name: str, binary: str, endpoint: str) -> None: ...
    def delete(self, name: str) -> None: ...


class OpenShellExecutor:
    """Drives a live OpenShell gateway through the CLI.

    The CLI must already be registered with a gateway (OPENSHELL_GATEWAY or the
    active gateway). The sandbox image comes from OSLAB_SANDBOX_IMAGE.
    """

    def __init__(self, cli: str | None = None, image: str | None = None, timeout: int = 300):
        self.cli = cli or os.environ.get("OPENSHELL_BIN", "openshell")
        self.image = image if image is not None else os.environ.get("OSLAB_SANDBOX_IMAGE", "")
        self.timeout = timeout

    def _run(self, args: list[str], check: bool = True, timeout: int | None = None) -> ExecResult:
        t0 = time.monotonic()
        env = {**os.environ, "OPENSHELL_TELEMETRY_ENABLED": "false"}
        p = subprocess.run(
            [self.cli, *args], capture_output=True, text=True, timeout=timeout or self.timeout, env=env
        )
        res = ExecResult(p.returncode, (p.stdout + p.stderr)[-4000:], time.monotonic() - t0)
        if check and p.returncode != 0:
            raise RuntimeError(f"{shlex.join([self.cli, *args])} failed ({p.returncode}): {res.output}")
        return res

    def create(self, name: str, policy_path: str) -> None:
        args = ["sandbox", "create", "--name", name, "--policy", policy_path, "--no-auto-providers", "--no-tty"]
        if self.image:
            args += ["--from", self.image]
        driver_cfg = os.environ.get("OSLAB_DRIVER_CONFIG", "")
        if driver_cfg:  # path to a JSON file, e.g. e2e/eks-driver-config.json
            with open(driver_cfg) as fh:
                args += ["--driver-config-json", fh.read().strip()]
        self._run([*args, "--", "true"], timeout=600)

    def exec(self, name: str, command: str) -> ExecResult:
        try:
            return self._run(
                ["sandbox", "exec", "-n", name, "--no-login-shell", "--", "/bin/bash", "-c", command],
                check=False,
                timeout=90,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(124, "timed out", 90.0)

    def policy_update(self, name: str, rule_name: str, binary: str, endpoint: str) -> None:
        self._run(
            ["policy", "update", name, "--rule-name", rule_name, "--binary", binary,
             "--add-endpoint", endpoint, "--wait"],
            timeout=180,
        )

    def delete(self, name: str) -> None:
        self._run(["sandbox", "delete", name], check=False, timeout=180)


class FakeExecutor:
    """Scripted executor for tests. `behaviour(policy, command, state)` returns an rc."""

    def __init__(self, behaviour: Callable[[str, str, dict], int]):
        self.behaviour = behaviour
        self.sandboxes: dict[str, dict] = {}
        self.log: list[tuple] = []

    def create(self, name: str, policy_path: str) -> None:
        self.sandboxes[name] = {"policy": os.path.basename(policy_path).removesuffix(".yaml"), "rules": []}
        self.log.append(("create", name, policy_path))

    def exec(self, name: str, command: str) -> ExecResult:
        sb = self.sandboxes[name]
        self.log.append(("exec", name, command))
        return ExecResult(self.behaviour(sb["policy"], command, sb), "", 0.01)

    def policy_update(self, name: str, rule_name: str, binary: str, endpoint: str) -> None:
        self.sandboxes[name]["rules"].append((rule_name, binary, endpoint))
        self.log.append(("policy_update", name, rule_name))

    def delete(self, name: str) -> None:
        self.sandboxes.pop(name, None)
        self.log.append(("delete", name))
