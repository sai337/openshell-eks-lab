# Runbook

| Symptom | Check | Fix |
|---|---|---|
| `helm install` fails on preflight | `kubectl get crd sandboxes.agents.x-k8s.io` | install Agent Sandbox first (`e2e/up.sh` does) |
| Gateway pod Pending | `kubectl -n openshell describe pod openshell-0` | no default StorageClass; on EKS run `infra/eks/install.sh` (creates gp3) |
| `sandbox create` hangs | `kubectl get sandboxes -A`, controller logs | image not loaded (`kind load docker-image oslab-agent:dev`) or wrong pull policy |
| NET-07 fails (raw TCP got out) | `kubectl get networkpolicy -n openshell` | the CNI is not enforcing: kind needs Calico; EKS needs `enableNetworkPolicy=true` on vpc-cni |
| NET-02 fails (allowed GET denied) | `openshell logs <sandbox> --source sandbox` | binary path differs in your image (`command -v curl`), update the rule |
| NET-03 fails | look for `policy_denied` in the response | endpoint is not `protocol: rest`, so methods are not inspected |
| `openshell status` cannot connect | `.work/port-forward.log` | restart the port-forward; check `~/.config/openshell/active_gateway` |
| Suite errors on every case | the `note` field in results.json | gateway unreachable or CLI not registered |

Deny logs: `openshell logs <sandbox> --since 10m --source sandbox` (OCSF lines with ALLOWED/DENIED,
the binary, the destination and the reason).
