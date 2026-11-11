# Workflow d'Orchestration des Tests de Projets

Ce document définit la méthode standard pour gérer les tests des projets d'intelligence artificielle via un environnement de notebooks au sein de l'écosystème SophIA.

## 1. Architecture du Système

Le modèle repose sur un orchestrateur souverain unique accédant à un ensemble de projets versionnés.

- **Calcul (Kubernetes) :** Un pod unique dédié aux notebooks, base image personnalisée.
- **Stockage :** Volume persistant monté sur `$WORKSPACE_DIR`.
- **Git :**
  - Dépôt global contenant les spécifications et procédures.
  - Un dépôt dédié par projet.
- **Isolation des environnements :** Environnements reproductibles par projet via un gestionnaire dédié.

---

## 2. Structure du Workspace

L'organisation garantit la persistance des environnements et du code :

```text
$WORKSPACE_DIR/
├── .local/                # Configuration de l'IDE notebooks
├── specs/                 # Clone du dépôt Brain (la doctrine)
├── projet-a/              # Dépôt du Projet A
│   ├── .env/              # Environnement isole
│   ├── env.toml           # Manifeste des dependances
│   └── data/              # Donnees locales
└── projet-b/              # Dépôt du Projet B
```

---

## 3. Workflow Opérationnel

### A. Initialisation ou Récupération

1.  Clonage avec token d'accès :

    ```bash
    cd $WORKSPACE_DIR
    git clone https://$GIT_SERVER/$USER/$PROJECT.git
    ```

2.  Configuration de l'environnement :

    ```bash
    cd $PROJECT
    env install   # installe les dependances du manifeste
    ```

### B. Configuration du Noyau de l'IDE

Chaque projet possède son propre noyau pour éviter les conflits de bibliothèques.

```bash
env run python -m ipykernel install --user \
    --name $PROJECT \
    --display-name "Python ($PROJECT)"
```

### C. Utilisation de l'Interface

1.  Ouvrir l'interface IDE via la route Kubernetes.
2.  Naviguer vers le dossier du projet.
3.  Sélectionner le noyau correspondant au projet actif.

---

## 4. Gestion des Données et Sauvegarde

- Les données (`/data`) sont stockées sur le volume persistant.
- Le code est synchronisé vers le dépôt Git interne via les commandes standard.
- Plusieurs projets peuvent être ouverts simultanément, chacun utilisant son propre environnement.

---

## 5. Maintenance

- Les tokens d'accès sont récupérables depuis les logs du pod.
- Les chemins des noyaux sont vérifiables dans la configuration de l'IDE.
- Les secrets globaux sont injectés dans le pod ; les secrets spécifiques peuvent être gérés par fichier d'environnement local.
