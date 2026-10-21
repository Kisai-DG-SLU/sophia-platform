# RabbitMQ — inter-agent messaging (`sophia-core`)

The agents' message bus: each agent receives its requests in its own queue, and a failed request goes to a dead-letter queue instead of vanishing. A single RabbitMQ node on a local volume of the server; the management UI is reachable through the VPN only, the AMQP port only from the agents' namespace.

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

## Files

| File | Content |
|---|---|
| `00-config.yaml` | `ConfigMap`: additions to the image configuration (memory, disk, log) |
| `01-storage.yaml` | local PV and PVC naming each other |
| `02-deployment.yaml` | cookie initContainer, RabbitMQ, probes, limits |
| `03-service.yaml` | AMQP (5672) and management (15672) |
| `04-route.yaml` | management UI, `edge` TLS, HTTP redirected to HTTPS |
| `05-network-policy.yaml` | AMQP open to the agents' namespace only |

## Variables

| Variable | Role |
|---|---|
| `${RABBITMQ_HOST}` | DNS name of the management UI, resolving to the VPN address |

Replace the node name (`master-0` in `01-storage.yaml`) with the one from `oc get nodes`.

## Procedure (administrator)

1. On the node: create the directory and give it the containers' SELinux label (commands at the top of `01-storage.yaml`).
2. Secrets, never committed:
   - `rabbitmq-admin-creds` (keys `username`, `password`): admin account created on first start;
   - `rabbitmq-erlang-cookie` (key `cookie`): `openssl rand -hex 32`, the same on every node if the RabbitMQ cluster grows.
3. `00` to `05`: `--dry-run=server`, then `apply`.
4. Check: pod `Running` and ready, `rabbitmq-diagnostics status` without alarms, management UI reachable through the VPN, port 5672 refused from any namespace other than the agents'.

**Moving to another volume** (old PVC bound to the wrong PV): first list the directory's content on the node. Then stop RabbitMQ, apply `01-storage.yaml`, switch the Deployment over, and only then delete the old PVC; the PV it held (`Retain`) must be released by hand.

## Next

The `/sophia` vhost is created at start. Still to do: one technical account per agent, `sophia.agent.<target>` queues with one dead-letter queue per agent, the message format, and the integration into the agents.
