# The Agent Pantheon: Specialization and Confinement

The **Agent Pantheon** is the set of specialized agents operating within the SophIA architecture. Each agent has a strictly defined role, rights, and scope of action.

The goal is to specialize behaviors rather than entrust all tasks to a generalist agent, which would be harder to control and audit.

---

## Design principle

In a multi-agent architecture, the main risk is the dilution of responsibilities. An agent capable of doing everything is an agent capable of doing anything.

The Agent Pantheon addresses this problem with three rules:

1. **One agent, one domain.** Each agent specializes in one type of task and cannot perform others.
2. **Minimal rights.** Each agent has the strictly necessary permissions for its tasks, and nothing more. The guarantee comes from the executor's rights, never from the instruction it receives.
3. **No agent talks to another.** Every request goes through a deterministic component, the **dispatcher**, which decides without a model.

**Model-agnostic.** Each agent being a pod, each one can use a different model, or none: agentic behavior (specialization, confinement, output format) is enforced by the infrastructure, not assumed from the model.

**Autonomy where it is the job.** An autonomous agent engine (Hermes Agent, pinned version) is only used where a free loop with tools is the work itself. Elsewhere, thinking is a model call inside a workflow written in code (see [Deterministic Automation](09-automation-deterministe.en.md)).

---

## Two layers

| Layer | Who | Role |
|---|---|---|
| **Top** | the chat interface, and through it the users | identity, guards, short answers, **human approvals**; it becomes a **requester** of the dispatcher for what it cannot do alone |
| **Bottom** | the pantheon agents | **executors**, reached by the dispatcher only |

Memory (RAG) and the language model are **services** called by both layers, each with its own rights: they belong to no agent.

---

## The agents

The architecture defines four fundamental roles, plus a planner. The list can be extended.

| Agent | Domain | Rights | Engine | Status |
|---|---|---|---|---|
| **Hephaistos** | development | full powers in its development environment, one child cluster per project; everything it produces is versioned in the Git forge | autonomous agent | in acceptance testing, first executor behind the dispatcher |
| **Ouranos** | application deployment | limited to the applications namespace | agent, closed tool list, every command approved | planned |
| **Athena** | platform maintenance | cluster administrator, **every command approved** by a human after the plan is approved | agent, closed tool list (the terminal under approval) | planned |
| **Dionysos** | supervision | read-only on the whole cluster and on metrics; can alert, never act | deterministic read functions exposed to the dispatcher, in a separate pod, without node network access or secrets, with a read-only account; interpretation is left to the model, inside a workflow | planned: designed and tested, not deployed |
| **Planner** | open goals: break them down, then share them out among agents | no rights of its own: it only makes requests to the dispatcher | workflow in code, one model decision at a time | planned, prototype to be compared with a planner agent |

Athena and Dionysos never request anything. Only the planner, or the interface, assigns a mission.

---

## The dispatcher

The dispatcher is a service without a model, in `sophia-core`. It is the **only client of the durable workflow engine** (Temporal) and the **only publisher of events** (RabbitMQ).

1. **Request.** A requester sends a type (`lecture` for read, `mission`, `consultation`), a target and a goal in text. A request carries no right, no command, no approval.
2. **Identity.** It is proven, not declared: the pod presents a short-lived projected service account token, checked against the Kubernetes API. Hence **one service account per agent**.
3. **Decision.** A versioned rule table, read at startup, says who may ask what of whom, with which approvals and quotas. Everything else is refused and logged. A model cannot change these rules.
4. **Execution.** One durable workflow per request (its id is the task's) calls the executor once, follows its progress, stops it at the maximum duration. An agent's work is never retried: a retry is a new request.
5. **Destination filters.** Deterministic workflow steps, chosen by destination: secret detection on supervision answers, leak filter before any output to an external model, semantic tribunal on the way back. A missing or uncertain filter stops the workflow: nothing passes by default.
6. **Events.** Each step publishes a dated event on the bus, signed by the dispatcher's account; consumers refuse any other publisher.

**Human approvals.** Two levels: approving the plan before departure, then approving each command. Today they go through a single path, the workflow engine's interface, restricted to the administration group; they will move into the chat interface, with the person's token relayed and verified, the workflow engine's interface staying the fallback: the authenticated author of each signal is recorded in the history, and only an approver from the list is accepted. A signal carries only a decision and a hash, never a command. An approval is valid once: nothing is written into a permanent allow list.

Status: **in service** for rules, workflow, events and the mission to development (in acceptance testing); the first real requester, the Sophia agent, completed the full round trip entirely on the local model. **Ready** (written and tested, at the next build): one mission at a time per executor, and local-model slots by time of day. **Planned**: the interface as requester, reads to supervision, deployment and maintenance missions, consulting an external model (after the leak filter and the tribunal), mutual TLS.

---

## Confinement and isolation

- **One namespace shared by the agents.** Isolation does not come from the namespace, but from a service account and a UID specific to each pod, from NetworkPolicies that open the agents' entry to the dispatcher only, and from each account's rights.
- **No agent access to the workflow engine, no write access to the bus.** An executor has no way to reach another agent: no other agent's key, no workflow engine, no bus.
- **A key per executor**, known to it and to the dispatcher only.
- **One model-router key per agent**, limited to the local background model and embedding: no agent holds the router's master key or a remote model.
- **The bus has no agent accounts any more**: their queues are removed; agents are not bus clients.
- **Closed tool list** per agent, checked in non-regression testing: the tools actually given to the model are listed at every update of the agent engine, whose defaults may change.

---

## Position in the architecture

The Agent Pantheon relies on:

- the dispatcher (`sophia-core`) for any request between layers or between agents;
- development environments (`sophia-sandbox`) for isolated execution;
- MCP tools (`sophia-skills`) for local capabilities;
- human approval, enforced by code, on deployment and infrastructure.

---

## Objective

Structure the system's intelligence into specialized domains, each isolated, auditable and controlled independently. The attack surface shrinks to a single component to protect strongly, the dispatcher; an agent can be added, replaced or removed without impact on the rest.
