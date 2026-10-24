# RabbitMQ — inter-agent messaging (`sophia-core`)

The agents' message bus: each agent receives its requests in its own queue, and a failed request goes to a dead-letter queue instead of vanishing. A single RabbitMQ node on a local volume of the server; the management UI is reachable through the VPN only and **behind Keycloak**, the AMQP port only from the agents' namespace. Each agent has **its own account**, which only reads its own queue.

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
| Accounts | **definitions imported on every start**: `/sophia` vhost, one account per agent and one for the visualisation relay, permissions; a **secret-free** template in the `ConfigMap`, passwords inserted by an initContainer from a Secret, into an in-memory volume | accounts and permissions are described in the repository and replayed identically; the password is hashed on import; the initContainer fails if a template account has no password |
| Agent permissions | no write at all; read of its `sophia.agent.<name>` queue, unused since the dispatcher, until it is removed; configure nothing | agents are executors, reached by the dispatcher only, which is the **only publisher** on `sophia.events` (keys `<requester>.delegate.<event>`, through `topic_permissions`) |
| Visualisation relay | temporary queue (`amq.gen-*`) bound to `sophia.events`, without publishing | live reading of events, unable to emit anything |
| Internal administrator | in the definitions (Secret `rabbitmq-admin-creds`) | with definitions, RabbitMQ no longer creates `RABBITMQ_DEFAULT_USER` on a fresh volume |
| Management UI | `rabbitmq_auth_backend_oauth2` plugin: realm tokens, **public PKCE** client `rabbitmq`; **password login disabled** (`management.oauth_disable_basic_auth`) | one identity for every console; agents keep their internal accounts over AMQP (`auth_backends`: OAuth2, then internal) |
| People's permissions | Keycloak groups (`groups` claim) become scopes (`additional_scopes_key`); only the `admin` group gets a full-permission alias (`scope_aliases.admin`) | a realm account outside the `admin` group has no permission in RabbitMQ |
| Signing keys | `jwks_uri` over **HTTPS** through Keycloak's public name, certificate verified (`hostname_verification = wildcard` for the router's wildcard certificate) | RabbitMQ refuses an HTTP `jwks_uri`, and Keycloak's internal address is HTTP |

## Topology

Delegations between agents go through [Temporal](../temporal/); RabbitMQ only carries **events** and **simple messages**. Everything is declared by the definitions import (`00-config.yaml`): no client configures anything.

| Object | Type | Role |
|---|---|---|
| `sophia.agents` | `direct` exchange | simple message to an agent, routing key = agent name |
| `sophia.agent.<name>` | quorum queue, one per agent | the agent's mailbox; `sophia-agents` policy: dead letters to `sophia.dlx`, at most 5 deliveries, `at-least-once`, 10,000 messages then **publish rejected** (the publisher gets a *nack*: nothing is silently lost) |
| `sophia.events` | `topic` exchange | events (delegation started, finished…), key `<requester>.delegate.<event>`, published by the dispatcher only; read live by the visualisation relay |
| `sophia.dlx` → `sophia.dlq` | `fanout` → quorum queue | dead letters; `sophia-dlq` policy: 30 days, 10,000 messages (oldest dropped); read by the administrator |

| Account | configure | write | read |
|---|---|---|---|
| agent `<name>` | nothing | nothing | `sophia.agent.<name>` |
| dispatcher | nothing | `sophia.events` (keys `<requester>.delegate.<event>`) | nothing |
| visualisation relay | `amq.gen-*` | `amq.gen-*` | `sophia.events`, `amq.gen-*` |
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
| `05-network-policy.yaml` | AMQP: agents' namespace and node network (coding assistant in `hostNetwork`); 15672: router |

## Variables

| Variable | Role |
|---|---|
| `${RABBITMQ_HOST}` | DNS name of the management UI, resolving to the VPN address |
| `${IDP_HOST}` | Keycloak's public name (token issuer, signing keys) |

Replace the node name (`master-0` in `01-storage.yaml`) with the one from `oc get nodes`.

## Procedure (administrator)

1. On the node: create the directory and give it the containers' SELinux label (commands at the top of `01-storage.yaml`).
2. Secrets, never committed:
   - `rabbitmq-admin-creds` (keys `username`, `password`): admin account created on first start;
   - `rabbitmq-erlang-cookie` (key `cookie`): `openssl rand -hex 32`, the same on every node if the RabbitMQ cluster grows;
   - `rabbitmq-users` (`sophia-core`): one key per template account, the password as value; and, for each agent, `rabbitmq-agent-<name>` (`username`, `password`) in the agents' namespace — **the same password**, generated once, without a temporary file:

```bash
ARGS=()
for a in ${AGENTS}; do                    # e.g. "sophia athena hephaistos ouranos dionysos"
  p=$(openssl rand -hex 32)
  ARGS+=(--from-literal=$a=$p)
  oc -n ${NS_AGENTS} create secret generic rabbitmq-agent-$a --from-literal=username=$a --from-literal=password=$p
done
ARGS+=(--from-literal=sophia-workflow=$(openssl rand -hex 32))   # visualisation relay
oc -n sophia-core create secret generic rabbitmq-users "${ARGS[@]}"
unset ARGS p
```

3. Keycloak: the realm's `rabbitmq` client ([`../../identity/`](../../identity/)); the namespace EgressFirewall open to `${IDP_HOST}` on 443 ([`../network/policies.yaml`](../network/policies.yaml)) — **without this rule, UI login fails**: the public name resolves to the node, outside the allowed internal networks.
4. `00` to `05`: `--dry-run=server`, then `apply`.
5. Check: pod `Running` and ready, `rabbitmq-diagnostics status` without alarms, `rabbitmqctl list_users`, `list_permissions`, `list_queues name type policy`, `list_exchanges` and `list_bindings` (`-p /sophia`) matching the template, management UI reachable through the VPN (Keycloak login, refused outside the `admin` group), port 5672 refused from any namespace other than the agents'.

**Adding an account**: add it to the template in `00-config.yaml`, add its key to `rabbitmq-users`, restart RabbitMQ. An account removed from the template is **not** deleted: `rabbitmqctl delete_user`.

**Moving to another volume** (old PVC bound to the wrong PV): first list the directory's content on the node. Then stop RabbitMQ, apply `01-storage.yaml`, switch the Deployment over, and only then delete the old PVC; the PV it held (`Retain`) must be released by hand.

## Next

Delegation events are published by the [dispatcher](../repartiteur/). Still to do: their consumers, and removing the `sophia.agent.<name>` queues and the `sophia.agents` exchange, now unused.
