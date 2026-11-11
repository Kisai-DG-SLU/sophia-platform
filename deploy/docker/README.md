# Images du socle (historique, non maintenu)

Ces images datent du socle de juin 2026. Aucune n'est construite ni déployée aujourd'hui dans l'installation de référence. Elles sont gardées comme historique et ne suivent plus les règles de la plateforme (images figées par empreinte, comptes sans privilège, namespaces dédiés). Chaque fichier porte la même mention en tête.

| Dossier | État | Version qui fait foi |
|---|---|---|
| `core/` | ancienne copie | [`okd/pod-bases/core/Containerfile`](../okd/pod-bases/core/), image de base construite |
| `litellm/` | ancienne copie | [`okd/core/litellm/Containerfile`](../okd/core/README.md), image du routeur de modèles construite |
| `runner/` | runner d'intégration continue, à l'arrêt (0 réplique) | [`okd/pod-bases/runner/`](../okd/pod-bases/runner/README.md) |
| `dev-assist/`, `dev-bastion/`, `workspaces/` | jamais déployées | — |
