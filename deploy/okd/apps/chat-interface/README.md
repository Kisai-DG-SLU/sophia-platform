# Interface de discussion — déploiement de production

Modèle de déploiement d'une interface web de discussion devant le routeur de modèles, **sans aucune clé dans le navigateur** et avec **connexion obligatoire**. Le code du front n'est pas fourni : ce répertoire décrit le conteneur, le proxy et les ressources Kubernetes.

```
Navigateur → Route (TLS) → oauth2-proxy :4180 → nginx :8080 → routeur de modèles (LiteLLM)
                              │ connexion OIDC        │ front statique (liste blanche)
                              └→ Keycloak             │ clé du routeur injectée côté serveur
                                                      └ identité → x-litellm-end-user-id
```

| Fichier | Rôle |
|---|---|
| `Containerfile` | UBI 9 minimal, nginx et python3 du système, UID arbitraire (OpenShift), journaux sur stdout/stderr |
| `entrypoint.sh` | rendu de la configuration puis nginx au premier plan |
| `render-config.py` | injecte la clé du routeur dans `nginx.conf` (mode 600), jamais affichée ; refuse une clé mal formée |
| `render-pricing.py` | lit les tarifs du routeur côté serveur et écrit `pricing.json` pour le calcul du coût dans le front |
| `nginx.conf.in` | gabarit : **liste blanche** des fichiers servis et des routes relayées vers le routeur, en-têtes d'identité imposés |
| `sophia-interface.yaml` | ImageStream, BuildConfig, Deployment (oauth2-proxy + nginx), Service, Route, NetworkPolicy |

## Garde-fous

- **Liste blanche des fichiers** : seuls `/`, `index.html`, `models.js`, `pricing.json`, `css/`, `js/`, `images/` sont servis. Sans elle, la configuration rendue — qui contient la clé — était téléchargeable.
- **Liste blanche des routes** : seules `v1/models`, `v1/chat/completions` et `health/liveliness` sont relayées. Sans elle, l'API d'administration du routeur était accessible avec la clé du serveur.
- **Clé dédiée** : une *virtual key* du routeur, limitée aux modèles exposés, avec budget et débit plafonnés.
- **Identité imposée** : `x-litellm-end-user-id` vient d'oauth2-proxy, les en-têtes envoyés par le client sont écrasés. Le routeur suit les dépenses par personne.
- **Réseau** : entrée depuis le routeur OpenShift seulement, vers oauth2-proxy ; sortie vers le routeur de modèles, Keycloak et le DNS.

## Prérequis (secrets)

| Secret | Contenu |
|---|---|
| `forgejo-build-credentials` | accès en lecture au dépôt du front, pour le build |
| `sophia-interface-litellm` | `LITELLM_API_KEY` : virtual key dédiée |
| `sophia-interface-oauth2` | `client-secret` (client Keycloak) et `cookie-secret` (32 caractères aléatoires) |

## Remarque

Un pod en `hostNetwork` passe à travers les NetworkPolicies (le trafic du nœud est toujours accepté). Tester l'isolement depuis un pod ordinaire.
