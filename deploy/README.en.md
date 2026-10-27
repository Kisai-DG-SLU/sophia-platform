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
- size and prepare persistent storage: see [persistent storage](stockage-persistant.en.md)

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

## Recipes

Each directory describes one component: its choices and their reasons, its templates (`${…}` variables), its Secrets (names and keys, never a value), a step-by-step procedure with the expected checks, and the rollback.

| Directory | Content |
|---|---|
| [`okd/host/wireguard/`](okd/host/wireguard/) | VPN-only access, node filter and its safeguard |
| [`okd/cluster/`](okd/cluster/) | priority classes and per-namespace quotas |
| [`okd/monitoring/`](okd/monitoring/) | minimal observability: metrics, alert rules, node exporter |
| [`okd/core/`](okd/core/) | model router, relational database, event bus, durable workflows, dispatcher |
| [`okd/inference/`](okd/inference/) | local models: text and vision on GPU, voice and images on CPU |
| [`okd/memory/`](okd/memory/) | embedding and the vector memory schema |
| [`okd/storage/`](okd/storage/) | shared S3 object storage |
| [`okd/office/`](okd/office/) | office suite: each person's files and document editing (La Suite Drive, Collabora) |
| [`okd/identity/`](okd/identity/), [`okd/ingress/`](okd/ingress/) | identity and SSO, certificates |
| [`okd/apps/`](okd/apps/), [`okd/skills/`](okd/skills/), [`okd/dmz/`](okd/dmz/) | interface, local MCP tools, web airlock |
| [`okd/hermes-system/`](okd/hermes-system/) | pantheon agents and coding assistant |

## Application method

The same for every recipe; its aim is never to break what is running:

1. **An order of steps written in advance**, by impact: first what has no effect (classes, quotas, Secrets, new objects), then what touches no user, finally what restarts a service in use, when nobody is using it. A manifest that depends on a prerequisite waits for it, so a pod restarts only once.
2. **An `oc diff` read in full before every `oc apply`.** It must only show the intended change; an unrelated difference signals drift between the repository and the cluster, to realign first.
3. **One step at a time**, each with its expected check, read after applying, and its rollback ready beforehand.
4. **The real path** to verify: the Route, SSO, the model router, the built image, not just the code.
5. **Secrets through standard input** (`printf … | oc create secret generic … --from-env-file=/dev/stdin`), never as a command argument, where the process list would show them; no value is printed.
6. **A shared setting is tried on a single component** before the others.
7. **No implicit deletion**: an object removed from a template is removed from the cluster by a separate, checked step.

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
| sophia-apps | modules |
| sophia-interface | chat interface |
| sophia-workflow | visualisation tool |
| sophia-workspace | office suite |
| sophia-messagerie | permanent chat (Matrix), in acceptance testing |
| sophia-visio | video calls (Jitsi Meet), in acceptance testing |
| sophia-skills-build | MCP tool builds, no agent account |
| agents namespace | pantheon and coding assistant |
| sophia-identity | identity and SSO (Keycloak) |
| sophia-storage | shared S3 object storage |

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
