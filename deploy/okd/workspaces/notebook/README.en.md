# Sophia Notebook Workspace

> **Historical, not maintained.** Notebook workspace from the June 2026 base, never deployed in the reference installation. It is kept as an example; its manifests have not followed today's rules (namespace, network, identity). Each file carries the same note.

Generic notebook workspace for SophIA.

## Purpose
Provide a reusable JupyterLab interface for multiple projects.

## Principle
- The image contains Pixi, git and JupyterLab
- Scientific dependencies live in each project repository (`pixi.toml` / `pixi.lock`)
- The persistent workspace is mounted on `/workspace`

## Volume
`pv.yaml` carries the `${NODE_NAME}` variable, the node carrying the volume (`oc get nodes`), and `${NOTEBOOK_MOUNT_POINT}`, the volume's directory on the node: `envsubst '${NODE_NAME} ${NOTEBOOK_MOUNT_POINT}' < pv.yaml | oc apply -f -`.

## Usage
In Jupyter terminal:

```bash
cd /workspace
git clone <project-repo>
cd <project-repo>
pixi install
pixi run python -m ipykernel install --user --name <kernel-name> --display-name "<Display name>"
```
