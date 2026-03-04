#!/usr/bin/env bash
# deploy.sh — Deploy build artifact to production.
# Usage: ./scripts/deploy.sh --artifact <digest> --commit <sha> --mode <deploy|rollback>
#
# Environment variables:
#   DEPLOY_TARGET (required) — deployment target identifier
#   REGISTRY       — container registry URL (default: ghcr.io)
#   IMAGE_NAME     — image name (default: omarbit)
set -euo pipefail

ARTIFACT_DIGEST=""
COMMIT_SHA=""
MODE="deploy"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --artifact) ARTIFACT_DIGEST="$2"; shift 2 ;;
    --commit)   COMMIT_SHA="$2";      shift 2 ;;
    --mode)     MODE="$2";            shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$ARTIFACT_DIGEST" || -z "$COMMIT_SHA" ]]; then
  echo "Usage: $0 --artifact <digest> --commit <sha> [--mode deploy|rollback]" >&2
  exit 1
fi

DEPLOY_TARGET="${DEPLOY_TARGET:?DEPLOY_TARGET environment variable required}"
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-omarbit}"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "=== OmarBit Deploy ==="
echo "Mode:     ${MODE}"
echo "Artifact: ${ARTIFACT_DIGEST}"
echo "Commit:   ${COMMIT_SHA}"
echo "Target:   ${DEPLOY_TARGET}"
echo "Time:     ${TIMESTAMP}"

# Emit structured deploy metadata for audit trail
cat <<EOF > /tmp/deploy-metadata.json
{
  "mode": "${MODE}",
  "artifact_digest": "${ARTIFACT_DIGEST}",
  "commit_sha": "${COMMIT_SHA}",
  "deploy_target": "${DEPLOY_TARGET}",
  "timestamp": "${TIMESTAMP}",
  "registry": "${REGISTRY}",
  "image": "${IMAGE_NAME}"
}
EOF

case "${MODE}" in
  deploy)
    echo "Deploying ${REGISTRY}/${IMAGE_NAME}@${ARTIFACT_DIGEST}..."
    # Phase 3+: uncomment and configure for your infrastructure:
    # docker push "${REGISTRY}/${IMAGE_NAME}:${COMMIT_SHA}"
    # kubectl set image "deployment/${IMAGE_NAME}" \
    #   "${IMAGE_NAME}=${REGISTRY}/${IMAGE_NAME}@${ARTIFACT_DIGEST}"
    echo "Deploy recorded: ${ARTIFACT_DIGEST} -> ${DEPLOY_TARGET}"
    ;;
  rollback)
    echo "Rolling back to ${REGISTRY}/${IMAGE_NAME}@${ARTIFACT_DIGEST}..."
    # Phase 3+: uncomment and configure for your infrastructure:
    # kubectl rollout undo "deployment/${IMAGE_NAME}"
    echo "Rollback recorded: ${ARTIFACT_DIGEST} -> ${DEPLOY_TARGET}"
    ;;
  *)
    echo "Unknown mode: ${MODE}" >&2
    exit 1
    ;;
esac

echo "=== Deploy complete (${MODE}) ==="
