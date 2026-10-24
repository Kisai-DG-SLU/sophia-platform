# Observability and Incident Response

This page says **who sees what**, **who receives an alarm** and **who turns an alarm into an action plan**. It applies the [Deterministic Automation](09-automation-deterministe.en.md) pattern: deterministic collection, diagnosis by the model, decision by rules, execution under human approval.

---

## Problem

A platform serving a household or an organization must know it is unwell before its users do: a saturated model, a pod killed for lack of memory, a failing message queue, a stuck workflow. A metric without a recipient protects nothing, and a free agent that "fixes" things unchecked is one more risk.

---

## Three steps

### 1. See: minimal observability

| Element | What it brings | Status |
|---|---|---|
| Platform metrics (Prometheus, Alertmanager provided by OKD) | state of the node and the cluster components | in service |
| Read access to metrics for supervision | queries, peaks over several days | in service |
| Application workload monitoring | metrics of SophIA's services: message bus, workflow engine, inference server | planned |
| Alert rules | memory exhausted, GPU, workflow failures, dead-lettered messages, VPN access filter removed by its safeguard | planned |

Target cost: a few tenths of a core and one to two gigabytes of memory, without touching the services.

Traceability, already in place: the history of each delegation workflow (30 days), dated events published on the bus by the dispatcher, the model router's request log.

### 2. Receive: the alarm becomes a request

The alert goes from Alertmanager to an **"alerts" requester** of the dispatcher, like any other request: proven identity, rules, quotas. The dispatcher starts an **"incident" workflow**. **Planned.**

### 3. React: the "incident" workflow

1. **Deterministic collection**: state of the objects involved, events, logs, metric queries, through supervision read functions. A secret filter applies to everything read.
2. **Diagnosis** by the model, in constrained output. If information is missing, the model asks for another read (a typed "read X" tool); the rules validate it, supervision performs it. The loop is bounded by code.
3. **Plan**, proposed by the model: the why, the actions, the manifests.
4. **Severity rules**: they set the recipient and the automatic actions allowed. **None at first.**
5. **Administrator notification**, then plan approval.
6. **Execution** by the maintenance agent, **every command approved**.

Every step, from the alarm to the last command, is in the workflow history, with the authenticated author of each approval.

---

## What this page does not do

- No agent reacts to an alarm on its own: supervision reads and alerts, it never acts.
- No automatic action until severity rules have explicitly allowed it, action by action.
- Approvals currently go through the workflow engine's interface, restricted to the administration group; other channels (chat interface, messaging) will come on the same verified-identity principle.

---

## Position in the architecture

- metrics: components provided by OKD, and rules versioned with the manifests;
- reception and decision: the dispatcher (`sophia-core`), see [Agent Pantheon](08-pantheon-agentique.en.md);
- diagnosis and plan: the local model, through the same router as everything else (see [Inference and Hardware](11-inference-materiel.en.md)).
