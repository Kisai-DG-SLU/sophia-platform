# Bureautique — Fichiers et Collabora (`sophia-workspace`) ; chat permanent et visio

Recette de l'installation de référence pour le module [Bureautique](../../../docs/modules/bureautique/documentation.md) : La Suite Drive (« Fichiers », 0.25.3) et Collabora Online (CODE 26.04), dans un namespace dédié. Les choix et leurs raisons sont dans la documentation du module ; ici, les composants, les prérequis, les Secrets et la procédure. Les manifestes de l'installation de référence ne sont pas publiés : ils suivent les manifestes amont de Drive, avec les réglages ci-dessous, rendus par Kustomize.

État : en service ; cette recette est une procédure, sans les manifestes de l'installation de référence ; essais détaillés (second compte, partages, lecture depuis la discussion) à faire.

Le chat permanent et la visio du [module Communication](../../../docs/modules/communication/documentation.md), installés par le même projet dans deux autres namespaces, ont leur recette en fin de page : [Chat permanent et visio](#chat-permanent-et-visio).

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

## Chat permanent et visio

Recette du [module Communication](../../../docs/modules/communication/documentation.md) : Matrix (Synapse 1.163.2, MAS, Element Web, ntfy) dans `sophia-messagerie`, Jitsi Meet (`stable-11248-2` : web, Prosody, Jicofo, JVB) et un adaptateur OIDC → jeton dans `sophia-visio`. Comme pour la bureautique, c'est une procédure, sans les manifestes de l'installation de référence ; les choix et leurs raisons sont dans la documentation du module.

État : **installé, en recette** ; essais avec les appareils du foyer à faire.

### Composants

| Namespace | Objet | Rôle |
|---|---|---|
| `sophia-messagerie` | `synapse` | serveur Matrix, fédération coupée, chiffrement de bout en bout coupé par défaut (`extra_well_known_client_content` → `io.element.e2ee: {default: false}`), médias de 50 Mo au plus sur le volume dédié |
| | `mas` | service d'authentification Matrix, client OIDC du fournisseur d'identité ; les chemins de connexion, de déconnexion et de rafraîchissement de l'API Matrix lui sont routés sur le nom du serveur |
| | `element` | client web, sans adresse externe dans sa configuration |
| | `ntfy` | notifications UnifiedPush, sans texte ni expéditeur |
| `sophia-visio` | `web`, `prosody`, `jicofo`, `jvb` | Jitsi Meet en authentification par jeton ; Jicofo sondé en `exec` (son API de santé n'écoute que sur `127.0.0.1`) |
| | `adaptateur` | connexion OIDC, puis jeton signé de 600 s pour une seule salle ; image construite dans le cluster depuis la forge, figée par empreinte |
| | `jvb-media` | Service `ClusterIP` avec `externalIPs: [${VPN_IP}]`, port `${JVB_UDP_PORT}/UDP` ; **pas de NodePort** |

Réglages de Jitsi à retenir : `ENABLE_THIRD_PARTY_REQUESTS=false`, pair-à-pair coupé, `JVB_ADVERTISE_PRIVATE_CANDIDATES=false`, `ENABLE_COLIBRI_WEBSOCKET=0` (canal de pont par SCTP), `S6_YES_I_WANT_A_WORLD_WRITABLE_RUN_BECAUSE_KUBERNETES=1` pour l'UID arbitraire, sans privilège ni `anyuid`.

### Prérequis

| # | Objet | Recette |
|---|---|---|
| 0 | **Socle** de chaque namespace, appliqué en premier : Namespace, `ResourceQuota`, `LimitRange`, EgressFirewall, `default-deny`, `allow-dns` ; aucune RoleBinding d'agent | ci-dessous |
| 1 | Classe de la bureautique pour tous les pods, classe de la voix pour JVB | [`../cluster/`](../cluster/README.md) |
| 2 | Bases `synapse` (collation `C`, depuis `template0`) et `mas`, un rôle propriétaire chacune ; entrée de PostgreSQL depuis `sophia-messagerie` | [`../core/postgres18/`](../core/postgres18/README.md) |
| 3 | Clients OIDC `matrix` et `jitsi`, rôle de client d'accès, flux qui refuse le groupe des invités | [`../identity/`](../identity/README.md) |
| 4 | Volume logique dédié aux médias de Synapse (10 Gio), PV `Retain` | [`../../stockage-persistant.md`](../../stockage-persistant.md) |
| 5 | Règle UDP du pont média dans la table nftables du VPN | [`../host/wireguard/`](../host/wireguard/README.md#6-média-de-la-visio) |

### Réseau

- **Entrée** : depuis le routeur pour les pages et les API ; JVB depuis `${VPN_NETWORK}` seulement, en UDP sur `${JVB_UDP_PORT}`.
- **Sortie** : Synapse vers MAS et ntfy ; MAS et l'adaptateur vers le nom public du fournisseur d'identité, en 443, par le routeur ; JVB en UDP vers `${VPN_NETWORK}` seulement (réponses aux appareils), dans sa NetworkPolicy **et** dans l'EgressFirewall du socle, avant la règle de refus.
- Le pont média n'utilise pas de NodePort : un NodePort serait joignable depuis le réseau local, et le pod n'y verrait que l'adresse de jonction d'OVN-Kubernetes. L'`externalIP` sur l'adresse VPN, comme la forge, n'est joignable que par le VPN et garde l'adresse réelle du client.

### Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${MATRIX_HOST}` | nom du serveur Matrix (API et `.well-known`) | `matrix.apps.example.org` |
| `${MAS_HOST}` | nom du service d'authentification | `account.apps.example.org` |
| `${ELEMENT_HOST}` | nom du client web | `chat.apps.example.org` |
| `${NTFY_HOST}` | nom du relais de notifications | `ntfy.apps.example.org` |
| `${VISIO_HOST}` | nom de la visio (pages et adaptateur) | `meet.apps.example.org` |
| `${VPN_IP}`, `${VPN_NETWORK}` | adresse du nœud sur le VPN, réseau du VPN ([`../host/wireguard/`](../host/wireguard/README.md)) | `192.0.2.1`, `192.0.2.0/24` |
| `${JVB_UDP_PORT}` | port UDP du média | un port libre du nœud |

### Secrets (contenu, jamais de valeur)

| Secret | Contenu |
|---|---|
| `sophia-messagerie/synapse` | mot de passe de la base, secret partagé avec MAS, secrets internes de Synapse |
| `sophia-messagerie/mas` | mot de passe de la base, secret du client OIDC, clés de chiffrement et de signature (une RSA, une EC), secret partagé avec Synapse |
| `sophia-visio/adaptateur-visio` | secret du client OIDC (clé `client-secret`) |
| `sophia-visio/jitsi` | mots de passe internes des composants de Jitsi, secret de signature des jetons de salle (clé `jwt-secret`) |

Chaque valeur est générée sur place et écrite par un tube, sans saut de ligne final ; le secret partagé entre Synapse et MAS est recopié de Secret à Secret. Contrôles : noms des clés, longueurs, et **égalité des deux copies par empreintes**, jamais par affichage. Synapse lit ses secrets par des chemins de fichiers et le mot de passe de sa base par `PGPASSWORD` (libpq ignore un fichier de mots de passe lisible par le groupe, ce que sont les Secrets montés) ; MAS lit chaque secret dans un fichier.

### Procédure

1. **Socles** (étape 0) : `oc diff`, `--dry-run=server`, `oc apply` ; contrôle champ à champ ; aucune RoleBinding hors de celles créées par OKD.
2. **Prérequis 1 à 5** en place ; un point manque : s'arrêter.
3. **Secrets**, écrits par tube, sans variable ni affichage (ci-dessus).
4. **Chat** : `oc diff -k`, dry-run serveur, `oc apply -k`, attente des déploiements. Contrôles par le vrai chemin : `.well-known` avec `io.element.e2ee` à `false`, `versions` de l'API, flux de connexion servis par MAS, découverte OIDC de MAS, ntfy, Element. Connexion d'un compte admis (deux pages de MAS à la première fois), refus d'un invité, salon créé sans cadenas.
5. **Visio** : build de l'adaptateur, puis `oc apply -k`. Contrôles : pods prêts ; JVB annonce l'adresse VPN et est joint par Jicofo ; `config.js` sans requête tierce, pair-à-pair coupé ; adaptateur en bonne santé ; essai à deux appareils au moins, invité refusé, **compteur de la règle nftables qui augmente**.

### Retour arrière

`oc delete -k` sur le chat ou la visio : la base, le volume des médias et les Secrets restent. Socles, bases, clients OIDC et règle nftables : suppressions par l'administrateur, selon leurs recettes.
