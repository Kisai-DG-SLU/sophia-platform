# Orchestration — `sophia-core`

The heart of the platform: the model router (LiteLLM), the shared PostgreSQL database, the event bus (RabbitMQ) and the durable workflow engine (Temporal). Everything that talks to a model goes through LiteLLM; no application calls a provider directly.

## Components

| Directory | Role |
|---|---|
| `litellm/` | model router: stable aliases (`sophia-local`, `sophia-local-fond`, `sophia-embedder`, `sophia-stt`, `sophia-tts`, and remote aliases for development), restricted virtual keys, costs |
| [`postgres18/`](postgres18/) | **PostgreSQL 18**, shared instance for every database (LiteLLM, Keycloak, interface, Temporal, memory, human approvals, office suite, modules), one owner role per database, no network superuser; dedicated logical volume |
| `postgres/` | former PostgreSQL 15 instance, replaced by `postgres18/`: at 0 replicas for a 7-day hold, then removed; `pv.yaml` carries the `${NODE_NAME}` variable (volume node) |
| [`rabbitmq/`](rabbitmq/) | event bus, with the dispatcher as only publisher; management UI behind Keycloak |
| [`temporal/`](temporal/) | agents' durable workflows (delegation, recovery after failure) |
| [`repartiteur/`](repartiteur/) | delegation dispatcher: rules without a model, only Temporal client, only event publisher |
| `network/` | namespace egress (EgressFirewall), Postgres ingress, default ingress deny (`default-deny-ingress.yaml`) |
| `00-namespace-guardrails.yaml` | namespace `ResourceQuota` and `LimitRange` |

## Choices

