#!/usr/bin/env bash
set -euo pipefail

# Usage: ./samples/deploy.sh <cpu|memory>

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <cpu|memory>" >&2
  exit 1
fi

KIND="$1"
STACK="autoscale-${KIND}"
FILE="samples/swarm-stack-${KIND}.yml"

if [[ ! -f "$FILE" ]]; then
  echo "Unknown kind: $KIND (expected cpu or memory)" >&2
  exit 1
fi

echo "Ensuring Swarm is initialized..."
docker swarm init >/dev/null 2>&1 || true

echo "Deploying stack $STACK using $FILE ..."
docker stack deploy -c "$FILE" "$STACK"

echo "Done. Services:"
docker service ls | grep "$STACK" || true


