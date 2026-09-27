# Reference Infrastructure

This document describes the infrastructure used for the Proof of Concept (POC) of the SophIA architecture. This configuration is one possible implementation among others and does not constitute a prerequisite.

## Agnosticism principle

The SophIA architecture is designed to be:

- **Hardware-agnostic.** No specific hardware dependency. The infrastructure can be adapted to each organization's budgetary, performance, and sovereignty constraints.
- **Software-agnostic.** Each software component can be replaced by an equivalent alternative, whether open-source, proprietary, or internally developed.

The technical choices documented here are examples validated by the POC experience, not requirements.

## POC configuration

The reference infrastructure for this POC is based on the following elements:

- **Orchestration:** Single Node OKD (OpenShift Kubernetes Distribution)
- **Memory:** 512 GB RAM
- **Acceleration:** 1 GPU 16 GB
- **Storage:** Persistent volumes on local disks

This configuration allows running the entire stack (orchestration, local inference, vector database, Git, tools) on a single node, sufficient for a POC and initial deployment phases.

## Possible substitutions

| Component            | POC Example      | Possible Alternatives                        |
|:---------------------|:-----------------|:---------------------------------------------|
| Container orchestration | OKD          | Kubernetes, K3s, Rancher, EKS, AKS           |
| Local inference      | Ollama / llama.cpp | vLLM, LocalAI, custom inference            |
| Model routing        | LiteLLM          | Portkey, custom gateway                       |
| Vector database      | Qdrant           | Weaviate, Milvus, Pinecone, FAISS             |
| Git / versioning     | Forgejo          | Gitea, GitLab CE, GitHub Enterprise           |
| Workflow engine      | n8n              | Node-RED, StackStorm, Temporal                |
| Relational database  | PostgreSQL       | MariaDB, MySQL                                |
| Development environment | OpenCode / Jupyter | VS Code Server, Coder, Theia              |
| Web acquisition      | Paranoia Airlock | Custom tooling, dedicated proxy               |

This list is not exhaustive. It illustrates the architecture's philosophy: no component is indispensable in itself, only the coherence of the whole matters.

## General prerequisites

Regardless of infrastructure choices, the following prerequisites apply:

- a containerization environment (Kubernetes or equivalent)
- a network isolation mechanism (network policies)
- persistent storage for databases and repositories, prepared and sized as described in [persistent storage](stockage-persistant.en.md)
- secure access (VPN or equivalent) for administrators and users