| Item | Choice | Reason |
|---|---|---|
| Model aliases | applications ask for a **role** (`sophia-think`), never a model | changing model or provider only touches `litellm/config.yaml` |
| Local model | `sophia-local` → llama.cpp server in `sophia-inference`, zero cost, `supports_vision`, `max_input_tokens` 61,440 | same interface as remote models; the cap matches the server's per-conversation window ([`../inference/`](../inference/)) |
| Background alias | `sophia-local-fond` → same server, `max_parallel_requests: 1`, for agents and non-urgent application tasks | leaves the server's other slots to chat; **when streaming, the lock is released at the first response** and does not cover generation: it only applies to non-streaming calls, and agents' missions are bounded by the [dispatcher](repartiteur/) |
| Embedding | `sophia-embedder` → `sophia-memory` embedding service, cost 0 | ingestion and the memory service call embedding through the router, like everything else |
| Voice | `sophia-stt` and `sophia-tts` → voice service in `sophia-inference`, zero cost | voice goes through the same router, keys and logs |
| Restricted keys | each client (interface, agents) has a key limited to a model list; `add-model-to-keys.py` adds a new alias to it | a new alias is invisible until it is added to the keys that need it |
| One key per agent | `agent-<name>` (`litellm/create-agent-key.py`): background alias and embedding only, 120 requests per minute; Secret `litellm-cle-<agent>` in the agents namespace | the master key administers the router (keys, budgets) and opens every model: it does not leave the router's pod |
| Prices | copied from the provider's API by `sync-pricing.py`, never by hand | the displayed cost follows the real price |
| Per-use keys | one virtual key per caller (`litellm/create-virtual-key.py`): chat voice (its two aliases, its own rate), each development pod (the chat's models without voice), each application; never `*` | the rule is held by the router, whatever the request; see [Models by role](../../../docs/concepts/13-modeles-par-role.en.md) |
| Zero-downtime switch | `readiness` (`/health/readiness`, 3 s) and `liveness` (`/health/liveliness`) probes, `RollingUpdate` strategy (`maxSurge: 1`, `maxUnavailable: 0`) | without a probe, the pod was declared ready before listening: each restart (configuration, master key) cut the chat |
| LiteLLM logs | `INFO`, not `DEBUG` | in `DEBUG`, every full request (private conversations, base64 photos) lands in the logs and slows down large requests |
| Guardrails | namespace quota (16 Gi, 12 CPU, 15 pods) and explicit limits on **every** container, builds included | a container without limits gets 512 Mi by default: LiteLLM, Postgres or a build would be OOM-killed. **Apply the limits before the quota** |
| LiteLLM | 768 Mi requested, at most 2 Gi and 2 CPU | ≈ 550 Mi at rest, photos inflate requests; the CPU cap also bounds a pathological token count freeze |
| Postgres | **version 18**, image **pinned by digest**, `IfNotPresent`, `Recreate`, 2 Gi, `pg_isready` probes, dedicated logical volume growable online | a restart never pulls another version; never two Postgres on the same local volume; the image derives its buffers from the memory limit; details and migration in [`postgres18/`](postgres18/) |
| Router retention | detailed call log (`LiteLLM_SpendLogs`) kept 30 days (`maximum_spend_logs_retention_period`); daily aggregates remain | about 3 KB per call: without retention, the table would grow forever |
| Ingress | default ingress deny, then one rule per service; the model router (`litellm/network-policy.yaml`) only admits the namespaces of its recorded callers, the ingress router and the node network | without a rule, any pod in the cluster reaches the router and spends its keys; per namespace rather than per pod, to cover ephemeral pods |
| Egress | deny all except cluster Services and pods, the remote model provider, the registries and package indexes used by builds, and the identity provider on 443 | RabbitMQ reads Keycloak's signing keys through its public name, which resolves to the node, outside the internal networks |

## Variables

| Variable | Role | Example |
|---|---|---|
| `${AGENT_NAMESPACE}` | namespace of the pantheon agents | `agents` |
| `${CONFIG_REPO_URL}` | internal Git repository containing this directory (builds) | `http://git.example.internal/org/platform.git` |
| `${LITELLM_HOST}` | LiteLLM DNS name, resolved to the VPN address | `llm.example.org` |
| `${IDP_HOST}` | identity provider's public name | `auth.example.org` |

## Secrets (never committed)

| Secret | Keys |
|---|---|
| `llm-api-keys` | `DEEPINFRA_API_KEY`, `LITELLM_MASTER_KEY`, `DATABASE_URL`, `LITELLM_SALT_KEY` (encrypts what LiteLLM stores in its database: set it **to the current master key value** before rotating the master key) |
| `litellm-cle-<agent>` | `cle`: the agent's virtual key (agents namespace) |
| `postgres-sophia-18-creds`, `postgres-18-<role>` | `password`: see [`postgres18/`](postgres18/) |
| `forgejo-creds` | build read access to the internal repository |

## Procedure (administrator)

1. Explicit limits first: `litellm/deployment.yaml`, `litellm/build.yaml` — `--dry-run=server`, then `apply`.
2. Guardrails: `00-namespace-guardrails.yaml`, then `oc describe quota -n sophia-core`. Then the database, through its own procedure: [`postgres18/`](postgres18/).
3. Network: `network/policies.yaml`, `postgres18/03-network.yaml`, `litellm/network-policy.yaml`, and **only then** `network/default-deny-ingress.yaml`. Before and after: the router answers through its Route and from each calling namespace; rollback: delete `default-deny-ingress`.
4. Router: `litellm/config.yaml` (`oc diff` first: only the expected aliases change), restart LiteLLM, then `add-model-to-keys.py` dry-run and with `--apply` for each new alias:

```bash
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local < litellm/add-model-to-keys.py           # dry run
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local --apply < litellm/add-model-to-keys.py   # apply
```

The script reads the master key from the pod's environment, never prints it, and only touches keys that already list the reference model (`sophia-think` by default, or `--reference=<alias>`, for instance `--reference=sophia-local` to open the background alias to application keys).

5. **Agent keys**, in three steps.
   1. Keys and Secrets, with no effect on what runs: `create-agent-key.py <agent> --dry-run`, then the `--eval CLE_AGENT` form, and a Secret created from standard input (`printf '%s' "$CLE_AGENT" | oc create secret generic litellm-cle-<agent> --from-file=cle=/dev/stdin`), then `unset CLE_AGENT`. No key is printed.
   2. One `apply` per agent ([`../hermes-system/`](../hermes-system/)), one agent at a time. Check inside the agent: `/key/info` with its own key returns `agent-<name>` and its two models, then a "pong" mission.
   3. Once no agent reads it any more: remove the master key from the agents' Secret, set `LITELLM_SALT_KEY`, then rotate the master key. Each value goes through `--patch-file=/dev/stdin`, never in a command's arguments. List every consumer of the master key beforehand (scripts, administration workstations).
6. **Per-use keys** (voice, development pod, application): `create-virtual-key.py`, always dry-run first.

```bash
oc exec -i -n sophia-core deploy/litellm -- python3 - <alias> --modeles <m1>,<m2> --rpm <N> --dry-run < litellm/create-virtual-key.py
oc exec -i -n sophia-core deploy/litellm -- python3 - <alias> --comme <reference-alias> --sans <m1> --dry-run < litellm/create-virtual-key.py
oc exec -i -n sophia-core deploy/litellm -- python3 - --info <alias> < litellm/create-virtual-key.py
```

Creation replaces `--dry-run` with `--eval <VARIABLE>` inside an `eval "$(…)"`, then the key goes into the caller's Secret through standard input. `--info` gives the models, the limits and the start of the key's SHA-256 fingerprint: compared with the fingerprint of the Secret's value, it proves it is the right key, without displaying it.
