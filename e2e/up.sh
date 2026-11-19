#!/usr/bin/env bash
# Bring up the POC: kind + Calico (enforces NetworkPolicy) + Agent Sandbox +
# OpenShell gateway, then register the CLI. Works on a laptop and in CI.
#   TARGET=kind (default) creates the cluster. TARGET=eks uses the current
#   kubectl context (an EKS cluster from infra/eks/terraform) and skips kind/Calico.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/versions.env"
TARGET="${TARGET:-kind}"
CLUSTER="${KIND_CLUSTER_NAME:-oslab}"
NS=openshell
WORK="${OSLAB_WORK:-$ROOT/.work}"
mkdir -p "$WORK"
log() { printf '\n==> %s\n' "$*"; }
need() { command -v "$1" >/dev/null || { echo "missing tool: $1" >&2; exit 2; }; }
for t in kubectl helm docker curl; do need "$t"; done

if [ "$TARGET" = kind ]; then
  need kind
  log "kind cluster '$CLUSTER' with the default CNI disabled"
  if ! kind get clusters | grep -qx "$CLUSTER"; then
    kind create cluster --name "$CLUSTER" --config "$ROOT/e2e/kind-config.yaml" --wait 0s
  fi
  kubectl config use-context "kind-$CLUSTER"

  log "Calico $CALICO_VERSION (OpenShell requires a CNI that enforces egress NetworkPolicy)"
  curl -fsSL "https://raw.githubusercontent.com/projectcalico/calico/$CALICO_VERSION/manifests/calico.yaml" \
    | sed 's@192.168.0.0/16@10.244.0.0/16@g' > "$WORK/calico.yaml"
  kubectl apply -f "$WORK/calico.yaml"
  kubectl -n kube-system rollout status daemonset/calico-node --timeout=300s
  kubectl -n kube-system rollout status deployment/calico-kube-controllers --timeout=300s
  kubectl wait nodes --all --for=condition=Ready --timeout=180s

  log "build and load the agent sandbox image"
  docker build -q -t oslab-agent:dev "$ROOT/sandbox-image"
  kind load docker-image oslab-agent:dev --name "$CLUSTER"
  VALUES="$ROOT/infra/helm/values-kind.yaml"
else
  VALUES="$ROOT/infra/helm/values-eks.yaml"
  # CI only: the gateway is reachable solely through kubectl port-forward, so AWS IAM +
  # Kubernetes RBAC are the access gate. Production drops this file and uses OIDC.
  [ "${OSLAB_EKS_CI:-1}" = 1 ] && VALUES_EXTRA="$ROOT/infra/helm/values-eks-ci.yaml"
fi

log "Agent Sandbox $AGENT_SANDBOX_VERSION (controller + CRDs)"
kubectl apply -f "https://github.com/kubernetes-sigs/agent-sandbox/releases/download/$AGENT_SANDBOX_VERSION/sandbox.yaml"
kubectl wait --for=condition=Established crd/sandboxes.agents.x-k8s.io --timeout=120s
kubectl -n agent-sandbox-system rollout status deployment/agent-sandbox-controller --timeout=300s

log "OpenShell gateway chart $OPENSHELL_CHART_VERSION (telemetry off)"
helm upgrade --install openshell oci://ghcr.io/nvidia/openshell/helm-chart \
  --version "$OPENSHELL_CHART_VERSION" --namespace "$NS" --create-namespace \
  --values "$VALUES" ${VALUES_EXTRA:+--values "$VALUES_EXTRA"} \
  --set "server.telemetryEnabled=$OPENSHELL_TELEMETRY_ENABLED" \
  --set supervisor.sandboxRuntime.networkPolicyEnforced=true \
  --wait --timeout 10m
kubectl -n "$NS" rollout status statefulset/openshell --timeout=300s

log "OpenShell CLI $OPENSHELL_VERSION (installer pinned to the release tag; it verifies checksums)"
if ! command -v openshell >/dev/null || ! openshell --version 2>/dev/null | grep -q "${OPENSHELL_VERSION#v}"; then
  curl -fsSL "https://raw.githubusercontent.com/NVIDIA/OpenShell/$OPENSHELL_VERSION/install.sh" -o "$WORK/openshell-install.sh"
  OPENSHELL_VERSION="$OPENSHELL_VERSION" sh "$WORK/openshell-install.sh"
fi
openshell --version

log "port-forward the gateway and register it with the CLI"
PORT="${OSLAB_PORT:-18080}"
pkill -f "port-forward svc/openshell $PORT:8080" 2>/dev/null || true
nohup kubectl -n "$NS" port-forward svc/openshell "$PORT:8080" >"$WORK/port-forward.log" 2>&1 &
echo $! > "$WORK/port-forward.pid"
for _ in $(seq 1 30); do (echo >"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break; sleep 1; done

CFG="${XDG_CONFIG_HOME:-$HOME/.config}/openshell"
GW="oslab-$TARGET"
mkdir -p "$CFG/gateways/$GW"
if [ "$TARGET" = kind ]; then
  cat >"$CFG/gateways/$GW/metadata.json" <<EOF
{ "name": "$GW", "gateway_endpoint": "http://127.0.0.1:$PORT", "is_remote": false, "gateway_port": $PORT, "auth_mode": "plaintext" }
EOF
else
  # TLS gateway: trust the chart-generated CA and present its client bundle.
  mkdir -p "$CFG/gateways/$GW/mtls"
  kubectl -n "$NS" get secret openshell-client-tls -o jsonpath='{.data.ca\.crt}' | base64 -d >"$CFG/gateways/$GW/mtls/ca.crt"
  kubectl -n "$NS" get secret openshell-client-tls -o jsonpath='{.data.tls\.crt}' | base64 -d >"$CFG/gateways/$GW/mtls/tls.crt"
  kubectl -n "$NS" get secret openshell-client-tls -o jsonpath='{.data.tls\.key}' | base64 -d >"$CFG/gateways/$GW/mtls/tls.key"
  chmod 600 "$CFG/gateways/$GW/mtls/tls.key"
  cat >"$CFG/gateways/$GW/metadata.json" <<EOF
{ "name": "$GW", "gateway_endpoint": "https://127.0.0.1:$PORT", "is_remote": false, "gateway_port": $PORT }
EOF
fi
printf '%s' "$GW" >"$CFG/active_gateway"
export OPENSHELL_GATEWAY="$GW"
openshell status
log "ready: gateway '$GW' on 127.0.0.1:$PORT. Next: make e2e"
