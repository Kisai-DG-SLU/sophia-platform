# Delegation dispatcher (`sophia-core`)

The dispatcher is the only path through which a request reaches an agent. It **decides without a model**, through versioned rules, and runs each accepted request in a durable workflow. Concepts: [Agent Pantheon](../../../../docs/concepts/08-pantheon-agentique.en.md), [Deterministic Automation](../../../../docs/concepts/09-automation-deterministe.en.md).

```
requester ──POST /v1/demandes──▶ DISPATCHER (sophia-core, no model)
 (a request, never an order)      │ proven identity (TokenReview), rules, quotas
                                  │ only Temporal client and only worker
                                  ▼
                       Delegation workflow (id = task_id)
                         destination filters, human approvals
                                  │ HTTP, one key per executor
                                  ▼
                       EXECUTOR: the target agent's api_server
                                  │
                       events ──▶ RabbitMQ sophia.events (dispatcher is the only publisher)
```

## Design

| Principle | Implementation | Why |
|---|---|---|
| **A request is not an order** | a request carries a type (`lecture` for read, `mission`, `consultation`), a target, a goal in text and, for a follow-up, the parent `task_id`; **no right, no command, no approval** | what an executor can do comes from its own rights, never from the instruction it receives |
| **Identity proven, not declared** | the requester presents its service account's **projected** token (audience `repartiteur`, short-lived); the dispatcher checks it with `TokenReview` and derives the agent from it | one service account per agent; an account shared by several pods proves nothing |
| **Rules without a model** | a versioned table (`02-regles.yaml`), read at startup: who asks what of whom, approval, maximum duration, hourly quota, return filters; **everything else is refused and logged** | a model can neither read nor change the rules |
| **Only Temporal client** | one workflow per request (id = `task_id`); agents have no access to Temporal | Temporal's authorizer only knows (namespace, role) pairs: removing the right is the only protection |
| **Only event publisher** | each step publishes on `sophia.events` (keys `<requester>.delegate.<event>`), `user_id` always set; agents no longer write to the bus | a consumer refuses any event from another publisher |
| **Single-attempt execution** | start with `Idempotency-Key = task_id`, follow the stream with resumption, stop at the maximum duration; the work itself is never retried | an agent's work is not idempotent: a retry is a new request |
| **Destination filters** | deterministic workflow steps: secret detection on supervision answers; leak filter on the way out and tribunal on the way back for an external consultation; a missing or uncertain filter stops the workflow | nothing passes by default; until these filters exist, the rules refuse consultation |
| **D3a and D3b approvals** | D3a: approval of the goal before departure (signal bound to its hash); D3b: approval of **each command**; the dispatcher only passes `once` or `deny` to the executor, never a permanent approval | an approval is valid once |
| **Verified principal** | with `frontend.enablePrincipalPropagation`, each event of the Temporal history carries the `sub` of the caller's token; only the `sub` values in the `approbateurs` list are accepted; approvals go through the Temporal UI, restricted to the `admin` group | a signal's `identity` field is declared by the client: it proves nothing |

## HTTP contract

| Endpoint | Role |
|---|---|
| `POST /v1/demandes` | `{type, cible, objectif[, parent]}` with `Authorization: Bearer <projected token>`; `202 {task_id, etat}` if a rule accepts it, `403 {refus}` otherwise, `401` without a valid token |
| `GET /v1/demandes/{task_id}` | status and filtered result, for the requester only |
| `GET /sante` | health (probe) |

The service code is not provided: this directory describes its contract and deployment. It is written in Python (Temporal SDK), without a model; its image starts from a base pinned by index digest, with dependencies locked by hash (`pip install --require-hashes`), under an arbitrary UID, read-only root filesystem.

## Files

| File | Content |
|---|---|
| `00-build.yaml` | dispatcher ImageStream; **base image imported through an ImageStream** (index digest, `referencePolicy: Local`); BuildConfig with a **binary source** |
| `01-rbac.yaml` | service account and `system:auth-delegator` (TokenReview, nothing else) |
| `02-regles.yaml` | **inert example rules**: no requester, no executor, every request refused |
| `03-deployment.yaml` | Deployment (one replica, `Recreate`), **image pinned by digest** with `IfNotPresent`, TLS Service through the OKD service certificate |
| `04-network-policy.yaml` | ingress from the agents namespace only; RabbitMQ accepts the dispatcher |
| [`../../hermes-system/09-executants-network.yaml`](../../hermes-system/09-executants-network.yaml) | an executor's ingress open to the dispatcher only |
| [`../../hermes-system/10-recette-repartiteur.yaml`](../../hermes-system/10-recette-repartiteur.yaml) | acceptance Job through the real path |

Changes to neighbouring components, already in their templates: `repartiteur` account and `topic_permissions` in [RabbitMQ](../rabbitmq/), agents without write access; `enablePrincipalPropagation` and ingress reserved for the dispatcher in [Temporal](../temporal/); `temporal-repartiteur` client and Keycloak accepting the dispatcher ([identity](../../identity/)); EgressFirewall rule to the Kubernetes API (6443) for TokenReview ([`../network/policies.yaml`](../network/policies.yaml)).

| Variable | Role | Example |
|---|---|---|
| `${REPARTITEUR_SRC_DIR}` | directory of the service code in the internal repository | `services/repartiteur` |
| `${REPARTITEUR_DIGEST}` | digest of the built image | `sha256:…` |
| `${AGENT_NAMESPACE}` | agents namespace (requesters and executors) | `agents` |

