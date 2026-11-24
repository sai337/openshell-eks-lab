# OpenShell lab: the plain-language guide

Everything about this project in simple words, from what it is to every component, flow, command and signal. The same content, with diagrams, is the bible page at `site/index.html` and the matching tab in the Study Bible.

## Start here: the whole idea in plain words

**The problem.** An AI agent runs code and calls the internet on your behalf. If a prompt injection hijacks it, it will try to read secrets, call your cloud metadata endpoint, upload data, or reach the Kubernetes API. A normal container lets it.

**What OpenShell does.** Every agent gets its own sandbox, and every network connection it opens goes to a guard (the *supervisor*) that checks a written rulebook (the *policy*) before anything leaves: which website, which port, which program is asking, and whether it may only read or also write. Secrets stay with the guard, never in the agent. Every decision is written to a logbook (OCSF events).

### Think of it as a guarded office

| OpenShell word           | Plain meaning                                                                        | Office version                          |
|--------------------------|--------------------------------------------------------------------------------------|-----------------------------------------|
| Gateway                  | Control plane: creates sandboxes, stores policies and credentials, authenticates you | Security office at reception            |
| Sandbox                  | One isolated place where one agent works                                             | A private office with no windows        |
| Workload pod             | The pod running the agent's image and processes                                      | The desk inside the office              |
| Supervisor               | Trusted process outside the agent's reach that checks every connection               | A guard at the office door              |
| Policy                   | YAML rulebook: files, programs, hosts, HTTP methods                                  | The guard's rulebook                    |
| Provider                 | A stored credential the supervisor adds to approved requests                         | The key cabinet only the guard can open |
| Landlock, seccomp        | Kernel features that lock files and system calls inside the sandbox                  | Locked drawers inside the office        |
| NetworkPolicy            | Kubernetes rule that the workload has no route out except the supervisor             | No windows, one door                    |
| Agent Sandbox controller | kubernetes-sigs controller that turns a Sandbox resource into pods                   | The building crew                       |
| OCSF events              | Structured allow/deny log lines (Open Cybersecurity Schema Framework)                | The guard's logbook                     |

## One request, every component

Steps 1-3 happen once when the sandbox is created. Steps 4-6 happen on every connection the agent opens.

*Diagram: open `site/index.html` (the bible page) for the drawing.*

**1. Ask for a sandbox**

`openshell sandbox create --name os-net-01 --from oslab-agent:dev --policy deny-all.yaml --detach -- sleep infinity`. The CLI talks to the gateway over mTLS (kind) or OIDC (EKS).

**2. Gateway records it**

Validates the policy, stores the sandbox record, and creates a `Sandbox` custom resource through its Kubernetes compute driver.

**3. Pods appear**

The Agent Sandbox controller builds the workload pod and the separate supervisor pod. OpenShell writes NetworkPolicies so the workload can talk only to its supervisor. Upstream design: the agent does not start until the supervisor confirms the fence.

**4. Agent opens a connection**

e.g. `curl https://pypi.org/simple/`. It cannot go straight out; the request travels to the supervisor, which learns the real program behind it (`/usr/bin/curl`).

**5. Rulebook says yes**

Host, port and program match a rule. With `protocol: rest` the supervisor opens the TLS and checks the method: `read-only` allows GET, HEAD, OPTIONS. It adds provider credentials if the rule allows, then connects.

**6. Or no**

Unknown host: connection refused. Allowed host, forbidden method (POST on read-only): HTTP 403 `policy_denied`. Either way an OCSF event records who, what, where and why.

## Nodes, pods and who creates what

### Nodes (EKS)

Two node groups from our Terraform: `system` (gateway, Agent Sandbox controller) and `agent-sandbox` (tainted and labelled, only sandboxes). Sandboxes are steered there with `--driver-config-json` (node selector + toleration, file `e2e/eks-driver-config.json`).

### Gateway

A StatefulSet in namespace `openshell` with its own volume (EBS on EKS), plus a one-off PKI job that makes the mTLS certificates.

### Per sandbox: two pods

In v0.1.9 each sandbox is a workload pod (the agent) and a supervisor pod (the guard), created by the Agent Sandbox controller from the gateway's Sandbox resource. Nothing is shared between sandboxes.

### Always on

A sandbox's pods run until you stop or delete it. There is no sleep and wake: 100 agents means 100 sandboxes running. That is the cost trade-off against Substrate.

### The fence needs a CNI that enforces NetworkPolicy

