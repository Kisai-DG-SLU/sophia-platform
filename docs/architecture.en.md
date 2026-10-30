# SOPHIA Architecture

SOPHIA (Sovereign Orchestrator Platform for Holistic Intelligence Architecture) is an experimental open architecture designed to orchestrate artificial intelligence systems in a sovereign and secure environment.

The platform assembles open-source components into a coherent infrastructure that enables organizations to deploy, govern and operate AI systems while preserving control over their data and infrastructure.

---

# Architectural Principles

- **Sovereignty** over data, models and infrastructure; target: fully local inference (see [Inference and Hardware](concepts/11-inference-materiel.en.md)).
- **Model-agnostic**: the architecture depends on no specific model. Each agent, being a pod, can use a different model, from the smallest local model to the largest. The system's intelligence resides in the architecture, not the model.
- **Code orchestrates, the model thinks, rules decide**: analysis by the model, decision by rules, execution by a deterministic skill (see [Deterministic Automation](concepts/09-automation-deterministe.en.md)).
- Strict network isolation between critical components.
- Modular integration of open-source technologies.
- Reproducible infrastructure deployment.
- Auditability of AI interactions.

The architecture is designed to be **model-agnostic**, **software-agnostic**, and **hardware-agnostic**. Each component can be replaced by an equivalent alternative, open-source, proprietary, or internally developed. The choices of the reference implementation are examples among many possible configurations.

---

# High-Level Architecture

SOPHIA is built on a Kubernetes platform (OKD / OpenShift). Core services are isolated in dedicated namespaces, development and application environments in separate zones.

```
            users (VPN, SSO)
                     |
          +----------------------+
          |  interface (apps)    |   top layer: identity, guards,
          |  requester           |   short answers, approvals
          +----------+-----------+
                     | requests
          +----------v-----------+        +-------------------+
          |  sophia-core         |------->| sophia-inference  |
          |  model router        |        | local models      |
          |  dispatcher          |        +-------------------+
          |  workflows, bus      |        +-------------------+
          +----------+-----------+------->| sophia-memory     |
                     | missions           | memory (RAG)      |
          +----------v-----------+        +-------------------+
          |  pantheon agents     |        +-------------------+
          |  executors           |------->| sophia-skills     |
          +----------------------+        | MCP tools         |
                                          +-------------------+
          sophia-git: code, specs      sophia-dmz: web, sanitized
```

---

# Two Layers

- **Top layer: the interface.** It carries user identity, guards, short answers and human approvals. For a simple request, it understands the request in constrained output, and the server builds the tool call (in service). For what it cannot do alone, it becomes a **requester** of the dispatcher (planned). It is also the **cockpit**: the shell that displays each application in the centre, under its own sign-in, and gathers their deterministic summaries; the whole page remains the chat's, applications are only frames from a closed list (in progress, see [chat interface](../deploy/okd/apps/chat-interface/README.en.md)).
- **Bottom layer: the agents.** They are **executors**, reached by the dispatcher only. They never talk to each other.
- **Shared services**: the language model and memory are called by both layers, each with its own rights.

---

# Agent Orchestration

| Component | Role | Status |
|---|---|---|
| **Dispatcher** (`sophia-core`) | single entry point for requests; identity proven by service account token; deterministic rules (who asks what of whom, approvals, quotas); one durable workflow per request; destination filters; two-level human approvals | in service |
| **Temporal** (`sophia-core`) | durable workflows; **single application client: the dispatcher**; each workflow's history serves as its log | in service |
| **RabbitMQ** (`sophia-core`) | **events**: each step of a delegation is published on an events exchange by the dispatcher, the only publisher; dead-letter queues | in service, without agent accounts; consumers planned |
| **Autonomous agents** (Hermes Agent, pinned version) | where a free loop with tools is the job: development, then maintenance and deployment with a closed tool list and every command approved | development in acceptance testing, the rest planned |
| **Planner** | open goals: a workflow in code that asks the model for one decision at a time, has it validated by rules and executed by the dispatcher | planned, prototype to be compared with a planner agent |
| **Supervision** | deterministic read functions exposed to the dispatcher, in a separate pod; interpretation is left to the model inside an "incident" workflow | planned: designed and tested |
| **Metrics and alerts** | monitoring of the platform's workloads, alert rules, node exporter | in service |

