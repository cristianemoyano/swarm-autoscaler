#!/usr/bin/env bash
set -euo pipefail

# Bring down all sample stacks deployed from samples/
# Usage: ./samples/down.sh

echo "Removing sample stacks (if present)..."
docker stack rm autoscale-cpu 2>/dev/null || true
docker stack rm autoscale-mem 2>/dev/null || true

echo "Waiting for stacks to be removed..."
for i in {1..30}; do
  out=$(docker stack ls --format '{{.Name}}' | grep -E '^(autoscale-cpu|autoscale-mem)$' || true)
  if [ -z "$out" ]; then
    echo "Stacks removed."
    break
  fi
  sleep 1
done

echo "Done."


