# Sophia Notebook Workspace

Workspace notebook générique pour SophIA.

## Objectif
Fournir une interface JupyterLab réutilisable pour plusieurs projets.

## Principe
- L'image contient Pixi, git et JupyterLab
- Les dépendances scientifiques vivent dans chaque repo projet (`pixi.toml` / `pixi.lock`)
- Le workspace persistant est monté sur `/workspace`

## Volume
`pv.yaml` porte les variables `${NODE_NAME}`, nœud qui porte le volume (`oc get nodes`), et `${NOTEBOOK_MOUNT_POINT}`, répertoire du volume sur le nœud : `envsubst '${NODE_NAME} ${NOTEBOOK_MOUNT_POINT}' < pv.yaml | oc apply -f -`.

## Utilisation
Dans Jupyter terminal :

```bash
cd /workspace
git clone <repo-projet>
cd <repo-projet>
pixi install
pixi run python -m ipykernel install --user --name <nom-kernel> --display-name "<Nom affiché>"
