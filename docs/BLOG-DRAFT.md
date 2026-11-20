# Draft: "Don't trust the sandbox. Test it." Running hostile agents on OpenShell + EKS

**Problem.** Every agent platform now says "sandboxed". A security team needs evidence: which
escapes were tried, on which version, with what result, and does it still hold after the next upgrade.

**What I built.** A repo that treats sandbox safety like any other release gate:
- policies as code, linted against rules a security reviewer would write;
- 18 hostile-agent cases, from IMDS theft to raw-socket bypass to a POST through a read-only host;
- the same suite on kind (every push, nightly) and on EKS (create → test → destroy).

**Architecture.** (diagram from the README) The agent pod has no route out. The supervisor pod is
the only door, and it checks host, binary and HTTP method. NetworkPolicy closes the side door.

**Results (kind, first green run).** 18 of 18 cases passed on a live OpenShell 0.1.9 gateway with Calico: every
exfiltration path refused in milliseconds, a POST through a read-only host answered `policy_denied`, python could not
reuse curl's rule, and a live policy update opened pypi.org for GET only. EKS numbers: next.

**Lessons so far.**
1. The CNI is part of the sandbox. Without an enforcing CNI, a raw socket walks around the proxy.
   OpenShell says this in bold; the suite makes it a failing test (NET-07).
2. Allow-lists need two dimensions: host and binary. Otherwise any interpreter reuses curl's rule.
3. "Read-only" has to mean HTTP methods, which needs L7 inspection (`protocol: rest`).
4. Turn vendor telemetry off on day one, in the chart and the CLI.
5. The upstream chart is labelled experimental. Pin it, render it in CI, and run the suite nightly.
6. My first run showed 9 'passes' that were false: the sandbox had exited, so every command failed, which looked like
   being blocked. A security suite must tell "blocked" from "never ran". The runner now uses a readiness canary and
   scores CLI errors as errors.

**Next.** Provider-credential injection against a real AI gateway, OIDC with a real IdP in CI, and a
comparison run on Agent Substrate (see agent-substrate-lab).
