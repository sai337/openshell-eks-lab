# Plan

## Goal
Show, with evidence, that NVIDIA OpenShell on Kubernetes can host untrusted agents safely, and give a
platform team a repeatable way to keep proving it as policies and versions change.

## What it proves
- Default-deny egress holds, including against direct sockets (needs an enforcing CNI).
- Least-privilege L7 rules work: right host, right binary, right HTTP methods only.
- The workload has no platform credentials (no SA token, no IMDS, no API keys in env).
- Filesystem and identity limits hold (read-only system paths, non-root, no setuid).
- Policy changes apply live and stay as narrow as asked.

## Scope
In: gateway on Kubernetes (Helm), Agent Sandbox CRDs, policies, the hostile-agent suite, kind POC,
EKS pilot with Terraform, CI gates, docs.
Out (next): provider-credential injection tests against a real LLM gateway, OIDC with a real IdP in CI,
GPU sandboxes, multi-tenant managed workspaces, the OpenShell VM driver.

## POC vs enterprise
| | POC (kind) | Enterprise (EKS) |
|---|---|---|
| CNI enforcement | Calico v3.30.3 | VPC CNI with `enableNetworkPolicy` |
| Gateway transport | plaintext over port-forward | TLS, chart PKI, OIDC for people |
| Sandbox placement | any node | tainted `agent-sandbox` node group, IMDS hop limit 1 |
| Agent image | built locally, `kind load` | ECR, immutable tags, scan on push, pinned by digest |
| State | default PVC | gp3 encrypted EBS |
| Lifecycle | `make poc` / `make poc-down` | `eks-e2e`: apply → test → destroy |

## Risks
- Upstream chart is experimental; values can change between releases. Mitigation: pin, render in CI, nightly e2e.
- kind images come from ghcr.io and Docker Hub; rate limits can flake CI. Mitigation: GHCR login, retry.
- A green suite proves these 18 behaviours only. It is not a full penetration test.

## Milestones
1. M1 repo, policies, lint, suite, unit tests (done)
2. M2 green `e2e-kind` run with results committed
3. M3 green `eks-e2e` run in a lab account
4. M4 provider-credential cases + blog post with measured numbers
