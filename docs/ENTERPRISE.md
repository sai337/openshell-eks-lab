# Enterprise path (EKS)

## One-time setup (personal lab account, about 15 minutes)
1. Deploy the OIDC bootstrap:
   ```bash
   aws cloudformation deploy --template-file infra/eks/bootstrap/github-oidc.yaml \
     --stack-name oslab-github-oidc --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides Repo=sai337/openshell-eks-lab
   ```
2. In the repo settings, create the environment `eks` with yourself as a required reviewer.
3. Set repo variables `AWS_ROLE_ARN` (stack output) and `AWS_REGION` (for example `us-west-2`).
4. Optional: an environment secret `BUDGET_EMAIL` turns on the monthly budget alarm.

## Run
Actions → `eks-e2e` → Run workflow. It applies Terraform, installs Agent Sandbox and OpenShell with
`values-eks.yaml`, pushes the agent image to ECR, runs the 18 cases on tainted sandbox nodes, uploads
the results and destroys everything. Expect about 35–45 minutes. Cost is the cluster-hour plus
NAT and three small nodes for under an hour.

## Production changes beyond the pilot
| Area | Pilot | Production |
|---|---|---|
| People auth | none (port-forward only, `values-eks-ci.yaml`) | `server.oidc.issuer` = your IdP; delete `values-eks-ci.yaml` |
| Gateway exposure | port-forward | Gateway API ingress with TLS; see the OpenShell ingress guide |
| Credentials | none in tests | OpenShell providers backed by Kubernetes Secrets or Vault, injected in the supervisor only |
| LLM egress | n/a | `policies/llm-gateway.yaml` pointing at your AI gateway, `read-write` only to that host |
| Isolation | runc + Landlock | add `runtime_class_name` (gVisor, Kata or Nitro) in the driver config |
| State | single gateway, local PVC | external PostgreSQL (`server.externalDbSecret`), HA per upstream guide |
| Logs | pod logs | ship supervisor OCSF JSONL to the SIEM |
| Terraform | local state, AdministratorAccess role | S3 backend with locking, least-privilege deploy role |

## Credentials
The sandbox must never hold an API key. Create a provider (`openshell provider create`), attach it to
the sandbox, and the supervisor injects the credential into approved requests. Case SEC-01 checks the
workload environment stays clean.