| Secret | Namespace | Keys |
|---|---|---|
| `temporal-repartiteur` | `sophia-core` | `client-id`, `client-secret` (set by `identity/temporal-keycloak.py`) |
| `rabbitmq-users` | `sophia-core` | key `repartiteur` (hexadecimal password) |
| `repartiteur-cle-<executor>` | `sophia-core` **and** agents namespace | `cle`: the same value on both sides, generated in place, never displayed |
| `repartiteur-tls` | `sophia-core` | created by OKD (Service annotation) |

## Procedure (administrator)

From a clean, up-to-date clone of the internal repository; template paths are relative to `deploy/okd/`, except `git archive`, run at the repository root. One step at a time; each `oc apply` is preceded by an `oc diff`.

1. **RabbitMQ password** for the dispatcher, before step 5 (without it, RabbitMQ's initContainer refuses to start):
   ```bash
   oc -n sophia-core patch secret rabbitmq-users --type=merge -p "{\"stringData\":{\"repartiteur\":\"$(openssl rand -hex 32)\"}}"
   ```
2. **Keycloak**: `python3 identity/temporal-keycloak.py --dry-run`, then without `--dry-run`. Expected: `temporal-repartiteur` created (`sophia:write`), its Secret, and the former `temporal-<agent>` clients disabled. Then delete the `temporal-agent-<agent>` Secrets from the agents namespace.
3. **Network**: `identity/02-network.yaml`, `core/network/policies.yaml`, `core/temporal/03-network-policy.yaml`. Expected in `oc diff`: Keycloak accepts `repartiteur`; the EgressFirewall gains the 6443 rule to the control plane, before the final deny; Temporal no longer accepts the agents namespace or the node network, but the `repartiteur` pod.
4. **Temporal**: `core/temporal/02-server.yaml`. Only the dynamic configuration ConfigMap changes; the server reloads it without restarting.
5. **RabbitMQ**: `core/rabbitmq/00-config.yaml`, then `rollout restart deploy/rabbitmq`. Check: `rabbitmqctl list_permissions -p /sophia` (the dispatcher writes on `^sophia\.events$` only, agents write nowhere) and `list_topic_permissions -p /sophia` (one line: `repartiteur`, `sophia.events`, `^[a-z]+\.delegate\.[a-z_]+$`).
6. **Image**: apply `00-build.yaml`, `01-rbac.yaml`, `02-regles.yaml`, `04-network-policy.yaml`, then build from the **committed** code:
   ```bash
   git archive --format=tar.gz -o /tmp/repartiteur.tar.gz HEAD ${REPARTITEUR_SRC_DIR}
   oc -n sophia-core start-build repartiteur --from-archive=/tmp/repartiteur.tar.gz --follow --wait
   rm /tmp/repartiteur.tar.gz
   ```
   Expected: `Uploading archive file`, build `Complete`, dependencies installed with hash checking. Note the digest (`oc -n sophia-core get istag repartiteur:latest -o jsonpath='{.image.metadata.name}'`) and put it in `03-deployment.yaml` (`${REPARTITEUR_DIGEST}`).
7. **Deployment**: `03-deployment.yaml`, then `rollout status`. The log contains `temporal` `connecté`, `rabbitmq` `connecté`, then `demarrage` with empty `executants` and `agents` 0; afterwards, no `PermissionDenied` or `ACCESS_REFUSED` error.
8. **Check through the real path**, from a throwaway pod in the agents namespace: `GET /sante`, `POST /v1/demandes` without a token, then with a fake token. Expected: **`200 401 401`**. The first code proves the Service, TLS and network rule; the other two, the refusal without identity. The second refusal goes through the Kubernetes API, which also checks the 6443 rule (a 500 on this third call means the API is unreachable).
9. **Pinned image**: an `oc diff` of `03-deployment.yaml` only shows `image` and `imagePullPolicy`; after `apply`, the pod's `imageID` ends with the recorded digest, and check 8 gives `200 401 401` again. A new build no longer changes anything in service.

### First executor and "pong" acceptance test

1. **Key**: one value generated in place, stored in `repartiteur-cle-<executor>` in both namespaces, never displayed (`K=$(openssl rand -hex 32)`, two `oc create secret`, `unset K`).
2. **Executor ingress**: `hermes-system/09-executants-network.yaml`. Negative check: another pod in the agents namespace cannot reach the `api_server` (`ConnectTimeout` expected).
3. **Executor**: the agent starts its `api_server` with the key (recent Hermes Agent, pinned by digest; a configuration from an earlier version is migrated before startup, and the values the migration changes are checked).
4. **Rules**: declare the `recette` requester, the executor and the `mission` rule recette → executor (300 s, 10 per hour), add the key variable to the Deployment, restart. Log: `demarrage` with the executor, the rules and one agent.
5. **Acceptance test**: `hermes-system/10-recette-repartiteur.yaml`, then `oc wait --for=condition=complete`. Expected in the Job log: `sans règle : 403`, `mission : 202` with a `task_id`, `résultat :` in state `terminée` containing **`pong`**, then `RECETTE RÉUSSIE`. In the Temporal UI, the workflow with the same `task_id` is `Completed`, with its start, follow and publish activities. The Job can be replayed after deleting it.

## Rollback

The dispatcher alone: delete its Deployment, Service and two NetworkPolicies. The rest, object by object: go back to the previous template version, then `oc apply` (and restart RabbitMQ). The former Keycloak clients can be re-enabled in the console; their Secrets only need recreating if an agent had to talk to Temporal again, which the design excludes.

## Next

Planned: the interface as a requester; reads to supervision (with the secret filter); deployment and maintenance missions with D3a and D3b and the approver list; mutual TLS between the dispatcher and executors (the `api_server` currently speaks HTTP inside the cluster, the key travels over it, ingress being limited to the dispatcher); external consultation, after the leak filter and the tribunal.
