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
| Identity and forge | `sophia-identity`, `sophia-git` | SSO, repositories | **in place**: ingress closed except intended flows. **Caveat**: the rule set by the identity provider's operator opens its internal HTTP port to the whole cluster, which cancels the restriction; to be fixed |
| Inference | `sophia-inference` | local models | **in place**: deny all, ingress from the model router and the image tool only, no egress |
| Local tools | `sophia-skills` | MCP servers | **in place**: no egress besides DNS and image models, except the files tool (identity provider and the office suite's internal port) |
| Airlock | `sophia-dmz` | web acquisition | **in place**: default deny; egress to the web reserved for acquisition |
| Applications | `sophia-apps` | modules | **in place**: default ingress deny, one rule per application; no privileged SCC left on the default account. The deployment agent is administrator there and could read an application's Secrets: that is why the chat interface and the visualisation tool moved out |
| Chat interface | `sophia-interface` | chat | **in place**: its own namespace, with no binding to any agent; quota, defaults, default ingress deny; the services it reaches (database, web gateway, MCP tools, modules) only admit the interface from this namespace, the former location is emptied and its entries removed; the cockpit's egress towards applications (authentication relays of cooking and visualisation, messaging summary route) is in a separate policy, one rule per destination |
| Permanent chat | `sophia-messagerie` | the household's Matrix messaging | **in service, in acceptance testing**: quota, defaults, EgressFirewall, default deny, no agent binding; federation off; access restricted to the household groups, guests refused; only new ingress: the summary route from the interface pod |
| Video calls | `sophia-visio` | video conferencing | **in service, in acceptance testing**: same base; media on a single UDP port, reachable through the VPN only; peer-to-peer and third-party servers off; browser only, no more mobile app |
| Visualisation | `sophia-workflow` | measured state of the platform, mirror check | **in place**: its own namespace, no binding to any agent; a read account that does not read Secrets; default ingress deny |
| Office suite | `sophia-workspace` | files and online editing | **in place**: default ingress deny, one rule per flow; the API for tools is open only to the tool's pod, on an internal read-only port |
| Builds | `sophia-skills-build` | building MCP tools | **in place**: no agent account; egress bounded by an EgressFirewall to the internal registry, cluster services, the cluster API and the Python package index |
| Object storage | `sophia-storage` | shared S3 | **in place**: default deny on ingress **and** egress (DNS only); one identity per application, limited to its bucket; no anonymous access |
| Agents | agents namespace | pantheon | **in place**: agents' ingress open to the dispatcher only; one service account and one UID per pod; one model-router key per agent. **Target**: Internet egress, uncontrolled today, to be inventoried then closed by an EgressFirewall, first in observation mode |
| Memory | `sophia-memory` | vector database, embedding, graph | **target**: default deny to apply after the memory service; the zone is not isolated yet, and the vector database answers without a key (empty collection, ingestion suspended) |
| Development | `sophia-sandbox` | development environments; planned: one virtual cluster per project | **in place**: no privileged SCC left, a privileged pod is refused there; the SSH gateway has its own SCC (the fixed-UID one, plus `SYS_CHROOT` only). **Target**: an admin network policy over the whole namespace and admission of internal-registry images only |

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
| Development | full powers in its environment, without privilege on the node; planned: one ephemeral virtual cluster per project, recreated from the forge | no access to deployment or production data; everything is versioned | in acceptance testing |
| Deployment | limited to the applications namespace | approval of the plan, then of each command | planned |
| Maintenance | cluster administrator | approval of the plan, then of **every** command | planned |
| Supervision | read-only on the cluster and metrics | secret filter on everything it returns | planned |

- **No agent reaches the workflow engine or writes to the bus**: the dispatcher is their only client and only publisher.
- **Proven identity**: each request presents a short-lived projected service account token, checked against the Kubernetes API.
- **One key per executor**, known to it and to the dispatcher only.
- **One model-router key per agent**, limited to the local background model and embedding; the router's master key no longer leaves its pod, and it has been rotated ([Models by Role](concepts/13-modeles-par-role.en.md)).
- **Agents' web tools without internal addresses** (`allow_private_urls` off, against request forgery towards the cluster); online model catalog off.
- **Administrator alerts outside the platform**: a dedicated bot, which only writes to the administrator, receives the `warning` and `critical` alerts of both Alertmanagers; its token only exists in the two monitoring namespaces; no agent has access to it ([Observability](concepts/10-observabilite.en.md)).
- **Administration availability**: the cluster read pod and the Git forge are in a priority class no other workload can evict ([`deploy/okd/cluster/`](../deploy/okd/cluster/)).
- **Human approvals** through a single path today, the workflow engine's interface, restricted to the administration group (the chat interface, with the person's token relayed, will become the first path); the authenticated author of each signal is checked against the approver list; an approval is valid once.

---

# External Data Acquisition

External information is retrieved through a dedicated isolation layer. The DMZ layer extracts, sanitizes, removes executable content and delivers purified text to the internal system.

