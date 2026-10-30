# Module Cuisine — menus, recettes et courses d'un foyer

Module privé construit sur SophIA : il tient le **planning des repas** d'un foyer (midi et soir, par personne), son **catalogue de recettes** et sa **liste de courses**. Le modèle **invente** des recettes ; des **règles décident** si elles entrent au catalogue.

| | |
|---|---|
| État | en service dans l'installation de référence ; affichée au centre du cockpit de l'interface (en service, vérifiée) |
| Utilisateurs | les adultes du foyer (accès complet), les enfants (comptes protégés : planning en lecture, et seulement les recettes au planning du foyer) |
| Modèle | `sophia-local` (inférence locale) par défaut, par le routeur de modèles |
| Briques de la plateforme | SSO, routeur de modèles, PostgreSQL 18 partagé, outil MCP `image`, sas web, interface de discussion, module Courses |
| Code | privé ; cette page décrit l'architecture et les règles pour en construire un équivalent |

Documentation détaillée : [documentation.md](documentation.md). Autres modules : [modules privés](../README.md).
