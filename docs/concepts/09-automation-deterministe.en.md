# Deterministic Automation: Engine Separation

The **Deterministic Automation** module defines the strict separation between cognitive orchestration, handled by AI agents, and process automation, handled by deterministic engines.

The goal is to avoid entrusting a probabilistic system (a language model) with the execution of business processes that require absolute reliability.

---

## Problem

Language models are probabilistic systems. Even with a high success rate, they retain a non-zero probability of error, off-topic responses, or hallucination.

For creative or exploratory tasks, this variability is acceptable. For reproducible business processes (sending notifications, updating databases, triggering validation workflows), it is not.

Entrusting process automation to an AI agent means introducing uncertainty where the organization expects certainty.

---

## Principle

SophIA strictly separates two types of execution:

**Cognitive orchestration**, handled by Agent Pantheon agents. It is based on language models and manages tasks requiring reasoning, adaptation, and contextual understanding. Its output is probabilistic and subject to validation.

**Deterministic automation**, handled by a workflow engine. It executes defined, immutable, and reproducible processes. Its output is binary: the process executes correctly or fails with an identifiable cause.

An agent can trigger a deterministic workflow, but does not control its execution. The workflow runs according to its internal rules, without model intervention.

---

## Operation

### Workflow definition

Workflows are defined explicitly, through a visual programming language or hard-coded configuration. Each workflow specifies:

- trigger events
- execution steps
- branching conditions
- error handling actions
- notifications and logging

### Execution

Workflow execution is entirely deterministic:

- steps follow in the defined order
- conditions are evaluated by logical operators, not by a model
- actions are executed by predefined connectors
- step failure interrupts the workflow and triggers the defined error procedure

### Agent interaction

An agent can trigger a workflow through the orchestrator. The request is transmitted to the automation engine, which executes it without further model intervention. The agent receives the result once execution is complete.

The reverse is also possible: a workflow can, at a defined step, solicit an agent for a reasoning task before continuing its deterministic execution.

---

## Position in the architecture

The automation engine operates in a dedicated namespace, isolated from inference and memory namespaces. It is accessible from `sophia-core` through a secure interface.

Possible technologies: n8n, Node-RED, StackStorm, Temporal, or any workflow engine meeting isolation and determinism requirements.

---

## Objective

Guarantee that reproducible business processes are executed reliably and predictably, independently of the state or performance of AI models. Deterministic automation and cognitive orchestration are complementary: the former ensures flow reliability, the latter brings intelligence where needed.
