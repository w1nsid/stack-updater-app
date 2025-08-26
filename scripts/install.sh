#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo 'uv not found. Installing uv...' >&2
  curl -fsSL https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -f uv.lock ]; then
  echo 'Generating uv.lock from pyproject.toml...'
  uv lock
fi

echo 'Syncing environment with uv (creates .venv)...'
uv sync

echo 'Done.'
echo 'Run the app with:'
echo '  uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080'
