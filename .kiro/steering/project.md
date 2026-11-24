---
inclusion: always
---
# openshell-eks-lab: working rules

Goal: deploy NVIDIA OpenShell on EKS with Terraform, run the 18-case hostile-agent suite, record
the results, tear down. Follow docs/DEPLOYMENT.md step by step; it is the source of truth.

Rules
- AWS: only the profile in `$AWS_PROFILE` (personal lab account). Never a company account.
- Region default `us-west-2`. Always finish with `terraform destroy` unless told to keep the cluster.
- Never write secrets, keys or account IDs into the repo. `.work/` stays untracked.
- Commits: author `sai337 <sai.devop@gmail.com>`, no co-author or tool attribution lines.
- Pinned versions live in `versions.env`; do not bump them without re-reading docs/SECURITY-VET.md.
- OpenShell telemetry must stay off (`server.telemetryEnabled=false`, `OPENSHELL_TELEMETRY_ENABLED=false`).

Definition of done
1. `make test` passes locally.
2. `evals/results/<date>-eks/summary.md` shows `Gate: PASS` with 18/18.
3. Sandbox pods ran on `workload=agent-sandbox` nodes; NET-07 passed (VPC CNI enforces NetworkPolicy).
4. Results folder committed; README scorecard row "EKS enterprise path" updated with the run date.
5. `terraform destroy` completed.

If a step fails, use the table at the end of docs/DEPLOYMENT.md and docs/RUNBOOK.md before
changing code. Record any fix in docs/RUNBOOK.md.

## Read first
- docs/GUIDE.md explains every component, flow, command and signal in plain words. Use it to explain results to the owner.
- docs/DEPLOYMENT.md is the exact EKS procedure. Personal lab AWS account only; destroy when done.
