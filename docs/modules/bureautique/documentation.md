# Module Bureautique — documentation

## Ce que fait le module

- **Ranger et partager** : chaque personne a son espace de fichiers, avec dossiers, aperçus et historique des versions. Tout est **privé par défaut** ; un partage (lecteur ou éditeur) demande un geste explicite, et un lien reste « restreint » tant qu'on ne l'ouvre pas.
- **Éditer** : les documents bureautiques (texte, tableur, présentation, OpenDocument et formats Microsoft) s'ouvrent dans Collabora, à plusieurs à la fois. Fichiers ouvre l'éditeur dans **un nouvel onglet** ; dans le cockpit de l'interface, le document s'ouvre dans son propre cadre (ci-dessous).
- **Depuis la discussion** : Sophia retrouve un fichier de la personne par son nom, puis propose de l'ouvrir (dans Collabora pour un document modifiable, dans Fichiers sinon) et de voir le dossier qui le contient. Elle peut aussi lire et résumer le contenu d'un document, avec un modèle local seulement.

## Architecture

```
navigateur (VPN) ──► routeur d'entrée ──► nginx de Fichiers ──► interface, API, Collabora
                                              │
                                              ├──► S3 commun (médias, après autorisation par l'API)
                                              └──► port interne réservé, GET seulement ◄── outil MCP « fichiers »

API de Fichiers ──► PostgreSQL 18 partagé, fournisseur d'identité (OIDC), Valkey (file de tâches, cache)
Collabora ──► API WOPI de Fichiers (TLS interne), DNS ; rien d'autre
```

| Élément | Choix | Raison |
|---|---|---|
| Namespace | dédié (`sophia-workspace`), quota et LimitRange propres | isoler la bureautique du chat et des agents ; le quota couvre les Jobs et le pod de plus d'une mise à jour progressive |
| Priorité | classe `sophia-workspace-low`, sans préemption | sous la discussion, la voix et les agents ; au-dessus des images et du développement ([priorités](../../../deploy/okd/cluster/README.md)) |
| Base | PostgreSQL 18 partagé, un rôle et une base propres, sans superutilisateur | Drive range ses éléments dans des chemins `ltree` dont les étiquettes contiennent des tirets, refusés avant PostgreSQL 16 : la création d'un dossier échouait en 15 |
| Fichiers | S3 commun ([`deploy/okd/storage/`](../../../deploy/okd/storage/README.md)), seau versionné, **corbeille de 30 jours** pour les versions remplacées | une version écrasée ou supprimée se retrouve pendant 30 jours, puis l'espace est rendu |
| Téléversement | URL présignée, du navigateur vers le S3 | le fichier ne transite pas par l'API |
| Médias | servis par nginx après une sous-requête d'autorisation à l'API | les droits restent ceux de Fichiers |
| Identité | client OIDC confidentiel, flux standard avec PKCE | connexion unique ; aucun compte local |
| Isolation | pods en `restricted-v2`, sans capacité ; Collabora isole les documents par **Landlock** | Collabora ne reçoit aucune capacité Linux ; Landlock est vérifié actif dans son journal |
| Collabora | `always_save_on_exit=true`, `idle_timeout_secs=1800`, `max_concurrency=2`, `cleanup.limit_dirty_mem_mb=1024` ; sauvegarde automatique à 30 s et 5 min ; sonde sur `/` | rien ne se perd à la fermeture ; un document oublié libère la mémoire ; deux conversions au plus en parallèle sur un nœud partagé |
| Preuve WOPI | une clé de preuve RSA dans un Secret monté | sans elle, Collabora ne signe pas ses appels et Fichiers ne vérifie pas leur origine |
| Images | figées par empreinte | une mise à jour est une décision |

### nginx de Fichiers : trois correctifs de la mise en service

| Constat | Cause | Correctif |
|---|---|---|
| Aperçu d'image en 403 | nginx relayait vers le S3 les en-têtes `X-Forwarded-*` posés par le routeur ; SeaweedFS vérifiait la signature sur l'hôte public, pas sur l'hôte interne signé par l'API | ces en-têtes sont vidés dans les locations de médias |
| Éditeur : « failed to establish socket connection » | la location `^~ /cool` arrêtait la recherche avant la regex du WebSocket ; Collabora recevait un GET sans `Upgrade` | `location ~ ^/cool` après la regex `/ws`, comme la configuration de référence de Collabora ; les deux formes d'URL du WebSocket passent |
| Jetons WOPI dans le journal d'accès | format de journal par défaut | un format qui masque le chemin de `/cool/`, retire la requête des appels WOPI et masque un Referer qui contient un jeton |

Leçon : un relais se teste par de vraies requêtes contre de faux services, en-têtes compris, pas seulement par `nginx -t`.

## Dans le cockpit

