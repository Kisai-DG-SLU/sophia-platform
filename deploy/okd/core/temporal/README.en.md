# Temporal — agents' durable workflows (`sophia-core`)

Durable execution of delegations between agents: each delegation is a **workflow** whose state is saved at every step; an agent that restarts resumes where it was, a failing step is retried according to its policy. RabbitMQ keeps the **events** ([`../rabbitmq/`](../rabbitmq/)).

## Choices

| Item | Choice | Reason |
|---|---|---|
| Version | server and tools `1.32.1`, pinned | controlled upgrades, one minor version at a time |
| Shape | one pod, four services (frontend, history, matching, worker) and an internal frontend | a single node today; separable through `TEMPORAL_SERVICES` without touching the database (pods find each other through the membership table) |
| Database | `temporal` and `temporal_visibility` in the shared PostgreSQL, `temporal` role | no extra database to operate; connection pool capped per service (at most 28) |
| History shards | **128, irreversible** | set when the database is created: changing it means migrating to another Temporal cluster |
| Entry point | Service `temporal-frontend:7233` (gRPC) | clients: the [dispatcher](../repartiteur/) (only application client; agents have no access to Temporal), the UI, admin Jobs |
| Authorisation | **a Keycloak token on every call**; permissions in the `permissions` claim as `namespace:role` (`sophia:write`, `temporal-system:admin`) | one service account for the dispatcher (`temporal-repartiteur`, `sophia:write`), one for administration; the former per-agent accounts are disabled; no anonymous call; the authenticated author of each signal is recorded in the history (`frontend.enablePrincipalPropagation`) |
| System tasks | internal frontend (7236) without a token, reachable between Temporal pods only | Temporal's official configuration with authorisation |
| Encryption | **verified TLS**, clients and between services: OKD service certificate for `temporal-frontend.sophia-core.svc`, renewed by the cluster | traffic stays encrypted the day services run on several nodes; warning 30 days before expiry, error at 7 days |
| UI | `temporal-ui` behind an **oauth2-proxy** (realm `admin` group), which forwards the ID token | the UI does not filter by group; the server refuses any call without a token |
| Temporal namespace | `sophia` (agents' workflows), 30-day history retention | |

## Files

| File | Content |
|---|---|
| `01-schema-job.yaml` | Job creating and updating the schemas (replayable) |
| `02-server.yaml` | dynamic configuration, certificate authority, server, Services (including the certificate annotation) |
| `03-network-policy.yaml` | ingress to Temporal (dispatcher, UI, Jobs, between Temporal pods) and to Postgres (Temporal); the UI ingress (router) is in `04-ui.yaml` |
| `04-ui.yaml` | UI, oauth2-proxy, `edge` Route |
| `05-namespace-job.yaml` | creates the `sophia` namespace (admin account token) |
| `06-smoke-test-job.yaml` | acceptance test: call without a token refused, then an end-to-end "hello" workflow |
| [`../../identity/temporal-keycloak.py`](../../identity/temporal-keycloak.py) | `temporal` client, `temporal-permissions` scope, service accounts and their Secrets (replayable, `--dry-run`) |
| [`../../identity/clients/`](../../identity/clients/) | `temporal-ui` and `rabbitmq` clients, to import into an existing realm |

Replace the `example.org` domain of Routes and redirect URLs with yours.

## Procedure (administrator)

1. **Role, databases and Secret** — password through standard input, never as an argument:

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

2. **Keycloak**: import `identity/clients/temporal-ui.json` (console, *Clients → Import client*), copy its secret into the `temporal-ui-oauth2` Secret (`client-secret`, and `cookie-secret` = `openssl rand -hex 16`), then `python3 deploy/okd/identity/temporal-keycloak.py --dry-run` and without `--dry-run`. The script creates the service accounts and stores their Secrets (`temporal-agent-<agent>` in the agents' namespace, `temporal-admin-client` in `sophia-core`) without ever printing a secret.
3. **Network, schemas, server and UI** — `identity/02-network.yaml`, `03`, `01` (wait for `complete`), then `02` and `04` **together** (a UI without a token would be refused by the server); `--dry-run=server` first each time.
4. **Namespace and acceptance test**: `05`, then `06`; expected in the test logs: `sans jeton : refusé (attendu)`, then `résultat : Bonjour Sophia`. The UI opens through the VPN for an `admin` group account.

**Upgrade**: new image in `01-schema-job.yaml` (Job name included) and `02-server.yaml`; Job first, server next. Never two minor versions at once.

## Clients

Always with certificate name verification:

- Python SDK: `tls=TLSConfig(server_root_ca_cert=<service-ca.crt>, domain="temporal-frontend.sophia-core.svc")`, token through `api_key`, **renewed** by a long-running worker (the token lives 5 min);
- CLI: `--tls --tls-ca-path …/service-ca.crt --tls-server-name temporal-frontend.sophia-core.svc`;
- UI: `TEMPORAL_TLS_CA`, `TEMPORAL_TLS_SERVER_NAME` **and** `TEMPORAL_TLS_ENABLE_HOST_VERIFICATION=true` — without the latter, any certificate is accepted.

The certificate authority is a `temporal-service-ca` ConfigMap (`inject-cabundle` annotation), one per client namespace.
