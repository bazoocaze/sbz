#!/usr/bin/env bash
set -euo pipefail
if command -v uv >/dev/null 2>&1; then
  exec uv run --group dev pytest "$@"
fi
exec python3 -m pytest "$@"
