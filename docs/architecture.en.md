# SOPHIA Architecture

SOPHIA (Sovereign Orchestrator Platform for Holistic Intelligence Architecture) is an experimental open architecture designed to orchestrate artificial intelligence systems in a sovereign and secure environment.

The platform assembles open-source components into a coherent infrastructure that enables organizations to deploy, govern and operate AI systems while preserving control over their data and infrastructure.

---

# Architectural Principles

The design of SOPHIA is guided by several core principles:

- Sovereignty over data, models and infrastructure
- **Model-agnostic**: The architecture does not depend on any specific model. Each agent, as an autonomous pod, can use a different model -- from the smallest local model to the largest public one. The system's intelligence resides in the architecture, not the model.
- Strict network isolation between critical components
- Modular integration of open-source technologies
- Reproducible infrastructure deployment
- Auditability of AI interactions

The architecture is designed to be **model-agnostic**, **software-agnostic**, and **hardware-agnostic**. Each component can be replaced by an equivalent alternative, whether open-source, proprietary, or internally developed. The choices made in the reference implementation (detailed in the deployment documentation) are examples among many possible configurations.

---

# High-Level Architecture

SOPHIA is built on top of a Kubernetes platform (OKD / OpenShift).

The architecture follows a Hub and Spoke model: core cognitive services are isolated in central namespaces, while development and application environments are separated into dedicated zones.

```
                +-----------------------+
                |     sophia-core       |
                |   AI Orchestration    |
                +-----------+-----------+
                            |
        ----------------------------------------------
        |                    |                       |
+---------------+   +---------------+      +---------------+
| sophia-git    |   | sophia-memory |      | sophia-skills |
| Code & specs  |   | Vector store  |      | MCP servers   |
+---------------+   +---------------+      +---------------+
                                                    |
                                              +-----------+
                                              | inference |
                                              | models    |
                                              +-----------+
                                                    |
                                              +-----------+
                                              |   DMZ     |
                                              | web data  |
                                              +-----------+
```

---

# Core Namespaces

## sophia-core

Central orchestration layer.

Responsibilities:

- LLM routing
- agent orchestration
- execution workflows
- API access

Technologies (example): LiteLLM, orchestration engines, logging and telemetry

---

## sophia-inference

Local model execution environment.

Responsibilities:

- hosting local models
- CPU/GPU-based inference
- model execution isolation

Technologies (example): Ollama, llama.cpp

---

## sophia-memory

Persistent knowledge layer.

Responsibilities:

- vector storage
- RAG indexing
- knowledge persistence

Technologies (example): Qdrant

---

## sophia-git

Knowledge and code governance layer.

Responsibilities:

- project memory
- specifications storage
- code versioning

Technologies (example): Forgejo

---

## sophia-skills

Tooling and contextual capabilities.

Responsibilities:

- MCP servers
- context injection
- tool execution for agents

---

## sophia-dmz

Secure web acquisition layer.

Responsibilities:

- external web extraction
- sanitization
- anti-tracking mechanisms

---

# Development and Runtime Zones

Additional namespaces provide controlled environments:

| Namespace      | Role                        |
| -------------- | --------------------------- |
| sophia-sandbox | development environments    |
| sophia-test    | CI/CD validation            |
| sophia-apps    | user interfaces             |
| prod-*         | tenant production workloads |

---

# Infrastructure Platform

The reference implementation of the SOPHIA architecture currently runs on a single-node Kubernetes cluster (OKD) deployed on a bare-metal server.

Key characteristics:

- Kubernetes orchestration
- strict network policies via isolation mechanisms
- persistent storage
- hardware-agnostic design (any infrastructure meeting the requirements can be substituted)

The specific hardware configuration used for the Proof of Concept is documented in the deployment section. It is intentionally non-prescriptive: each organization should adapt the infrastructure choices to its own context, scale, and security requirements.

---

# Anti-Hallucination Architecture

The platform is designed to constrain hallucinations through architecture, not model capability. The following mechanisms work independently of the underlying model:

- **RBAC confinement**: each agent has strictly minimal permissions. Even if an agent hallucinates a destructive command, the Kubernetes cluster rejects it (principle of least privilege).
- **Code-enforced HITL**: Athena and Ouranos have their mutation actions intercepted by a HITL lock at the terminal level. No critical action is executed without human validation, regardless of the model.
- **Enforced output format**: sub-agents communicate exclusively in strict JSON. Any format deviation is detected and rejected.
- **Network isolation**: NetworkPolicies prevent any agent from communicating outside its authorized perimeter.
- **Supervision**: Dionysos observes the entire system in read-only mode and can alert on abnormal behavior.

These mechanisms work with any model, from the smallest (a few billion parameters) to the largest. The architecture assumes no intrinsic agentic capability from the model -- agentic behavior is enforced by pod structure, RBAC, and infrastructure constraints.

---

# Status

The architecture is currently experimental. Initial infrastructure components are operational and the documentation is progressively being published.
