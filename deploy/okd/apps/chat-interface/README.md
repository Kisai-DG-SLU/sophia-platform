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
- **Fenêtre de contexte** : bornée par modèle (`SOPHIA_CONTEXT_LIMITS`) ; au-delà, les échanges les plus anciens sont résumés, et un fichier trop gros est refusé avec un message clair.
- **API des discussions** : écoute sur `127.0.0.1` seulement, derrière nginx ; l'identité vient des en-têtes posés par nginx.
- **Réseau** : entrée depuis le routeur OpenShift seulement, vers oauth2-proxy ; sortie vers le routeur de modèles, Keycloak, PostgreSQL, Forgejo, le sas web, les serveurs MCP de `sophia-skills` (et des modules) et le DNS.

## Prérequis (secrets)

| Secret | Contenu |
|---|---|
| `forgejo-build-credentials` | accès en lecture au dépôt du front, pour le build |
| `sophia-interface-litellm` | `LITELLM_API_KEY` : virtual key dédiée |
| `sophia-interface-oauth2` | `client-secret` (client Keycloak) et `cookie-secret` (32 caractères aléatoires) |
| `sophia-chat-db` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` : base des discussions |
| `sophia-chat-forgejo` | `FORGEJO_TOKEN` d'un compte de service Forgejo (`write:repository`, `write:organization`, `read:user`) — facultatif : sans lui, seul le projet global existe |

## Remarque

Un pod en `hostNetwork` passe à travers les NetworkPolicies (le trafic du nœud est toujours accepté). Tester l'isolement depuis un pod ordinaire.
