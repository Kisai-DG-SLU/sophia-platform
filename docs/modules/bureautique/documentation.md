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
- **Tablette ancienne** : Fichiers exige un moteur récent. Pour un enfant, la tuile « Bureau » ouvre son [poste au navigateur](#poste-au-navigateur-par-enfant) ; pour les autres comptes, le cockpit affiche une explication à la place du cadre.
- **Résumé « Quoi de neuf ? »** : l'outil MCP sert `GET /api/resume` (fichiers partagés avec la personne et modifiés depuis 14 jours), avec le même jeton relayé que ses outils. Appelée par l'interface : en service, vérifiée.

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

## Poste au navigateur par enfant

**En service, en recette.** Les tablettes anciennes du foyer ne peuvent pas faire tourner Fichiers et Collabora (moteur trop ancien). Pour les enfants, la tuile « Bureau » du cockpit affiche donc un **poste au navigateur** : un navigateur récent qui tourne dans le cluster, ouvert sur Fichiers, et dont la tablette ne reçoit que l'image (VNC dans la page, par noVNC). Un poste par enfant, avec son propre profil de navigateur ; adultes et invités gardent Fichiers au centre du cockpit.

```
tablette (cockpit, cadre « Bureau ») ──► routeur ──► portier : nginx ─► oauth2-proxy (session, groupe des enfants)
                                                         │      └─► portier.py (table personne → poste, réveil, extinction)
                                                         └──► poste de l'enfant (noVNC ─► navigateur en kiosque ─► Fichiers)
```

| Élément | Choix | Raison |
|---|---|---|
| Namespace | dédié (`sophia-postes`), quota, refus par défaut, EgressFirewall | les postes sont des navigateurs complets : les isoler du reste |
| Poste | une image figée par empreinte : Chromium en kiosque sur Fichiers, serveur X virtuel, noVNC et websockify ; un Deployment par enfant (`poste-a`, `poste-b`, jamais un prénom), **sans nombre de réplicas** : c'est le portier qui allume et éteint ; profil du navigateur sur un volume local `Retain` ; aucun jeton de compte de service monté | chaque enfant retrouve ses onglets et sa session ; rien ne tourne quand personne ne s'en sert |
| Portier | une seule adresse pour tous, sans identifiant dans l'URL ; un pod à trois conteneurs : nginx, oauth2-proxy (figé par empreinte), et un petit programme Python (bibliothèque standard, règles fixes, aucun modèle) | la cible se décide côté serveur, jamais d'après la requête |
| Aiguillage | nginx à deux étages : le premier vérifie la session et pose l'identifiant de la personne (en-tête **écrasé**, même vide, toute variante ignorée) ; le second, en boucle locale, demande la cible au portier **à chaque requête, WebSocket comprise** | un enfant ne peut pas viser le poste d'un autre |
| Table | personne → poste, par l'**identifiant technique** du fournisseur d'identité (jamais un nom), dans une ConfigMap posée par l'administrateur ; formes contrôlées, table mal formée refusée au démarrage | aucune donnée nominative dans le cluster |
| Accès | réservé au groupe des enfants (`--allowed-group`), puis à la table : un adulte ou un invité est refusé deux fois (page de refus, puis 403) | le poste est un outil pour les enfants |
| Réveil | à la première requête du Bureau, le portier passe le poste à 1 réplica et sert une page d'attente ; la page déclare l'échec à 55 s, avant le délai de 60 s du cockpit, pour qu'il n'y ait qu'un seul déclencheur ; « Réessayer » relance | un poste éteint ne coûte rien |
| Extinction au repos | après **30 minutes sans connexion** à l'écran distant ; le portier interroge l'état de chaque poste toutes les 15 s ; le client noVNC ne se reconnecte pas tout seul (sinon le poste ne s'endormirait jamais) | rendre la mémoire et le processeur au reste de la plateforme |
| Droits du portier | un Role limité aux Deployments des postes (`get`) et à leur sous-ressource `scale` (`get`, `patch`), par nom ; jeton monté dans le seul conteneur du portier | allumer et éteindre, rien d'autre |
| Signaux au cockpit | `sophia.poste` (`reveil`, `echec`, `veille`, `refuse`), `sophia.connexion_requise`, `sophia.pret`, vers la seule origine du cockpit et seulement dans un cadre ; le cockpit écrit lui-même les textes (« Ton bureau se prépare… », « s'est endormi ») | aucun texte venu de la page n'est affiché |
| Récupérer un document | le poste signale au portier le document ouvert ; le cockpit propose de le récupérer, sans réveiller un poste éteint ; l'envoi et la récupération passent par l'outil MCP « fichiers » | sans téléchargement dans la tablette |
| Supervision | métriques du portier (poste allumé, échecs de réveil) ; alertes : 3 échecs de réveil en 30 min, un échec de plus de 10 min, métriques absentes | un réveil qui échoue se voit |

**Isolement.** Un poste n'accepte en entrée que le portier, et ne sort que vers le routeur en HTTPS et le DNS : ni un autre poste, ni le portier. Le portier n'accepte que le routeur, le pod du chat et la métrologie (ces deux derniers sur son seul port d'état) ; il ne sort que vers les postes, le seul pod du fournisseur d'identité et l'API du cluster. Le chat lit l'état du poste de la personne sur une route qui vérifie le jeton relayé (audience et client propres, puis userinfo ; même identifiant exigé). La relecture a tenté douze attaques (identifiant forgé, en-tête doublé, WebSocket vers le poste d'un autre enfant, jeton d'adulte modifié ou non signé, routes internes) : toutes refusées. **Limite connue** : un WebSocket déjà ouvert n'est plus recontrôlé, jusqu'à une heure ; pour couper tout de suite, éteindre le poste.

**Session périmée effacée.** Sur une tablette, le cookie de session d'un autre compte restait dans le navigateur : oauth2-proxy le refusait, mais l'effacement qu'il émettait restait dans la sous-requête de nginx, et la connexion était redemandée sans fin. Au-delà de 4 Ko, la session tient en plusieurs cookies (`_0`, `_1`…), et nginx ne rendait que le premier effacement (il fusionne les `Set-Cookie` d'une sous-requête en un seul en-tête, dont le navigateur ne lit que le premier). Correctif : la page sans session (sur 401 seulement) efface elle-même le cookie entier et ses morceaux `_0` à `_3` (`Max-Age=0`, mêmes attributs) ; un cookie valide n'est jamais touché.

**Session de Fichiers au réveil.** La session de Fichiers dans le navigateur du poste ne tient pas une nuit : au réveil du lendemain, l'enfant tombait sur la page « Se connecter » de Fichiers. Correctif (image du poste reconstruite) : l'accueil du poste passe par la **connexion silencieuse** de Fichiers (`prompt=none`), qui reprend la session du fournisseur d'identité sans mot de passe, et sinon revient à l'accueil de Fichiers comme avant ; pour que cette session tienne d'un jour à l'autre (30 jours), l'enfant coche une fois « Se souvenir de moi » sur la page de connexion du poste. La restauration des onglets est coupée : un seul onglet, l'accueil, au lieu d'un onglet de plus à chaque réveil. Éprouvé au banc : trois démarrages sur le même profil, un seul onglet et la connexion silencieuse à chacun.

**Voile « Ton bureau se prépare » sans fin.** Le cockpit couvre le cadre du Bureau d'un voile pendant le réveil, et le lève sur `sophia.pret`, ou déclare l'échec après 60 s. Un signal `reveil` reçu après un endormissement, un échec ou une image remettait le voile **sans réarmer la minuterie** : le voile restait, alors que le bureau était prêt derrière. Correctif : la minuterie est réarmée à chaque « se prépare » ; au pire, l'enfant voit « n'a pas pu s'allumer » et « Réessayer ». Des traces d'observation, activées par un paramètre de l'adresse, servent à relever les états sur une tablette.

**Pièges de la mise en service.**

- **L'EgressFirewall coupait l'API du cluster** : le Service `kubernetes` aboutit à l'adresse du nœud, sur le port de l'API ; la NetworkPolicy l'autorisait, l'EgressFirewall du namespace non. Le portier ne pouvait ni lire, ni allumer, ni éteindre un poste. Correctif : une règle vers les nœuds du plan de contrôle, sur le port de l'API, avant le refus. Le banc n'avait pas d'EgressFirewall : croiser NetworkPolicy **et** EgressFirewall à la relecture.
- **Une session d'un autre compte restée sur la tablette** faisait voir le portier un adulte, refusé : d'où l'effacement ci-dessus, et la **déconnexion des modules** par le cockpit (voir l'[interface](../../../deploy/okd/apps/chat-interface/README.md#cockpit)).

**État** : en service ; les deux enfants ont leur bureau ; extinctions au repos réelles observées ; premier réveil à froid mesuré : **3 s** jusqu'au poste prêt, image déjà sur le nœud, sans le chargement de noVNC ; correctifs de la connexion à Fichiers et du voile en service, à vérifier sur chaque tablette. Restent à éprouver : la récupération d'un document, l'endormissement puis le réveil sur chaque tablette, et le coût réel de l'affichage à l'échelle 2. **Limite connue** : la page de refus du portier (`sophia.poste` `refuse`) n'est pas encore traitée par le cockpit.

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