Calico on kind, VPC CNI with `enableNetworkPolicy=true` on EKS. Without it the workload could bypass the supervisor.

### Isolation strength

Plain containers plus Landlock, seccomp, non-root, no service-account token. Add a gVisor runtime class for a kernel boundary (strong walls + strict guard).

## Every component and what it can do

Lab facts from v0.1.9 runs; component roles also from upstream docs/about/architecture.mdx.

| Component                    | Runs as                                                                                         | Capabilities                                                                                                                                                                                                                                                                                                                  |
|------------------------------|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **openshell CLI**            | Your laptop / CI                                                                                | `gateway add/select`, `status`, `sandbox create/get/list/exec/connect/delete`, `policy set` (live update), `provider create`, `logs`. Gateways registered under `~/.config/openshell/gateways/<name>/`.                                                                                                                       |
| **Gateway**                  | StatefulSet (Helm chart `oci://ghcr.io/nvidia/openshell/helm-chart` 0.1.9, marked experimental) | Authenticates users (mTLS client certs; OIDC with `server.oidc.issuer/audience`). Stores sandboxes, policies and provider credentials. Validates policies before a sandbox starts. Creates sandboxes through the Kubernetes compute driver. Delivers policy and credentials to supervisors. SSH / exec tunnel into sandboxes. |
| **Agent Sandbox controller** | Deployment in `agent-sandbox-system` (kubernetes-sigs v1.0.3)                                   | Reconciles the `Sandbox` custom resource into pods. Required by OpenShell's Kubernetes driver.                                                                                                                                                                                                                                |
| **Supervisor**               | Pod per sandbox (trusted side)                                                                  | Checks every connection against the policy: OPA rules for host, port and binary; an L7 engine for `protocol: rest` (method and path). Resolves DNS for the agent. Adds provider credentials only to approved requests. Writes OCSF allow/deny events. Freezes the agent if its link drops (fail closed).                      |
| **Workload pod (sandbox)**   | Pod per sandbox (untrusted side)                                                                | Runs your image as one non-root user (uid 1500 in our image) with no capabilities. Landlock limits files, seccomp hands every network open to the supervisor. Identifies the real program making each request from `/proc`.                                                                                                   |
| **Policy**                   | YAML, stored in the gateway                                                                     | Filesystem read-only and read-write paths, Landlock mode, named network rules with endpoints (host, port, protocol, enforcement, access) and the binaries allowed to use them. Updated live with `openshell policy set`.                                                                                                      |
| **Providers**                | Records in the gateway                                                                          | Store an API key once; the supervisor injects it into requests to the matching endpoint. The agent sees a placeholder, never the key.                                                                                                                                                                                         |
| **NetworkPolicy + CNI**      | Kubernetes objects OpenShell creates                                                            | Workload can reach only its supervisor; nothing else in or out.                                                                                                                                                                                                                                                               |
| **Anonymous telemetry**      | Inside gateway and supervisors                                                                  | On by default upstream; our installs set `server.telemetryEnabled=false` and `OPENSHELL_TELEMETRY_ENABLED=false`.                                                                                                                                                                                                             |

## OpenShell vs gVisor vs Substrate

Different layers. gVisor is the walls, OpenShell is a guard at each door, Substrate is a hotel that puts idle guests to sleep.

|                     | NVIDIA OpenShell                                       | gVisor                                           | Agent Substrate                                                  |
|---------------------|--------------------------------------------------------|--------------------------------------------------|------------------------------------------------------------------|
| Question it answers | What may this agent do and talk to?                    | Can a hijacked agent break out onto the machine? | How do I run thousands of idle agents cheaply with their memory? |
| Network rules       | Per sandbox: host, port, program, HTTP method and path | None of its own                                  | Per actor: hostname and port                                     |
| Secrets             | Supervisor injects them                                | n/a                                              | Egress gateway injects them                                      |
| Sleep / wake        | No, always on                                          | Can checkpoint a process                         | Yes, about 150 ms resume                                         |
| Use when            | Each agent needs tight, auditable rules                | You need a kernel boundary under either          | Many mostly idle, stateful agents                                |

## Reading a policy, line by line

policies/research-readonly.yaml: the research agent may read the Python package index with curl, nothing else.

