# Third-party vet

Checked 2026-11-19 in a throwaway workspace. Nothing was installed or run there; only source was read
and scanned. These projects are too large (2,000 to 14,000 files) to read line by line, so the vet is
provenance + pinning + a targeted scan + containment, and the residual risk is stated.

| Component | Source | Pin | Verdict |
|---|---|---|---|
| OpenShell CLI, gateway, chart | github.com/NVIDIA/OpenShell (vendor org, Apache-2.0, DCO, CodeQL in CI) | v0.1.9 = `ce58cf8e9b953281352d98a637e41616295b1318`, chart 0.1.9 | AMBER: use with telemetry off |
| Agent Sandbox | github.com/kubernetes-sigs/agent-sandbox (Kubernetes SIG Apps) | v1.0.3, commit `527d9346fe1d237dea5c003f3c720531c7bab1df` | GREEN |
| Calico | projectcalico/calico manifest | v3.30.3 (same pin as OpenShell CI) | GREEN |
| python:3.13-slim base | Docker official image | tag; pin by digest in your registry | GREEN |

## Findings
| Where | What | Action |
|---|---|---|
| `crates/openshell-core/src/telemetry.rs:27` | Anonymous telemetry to `events.telemetry.data.nvidia.com`, on by default | `server.telemetryEnabled=false` (chart), `OPENSHELL_TELEMETRY_ENABLED=false` (CLI and runner) |
| `install.sh` | Downloads release assets from GitHub and checks them against the release's SHA-256 checksum file | fetched from the pinned tag, never `main` |
| docs, examples, manifests | Hidden-Unicode scan of every `.yaml/.md/.mdx/.sh` under deploy, examples, k8s | 0 findings |

## Containment
- The POC runs only on throwaway kind clusters (laptop or GitHub runners) with no personal or company secrets.
- The EKS run uses a separate lab account through short-lived OIDC credentials and is destroyed after the test.
- No conversation content, memory or company data is passed to any of these tools.

## Residual risk
Compiled binaries and container images were not rebuilt from source; they are trusted on the vendor's
release pipeline. Re-vet on every version bump as a diff of the pinned SHAs.