Le [cockpit de l'interface](../../../deploy/okd/apps/chat-interface/README.md) affiche Fichiers au centre, sous le nom « Bureau ». État : en service, en recette sur chaque appareil.

- **Affichable par le seul chat** : `frame-ancestors 'self'` plus l'origine du chat sur les pages de Fichiers ; l'API, l'administration et les médias gardent leur refus d'être affichés en cadre. Collabora ajoute l'origine du chat à sa propre liste : `frame-ancestors` contrôle toute la chaîne des cadres, et l'éditeur est imbriqué. Réglages : [`deploy/okd/office/`](../../../deploy/okd/office/README.md#affichage-dans-le-cockpit).
- **Signal `sophia.pret`** : Fichiers prévient le cockpit qu'il est prêt quand la session de la personne répond ; sans signal au bout de 8 s, le cockpit propose « Ouvrir à part » et « Se reconnecter ».
- **Un document s'ouvre dans le cockpit** (en service, en recette) : le petit script injecté dans Fichiers remplace la seule ouverture d'onglet vers l'éditeur (`/wopi/<uuid>`, même origine, sans paramètre) par un message `sophia.ouvrir` au chat ; le chat vérifie la source (le cadre du Bureau), l'origine et la forme fermée du chemin, reconstruit l'adresse sur l'origine du module, et ouvre le document dans son propre cadre, avec un bouton « ← Fichiers ». Le document compte dans la limite de deux cadres vivants.
- **Tablette ancienne** : Fichiers exige un moteur récent ; le cockpit affiche une explication à la place du cadre.
- **Résumé « Quoi de neuf ? »** : l'outil MCP sert `GET /api/resume` (fichiers partagés avec la personne et modifiés depuis 14 jours), avec le même jeton relayé que ses outils. Appelée par l'interface : en service, en recette.

### « Sophia, ouvre le document X »

En service, en recette.

- **Analyse par le modèle** : l'intention « fichiers », avec l'action « ouvrir » et les termes de recherche.
- **Décision par des règles** : le serveur appelle `chercher_fichiers` avec le jeton de la personne et choisit selon le nombre de résultats ; **l'identifiant du document vient du résultat de l'outil, jamais du modèle**, et aucun mot de recherche n'entre dans une adresse.
- **Exécution** : un événement du serveur vers le cockpit, avec un chemin de forme fermée (identifiant en UUID minuscule), contrôlé côté serveur puis côté navigateur.
- Un résultat : le document (au téléphone, son **aperçu**) ; plusieurs : une liste cliquable dans le cockpit, ou le dossier commun ; aucun : « Mes fichiers ». Drive n'a pas d'adresse de recherche ni de vue « tous les fichiers » : le cockpit ne peut pas lui faire afficher une liste de résultats.

### Sophia écrit dans le document ouvert

**En service, vérifié sur le vrai chemin** (insertion directe et accusé) ; la détection du curseur, corrigée, est à revérifier. On le demande depuis la discussion de Sophia ou depuis le volet « Demander à Sophia » du Bureau.

Par l'API PostMessage de Collabora, relayée par le script injecté sur la page de l'éditeur : insertion de texte brut, annulable par Ctrl+Z, refusée si le document est en lecture seule. L'écriture par l'API de Drive est écartée : elle entrerait en conflit avec la session d'édition. Décision du foyer : **Sophia insère directement, sans clic** ; un bouton « Insérer » reste pour réinsérer. Contrôles déterministes, puisque la sortie du modèle quitte la conversation :

- le relais annonce l'éditeur (`sophia.editeur_pret`) quand un document modifiable est chargé ; seulement alors, l'interface offre l'intention d'écrire ou de reformuler ;
- insertion seulement si l'analyse la demande **et** qu'un document est ouvert ; seul le texte visible de la réponse, jamais depuis une réponse rechargée de l'historique ;
- texte brut, assaini des deux côtés et borné à 20 000 caractères ;
- la **sélection** (pour reformuler) n'est lue que pour un modèle local ;
- origines et cadre contrôlés à chaque saut, dans les deux sens ;
- **liste fermée de messages relayés** (insérer, lire la sélection, annonce de l'éditeur, erreurs nommées), jamais de commande UNO ni de script reçus de l'interface ;
- **position** : au curseur si la personne a cliqué ou tapé dans le texte, sinon à la fin du document, par une commande fixe du relais ; l'accusé dit où le texte a été mis ;
- traitement de texte seulement en première version (erreur nommée pour un autre type de document) ;
- un test des sélecteurs internes de l'éditeur, à relancer à chaque nouvelle image de Collabora.

## Confidentialité

- **Chacun ses fichiers** : un élément créé par une personne est invisible des autres, y compris par son adresse directe, tant qu'il n'est pas partagé.
- **Pas de chiffrement par personne** : les fichiers sont dans le S3 et la base de l'installation. L'administrateur du système peut donc lire les données brutes ; la confidentialité tient aux droits de l'application, pas à une clé propre à chaque personne.
- **Comptes protégés** (enfants) : ils ont un espace comme les autres ; depuis la discussion, le contenu de leurs documents ne part que vers le modèle local, comme toutes leurs données.

## Depuis la discussion : l'outil MCP « fichiers »

Un serveur MCP en lecture seule ([`deploy/okd/skills/`](../../../deploy/okd/skills/README.md)), sous l'identité de la personne : le chat relaie son jeton, l'outil le vérifie puis l'échange contre un jeton émis pour lui, et Fichiers applique ses propres droits. La chaîne complète est décrite dans [Relais de l'identité](../../concepts/12-relais-identite.md).

| Outil | Ce qu'il rend | État |
|---|---|---|
| `chercher_fichiers` | jusqu'à 10 éléments trouvés **par le nom** (sans accents ni casse), avec chemin, date, type, « modifiable » ; sans URL | en service |
| `details_fichier` | un élément et son chemin lisible | en service |
| `lire_fichier` | le texte d'un document (odt, docx, ods, xlsx, pdf, txt, md, csv), borné, marqué « contenu sensible » | déployé, recette à faire |
| route `GET /api/resume` | résumé pour « Quoi de neuf ? » : fichiers partagés avec la personne, modifiés depuis 14 jours, 20 au plus ; même jeton et même audience que les outils ; Fichiers n'expose pas la date du partage | en service, contrôlée sans jeton ; appel par l'interface prévu |

- **API dédiée** : Fichiers sert son API pour jeton relayé sur un **port interne réservé**, sans Route, **en GET seulement** ; le port public répond 404 sur ce chemin. Les actions permises sont une liste blanche de lecture. La lecture du contenu passe par la même autorisation que les médias, sur ce port.
- **Liens construits par le chat** : l'outil ne rend aucune adresse ; le chat compose « Ouvrir dans Collabora » pour un élément modifiable **et** de type bureautique (par l'extension **ou** le type MIME), « Ouvrir dans Fichiers » (l'aperçu) pour les autres, et « Voir dans Fichiers » vers le dossier qui contient l'élément quand il est lisible par la personne.
- **Contenu local seulement** : le chat n'appelle `lire_fichier` qu'avec un modèle de la liste des modèles locaux, retire ce contenu de tout appel à un autre modèle, et ne propose aucun outil après une lecture (voir [Modèles par rôle](../../concepts/13-modeles-par-role.md)).
- **Pas de recherche dans le contenu** : Drive n'indexe pas le texte des fichiers sans son moteur de recherche, non installé.

## Navigateurs

Drive et Collabora utilisent des blocs `static {}` d'ES2022 : il faut au moins **Safari 16.4** (ou un navigateur équivalent). Sur un appareil plus ancien, Fichiers ne démarre pas, et aucun correctif côté serveur n'est raisonnable. Le chat détecte le moteur par un petit script ES2022 (pas par le User-Agent) : sur un moteur trop ancien, les boutons vers Fichiers deviennent un texte inactif qui le dit, et la liste des résultats reste affichée. Dans le cockpit, une explication remplace le cadre du Bureau.

## Prévu

- **Courrier unifié** (décidé, **reporté** derrière les autres projets) : un agrégateur local qui rassemble les boîtes existantes d'une personne par IMAP (synchronisation bidirectionnelle), avec tri, anti-spam et webmail derrière le SSO ; aucun serveur exposé à Internet. Un **outil MCP** permettra au modèle ou à un workflow de chercher, lire, classer et préparer un brouillon, jamais d'envoyer ni de supprimer définitivement : l'envoi reste validé par la personne.
- **Discussion permanente et visio** : en service, en recette, dans un module à part ([Communication](../communication/README.md)) ; Jitsi Meet a remplacé la Visio de La Suite, et passe par le navigateur seulement. Lancer une visio depuis la discussion reste prévu.

## Leçons

- Une base « déjà testée » par les migrations ne l'est pas pour l'écriture : la première création de dossier a révélé l'exigence de PostgreSQL 16.
- Avant de basculer un service vers une nouvelle base, contrôler sa **sortie** réseau autant que l'entrée de la base.
- Un jeton peut finir dans un journal par une voie inattendue (journal d'accès, journal d'erreurs, client HTTP d'un outil) : chaque voie se vérifie.
- Une image minimale peut manquer de la base des fuseaux horaires : vérifier l'import et le démarrage **dans l'image de base même**, et faire échouer le build plutôt que le pod ([`deploy/okd/skills/`](../../../deploy/okd/skills/README.md)).
- Pour qu'un `sub_filter` de nginx injecte un script, la réponse amont ne doit pas être compressée : vider `Accept-Encoding` vers le frontend.
