# Acceptance checks

Each check maps to a test that runs in CI.

| # | Done when | Proven by |
|---|---|---|
| A1 | Every policy in `policies/` passes the repo's safety rules | `oslab lint` in `ci` |
| A2 | Each lint rule fires on a bad policy and not on a good one | `tests/unit/test_policy_lint.py` |
| A3 | The suite passes against a correctly configured sandbox model and fails, naming blockers, against a leaky one | `tests/unit/test_runner.py` |
| A4 | Missing tools in an image skip a case instead of failing it; gateway outages error the run | `tests/unit/test_runner.py` |
| A5 | The pinned chart renders with kind and EKS values; EKS values never allow anonymous users | `ci` / manifests |
| A6 | Terraform is formatted and validates | `ci` / manifests |
| A7 | All 18 cases pass on kind with Calico (gate = pass) | `e2e-kind` |
| A8 | All 18 cases pass on EKS with VPC CNI NetworkPolicy, then the cluster is destroyed | `eks-e2e` |
| A9 | No OpenShell telemetry leaves any environment | `server.telemetryEnabled=false` in both value sets + CLI env |
