# SophIA at a glance

This document presents SophIA at three lengths: one sentence, thirty seconds, three minutes. It also states plainly what already works and what is still to be built.

---

## In one sentence

**SophIA assembles open-source building blocks into an agentic AI platform that the organization hosts, governs and audits itself. Security comes from the architecture, not from the model.**

---

## In thirty seconds

Organizations want AI agents. But they cannot hand their sensitive data to opaque platforms outside their jurisdiction, nor let autonomous agents act without guardrails.

SophIA is a reference architecture that answers both constraints. It runs on a cluster the organization controls. Specialized agents have minimal rights and never talk to each other: every request goes through a dispatcher that decides by rules, without a model, and critical actions wait for human approval. Memory is versioned in Git. Models run locally, behind a router that accepts any model.

You change models without changing the architecture, and every decision stays auditable.

---

## In three minutes

### 1. The problem

Adopting AI today means accepting three risks:

- **Data leaves.** Most uses rely on external APIs, beyond any control.
- **Dependency sets in.** Proprietary APIs, closed ecosystems, infrastructure located in another jurisdiction.
- **Agents are unpredictable.** Prompt injection, exfiltration, ingestion of malicious or AI-generated web content.

On top of that, the ecosystem is fragmented. Every team hand-assembles tools that were never designed to work together.

### 2. The core idea

**We do not make the model reliable: we make the infrastructure reliable.**

A model may hallucinate. With SophIA, its mistakes have no consequences:

- code orchestrates, the model thinks, rules decide: the model proposes in constrained output, rules validate, a deterministic skill executes;
- an agent generating a destructive command is stopped by the cluster's access control;
- a mutating action waits for human approval, enforced by code rather than by an instruction;
- the network confines each component to its perimeter.

These guardrails work with any model, from the smallest to the largest.

### 3. The solution: four pillars

| Pillar | What it brings |
|---|---|
| **Sovereignty** | Controlled Kubernetes infrastructure, local storage, project memory in a self-hosted Git forge. Model-agnostic router: a local or remote model is a routing choice, not a dependency. |
| **Agentic Pantheon** | Specialized agents, one domain each: sandboxed development, deployment, maintenance, read-only supervision. They are reached by a single dispatcher, which decides by rules; minimal rights, human approval on critical actions. |
| **5D RAG memory** | Five complementary dimensions: vector, relational, versioned, structural, graph. Every retrieved fact can be traced back to its source. |
| **Security by design** | Isolated and sanitized web acquisition (Paranoid Airlock), cross-validation before ingestion (Semantic Tribunal), decoy queries (Ghost Search), leak filtering (DLP), interaction logging. |

### 4. What sets SophIA apart

SophIA is not yet another product. It is **a reproducible recipe** that assembles existing components (Kubernetes, LiteLLM, llama.cpp, Keycloak, Temporal, RabbitMQ, Qdrant, PostgreSQL, Forgejo, Hermes Agent) coherently.

- **Reproducible**: the infrastructure is described and versioned.
- **Auditable**: decisions, code and memory are tracked in Git.
- **Model-independent**: agentic behavior is enforced by the infrastructure, not assumed from the model.

### 5. Where the project stands

SophIA is an experimental architecture under construction. We separate what works from what is planned.

**Operational today**

- Single-node Kubernetes (OKD) cluster on a physical server, VPN-only access, single sign-on (SSO) for every interface.
- Local inference on the server's GPU (text and vision), voice and images on CPU, without network access; local model by default for the interface and modules.
- Unified model router: local and remote behind the same aliases.
- Chat interface connected to the router and to local tools (geography, images), with no key in the browser.
- Isolated web acquisition through the airlock, first brick of the Paranoid Airlock.
- Delegation dispatcher, durable workflows and event bus; first executor agent (development) in acceptance testing.
- Self-hosted Git forge, source of truth for code and project memory; isolated development environments.
- Vector database with its schema, embedding service, S3 object storage.
- Pantheon agents on the local model, with priority to chat on the graphics card; one router key per agent.
- Minimal observability: service metrics, alert rules, graphics card, VPN filter safeguard; CPU priorities without preemption and per-namespace quotas.

**In progress**

- The interface as a requester of the dispatcher.
- Memory service (designed), ingestion pipeline and graph dimension.

**Planned**

- Planner for open goals.
- "Incident" workflow; supervision, deployment and maintenance behind the dispatcher.
- Semantic Tribunal, Ghost Search, DLP filter.
- Memory confidentiality levels.
- Reproducible, multi-tenant deployment packages.

Details are in the [roadmap](roadmap.en.md).

### 6. What comes next

- **Demonstration**: the same question asked to a remote model and then to the local model, from the same selector in the interface; with the local model, nothing leaves the cluster.
- **Technical white paper**, in preparation.
- **Openness** to feedback from engineers, researchers and organizations interested in sovereign AI.

---

## Frequently asked questions

**Is SophIA sovereign today?**
Yes for everyday use: infrastructure, memory, access control and inference for the interface, the modules and the agents are local. A remote model remains only a development exception, chosen by routing.

**Do you need a very large model?**
No. Confinement, rules, human approval and constrained output do not depend on the model's capabilities. Tasks are broken into small decisions, within reach of a modest local model.

**Why not use an existing platform?**
Because the goal is control: every component is open source, replaceable and auditable, and the whole can be reproduced on the organization's own infrastructure.

---

See also: [Vision](vision.en.md) · [Architecture](architecture.en.md) · [Security](security.en.md) · [Glossary](glossary.en.md)
