# Workspace Management

**Workspace Management** defines how SophIA manages work environments for agents and users.

The goal is to guarantee reproducibility, isolation, and traceability.

---

## Problem

In agent-based systems, work environments can become chaotic: implicit dependencies, machine-dependent local paths, mixing of memory, code, and execution.

This makes systems difficult to maintain and reproduce.

---

## Principle

SophIA strictly separates three elements:

### Brain

The **Brain** contains the project's memory and specifications.

Examples:

- Brain repository for a development project
- Brain repository for an architecture project

Content: specifications, architectural decisions, project configuration.

---

### Repository

The repository contains the actual work: code, notebooks, resources.

---

### Workspace

The workspace is a temporary execution environment: ephemeral, isolated, and reproducible. It can be local, in a Kubernetes pod, or in a sandbox environment.

---

## Fundamental rule

The workspace is never the source of truth. The source of truth is always the Brain (memory) and the repository (code).

---

## Integration with agents

Agents operate within these workspaces. They can read specifications from the Brain, modify the repository, and execute tasks in the workspace.

---

## Objective

Ensure projects remain reproducible, environments stay clean, and agents do not depend on hidden local state.
