# Temporal — workflows durables des agents (`sophia-core`)

Exécution durable des délégations entre agents : chaque délégation est un **workflow** dont l'état est sauvegardé à chaque étape ; un agent qui redémarre reprend où il en était, une étape qui échoue est rejouée selon sa politique. RabbitMQ garde les **événements** ([`../rabbitmq/`](../rabbitmq/)).

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Version | serveur et outils `1.32.1`, figés | montée de version maîtrisée, une version mineure à la fois |
| Forme | un pod, quatre services (frontend, history, matching, worker) et un frontend interne | un seul nœud aujourd'hui ; séparables par `TEMPORAL_SERVICES` sans toucher à la base (les pods se trouvent par la table d'appartenance) |
| Base | `temporal` et `temporal_visibility` dans le PostgreSQL partagé, rôle `temporal` | pas de base de plus à exploiter ; pool de connexions borné par service (au plus 28) |
| Shards de l'historique | **128, irréversible** | fixé à la création de la base : en changer veut dire migrer vers un autre cluster Temporal |
| Point d'entrée | Service `temporal-frontend:7233` (gRPC) | clients : le [répartiteur](../repartiteur/) (seul client applicatif ; les agents n'ont aucun accès à Temporal), l'interface, les Jobs d'administration |
| Autorisation | **jeton Keycloak à chaque appel** ; droits dans le claim `permissions` sous la forme `namespace:rôle` (`sophia:write`, `temporal-system:admin`) | un compte de service pour le répartiteur (`temporal-repartiteur`, `sophia:write`), un pour l'administration ; les anciens comptes par agent sont désactivés ; aucun appel anonyme ; l'auteur authentifié de chaque signal est inscrit dans l'historique (`frontend.enablePrincipalPropagation`) |
| Tâches système | frontend interne (7236) sans jeton, joignable entre pods Temporal seulement | configuration officielle de Temporal avec autorisation |
| Chiffrement | **TLS vérifié**, clients et entre services : certificat de service d'OKD pour `temporal-frontend.sophia-core.svc`, renouvelé par le cluster | le trafic reste chiffré le jour où les services seront sur plusieurs nœuds ; avertissement 30 j avant l'expiration, erreur à 7 j |
| Interface | `temporal-ui` derrière un **oauth2-proxy** (groupe `admin` du realm), qui transmet le jeton d'identité | l'interface ne filtre pas par groupe ; le serveur refuse tout appel sans jeton |
| Namespace Temporal | `sophia` (workflows des agents), rétention de l'historique 30 j | |

## Fichiers

| Fichier | Contenu |
|---|---|
| `01-schema-job.yaml` | Job de création et de mise à jour des schémas (rejouable) |
| `02-server.yaml` | configuration dynamique, autorité de certification, serveur, Services (dont l'annotation du certificat) |
| `03-network-policy.yaml` | entrée de Temporal (répartiteur, interface, Jobs, entre pods Temporal) et de Postgres (Temporal) ; l'entrée de l'interface (routeur) est dans `04-ui.yaml` |
| `04-ui.yaml` | interface, oauth2-proxy, Route `edge` |
| `05-namespace-job.yaml` | création du namespace `sophia` (jeton du compte d'administration) |
| `06-smoke-test-job.yaml` | recette : appel sans jeton refusé, puis un workflow « bonjour » de bout en bout |
| [`../../identity/temporal-keycloak.py`](../../identity/temporal-keycloak.py) | client `temporal`, scope `temporal-permissions`, comptes de service et leurs Secrets (rejouable, `--dry-run`) |
| [`../../identity/clients/`](../../identity/clients/) | clients `temporal-ui` et `rabbitmq`, à importer sur un realm existant |

Le domaine `example.org` des Routes et des adresses de redirection se remplace par le vôtre.

## Procédure (l'administrateur)

1. **Rôle, bases et Secret** — mot de passe par l'entrée standard, jamais en argument :

```bash
T_DB_PASS=$(openssl rand -base64 30 | tr -d '/+=' | cut -c1-32)
oc create secret generic temporal-db -n sophia-core \
  --from-literal=username=temporal --from-literal=password="$T_DB_PASS"
oc exec -i -n sophia-core deploy/postgres-sophia -- psql -v ON_ERROR_STOP=1 <<SQL
CREATE ROLE temporal LOGIN PASSWORD '$T_DB_PASS';
CREATE DATABASE temporal OWNER temporal;
CREATE DATABASE temporal_visibility OWNER temporal;
REVOKE ALL ON DATABASE temporal FROM PUBLIC;
REVOKE ALL ON DATABASE temporal_visibility FROM PUBLIC;
SQL
unset T_DB_PASS
```

2. **Keycloak** : importer `identity/clients/temporal-ui.json` (console, *Clients → Import client*), copier son secret dans le Secret `temporal-ui-oauth2` (`client-secret`, et `cookie-secret` = `openssl rand -hex 16`), puis `python3 deploy/okd/identity/temporal-keycloak.py --dry-run` et sans `--dry-run`. Le script crée les comptes de service et pose leurs Secrets (`temporal-agent-<agent>` dans le namespace des agents, `temporal-admin-client` dans `sophia-core`) sans jamais afficher un secret.
3. **Réseau, schémas, serveur et interface** — `identity/02-network.yaml`, `03`, `01` (attendre `complete`), puis `02` et `04` **ensemble** (l'interface sans jeton serait refusée par le serveur) ; `--dry-run=server` d'abord à chaque fois.
4. **Namespace et recette** : `05`, puis `06` ; attendu dans les journaux de la recette : `sans jeton : refusé (attendu)`, puis `résultat : Bonjour Sophia`. L'interface s'ouvre par le VPN pour un compte du groupe `admin`.

**Montée de version** : nouvelle image dans `01-schema-job.yaml` (nom du Job compris) et `02-server.yaml` ; Job d'abord, serveur ensuite. Jamais deux versions mineures d'un coup.

## Clients

Toujours avec vérification du nom du certificat :

- SDK Python : `tls=TLSConfig(server_root_ca_cert=<service-ca.crt>, domain="temporal-frontend.sophia-core.svc")`, jeton par `api_key`, **renouvelé** par un worker durable (le jeton vit 5 min) ;
- CLI : `--tls --tls-ca-path …/service-ca.crt --tls-server-name temporal-frontend.sophia-core.svc` ;
- interface : `TEMPORAL_TLS_CA`, `TEMPORAL_TLS_SERVER_NAME` **et** `TEMPORAL_TLS_ENABLE_HOST_VERIFICATION=true` — sans cette dernière, tout certificat est accepté.

L'autorité de certification est un ConfigMap `temporal-service-ca` (annotation `inject-cabundle`), un par namespace client.
