#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
case "$(uname -s)" in
  Darwin|Linux) ;;
  *) echo "Unsupported OS. Transparent PNG Lab supports macOS and Linux only." >&2; exit 1 ;;
esac
PYTHON_BIN="${PYTHON_BIN:-python3}"
USE_GPU=0
WITH_INSPYRENET=0
WARM_MODELS=0
for arg in "$@"; do
  case "$arg" in
    --gpu) USE_GPU=1 ;;
    --cpu) USE_GPU=0 ;;
    --inspyrenet) WITH_INSPYRENET=1 ;;
    --warm-models) WARM_MODELS=1 ;;
    --help|-h)
      echo "Usage: ./install.sh [--cpu|--gpu] [--inspyrenet] [--warm-models]"
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Could not find $PYTHON_BIN. Set PYTHON_BIN=/path/to/python3.11, python3.12, or python3.13." >&2
  exit 1
fi
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if ((3,11) <= sys.version_info < (3,14)) else f"Python 3.11, 3.12, or 3.13 is required. Found {sys.version.split()[0]}")'
if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
VENV_PY="$ROOT/.venv/bin/python"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel
EXTRAS="cpu"
if [ "$USE_GPU" -eq 1 ]; then EXTRAS="gpu"; fi
if [ "$WITH_INSPYRENET" -eq 1 ]; then EXTRAS="$EXTRAS,inspyrenet"; fi
"$VENV_PY" -m pip install --upgrade -e ".[${EXTRAS}]"
chmod +x "$ROOT/tpng" "$ROOT/bin/tpng" "$ROOT/update.sh" || true
if [ "$(uname -s)" = "Linux" ]; then
  if ! command -v zenity >/dev/null 2>&1 && ! command -v kdialog >/dev/null 2>&1 && ! command -v yad >/dev/null 2>&1; then
    echo "Note: no Linux native save-dialog helper found. Install zenity, kdialog, or yad for a native save-file dialog. Browser fallback still works."
  fi
fi
if [ "$WARM_MODELS" -eq 1 ]; then
  "$ROOT/tpng" warm-models
fi
echo "Installed/updated Transparent PNG Lab. Try: ./tpng doctor ; ./tpng web ; ./tpng process inputs/your-image.png --open"
