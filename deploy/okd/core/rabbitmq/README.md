# RabbitMQ — communication entre agents (`sophia-core`)

Le bus de messages des agents : chaque agent reçoit ses demandes dans sa file, et une demande qui échoue part dans une file de rebut au lieu de disparaître. Un seul nœud RabbitMQ, sur un volume local du serveur ; l'interface d'administration n'est joignable que par le VPN et **derrière Keycloak**, le port AMQP que depuis le namespace des agents. Chaque agent a **son compte**, qui ne lit que sa file.

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Image | `rabbitmq:4.4.0-management`, version figée | interface d'administration incluse ; pas de mise à jour silencieuse |
| Volume | PV local et PVC **désignés l'un l'autre** (`claimRef` + `volumeName`) | une PVC sans PV désigné se lie au premier PV libre assez grand : dans l'installation de référence, elle avait pris le volume prévu pour les embeddings du RAG |
| Nom de nœud RabbitMQ | `hostname: rabbitmq` fixe | RabbitMQ nomme son répertoire de données d'après le nom du nœud ; avec le nom du pod, chaque recréation repartait d'un répertoire vide (files et comptes perdus) |
| Cookie Erlang | fourni par un Secret, **copié en `0400`** par un initContainer à chaque démarrage | RabbitMQ refuse de démarrer si le cookie est lisible par un autre que son propriétaire ; un Secret monté directement appartient à root et reste lisible par le groupe |
| `fsGroupChangePolicy: OnRootMismatch` | le kubelet ne réapplique plus le `fsGroup` à chaque démarrage | sinon il rend chaque fichier du volume lisible par le groupe — c'est ce qui a fait passer le cookie en `0660` et bloqué le pod après un redémarrage du nœud |
| Mémoire | `total_memory_available_override_value` **égal à la limite du conteneur** (1 Gi) | RabbitMQ lit la mémoire du nœud, pas celle du conteneur : son seuil d'alerte (60 %) ne se déclencherait jamais avant que le noyau ne tue le pod |
| Journal des files quorum | `raft.wal_max_size_bytes` à 64 Mo | 512 Mo par défaut, presque tout le seuil mémoire d'un conteneur de 1 Gi |
| Disque | `disk_free_limit.absolute = 1GB` | publications suspendues avant que le disque système ne soit plein (50 Mo par défaut) |
| Déploiement | `Recreate`, une réplique | volume `ReadWriteOnce` : jamais deux RabbitMQ sur le même répertoire |
| Comptes | **définitions importées à chaque démarrage** : vhost `/sophia`, un compte par agent et un pour le relais de visualisation, droits ; gabarit **sans secret** dans le `ConfigMap`, mots de passe insérés par un initContainer depuis un Secret, dans un volume en mémoire | les comptes et leurs droits sont décrits dans le dépôt et rejoués à l'identique ; le mot de passe est haché à l'import ; l'initContainer échoue si un compte du gabarit n'a pas de mot de passe |
| Droits d'un agent | publier sur `sophia.agents` et `sophia.events` ; lire sa seule file `sophia.agent.<nom>` ; ne rien configurer | pas d'écriture sur l'exchange par défaut : un agent ne peut pas déposer dans la file d'un autre ; droits provisoires, revus avec la topologie des événements |
| Relais de visualisation | file temporaire (`amq.gen-*`) liée à `sophia.events`, sans publier | lecture en direct des événements, sans rien pouvoir émettre |
| Administrateur interne | dans les définitions (Secret `rabbitmq-admin-creds`) | avec des définitions, RabbitMQ ne crée plus `RABBITMQ_DEFAULT_USER` sur un volume neuf |
| Interface d'administration | plugin `rabbitmq_auth_backend_oauth2` : jetons du realm, client **public PKCE** `rabbitmq` ; **connexion par mot de passe désactivée** (`management.oauth_disable_basic_auth`) | une seule identité pour toutes les consoles ; les agents gardent leurs comptes internes en AMQP (`auth_backends` : OAuth2, puis interne) |
| Droits des personnes | les groupes Keycloak (claim `groups`) deviennent des scopes (`additional_scopes_key`) ; seul le groupe `admin` reçoit un alias de droits complets (`scope_aliases.admin`) | un compte du realm hors du groupe `admin` n'a aucun droit dans RabbitMQ |
| Clés de signature | `jwks_uri` en **HTTPS** par le nom public de Keycloak, certificat vérifié (`hostname_verification = wildcard` pour le certificat joker du routeur) | RabbitMQ refuse un `jwks_uri` en HTTP, or l'adresse interne de Keycloak est en HTTP |

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-config.yaml` | `ConfigMap` : plugins, compléments à la configuration (mémoire, disque, journal, OAuth2, import des définitions), gabarit des définitions |
| `01-storage.yaml` | PV local et PVC désignés l'un l'autre |
| `02-deployment.yaml` | initContainers du cookie et des définitions, RabbitMQ, sondes, limites |
| `03-service.yaml` | AMQP (5672) et administration (15672) |
| `04-route.yaml` | interface d'administration, TLS `edge`, HTTP redirigé vers HTTPS |
| `05-network-policy.yaml` | AMQP : namespace des agents et réseau du nœud (assistant de code en `hostNetwork`) ; 15672 : routeur |

## Variables

| Variable | Rôle |
|---|---|
| `${RABBITMQ_HOST}` | nom DNS de l'interface d'administration, résolu vers l'adresse du VPN |
| `${IDP_HOST}` | nom public de Keycloak (émetteur des jetons, clés de signature) |

Le nom du nœud (`master-0` dans `01-storage.yaml`) se remplace par celui de `oc get nodes`.

## Procédure (l'administrateur)

1. Sur le nœud : créer le répertoire et lui donner l'étiquette SELinux des conteneurs (commandes en tête de `01-storage.yaml`).
2. Secrets, jamais versionnés :
   - `rabbitmq-admin-creds` (clés `username`, `password`) : compte d'administration créé au premier démarrage ;
   - `rabbitmq-erlang-cookie` (clé `cookie`) : `openssl rand -hex 32`, identique pour tous les nœuds si le cluster RabbitMQ s'agrandit ;
   - `rabbitmq-users` (`sophia-core`) : une clé par compte du gabarit, le mot de passe en valeur ; et, pour chaque agent, `rabbitmq-agent-<nom>` (`username`, `password`) dans le namespace des agents — **le même mot de passe**, généré une fois, sans fichier temporaire :

```bash
ARGS=()
for a in ${AGENTS}; do                    # ex. "sophia athena hephaistos ouranos dionysos"
  p=$(openssl rand -hex 32)
  ARGS+=(--from-literal=$a=$p)
  oc -n ${NS_AGENTS} create secret generic rabbitmq-agent-$a --from-literal=username=$a --from-literal=password=$p
