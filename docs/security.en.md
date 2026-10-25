# SOPHIA Security Model

Security is a fundamental design principle of SOPHIA.

The architecture follows a Zero Trust approach: each component is isolated and allowed to communicate only with explicitly intended services. This document separates what is **in place** in the reference install from what is a **target**: an unmet security promise is not written in the present tense.

---

# Core Security Principles

- least privilege network access;
- isolation between namespaces;
- controlled external connectivity;
- decisions by rules without a model, human approval enforced by code;
- reproducible infrastructure;
- traceability of AI interactions.

---

# Network Segmentation

Each namespace belongs to a security zone. Communication is restricted by Kubernetes NetworkPolicies; the principle is a **default ingress deny** (`default-deny-ingress`) in each namespace, then one rule per legitimate flow. Egress is bounded by each application's own rules and, for sensitive zones, by an EgressFirewall.

| Zone | Namespaces | Role | Isolation status |
|---|---|---|---|
| Orchestration | `sophia-core` | model router, dispatcher, workflows, bus, relational database | **in place**: default ingress deny, one rule per service (the model router only admits applications, agents, development, memory, the ingress router and the node network); egress bounded by an EgressFirewall |
| Identity and forge | `sophia-identity`, `sophia-git` | SSO, repositories | **in place**: ingress closed except intended flows |
| Inference | `sophia-inference` | local models | **in place**: deny all, ingress from the model router and the image tool only, no egress |
| Local tools | `sophia-skills` | MCP servers | **in place**: no egress besides DNS and image models |
| Airlock | `sophia-dmz` | web acquisition | **in place**: default deny; egress to the web reserved for acquisition |
| Applications | `sophia-apps` | interfaces and modules | **in place**: default ingress deny, one rule per application. The deployment agent is administrator there and could read an application's Secrets: the chat interface and the visualisation tool each get their own namespace (**planned**: designed, manifests ready), with no binding to any agent, and the school its own address |
| Object storage | `sophia-storage` | shared S3 | **in place**: default deny on ingress **and** egress (DNS only); one identity per application, limited to its bucket; no anonymous access |
| Agents | agents namespace | pantheon | **in place**: agents' ingress open to the dispatcher only; one service account and one UID per pod; one model-router key per agent. **Target**: Internet egress, uncontrolled today, to be inventoried then closed by an EgressFirewall, first in observation mode |
| Memory | `sophia-memory` | vector database, embedding, graph | **target**: default deny to apply after the memory service; the zone is not isolated yet, and the vector database answers without a key |
| Development | `sophia-sandbox` | development environments, child clusters | **target**: default deny to apply |

Templates: `deploy/okd/apps/00-default-deny.yaml`, `deploy/okd/core/network/default-deny-ingress.yaml` and the model router's ingress rule, `deploy/okd/core/litellm/network-policy.yaml`.

Each default deny is applied one namespace at a time: inventory of legitimate flows, rollback ready, check through the real path (HTTP codes of the Routes, then browser journeys) before and after.

## Access to the platform: VPN only

The platform is reached through a WireGuard VPN only, including from the local network; the local network is never reachable from the VPN. On the node, a dedicated nftables table, independent from OVN-Kubernetes, tells two ranges apart: **administration** (whole node, Forgejo) and **users** (HTTP/HTTPS only), and forwards nothing but Forgejo for administration. A safeguard checks that this table stays readable by the nft version embedded in OVN-Kubernetes; otherwise it removes the table and raises an alert, never cutting the VPN, the only administration path. See `deploy/okd/host/wireguard/`.

---

# Components Without Network Access

Some namespaces are isolated from external networks, to eliminate the risk of exfiltration: their models and data are placed from the node, at pinned revisions and checksums.

| Namespace | State in the reference install |
|---|---|
| sophia-inference | **in place**: deny all, ingress from the model router and the image tool only, no egress |
| sophia-skills | **in place**: no egress besides DNS and image models |
| sophia-memory | **target**: neither default deny nor bounded egress today |

---

# Agent Rights

Agents are executors, reached by the dispatcher only, which decides by rules without a model (see [Agent Pantheon](concepts/08-pantheon-agentique.en.md)).

| Agent | Rights | Safeguard | Status |
|---|---|---|---|
| Development | full powers in its environment, one child cluster per project | no access to deployment or production data; everything is versioned | in acceptance testing |
| Deployment | limited to the applications namespace | approval of the plan, then of each command | planned |
| Maintenance | cluster administrator | approval of the plan, then of **every** command | planned |
| Supervision | read-only on the cluster and metrics | secret filter on everything it returns | planned |

- **No agent reaches the workflow engine or writes to the bus**: the dispatcher is their only client and only publisher.
- **Proven identity**: each request presents a short-lived projected service account token, checked against the Kubernetes API.
- **One key per executor**, known to it and to the dispatcher only.
- **One model-router key per agent**, limited to the local background model and embedding; the router's master key no longer leaves its pod, then gets rotated.
- **Agents' web tools without internal addresses** (`allow_private_urls` off, against request forgery towards the cluster); online model catalog off.
- **Administration availability**: the cluster read pod and the Git forge are in a priority class no other workload can evict ([`deploy/okd/cluster/`](../deploy/okd/cluster/)).
- **Human approvals** through a single path today, the workflow engine's interface, restricted to the administration group (the chat interface, with the person's token relayed, will become the first path); the authenticated author of each signal is checked against the approver list; an approval is valid once.

---

# External Data Acquisition

External information is retrieved through a dedicated isolation layer. The DMZ layer extracts, sanitizes, removes executable content and delivers purified text to the internal system.

This prevents malicious scripts and tracking mechanisms from entering the platform. Nothing coming from the web is stored in memory until the [Semantic Tribunal](concepts/05-tribunal-semantique.en.md) is in service.

---

# Data Protection

- strict access control: SSO, groups, per-client restricted keys on the model router;
- secrets managed through Kubernetes: manifests contain none; a Secret is created from standard input, never as a command argument (visible in the process list), and no value is printed; a value found in a repository's history is changed, without rewriting history;
- repositories read through a read-only deploy key, specific to each repository, never through a forge administrator's token: **in place** for the school's content sync, **planned** for the builds of the interface and of the visualisation tool;
- audit logging;
- encrypted volumes: **target**, not yet in place (unencrypted local volumes).

Persistent data (vector databases, relational databases, repositories) lives on the server's local volumes; encryption at rest is still to be set up.

---

# Interaction Logging

- **In place**: the model router's request log (routing, costs, refusals); the history of each delegation workflow (30 days), with the author of each approval; dated events published by the dispatcher.
- **In place**: service metrics and alert rules, including the removal of the VPN filter by its safeguard (see [Observability](concepts/10-observabilite.en.md)).
- **Target**: raw history of exchanges in Git, for audit, replay and sourcing; alert routing to the dispatcher and "incident" workflow.

---

# Planned Improvements

- leak filter (DLP) before any output to an external model;
- Semantic Tribunal before storing anything from the web;
- default deny in `sophia-memory` and `sophia-sandbox`;
- egress control for the agents namespace;
- dedicated namespaces for the chat interface and the visualisation tool;
- rotation of the model router's master key;
- mutual TLS between the dispatcher and executors;
- encrypted volumes.
