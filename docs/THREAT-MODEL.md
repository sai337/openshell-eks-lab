# Threat model

Assumption: the agent is compromised (prompt injection, malicious tool output or a poisoned package)
and actively tries to escape, steal and exfiltrate.

| # | Threat | Control | Case |
|---|---|---|---|
| T1 | Exfiltrate data to any host | default-deny proxy | NET-01, NET-11 |
| T2 | Exfiltrate through an allowed host | L7 method rules (`read-only`) | NET-03, POL-01 |
| T3 | Reach an attacker host while others are allowed | exact-host rules, lint P021/P022 | NET-04 |
| T4 | Reuse another program's rule | binary pinning, lint P014 | NET-09 |
| T5 | Skip the proxy with a raw socket | NetworkPolicy enforced by the CNI | NET-07 |
| T6 | Steal node credentials from IMDS | proxy deny + IMDS hop limit 1 on EKS + lint P023 | NET-05 |
| T7 | Attack the cluster API or the gateway | proxy deny, no SA token, NetworkPolicy | NET-06, NET-08, ID-01 |
| T8 | Read API keys from the environment | credentials stay in the supervisor | SEC-01 |
| T9 | Persist or tamper with system files | Landlock read-only paths, lint P003 | FS-01, FS-03 |
| T10 | Escalate to root | non-root image, no setuid | ID-02, ID-03 |
| T11 | Risky policy merged by a person | `oslab lint` blocks the merge | ci |
| T12 | Version drift weakens behaviour | pinned versions + nightly e2e | e2e-kind |
| T13 | Vendor telemetry leaks usage data | telemetry off in chart + CLI | A9 |

Not covered yet: DNS tunnelling, side channels between sandboxes on one node, kernel exploits
(add gVisor/Kata/Nitro runtime class), supply chain of the agent's own dependencies.
