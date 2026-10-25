# Module Visualisation — voir ce qui tourne vraiment

Module privé construit sur SophIA : une page qui montre le **chemin d'une demande** (interface, répartiteur, workflows durables, agents exécutants, résultat) et, pour chaque composant, s'il est **théorique, déployé ou en panne**, d'après des mesures et non d'après la documentation. Le même collecteur **contrôle les miroirs** des dépôts de la forge.

| | |
|---|---|
| État | en service dans l'installation de référence (vue d'ensemble, relecture, direct, reste à déployer ; contrôle des miroirs) ; volet conformité conçu |
| Utilisateurs | le groupe d'administration seulement |
| Modèle | aucun : tout est déterministe |
| Briques de la plateforme | SSO, API du cluster et métrologie en lecture, bus d'événements en lecture, forge |
| Code | privé ; cette page décrit l'architecture et les règles pour en construire un équivalent |

Documentation détaillée : [documentation.md](documentation.md). Autres modules : [modules privés](../README.md).
