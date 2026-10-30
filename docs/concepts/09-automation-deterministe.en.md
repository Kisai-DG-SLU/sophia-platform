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

## Guards on the model's output

Any output of the model that leaves the conversation (a place passed to a tool, an identifier, a path, a text inserted elsewhere) goes through a **deterministic check**. These are not regular expressions used to understand an intent: the model understands, then rules check what it returned. Examples from the chat interface:

| Guard | Analysis (model) | Decision (rules) | Execution | Status |
|---|---|---|---|---|
| **A place must be said** | extracts the places from the request | a place is kept only if it appears in the current message, or is the name of a saved place; also applies to the model calling a tool freely | call to the weather, place, distance or map tool, or a question written by the server | in service, under acceptance testing |
| **A moment is never a place** | same | a closed list of moments is removed from places, as a second net | same | in service |
| **Expected country** | — | a result outside the expected countries, not named by the person, must be confirmed | confirmation sentence written by the server | in service |
| **Current place** | — | the server keeps the last place that came from the message and was accepted; the model never rereads the history to find a place | "and tomorrow?" reuses that place | in service, verified |
| **Place objects inserted by the server** | names a saved place | for a saved place, the server passes the town or coordinates to the tools; a place object or coordinates coming from the model are removed; the weather goes through the town centre, never the address | tool call | in service, under acceptance testing |
| **Identifier from the tool** | "open" intent and search terms | a document's identifier comes only from the tool's result (checked shape), never from the model; choice by number of results | event to the cockpit, path re-checked by the browser | in service, under acceptance testing |
| **Closed-shape path** | — | a path received from an application is refused if it leaves its closed shape, then the address is rebuilt on the module's origin and checked again | the document opens in a frame | in service, under acceptance testing |
| **Direct insertion into a document** | request to write or rephrase in the open document | intent offered only if the editor announced itself as editable; only the reply's visible text, sanitised and bounded; selection read for a local model only; closed list of relayed messages, never a command or a script; origins and frame checked; nothing from history | insertion at the cursor, or at the end if there was no click, undone with Ctrl+Z; acknowledgement with the position, or a named error | in service, verified |
| **An application's context** | — | the module header, re-validated against the role's modules, only adds one line of context and no right; the page context sent by an application is accepted only from its origin and frame, closed-shape fields only, re-validated by the server (school: subject and topic, nothing about the child) | context line for the model | in service, under acceptance testing |
| **A command's text is never copied** | — | a summary meant for another interface never repeats the text of a command proposed by a model, only its existence and state | "awaiting approval" line in "What's new?" | in service, under acceptance testing |

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
