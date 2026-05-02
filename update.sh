#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [ -d .git ]; then
  git pull --ff-only || true
fi
exec ./install.sh "$@"
