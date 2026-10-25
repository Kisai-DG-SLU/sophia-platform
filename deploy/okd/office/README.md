# Bureautique — Fichiers et Collabora (`sophia-workspace`)

Recette de l'installation de référence pour le module [Bureautique](../../../docs/modules/bureautique/documentation.md) : La Suite Drive (« Fichiers », 0.25.3) et Collabora Online (CODE 26.04), dans un namespace dédié. Les choix et leurs raisons sont dans la documentation du module ; ici, les composants, les prérequis, les Secrets et la procédure. Les manifestes de l'installation de référence ne sont pas publiés : ils suivent les manifestes amont de Drive, avec les réglages ci-dessous, rendus par Kustomize.

État : en service ; cette recette est une procédure, sans les manifestes de l'installation de référence ; essais détaillés (second compte, partages, lecture depuis la discussion) à faire.

## Composants

| Objet | Rôle |
|---|---|
| `valkey` | file de tâches et cache de Fichiers, sans persistance ; protégé par mot de passe |
| `fichiers-backend`, `-worker`, `-beat` | API Django de Fichiers, tâches de fond, planificateur |
| `fichiers-frontend` | interface web |
| `fichiers-nginx` | point d'entrée unique : Route `${FICHIERS_HOST}`, médias par sous-requête d'autorisation, interface de Collabora, port WOPI interne en TLS ; un second serveur sur `${API_INTERNAL_PORT}` pour l'outil MCP (overlay, ci-dessous) |
| `collabora` | éditeur, sans capacité Linux, isolation par Landlock, clé de preuve WOPI montée depuis un Secret |
| CA du service-ca | injectée pour vérifier le TLS interne : WOPI (Collabora → Fichiers) et API S3 |
| NetworkPolicies | règles internes au namespace ; Collabora ne sort que vers le port WOPI et le DNS |
| Jobs `migrate`, `configure-wopi` | migrations, puis enregistrement de Collabora auprès de Fichiers ; créés avec `oc create`, hors de Kustomize |

