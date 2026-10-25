# Visualisation module — documentation

## What the module does

- **Overview**: requesters at the top (the interface, the planner, the "incident" workflow), the dispatcher's gate in the middle (rules, workflow engine, event bus), executors at the bottom; supporting blocks (inference, memory, web airlock, MCP tools) are grouped and expand on click. A gauge shows the local model's slots: the chat's and the background tasks'.
- **Replay**: one execution as a sequence diagram, one lane per actor, step by step with its log.
- **Live**: the same execution as an animated map (namespaces as zones, current step travelled by a token) or as CI-like columns; two platforms, the **target** or **today**, where the execution stops at the first missing or failing component.
- **Still to deploy**: components that are not green, ordered by the decided work order, with their dependencies.
- **Mirror check**: every hour, each forge repository must have **a single** mirror to the external host, synchronised less than 24 h ago and without error. A repository without a mirror is on an exception list, with its reason; some exceptions are **forbidden** (for instance the transcripts of the coding-assistant sessions): a mirror appearing there is a fault.

Planned: a **compliance** section (GDPR, AI Act, ISO 27001 aimed at "certifiable", ANSSI hygiene guide), first a status board fed by read-only probes (network rules, quotas, Routes, pinned images, privileges, permissions, VPN safeguard, backups, retention, alerts, vulnerability watch), then an action plan and its follow-up; the live event stream (V2).

## Rules

| Rule | Why |
|---|---|
| **Nothing is assumed deployed without being measured** | a component's state comes from its probes: ready pods, waiting reason (`CrashLoopBackOff`, `ImagePullBackOff`), replicas, non-empty `EndpointSlice`s, firing alerts; a silent source or a refusal gives "not measured", **never** "ok"; a component without a probe stays "theoretical" |
| **Read only** | a service account that reads pods and metrics, **not Secrets**; a read-only bus account that rejects any message whose sender is not the dispatcher; a forge token scoped to "read repositories" only |
| **An open page costs nothing** | collection runs in the background every 30 seconds; the page only reads the latest result |
| **An alert is not noise** | the mirror alert fires after **two** failed checks in a row (two simultaneous pushes clash then resolve), and **immediately** for a mirror on a forbidden repository; it goes to the administrator only |
| **Isolated from agents** | its own namespace, with no role binding to any agent: an agent administering the applications namespace could have forged a session or used the read account |

## Architecture

```
browser ─VPN─→ router ─→ [ oauth2-proxy │ application + collector ]   (dedicated namespace)
                                          │  cluster API (read, no Secrets)
                                          │  metrics (alerts, local-model slots)
                                          │  event bus (read, temporary queue)
                                          └─ forge (mirrors, read token)
```

- A single container serves the page and the API (Starlette and uvicorn), behind oauth2-proxy and SSO, administration group.
- Namespace with quota, defaults and closed ingress; egress limited to the sources it reads.
- Built from the internal forge with a **read-only deploy key** on that repository alone, never with a forge administrator's token.
- Mirror-check metrics exposed to monitoring, with an alert rule in the namespace.

## Traps encountered

- **RabbitMQ 4.4** names server-created queues `amq_<32 hex digits>`, no longer `amq.gen-*`: the read account's permissions must follow, otherwise its listening queue is refused.
- **Forgejo** lists a repository's mirrors only to an administrator, and shows only the repositories the account can see: the check account is a site administrator, but its power is bounded by its token ("read repositories" only), with no known password or SSH key.
- Several mirrors to the same address (repeated creations) clash and push every commit several times: the "single mirror" rule came from that.
