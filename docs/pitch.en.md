# SophIA at a glance

This document presents SophIA at three lengths: one sentence, thirty seconds, three minutes. It also states plainly what already works and what is still to be built.

---

## In one sentence

**SophIA assembles open-source building blocks into an agentic AI platform that the organization hosts, governs and audits itself. Security comes from the architecture, not from the model.**

---

## In thirty seconds

Organizations want AI agents. But they cannot hand their sensitive data to opaque platforms outside their jurisdiction, nor let autonomous agents act without guardrails.

SophIA is a reference architecture that answers both constraints. It runs on a cluster the organization controls. Each specialized agent lives in a confined environment with minimal rights, and critical actions wait for human approval. Memory is versioned in Git. A model router accepts any model, local or remote.

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

- an agent generating a destructive command is stopped by the cluster's access control;
- a mutating action waits for human approval, enforced by code rather than by an instruction;
- sub-agents communicate only in strict JSON, and any deviation is rejected;
- the network confines each component to its perimeter.

These guardrails work with any model, from the smallest to the largest.

### 3. The solution: four pillars

| Pillar | What it brings |
|---|---|
| **Sovereignty** | Controlled Kubernetes infrastructure, local storage, project memory in a self-hosted Git forge. Model-agnostic router: a local or remote model is a routing choice, not a dependency. |
| **Agentic Pantheon** | Specialized agents, one domain each: sandboxed development, deployment, maintenance, read-only supervision. Minimal rights, human approval on critical actions. |
| **5D RAG memory** | Five complementary dimensions: vector, relational, versioned, structural, graph. Every retrieved fact can be traced back to its source. |
| **Security by design** | Isolated and sanitized web acquisition (Paranoid Airlock), cross-validation before ingestion (Semantic Tribunal), decoy queries (Ghost Search), leak filtering (DLP), interaction logging. |

### 4. What sets SophIA apart

SophIA is not yet another product. It is **a reproducible recipe** that assembles existing components (Kubernetes, LiteLLM, Qdrant, PostgreSQL, Forgejo, Hermes agents) coherently.

- **Reproducible**: the infrastructure is described and versioned.
- **Auditable**: decisions, code and memory are tracked in Git.
- **Model-independent**: agentic behavior is enforced by the infrastructure, not assumed from the model.

### 5. Where the project stands

SophIA is an experimental architecture under construction. We separate what works from what is planned.

**Operational today**

- Single-node Kubernetes (OKD) cluster on a physical server, VPN access, GPU available.
- Self-hosted Git forge, source of truth for code and project memory.
- Unified model router with several profiles (routine, reasoning, architecture).
- Isolated development environments driven by agents.
- Chat interface connected to the router, with no key in the browser.
- Pantheon agents deployed, each in its own environment.
- Vector database and embedding service running.

**In progress**

- Inference on the local GPU. Today, models go through a remote provider via the router: sovereignty is guaranteed by design, not yet in operation.
- Memory ingestion pipeline and graph dimension.
- Inter-agent messaging bus.

**Planned**

- Paranoid Airlock, Semantic Tribunal, DLP filter.
- Role-based permissions and memory confidentiality levels.
- Reproducible, multi-tenant deployment packages.

Details are in the [roadmap](roadmap.en.md).

### 6. What comes next

- **Demonstration**: the same question asked to a remote model and then to a local model, from the same interface, without local data leaving the cluster.
- **Technical white paper**, in preparation.
- **Openness** to feedback from engineers, researchers and organizations interested in sovereign AI.

---

## Frequently asked questions

**Is SophIA sovereign today?**
It is by design: infrastructure, memory and access control are under control. Inference still goes through a remote provider, and the move to the local GPU is under way. The router makes this switch transparent to users and agents.

**Do you need a very large model?**
No. Confinement, human approval and enforced output format do not depend on the model's capabilities.

**Why not use an existing platform?**
Because the goal is control: every component is open source, replaceable and auditable, and the whole can be reproduced on the organization's own infrastructure.

---

See also: [Vision](vision.en.md) · [Architecture](architecture.en.md) · [Security](security.en.md) · [Glossary](glossary.en.md)