Flux : navigateur → Route edge → `fichiers-nginx` → interface, API, S3 (médias, après autorisation de l'API), Collabora. Téléversement : PUT présigné du navigateur vers `https://${S3_HOST}`. WOPI : Collabora → Service `fichiers-wopi` en TLS (certificat du service-ca) → API. Le schéma et l'hôte sont conservés jusqu'à l'API, qui vérifie la signature de Collabora sur l'URL exacte.

## Prérequis

| # | Objet | Recette |
|---|---|---|
| 1 | PriorityClass `sophia-workspace-low` (50 000, sans préemption) | [`../cluster/`](../cluster/README.md) |
| 2 | Namespace, `ResourceQuota` (de quoi couvrir les Jobs et le pod de plus d'une mise à jour progressive), `LimitRange` | [`../cluster/`](../cluster/README.md) |
| 3 | Seau `fichiers` versionné, CORS de `https://${FICHIERS_HOST}`, identité S3 propre, corbeille de 30 jours | [`../storage/`](../storage/README.md) |
| 4 | Rôle et base `fichiers` dans PostgreSQL **18** (≥ 16 exigé), extensions `ltree`, `pg_trgm`, `fuzzystrmatch`, `unaccent` créées par le rôle lui-même (toutes « trusted ») ; entrée de la base depuis les pods `fichiers-*` seulement | [`../core/`](../core/README.md) |
| 5 | Client OIDC confidentiel `fichiers` : flux standard, PKCE S256, retour `https://${FICHIERS_HOST}/api/v1.0/callback/`, mappeur `groups` ; entrée du fournisseur d'identité depuis l'API et le worker | [`../identity/`](../identity/README.md) |

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${FICHIERS_HOST}` | nom DNS de Fichiers, résolu vers l'adresse du VPN ; son origine est le `${FILES_ORIGIN}` de [`../storage/`](../storage/README.md) | `files.apps.example.org` |
| `${S3_HOST}` | Route du S3, pour les téléversements présignés (même variable que [`../storage/`](../storage/README.md)) | `s3.apps.example.org` |
| `${S3_INTERNAL_URL}` | API S3 interne, en TLS du service-ca (adresse interne de [`../storage/`](../storage/README.md)) | `https://s3.sophia-storage.svc:9000` |
| `${API_INTERNAL_PORT}` | port interne réservé à l'API pour jeton relayé | un port libre du pod, distinct du port public |

## Secrets (noms et clés, jamais de valeur)

| Secret | Clés |
|---|---|
| `valkey` | `password` |
| `fichiers` | `DJANGO_SECRET_KEY`, `OIDC_RP_CLIENT_SECRET`, `DB_PASSWORD`, `AWS_S3_ACCESS_KEY_ID`, `AWS_S3_SECRET_ACCESS_KEY`, `REDIS_URL`, `DJANGO_CELERY_BROKER_URL` |
| `collabora-proof-key` | `proof_key` (clé RSA, générée et passée par un tube) |
| `fichiers-wopi-tls` | créé par le service-ca d'OKD (annotation du Service) |

Les valeurs sont produites sur place (mot de passe du rôle, secret du client OIDC, clés S3), gardées dans des variables du shell sans être affichées, et passées par l'entrée standard (`printf … | oc create secret generic … --from-env-file=/dev/stdin`), **dans un seul terminal**. Seules les longueurs sont affichées pour contrôle.

## Réglages notables

- **Collabora** : `always_save_on_exit=true`, `idle_timeout_secs=1800`, `max_concurrency=2`, `cleanup.limit_dirty_mem_mb=1024` ; sonde sur `/`.
- **nginx** : en-têtes `X-Forwarded-*` vidés vers le S3 (sinon la signature est vérifiée sur l'hôte public) ; `location ~ ^/cool` après la regex du WebSocket ; format de journal qui masque les jetons WOPI. Le serveur interne reprend les `proxy_set_header` du serveur public, `X-Forwarded-Proto: https` compris (sinon l'API, en production, répond 301 vers https).
- **Pods** : `restricted-v2`, classe `sophia-workspace-low`, images figées par empreinte.

## Overlay « API externe » (pour l'outil MCP « fichiers »)

Une fois l'outil en place, Fichiers s'applique **toujours par l'overlay**, jamais par la base seule (qui retirerait le port interne, les réglages de l'API et le secret d'introspection, et l'outil tomberait) :

- un second serveur nginx sur `${API_INTERNAL_PORT}`, qui ne sert que `GET` sur l'API externe et, pour la lecture du contenu, une location de médias autorisée par l'action `media_auth` de cette API ; le port public répond 404 sur ce chemin ; aucune Route ;
- côté API : serveur de ressources OIDC actif, introspection par le client `fichiers`, audience permise = le client de l'outil, liste blanche `EXTERNAL_API` en lecture (`list`, `retrieve`, `children`, `search`, `breadcrumb`, `media_auth` ; `users.get_me`) ;
- une NetworkPolicy qui n'ouvre ce port qu'au pod de l'outil.

Côté outil et fournisseur d'identité : [`../skills/`](../skills/README.md) et [Relais de l'identité](../../../docs/concepts/12-relais-identite.md).

## Procédure

1. **Prérequis en place** : PriorityClass, namespace, quota, Service S3, versioning et CORS du seau, entrées de la base et du fournisseur d'identité. Un point manque : s'arrêter.
2. **Lecture du rendu** : `oc kustomize`, `oc diff -k`, `oc apply -k … --dry-run=server`. Attendu : uniquement des créations dans le namespace, aucun refus de quota, de SCC ni de PriorityClass.
3. **Base, client OIDC et Secrets**, dans le même terminal (ci-dessus).
4. **Application** : `oc apply -k` ; Valkey, Collabora et nginx prêts ; l'API redémarre tant que la base n'est pas migrée.
5. **Jobs** : `migrate`, puis `configure-wopi` ; tous les pods `Running`.
6. **Contrôles** : SCC `restricted-v2` et classe de priorité de chaque pod ; Landlock actif dans le journal de Collabora ; nginx démarré sans erreur ; quota sous ses plafonds ; plus d'erreur de clé de preuve.
7. **Vrai chemin**, par le VPN : connexion SSO ; création d'un dossier ; téléversement et aperçu d'une image ; un document ouvert dans Collabora à deux navigateurs ; nouvelle version visible dans le seau ; avec un second compte, les éléments du premier sont invisibles (ni liste, ni adresse directe), puis visibles en lecture après un partage « Lecteur ».

## Retour arrière

`oc delete -k` et suppression des Jobs : les données restent (fichiers dans le seau versionné, schéma dans la base), les Secrets aussi. Un seul composant : `oc scale … --replicas=0`. Base, rôle et client OIDC : suppressions par l'administrateur, selon leurs recettes.