| Line                                                                | Meaning                                                                                                                                       |
|---------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| filesystem_policy.read_only: \[/bin, /usr, /lib, /proc, /etc, ...\] | The agent can read system files but never change them (FS-01, FS-03).                                                                         |
| read_write: \[/sandbox, /tmp, /dev/null\]                           | Its workspace. Files here live as long as the sandbox (FS-02).                                                                                |
| landlock.compatibility: best_effort                                 | Use Landlock if the node kernel supports it; do not fail on older kernels.                                                                    |
| network_policies.pypi_readonly                                      | One named rule. Anything not matched by a rule is denied.                                                                                     |
| host: pypi.org, port: 443                                           | Exact destination. files.pythonhosted.org is a second endpoint for downloads.                                                                 |
| protocol: rest                                                      | The supervisor opens the TLS and inspects each HTTP request (L7), not just the connection.                                                    |
| enforcement: enforce                                                | Block on violation (the alternative only logs).                                                                                               |
| access: read-only                                                   | GET, HEAD, OPTIONS only (NET-03 proves POST is refused). `read-write` adds writes; `full` allows everything and our linter rejects it (P027). |
| binaries: \[/usr/bin/curl\]                                         | Only curl may use this rule. `python3` calling pypi.org is denied (NET-09). Paths must be the real file, not a symlink.                       |

The three lab policies: `deny-all` (no network at all), `research-readonly` (above), `llm-gateway` (python3 may call your AI gateway, key injected by a provider). `oslab lint` checks every policy in CI before it can be used.

## The lab's "agent" and how the suite drives it

There is no long-running agent service in this lab. The sandbox image is the attacker's toolbox, and the harness plays a hijacked agent.

### Image

`sandbox-image/Dockerfile`: python:3.13-slim plus curl, user uid 1500. Built for linux/amd64 on EKS.

### Start

`--detach -- sleep infinity` keeps the sandbox Ready (a command that exits leaves it Completed). The harness waits for a canary command to work first.

### Attack

For each of the 18 cases, `openshell sandbox exec` runs a command (curl to metadata, write to /usr, POST to pypi.org...) and compares the result to the expected secure outcome. CLI failures retry 3 times and count as infra errors, not passes.

### Result

`evals/results/<date>-<target>/`: results.json, summary.md. Gate fails on any critical or high failure. Kind: 18/18, suite 39-42 s.

Sandbox names are prefixed `os` and kept at 19 characters or fewer (an upstream limit we hit). Cases are grouped by policy so one sandbox serves a group; POL-01 gets its own because it changes the policy live.

## Users, sessions and state

### What the gateway knows

Who called it (mTLS identity or OIDC user), each sandbox's name, ID, phase (Provisioning, Ready, Stopped, Completed, Error, Deleting), image, policy, attached providers and labels.

### What it does not

No end-user sessions, conversations or request history. Like Substrate, mapping a user or session to a sandbox is your app's job: one sandbox per agent, or per user for strict isolation, tagged with labels.

### Memory

No snapshots. Files under `/sandbox` stay while the sandbox exists; process memory is lost on restart. Context and history must be written to the workspace or to an external store the policy allows.

## Logs, metrics and traces

| Signal                                   | What exists                                                                                                                                                  | How to get it out                                                                                                                                                                                                        |
|------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Allow / deny events**                  | OCSF events from each supervisor: ALLOWED or DENIED, the program, the destination, the reason.                                                               | `openshell logs <sandbox> --since 10m --source sandbox`. The supervisor also writes them under `/var/log/` in its own pod and to stderr; ship pod logs with Fluent Bit to CloudWatch or OpenSearch for history and SIEM. |
| **Agent output**                         | Whatever the agent prints.                                                                                                                                   | `openshell sandbox exec` returns it; pod logs otherwise.                                                                                                                                                                 |
| **Gateway metrics**                      | Prometheus text format on a separate listener (`--metrics-port` / `OPENSHELL_METRICS_PORT`): API requests, database readiness, OCSF queue and drop counters. | Prometheus scrape, or ADOT to Amazon Managed Prometheus.                                                                                                                                                                 |
| **Traces, OCSF over OTLP, agent traces** | Gateway, drivers and supervisors export OTLP; supervisors can relay the agent's own traces without an egress rule.                                           | Configured in the gateway config (`[openshell.gateway.otlp]`, Helm `gatewayConfig`).                                                                                                                                     |

Metrics and OTLP settings are from upstream docs on main (Nov 2026). Confirm the flags exist in the 0.1.9 chart before relying on them. Our lab scripts install no collector; the suite's results.json is the record today.
