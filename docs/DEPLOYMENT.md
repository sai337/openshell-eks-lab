# Deployment: EKS end to end from a laptop (or Kiro)

This is the run book for creating the cluster, installing OpenShell, running the 18-case
suite and tearing everything down. It works from any machine with AWS credentials
(a laptop, Kiro, or the `eks-e2e` workflow, which runs the same steps).

**Use a personal lab AWS account with a budget. Never a company account.**

## 0. Prerequisites (10 min)

| Tool | Version | Check |
|---|---|---|
| AWS CLI v2 + a profile for the lab account | any v2 | `aws sts get-caller-identity` |
| Terraform | ≥ 1.6 | `terraform version` |
| kubectl | ≥ 1.33 | `kubectl version --client` |
| Helm | ≥ 3.14 | `helm version` |
| Docker (running) | any; builds `linux/amd64` images | `docker info` |
| Python | ≥ 3.11 | `python3 --version` |

```bash
export AWS_PROFILE=<lab-profile>          # the only credential the scripts use
export AWS_REGION=us-west-2
git clone https://github.com/sai337/openshell-eks-lab && cd openshell-eks-lab
make install && make test                 # 38 unit tests + policy lint, no cloud
```

## 1. Provision the infrastructure (15-20 min)

```bash
cd infra/eks/terraform
terraform init
terraform apply -var "region=$AWS_REGION" -var "budget_email=<you@example.com>"
cd ../../..
aws eks update-kubeconfig --name "$(terraform -chdir=infra/eks/terraform output -raw cluster_name)" --region "$AWS_REGION"
kubectl get nodes -L workload               # expect 2 x workload=system, 1 x workload=agent-sandbox
```

Creates: VPC (3 AZs, private nodes, one NAT), EKS 1.34, node groups `system` and
`agent-sandbox` (tainted, IMDS hop limit 1), VPC CNI with `enableNetworkPolicy=true`,
EBS CSI through Pod Identity, ECR repo (immutable, scan on push), optional budget alarm.

## 2. Install the platform (5-8 min)

```bash
bash infra/eks/install.sh
```

In order: gp3 StorageClass → agent image built for `linux/amd64` and pushed to ECR (the digest
is saved in `.work/sandbox-image-ref`) → Agent Sandbox v1.0.3 → OpenShell chart 0.1.9 with
`values-eks.yaml` + `values-eks-ci.yaml` (TLS on, telemetry off, reached only through
`kubectl port-forward`) → OpenShell CLI v0.1.9 → gateway registered as `oslab-eks`.

Check:
```bash
kubectl -n openshell get pods                     # openshell-0 Running
kubectl get crd sandboxes.agents.x-k8s.io
openshell status                                  # gateway oslab-eks reachable
```

## 3. Test end to end (about 1 min)

```bash
make eks-test        # = TARGET=eks OSLAB_DRIVER_CONFIG=e2e/eks-driver-config.json OSLAB_SANDBOX_IMAGE=<ecr digest> e2e/run.sh
cat evals/results/*-eks/summary.md
```

Pass criteria: **Gate: PASS, 18/18**. Also confirm placement and enforcement:
```bash
kubectl -n openshell get pods -o wide | grep " os-"    # during the run: NODE must be an agent-sandbox node
kubectl get networkpolicy -A
```

Commit the results folder `evals/results/<date>-eks/` (author sai337).

## 4. Promotion demo (optional, 2 min)

```bash
oslab policy-diff policies/research-readonly.yaml policies/llm-gateway.yaml   # G2 FAIL: widening
oslab policy-diff policies/research-readonly.yaml policies/llm-gateway.yaml --approved-by "owner+security"
```
See [PROMOTION.md](PROMOTION.md).

## 5. Tear down (10-15 min). Do not skip.

```bash
helm uninstall openshell -n openshell || true
cd infra/eks/terraform && terraform destroy -var "region=$AWS_REGION"
```
Then check the console for leftover load balancers or EBS volumes (there should be none).

## If something fails

| Step | Symptom | Fix |
|---|---|---|
| 1 | `UnsupportedAvailabilityZone` or version error | pick another region, or `-var kubernetes_version=1.33` |
| 2 | gateway pod Pending | `kubectl -n openshell describe pod openshell-0`: StorageClass gp3 missing or EBS CSI not ready |
| 2 | `exec format error` in sandbox pods | image built for ARM; rebuild with `--platform linux/amd64` (install.sh does this) |
| 3 | NET-07 fails on EKS | vpc-cni addon is missing `enableNetworkPolicy=true` |
| 3 | every case ERROR | port-forward died: rerun `TARGET=eks bash e2e/up.sh` (idempotent) |

More in [RUNBOOK.md](RUNBOOK.md).
