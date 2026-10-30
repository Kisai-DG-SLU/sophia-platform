# Interface de discussion — déploiement de production

Modèle de déploiement d'une interface web de discussion devant le routeur de modèles, **sans aucune clé dans le navigateur** et avec **connexion obligatoire**. Le code du front n'est pas fourni : ce répertoire décrit le conteneur, le proxy et les ressources Kubernetes.

L'interface est aussi la **coquille du cockpit** : une seule page qui affiche, à côté de la discussion avec Sophia, les applications de la plateforme (cuisine, école, visualisation, messagerie, visio, bureautique) dans des cadres. Voir la section [Cockpit](#cockpit).

```
Navigateur → Route (TLS) → oauth2-proxy :4180 → nginx :8080 ─→ API des discussions :8000 ─→ routeur de modèles (LiteLLM)
                              │ connexion OIDC        │ front statique       │ contexte injecté (persona, profil, date)
                              └→ Keycloak             │ (liste blanche)      ├→ PostgreSQL 18 (discussions, profils, droits)
                                                      │                      ├→ Forgejo (projets = dépôts)
                                                      │                      ├→ sas web (recherche, météo) — ../../dmz/
                                                      │                      └→ serveurs MCP (outils, modules ; Fichiers avec le jeton)
                                                      └ identité → x-litellm-end-user-id, X-Sophia-User, X-Sophia-Groups ;
                                                        jeton d'accès → X-Sophia-Jeton, sur la seule route de discussion
```

| Fichier | Rôle |
|---|---|
| `Containerfile` | UBI 9 minimal, nginx et python3 du système, UID arbitraire (OpenShift), journaux sur stdout/stderr ; Python 3.12 et dépendances de l'API des discussions (même image, conteneur voisin) |
| `entrypoint.sh` | rendu de la configuration, tarifs relus en tâche de fond (30 s tant que le routeur ne répond pas, puis 10 min), nginx au premier plan |
| `render-config.py` | injecte la clé du routeur et la clé de la voix dans `nginx.conf` (mode 600), jamais affichées ; refuse une clé mal formée ; sans clé de voix, reprend la clé du pod et l'annonce |
| `render-pricing.py` | lit les tarifs du routeur côté serveur et écrit `pricing.json` (écriture atomique) pour le calcul du coût dans le front |
| `nginx.conf.in` | gabarit : **liste blanche** des fichiers servis et des routes relayées vers le routeur, en-têtes d'identité imposés, jeton de la personne relayé sur une seule route, CORS pour la seule origine de l'école |
| `sophia-interface.yaml` | namespace dédié `sophia-interface` : ImageStream, BuildConfig (clé de déploiement en lecture), Deployment (oauth2-proxy + nginx + API des discussions, classe `sophia-chat`), Service, NetworkPolicy |
| `sophia-interface-cockpit-egress.yaml` | sorties propres au cockpit, dans une politique à part qui s'ajoute à celle de l'application : vers l'oauth2-proxy des applications qui fournissent un résumé, et vers la route de résumé de la messagerie |
| `sophia-interface-route.yaml` | Route de production, appliquée à la bascule |
| `sophia-interface-essai.yaml` | Route d'essai avant bascule, joignable par le VPN seulement, supprimée ensuite |

## Garde-fous

