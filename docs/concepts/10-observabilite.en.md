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
| Application workload monitoring | metrics of SophIA's services: message bus, workflow engine, inference server; 15 days of retention, without a persistent volume | in service |
| Alert rules | 29 rules: memory exhausted and crash loops (repeated in each namespace, since a rule only sees its own), dispatcher unavailable, bus dead letters and alarms, failed workflows, local model unavailable or saturated, volumes nearly full or full | in service: loaded, none in error |
| Node exporter | the graphics card (memory, utilisation, temperature, power), the node's volume usage and the metric files dropped by the node's scripts | in service |
| Measured state of components, mirror check | each component seen through its probes, never assumed; repository mirrors checked every hour ([Visualisation module](../modules/visualisation/README.en.md)) | in service |
| VPN filter safeguard as a metric | its code on each run; alerts: filter removed, check impossible, safeguard silent | in service |

Measured cost: about 0.2 core and one to two gigabytes of memory, without touching the services. Recipe: [`deploy/okd/monitoring/`](../../deploy/okd/monitoring/).

Traceability, already in place: the history of each delegation workflow (30 days), dated events published on the bus by the dispatcher, the model router's request log.

### 2. Receive: the administrator notified, the alarm becomes a request

**The administrator is notified by Telegram** (in service), for every actionable alert of the SophIA namespaces and of the OKD platform:
- a route placed first in the general configuration of each of the two Alertmanagers, which then lets each alert follow its previous path;
- a bot dedicated to alerts, which only writes to the administrator; its token lives only in the two monitoring namespaces;
- warnings and critical alerts only, permanent noise excluded by name; one message per problem (grouping by namespace and name, the critical alert inhibits the warning of the same name), a reminder every 24 h, then "Resolved" with the duration;
- only the name, severity, namespace, summary and start time are sent; the platform no longer sends e-mail.

**The alert also goes to an "alerts" requester** of the dispatcher, like any other request: proven identity, rules, quotas. **In service** for the core and the visualisation tool: the receiver validates and **logs** each alert, for the life of its pod. **Planned**: OKD platform alerts through the same circuit, then one **"incident" workflow** per alert group, and a durable incident register kept by the dispatcher. Both deliveries are independent: a stopped dispatcher does not prevent the message.

### 3. React: the "incident" workflow

1. **Deterministic collection**, by a recipe specific to each alert: state of the objects involved, events, logs, metric queries, through supervision read functions. A secret filter applies to everything read.
2. **Diagnosis** by the local model, in constrained output. If information is missing, the model asks for another read (a typed "read X" tool); the rules validate it, supervision performs it. **Two rounds at most**, bounded by code; a cap to revisit with use.
3. **Plan**, proposed by the model: the why, the actions, the manifests.
4. **Severity rules**, taken from the alert's label, never from the model: they set the recipient and the automatic actions allowed. **None at first.**
5. **Administrator notification** (the Telegram channel above), then plan approval.
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