Details: [Agent Pantheon](concepts/08-pantheon-agentique.en.md), [Observability](concepts/10-observabilite.en.md).

---

# Core Namespaces

## sophia-core

Central orchestration layer: model routing (LiteLLM), delegation dispatcher, durable workflows (Temporal), event bus (RabbitMQ), shared relational database (PostgreSQL 18, one role per database, dedicated volume).

## sophia-inference

Local model execution: hosting, CPU and GPU inference, isolation without network access.

Technologies (example): llama.cpp (text and vision, GPU), stable-diffusion.cpp (images, CPU), voice models on CPU. Alternatives: vLLM, Ollama.

## sophia-memory

Persistent knowledge: vector storage, RAG indexing, embedding. Memory is a **service**, called by the interface as well as by the agents, each according to its rights.

Technologies (example): Qdrant.

## sophia-git

Knowledge and code governance: project memory, specifications, versioning.

Technologies (example): Forgejo.

## sophia-skills

Local tools: MCP servers, context injection, tools for the interface and the agents.

## sophia-storage

Shared S3 object storage: one identity and one bucket per application, default deny on ingress and egress.

Technologies (example): SeaweedFS.

## sophia-dmz

Secure web acquisition: extraction, sanitization, anti-tracking mechanisms.

---

# Development and Runtime Zones

| Namespace | Role |
|---|---|
| agents namespace | pantheon pods, one service account and one UID per pod |
| sophia-sandbox | development environments, without privilege on the node; planned: one ephemeral virtual cluster per project |
| sophia-test | CI/CD validation |
| sophia-apps | modules |
| sophia-interface | the chat interface, now the cockpit, out of the deployment agent's reach; its egress towards applications is explicit |
| sophia-workflow | the visualisation tool, same reason |
| sophia-workspace | the office suite: files and online editing |
| sophia-messagerie | the household's permanent chat (Matrix), in service, in acceptance testing; displayed in the cockpit |
| sophia-visio | video conferencing (Jitsi Meet) through the browser only, in service, in acceptance testing; displayed in the cockpit |
| build namespaces | building sensitive tools, with no agent account |
| prod-* | tenant workloads |

---

# Infrastructure Platform

The reference implementation runs on a single-node Kubernetes cluster (OKD) deployed on a bare-metal server.

- Kubernetes orchestration;
- strict network policies;
- local persistent storage;
- hardware-agnostic design: any infrastructure meeting the requirements can be substituted.

The Proof of Concept hardware is documented in the deployment section; sharing the graphics card and the CPU budget in [Inference and Hardware](concepts/11-inference-materiel.en.md). These choices are not prescriptive: each organization adapts the infrastructure to its context, scale and security requirements.

---

# Anti-Hallucination Architecture

The platform constrains hallucinations through architecture, not model capability. These mechanisms work independently of the underlying model:

- **RBAC confinement**: each agent has strictly minimal permissions. If an agent hallucinates a destructive command outside its scope, the cluster rejects it.
- **Decision without a model**: the dispatcher accepts or refuses each request according to versioned rules that no model can change.
- **Code-enforced human approval**: approval of the plan, then of each command, through a single authenticated path; a signal carries only a decision and a hash.
- **Constrained output**: the model answers in an imposed schema; any deviation is rejected by the rules.
- **Network isolation**: NetworkPolicies open the agents' entry to the dispatcher only.
- **Supervision**: read-only access to the whole system makes it possible to alert on abnormal behavior.

These mechanisms work with any model, from the smallest (a few billion parameters) to the largest. The architecture assumes no agentic capability from the model: behavior is enforced by pod structure, RBAC, rules and infrastructure.

---

# Status

The architecture is experimental. Infrastructure, model routing, local inference (agents included), identity, the dispatcher and its workflows, metrics and alerts (filtered, sent to the administrator outside the platform), CPU priorities, object storage and the cockpit shell are in service; the status of each function is detailed in the [functional scope](functional-scope.en.md) and the [roadmap](roadmap.en.md).
