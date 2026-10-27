# SOPHIA Roadmap

The SOPHIA project evolves progressively from infrastructure experimentation to a complete sovereign AI platform. Each stage matches one or more phases of the work plan; a brick is only called "in service" once it runs in the reference install **and** its reproducible recipe is published in `deploy/`.

---

# Stage 0 — Infrastructure Foundations

In service.

- bare metal server, single-node OKD cluster
- VPN-only access ([`deploy/okd/host/wireguard/`](../deploy/okd/host/wireguard/))
- persistent local storage ([`deploy/stockage-persistant.en.md`](../deploy/stockage-persistant.en.md))
- namespaces per security zone, default ingress deny in applications and orchestration ([security](security.en.md))

---

# Stage 1 — Core Platform

In service.

- model routing through LiteLLM: remote and local models behind the same aliases, one virtual key per use, master key confined to the router ([`deploy/okd/core/`](../deploy/okd/core/), [models by role](concepts/13-modeles-par-role.en.md))
- shared relational database on PostgreSQL 18, one role per database, on a dedicated extensible volume ([`deploy/okd/core/`](../deploy/okd/core/))
- local inference: text and vision on GPU, voice and images on CPU, without network egress ([`deploy/okd/inference/`](../deploy/okd/inference/))
- identity and SSO: Keycloak for every interface ([`deploy/okd/identity/`](../deploy/okd/identity/))
- chat interface, in its own namespace ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/))
- office suite: files and online editing, found and read from the chat under the person's identity ([Office module](modules/bureautique/README.en.md), [identity relay](concepts/12-relais-identite.en.md))
- the household's permanent chat (Matrix) and video calls (Jitsi Meet): installed, in acceptance testing ([Communication module](modules/communication/README.en.md)); mail planned
- web search through an isolated airlock, first brick of the Paranoid Airlock ([`deploy/okd/dmz/`](../deploy/okd/dmz/))
- local MCP tools: geography, images with protection rules, the person's files ([`deploy/okd/skills/`](../deploy/okd/skills/))
- Git platform and persistent coding assistant ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/))

---

# Stage 2 — Agents and Memory

In progress. Work follows this order:

| # | Work | Status |
|---|---|---|
| 0 | **Event bus and durable workflows**: RabbitMQ (topology, rights, dead letters), Temporal; the delegation **dispatcher**, only client of Temporal and only publisher of events ([`deploy/okd/core/rabbitmq/`](../deploy/okd/core/rabbitmq/), [`deploy/okd/core/temporal/`](../deploy/okd/core/temporal/)) | in service ([`deploy/okd/core/repartiteur/`](../deploy/okd/core/repartiteur/)); agents' queues and accounts removed from the bus; event consumers to do |
| 1 | **Minimal observability** and **CPU priorities**: service metrics, alert rules, priority classes, per-namespace quotas ([observability](concepts/10-observabilite.en.md), [inference and hardware](concepts/11-inference-materiel.en.md)) | in service ([`deploy/okd/monitoring/`](../deploy/okd/monitoring/), [`deploy/okd/cluster/`](../deploy/okd/cluster/)), agents namespace quota and volume-fill alert included; filtered alerts sent to the administrator outside the platform, a copy logged by the dispatcher; incident register to do |
| 2 | **Agents on the local model**, with a "background" alias that leaves priority to chat, one router key per agent and card slots by time of day | in service ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/)); one mission at a time per executor, local-model slots by time of day |
| 3 | **Memory (RAG)**: collection and schema with tags, **memory API** (per-tag rights, long-term writes by the memory service), graph and ingestion, object storage for files | in progress: schema, vector database on its dedicated volume, embedding alias ([`deploy/okd/memory/`](../deploy/okd/memory/)) and object storage ([`deploy/okd/storage/`](../deploy/okd/storage/)) in service; memory API designed; graph and ingestion to rebuild |
| 4 | **The interface as a requester** of the dispatcher, with a return channel for approvals and notifications | designed; first steps in service: dedicated namespace, models per role, opening an application, the person's token relayed to a tool ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/)) |
| 5 | Delegations to **supervision** (read), **deployment** and **maintenance** (two-level approvals); mutual TLS | to do |
| 6 | **Planner** for open goals: workflow prototype, compared with a planner agent on real goals | to do |
| 7 | **n8n** (with the first tool that needs it), **leak filter**, **Semantic Tribunal** | to do |
| — | Measuring a mixture-of-experts model in hybrid card + RAM, CPU peak included, before any model change | to schedule |

Memory comes before the requester interface and the planner: both need it, as a typed tool and for long-term memory writes.

Also in this stage:

- modules built on the platform ([`docs/modules/`](modules/))
- workspace management, project model, context management

---

# Stage 3 — Security and Governance

Future work.

- memory confidentiality levels, role-based permissions on memory
- default deny in memory; admin network policy and admission of internal-registry images only in development (privilege on the node already removed there)
- development clusters: one ephemeral virtual cluster per project, recreated from the forge by a workflow, packages through read-only relays in the airlock, one router key per project limited to the local model
- encrypted volumes, full memory isolation
- scheduled, encrypted backups, with a restore test; two-factor authentication
- update and vulnerability watch for pinned images
- compliance (GDPR, AI Act, ISO 27001 aimed at "certifiable"): measured status, action plan, follow-up (designed, [Visualisation module](modules/visualisation/README.en.md))
- advanced audit logging, raw history of exchanges, knowledge verification workflows
- "incident" workflow: from alarm to approved plan ([observability](concepts/10-observabilite.en.md))

---

# Stage 4 — Opening and Supervision

Future work.

- opening to other users
- system dashboard: first step in service, the measured state of each component and the mirror check ([Visualisation module](modules/visualisation/README.en.md)); knowledge interface
- arbiter: an external model consulted after the leak filter

---

# Stage 5 — Industrialization

Long term.

- reproducible deployment packages
- reference architecture for organizations
- support for multi-tenant deployments
