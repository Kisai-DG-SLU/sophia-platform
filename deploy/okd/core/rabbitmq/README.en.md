# RabbitMQ — event bus (`sophia-core`)

The platform's event bus: each step of a delegation is published on it by the [dispatcher](../repartiteur/), the **only publisher**, and a visualisation relay reads it live. Agents are **not** clients of the bus: they are executors, reached by the dispatcher only. A single RabbitMQ node on a local volume of the server; the management UI is reachable through the VPN only and **behind Keycloak**, the AMQP port only from the dispatcher and the visualisation relay. Three accounts in all: the dispatcher, the relay, the administrator.

## Choices

| Item | Choice | Reason |
|---|---|---|
| Image | `rabbitmq:4.4.0-management`, pinned | management UI included; no silent upgrade |
| Volume | local PV and PVC **naming each other** (`claimRef` + `volumeName`) | a PVC without a named PV binds to the first free PV that is large enough: in the reference install, it had taken the volume meant for the RAG embeddings |
| RabbitMQ node name | fixed `hostname: rabbitmq` | RabbitMQ names its data directory after the node name; with the pod name, every re-creation started from an empty directory (queues and users lost) |
| Erlang cookie | provided by a Secret, **copied as `0400`** by an initContainer on every start | RabbitMQ refuses to start if anyone but its owner can read the cookie; a directly mounted Secret is owned by root and stays group-readable |
| `fsGroupChangePolicy: OnRootMismatch` | the kubelet no longer re-applies the `fsGroup` on every start | otherwise it makes every file on the volume group-readable — this turned the cookie into `0660` and blocked the pod after a node reboot |
| Memory | `total_memory_available_override_value` **equal to the container limit** (1 Gi) | RabbitMQ reads the node's memory, not the container's: its alarm threshold (60 %) would never fire before the kernel kills the pod |
| Quorum queue log | `raft.wal_max_size_bytes` at 64 MB | 512 MB by default, almost the whole memory threshold of a 1 Gi container |
| Disk | `disk_free_limit.absolute = 1GB` | publishing paused before the system disk is full (50 MB by default) |
| Rollout | `Recreate`, one replica | `ReadWriteOnce` volume: never two RabbitMQ on the same directory |
| Accounts | **definitions imported on every start**: `/sophia` vhost, one account for the dispatcher, one for the visualisation relay, the administrator, permissions; a **secret-free** template in the `ConfigMap`, passwords inserted by an initContainer from a Secret, into an in-memory volume | accounts and permissions are described in the repository and replayed identically; the password is hashed on import; the initContainer fails if a template account has no password |
| Agents | **no account**: the accounts, the `sophia.agent.<name>` queues, the `sophia.agents` exchange and the agents' policy have been removed (empty and without consumers) | agents are executors, reached by the dispatcher only, which is the **only publisher** on `sophia.events` (keys `<requester>.delegate.<event>`, through `topic_permissions`) |
| Visualisation relay | temporary server-named queue (`amq.gen-*`, or `amq_<32 hex>` since RabbitMQ 4.4) bound to `sophia.events`, without publishing | live reading of events, unable to emit anything |
| Internal administrator | in the definitions (Secret `rabbitmq-admin-creds`) | with definitions, RabbitMQ no longer creates `RABBITMQ_DEFAULT_USER` on a fresh volume |
| Management UI | `rabbitmq_auth_backend_oauth2` plugin: realm tokens, **public PKCE** client `rabbitmq`; **password login disabled** (`management.oauth_disable_basic_auth`) | one identity for every console; the dispatcher and the relay keep their internal accounts over AMQP (`auth_backends`: OAuth2, then internal) |
| People's permissions | Keycloak groups (`groups` claim) become scopes (`additional_scopes_key`); only the `admin` group gets a full-permission alias (`scope_aliases.admin`) | a realm account outside the `admin` group has no permission in RabbitMQ |
| Signing keys | `jwks_uri` over **HTTPS** through Keycloak's public name, certificate verified (`hostname_verification = wildcard` for the router's wildcard certificate) | RabbitMQ refuses an HTTP `jwks_uri`, and Keycloak's internal address is HTTP |

## Topology

Delegations go through [Temporal](../temporal/); RabbitMQ only carries **events**. Everything is declared by the definitions import (`00-config.yaml`): no client configures anything.

| Object | Type | Role |
|---|---|---|
| `sophia.events` | `topic` exchange | events (delegation started, finished…), key `<requester>.delegate.<event>`, published by the dispatcher only; read live by the visualisation relay |
| `sophia.dlx` → `sophia.dlq` | `fanout` → quorum queue | dead letters; `sophia-dlq` policy: 30 days, 10,000 messages (oldest dropped); read by the administrator; kept for future durable queues (none today) |

| Account | configure | write | read |
|---|---|---|---|
| dispatcher | nothing | `sophia.events` (keys `<requester>.delegate.<event>`) | nothing |
| visualisation relay | `amq.gen-*`, `amq_<32 hex>` | `amq.gen-*`, `amq_<32 hex>` | `sophia.events`, `amq.gen-*`, `amq_<32 hex>` |
| administrator | everything | everything | everything |

Client side: declare queues and exchanges with `passive=True` (no `configure` permission), manual `ack`, `user_id` = account name (RabbitMQ rejects a different value). An account, queue or binding is added in the template, never from a client.

## Files

