#!/usr/bin/env bash
# Run the hostile-agent security suite against the registered gateway and
# write results to evals/results/<date>-<target>/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${TARGET:-kind}"
export OPENSHELL_GATEWAY="${OPENSHELL_GATEWAY:-oslab-$TARGET}"
export OPENSHELL_TELEMETRY_ENABLED=false
IMAGE="${OSLAB_SANDBOX_IMAGE:-oslab-agent:dev}"
OUT="${OSLAB_OUT:-$ROOT/evals/results/$(date -u +%Y-%m-%d)-$TARGET}"
cd "$ROOT"
PYTHONPATH=app python3 -m oslab.cli run --image "$IMAGE" --target "$TARGET" --out "$OUT" "$@"
