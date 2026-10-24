# SOPHIA Roadmap

The SOPHIA project evolves progressively from infrastructure experimentation to a complete sovereign AI platform. Each stage below matches one or more phases of the work plan; a stage is only called "in service" once it runs in the reference install and its reproducible recipe is published in `deploy/`.

---

# Stage 0 — Infrastructure Foundations

In service.

- bare metal server, single-node OKD cluster
- VPN-only access ([`deploy/okd/host/wireguard/`](../deploy/okd/host/wireguard/))
- persistent local storage ([`deploy/stockage-persistant.en.md`](../deploy/stockage-persistant.en.md))
- namespaces per security zone

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

In progress.

- inter-agent communication: RabbitMQ for events, Temporal for durable delegations ([`deploy/okd/core/rabbitmq/`](../deploy/okd/core/rabbitmq/), [`deploy/okd/core/temporal/`](../deploy/okd/core/temporal/))
- memory and RAG (5+1 architecture), document ingestion
- deterministic automation: an agent triggers a workflow, it does not drive it
- modules built on the platform ([`docs/modules/`](modules/))
- workspace management, project model, context management

---

# Stage 3 — Security and Governance

Future work.

- role-based permissions, semantic tribunal
- DLP filtering pipeline
- encrypted volumes, full memory isolation
- advanced audit logging, knowledge verification workflows

---

# Stage 4 — Opening and Supervision

Future work.

- opening to other users
- system dashboard, knowledge interface
- operational monitoring tools

---

# Stage 5 — Industrialization

Long term.

- reproducible deployment packages
- reference architecture for organizations
- support for multi-tenant deployments