This prevents malicious scripts and tracking mechanisms from entering the platform. Nothing coming from the web is stored in memory until the [Semantic Tribunal](concepts/05-tribunal-semantique.en.md) is in service.

---

# Data Protection

- strict access control: SSO, groups; models enforced by the server per role (children and guests on the local model), one model-router virtual key per use, the master key confined to the router (see [Models by Role](concepts/13-modeles-par-role.en.md));
- a tool acting for the person receives their identity through a token relayed on a single route, to a closed list of servers, verified then exchanged for a token issued to the tool; the service keeps its own permissions, and the model never sees the token (see [Identity Relay](concepts/12-relais-identite.en.md)); towards a cockpit summary route, the token is verified as is: an audience specific to the application (added by a mapper on the interface's client), no additional issuer, a rejected token gets a 403 and never a redirect;
- applications displayed in the cockpit: each one only accepts being framed by the interface (`frame-ancestors`), the interface's list of frames is closed and tested, and a message from a frame is accepted only if it comes from the expected origin **and** frame; the identity provider's sign-in page is still refused in a frame ("Sign in again" opens a tab). Planned: access to the applications through the cockpit only, with an exception for the administrator; this is a usage rule, not a security barrier, since each application keeps its own sign-in;
- model outputs that leave the conversation are wrapped in deterministic checks: a place extracted by the model is kept only if it appears in the message or among the saved places, a document identifier comes from a tool result and never from the model, a path opened in the cockpit has a closed form checked again by the browser, a place given by coordinates is only inserted by the server (coordinates coming from the model are removed) and an external weather service only receives the municipality's centre, rounded; inserting text into an open document (in service) only happens if the analysis asks for it and an editable document is open, as sanitised, bounded plain text, through a closed list of messages; an application's context (module, page) only adds one line to the system message, never a permission;
- secrets managed through Kubernetes: manifests contain none; a Secret is created from standard input, never as a command argument (visible in the process list), and no value is printed; a value found in a repository's history is changed, without rewriting history;
- repositories read through a read-only deploy key, specific to each repository, never through a forge administrator's token: **in place** for the school's content sync and for the builds of the interface and of the visualisation tool. **Remaining**: the forge administrator's token is still used for pushing and for other builds; inventory of its uses, then tokens limited per use;
- relational database: **one role per database, no superuser**; the superuser only connects locally;
- trust of the authentication relays: the interface's oauth2-proxy only believes the forwarded client address when it comes from the ingress router; likewise for every other oauth2-proxy (modules, visualisation, workflow interface);
- interface and household devices without external dependencies: browser fonts and libraries served by the image, no CDN in the content security policy;
- permanent chat and video calls without end-to-end encryption, a deliberate choice: a platform administrator can read the rooms; chat media have no backup;
- tokens masked in the relays' access logs; model-router logs at `INFO`, never `DEBUG` (which would write every full request);
- retention: the model router's detailed log and workflow history 30 days; object-storage trash 30 days; metrics 15 days; conversations and applications without automatic purge;
- **scheduled backups: target**. Today, full manual backups before each operation; forge repositories each have **one** private mirror at an external host, checked every hour ([Visualisation module](modules/visualisation/README.en.md)); work happens in the forge only, and the default branch of public mirrors is protected against force-push and deletion, and some repositories never get one (transcripts of the coding-assistant sessions). Target: an encrypted backup in Europe for sensitive repositories, mandatory in a professional setting;
- **minimisation of working notes**: the logs and plans read by coding assistants contain no child's first name and no sensitive data (health, schooling, address), only roles; a pre-commit hook rejects forbidden terms by their fingerprints (HMAC), without ever displaying them; history is not rewritten;
- audit logging;
- two-factor authentication: **target**;
- encrypted volumes: **target**, not yet in place (unencrypted local volumes).

Persistent data (vector databases, relational databases, repositories) lives on the server's local volumes; encryption at rest is still to be set up.

---

# Interaction Logging

- **In place**: the model router's request log (routing, costs, refusals); the history of each delegation workflow (30 days), with the author of each approval; dated events published by the dispatcher.
- **In place**: service metrics and alert rules, including the removal of the VPN filter by its safeguard; filtered alerts (warnings and criticals, one message per problem, resolution notice) sent to the administrator outside the platform; a copy to the dispatcher, which logs them (see [Observability](concepts/10-observabilite.en.md)).
- **Target**: raw history of exchanges in Git, for audit, replay and sourcing; durable incident register and "incident" workflow; metrics on a persistent volume (15 days in the pod's memory today).

---

# Planned Improvements

- leak filter (DLP) before any output to an external model;
- Semantic Tribunal before storing anything from the web;
- default deny in `sophia-memory`; admin network policy and image admission in `sophia-sandbox`;
- egress control for the agents namespace;
- restricting the identity provider's internal port to client namespaces;
- access to the applications through the cockpit only, with an exception for the administrator;
- update and vulnerability watch for pinned images (local scanner, update requests opened without automatic merge, report to the administrator);
- scheduled, encrypted backups, with a restore test;
- two-factor authentication for administration accounts and guardians;
- mutual TLS between the dispatcher and executors;
- encrypted volumes.
