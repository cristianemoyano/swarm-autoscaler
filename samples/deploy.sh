#!/usr/bin/env bash
set -euo pipefail

# Usage: ./samples/deploy.sh <cpu|memory> [suite_image] [suite_tag]
# Example: ./samples/deploy.sh cpu clifford666/swarm-autoscaler-suite latest

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <cpu|memory> [suite_image] [suite_tag]" >&2
  exit 1
fi

KIND="$1"
STACK="autoscale-${KIND}"
FILE="samples/swarm-stack-${KIND}.yml"

SUITE_IMAGE="${2:-${SUITE_IMAGE:-clifford666/swarm-autoscaler-suite}}"
SUITE_TAG="${3:-${SUITE_TAG:-latest}}"

if [[ ! -f "$FILE" ]]; then
  echo "Unknown kind: $KIND (expected cpu or memory)" >&2
  exit 1
fi

echo "Ensuring Swarm is initialized..."
docker swarm init >/dev/null 2>&1 || true

echo "Deploying stack $STACK using $FILE with $SUITE_IMAGE:$SUITE_TAG ..."
SUITE_IMAGE="$SUITE_IMAGE" SUITE_TAG="$SUITE_TAG" docker stack deploy --with-registry-auth -c "$FILE" "$STACK"

echo "Done. Services:"
docker service ls | grep "$STACK" || true


