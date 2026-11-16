# Components: technical description

For each component of the [`okd/`](okd/) templates: its storage, its resources, its image and how it is pinned, its exposure, and the reason for these choices. Values are read from the repository's manifests (15/11/2026); the reason comes from each directory's README, which prevails in case of discrepancy. A value the manifest does not set is noted "not set".

How to read the columns:

- **Resources**: `requested → at most` (requests → limits) of the main container; sidecar containers are mentioned when they weigh.
- **Image**: *digest* = pinned by `@sha256` (a restart never pulls another version); *version* = version tag; *built* = image built inside the cluster (`BuildConfig`), then pulled from the internal registry.
- **Exposure**: Service (port), Route (TLS termination); the namespace's network filtering is summarised under each table.

## Common rules

| Rule | Implementation | Reason |
|---|---|---|
| A priority class named by every workload | `sophia-socle` to `sophia-dev`, no default class, no preemption except inference ([`okd/cluster/`](okd/cluster/README.en.md)) | a pod without a class comes after every workload; a preemption kills a pod in the middle of its work |
| Limits on every container, quota per namespace | `ResourceQuota` on limits and a `LimitRange` of default values | declared limits exceeded 160 % of the node; a container without limits gets the default value, often too low |
| Bound local volume | `local:` PV and PVC bound to each other (`claimRef` + `volumeName`), `Retain`; a dedicated XFS logical volume for any data that grows ([`stockage-persistant.en.md`](stockage-persistant.en.md)) | no other PVC takes the volume; data survives the deletion of the objects; online growth |
| One replica, `Recreate` for every `ReadWriteOnce` volume | never two instances on the same directory | a single node, no shared storage |
| Ingress denied by default | one NetworkPolicy per called service; egress closed where the component needs nothing | a compromised pod only reaches what the architecture plans for |
| Exposure through the VPN only | Routes under the router's wildcard domain, names resolved to the VPN address ([`okd/ingress/`](okd/ingress/README.en.md), [`okd/host/wireguard/`](okd/host/wireguard/README.en.md)) | a single access path, the local network out of the VPN's reach |

## Orchestration — `${NS_CORE}` ([`okd/core/`](okd/core/README.en.md))

Namespace quota: 12 CPU, 16 Gi, 15 pods.

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Model router ([LiteLLM](okd/core/README.en.md)) | none (`emptyDir`; data in PostgreSQL) | 250m, 768 Mi → 2 CPU, 2 Gi | built on a base pinned by digest (*nightly* version), `latest` tag, `Always` | Service 4000, edge Route `${LITELLM_HOST}` | ≈ 550 Mi at rest, photos inflate requests; the CPU cap bounds a freeze on a pathological token count; probes and `RollingUpdate` to change configuration without cutting the chat |
| [PostgreSQL 18](okd/core/postgres18/README.en.md) (every database) | dedicated logical volume, `${PG_SIZE}` (20 Gi to start) | 100m, 256 Mi → 2 CPU, 2 Gi | digest (`${PG18_DIGEST}`), `IfNotPresent` | Service 5432, no Route | one shared instance, one owner role per database, no network superuser; outside the node's `/var`, alert at 80 and 90 % |
| [RabbitMQ](okd/core/rabbitmq/README.en.md) (event bus) | node directory, 5 Gi, bound by name | 100m, 256 Mi → 1 CPU, 1 Gi | version (`4.4.0-management`) | Service 5672 and 15672, edge Route for the management UI (behind the identity provider) | a PVC without a designated PV had taken another component's volume; memory aligned on the limit |
| [Temporal](okd/core/temporal/README.en.md) (durable workflows) | none (databases in PostgreSQL) | 250m, 512 Mi → 1 CPU, 1.5 Gi | version (`1.32.1`) | Service 7233 (gRPC) and 7243, no Route | no extra database to operate; upgrades one minor version at a time |
| Temporal UI | none | 20m, 64 Mi → 500m, 256 Mi, plus oauth2-proxy | version (`2.56.0`); oauth2-proxy by version | Service 4180 (oauth2-proxy), edge Route | the UI only opens after signing in to the identity provider |
| [Dispatcher](okd/core/repartiteur/README.en.md) (delegations) | none | 50m, 128 Mi → 500m, 512 Mi | built, deployed by digest (`${REPARTITEUR_DIGEST}`), `IfNotPresent` | Service 8443 (TLS with the service certificate), no Route | only Temporal client and only event publisher; decides by rules, without a model |

