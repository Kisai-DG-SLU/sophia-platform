# SophIA: actual state

State as of **15/11/2026**, for the reference installation: one physical server, a single-node cluster, one household. This page says, brick by brick, what runs, what is being built and what is still planned. The story is in the [pitch](pitch.en.md) and the order of work in the [roadmap](roadmap.en.md).

Three states:

- **Deployed**: in service in the reference installation. "Under acceptance testing" means the household is still trying it on its devices before calling it verified.
- **In progress**: decided and being built, or partly in place.
- **Planned**: to do, not started yet.

A brick is only called deployed if it runs **and** its reproducible recipe, or its page, is published in this repository.

---

## Foundation and security

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Single-node OKD cluster on a physical server | Deployed | namespaces per security zone, quotas and priority classes per namespace | [`deploy/`](../deploy/README.en.md), [`okd/cluster/`](../deploy/okd/cluster/README.en.md) |
| Access through the VPN only | Deployed | VPN filter on the node, with a safeguard that removes the table and alerts if it becomes unreadable | [`okd/host/wireguard/`](../deploy/okd/host/wireguard/README.en.md) |
| Persistent local storage | Deployed | named local volumes, dedicated logical volumes for data that grows | [persistent storage](../deploy/stockage-persistant.en.md) |
| Default ingress deny | Deployed, extension in progress | in place in the applications, orchestration and memory; the other namespaces follow | [security](security.en.md) |
| Images pinned by digest and vulnerability watch | In progress | inventory, local scanner, alert; version upgrades decided, never automatic | [security](security.en.md#planned-improvements) |
| Encryption of internal traffic | In progress | service by service, with the cluster's service certificates | [security](security.en.md) |
| Encrypted volumes | Planned | not in place yet: local volumes are not encrypted | [security](security.en.md#data-protection) |
| Two-factor authentication | Planned | administration accounts and household heads | [roadmap](roadmap.en.md) |

## Inference and models

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Local language model on GPU (text and vision) | Deployed | default local model of the interface and the modules, no network egress | [`okd/inference/`](../deploy/okd/inference/README.en.md), [inference and hardware](concepts/11-inference-materiel.en.md) |
| Voice on CPU (recognition and synthesis) | Deployed | the answer is read aloud while it is being written | [`okd/inference/`](../deploy/okd/inference/README.en.md) |
| Image generation on CPU | Deployed | protection rules before generation, classifier on each image produced | [`okd/inference/`](../deploy/okd/inference/README.en.md), [`okd/skills/`](../deploy/okd/skills/README.en.md) |
| Unified model router (LiteLLM) | Deployed | local and remote behind the same aliases, one virtual key per use, master key confined to the router | [`okd/core/`](../deploy/okd/core/README.en.md), [models by role](concepts/13-modeles-par-role.en.md) |
| Measurement of a mixture-of-experts model (GPU and RAM) | In progress | before any model change | [roadmap](roadmap.en.md) |
| Speculative decoding, new series of measurements | Planned | | |
| Camera: objects and faces on CPU | Planned | consent rules before any face is recorded | |

## Memory

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Vector database (Qdrant) and its schema, embedding service | Deployed | dedicated volume; embedding goes through the model router | [`okd/memory/`](../deploy/okd/memory/README.en.md) |
| S3 object storage | Deployed | recycle bin, versioned bucket for originals | [`okd/storage/`](../deploy/okd/storage/README.en.md) |
| Memory service | Deployed | originals in a versioned bucket, version registry, validated texts in the forge, validation by a single person, isolated file extraction | [`okd/memory/memoire/`](../deploy/okd/memory/memoire/README.en.md), [5D RAG](concepts/03-rag-5d.en.md) |
| Memory confidentiality levels | In progress | enforced for people in the memory service; agents stay at the public level as long as the dispatcher does not pass on the person served | [roadmap](roadmap.en.md) |
| Dashboard "Memory" page, memory tool of the chat | In progress | upload and validation page deployed; lookup from the chat under the person's identity | [interface](../deploy/okd/apps/chat-interface/README.en.md) |
| Memory front for agents | Planned | | |
| Ingestion pipeline | Planned | documents read from object storage, filed through the memory service | |
| Graph dimension | Planned | blocked until the image and volume are chosen | |

## Agents and orchestration

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Event bus (RabbitMQ) and durable workflows (Temporal) | Deployed | administration behind the identity provider; event consumers still to do | [RabbitMQ](../deploy/okd/core/rabbitmq/README.en.md), [Temporal](../deploy/okd/core/temporal/README.en.md) |
| Delegation dispatcher | Deployed | only Temporal client and only event publisher, decides by rules without a model | [`okd/core/repartiteur/`](../deploy/okd/core/repartiteur/README.en.md) |
| Pantheon agents on the local model | Deployed | "background" alias that leaves priority to the chat, one router key per agent | [`okd/hermes-system/`](../deploy/okd/hermes-system/README.en.md) |
| First executing agent (development) | Deployed, under acceptance testing | one mission at a time | [`okd/hermes-system/`](../deploy/okd/hermes-system/README.en.md) |
| Interface as a requester of the dispatcher | In progress | return channel for approvals and notifications | [roadmap](roadmap.en.md) |
| Mutual TLS between the dispatcher and the executors | Planned | | |
| Delegations to supervision, deployment and maintenance | Planned | two-level approvals | |
| Open-goal planner | Planned | workflow prototype, compared with a planner agent | |
| Deterministic automation (n8n) | Planned | with the first tool that needs it | [deterministic automation](concepts/09-automation-deterministe.en.md) |
| Leak filter, Semantic Tribunal, Ghost Search | Planned | | [DLP](concepts/07-dlp-filter.en.md), [Tribunal](concepts/05-tribunal-semantique.en.md), [Ghost Search](concepts/06-ghost-search.en.md) |

## Identity

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Single identity provider (Keycloak) | Deployed | one sign-in for every interface, household groups | [`okd/identity/`](../deploy/okd/identity/README.en.md) |
| Server-side authentication sessions | Deployed | a reserved key-value store, one user per application | [sessions](../deploy/okd/identity/sessions/README.en.md) |
| Identity relay down to tools and applications | Deployed | the person's token, one audience per service | [identity relay](concepts/12-relais-identite.en.md) |
| Account birth dates, read by an application | Deployed | read client limited to one group, no date in tokens | [identity](../deploy/okd/identity/README.en.md#account-birth-dates-read-by-an-application) |
| Single sign-on for administration tools (forge, cluster console) | In progress | | |

## Interface and dashboard

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Chat interface | Deployed | dedicated namespace, no key in the browser, no external dependency, model enforced by the server according to the role | [interface](../deploy/okd/apps/chat-interface/README.en.md) |
| Dashboard: applications in the centre, each under its own sign-in | Deployed | cooking, school, visualisation and finances verified; messaging, video calls and office suite under acceptance testing; mail and shopping added, under acceptance testing | [plugging a module in](modules/README.en.md#plugging-a-module-into-the-dashboard) |
| "What's new?", "Ask Sophia", Sophia opening the right page | Deployed, under acceptance testing | deterministic summaries from the applications | [interface](../deploy/okd/apps/chat-interface/README.en.md) |
| Signing out of the dashboard closes the modules | Deployed, under acceptance testing | | [interface](../deploy/okd/apps/chat-interface/README.en.md) |
| Household places and weather | Deployed | the weather service only receives the town centre; fallback cache verified | [interface](../deploy/okd/apps/chat-interface/README.en.md) |
| Local geocoding of recorded addresses | In progress | | |
| Access to the applications through the dashboard only | Planned | exception for the administrator (troubleshooting) | [modules](modules/README.en.md) |

## Modules

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Cooking | Deployed | meal planning, recipes generated under rules, shopping; verified in the dashboard | [Cooking](modules/cuisine/README.en.md) |
| School | Deployed | playful school, hints without the answer; verified on computers, sign-in again on phones under acceptance testing | [School](modules/ecole/README.en.md) |
| Shopping | Deployed | product choice according to household rules, express basket; display in the dashboard under acceptance testing | [Shopping](modules/courses/README.en.md) |
| Visualisation | Deployed | measured state of each component, hourly check of repository mirrors; for the administrator | [Visualisation](modules/visualisation/README.en.md) |
| Business applications (customers, invoicing, finances) | Deployed | one shared database per domain, no API and no copy between them | [shared data](architecture.en.md#data-shared-between-applications) |
| Shared household database (places, later the members) | Planned | written by the dashboard, read by the modules | [shared data](architecture.en.md#data-shared-between-applications) |
| Mail | In progress | display in the dashboard under acceptance testing | [roadmap](roadmap.en.md) |
| Assisted development (vibe coding) | In progress | study: visual mock-ups of each person's projects, agent tracking | [assisted development](development/opencode-workflow.en.md) |

## Communication and office suite

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Office suite: files and online editing | Deployed, under acceptance testing | documents found, opened and read from the chat under the person's identity; the editor's REST API is never exposed | [Office suite](modules/bureautique/README.en.md), [recipe](../deploy/okd/office/README.en.md) |
| One browser workstation per child (older tablets) | Deployed, under acceptance testing | switched on on demand, off when idle | [Office suite](modules/bureautique/README.en.md) |
| Household messaging (XMPP: Prosody, Converse.js) | Deployed, under acceptance testing | Family room, Android notifications without content, "tell" | [XMPP recipe](../deploy/okd/office/README.en.md#xmpp-messaging-final-version), [Communication](modules/communication/README.en.md) |
| End-to-end encryption refused on the server side | Deployed, under acceptance testing | household choice: the administrator can read the rooms | [recipe](../deploy/okd/office/README.en.md#encryption-refused-on-the-server-side) |
| Video calls (Jitsi Meet, browser only) | Deployed, under acceptance testing | media reachable through the VPN only | [persistent chat and video calls](../deploy/okd/office/README.en.md#persistent-chat-and-video-calls) |
| Dismantling the former messaging (Matrix) | In progress | readable until the end of acceptance testing | [Communication](modules/communication/README.en.md) |

## Operations

| Capability | State | Detail | Recipe or page |
|---|---|---|---|
| Minimal monitoring | Deployed | service metrics, alert rules, GPU, volume filling; filtered alerts sent to the administrator outside the platform | [`okd/monitoring/`](../deploy/okd/monitoring/README.en.md), [observability](concepts/10-observabilite.en.md) |
| "Incident" workflow and incident register | Planned | from the alarm to the approved plan, no automatic action | [observability](concepts/10-observabilite.en.md) |
| Scheduled, encrypted backup | In progress | not in service yet; recommended solutions: client-side encryption, a local copy and a sovereign off-site copy, restore test | [security](security.en.md#backup-and-storage-sovereign-solutions) |
| Reproducible recipes per component | Deployed | templates with variables and procedures published in this repository | [`deploy/`](../deploy/README.en.md) |
| Portability of an installation | In progress | node names and paths as variables in the templates; choosing the node of each volume remains | [roadmap](roadmap.en.md) |
| Drift check between the cluster and the repositories | In progress | read-only, deterministic, with an alert | |
| Cluster installation procedure | Planned | prerequisite for rebuilding the server in one day | |
| Compliance (GDPR, AI Act, ISO 27001) | In progress | designed: measured baseline, action plan, follow-up | [Visualisation](modules/visualisation/README.en.md) |
| Opening to other users, multi-tenant deployments | Planned | | [roadmap](roadmap.en.md) |
