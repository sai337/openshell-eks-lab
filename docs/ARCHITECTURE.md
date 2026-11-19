# Architecture

Upstream facts below come from the OpenShell v0.1.9 docs and chart (links at the end).

## Components
- **Gateway** (StatefulSet in `openshell`): API for the CLI and SDKs, policy store, PKI bootstrap job,
  Kubernetes compute driver. It creates a `Sandbox` resource per sandbox.
- **Agent Sandbox controller** (`agent-sandbox-system`): kubernetes-sigs project that turns a
  `Sandbox` resource into the workload pod.
- **Supervisor pod**: trusted, separately scheduled. Runs the policy proxy (OPA for connections,
  L7 engine for REST), holds provider credentials, writes OCSF policy logs.
- **Workload pod**: the agent image. Landlock limits the filesystem. It has no direct route out.
- **NetworkPolicy**: lets only the supervisor reach the workload's boundary port and blocks new
  workload-initiated connections. OpenShell creates the policies; the CNI must enforce them.

## Request flow (agent calls pypi.org)
1. The agent runs `curl https://pypi.org/simple/`.
2. The request goes to the supervisor over the established boundary channel.
3. The supervisor matches host + port + binary (`/usr/bin/curl`) to a rule, terminates TLS
   (`protocol: rest`) and checks the method against `access: read-only`.
4. Allowed: the supervisor opens the upstream connection. Denied: CONNECT is refused, or an HTTP 403
   with `policy_denied` comes back; either way an OCSF event is logged.

## Trust boundaries
| Boundary | Trusted side | Untrusted side | Control |
|---|---|---|---|
| Workload ↔ network | supervisor | agent code | proxy + NetworkPolicy |
| Workload ↔ secrets | supervisor | agent code | credentials mount only in the supervisor |
| Workload ↔ node | kubelet / node | agent code | non-root, Landlock, seccomp, no SA token, IMDS hop limit (EKS) |
| User ↔ gateway | gateway | caller | TLS + OIDC (EKS), port-forward only (kind) |

## EKS layout
Private subnets across 3 AZs, one NAT (lab), node groups `system` (gateway, controllers) and
`agent-sandbox` (tainted, labelled; sandboxes placed with `--driver-config-json`). VPC CNI runs with
`enableNetworkPolicy=true`. EBS CSI via Pod Identity for the gateway volume. ECR for the agent image.

## Sources
- OpenShell on Kubernetes: https://docs.nvidia.com/openshell/latest/kubernetes/setup
- Chart values (v0.1.9): https://github.com/NVIDIA/OpenShell/blob/v0.1.9/deploy/helm/openshell/values.yaml
- Policy quickstart: https://github.com/NVIDIA/OpenShell/tree/v0.1.9/examples/sandbox-policy-quickstart
- Agent Sandbox: https://github.com/kubernetes-sigs/agent-sandbox
- EKS network policies: https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html
