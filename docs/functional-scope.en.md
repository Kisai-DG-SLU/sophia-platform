# Functional scope

This document describes **what SophIA must do, and for whom**. The [concept sheets](index.en.md#architectural-concepts) describe *how* each mechanism works; the [roadmap](roadmap.en.md) says *when*.

Each function carries a status: **operational**, **in progress** or **planned**. What is planned describes the target, not what exists today.

---

## At a glance

1. **The foundation is a sovereign AI platform**: a controlled Kubernetes cluster, multi-layer memory, a pantheon of specialized agents, and security enforced by the infrastructure rather than by the model.
2. **Functional building blocks are added on top**: conversation, search, on-demand tool development, automation, voice.
3. **Trajectory**: assemble open-source building blocks to move fast; once the solution works, some blocks may be rewritten by the platform's own agents.

---

## Intent

An **assistant for a household or an organization**: it converses, searches, builds tools as needs arise, and continuously enriches its memory to answer correctly and in the most appropriate way.

It relies on **deterministic tools when reliability requires it**, and on language models for creativity and reasoning.

The project is run to professional standards: reproducibility, resilience, auditability. **Limited hardware is treated as a study constraint**: the goal is to reach the target despite it, or to document the obstacles and the paths to get there.

---

## Users and roles

| Role | Access |
|---|---|
| **Administrator** | everything; any emergency access is notified and logged |
| **Guardian** | their own spaces; receives alerts about the protected users in their care |
| **Protected user** (for example a minor) | their personal and private space only; their guardian is alerted in critical situations |
| **Guest** | public information only |

Five confidentiality levels, from most open to most restricted: `public` > `family` (or group) > `personal` > `private` > `admin`.

---

## Cross-cutting principles

| Principle | Statement |
|---|---|
| **Everything is a project** | a professional activity, a personal project, a development, a study. A project brings together a **Brain** (memory, specifications), a **Repository** (deliverable) and a **Workspace** (ephemeral, never the source of truth) — see [Project Model](concepts/00-project-model.en.md) |
| **Conversations are projects** | each new conversation is **attached** to an existing project, to the global conversation project, or opened as a new project. A conversation that grows is **promoted** to a project of its own. Eventually everything is driven through conversation, development included |
| **Deterministic or model** | code orchestrates, the model thinks, rules decide: a business process runs in a deterministic engine; an agent may trigger it, not drive it; a workflow may call on the model at a defined step — see [Deterministic Automation](concepts/09-automation-deterministe.en.md) |
| **Two layers** | on top, the interface: identity, guards, short answers, human approvals; below, the agents, executors reached by the dispatcher only. The model and memory are services shared by both layers — see [Agentic Pantheon](concepts/08-pantheon-agentique.en.md) |
| **Answer correctly** | every statement is sourced from memory; an unverified inference is marked as such and remains to be checked |
| **Controlled enrichment** | every exchange may feed memory, with a confidence level; information from the web is stored only after validation and consent |
| **Reliability through infrastructure** | minimal rights, decisions by rules without a model, human approval enforced by code, constrained output, network isolation — whatever the model |
| **Agnosticism** | model, software and hardware are replaceable |
| **Sovereignty** | target: fully local inference. A remote model is only a development exception, chosen by routing — see [Inference and Hardware](concepts/11-inference-materiel.en.md) |

---

## Foundation functions

| Function | What it does | Status |
|---|---|---|
| **Orchestrator** | two roles. **The interface**, main interlocutor: listens, understands the request, answers simple requests with tools, collects approvals; for the rest, it becomes a **requester** of the dispatcher. **The planner**, for open goals: a workflow that breaks the goal down one decision at a time, has each step validated by rules and executed by the dispatcher, then turns the result into a readable report; the approved plan is versioned in Git. **Neither modifies the infrastructure itself** | in progress: interface operational for simple requests; requester and planner planned |
| **Agent pantheon** | one agent per domain, executors reached by the **dispatcher** only, which decides by rules without a model: read-only supervision, autonomous development, eventually in one ephemeral virtual cluster per project, deployment limited to applications, platform maintenance. Approval of the plan then of each command on deployment and infrastructure — see [Agentic Pantheon](concepts/08-pantheon-agentique.en.md) | in progress: dispatcher in service, development in acceptance testing; supervision, deployment and maintenance planned |
| **Asynchronous messaging** | one durable workflow per delegation (Temporal, whose only client is the dispatcher), progress events published on a bus (RabbitMQ) by the dispatcher alone, failed messages dead-lettered. Rationale: a delegation that codes, tests and fixes exceeds the time limits of a synchronous call | operational: workflows and events; the bus has no agent queues or accounts any more; event consumers planned |
| **Projects and conversations** | attachment and promotion of conversations (principle above), history kept and retrievable; per-project rights (hiding, invitations), attachment requests approved by an adult, a private journal per person | operational: server-side conversations, projects = Git repositories, rights and journal |
| **Memory** | a service called by the interface as well as by the agents, each according to its rights; writing to long-term memory belongs to the memory service, under the rules of tags and the tribunal. See the next section | in progress: embedding and the collection with its schema (18 tags) in service, object storage in service; memory API designed; ingestion and graph to rebuild |
| **Permissions** | roles and confidentiality levels above; alerts by email, SMS or interface | in progress: roles and single sign-on (SSO) operational; models enforced by the server per role ([Models by Role](concepts/13-modeles-par-role.en.md)); memory confidentiality and alerts planned |
| **Safe external knowledge** | isolated, sanitized web acquisition ([Paranoid Airlock](concepts/04-sas-paranoiaque.en.md)), decoy queries ([Ghost Search](concepts/06-ghost-search.en.md)), cross-validation before ingestion ([Semantic Tribunal](concepts/05-tribunal-semantique.en.md)) | in progress: acquisition airlock operational (self-hosted metasearch, pages reduced to text without scripts, internal addresses refused); decoy queries and tribunal planned |
| **Observability and response** | metrics, alert rules; an alarm becomes a request to the dispatcher, which starts an "incident" workflow: collection, diagnosis, plan, notification, approved execution, no automatic action at first — see [Observability](concepts/10-observabilite.en.md) | in progress: platform and service metrics, alert rules (volume fill included), node exporter (graphics card, VPN safeguard), measured state of each component and mirror check ([Visualisation module](modules/visualisation/README.en.md)) in service; filtered alerts sent to the administrator outside the platform, a copy logged by the dispatcher; incident register and "incident" workflow planned |
| **Leak filter** | before any call to a remote service: allow, anonymize or block — see [DLP Filter](concepts/07-dlp-filter.en.md) | planned |
| **Inference** | one model per agent through the router; switching between a remote and a local model is a routing change; comparative quality and cost measurement | operational: local model by default on the server's GPU (reliable tool calls) for the interface and modules; agents on the local model through a background alias, card slots shared by time of day, CPU priorities and quotas in service — see [Inference and Hardware](concepts/11-inference-materiel.en.md) |
| **Governance** | cost per token and per project, per-key budgets; log of requests, routing decisions and blocks; after-the-fact analysis | in progress: costs and budgets operational; one key per use; retention decided; compliance (GDPR, AI Act, ISO 27001) designed |
| **Industrialization** | reproducible recipe, multi-tenant environments, reference architecture | planned |

---

## Functional building blocks

| Block | What it does | Status |
|---|---|---|
| **Conversation** | multi-model web interface, with displayed cost and history; no key in the browser; mandatory sign-in, profile and context adapted to each person (current date and time included) | operational, in its own namespace; new-version notice; visual themes to choose (light and dark) and calendar themes offered on the day, fonts and libraries embedded, no CDN; the person's files found, opened and read (local model only) from the chat |
| **Search** | memory first; the web through the airlock when information is missing, sources ranked by reliability and cited; forecast data for weather; consent before storing | in progress: web search operational, memory to be built |
| **Arbiter** | a high-end external model, queried by the agents through the message queue, **after anonymization** by the leak filter | planned |
| **On-demand tool development** | a need expressed in conversation becomes a project; one agent codes and tests it in the sandbox; another deploys it after human approval | in progress: development environments driven by agents |
| **Deterministic automation** | workflow engine triggered by agents, and able to call on them at a defined step | planned |
| **Business tools** | office, graphics, etc., exposed to agents as tools | in progress: office suite (files, online editing) in service, files MCP tool under the person's identity ([Office module](modules/bureautique/README.en.md)); the household's permanent chat and video calls installed, in acceptance testing ([Communication module](modules/communication/README.en.md)); mail planned; graphics later |
| **Voice and presence** | speech synthesis and recognition, speech-to-speech, vision; eventually an open-source companion robot for a physical presence in the living space | in progress: local speech recognition and synthesis on CPU (dictation sent, reply read aloud); speech-to-speech, vision and robot planned |

---

## Memory: two complementary axes

### The five storage layers (5D RAG)

| # | Layer | Role | Example |
|---|---|---|---|
| 1 | Git repository | versioned source of truth | Forgejo |
| 2 | Relational database | timestamped facts, references to stored files, rights, metadata | PostgreSQL |
| 3 | Vector database | semantic proximity | Qdrant |
| 4 | Graph database | complex or cross-cutting relationships | Neo4j |
| 5 | Note graph | human visualization, synchronized from the other layers | Obsidian |

Details: [5D RAG](concepts/03-rag-5d.en.md).

### Memory types (5 + 1)

| Type | Content | Layers |
|---|---|---|
| Semantic | stable facts and knowledge | vector + relational |
| Episodic | dated events, conversations, decisions | relational |
| Procedural | agent roles, templates, prompts, workflows | Git |
| Personal and private | journal, confidential exchanges, isolated by confidentiality level | vector + relational |
| Graph | relationships between projects, decisions, consequences | graph |
| **+1: raw history** | full transcripts of exchanges, for audit, replay and sourcing | Git |

Every piece of information carries a set of **tags** defined by the administrator (author, dates, memory type, provenance, format, confidence level, confidentiality, project, validation status…). Agents cannot create new ones.

---

## Hardware

The reference implementation runs on a single node with entry-level GPUs — see [POC infrastructure](../deploy/infrastructure.en.md). The intended layout assigns **one family of tasks per card**: language model, embedding, voice and vision. Each card hosts its own models, which isolates the workloads. Today, a single card carries the language model, shared by chat, modules and agents; voice, images and embedding run on CPU — see [Inference and Hardware](concepts/11-inference-materiel.en.md).

---

## Trajectory

| Stage | Choice |
|---|---|
| **1. Assemble** | existing open-source building blocks, to move fast |
| **2. Make it work** | complete foundation, then building blocks; development shortcuts (remote models, manual steps) are lifted one by one |
| **3. Rewrite, possibly** | some blocks rewritten by the platform's own agents, for performance, fit to need and maintainability — **only once the solution works** |

---

See also: [Vision](vision.en.md) · [Pitch](pitch.en.md) · [Architecture](architecture.en.md) · [Roadmap](roadmap.en.md)
