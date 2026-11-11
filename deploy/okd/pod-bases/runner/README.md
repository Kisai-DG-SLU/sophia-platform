# Runners CI — Forgejo Actions

> **Historique, non maintenu.** Runner d'intégration continue du socle de juin 2026, à l'arrêt (0 réplique) dans l'installation de référence ; son retrait est en attente. Ses manifestes n'ont pas suivi les règles d'aujourd'hui. Chaque fichier porte la même mention.

Ce répertoire contient les manifests de déploiement pour les Forgejo Action Runners.

## Ressources

- `runner-gpu.yaml` — Déploiement d'un runner avec GPU pour les charges de travail CI nécessitant une accélération GPU
- `policy-runner.yaml` — NetworkPolicy autorisant l'accès du runner a l'API Forgejo
- `Dockerfile` — dans `deploy/docker/runner/Dockerfile`
