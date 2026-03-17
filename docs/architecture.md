# SOPHIA Architecture

SOPHIA (Sovereign Orchestrator Platform for Holistic Intelligence Architecture) is an experimental open architecture designed to orchestrate artificial intelligence systems in a sovereign and secure environment.

The platform assembles open-source components into a coherent infrastructure that enables organizations to deploy, govern and operate AI systems while preserving control over their data and infrastructure.

---

# Architectural Principles

The design of SOPHIA is guided by several core principles:

- Sovereignty over data, models and infrastructure
- Strict network isolation between critical components
- Modular integration of open-source technologies
- Reproducible infrastructure deployment
- Auditability of AI interactions

---

# High-Level Architecture

SOPHIA is built on top of a Kubernetes platform (OKD / OpenShift).

The architecture follows a **Hub & Spoke model**:

Core cognitive services are isolated in central namespaces, while development and application environments are separated into dedicated zones.
```
                +-----------------------+
                |      sophia-core     |
                |   Orchestration AI   |
                +-----------+----------+
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

* LLM routing
* agent orchestration
* execution workflows
* API access

Technologies:

* LiteLLM
* orchestration engines
* logging and telemetry

---

## sophia-inference

Local model execution environment.

Responsibilities:

* hosting local models
* CPU-based inference
* model execution isolation

Technologies:

* Ollama
* llama.cpp

---

## sophia-memory

Persistent knowledge layer.

Responsibilities:

* vector storage
* RAG indexing
* knowledge persistence

Technologies:

* Qdrant

---

## sophia-git

Knowledge and code governance layer.

Responsibilities:

* project memory
* specifications storage
* code versioning

Technologies:

* Forgejo

---

## sophia-skills

Tooling and contextual capabilities.

Responsibilities:

* MCP servers
* context injection
* tool execution for agents

---

## sophia-dmz

Secure web acquisition layer.

Responsibilities:

* external web extraction
* sanitization
* anti-tracking mechanisms

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

SOPHIA currently runs on a **single-node OpenShift (OKD)** cluster deployed on a bare-metal server.

Key characteristics:

* Kubernetes orchestration
* OVN-Kubernetes networking
* strict network policies
* persistent storage via LVM

---

# Status

The architecture is currently experimental.

Initial infrastructure components are operational and the documentation is progressively being published.

````
