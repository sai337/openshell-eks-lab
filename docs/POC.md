# POC on kind

```bash
make install && make test
make poc     # 5-8 minutes: kind, Calico, Agent Sandbox, OpenShell 0.1.9, CLI, port-forward on 127.0.0.1:18080
make e2e     # 3-6 minutes: 3 sandboxes (deny-all, research-readonly, POL-01), 18 cases
cat evals/results/*-kind/summary.md
make poc-down
```

What `make poc` does, in order: creates kind with the default CNI disabled; installs Calico with the
pod CIDR patched to 10.244.0.0/16; builds `oslab-agent:dev` and loads it into kind; installs Agent
Sandbox v1.0.3 and waits for the CRD; installs the OpenShell chart with `values-kind.yaml`
(plaintext, anonymous, local only, telemetry off); installs the CLI from the pinned tag's installer;
port-forwards the gateway and registers it as `oslab-kind`.

Try one case by hand:
```bash
openshell sandbox create --name try --from oslab-agent:dev --policy policies/research-readonly.yaml --no-auto-providers --no-tty --detach -- sleep infinity
openshell sandbox exec -n try --no-login-shell -- curl -s -X POST https://pypi.org/simple/   # policy_denied
openshell logs try --since 5m --source sandbox
openshell sandbox delete try
```
