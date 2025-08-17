#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/publish.sh <dockerhub_user> [tag]
#
# Or with env vars:
#   DOCKERHUB_USER=<user> TAG=<tag> IMAGE_NAME=<name> DOCKERHUB_TOKEN=<token> ./scripts/publish.sh
#
# Notes:
# - If DOCKERHUB_TOKEN is provided, the script will docker login non-interactivamente.
# - If TAG != latest, the script also tags and pushes :latest.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$REPO_ROOT"

DOCKERHUB_USER="${1:-${DOCKERHUB_USER:-}}"
TAG="${2:-${TAG:-latest}}"
IMAGE_NAME="${IMAGE_NAME:-swarm-autoscaler-suite}"

if [[ -z "${DOCKERHUB_USER}" ]]; then
  echo "Usage: $0 <dockerhub_user> [tag]" 1>&2
  echo "Or set DOCKERHUB_USER and optional TAG/IMAGE_NAME env vars." 1>&2
  exit 1
fi

FULL_IMAGE="${DOCKERHUB_USER}/${IMAGE_NAME}:${TAG}"

echo "[build] Building image ${FULL_IMAGE} from services/common/Dockerfile ..."
docker build -f services/common/Dockerfile -t "${FULL_IMAGE}" .

if [[ -n "${DOCKERHUB_TOKEN:-}" ]]; then
  echo "[login] Logging in to Docker Hub as ${DOCKERHUB_USER} ..."
  echo "${DOCKERHUB_TOKEN}" | docker login -u "${DOCKERHUB_USER}" --password-stdin
else
  echo "[login] Skipping docker login (DOCKERHUB_TOKEN not set). Ensure you are logged in (docker login)."
fi

echo "[push] Pushing ${FULL_IMAGE} ..."
docker push "${FULL_IMAGE}"

if [[ "${TAG}" != "latest" ]]; then
  LATEST_IMAGE="${DOCKERHUB_USER}/${IMAGE_NAME}:latest"
  echo "[tag] Also tagging and pushing ${LATEST_IMAGE} ..."
  docker tag "${FULL_IMAGE}" "${LATEST_IMAGE}"
  docker push "${LATEST_IMAGE}"
fi

echo "Done. Pushed: ${FULL_IMAGE}"


