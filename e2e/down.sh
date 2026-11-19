#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${OSLAB_WORK:-$ROOT/.work}"
[ -f "$WORK/port-forward.pid" ] && kill "$(cat "$WORK/port-forward.pid")" 2>/dev/null || true
if [ "${TARGET:-kind}" = kind ]; then
  kind delete cluster --name "${KIND_CLUSTER_NAME:-oslab}"
else
  helm uninstall openshell -n openshell || true
fi
