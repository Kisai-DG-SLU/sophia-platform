# Module Communication — chat permanent et visio du foyer

Module construit sur SophIA à partir de logiciels libres existants : **Matrix** (serveur Synapse, client Element) pour un chat permanent entre les membres du foyer, **Jitsi Meet** pour la visio. Connexion unique par le fournisseur d'identité de la plateforme, sans compte local ; tout reste à la maison, joint par le VPN.

| | |
|---|---|
| État | **en service, en recette** dans l'installation de référence : les deux services tournent et la première connexion est faite ; Messages et Visio s'affichent dans le cockpit de l'interface ; la recette (visio à plusieurs appareils, invité refusé, compte protégé, clients du chat sur téléphone et tablette) reste à faire ; la visio passe par le navigateur seulement ; recette de déploiement publiée sous forme de procédure, sans les manifestes |
| Utilisateurs | les groupes du foyer ; les invités sont refusés par le fournisseur d'identité, et par la visio elle-même |
| Modèle | aucun : pas d'agent dans les salons pour l'instant ; le résumé des non-lus pour l'interface est un calcul déterministe |
| Briques de la plateforme | SSO, PostgreSQL 18 partagé, volume local dédié, classes de priorité et quotas, VPN (média de la visio) |
| Code | logiciels amont, images figées par empreinte ; un petit adaptateur écrit pour la visio ; manifestes de l'installation de référence non publiés ; architecture et recette décrites ici |

Documentation détaillée : [documentation.md](documentation.md). Recette de déploiement : [`deploy/okd/office/`](../../../deploy/okd/office/README.md#chat-permanent-et-visio). Autres modules : [modules privés](../README.md).
