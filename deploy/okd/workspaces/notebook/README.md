# Sophia Notebook Workspace

Workspace notebook générique pour SophIA.

## Objectif
Fournir une interface JupyterLab réutilisable pour plusieurs projets.

## Principe
- L'image contient Pixi, git et JupyterLab
- Les dépendances scientifiques vivent dans chaque repo projet (`pixi.toml` / `pixi.lock`)
- Le workspace persistant est monté sur `/workspace`

## Utilisation
Dans Jupyter terminal :

```bash
cd /workspace
git clone <repo-projet>
cd <repo-projet>
pixi install
pixi run python -m ipykernel install --user --name <nom-kernel> --display-name "<Nom affiché>"
