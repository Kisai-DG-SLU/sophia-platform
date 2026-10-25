# Interface de discussion — déploiement de production

Modèle de déploiement d'une interface web de discussion devant le routeur de modèles, **sans aucune clé dans le navigateur** et avec **connexion obligatoire**. Le code du front n'est pas fourni : ce répertoire décrit le conteneur, le proxy et les ressources Kubernetes.

```
Navigateur → Route (TLS) → oauth2-proxy :4180 → nginx :8080 ─→ API des discussions :8000 ─→ routeur de modèles (LiteLLM)
                              │ connexion OIDC        │ front statique       │ contexte injecté (persona, profil, date)
                              └→ Keycloak             │ (liste blanche)      ├→ PostgreSQL (discussions, profils, droits)
                                                      │                      ├→ Forgejo (projets = dépôts)
                                                      │                      └→ sas web (recherche, météo) — ../../dmz/
                                                      └ identité → x-litellm-end-user-id, X-Sophia-User, X-Sophia-Groups
```

| Fichier | Rôle |
|---|---|
| `Containerfile` | UBI 9 minimal, nginx et python3 du système, UID arbitraire (OpenShift), journaux sur stdout/stderr ; Python 3.12 et dépendances de l'API des discussions (même image, conteneur voisin) |
| `entrypoint.sh` | rendu de la configuration, tarifs relus en tâche de fond (30 s tant que le routeur ne répond pas, puis 10 min), nginx au premier plan |
| `render-config.py` | injecte la clé du routeur dans `nginx.conf` (mode 600), jamais affichée ; refuse une clé mal formée |
| `render-pricing.py` | lit les tarifs du routeur côté serveur et écrit `pricing.json` (écriture atomique) pour le calcul du coût dans le front |
| `nginx.conf.in` | gabarit : **liste blanche** des fichiers servis et des routes relayées vers le routeur, en-têtes d'identité imposés |
| `sophia-interface.yaml` | ImageStream, BuildConfig, Deployment (oauth2-proxy + nginx + API des discussions), Service, Route, NetworkPolicy |

## Garde-fous

- **Liste blanche des fichiers** : seuls `/`, `index.html`, `models.js`, `pricing.json`, `css/`, `js/`, `images/` sont servis. Sans elle, la configuration rendue — qui contient la clé — était téléchargeable.
- **Liste blanche des routes** : seules `v1/models`, `v1/chat/completions` et `health/liveliness` sont relayées. Sans elle, l'API d'administration du routeur était accessible avec la clé du serveur.
- **Clé dédiée** : une *virtual key* du routeur, limitée aux modèles exposés, avec budget et débit plafonnés.
- **Identité imposée** : `x-litellm-end-user-id` vient d'oauth2-proxy, les en-têtes envoyés par le client sont écrasés. Le routeur suit les dépenses par personne.
- **Contexte côté serveur** : en production, `v1/chat/completions` passe par l'API des discussions, qui injecte la persona, le profil de la personne et la date avant le routeur ; le navigateur ne peut pas les modifier.
- **Recherche web** : la boucle d'outils (recherche, lecture de page, météo) tourne dans l'API, contre le sas `sophia-dmz`. Une page ne peut être lue que si son adresse vient d'un résultat de recherche ou d'un message de la personne : une adresse devinée par le modèle est refusée par le code.
- **Outils en MCP** : l'API est un client MCP ; elle lit la liste des outils de chaque serveur de `SOPHIA_MCP_URLS` (sas web, [outils locaux](../../skills/README.md), modules), affiche l'annonce que chaque outil déclare (icône, libellé), remplit elle-même les paramètres réservés (compte protégé) et insère dans la réponse, après vérification, les images et cartes que l'outil renvoie. Ajouter un outil ne demande aucun changement de l'interface.
- **Modèles par rôle** : `SOPHIA_MODELS_BY_ROLE` (par défaut, enfants et invités sur le modèle local seulement ; un compte sans rôle connu est traité comme invité). Un modèle envoyé par le navigateur hors de la liste reçoit un **403 explicite** et rien ne part vers le routeur : pas de remplacement silencieux. Les appels internes (analyse, reformulation, résumé) reprennent le modèle déjà contrôlé ; le profil n'expose que les modèles permis. La voix passe par une clé virtuelle à part (`LITELLM_AUDIO_API_KEY`), limitée aux deux alias de la voix et posée par nginx sur ses seules routes : la règle est tenue par le routeur, sans analyser le formulaire.
- **Places sur la carte graphique** : les discussions prennent au plus 2 des emplacements du serveur local le jour, 1 de 3 h à 7 h (`SOPHIA_LOCAL_CHAT_PLAGES`) ; l'école n'attend jamais ; une discussion de plus attend 60 s au plus, puis reçoit un message « très occupée ». Les tâches de fond du navigateur (titre, résumé demandé) portent l'en-tête `X-Sophia-Tache: fond` et partent sur l'alias de fond, en relais simple, avec repli sur l'alias principal si le routeur ou la clé le refuse ; le résumé de compaction reste sur l'alias principal, puisqu'il est sur le chemin du message de la personne.
- **Réponse écrite par le service** : un outil MCP peut rendre `_trace` (une ligne affichée avant la réponse) et `_fin` (la réponse finale, affichée telle quelle, sans rappeler le modèle). La décision reste au service qui connaît ses données (par exemple « rien de prévu » sur un créneau vide) : le modèle ne peut plus l'enjoliver.
- **Parcours déclarés par les outils** : un serveur MCP déclare dans les métadonnées de chaque outil son parcours (`sophia/parcours` : `express`, `lecture`, `liste`). Le serveur du chat choisit par règles les outils proposés au modèle, ou appelle lui-même l'outil d'un parcours express et écrit la réponse à partir des messages du service ; un serveur sans parcours déclarés garde l'ancien comportement.
- **Ouvrir une application** : intention `application` de l'analyse, avec des énumérations construites par le serveur pour le rôle de la personne ; décision dans la politique, sur une liste fermée et versionnée (`SOPHIA_APPLICATIONS` : identifiant, nom, adresse de base, pages permises, rôles) ; le serveur écrit la phrase et un **bouton**, et le navigateur n'accepte un bouton d'application que si son adresse commence par une base de la liste. Le clic ouvre ou réutilise un **onglet nommé** par application (un navigateur bloque l'ouverture d'un onglet sans geste de la personne). Réservé aux adultes responsables ; les boutons sont retirés de l'historique envoyé au modèle, qui ne doit jamais écrire une adresse.
- **Fenêtre de contexte** : bornée par modèle (`SOPHIA_CONTEXT_LIMITS`) ; au-delà, les échanges les plus anciens sont résumés, et un fichier trop gros est refusé avec un message clair.
- **API des discussions** : écoute sur `127.0.0.1` seulement, derrière nginx ; l'identité vient des en-têtes posés par nginx.
- **Réseau** : entrée depuis le routeur OpenShift seulement, vers oauth2-proxy ; sortie vers le routeur de modèles, Keycloak, PostgreSQL, Forgejo, le sas web, les serveurs MCP de `sophia-skills` (et des modules) et le DNS.

