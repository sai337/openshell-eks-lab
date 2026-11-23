# LinkedIn

**One line**
I attacked my own AI agent sandbox 18 ways on Kubernetes with NVIDIA OpenShell. All 18 held, and the most useful finding was a test bug that had scored 9 attacks as "passed". Code and write-up: <article link>

**Longer variant**
"Sandboxed" is not an answer a security review accepts. So I wrote 18 attacks a hijacked AI agent would try (cloud metadata, the Kubernetes API, raw sockets, POSTs through read-only hosts, secrets, root) and ran them every night against NVIDIA OpenShell on Kubernetes.

18/18 held, in about 40 seconds per run. The lesson that surprised me: my first run reported 9 passes that never ran. A security suite has to tell "blocked" from "never happened".

Open source, with EKS Terraform and a policy-diff gate for promotions: <repo link>
#AIAgents #Kubernetes #PlatformEngineering #AISecurity
