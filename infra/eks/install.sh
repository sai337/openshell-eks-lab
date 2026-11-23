#!/usr/bin/env bash
# Enterprise install on the current EKS context: gp3 StorageClass, agent image
# to ECR (immutable, scanned), then the same install as the POC with EKS values.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TF="$ROOT/infra/eks/terraform"
WORK="${OSLAB_WORK:-$ROOT/.work}"
mkdir -p "$WORK"

kubectl apply -f - <<'EOF'
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
provisioner: ebs.csi.aws.com
parameters: { type: gp3, encrypted: "true" }
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
allowVolumeExpansion: true
EOF

REPO="$(terraform -chdir="$TF" output -raw ecr_repository_url)"
REGION="$(terraform -chdir="$TF" output -raw region)"
TAG="$(git -C "$ROOT" rev-parse --short HEAD)"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${REPO%%/*}"
docker build --platform linux/amd64 -t "$REPO:$TAG" "$ROOT/sandbox-image"  # EKS nodes are x86_64
docker push "$REPO:$TAG"
DIGEST="$(docker inspect --format '{{index .RepoDigests 0}}' "$REPO:$TAG")"
echo "$DIGEST" > "$WORK/sandbox-image-ref"
echo "agent image: $DIGEST"

TARGET=eks bash "$ROOT/e2e/up.sh"
