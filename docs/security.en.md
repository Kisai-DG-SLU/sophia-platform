
---

# SOPHIA Security Model

Security is a fundamental design principle of SOPHIA.

The architecture implements a **Zero Trust approach** in which each component is isolated and allowed to communicate only with explicitly authorized services.

---

# Core Security Principles

The system is designed around the following principles:

- Least privilege network access
- Isolation between namespaces
- controlled external connectivity
- reproducible infrastructure
- full traceability of AI interactions

---

# Network Segmentation

Each namespace belongs to a specific security zone.

| Zone | Purpose |
|-----|--------|
| brain | orchestration services |
| air-gapped | local inference and memory |
| outils | tooling and MCP services |
| sas | external web acquisition |
| dev | development environments |
| frontend | user interfaces |

Network communication between zones is restricted using Kubernetes **NetworkPolicies**.

### Access to the platform: VPN only

The platform is reached through a WireGuard VPN only, including from the local network; the local network is never reachable from the VPN. On the node, a dedicated nftables table, independent from OVN-Kubernetes, tells two ranges apart: **administration** (whole node, Forgejo) and **users** (HTTP/HTTPS only), and forwards nothing but Forgejo for administration. A safeguard checks that this table stays readable by the nft version embedded in OVN-Kubernetes; otherwise it removes the table and raises an alert, never cutting the VPN, the only administration path. See `deploy/okd/host/wireguard/`.

---

# Air-Gapped Components

Certain namespaces are intentionally isolated from external networks.

Examples:

| Namespace | State in the reference install |
|---|---|
| sophia-inference | **in place**: deny all, ingress from the model router and the image tool only, no egress |
| sophia-skills | **in place**: no egress besides DNS and image models |
| sophia-memory | **target**: isolation still to apply |

These namespaces are prevented from accessing the internet to eliminate the risk of data exfiltration; their models and data are placed from the node, at pinned revisions and checksums.

---

# External Data Acquisition

External information is retrieved through a dedicated isolation layer.

The **DMZ layer** is responsible for:

- web extraction
- content sanitization
- removal of executable content
- delivery of purified markdown data to the system

This prevents malicious scripts or tracking mechanisms from entering the platform.

---

# Data Protection

Sensitive data is protected using several mechanisms:

- strict access control (SSO, groups, per-client restricted keys)
- secrets managed through Kubernetes, never in repositories
- audit logging
- encrypted storage volumes: **target**, not yet in place in the reference install (unencrypted local volumes)

Persistent data (vector databases, relational databases, repositories) lives on the server's local volumes; encryption at rest is still to be set up.

---

# Prompt and Interaction Logging

All AI interactions can be logged to ensure auditability.

Logs include:

- prompts
- responses
- routing decisions
- blocked requests

This allows forensic analysis and traceability of AI behaviour.

---

# Future Security Enhancements

Planned improvements include:

- advanced DLP filtering
- semantic verification pipelines
- automated validation of external knowledge sources
