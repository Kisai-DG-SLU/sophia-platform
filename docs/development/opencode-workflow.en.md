# Assisted Development Architecture and Workflow

## 1. Philosophy and Overview

SophIA's assisted development module relies on code agents (such as OpenCode) running within ephemeral pods on a Kubernetes platform. The goal is to provide the AI with a structured, secure work environment interfaced with development tools and version control systems.

**Core principles:**

- Strict isolation between production code and AI memory
- Controlled traceability: the public Git history is attributable to the human, while the AI's raw work remains auditable internally
- Centralized configuration through a dedicated hub

---

## 2. Ephemeral Pod Architecture (The Triptych)

Each launched project generates a dedicated agent pod. The internal filesystem is organized into three distinct mount zones to constrain the AI's scope:

| Internal Path | Rights   | Source                         | Role |
|:---|:---|:---|:---|
| `$RULES_DIR`  | ReadOnly | Central rules repository       | Global rules, models, system prompts. Unalterable by the AI. |
| `$SPECS_DIR`  | ReadWrite | Project Brain repository       | Specifications, logbook, prompt history. |
| `$PROD_DIR`   | ReadWrite | Project repository             | Deliverable source code. No AI data persisted. |

---

## 3. AI Confinement and Security

Two mechanisms prevent the AI from writing its memory artifacts into the production directory:

1. **Routing through specialized tools.** The agent has no access to raw write commands. It uses dedicated functions that constrain writing to the respective paths (`$PROD_DIR` and `$SPECS_DIR`).

2. **Local Git filter.** At pod startup, an initialization script injects exclusion rules (memory files, logs) into the production repository's local Git configuration, blocking any accidental commit of AI files.

---

## 4. Access and Configuration

The pod inherits its environment at startup from a central configuration hub:

- **Software environment:** automatically activated at pod startup
- **Secure connection:** an SSH key is injected via a Kubernetes secret; an internal service assigns a stable IP to the pod; a client-side script updates the local SSH configuration for immediate connection from the IDE

---

## 5. Git Workflow

The development cycle revolves around an internal Git platform and its CI/CD system.

### Development and Testing (internal)

1. The agent works in `$PROD_DIR` on ephemeral branches (`feat/*`, `fix/*`).
2. Agent commits use a dedicated internal identity.
3. Pushing triggers a runner that executes tests.

### Validation and identity masking

1. If tests pass, an automated merge request is created to the validation branch.
2. The merge uses squash with author rewriting: the agent's identity is replaced by the human validator's identity.

### Production and external mirror

1. The validation branch is functionally tested by the user.
2. A final validation merges to the main branch.
3. Only validated branches are pushed to the public mirror. The AI's work history remains on the private infrastructure.
