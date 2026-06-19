# Context Management

**Context Management** defines how SophIA builds, controls, and limits the context provided to artificial intelligence models.

In most current systems, context is built implicitly from chat history, approximate RAG, system instructions, and available tools. This approach works for simple use cases but becomes unstable in complex systems.

SophIA treats context as a critical resource that must be explicitly managed.

---

## Problem

Language models suffer from several structural limitations:

- limited context window
- progressive information loss
- context pollution by irrelevant elements
- difficulty distinguishing important instructions
- excessive reliance on conversational history

In multi-agent systems, these problems are amplified: useless context accumulation, information duplication, loss of coherence between agents.

Without explicit control, the system becomes slow, unstable, and unpredictable.

---

## Principle

Context Management is based on a simple idea: the context sent to the model must be intentionally constructed, not passively inherited from a conversation.

The system dynamically assembles context from multiple sources.

---

## Context sources

### System instructions

Define the agent's role and general rules: assistant role, security constraints, expected response style.

### Project specifications

Specifications describe project objectives. They typically come from the Brain.

### Memory

Persistent information can be injected from memory: past decisions, indexed knowledge, research results.

### Task state

Context may include the current state of a task: current step, intermediate result, limited action history.

### Available tools

The model must be aware of available capabilities: repository access, MCP tools, workspace access.

---

## Context construction

Context is dynamically built by the orchestrator. The typical process is:

1. identification of the relevant project
2. retrieval of pertinent specifications
3. optional memory retrieval
4. selection of available tools
5. final prompt assembly

This construction minimizes noise and maximizes relevance.

---

## Voluntary context limitation

An important principle of SophIA is to voluntarily limit context. More context does not necessarily mean better responses.

An overly broad context can cause dilution of important information, interpretation errors, and increased cost and latency.

The system therefore favors targeted, structured, and limited context.

---

## Relationship with other concepts

Context Management is closely linked to several other mechanisms in the architecture:

- **Workspace Management** provides the execution environment but is not a source of lasting context.
- **Project Model** identifies relevant context sources for a given project.
- **Tribunal Semantique** validates knowledge before its integration into memory.
- **RAG 5D** provides the memory structure exploitable as a context source.

---

## Objective

The goal of Context Management is to ensure models have the right information, that context remains controlled, that agents stay predictable, and that the system remains scalable.

In SophIA, context is not a side effect of conversation. It becomes an architectural component in its own right.