- **Liste blanche des fichiers** : seuls `/`, `index.html`, `models.js`, `pricing.json`, `css/`, `js/`, `images/`, `fonts/`, `vendor/` sont servis. Sans elle, la configuration rendue — qui contient la clé — était téléchargeable.
- **Liste blanche des routes** : seules `v1/models`, `v1/chat/completions` et `health/liveliness` sont relayées. Sans elle, l'API d'administration du routeur était accessible avec la clé du serveur.
- **Clé dédiée** : une *virtual key* du routeur, limitée aux modèles exposés, avec budget et débit plafonnés.
- **Confiance d'oauth2-proxy limitée au routeur** : `--trusted-proxy-ip` n'admet les en-têtes `X-Forwarded-*` que de l'adresse par laquelle le routeur OpenShift joint les pods (`ROUTER_POD_SIDE_IP`, relevée dans le journal d'oauth2-proxy, qui avertit au démarrage tant qu'aucune n'est donnée). Limite : tout processus en `hostNetwork` du nœud partage cette adresse. En service sur tous les oauth2-proxy de la plateforme : discussion, école, modules (et navigateur distant des courses), visualisation, interface des workflows.
- **Identité imposée** : `x-litellm-end-user-id` vient d'oauth2-proxy, les en-têtes envoyés par le client sont écrasés. Le routeur suit les dépenses par personne.
- **Contexte côté serveur** : en production, `v1/chat/completions` passe par l'API des discussions, qui injecte la persona, le profil de la personne et la date avant le routeur ; le navigateur ne peut pas les modifier.
- **Recherche web** : la boucle d'outils (recherche, lecture de page, météo) tourne dans l'API, contre le sas `sophia-dmz`. Une page ne peut être lue que si son adresse vient d'un résultat de recherche ou d'un message de la personne : une adresse devinée par le modèle est refusée par le code.
- **Lieux** (météo, lieu, distance, carte) : le modèle tire les lieux de la demande ; des gardes déterministes contrôlent sa sortie avant tout appel :
  - **un lieu doit être dit** : un lieu tiré par le modèle n'est retenu que s'il figure dans le message courant (comparaison sans accents, casse ni article) ou s'il est le nom d'un lieu enregistré. La règle vaut aussi pour l'appel libre d'un outil par le modèle, refusé sans appel réseau. Elle empêche un lieu repris de l'historique ou inventé (un mot mal compris géocodé à l'autre bout du monde). En service, en recette ;
  - **un moment n'est jamais un lieu** : une liste fermée de moments (« demain », jours de la semaine…) est retirée des lieux, en second filet ;
  - **sans lieu, la question est écrite par le serveur**, sans rappeler le modèle ;
  - **pays attendu** : un résultat hors des pays attendus (`SOPHIA_PAYS_ATTENDUS`) et non nommé par la personne se fait confirmer au lieu d'être annoncé ;
  - **lieu courant de la discussion** : le serveur retient en base le dernier lieu **venu du message** et accepté par les gardes ; « et demain ? » reprend ce lieu, jusqu'à ce qu'un autre soit nommé. Le modèle ne relit jamais l'historique pour trouver un lieu. Pas de lieu courant pour une distance (deux lieux), ni pour un compte invité, qui reçoit toujours la question. En service, vérifié.
  - **Lieux du profil** (prévu) : deux lieux du foyer communs à tous (un domicile, lieu par défaut, et une résidence secondaire), réglés par un administrateur, et quelques lieux personnels par personne, nommés librement ; un responsable règle ceux d'un enfant ; on ne lit jamais les lieux d'un autre profil ; les invités n'ont que les lieux qu'ils nomment. L'adresse reste dans la base du chat ; le modèle ne reçoit que les **noms** des lieux, et l'annonce montre le nom, pas la commune. Une table d'alias fermée (« chez moi » → le domicile) s'applique après l'analyse du modèle. Ordre de résolution : lieu dit, sinon lieu courant, sinon le domicile (pour un invité : la question). **Géocodage local** de l'adresse, une fois à l'enregistrement, par la base d'adresses nationale servie dans le namespace des outils sans Internet ; hors de cette base, un code de localisation ouvert (Open Location Code) saisi par l'administrateur et décodé localement, refusé s'il tombe loin de la commune choisie. Les autres demandes restent géocodées en ligne par le sas web.
