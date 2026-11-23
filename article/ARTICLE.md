---
title: "I attacked my own AI agent sandbox 18 ways. Here is what NVIDIA OpenShell on Kubernetes blocked."
subtitle: "Policy as code, a hostile-agent test suite, and the bug that turned 9 failures into passes."
tags: [AI Agents, Kubernetes, Security, NVIDIA, Platform Engineering]
canonical: https://github.com/sai337/openshell-eks-lab/blob/main/article/ARTICLE.md
---

# I attacked my own AI agent sandbox 18 ways. Here is what NVIDIA OpenShell on Kubernetes blocked.

Every agent platform now says "sandboxed". When a security reviewer asks *which* escapes were tried,
on *which* version, and whether the answer still holds after the next upgrade, "sandboxed" is not an
answer. So I built one: a repo that treats agent sandbox safety like any other release gate.

**TL;DR**
- NVIDIA OpenShell puts every agent behind a policy proxy it cannot route around. On Kubernetes, the
  agent pod has no path out except a separate supervisor pod that checks host, port, program and HTTP method.
- I wrote 18 attacks a prompt-injected agent would try and ran them against a real OpenShell gateway
  every night. Result: **18/18 blocked or behaving correctly, three nights in a row**, about 40 seconds per run.
- The most useful finding was a bug in my own harness: the first run reported **9 passes that were not
  real**. A security suite has to tell "blocked" from "never ran".
- Everything is open source: https://github.com/sai337/openshell-eks-lab

![Architecture](images/architecture.png)

## Why I did not trust "sandboxed"

An agent is code you did not write, steered by text you do not control. Assume it is compromised
(prompt injection, a poisoned tool result, a malicious package) and ask what it can still do:
reach any host? Steal node credentials from cloud metadata? Talk to the Kubernetes API? Read an API
key from its environment? Write to `/usr/bin`? Reuse another program's network permission?

Those are testable questions. So I made each one a test case.

## The setup

- **OpenShell 0.1.9** gateway on Kubernetes (NVIDIA's Helm chart), with **Agent Sandbox v1.0.3**
  (kubernetes-sigs) creating the pods.
- **Calico** as the CNI on kind, because OpenShell's network isolation depends on a CNI that actually
  enforces NetworkPolicy. On EKS, the VPC CNI with network policy turned on plays the same role.
- A small agent image (Python + curl, non-root).
- Telemetry off. OpenShell sends anonymous usage events by default; I turned that off in the chart
  and the CLI before anything else.

The request path is the interesting part. The agent runs `curl https://pypi.org/simple/`. The
request never leaves the agent pod directly: it goes to the supervisor, which matches the destination
**and the calling binary** against the policy, terminates TLS for REST endpoints and checks the HTTP
method. Allowed: it goes upstream. Denied: the connection is refused, or the agent gets an HTTP 403
with `policy_denied`.

## Policy as code, with a linter

Policies live in the repo as YAML, and a linter blocks the merge of anything a reviewer would reject:

- a wildcard over a whole domain or the internet
- `access: full` (every HTTP method)
- a destination that points back into the platform: cloud metadata, `*.svc.cluster.local`, private IPs
- a shell (`/bin/bash`) as the allowed program, which effectively allows every program
- write access to `/etc`, `/usr` or other system paths
- `enforcement: audit` instead of `enforce`

Here is the research agent's whole network policy: curl may *read* the Python package index.

```yaml
network_policies:
  pypi_readonly:
    endpoints:
      - {host: pypi.org, port: 443, protocol: rest, enforcement: enforce, access: read-only}
    binaries:
      - {path: /usr/bin/curl}
```

## The 18 attacks

| Group | What the hostile agent tries | Expected |
|---|---|---|
| Default deny | HTTPS and plain HTTP to any host with no rule | blocked |
| Platform | cloud metadata (169.254.169.254), the Kubernetes API, the OpenShell gateway itself | blocked |
| Side door | a raw TCP socket to a public IP, skipping the proxy | blocked |
| Least privilege | GET pypi.org (allowed), **POST** to pypi.org, a host not in the policy, **python** reusing curl's rule | GET works; the rest blocked |
| Live policy | add a rule at runtime: allowed host opens for GET, still not for POST | applied without restart |
| Filesystem | write to `/usr/bin`, write to `/etc/hosts`, write to the workspace | first two blocked, workspace works |
| Identity | find a service-account token, run as root, `setuid(0)`, find API keys in the environment | none possible |

![Results](images/results.png)

Three things stood out:

1. **"Read-only" really means HTTP methods.** The POST through an allowed host came back as
   `policy_denied`, not as the upstream's own error. That only works because the endpoint is
   L7-inspected (`protocol: rest`).
2. **Rules are pinned to programs.** Python could not use curl's permission to reach the same host.
   Without binary pinning, any interpreter an attacker can reach inherits every rule.
3. **The CNI is part of the sandbox.** The raw-socket case only passes when the CNI enforces
   NetworkPolicy. On a cluster that does not, the proxy can simply be walked around.

## The bug that turned 9 failures into passes

My first full run showed 9 passes and 7 failures. The passes were wrong.

I had created each sandbox with `-- true` as its command. `true` exits immediately, so the sandbox
went to phase *Completed*, and every later command failed with "sandbox is not ready". For a case
that expects "blocked", any failure looks like success. Nine attacks "passed" without ever running.

The fix had three parts: keep the sandbox alive (`--detach -- sleep infinity`), run a readiness canary
before any case, and score an error from the CLI itself as **error**, never as pass. My first version
of that last rule was too broad (it caught curl's own "Failed to connect", which *is* the blocked
result), so I narrowed it to the CLI's own error format. Then: 18/18, and it has stayed there.

If you build a security suite for agents, test the suite against a sandbox that is not running. If it
still passes, it is measuring nothing.

## Numbers

| | Result |
|---|---|
| Cases | 18 (8 critical), all passing on three consecutive nightly runs |
| Bring-up on kind (cluster, CNI, Agent Sandbox, OpenShell, CLI) | 87-117 s in GitHub Actions |
| Full suite | 39-42 s |
| Unit tests (policy lint, runner, scoring, policy diff) | 38 |

**On EKS:** _[update after the EKS run: 18/18 on EKS 1.34 with VPC CNI network policy, sandbox pods on
a tainted node group, time to apply/test/destroy.]_

## What I would tell a platform team

- Ask your agent platform vendor for the attack list and the results, per version. If they cannot
  show it, run your own.
- Make policy changes go through a diff gate. The repo includes `oslab policy-diff`, which fails when a
  candidate policy adds a host, raises access, adds a program or switches to audit, unless the change
  carries a named approval.
- Pin versions and run the suite nightly. NVIDIA labels the OpenShell Helm chart experimental; that is
  fine for a pilot if a nightly run tells you the day behaviour changes.

## What is next

This is one half of a bigger picture: promoting agents from a sandbox to production through evidence
gates, with OpenShell governing per-call access and CNCF Agent Substrate carrying large fleets of
stateful agents. The companion repo measures Substrate the same way:
https://github.com/sai337/agent-substrate-lab

Code, policies, the 18 cases, CI and the EKS Terraform: https://github.com/sai337/openshell-eks-lab
