# Modules privés — ce qu'on peut construire avec SophIA

Un **module** est une application du foyer ou de l'organisation, construite sur les briques de la plateforme au lieu de les réinventer : connexion unique, routeur de modèles et modèle local, base PostgreSQL partagée, outils MCP, interface de discussion. Les modules ci-dessous tournent dans l'installation de référence ; leur code est **privé** (il porte des données et des réglages propres à un foyer), mais leur architecture et leurs règles sont décrites ici pour qu'un tiers puisse en construire d'équivalents.

| Module | Ce qu'il fait | Briques de la plateforme |
|---|---|---|
| [Cuisine](cuisine/README.md) | planning des repas, catalogue de recettes, génération de recettes sous règles, courses | SSO, modèle local, PostgreSQL, outil `image`, sas web, MCP vers la discussion et vers le module Courses |
| [Courses](courses/README.md) | choix des produits d'un drive selon les règles du foyer, remplissage du vrai panier, panier express depuis la discussion | SSO, modèle local, PostgreSQL, navigateur distant dans le sas, MCP |
| [École](ecole/README.md) | école ludique du primaire au collège, indices sans la réponse, carnet de notes, lecture des devoirs photographiés | SSO et rôles, modèle local avec vision, interface de discussion, contenus par Git |
| [Bureautique](bureautique/README.md) | fichiers de chacun, privés par défaut, édition des documents dans le navigateur, recherche et lecture depuis la discussion | SSO, PostgreSQL 18, S3 commun, outil MCP « fichiers » sous l'identité de la personne |
| [Communication](communication/README.md) | chat permanent entre les membres du foyer et visio, à la maison seulement ; installé, en recette | SSO, PostgreSQL 18, volume local dédié, VPN pour le média de la visio |
| [Visualisation](visualisation/README.md) | état mesuré de chaque composant et chemin d'une demande, contrôle horaire des miroirs des dépôts ; conformité prévue | SSO, API du cluster et métrologie en lecture, bus d'événements en lecture, forge |

## Le patron commun

| Règle | Comment elle s'applique |
|---|---|
| **Le modèle analyse, des règles décident, un outil exécute** | le modèle propose (une recette, la compréhension d'une ligne de courses, un indice) en JSON strict ; un validateur déterministe accepte ou rejette avec ses motifs ; seul le code agit (enregistrer, remplir un panier, publier) |
| **Un contrôle autour de toute sortie du modèle** | sources citées = pages réellement lues ; marque acceptée seulement si elle est écrite ; un indice ne contient jamais la réponse ; une image passe par le classifieur |
| **L'identité vient de la plateforme, jamais du modèle** | en-tête posé par oauth2-proxy sur les pages ; paramètre injecté par l'interface (`sophia/injecte`) dans les outils MCP ; liste des membres autorisés vérifiée par le serveur |
| **Comptes protégés** | les enfants lisent, ne déclenchent ni achat ni génération coûteuse ; leurs données ne partent jamais vers un modèle distant |
| **Réseau en liste fermée** | chaque module n'ouvre que les flux dont il a besoin (entrée par le routeur et par l'interface, sortie vers le routeur de modèles, le fournisseur d'identité, sa base, les outils utilisés) ; l'accès à Internet passe par le sas |
| **Un module = un pod, une base, un groupe** | pod avec son oauth2-proxy sur sa propre adresse (une application servie sous l'origine de l'interface aurait tous les droits de la personne sur la discussion), base et rôle propres dans le PostgreSQL partagé, groupe du realm ; build depuis la forge interne. Dans le cockpit, le module est affiché **en cadre** depuis sa propre adresse : il ne partage jamais l'origine de l'interface |
| **L'humain garde la main sur l'irréversible** | validation d'une liste, paiement, correction d'une dictée |

Pour intégrer un module à la discussion : exposer un serveur MCP (voir le [contrat des outils](../../deploy/okd/skills/README.md)), l'ajouter à `SOPHIA_MCP_URLS` de l'[interface](../../deploy/okd/apps/chat-interface/README.md) et ouvrir le flux dans sa NetworkPolicy ; pour lui donner une base : un bloc dans [`allow-apps-to-postgres.yaml`](../../deploy/okd/core/postgres/allow-apps-to-postgres.yaml).

## Intégrer un module au cockpit

L'interface de discussion est aussi le **cockpit** du foyer : un cadre commun (volet des modules, liste fermée par rôle décidée par le serveur) qui affiche chaque application au centre, avec sa propre charte (voir l'[interface](../../deploy/okd/apps/chat-interface/README.md)). Masquer un module n'est pas un contrôle : chaque application garde sa connexion et ses groupes. Un module y entre par cinq réglages, tous de son côté sauf le dernier ; un sixième, facultatif, donne à Sophia le contexte de la page.