| File | Content |
|---|---|
| `00-config.yaml` | `ConfigMap`: plugins, configuration additions (memory, disk, log, OAuth2, definitions import), definitions template |
| `01-storage.yaml` | local PV and PVC naming each other |
| `02-deployment.yaml` | cookie and definitions initContainers, RabbitMQ, probes, limits |
| `03-service.yaml` | AMQP (5672) and management (15672) |
| `04-route.yaml` | management UI, `edge` TLS, HTTP redirected to HTTPS |
| `05-network-policy.yaml` | 15672: router; AMQP: visualisation relay, from its own namespace. The dispatcher's ingress is in [`../repartiteur/04-network-policy.yaml`](../repartiteur/04-network-policy.yaml) |

## Variables

| Variable | Role |
|---|---|
| `${RABBITMQ_HOST}` | DNS name of the management UI, resolving to the VPN address |
| `${IDP_HOST}` | Keycloak's public name (token issuer, signing keys) |
| `${VIEWER_NAMESPACE}` | the visualisation relay's own namespace, with no agent account bound to it |
| `${NODE_NAME}` | node carrying the volume (`oc get nodes`), in `01-storage.yaml` |

Variables are replaced by a named substitution, for instance `envsubst '${NODE_NAME}' < 01-storage.yaml | oc apply -f -`.

## Procedure (administrator)

1. On the node: create the directory and give it the containers' SELinux label (commands at the top of `01-storage.yaml`).
2. Secrets, never committed:
   - `rabbitmq-admin-creds` (keys `username`, `password`): admin account created on first start;
   - `rabbitmq-erlang-cookie` (key `cookie`): `openssl rand -hex 32`, the same on every node if the RabbitMQ cluster grows;
   - `rabbitmq-users` (`sophia-core`): one key per template account (`repartiteur`, `sophia-workflow`), the password as value. Values go through a pipe, never through `oc`'s arguments (visible to `ps`):

```bash
printf 'repartiteur=%s\nsophia-workflow=%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" | oc -n sophia-core create secret generic rabbitmq-users --from-env-file=/dev/stdin
```

3. Keycloak: the realm's `rabbitmq` client ([`../../identity/`](../../identity/)); the namespace EgressFirewall open to `${IDP_HOST}` on 443 ([`../network/policies.yaml`](../network/policies.yaml)) — **without this rule, UI login fails**: the public name resolves to the node, outside the allowed internal networks.
4. `00` to `05`: `--dry-run=server`, then `apply`.
5. Check: pod `Running` and ready, `rabbitmq-diagnostics status` without alarms, `rabbitmqctl list_users`, `list_permissions`, `list_queues name type policy`, `list_exchanges` and `list_bindings` (`-p /sophia`) matching the template, management UI reachable through the VPN (Keycloak login, refused outside the `admin` group), port 5672 refused from any pod other than the dispatcher and the relay.

**Adding an account**: add it to the template in `00-config.yaml`, add its key to `rabbitmq-users`, restart RabbitMQ. An account removed from the template is **not** deleted from the server: see below.

**Server-named queues**: RabbitMQ 4.4 names a queue declared without a name `amq_<32 hex>`, no longer `amq.gen-*`. A permission written for the old form refuses the relay's listening queue (access refused at declaration). The permissions therefore admit both forms; a live fix goes through `rabbitmqctl set_permissions`, without restart, then through the template.

## Removing an account or a queue

**The definitions import deletes nothing**: an account, queue, exchange or policy removed from the template stays on the server. Removal is a separate step, without restart:

1. Apply the new `00-config.yaml` (`oc diff` first: it must only show removals).
2. Check that the queues concerned are empty and without consumers: `rabbitmqctl list_queues -p /sophia name messages consumers`.
3. **Quorum queues**: `rabbitmqctl delete_queue --if-empty` is refused on them (code 69, "not supported by quorum queues"). Re-read the message count in the same command, and delete only at 0:

```bash
for q in ${QUEUES}; do n=$(oc -n sophia-core exec deploy/rabbitmq -- rabbitmqctl list_queues -p /sophia -q --no-table-headers name messages | awk -v q="$q" '$1==q {print $2}'); if [ "$n" = "0" ]; then oc -n sophia-core exec deploy/rabbitmq -- rabbitmqctl delete_queue -p /sophia "$q"; else echo "$q : [$n] message(s), not deleted"; fi; done
```

4. Policies and accounts: `rabbitmqctl clear_policy -p /sophia <policy>`, then `rabbitmqctl delete_user <account>` (its permissions go with it). Once the accounts are deleted, nobody can publish to the remaining queues.
5. **Exchange**: `rabbitmqctl` has no command to delete one; use the management UI (Exchanges, vhost `/sophia`, "Delete this exchange"). Without a bound queue it is harmless: this step can wait.
6. Network rules no longer needed: delete them.
7. Check: `list_queues` and `list_users`, and no new error in the dispatcher's log.

Removed passwords stay **one week** in `rabbitmq-users`: they are what makes rollback possible (re-apply the previous template, then `rollout restart deploy/rabbitmq`: the import recreates queues, accounts and permissions).

**Moving to another volume** (old PVC bound to the wrong PV): first list the directory's content on the node. Then stop RabbitMQ, apply `01-storage.yaml`, switch the Deployment over, and only then delete the old PVC; the PV it held (`Retain`) must be released by hand.

## Next

Delegation events are published by the [dispatcher](../repartiteur/). The visualisation relay rejects any message whose `user_id` is not `repartiteur` (the account name, set and checked by RabbitMQ). Still to do: the event consumers, and widening `topic_permissions` to incident events ([observability](../../../../docs/concepts/10-observabilite.en.md)).
