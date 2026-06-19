# Project Model

The **Project Model** defines how SophIA structures and identifies units of work.

In SophIA, everything is modeled as a project. This includes software development projects, research studies, professional activities, personal goals, and strategic initiatives.

The project model provides a common structure for these activities.

---

## Principle

A SophIA project is defined by three distinct elements:

- **Brain**
- **Repository**
- **Workspace**

These three elements have different roles and must never be confused.

---

## Brain

The **Brain** contains the memory and intellectual structure of the project. It is stored in a dedicated repository.

The Brain typically includes:

- specifications (`specs`)
- project configuration
- persistent memory (`_memory`)
- architectural decisions

The Brain is the documentary source of truth. It never contains executable code.

---

## Repository

The **Repository** contains the work artifacts: source code, notebooks, datasets, generated documents.

The repository usually corresponds to a Git repository. It represents the project deliverable.

---

## Workspace

The **Workspace** is the temporary execution environment. It is ephemeral, reproducible, and isolated.

It can be a local directory, a sandbox environment, or a Kubernetes pod. The workspace can be destroyed and recreated without information loss.

---

## Minimal project structure

A SophIA project contains at minimum:

```
project.yaml
_config/
_memory/
specs/
```

The `project.yaml` file serves as the project manifest. It allows the orchestrator to identify the project identity, its Brain, its repository, and its default agent.

---

## Project identity

Each project has a unique identifier. Example:

```
organization/project_10/component_name
```

This identifier allows finding associated resources, resolving the Brain, and locating the repository.

---

## Agents and projects

Agents always operate within the context of a project. They can read specifications, modify the repository, and execute tasks in the workspace.

The project is the fundamental unit of work in the system.

---

## Objective

The Project Model enables structuring activities, separating memory from execution, making projects reproducible, and facilitating agent work.

In SophIA, the project becomes the central element connecting knowledge, execution, tools, and objectives.
