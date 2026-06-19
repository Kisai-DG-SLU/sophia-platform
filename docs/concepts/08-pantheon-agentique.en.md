# The Agent Pantheon: Specialization and Confinement

The **Agent Pantheon** is the set of specialized agents operating within the SophIA architecture. Each agent has a strictly defined role, rights, and scope of action.

The goal is to specialize behaviors rather than entrust all tasks to a generalist agent, which would be harder to control and audit.

---

## Design principle

In a multi-agent architecture, the main risk is the dilution of responsibilities. An agent capable of doing everything is an agent capable of doing anything.

The Agent Pantheon addresses this problem by applying two strict rules:

1. **One agent, one domain.** Each agent specializes in one type of task and cannot perform others.
2. **Minimal rights.** Each agent has the strictly necessary permissions to execute its tasks, and nothing more.

This approach limits the impact of erroneous or malicious behavior: a compromised agent cannot leave its domain.

---

## The agents

The architecture defines four fundamental agent roles. This list is not exhaustive and can be extended according to the organization's needs.

### Hephaistos (development)

Agent in charge of developing new tools and components. It operates exclusively in a sterile sandbox environment, isolated from the production system.

Its scope:

- code creation in an isolated environment
- test execution in the sandbox
- submission of validated components to the validation pipeline

It has no access to deployment, persistent memory, or production data.

### Ouranos (deployment)

Agent in charge of deploying and exposing components validated by the validation pipeline.

Its scope:

- deployment in pre-production and production spaces
- service exposure through authorized interfaces
- application of validated configurations

It has no access to source code under development or unvalidated raw data.

### Athena (maintenance)

Agent in charge of platform maintenance and applying fixes.

Its scope:

- component health monitoring
- application of validated fixes
- execution of planned maintenance tasks

Athena is subject to a specific security rule: any action impacting the system is subject to an external deterministic script that validates or rejects the operation, independently of the model's decision. This mechanism, called code-enforced Human-In-The-Loop (HITL), guarantees that no critical action is executed based solely on inference.

### Dionysos (supervision)

Agent in charge of overall architecture and agent supervision.

Its scope:

- agent behavior monitoring
- anomaly and deviation detection
- alert escalation

Dionysos has read-only access to the entire system. It can alert but cannot act directly on components.

---

## Confinement and isolation

Each agent operates in a dedicated Kubernetes namespace, with NetworkPolicies restricting its incoming and outgoing communications.

Agents cannot communicate directly with each other. Any inter-agent interaction transits through the central orchestrator (`sophia-core`), which applies routing and security rules.

---

## Position in the architecture

The Agent Pantheon relies on:

- the orchestrator (`sophia-core`) for routing requests to the appropriate agent
- workspaces (`sophia-sandbox`) for isolated execution environments
- MCP tools (`sophia-skills`) for external capabilities
- the automated and human validation pipeline to validate actions before deployment

---

## Objective

The Agent Pantheon structures the system's intelligence into specialized domains, each isolated, auditable, and independently controlled. This architecture reduces the attack surface, facilitates debugging, and allows progressive evolution by adding or replacing agents without impact on the rest of the system.
