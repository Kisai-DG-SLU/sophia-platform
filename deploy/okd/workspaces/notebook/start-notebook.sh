#!/usr/bin/env bash
# Historique, non maintenu : espace de notebooks du socle de juin 2026, jamais déployé dans l'installation de référence (voir README.md de ce dossier).
set -euo pipefail

export PATH="/tmp/.pixi/bin:${PATH}"
export HOME="${HOME:-/tmp}"
export WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"

mkdir -p "${WORKSPACE_DIR}"
mkdir -p "${HOME}/.local/share/jupyter"

exec /tmp/.pixi/bin/jupyter-lab --config=/opt/app-root/jupyter_lab_config.py