Network: ingress denied by default, then one rule per service; the router only admits the namespaces of its recorded callers, the ingress router and the node network. Egress (EgressFirewall): cluster Services and pods, the remote model provider, the registries and package indexes used by builds, the identity provider on 443.

## Identity — `sophia-identity` ([`okd/identity/`](okd/identity/README.en.md))

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Keycloak (official operator, manual approval) | none (database in PostgreSQL) | 200m, 768 Mi → 2 CPU, 1.5 Gi | digest | the operator's Service, edge Route (`auth.apps.example.org`) | realm and clients described as Kubernetes resources, reproducible; no new volume |
| oauth2-proxy [sessions Valkey](okd/identity/sessions/README.en.md) | small local volume, 1 Gi, AOF every second | 20m, 64 Mi → 200m, 192 Mi | digest, `IfNotPresent` | Service 6379, no Route | the whole session in the cookie exceeded header limits; a restart signs nobody out |

Network: on its HTTP port, Keycloak only admits the router and a named list of clients that go through its internal Service (the same list is carried by the operator's resource, which otherwise creates its own open policy); its management port, its own namespace only. Valkey: ingress from the named applications' pods, **no egress**.

## Memory — `${NS_MEMORY}` ([`okd/memory/`](okd/memory/README.en.md))

Namespace quota: 8 CPU, 16 Gi, 10 pods.

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Embedding service (bge-m3, CPU) | none in the manifest (model in the image) | 1 CPU, 2 Gi → 2 CPU, 4 Gi (variables' default values) | built, `latest` tag, `Always` | not set in the template; port 8080 without authentication | the pod starts without Internet, the model revision follows the image; the model fits in memory without a GPU |
| [Vector database (Qdrant)](okd/memory/README.en.md) | dedicated logical volume, 20 Gi to start | 100m, 256 Mi → 2 CPU, 2 Gi | version and digest (`v1.13.4`) | Service 6333 and 6334, API key, reachable from the memory service only; no Route | outside the node's `/var`; Qdrant's optimisation needs up to twice the space; telemetry off |
| Graph (Neo4j) | node directory, 10 Gi | not published | not published | not published | **at 0 replicas**, never started |
| [Memory service](okd/memory/memoire/README.en.md) | registry in PostgreSQL, documents in object storage | 50m, 192 Mi → 1 CPU, 512 Mi; extraction 50m, 128 Mi → 1 CPU, 1,536 Mi | built, deployed by digest (`${MEMOIRE_IMAGE_DIGEST}`); one image for the service and the extraction | Service 8080, reachable from the chat only; extraction 8081, reachable from the service only; no Route | document extraction runs apart, with no Secret, no token, no egress |

Network: ingress and egress denied by default, then one rule per flow; EgressFirewall limited to the cluster's internal networks. The embedding service must only be reachable from the model router.

## Inference — `sophia-inference` ([`okd/inference/`](okd/inference/README.en.md))

Namespace quota: 36 CPU, 40 Gi, 6 pods. The three servers read the same models volume (dedicated 200 Gi logical volume, mounted read-only).

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Language model server (`llama-server`, GPU) | models volume; driver library mounted from the host | 2 CPU, 4 Gi → 8 CPU, 16 Gi | built, version (`v0.7.0-cu124`) | Service 8080, no Route | CUDA compatible with the node's driver; privileged container, without the `nvidia.com/gpu` resource (the operator's hook fails on this node); the only class that preempts |
| Voice (recognition and synthesis, CPU) | models volume | 1 CPU, 2 Gi → 4 CPU, 4 Gi | built, `latest` tag | Service 8000, no Route | the GPU stays with text; `sophia-voix` class above the agents |
| Image generation and classifier (CPU) | models volume | 1 CPU, 6 Gi → 8 CPU, 12 Gi; classifier 100m, 512 Mi → 2 CPU, 1 Gi | built, `latest` tag | Service 1234 and 8001, no Route | capped at 8 CPU so as not to compete with voice; deterministic check of every generated image |
| Node metrics exporter ([`okd/monitoring/`](okd/monitoring/README.en.md)) | host directories, read-only | 10m, 32 Mi → 100m, 64 Mi | digest, `IfNotPresent` | Service 9400, no Route | usage of `/var` and of the dedicated volumes, GPU state |

Network: **no egress**; models are placed from the node, at pinned revisions and digests.

## Monitoring ([`okd/monitoring/`](okd/monitoring/README.en.md))

OKD's user workload monitoring, not a separate stack: a single stack, already maintained by the platform. Prometheus 1 to 3 Gi, 15-day retention, measured cost of about 0.2 CPU and 1 to 2 Gi. Separate metrics Services (`*-metrics`), so as to change nothing in the existing Services; one NetworkPolicy per namespace only opens the metrics ports to the user workload Prometheus alone. The node exporter is described with inference, above.

## Local tools — `sophia-skills` ([`okd/skills/`](okd/skills/README.en.md))

Namespace quota: 8 CPU, 6 Gi, 8 pods.

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Geography (`sophia-geo`) | `skills` folder of the models volume, 20 Gi, read-only | 20m, 320 Mi → 1 CPU, 768 Mi | built, `latest` tag | Service 8000 (MCP), no Route | compute positions, distances and maps instead of letting the model guess; data prepared from the node |
| Images (`sophia-image`) | none | 20m, 96 Mi → 1 CPU, 384 Mi | built, `latest` tag | Service 8000 (MCP), no Route | protection rules applied before generation |

Network: everything denied; ingress from the interface on 8000, from a module to the image tool only; egress DNS and image tool → generator. No egress to the Internet.

## Web airlock — `sophia-dmz` ([`okd/dmz/`](okd/dmz/README.en.md))

Namespace quota: 8 CPU, 12 Gi, 12 pods.

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Metasearch engine (SearXNG) | none (cache `emptyDir`) | 50m, 128 Mi → 1 CPU, 512 Mi | version | Service 8080, no Route | self-hosted search, JSON output, private instance |
| Web service (`sophia-web`: search, pages, weather) | none (weather cache in memory only) | 20m, 320 Mi → 1 CPU, 768 Mi | built (applications namespace), `latest` tag | Service 8000 (MCP and REST), no Route | read the web from a zone that cannot reach any internal address |

Network: everything denied by default; Internet egress on 80/443 outside private ranges, and DNS; web service ingress from the interface, the agents and the Cooking module; the metasearch engine is reachable by the web service only.

## Object storage — `sophia-storage` ([`okd/storage/`](okd/storage/README.en.md))

Namespace quota: 3 CPU, 3 Gi, 4 pods.

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| SeaweedFS (`weed mini`, S3 gateway) | dedicated logical volume, `${S3_SIZE}` (200 Gi in the reference installation) | 100m, 256 Mi → 2 CPU, 2 Gi | version and digest, `IfNotPresent` | Service 9000 (TLS) to port 8443, reencrypt Route `${S3_HOST}` | maintained, a single process on one node; only the TLS gateway is open |
| Initialisation Job (bucket, versioning, CORS, policy) | none | 20m, 64 Mi → 500m, 256 Mi | version and digest | none | replayable setup |

Network: deny by default on ingress and egress; ingress on 8443 from the router, the workspace (office suite) namespace and the Job; egress DNS only.

## Chat interface — dedicated namespace ([`okd/apps/chat-interface/`](okd/apps/chat-interface/README.en.md))

Namespace quota: 4 CPU, 3 Gi, 6 pods.

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| oauth2-proxy | none (sessions in the sessions Valkey) | 10m, 32 Mi → 200m, 128 Mi | version (`v7.15.5`) | Service 8080 to its port 4180, edge Route | mandatory sign-in, no key in the browser |
| nginx and front end | none | 20m, 64 Mi → 500m, 256 Mi | built, `latest` tag | port 8080, reachable from the pod only | static front end, allow-list of routes |
| Conversations API | none (data in PostgreSQL) | 20m, 96 Mi → 500m, 256 Mi | same built image | inside the pod | injected context, MCP tools, identity relay |

Network: ingress denied by default, then the ingress router on 4180 (oauth2-proxy); named egress: model router, identity, sessions Valkey, database, forge, web airlock, MCP tools, school, modules; a separate policy opens the summary route of each dashboard application. A namespace of its own: the deployment agent, administrator of the applications namespace, does not read its Secrets there.

## Agents — `${NS_AGENTS}` ([`okd/hermes-system/`](okd/hermes-system/README.en.md))

Namespace quota: 28 CPU, 48 Gi, 15 pods.

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Coding assistant (cluster reader pod) | `emptyDir`, configuration pushed back to a dedicated repository | 1 CPU, 12 Gi → 16 CPU, 32 Gi | built, deployed by digest (`${AGENT_IMAGE_DIGEST}`) | no Route | `sophia-socle` class: understand the cluster's state even when it is down; memory request above the measured peak |
| Sophia (main agent) | `emptyDir` | 500m, 1 Gi → 2 CPU, 4 Gi (variables' default values) | digest | none | an account without any rights: Sophia never changes the infrastructure |
| Maintenance and deployment agents | `emptyDir` | 50m, 256 Mi → 1 CPU, 1 Gi | digest | Service `${AGENT_API_PORT}` (API switched off outside the executor) | delegation through the dispatcher only |
| Executor (recent Hermes) | `emptyDir` | 100m, 512 Mi → 2 CPU, 2 Gi | built, digest (`${EXECUTANT_IMAGE_DIGEST}`), `IfNotPresent` | Service `${AGENT_API_PORT}`, ingress reserved to the dispatcher | a key of its own, known to it and to the dispatcher only |

Network: executors' ingress reserved to the dispatcher; web tools without internal addresses.

## Development — `${SANDBOX_NAMESPACE}` ([`okd/pod-bases/dev-bastion/`](okd/pod-bases/dev-bastion/README.en.md))

| Component | Storage | Resources | Image | Exposure | Reason |
|---|---|---|---|---|---|
| Development SSH gateway | none (public key through a Secret) | not set | built, `latest` tag | Service 2222 as ClusterIP only; Service on the VPN address, port `${DEV_GATEWAY_VPN_PORT}` | no NodePort, which would be served on the local network; its own SCC (copy of `anyuid` plus `SYS_CHROOT`), no privileged pod in the namespace |

Network: the gateway only reaches DNS and the development pods.

## Components described without public manifests

They are documented by a recipe (components, prerequisites, network, variables, procedure), without a complete template:

| Component | Recipe |
|---|---|
| Office suite (Files, Collabora), persistent chat, video calls, XMPP messaging | [`okd/office/`](okd/office/README.en.md) |
| Git forge | only the namespace's egress filter is published ([`okd/git/network/egress.yaml`](okd/git/network/egress.yaml)); in the reference installation, Forgejo has a readiness probe on `/api/healthz` (HTTP port), a quota and default values ([quotas](okd/cluster/README.en.md#quotas-in-the-reference-install)) |

The June 2026 base (`docker/`, `okd/workspaces/notebook/`, `okd/pod-bases/runner/`) is **historical, not maintained**: it is not described here.
