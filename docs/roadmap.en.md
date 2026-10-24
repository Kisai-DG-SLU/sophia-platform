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

- model routing through LiteLLM: remote and local models behind the same aliases ([`deploy/okd/core/`](../deploy/okd/core/))
- local inference: text and vision on GPU, voice and images on CPU, without network egress ([`deploy/okd/inference/`](../deploy/okd/inference/))
- identity and SSO: Keycloak for every interface ([`deploy/okd/identity/`](../deploy/okd/identity/))
- chat interface ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/))
- web search through an isolated airlock, first brick of the Paranoid Airlock ([`deploy/okd/dmz/`](../deploy/okd/dmz/))
- local MCP tools: geography, images with protection rules ([`deploy/okd/skills/`](../deploy/okd/skills/))
- Git platform and persistent coding assistant ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/))

---

# Stage 2 — Agents and Memory

In progress. Work follows this order:

| # | Work | Status |
|---|---|---|
| 0 | **Event bus and durable workflows**: RabbitMQ (topology, rights, dead letters), Temporal; the delegation **dispatcher**, only client of Temporal and only publisher of events ([`deploy/okd/core/rabbitmq/`](../deploy/okd/core/rabbitmq/), [`deploy/okd/core/temporal/`](../deploy/okd/core/temporal/)) | in service ([`deploy/okd/core/repartiteur/`](../deploy/okd/core/repartiteur/)); event consumers to do |
| 1 | **Minimal observability** and **CPU priorities**: service metrics, alert rules, priority classes, per-namespace quotas ([observability](concepts/10-observabilite.en.md), [inference and hardware](concepts/11-inference-materiel.en.md)) | to do |
| 2 | **Agents on the local model**, with a "background" alias that leaves priority to chat | to do |
| 3 | **Memory (RAG)**: collection and schema with tags, **memory API** (per-tag rights, long-term writes by the memory service), graph and ingestion, object storage for files | to do, partly ready |
| 4 | **The interface as a requester** of the dispatcher, with a return channel for approvals and notifications | being designed |
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
- default deny in memory and development
- encrypted volumes, full memory isolation
- advanced audit logging, raw history of exchanges, knowledge verification workflows
- "incident" workflow: from alarm to approved plan ([observability](concepts/10-observabilite.en.md))

---

# Stage 4 — Opening and Supervision

Future work.

- opening to other users
- system dashboard, knowledge interface
- arbiter: an external model consulted after the leak filter

---

# Stage 5 — Industrialization

Long term.

- reproducible deployment packages
- reference architecture for organizations
- support for multi-tenant deployments
