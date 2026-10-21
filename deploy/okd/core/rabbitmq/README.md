# RabbitMQ — communication entre agents (`sophia-core`)

Le bus de messages des agents : chaque agent reçoit ses demandes dans sa file, et une demande qui échoue part dans une file de rebut au lieu de disparaître. Un seul nœud RabbitMQ, sur un volume local du serveur ; l'interface d'administration n'est joignable que par le VPN, le port AMQP que depuis le namespace des agents.

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

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-config.yaml` | `ConfigMap` : compléments à la configuration de l'image (mémoire, disque, journal) |
| `01-storage.yaml` | PV local et PVC désignés l'un l'autre |
| `02-deployment.yaml` | initContainer du cookie, RabbitMQ, sondes, limites |
| `03-service.yaml` | AMQP (5672) et administration (15672) |
| `04-route.yaml` | interface d'administration, TLS `edge`, HTTP redirigé vers HTTPS |
| `05-network-policy.yaml` | AMQP ouvert au seul namespace des agents |

## Variables

| Variable | Rôle |
|---|---|
| `${RABBITMQ_HOST}` | nom DNS de l'interface d'administration, résolu vers l'adresse du VPN |

Le nom du nœud (`master-0` dans `01-storage.yaml`) se remplace par celui de `oc get nodes`.

## Procédure (l'administrateur)

1. Sur le nœud : créer le répertoire et lui donner l'étiquette SELinux des conteneurs (commandes en tête de `01-storage.yaml`).
2. Secrets, jamais versionnés :
   - `rabbitmq-admin-creds` (clés `username`, `password`) : compte d'administration créé au premier démarrage ;
   - `rabbitmq-erlang-cookie` (clé `cookie`) : `openssl rand -hex 32`, identique pour tous les nœuds si le cluster RabbitMQ s'agrandit.
3. `00` à `05` : `--dry-run=server`, puis `apply`.
4. Vérifier : pod `Running` et prêt, `rabbitmq-diagnostics status` sans alarme, interface d'administration joignable par le VPN, port 5672 refusé depuis un autre namespace que celui des agents.

**Changer de volume** (ancienne PVC liée au mauvais PV) : relever d'abord le contenu du répertoire sur le nœud. Puis arrêter RabbitMQ, appliquer `01-storage.yaml`, basculer le Deployment, et seulement ensuite supprimer l'ancienne PVC ; le PV qu'elle occupait (`Retain`) reste à libérer à la main.

## Suite

Le vhost `/sophia` est créé au démarrage. Restent les comptes techniques par agent, les files `sophia.agent.<cible>` avec une file de rebut par agent, le format des messages et l'intégration dans les agents.