done
ARGS+=(--from-literal=sophia-workflow=$(openssl rand -hex 32))   # relais de visualisation
oc -n sophia-core create secret generic rabbitmq-users "${ARGS[@]}"
unset ARGS p
```

3. Keycloak : client `rabbitmq` du realm ([`../../identity/`](../../identity/)) ; EgressFirewall du namespace ouvert vers `${IDP_HOST}` en 443 ([`../network/policies.yaml`](../network/policies.yaml)) — **sans cette règle, la connexion à l'interface échoue** : le nom public résout vers le nœud, hors des réseaux internes autorisés.
4. `00` à `05` : `--dry-run=server`, puis `apply`.
5. Vérifier : pod `Running` et prêt, `rabbitmq-diagnostics status` sans alarme, `rabbitmqctl list_users` et `list_permissions -p /sophia` conformes au gabarit, interface d'administration joignable par le VPN (connexion par Keycloak, refusée hors du groupe `admin`), port 5672 refusé depuis un autre namespace que celui des agents.

**Ajouter un compte** : l'ajouter au gabarit de `00-config.yaml`, ajouter sa clé à `rabbitmq-users`, redémarrer RabbitMQ. Un compte retiré du gabarit n'est **pas** supprimé : `rabbitmqctl delete_user`.

**Changer de volume** (ancienne PVC liée au mauvais PV) : relever d'abord le contenu du répertoire sur le nœud. Puis arrêter RabbitMQ, appliquer `01-storage.yaml`, basculer le Deployment, et seulement ensuite supprimer l'ancienne PVC ; le PV qu'elle occupait (`Retain`) reste à libérer à la main.

## Suite

Restent la topologie des événements (exchanges `sophia.agents` et `sophia.events`, files quorum `sophia.agent.<nom>`, file de rebut), le format des messages et l'intégration dans les agents ; les délégations entre agents passent par [Temporal](../temporal/).
