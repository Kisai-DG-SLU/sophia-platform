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
| **An alert is not noise** | the mirror alert fires after **two** failed checks in a row (two simultaneous pushes clash then resolve), and **immediately** for a mirror on a forbidden repository; it goes to the administrator only, through the monitoring's general Telegram route (warnings and critical alerts, one message when it opens, another when it resolves) |
| **Isolated from agents** | its own namespace, with no role binding to any agent: an agent administering the applications namespace could have forged a session or used the read account; the last read binding in that namespace is deleted, and the chat interface probe reads its own namespace |

## Architecture

```
browser ─VPN─→ router ─→ [ oauth2-proxy │ application + collector ]   (dedicated namespace)
                                          │  cluster API (read, no Secrets)
                                          │  metrics (alerts, local-model slots)
                                          │  event bus (read, temporary queue)
                                          └─ forge (mirrors, read token)
```

- A single container serves the page and the API (Starlette and uvicorn), behind oauth2-proxy and SSO, administration group; oauth2-proxy's trust in `X-Forwarded-*` headers, is limited to the router.
- Namespace with quota, defaults and closed ingress, except from the router and, on oauth2-proxy's port, from the interface pod; egress limited to the sources it reads.
- **Cockpit** ([integration contract](../README.en.md#plugging-a-module-into-the-cockpit)): `frame-ancestors` limited to the interface on every response; `sophia.pret` signal (identifier `workflow`) after the first state response; shown in the centre of the cockpit for the administrator only: in service, verified on a computer, logging in again on a phone under acceptance testing. Switching to it without a click by Sophia is ready, being rolled out.
- **The person's token**: oauth2-proxy accepts the token relayed by the interface's server (`--skip-jwt-bearer-tokens`, the application's audience added by a mapper on the interface's client, never `--extra-jwt-issuers`); the administration group is still required; a refused token gets 403, without a redirect (`--bearer-token-login-fallback=false`): in service, 403 verified for an invalid token.
- **Summary for "What's new?"** (`GET /api/resume`, deterministic): commands awaiting approval, failed runs over 24 h, alerts, silent alert chain, mirrors. **The text of a command awaiting approval is never copied**: it is a model output, which does not leave the approval screen; the reason for a failure, written by the dispatcher, is included, truncated to 160 characters. Events are kept in memory only, and forgotten on restart. Route in service, not yet called by the interface.
- Built from the internal forge with a **read-only deploy key** on that repository alone, never with a forge administrator's token.
- Mirror-check metrics exposed to monitoring, with an alert rule in the namespace.

## Traps encountered

- **RabbitMQ 4.4** names server-created queues `amq_<32 hex digits>`, no longer `amq.gen-*`: the read account's permissions must follow, otherwise its listening queue is refused.
- **Forgejo** lists a repository's mirrors only to an administrator, and shows only the repositories the account can see: the check account is a site administrator, but its power is bounded by its token ("read repositories" only), with no known password or SSH key.
- Several mirrors to the same address (repeated creations) clash and push every commit several times: the "single mirror" rule came from that.
- **A push mirror overwrites the external host**: a branch changed directly on the host was replaced by the forge's at the next sync (everything was recovered). Rules adopted: work happens in the forge only; on the host, the default branch of public repositories is protected against force-push and deletion (private ones cannot be without a paid plan). A divergence check between the forge and the host is proposed, not built.
