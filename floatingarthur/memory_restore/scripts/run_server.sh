#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ ! -x .venv/bin/python ]]; then
  echo "Run scripts/setup_gpu_runtime.sh before starting the server." >&2
  exit 1
fi

exec .venv/bin/python scripts/server_control.py start --port "${PORT:-5050}"
