# Sophia Notebook Workspace

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
