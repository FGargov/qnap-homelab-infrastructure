#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
compose=(
  docker compose -p qnap-review --env-file demo/compose.defaults
  -f compose/monitoring.compose.yml
  -f compose/grafana-provisioning.compose.yml
  -f compose/reviewer.compose.yml
)

case "${1:-}" in
  up)
    "${compose[@]}" config -q
    "${compose[@]}" up -d
    ;;
  test)
    exec python3 demo/smoke_test.py "${compose[@]}"
    ;;
  down)
    "${compose[@]}" down
    ;;
  *)
    printf 'Usage: %s {up|test|down}\n' "$0" >&2
    exit 2
    ;;
esac
