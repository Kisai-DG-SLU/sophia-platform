# CPU priorities and quotas (cluster)

A single node carries chat, the language model, voice, agents, office suite, images and development. RAM has headroom, **CPU does not**: actual use is low, but declared limits exceed the node's capacity. This directory sets **who goes first** when room runs out, and **how much each namespace may declare**. Concept: [Inference and hardware](../../../docs/concepts/11-inference-materiel.en.md).

## Priority classes

| Class | Value | Preemption | Workloads |
|---|---|---|---|
| `sophia-socle` | 2,000,000 | no | cluster read pod (coding assistant), Git forge |
| `sophia-inference-high` | 1,000,000 | **yes** | language model server ([`../inference/00-namespace-guardrails.yaml`](../inference/00-namespace-guardrails.yaml)) |
| `sophia-chat` | 100,000 | no | interface, household applications, model router, relational database, identity |
| `sophia-voix` | 90,000 | no | speech recognition and synthesis |
| `sophia-agents` | 80,000 | no | dispatcher, workflows, bus, agents, embedding, web airlock |
| `sophia-workspace-low` | 50,000 | no | office suite |
| `sophia-images` | 30,000 | no | image generation, capped at 8 CPU |
| `sophia-dev` | 10,000 | no | development pods, dev gateway, child clusters |

## Design

| Element | Choice | Why |
|---|---|---|
| Preemption | **no SophIA class preempts** (`preemptionPolicy: Never`); only the existing inference class keeps that right | preemption kills a pod mid-work; with about twenty CPUs of request headroom, the queue is enough |
| Base above inference | `sophia-socle` (2,000,000) rather than switching `sophia-inference-high` to `Never` | the scheduler never evicts a pod of equal or higher priority; `preemptionPolicy` cannot be changed on an existing class: it would have meant deleting and recreating it, then recreating the inference server |
| Base | the cluster read pod and the Git forge | the first lets you understand the cluster's state during an outage; every deployment starts from the second: without it, nothing starts |
| Base memory request | above the measured peak (read pod 12 GiB for 10.8 GiB, forge 1.5 GiB for 965 MiB) | under memory pressure, the kubelet first evicts pods exceeding their request, **whatever their class**; a pod without a request (`BestEffort`) goes first |
| No default class | `globalDefault: false` | a pod without a class is worth 0 and comes after every SophIA workload: each workload names its own |
| Images | 8 CPU at most, 8 threads | image generation used up to 16 CPU, competing directly with voice |
| Quotas | on **limits**, per namespace, with a `LimitRange` of defaults | declared limits exceeded 160 % of the node; the quota bounds what a namespace may promise, the `LimitRange` gives limits to pods that declare none |

## Quotas in the reference install

| Namespace | CPU limits | memory limits | pods | Note |
|---|---|---|---|---|
| `sophia-memory` | 8 | 16 Gi | 10 | graph database 2 CPU / 8 Gi at most |
| `sophia-dmz` | 8 | 12 Gi | 12 | remote browser for groceries |
| `sophia-apps` | 24 | 40 Gi | 30 | builds run here, including a CUDA compilation at 16 CPU / 24 Gi |
| `${AGENT_NAMESPACE}` | 28 | 48 Gi | 15 | read pod 16 CPU / 32 Gi at most; explicit resources on **every** container, init included |
| office suite | 10 | 10 Gi | 15 | plus requests 2 CPU / 4 Gi |
| chat interface (dedicated namespace) | 4 | 3 Gi | 6 | |
| workflow dashboard (dedicated namespace) | 3 | 3 Gi | 5 | |
| object storage | 3 | 3 Gi | 4 | |
| MCP tool builds | one build at a time | | | no agent account in the namespace |

Template: `01-namespace-quota.yaml` (one copy per namespace).