| Réglage | Contenu |
|---|---|
| **Affichage dans le seul cockpit** | `Content-Security-Policy: frame-ancestors 'self' <origine de l'interface>` sur **toute** réponse de l'application (refus, 401, 404 et fichiers statiques compris), et plus de `X-Frame-Options`. L'origine est un réglage (variable d'environnement ou paramètre de build), jamais une adresse écrite dans le dépôt. Limite admise : les pages propres d'oauth2-proxy (connexion, erreurs) n'ont pas cet en-tête |
| **Signal « prêt »** | une fois la page utilisable, `postMessage({type: "sophia.pret", module: "<identifiant>"}, <origine de l'interface>)`, seulement si la page est dans un cadre, jamais vers `*`. L'identifiant est **celui du module dans la liste de l'interface**, pas le nom de l'application : un identifiant faux fait ignorer le signal, et le cockpit affiche sa barre de repli au bout de 8 s (cas réel, corrigé par une ligne). Écrit en ES5 si des tablettes anciennes doivent l'exécuter |
| **Résumé pour « Quoi de neuf ? »** | `GET /api/resume`, **déterministe, sans modèle**, `Cache-Control: no-store` : `{application, version, genere_le, elements: [{id, groupe, titre, detail, date, expire, lien, priorite}]}`, 20 éléments au plus ; `id` stable, `groupe` ∈ `a_faire` \| `notification` \| `nouveaute`, `titre` ≤ 80 et `detail` ≤ 160 caractères, `lien` = chemin relatif (l'interface le reconstruit sur l'adresse de la liste fermée), `priorite` 0, 1 ou 2 (2 = le plus urgent). `503 {"etat": "en_attente"}` : l'application est simplement absente du volet. L'interface valide le schéma et n'affiche jamais ce texte en HTML |
| **Identité de la personne** | c'est le **serveur** de l'interface qui appelle la route, avec le jeton d'accès de la personne (`Authorization: Bearer`). Application derrière oauth2-proxy : `--skip-jwt-bearer-tokens=true` (le jeton passe par le vérificateur du fournisseur principal : clés, émetteur, audience égale au `client-id` de l'application, groupes et `--allowed-group`) et `--bearer-token-login-fallback=false` (un jeton refusé reçoit 403, jamais une redirection). L'audience de l'application est ajoutée au jeton par un **mappeur d'audience sur le client de l'interface** (voir l'[identité](../../deploy/okd/identity/README.md)), avec les groupes **sans chemin**. **Jamais `--extra-jwt-issuers`** : il ferait une découverte OIDC sur l'adresse publique du fournisseur d'identité, que les pods ne joignent pas. Application sans oauth2-proxy : la route vérifie elle-même le jeton (signature, émetteur, dates, audience, client émetteur, groupes). Module statique : le résumé est calculé par l'interface elle-même, sans jeton |
| **Réseau** | entrée de l'oauth2-proxy (ou de la route) depuis le seul pod de l'interface ; côté interface, une sortie vers ce port dans une politique de sortie à part, qui s'additionne à la sienne sans rien couper |
| **Contexte de la page** (facultatif) | `postMessage({type: "sophia.contexte", module: "<identifiant>", …}, <origine de l'interface>)` après le signal « prêt », puis à chaque changement de page, seulement dans un cadre. Des **champs de forme fermée** seulement, jamais de texte libre ni de donnée de la personne (école : matière et thème, identifiants de l'index ; cuisine : page et identifiant de la recette affichée). L'interface ne l'accepte que de l'origine et du cadre du module, jette tout champ en trop, et son serveur revalide avant d'ajouter **une ligne de contexte** au « Demander à Sophia » de l'application, sans aucun droit en plus |

Mise en service : par **modifications ciblées** des arguments d'oauth2-proxy et de la règle réseau, gardées par des contrôles de la valeur attendue, essai à blanc côté serveur, contrôle d'un jeton invalide (403 attendu) et retour arrière en deux temps. Un `apply` du manifeste complet remettrait l'image sur une étiquette mobile au lieu de l'empreinte construite. L'interface passe ensuite le module en cadre par un réglage de son manifeste, sans build.

| Module | Dans le cockpit |
|---|---|
| Cuisine | affichée au centre : **en service, vérifiée** ; jeton accepté (403 vérifié pour un jeton invalide) ; route de résumé appelée par l'interface : en service, vérifiée ; contexte de page : en service, en recette |
| École | affichée au centre : **en service, vérifiée** sur ordinateur ; la reconnexion au téléphone est en recette ; résumé et nouveautés calculés par l'interface ; contexte de page (matière et thème) en service, en recette |
| Visualisation | affichée au centre, pour l'administrateur seul : **en service, vérifiée** sur ordinateur, reconnexion au téléphone en recette ; jeton accepté (403 vérifié) ; route de résumé appelée par l'interface : en service, vérifiée |
| Bureautique, Communication | affichées au centre : en service, en recette (voir leurs pages) |
| Courses | pas encore dans le cockpit : ouverte à part |

L'ouverture d'un module sur la bonne page par Sophia, sans clic (école, cuisine, visualisation), et le volet « Demander à Sophia » de chaque application, avec une discussion par application, sont en service, en recette. Prévu : l'accès aux applications par le cockpit seulement, avec une exception pour l'administrateur (dépannage).