- **Outils en MCP** : l'API est un client MCP ; elle lit la liste des outils de chaque serveur de `SOPHIA_MCP_URLS` (sas web, [outils locaux](../../skills/README.md), modules), affiche l'annonce que chaque outil déclare (icône, libellé), remplit elle-même les paramètres réservés (compte protégé) et insère dans la réponse, après vérification, les images et cartes que l'outil renvoie. Ajouter un outil ne demande aucun changement de l'interface.
- **Modèles par rôle** : `SOPHIA_MODELS_BY_ROLE` (par défaut, enfants et invités sur le modèle local seulement ; un compte sans rôle connu est traité comme invité). Un modèle envoyé par le navigateur hors de la liste reçoit un **403 explicite** et rien ne part vers le routeur : pas de remplacement silencieux. Les appels internes (analyse, reformulation, résumé) reprennent le modèle déjà contrôlé ; le profil n'expose que les modèles permis. La voix passe par une clé virtuelle à part (`LITELLM_AUDIO_API_KEY`, en service), limitée aux deux alias de la voix et posée par nginx sur ses seules routes : la règle est tenue par le routeur, sans analyser le formulaire. Voir [Modèles par rôle](../../../../docs/concepts/13-modeles-par-role.md).
- **Places sur la carte graphique** : les discussions prennent au plus 2 des emplacements du serveur local le jour, 1 de 3 h à 7 h (`SOPHIA_LOCAL_CHAT_PLAGES`) ; l'école n'attend jamais ; une discussion de plus attend 60 s au plus, puis reçoit un message « très occupée ». Les tâches de fond du navigateur (titre, résumé demandé) portent l'en-tête `X-Sophia-Tache: fond` et partent sur l'alias de fond, en relais simple, avec repli sur l'alias principal si le routeur ou la clé le refuse ; le résumé de compaction reste sur l'alias principal, puisqu'il est sur le chemin du message de la personne.
- **Réponse écrite par le service** : un outil MCP peut rendre `_trace` (une ligne affichée avant la réponse) et `_fin` (la réponse finale, affichée telle quelle, sans rappeler le modèle). La décision reste au service qui connaît ses données (par exemple « rien de prévu » sur un créneau vide) : le modèle ne peut plus l'enjoliver.
- **Parcours déclarés par les outils** : un serveur MCP déclare dans les métadonnées de chaque outil son parcours (`sophia/parcours` : `express`, `lecture`, `liste`). Le serveur du chat choisit par règles les outils proposés au modèle, ou appelle lui-même l'outil d'un parcours express et écrit la réponse à partir des messages du service ; un serveur sans parcours déclarés garde l'ancien comportement.
- **Ouvrir une application** : intention `application` de l'analyse, avec des énumérations construites par le serveur pour le rôle de la personne ; décision dans la politique, sur une liste fermée et versionnée (`SOPHIA_APPLICATIONS` : identifiant, nom, adresse de base, pages permises, rôles). Les rôles permis sont ceux de la liste (Fichiers : toute la famille, chacun pour ses propres fichiers ; jamais les invités) ; le modèle n'écrit jamais une adresse.
  - **Dans le cockpit** : plus de bouton. Le serveur ajoute au flux un événement qui fait basculer le cockpit sur le module et la page demandés, pris dans la liste fermée ; le navigateur revérifie le module, son mode et la forme du chemin. Depuis l'accueil et le module Sophia, la bascule est directe ; depuis « Demander à Sophia » dans une autre application, le cockpit demande d'abord. Un bandeau « Sophia t'a ouvert … » propose de revenir. **Prête, en cours de mise en service.**
  - **Chat ouvert seul** (hors cockpit, ou appareil qui ne peut pas afficher l'application) : le serveur écrit la phrase et un **bouton**, et le navigateur n'accepte un bouton d'application que si son adresse commence par une base de la liste. Le clic ouvre ou réutilise un **onglet nommé** par application (un navigateur bloque l'ouverture d'un onglet sans geste de la personne). Les boutons sont retirés de l'historique envoyé au modèle. En service.
- **Fichiers dans le chat** (en service) : retrouver un fichier de la personne dans la bureautique, puis l'ouvrir. oauth2-proxy relaie le jeton d'accès (`--pass-access-token`, `--cookie-refresh=4m`, sous la vie de 5 minutes du jeton) ; nginx ne le transmet à l'API que sur la route de discussion (`X-Sophia-Jeton`) et le vide partout ailleurs, jamais vers le routeur ; l'API ne l'envoie qu'aux serveurs de la liste fermée `SOPHIA_MCP_JETON_URLS`, et jamais au modèle. La recherche porte sur le nom ; la réponse est écrite par le serveur, avec les liens qu'il construit : « Ouvrir dans Collabora » pour un document modifiable, « Ouvrir dans Fichiers » (aperçu) pour un autre fichier, et « Voir dans Fichiers », qui ouvre le **dossier** qui contient le fichier. La **lecture du contenu** d'un document (« lis-moi le deuxième ») est déployée, recette à faire : réservée aux modèles locaux (`SOPHIA_MODELES_CONTENU`), contenu retiré de tout appel à un autre modèle, aucun outil proposé après une lecture. Voir [Relais de l'identité](../../../../docs/concepts/12-relais-identite.md).
- **École sur sa propre adresse** : le bouton de l'école ouvre l'adresse propre de l'école, avec un lien profond par niveau et matière construit par le serveur ; côté navigateur, tout lien vers l'école devient ce bouton (une route connue est gardée, un chemin inventé mène à l'accueil, une adresse ressemblante reste un lien ordinaire), et la consigne du modèle ne contient plus l'adresse. L'ancien chemin `/ecole/` n'est plus relayé : une redirection 302 (et non 301, gardée pour toujours par le navigateur) mène à l'adresse de l'école, pour les marque-pages et les boutons des anciennes réponses, fragment compris.
- **Avis de nouvelle version** (en service) : l'API pose l'en-tête `X-Sophia-Version` (le commit de l'image) sur chaque réponse ; le front compare à la version de son chargement, à chaque réponse et au retour sur l'onglet, et affiche un bandeau « Recharger », jamais pendant une saisie ou une réponse ; jamais de rechargement automatique, le brouillon est gardé.
- **Aucune ressource tierce** (en service) : les bibliothèques du front (lecteur PDF, rendu Markdown, nettoyage du HTML, archives ZIP) sont servies par l'image sous `vendor/<paquet>@<version>/`, avec leurs licences et un manifeste d'intégrité ; les polices des thèmes aussi, sous `fonts/`. Plus aucun CDN dans la politique de sécurité du contenu : le navigateur ne joint que l'adresse de la discussion.
- **Thèmes** (en service, essais à l'étape de recette) : six thèmes au choix dans le profil, chacun en clair et en sombre, combinés au réglage clair / sombre / système ; contraste d'au moins 4,5:1 vérifié par test ; douze polices woff2 sous licence OFL embarquées ; un responsable règle le thème d'un enfant. Des thèmes du calendrier sont proposés par un bandeau « Essayer / Non merci », décidé par le serveur à l'heure locale : les fêtes **le jour même seulement** (Halloween le 31/10, Noël le 25/12, Nouvel an le 1/1, Saint-Valentin le 14/2, Pâques le dimanche, 1er mai, 14 juillet) et l'anniversaire de la personne ; les saisons le jour de leur début. Tous restent choisissables à tout moment dans « Thèmes bonus ». Les volets des discussions et des réglages sont fermés par défaut sur tous les écrans ; sur un téléphone, un seul à la fois, en surimpression.
- **Avatars** (en service) : un catalogue de dessins commun à la discussion et à l'école, servi par l'école et lu par l'API ; le profil garde une image réduite (PNG contrôlé : signature, dimensions, taille ; aucun SVG).
- **Navigateurs anciens** (Safari 15) : une garde au build refuse la syntaxe postérieure à l'ES2021 et les API absentes de Safari 15 ; la feuille de style a ses replis (`color-mix`, préfixes `-webkit-`). Une application qui exige un moteur plus récent (la bureautique) affiche un texte inactif à la place du bouton, détecté par fonction et non par le User-Agent.
- **Comptes de test** : des rôles fictifs (`enfant-a`, `parent-b`), jamais les prénoms de la famille.
- **Fenêtre de contexte** : bornée par modèle (`SOPHIA_CONTEXT_LIMITS`) ; au-delà, les échanges les plus anciens sont résumés, et un fichier trop gros est refusé avec un message clair.
- **API des discussions** : écoute sur `127.0.0.1` seulement, derrière nginx ; l'identité vient des en-têtes posés par nginx.
- **Réseau** : entrée depuis le routeur OpenShift seulement, vers oauth2-proxy ; les services joints (base, sas web, outils, modules) n'admettent plus l'interface que depuis son namespace ; sortie vers le routeur de modèles, Keycloak, PostgreSQL 18 (l'ancienne instance reste ouverte pendant la garde qui suit la migration), Forgejo, le sas web, les serveurs MCP de `sophia-skills` et des modules, l'école et le DNS. Le cockpit ajoute une **politique à part** (`sophia-interface-cockpit-egress.yaml`) : sorties vers le port d'oauth2-proxy des applications qui fournissent un résumé et vers la route de résumé de la messagerie ; les règles s'additionnent, celle de l'application ne change pas. Aucune sortie vers les applications affichées en cadre : c'est le navigateur qui les charge.

## Cockpit

Le chat devient la coquille unique des usages de la plateforme, plutôt qu'un chat qui renvoie vers des onglets. Chaque application garde sa propre charte et sa propre connexion ; le cadre (volets, en-tête, accueil) suit le thème choisi dans le profil.

### Coquille

- **Volet des modules** à gauche, masqué par défaut, ouvert par un bouton menu. La liste est **fermée, construite par le serveur et filtrée par rôle** (identifiant, nom, mode `interne` / `a_part` / `iframe`, adresse, rôles, page en lecture seule, moteur exigé) ; une adresse qui n'est pas en `https://` ou un mode inconnu sont écartés. Masquer un module n'est pas un contrôle : chaque application garde son oauth2-proxy et ses groupes. Sans liste de modules, le chat reste seul.
- **Une adresse par module** (`#/<module>`) : le bouton Retour et le rechargement fonctionnent.
- **Volets de droite**, masqués par défaut, dont le bouton disparaît volet ouvert : « Quoi de neuf ? » à l'accueil, discussions et journal dans le module Sophia, « Demander à Sophia » dans les autres applications (prévu). Sur grand écran, ils prennent leur place ; sur un téléphone, ils passent en surimpression. Leur état est retenu au changement de module et au rechargement.
- **Thème** : un bouton dans l'en-tête ouvre le choix (clair ou sombre, thèmes du profil, thèmes du calendrier), enregistré dans le profil comme dans le chat.
- **Module de développement « Zone Grise »**, réservé à l'administrateur : gérer et superviser le développement assisté par les agents de développement, et discuter avec eux ; plus tard, un bouton « Pair Programming » qui ouvre un terminal dans l'outil de code. **Prévu** : absent de la liste tant qu'il n'existe pas.

État : en service ; mise en page validée sur ordinateur, essais sur tablette ancienne et téléphone en recette.

### Accueil

- Page d'ouverture du cockpit. On y **parle à Sophia** : l'accueil passe par le même chemin d'envoi, le même micro et la même voix que le chat, et n'affiche que la dernière phrase de la personne et la dernière réponse de Sophia, avec « Voir toute la discussion ».
- **Session active**, tenue par le serveur et partagée entre les appareils : la discussion de l'accueil continue si elle date du jour et de moins de 3 heures, sinon une nouvelle s'ouvre ; son titre et son heure de début sont affichés, avec « Changer » et « Nouvelle ».
- **Hologramme** de l'avatar de Sophia : nuage de points tiré de l'avatar, dessiné en 2D dans le navigateur sans bibliothèque, qui se balance de ±30°, avec expressions et clignement. **Adaptatif** : trois paliers de densité, départ au plus léger sur un appareil inconnu, montée ou descente selon le temps mesuré par image, repli sur une image fixe ; le palier retenu expire au bout d'une semaine et à chaque nouvelle version. Arrêté hors de l'accueil et onglet caché ; tête fixe si l'appareil demande moins de mouvement.
- **Accueil par thème** : fond de scène, teinte de l'hologramme et petits pictogrammes discrets d'une liste fermée, par thème ; contrastes contrôlés par un test.
- **États de Sophia** : un nuage doré dans la tête pendant la réflexion, allumé dès l'envoi de la question ; l'icône de l'outil appelé à côté de la tête, gardée au moins 2,5 s ; les lèvres bougent quand le texte visible grandit et pendant la voix.

État : en service ; texte de l'accueil, nuage dès l'envoi, icône de l'outil, ordre des états et thème de l'accueil vérifiés par l'administrateur sur le vrai chemin ; essais sur tablette ancienne et téléphone en recette.

### États dans le flux

- Le serveur ajoute au flux de réponse (compatible OpenAI) des événements **sans `choices`**, donc ignorés des autres clients : `sophia_etat` (`reflexion`, `outil` avec une icône et un libellé, `fin`).
- L'icône est choisie **par le serveur** dans une liste fermée (cuisine, messages, météo, fichiers, école, web, générique), d'après le nom de l'outil ou son serveur ; jamais d'après un texte du modèle.
- Les annonces et traces d'outil portent `sophia_annonce` et ne comptent jamais comme texte de Sophia. Le texte visible est décidé par le navigateur seul ; la réflexion du modèle (balises ou champ dédié) maintient l'état « réflexion ».
- Les **tâches de fond** (titre, résumé) n'agissent jamais sur l'hologramme, ni côté serveur ni côté navigateur.
- **Mode d'observation**, activé seulement par un paramètre de l'adresse : surimpression locale et horodatée des états reçus, avec « Copier », pour diagnostiquer sur une vraie question. Rien n'est envoyé.

### Voix au fil du flux

La voix part pendant l'écriture : par groupes de phrases (le premier dès une quarantaine de caractères, puis 80 à 150), enchaînés sans trou avec une synthèse d'avance, sans double lecture à la fin, coupés proprement. Le délai d'un groupe tient compte de la file d'attente de la synthèse ; à l'expiration, le groupe est relancé puis fusionné au suivant : **aucun texte n'est perdu**, un groupe n'est sauté que si le service échoue. En service, vérifié (la voix part bien avant la fin du texte) ; son sur tablette ancienne en recette. Côté service : [`deploy/okd/inference/`](../../inference/README.md).

### Applications en cadre

| Réglage | Rôle |
|---|---|
| `SOPHIA_MODULES_CADRE` | liste des modules affichés au centre, lue au démarrage : changer de mode demande un `oc apply`, pas un build |
| `frame-src` de la politique de contenu | limité aux adresses de la liste fermée, comparé par un test |
| cadres vivants | **deux au plus**, chargés à la première ouverture ; le plus ancien est déchargé, jamais celui qui est affiché |
| `allow` | caméra et micro pour la seule visio ; presse-papiers et plein écran pour un document |

- **Signal `sophia.pret`** : chaque application poste `{type: "sophia.pret", module: "<identifiant>"}` vers la seule origine du chat quand elle est prête. Le chat n'accepte un message que si son **origine** est celle du module **et** si sa **source** est le cadre de ce module ; un faux signal posté par une autre page est ignoré. L'identifiant doit être exactement celui du module dans la liste (un identifiant différent est ignoré, et le repli s'affiche à tort).
- **Repli au bout de 8 s** sans signal : « Ouvrir à part » (onglet nommé) et « Se reconnecter » (connexion dans un onglet, puis rechargement du cadre au retour sur le cockpit).
- **Connexion expirée** : rien ne change dans les en-têtes du fournisseur d'identité, dont la page de connexion reste refusée dans un cadre. Une application sans session sur l'appareil affiche le repli ; « Se reconnecter » une fois par application et par appareil suffit (déjà connecté au fournisseur, donc sans saisie).
- **Chaque application** pose `frame-ancestors 'self' <origine du chat>` : seule la discussion peut l'afficher. `frame-ancestors` contrôle toute la chaîne des cadres : un éditeur imbriqué dans une application (bureautique) doit aussi admettre le chat.
- Tout est sous un même domaine parent : les cookies des cadres ne sont pas des cookies tiers.
- Une application qui exige un moteur plus récent que celui de l'appareil affiche une explication à la place du cadre.

État : cuisine, école et visualisation en cadre, en service, vérifiés ; messagerie, visio et bureautique en cadre, en service, en recette. Réglages de chaque application : [modules](../../../../docs/modules/README.md), [bureautique, chat permanent et visio](../../office/README.md).

### Document ouvert depuis la bureautique

L'application de fichiers ouvre l'éditeur dans un nouvel onglet. Dans le cockpit, le petit script qu'elle sert remplace ce seul geste : il poste `{type: "sophia.ouvrir", module: "bureau", chemin: "/wopi/<id>"}` vers le seul chat, seulement si son parent direct est le chat et pour un chemin exact de même origine. Le chat refuse un chemin trop long, contenant `..`, `?`, `#` ou `\`, ou hors de la forme fermée ; il reconstruit l'adresse sur l'origine du module et la revérifie. Le document s'ouvre dans un cadre posé par-dessus la liste, avec un bouton « ← Fichiers », son propre signal et son propre repli, et compte dans la limite de deux cadres. En service, en recette.

Prévu :

- **« Sophia, ouvre le document X »** : analyse par le modèle (intention et termes) ; décision par des règles (outil de recherche appelé avec le jeton de la personne, choix selon le nombre de résultats) ; exécution par un événement du serveur vers le cockpit. **L'identifiant vient du résultat de l'outil, jamais du modèle**, et le chemin est contrôlé des deux côtés. Un résultat : le document (l'aperçu sur un téléphone) ; plusieurs : une liste cliquable, ou leur dossier commun ; aucun : « Mes fichiers ».
- **Sophia écrit dans le document ouvert** : insertion directe en texte brut à la position du curseur, par l'API d'intégration de l'éditeur relayée par le script de l'application, annulable par Ctrl+Z, avec un bouton « Insérer » pour réinsérer. Contrôles déterministes, puisque la sortie du modèle quitte la conversation : insertion seulement si l'analyse la demande **et** qu'un document est ouvert, texte assaini et borné, origines contrôlées à chaque saut, liste fermée de deux messages relayés (jamais de commande ni de script), accusé ou erreur affichés.

### « Quoi de neuf ? »

- Volet de l'accueil, en trois groupes : à faire, notifications, nouveautés ; chaque ligne porte l'avatar et la couleur de son application.
- **Calculé par le serveur du chat**, pour que le volet soit complet sur un appareil neuf : le navigateur n'interroge aucune application.
- **Contrat** : chaque application expose `GET /api/resume`, déterministe, sans modèle de langage, au plus 20 éléments `{id, groupe, titre, detail, date, expire, lien relatif, priorite}` ; `503` signifie « absente pour l'instant ». Le chat valide le schéma, n'affiche jamais un texte en HTML et reconstruit chaque lien sur la base de la liste fermée.
- **Identité** : le serveur du chat relaie le jeton d'accès de la personne (voir [Relais de l'identité](../../../../docs/concepts/12-relais-identite.md#vers-les-routes-de-résumé)).
- Une application sans données propres (l'école, site statique) n'a pas de route : son résumé et la date de première apparition de ses nouveautés sont calculés par le chat dans sa base.

État : première version en service, en recette (résumé de l'école et nouveautés du contenu, calculés par le chat ; une source en panne n'affiche rien). Chaîne d'accès des autres applications en place (audiences, sorties réseau, applications qui acceptent le jeton et répondent 403 à un jeton invalide) ; **appels du chat aux routes de résumé prévus**.

### Accès par le cockpit seul (prévu)

Dernière étape, après la recette sur tous les appareils : une page d'application ouverte en entier est renvoyée vers le cockpit, sur le bon module. Deux couches : `frame-ancestors` (déjà posé), puis le renvoi, côté serveur par l'en-tête de destination de la requête, et côté page par un script pour les navigateurs anciens qui n'envoient pas cet en-tête. Exception pour l'administrateur, pour le dépannage. C'est une règle d'usage, pas une barrière de sécurité : chaque application garde sa connexion. Non concernés : les applications natives, les routes techniques (résumés, outils), la page de connexion.

## Prérequis (secrets)

| Secret | Contenu |
|---|---|
| `sophia-interface-git` | clé de déploiement en **lecture seule** du dépôt du front (SSH), pour le build ; jamais le jeton d'un administrateur de la forge |
| `sophia-interface-litellm` | `LITELLM_API_KEY` : virtual key dédiée ; `LITELLM_AUDIO_API_KEY` (facultative) : clé de la voix, limitée à ses deux alias — absente, la voix passe par la clé du pod, avec un avertissement au démarrage |
| `sophia-interface-oauth2` | `client-secret` (client Keycloak) et `cookie-secret` (32 caractères aléatoires) |
| `sophia-chat-db` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` : base des discussions |
| `sophia-chat-forgejo` | `FORGEJO_TOKEN` d'un compte de service Forgejo (`write:repository`, `write:organization`, `read:user`) — facultatif : sans lui, seul le projet global existe |

## Namespace dédié (en service)

L'interface est sortie du namespace des applications, où l'agent de déploiement est administrateur et pourrait lire ses Secrets. Limite : le namespace protège de l'agent de déploiement, pas de l'agent de maintenance, administrateur du cluster.

1. **Préparation**, sans effet sur ce qui tourne : namespace, quota, valeurs par défaut, entrée fermée ; les entrées des services que l'interface appelle (routeur, base, identité, forge, sas web, outils, modules) admettent **les deux** namespaces pendant la bascule.
2. **Secrets recopiés par tube** (`oc get … -o yaml | sed | oc create`), sans fichier et sans les renouveler ; clé de déploiement en lecture seule ajoutée dans la forge pour le build.
3. **Essai** complet sur la Route temporaire (`sophia-interface-essai.yaml`), joignable par le VPN seulement : discussion, école, modules, voix, Fichiers, recherche web, avec un compte enfant.
4. **Bascule** : `rollout status` exigé, puis suppression de l'ancienne Route et création de la nouvelle (`sophia-interface-route.yaml`) : la coupure tient en quelques secondes. L'ancien Deployment passe à 0, sans suppression ; l'adresse de retour d'essai est retirée du client Keycloak.
5. **Ménage**, après un jour sans incident, par une étape à part (jusque-là, le retour arrière tient en quatre commandes) : **fait**. L'ancien Deployment, ses Secrets et l'ancienne Route sont supprimés, et les entrées depuis le namespace des applications sont retirées des règles de la base, du sas web, des outils, de l'école et des modules ; ce namespace n'héberge plus rien de l'interface.

## Évolutions préparées

| Évolution | Contenu | État |
|---|---|---|
| **École sur sa propre adresse** | une école servie sous l'origine de la discussion aurait tous les droits de la personne sur la discussion. L'école passe sur son adresse, derrière son propre oauth2-proxy (sans les invités) ; le CORS ne couvre qu'un préfixe d'API (`/api/store/school/`), pour l'origine exacte de l'école ; routes dédiées pour l'avatar, les réactions et la voix, plutôt que le profil (qui modifierait la persona) ou les complétions (qui ouvriraient le modèle) ; cookie de la discussion sans domaine parent ; photos en `Cross-Origin-Resource-Policy: same-site` | trois étapes compatibles : (a) côté discussion, **en service** ; (b) l'école sur son adresse, **en service** ; (c) liens du chat vers la nouvelle adresse, **en service** ; (d) l'ancien relais `/ecole/` devenu une redirection, **en service** |
| **Avatars en image** | les dessins de l'école sont rangés en image réduite dans le profil de la discussion (PNG contrôlé : signature, dimensions, taille ; aucun SVG), les profils existants migrés ; ensuite `/ecole/` devient une redirection vers l'adresse de l'école | **en service** |
| **L'interface comme demandeur** | intention `deleguer` (analyse contrainte, règles, confirmation par un clic avec un jeton à usage unique, appel au [répartiteur](../../core/repartiteur/)) ; jeton de la personne relayé et vérifié dès le départ ; quotas par personne ; approbations du plan et des commandes dans l'interface ; suivi dans la discussion | conçu |

## Remarque

Un pod en `hostNetwork` passe à travers les NetworkPolicies (le trafic du nœud est toujours accepté). Tester l'isolement depuis un pod ordinaire.
