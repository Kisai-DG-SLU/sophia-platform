# Modules privés — ce qu'on peut construire avec SophIA

Un **module** est une application du foyer ou de l'organisation, construite sur les briques de la plateforme au lieu de les réinventer : connexion unique, routeur de modèles et modèle local, base PostgreSQL partagée, outils MCP, interface de discussion. Les modules ci-dessous tournent dans l'installation de référence ; leur code est **privé** (il porte des données et des réglages propres à un foyer), mais leur architecture et leurs règles sont décrites ici pour qu'un tiers puisse en construire d'équivalents.

| Module | Ce qu'il fait | Briques de la plateforme |
|---|---|---|
| [Cuisine](cuisine/README.md) | planning des repas, catalogue de recettes, génération de recettes sous règles, courses | SSO, modèle local, PostgreSQL, outil `image`, sas web, MCP vers la discussion et vers le module Courses |
| [Courses](courses/README.md) | choix des produits d'un drive selon les règles du foyer, remplissage du vrai panier, panier express depuis la discussion | SSO, modèle local, PostgreSQL, navigateur distant dans le sas, MCP |
| [École](ecole/README.md) | école ludique du primaire au collège, indices sans la réponse, carnet de notes, lecture des devoirs photographiés | SSO et rôles, modèle local avec vision, interface de discussion, contenus par Git |
| [Bureautique](bureautique/README.md) | fichiers de chacun, privés par défaut, édition des documents dans le navigateur, recherche et lecture depuis la discussion | SSO, PostgreSQL 18, S3 commun, outil MCP « fichiers » sous l'identité de la personne |
| [Visualisation](visualisation/README.md) | état mesuré de chaque composant et chemin d'une demande, contrôle horaire des miroirs des dépôts ; conformité prévue | SSO, API du cluster et métrologie en lecture, bus d'événements en lecture, forge |

## Le patron commun

| Règle | Comment elle s'applique |
|---|---|
| **Le modèle analyse, des règles décident, un outil exécute** | le modèle propose (une recette, la compréhension d'une ligne de courses, un indice) en JSON strict ; un validateur déterministe accepte ou rejette avec ses motifs ; seul le code agit (enregistrer, remplir un panier, publier) |
| **Un contrôle autour de toute sortie du modèle** | sources citées = pages réellement lues ; marque acceptée seulement si elle est écrite ; un indice ne contient jamais la réponse ; une image passe par le classifieur |
| **L'identité vient de la plateforme, jamais du modèle** | en-tête posé par oauth2-proxy sur les pages ; paramètre injecté par l'interface (`sophia/injecte`) dans les outils MCP ; liste des membres autorisés vérifiée par le serveur |
| **Comptes protégés** | les enfants lisent, ne déclenchent ni achat ni génération coûteuse ; leurs données ne partent jamais vers un modèle distant |
| **Réseau en liste fermée** | chaque module n'ouvre que les flux dont il a besoin (entrée par le routeur et par l'interface, sortie vers le routeur de modèles, le fournisseur d'identité, sa base, les outils utilisés) ; l'accès à Internet passe par le sas |
| **Un module = un pod, une base, un groupe** | pod avec son oauth2-proxy (ou servi derrière celui de l'interface, comme l'École), base et rôle propres dans le PostgreSQL partagé, groupe du realm ; build depuis la forge interne |
| **L'humain garde la main sur l'irréversible** | validation d'une liste, paiement, correction d'une dictée |

Pour intégrer un module à la discussion : exposer un serveur MCP (voir le [contrat des outils](../../deploy/okd/skills/README.md)), l'ajouter à `SOPHIA_MCP_URLS` de l'[interface](../../deploy/okd/apps/chat-interface/README.md) et ouvrir le flux dans sa NetworkPolicy ; pour lui donner une base : un bloc dans [`allow-apps-to-postgres.yaml`](../../deploy/okd/core/postgres/allow-apps-to-postgres.yaml).
