# SOPHIA — Deployment Example

This directory contains an example deployment of the SOPHIA architecture (for now on **OKD (OpenShift Kubernetes Distribution)**).

The configuration provided here corresponds to the **Proof of Concept environment** used during the initial development of the project.

It demonstrates how the different components of the SOPHIA architecture can be deployed on a Kubernetes platform.

---

## Purpose

The goal of this directory is to:

- provide a **reference deployment layout**
- illustrate how the platform components are organized
- document the **namespace architecture**
- allow experimentation and local reproduction of the system

This configuration is **not intended to be a production-ready distribution**.

Instead, it serves as an **example infrastructure** used for experimentation and documentation.

---

## Platform

The reference deployment environment uses:

- OKD (OpenShift Kubernetes Distribution)
- containerized services
- namespace-based isolation
- network segmentation via Kubernetes NetworkPolicies

The deployment structure follows the architectural principles described in:

```

docs/architecture.md

```

---

## Namespace Model

The example deployment uses a segmented namespace architecture.

Typical namespaces include:

| Namespace | Role |
|----------|------|
| sophia-core | orchestration services |
| sophia-inference | local model runtime |
| sophia-memory | vector database |
| sophia-git | project repositories |
| sophia-skills | MCP tools |
| sophia-dmz | controlled web acquisition |
| sophia-sandbox | development workspaces |
| sophia-test | validation environments |
| sophia-apps | user interfaces |

This layout illustrates the **Hub & Spoke architecture** used by the platform.

---

## Important Notes

This deployment example reflects the configuration used for the author's experimentation environment.

It may include:

- simplified security policies
- local infrastructure assumptions
- development-specific configurations

Before any real-world deployment, organizations should adapt the configuration to their own infrastructure and security requirements.

---

## Future Improvements

In the future, the deployment layer may include:

- reproducible Helm charts
- Kustomize packages
- automated cluster bootstrap
- reference architectures for different deployment scales

---

## Status

Experimental.

This directory documents the infrastructure used to validate the architecture concepts described in this repository.

---
