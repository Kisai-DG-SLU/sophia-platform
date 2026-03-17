#!/usr/bin/env bash
set -euo pipefail

export PATH="/tmp/.pixi/bin:${PATH}"
export HOME="${HOME:-/tmp}"
export WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"

mkdir -p "${WORKSPACE_DIR}"
mkdir -p "${HOME}/.local/share/jupyter"

exec /tmp/.pixi/bin/jupyter-lab --config=/opt/app-root/jupyter_lab_config.py
