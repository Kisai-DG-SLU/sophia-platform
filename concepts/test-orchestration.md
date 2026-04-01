# 🧠 Workflow Sophia-Brain : Orchestration des tests de Projets sur OKD

Ce document définit la méthode standard pour gérer les tests des projets d'intelligence artificielle via Jupyter Lab au sein de l'écosystème **SophIA** (Sovereign Orchestrator Platform for Holistic Intelligence Architecture).

## 1. Architecture du Système
Le modèle repose sur un **Souverain Orchestrateur** unique accédant à une galaxie de projets versionnés.

* **Calcul (OKD)** : Un Pod unique `sophia-notebook` (image personnalisée).
* **Stockage (PVC)** : Volume persistant `sophia-notebook-workspace-pvc` monté sur `/workspace`.
* **Forgejo (Git)** : 
    * `Guesdon-Brain` : Dépôt global contenant les spécifications et SOP.
    * `Dépôts Projets` : Un dépôt dédié par projet (ex: `label_image`).
* **Isolation (Pixi)** : Environnements reproductibles par projet via `.pixi/`.

---

## 2. Structure du Workspace
L'organisation sur le PVC garantit la persistance des environnements et du code :

```text
/workspace/
├── .local/                # Configuration Jupyter (Kernels, extensions)
├── specs/                 # Clone du repo Guesdon-Brain (La doctrine)
├── projet-A/              # Dépôt Forgejo du Projet A
│   ├── .pixi/             # Environnement Python/Conda isolé
│   ├── pixi.toml          # Manifeste des dépendances
│   └── data/              # Données locales (images, datasets)
└── projet-B/              # Dépôt Forgejo du Projet B
```

---

## 3. Workflow Opérationnel

### A. Initialisation ou Récupération
Pour travailler sur un projet dans le Pod générique :

1.  **Clonage avec PAT** :
    ```bash
    cd /workspace
    git clone http://<votre-pat>@forgejo.sophia/user/nom-du-projet.git
    ```
2.  **Configuration Pixi** :
    ```bash
    cd nom-du-projet
    pixi install  # Installe les dépendances définies dans le pixi.toml
    ```

### B. Création du Kernel Jupyter (Isolation Logicielle)
Chaque projet doit posséder son propre noyau pour éviter les conflits de bibliothèques (ex: versions de `numpy` ou `torch`).

```bash
# Commande à exécuter dans le terminal du pod (oc rsh)
pixi run python -m ipykernel install --user \
    --name nom-du-projet \
    --display-name "Python (Nom du Projet)"
```

### C. Utilisation de l'Interface Jupyter Lab
1.  Ouvrir Jupyter Lab via la Route OKD.
2.  Naviguer vers le dossier du projet dans l'explorateur à gauche.
3.  **Sélection du Kernel** : Lors de l'ouverture d'un `.ipynb`, s'assurer que le kernel sélectionné en haut à droite est bien celui du projet actif.

---

## 4. Gestion des Données et Sauvegarde
* **Données (`/data`)** : Stockées sur le PVC. Attention, si elles ne sont pas suivies par Git (LFS ou ignorées), une suppression manuelle est définitive.
* **Commit & Push** : Le terminal de Jupyter Lab ou `oc rsh` doit être utilisé pour synchroniser le code vers Forgejo.
* **Multi-projets** : Plusieurs projets peuvent être ouverts simultanément dans Jupyter Lab (onglets différents), chacun utilisant son propre Kernel Pixi.

---

## 5. Maintenance Rapide
* **Retrouver le Token** : `oc logs <pod_name>` ou `oc rsh <pod_name> jupyter lab list`.
* **Réparer un Kernel** : Si un module est introuvable malgré l'installation, vérifier le chemin dans `~/.local/share/jupyter/kernels/<projet>/kernel.json`.
* **Variables d'environnement** : Les secrets globaux sont partagés dans le Pod. Pour des secrets spécifiques, utiliser un fichier `.env` chargé par `python-dotenv` au sein du kernel spécifique.

---
*Dernière mise à jour : 1er Avril 2026*