| Variable | Role | Example |
|---|---|---|
| `${NAMESPACE}` | target namespace | `sophia-memory` |
| `${QUOTA_NAME}` | quota name | `memory-quota` |
| `${QUOTA_LIMITS_CPU}`, `${QUOTA_LIMITS_MEMORY}`, `${QUOTA_PODS}` | ceilings | `8`, `16Gi`, `10` |
| `${DEFAULT_CPU_LIMIT}`, `${DEFAULT_MEMORY_LIMIT}` | default container limits | `500m`, `512Mi` |
| `${DEFAULT_CPU_REQUEST}`, `${DEFAULT_MEMORY_REQUEST}` | default requests | `20m`, `64Mi` |
| `${AGENT_NAMESPACE}` | agents namespace | `agents` |

## Procedure (administrator)

One step at a time, from a clean, up-to-date clone of the internal repository, first compared with the cluster: `oc diff` must only show the intended changes. **Each `oc apply` is preceded by an `oc diff` read in full.** A class changes nothing for running pods: each `apply` of a workload restarts its pod once, on the same image.

1. **Classes** (no effect on what runs): `priority-classes.yaml`. Check: `oc get priorityclass -o custom-columns=NAME:.metadata.name,VALUE:.value,PREEMPTION:.preemptionPolicy`, the seven classes in `Never`, the inference class in `PreemptLowerPriority`. Rollback: delete the seven classes, unused until step 3.
2. **Quotas** (no effect on what runs): one copy of `01-namespace-quota.yaml` per namespace, **except** those where a container has no explicit resources yet (see step 4). Check: `oc describe resourcequota -n <namespace>`, current use fits under the ceilings.
3. **Workloads, by order of impact**:
   - first those that affect no user: dispatcher, workflows, bus, embedding, web airlock, dev gateway;
   - then, **when nobody is using chat**: model router, relational database (about 30 s without a database for every application), identity (SSO down one to two minutes), voice, images. Before restarting a pod with `imagePullPolicy: Always`, check that the internal registry does serve its image;
   - a workload whose manifest is not versioned (for instance the forge) gets a patch: backup of the object outside the repository, `--dry-run=server` trial, then apply;
   - a manifest that carries another change depending on a prerequisite (for instance a new model alias) waits for that prerequisite, so the pod restarts only once.

   For each: `oc diff -f <file>`, `oc apply -f <file>`, `oc rollout status`, then `oc get pod -o jsonpath='{.items[0].spec.priorityClassName} {.items[0].status.containerStatuses[0].ready}'`, expected `<class> true`. Rollback: `oc rollout undo`.
4. **Base, in its slot**: the cluster read pod gets its class and explicit resources; recreating it cuts the sessions it carries. **Only then**, its namespace's quota.

## Status

| Item | Status |
|---|---|
| Seven classes, no preemption except inference | in service |
| Classes set on workloads, including the base (cluster reading pod and forge) | in service; the reading pod got it in its slot, with explicit resources (`Burstable` QoS class) |
| Quotas and `LimitRange` of the namespaces in the table, including the agents' | in service; the agents' one was set after the reading pod's slot, as step 4 requires |

## Checks

- No preemption possible above the base: `oc get pod -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,PRIO:.spec.priority | sort -k3 -n -r | head`.
- Quality of service: `oc get pod -o jsonpath='{.status.qosClass}'` must never return `BestEffort` for a base workload.
- Applications reconnect their connection pool by themselves after the database restarts: one or two probe errors at most, no pod restart.

## Lessons

- **`BestEffort` comes before the class**: a pod without a request is the first evicted under memory pressure, even in a high class. A priority class only protects pods that declare their resources.
- **Quota after resources**: a quota on limits imposes the `LimitRange` default on recreated pods; set before every container has its resources, it chokes the first recreated pod (1 CPU, 1 GiB).
- **Preemption only looks at requests**, not actual use; a pod without a class is worth 0 and goes before everything else.
- **OpenShift image triggers** replace tags with digests in cluster objects: realign the repository before the first `oc diff`, otherwise it shows unrelated differences.
