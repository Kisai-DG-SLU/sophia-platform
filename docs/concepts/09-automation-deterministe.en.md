# Deterministic Automation: Engine Separation

The **Deterministic Automation** module defines the strict separation between thinking, handled by language models, and process execution, handled by deterministic engines.

The goal is to avoid entrusting a probabilistic system (a language model) with the execution of processes that require absolute reliability.

---

## Problem

Language models are probabilistic systems. Even with a high success rate, they keep a non-zero probability of error, off-topic output or hallucination.

For a creative or exploratory task, this variability is acceptable. For a reproducible process (sending notifications, updating databases, triggering an approval, acting on the infrastructure), it is not.

---

## Principle

**Code orchestrates, the model thinks, rules decide.**

- **Thinking** is a model call: understand, break down, propose. Its result is probabilistic and subject to validation.
- **Executing** belongs to a deterministic engine: the process runs correctly, or fails with an identifiable cause.
- **Execution autonomy**, that is a free agent loop with tools, is reserved for roles whose job it is, such as development (see [Agent Pantheon](08-pantheon-agentique.en.md)).

An agent can trigger a workflow, it does not drive its execution. Conversely, **a workflow can call on the model at a defined step**: this is SophIA's general pattern.

---

## The workflow calls on the model

Whenever thinking is needed before acting, the same pattern applies:

1. **Analysis.** The model receives the context and returns an answer **in constrained output** (an imposed schema): for example "next step: tool, target, arguments".
2. **Decision.** Deterministic rules validate the answer: tool from the closed list, allowed target, well-formed arguments, quota, human approval required or not.
3. **Execution.** A deterministic skill makes the call, or the dispatcher passes the request to the relevant agent.
4. **Return.** The result goes back to the model, which summarizes or proposes the next step.

The loop is **bounded by code** (number of steps, duration). The model makes **one decision at a time**, rather than a whole plan: a modest local model is enough, and each decision stays checkable.

| Use | What the model does | Status |
|---|---|---|
| **Chat interface** | understands the request and picks the tool; the server builds the call | in service |
| **Delegations** | nothing: the dispatcher decides by its rules, the workflow executes | in service |
| **Planner** for open goals | breaks the goal down, one step at a time, among tools and agents | planned (prototype) |
| **Maintenance** | writes a proposal (the why and the manifest); a human approves it, then each command | planned |
| **Incidents** | diagnoses from a deterministic collection and proposes a plan (see [Observability](10-observabilite.en.md)) | planned |

---

## Defining workflows

Workflows are written explicitly, in code or through visual programming. Each one specifies:

- triggering events
- execution steps
- branching conditions, evaluated by logical operators and not by a model
- error actions: a failed step interrupts the workflow and triggers the defined procedure
- notifications and logging

---

## Engines

| Engine | Use | Status |
|---|---|---|
| **Temporal** | durable workflows in code: delegations between agents, then the planner and incidents. Each workflow's history serves as its log | in service for delegations |
| **n8n** | automations through visual programming (connectors, notifications) | planned, deployed with the first tool that needs it; off the delegation path |

The durable workflow engine has a single application client, the dispatcher (`sophia-core`): no agent reaches it directly.

---

## Objective

Guarantee that reproducible processes run reliably and predictably, whatever the model's state. The model brings understanding where it is needed; code and rules stay in charge of what is done.