## Prérequis (secrets)

| Secret | Contenu |
|---|---|
| `forgejo-build-credentials` | accès en lecture au dépôt du front, pour le build |
| `sophia-interface-litellm` | `LITELLM_API_KEY` : virtual key dédiée ; `LITELLM_AUDIO_API_KEY` (facultative) : clé de la voix, limitée à ses deux alias — absente, la voix passe par la clé du pod, avec un avertissement au démarrage |
| `sophia-interface-oauth2` | `client-secret` (client Keycloak) et `cookie-secret` (32 caractères aléatoires) |
| `sophia-chat-db` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` : base des discussions |
| `sophia-chat-forgejo` | `FORGEJO_TOKEN` d'un compte de service Forgejo (`write:repository`, `write:organization`, `read:user`) — facultatif : sans lui, seul le projet global existe |

## Évolutions préparées

| Évolution | Contenu | État |
|---|---|---|
| **Namespace dédié** | l'interface sort du namespace des applications, où l'agent de déploiement est administrateur et pourrait lire ses Secrets : namespace propre avec quota, valeurs par défaut et entrée fermée, entrées des services qu'elle appelle **doublées** pendant la bascule (puis l'ancienne source retirée un jour après), essai par une Route temporaire joignable par le VPN seulement, puis bascule de la Route ; le build clone par une **clé de déploiement en lecture seule** en SSH, jamais avec le jeton d'un administrateur de la forge | conçu, manifestes prêts, non appliqué. Limite : le namespace protège de l'agent de déploiement, pas de l'agent de maintenance, administrateur du cluster |
| **École sur sa propre adresse** | une école servie sous l'origine de la discussion aurait tous les droits de la personne sur la discussion. L'école passe sur son adresse, derrière son propre oauth2-proxy (sans les invités) ; le CORS ne couvre qu'un préfixe d'API (`/api/store/school/`), pour l'origine exacte de l'école ; routes dédiées pour l'avatar, les réactions et la voix, plutôt que le profil (qui modifierait la persona) ou les complétions (qui ouvriraient le modèle) ; cookie de la discussion sans domaine parent ; photos en `Cross-Origin-Resource-Policy: same-site` | en trois étapes compatibles : (a) côté discussion, **en service** ; (b) l'école, codée ; (c) fin de l'ancien chemin |
| **L'interface comme demandeur** | intention `deleguer` (analyse contrainte, règles, confirmation par un clic avec un jeton à usage unique, appel au [répartiteur](../../core/repartiteur/)) ; jeton de la personne relayé et vérifié dès le départ ; quotas par personne ; approbations du plan et des commandes dans l'interface ; suivi dans la discussion | conçu |

## Remarque

Un pod en `hostNetwork` passe à travers les NetworkPolicies (le trafic du nœud est toujours accepté). Tester l'isolement depuis un pod ordinaire.
