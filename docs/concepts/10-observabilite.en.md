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
| Application workload monitoring | metrics of SophIA's services: message bus, workflow engine, inference server; 15 days of retention | in service |
| Alert rules | 27 rules: memory exhausted and crash loops (repeated in each namespace, since a rule only sees its own), dispatcher unavailable, bus dead letters and alarms, failed workflows, local model unavailable or saturated | in service: loaded, none in error |
| Node exporter | the graphics card (memory, utilisation, temperature, power) and the metric files dropped by the node's scripts | in service |
| VPN filter safeguard as a metric | its code on each run; alerts: filter removed, check impossible, safeguard silent | in service |

Measured cost: about 0.2 core and one to two gigabytes of memory, without touching the services. Recipe: [`deploy/okd/monitoring/`](../../deploy/okd/monitoring/).

Traceability, already in place: the history of each delegation workflow (30 days), dated events published on the bus by the dispatcher, the model router's request log.

### 2. Receive: the alarm becomes a request

The alert goes from Alertmanager to an **"alerts" requester** of the dispatcher, like any other request: proven identity, rules, quotas. The dispatcher starts an **"incident" workflow**, one per alert group. OKD platform alerts go through the same circuit, through a route added at the top of its Alertmanager, which then lets each alert follow its previous path. **Planned**: the route is ready and not enabled, the dispatcher's receiver written and disabled; at first it will only validate and log.

### 3. React: the "incident" workflow

1. **Deterministic collection**, by a recipe specific to each alert: state of the objects involved, events, logs, metric queries, through supervision read functions. A secret filter applies to everything read.
2. **Diagnosis** by the local model, in constrained output. If information is missing, the model asks for another read (a typed "read X" tool); the rules validate it, supervision performs it. **Two rounds at most**, bounded by code; a cap to revisit with use.
3. **Plan**, proposed by the model: the why, the actions, the manifests.
4. **Severity rules**, taken from the alert's label, never from the model: they set the recipient and the automatic actions allowed. **None at first.**
5. **Administrator notification**, then plan approval.
6. **Execution** by the maintenance agent, **every command approved**.

Every step, from the alarm to the last command, is in the workflow history, with the authenticated author of each approval.

**Supervision read functions** run in a separate pod, without node network access, without an assistant session or forge token, reachable by the dispatcher only, with its own read-only account on the cluster and metrics. Five typed functions: list, describe, logs, metric, alerts. Neither Secrets nor ConfigMaps; environment values masked; sizes bounded. **Planned**: designed and tested, not deployed.

---

## What this page does not do

- No agent reacts to an alarm on its own: supervision reads and alerts, it never acts.
- No automatic action until severity rules have explicitly allowed it, action by action.
- Approvals will go through the chat interface, with the person's token relayed and verified; the workflow engine's interface, restricted to the administration group, stays the fallback path, and the only one today.

---

## Position in the architecture

- metrics: components provided by OKD, and rules versioned with the manifests;
- reception and decision: the dispatcher (`sophia-core`), see [Agent Pantheon](08-pantheon-agentique.en.md);
- diagnosis and plan: the local model, through the same router as everything else (see [Inference and Hardware](11-inference-materiel.en.md)).
