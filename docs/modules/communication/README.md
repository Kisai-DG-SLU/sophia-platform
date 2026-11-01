# Module Communication — chat permanent et visio du foyer

Module construit sur SophIA à partir de logiciels libres existants : un chat permanent entre les membres du foyer, **Converse.js et Prosody** (XMPP), à la place de **Matrix** (décision prise après un essai sur la vraie tablette) ; « dis à », pour que Sophia écrive au nom de la personne ; **Jitsi Meet** pour la visio. Connexion unique par le fournisseur d'identité de la plateforme, sans compte local ; tout reste à la maison, joint par le VPN.

| | |
|---|---|
| État | **en service, en recette** dans l'installation de référence : chat Matrix et visio affichés dans le cockpit ; **première visio avec image** entre un ordinateur et la tablette ancienne, dans le cockpit, par le VPN ; **messagerie XMPP définitive en service** dans le cockpit, avec « dis à » ; Matrix lisible jusqu'à la fin de la recette, puis démonté ; **recette familiale en cours**, sur chaque appareil du foyer ; la visio passe par le navigateur seulement ; recette de déploiement publiée sous forme de procédure, sans les manifestes |
| Utilisateurs | les groupes du foyer ; les invités sont refusés par le fournisseur d'identité, et par la visio elle-même |
| Modèle | aucun dans la messagerie : pas d'agent dans les salons ; « dis à » passe par le modèle du chat pour l'intention, puis par une confirmation et une règle pour l'envoi ; le résumé des non-lus est un calcul déterministe |
| Briques de la plateforme | SSO, PostgreSQL 18 partagé, volume local dédié, classes de priorité et quotas, VPN (média de la visio) |
| Code | logiciels amont, images figées par empreinte ; un petit adaptateur écrit pour la visio ; modules de Prosody (groupes du foyer, « dis à »), passerelle de push et greffons de Converse.js écrits pour le foyer ; manifestes de l'installation de référence non publiés ; architecture et recette décrites ici |

Documentation détaillée : [documentation.md](documentation.md). Recette de déploiement : [`deploy/okd/office/`](../../../deploy/okd/office/README.md#chat-permanent-et-visio). Autres modules : [modules privés](../README.md).
