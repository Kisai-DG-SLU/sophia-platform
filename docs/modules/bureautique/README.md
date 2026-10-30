# Module Bureautique — fichiers et documents du foyer

Module construit sur SophIA à partir de logiciels libres existants : **La Suite Drive** (« Fichiers ») pour ranger et partager les fichiers, **Collabora Online** pour éditer les documents dans le navigateur. Chaque personne a son espace, privé par défaut ; depuis la discussion, Sophia retrouve un fichier de la personne et l'ouvre par un bouton. Dans le cockpit de l'interface, Fichiers s'affiche au centre, sous le nom « Bureau », et un document s'y ouvre dans son propre cadre.

| | |
|---|---|
| État | en service dans l'installation de référence ; affichage dans le cockpit en service, en recette ; recette publiée sous forme de procédure, sans les manifestes ; essais détaillés à faire. Prévu : « Sophia, ouvre le document X » et l'insertion de texte par Sophia dans le document ouvert |
| Utilisateurs | tous les comptes du realm, chacun dans son espace ; les invités n'ont pas l'outil de recherche dans la discussion |
| Modèle | aucun dans le module ; depuis la discussion, la lecture du contenu d'un document est réservée aux modèles locaux |
| Briques de la plateforme | SSO, PostgreSQL 18 partagé, stockage objet S3 commun, classes de priorité et quotas, interface de discussion, outil MCP « fichiers » |
| Code | logiciels amont, images figées par empreinte ; manifestes de l'installation de référence non publiés ; architecture et recette décrites ici |

Documentation détaillée : [documentation.md](documentation.md). Recette de déploiement : [`deploy/okd/office/`](../../../deploy/okd/office/README.md). Autres modules : [modules privés](../README.md).
