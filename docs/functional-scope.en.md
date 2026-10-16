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
| **Deterministic or model** | a business process runs in a deterministic engine; an agent may trigger it, not drive it — see [Deterministic Automation](concepts/09-automation-deterministe.en.md) |
| **Answer correctly** | every statement is sourced from memory; an unverified inference is marked as such and remains to be checked |
| **Controlled enrichment** | every exchange may feed memory, with a confidence level; information from the web is stored only after validation and consent |
| **Reliability through infrastructure** | minimal rights, human approval enforced by code, strict JSON between agents, network isolation — whatever the model |
| **Agnosticism** | model, software and hardware are replaceable |
| **Sovereignty** | target: fully local inference. A remote model remains a routing choice, usable during development |

---

## Foundation functions

| Function | What it does | Status |
|---|---|---|
| **Orchestrator** | main interlocutor: listens, challenges the request, validates the plan (intent, action, report), writes the specification to Git, delegates, turns the agents' results into a readable report. **It never modifies the infrastructure itself** | in progress |
| **Agent pantheon** | one agent per domain: read-only supervision, sandboxed development, application deployment, infrastructure maintenance. Human approval on deployment and infrastructure — see [Agentic Pantheon](concepts/08-pantheon-agentique.en.md) | in progress: agents deployed |
| **Asynchronous messaging** | one queue per agent, dead-letter queues, progress events. Rationale: a delegation that codes, tests and fixes exceeds the time limits of a synchronous call | planned |
| **Projects and conversations** | attachment and promotion of conversations (principle above), history kept and retrievable; per-project rights (hiding, invitations), attachment requests approved by an adult, a private journal per person | operational: server-side conversations, projects = Git repositories, rights and journal |
| **Memory** | see the next section | in progress: layers deployed, ingestion to be built |
| **Permissions** | roles and confidentiality levels above; alerts by email, SMS or interface | in progress: roles and single sign-on (SSO) operational; memory confidentiality and alerts planned |
| **Safe external knowledge** | isolated, sanitized web acquisition ([Paranoid Airlock](concepts/04-sas-paranoiaque.en.md)), decoy queries ([Ghost Search](concepts/06-ghost-search.en.md)), cross-validation before ingestion ([Semantic Tribunal](concepts/05-tribunal-semantique.en.md)) | in progress: acquisition airlock operational (self-hosted metasearch, pages reduced to text without scripts, internal addresses refused); decoy queries and tribunal planned |
| **Leak filter** | before any call to a remote service: allow, anonymize or block — see [DLP Filter](concepts/07-dlp-filter.en.md) | planned |
| **Inference** | one model per agent through the router; switching between a remote and a local model is a routing change; comparative quality and cost measurement | in progress: router operational, local inference to be deployed |
| **Governance** | cost per token and per project, per-key budgets; log of requests, routing decisions and blocks; after-the-fact analysis | in progress: costs and budgets operational |
| **Industrialization** | reproducible recipe, multi-tenant environments, reference architecture | planned |

---

## Functional building blocks

| Block | What it does | Status |
|---|---|---|
| **Conversation** | multi-model web interface, with displayed cost and history; no key in the browser; mandatory sign-in, profile and context adapted to each person (current date and time included) | operational |
| **Search** | memory first; the web through the airlock when information is missing, sources ranked by reliability and cited; forecast data for weather; consent before storing | in progress: web search operational, memory to be built |
| **Arbiter** | a high-end external model, queried by the agents through the message queue, **after anonymization** by the leak filter | planned |
| **On-demand tool development** | a need expressed in conversation becomes a project; one agent codes and tests it in the sandbox; another deploys it after human approval | in progress: development environments driven by agents |
| **Deterministic automation** | workflow engine triggered by agents, and able to call on them at a defined step | planned |
| **Business tools** | office, graphics, etc., exposed to agents as tools | planned, longer term |
| **Voice and presence** | speech synthesis and recognition, speech-to-speech, vision; eventually an open-source companion robot for a physical presence in the living space | planned, longer term |

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

The reference implementation runs on a single node with entry-level GPUs — see [POC infrastructure](../deploy/infrastructure.en.md). The intended layout assigns **one family of tasks per card**: language model, embedding, voice and vision. Each card hosts its own models, which isolates the workloads.

---

## Trajectory

| Stage | Choice |
|---|---|
| **1. Assemble** | existing open-source building blocks, to move fast |
| **2. Make it work** | complete foundation, then building blocks; development shortcuts (remote models, manual steps) are lifted one by one |
| **3. Rewrite, possibly** | some blocks rewritten by the platform's own agents, for performance, fit to need and maintainability — **only once the solution works** |

---

See also: [Vision](vision.en.md) · [Pitch](pitch.en.md) · [Architecture](architecture.en.md) · [Roadmap](roadmap.en.md)
