# Minimal observability

See the platform's state before its users do: a saturated model, a pod killed for lack of memory, dead-lettered messages, a failed workflow, a full graphics card, a VPN access filter removed. This directory relies on the monitoring stack provided by OKD, with no extra component besides a small exporter for the node. Concept: [Observability and Incident Response](../../../docs/concepts/10-observabilite.en.md).

```
RabbitMQ, Temporal, llama-server ──┐            ┌─ Thanos Ruler: 27 "Sophia…" rules
node exporter (GPU, .prom) ────────┼─ Prometheus ┤
                                   │  (user      └─ user workload Alertmanager
       OKD metrics (kube-state-metrics…)  workload) ─┐       │ (ready, not enabled)
                                                     │       ▼
                                Thanos (read) ◀──────┘  dispatcher /v1/alertes → "incident" workflow (planned)
```

## Status

| Element | Status |
|---|---|
| User workload monitoring (its own Prometheus, Thanos Ruler, Alertmanager) | in service |
| Scraping of RabbitMQ, Temporal and llama-server | in service |
| 27 alert rules: 21 in `20-regles.yaml`, 6 for the node in `40-node-metrics.yaml` | in service: loaded, none in error |
| Node exporter: GPU through NVML, `.prom` files dropped by the node's scripts | in service |
| VPN filter safeguard writing its code as a metric | in service |
| Alert routing to the dispatcher (`30-alertmanager-config.yaml`, `/v1/alertes` receiver) | ready, **not enabled** |
| OKD platform alerts (`alertmanager-main`) through the same path | planned, after enabling |
| "Incident" workflow | planned |

## Design

| Element | Choice | Why |
|---|---|---|
| Stack | OKD's user workload monitoring (`enableUserWorkload`), not a separate Prometheus stack | one stack, already maintained by the platform; rules are read with the rest in the console (**Observe**) |
| Resources | Prometheus 1 to 3 GiB, Thanos Ruler and Alertmanager bounded; 15-day retention; measured cost ≈ 0.2 CPU and 1 to 2 GiB | CPU is the node's scarce resource, not memory |
| Metrics Services | separate Services (`*-metrics`), labelled `sophia-metrics` | existing Services, and so their clients, are left untouched |
| Ingress | one NetworkPolicy per namespace, opening only the metrics ports to the user workload Prometheus only | `sophia-core` and `sophia-inference` deny all ingress by default |
| RabbitMQ | aggregates every 30 s; per-queue and per-exchange detail of the vhost every 60 s | the dead-letter queue is read in the detail, not in the aggregates |
| Common rules | OOM and restart loops, **repeated in each monitored namespace** | a user workload `PrometheusRule` only sees its own namespace's series |
| `sophia: oui` label | on every rule and every alert | it is what the AlertmanagerConfig routes, and the only thing |
| GPU | Python standard-library exporter reading NVML through `ctypes` in the driver library mounted from the node; privileged pod in `sophia-inference`, whose account already has llama-server's `privileged` SCC | no GPU operator or DCGM on a "driver only" path; no new right; NVML only reads, with no effect on llama-server |
| Node metrics | the node's scripts drop `.prom` files into a node directory, which the exporter reads read-only | the OKD node-exporter `textfile` collector is an `emptyDir`: the node cannot write to it |
| VPN filter safeguard | one function added: on each run it writes its code (0 readable, 1 filter removed, 2 check impossible) and a timestamp; atomic write (temporary file then `mv`), **errors ignored** | its decisions, actions and exit codes are unchanged; one alert warns if the filter is removed, another if the safeguard has been silent for more than 45 minutes |
| Exposition format | one `# TYPE` line above each family, its series grouped below | a single `TYPE` line at the top, for a single family, leaves the others untyped |
| Alerts to the dispatcher | AlertmanagerConfig (user workload) and a route added to `alertmanager-main` (OKD), with a bearer token and service TLS | an alarm becomes a request like any other, with a verified identity; the receiver only validates and logs until the "incident" workflow exists |
| Route in `alertmanager-main` | placed **first**, `continue: true`, warnings and critical only | every alert then follows exactly its former path; `Watchdog`, `InfoInhibitor` and `info` do not pass |

## Files

| File | Content |
|---|---|
| `00-cluster-monitoring-config.yaml` | enables user workload monitoring |
| `01-user-workload-config.yaml` | retention, resources, user workload Alertmanager with AlertmanagerConfig |
| `10-metrics-services.yaml` | metrics Services for RabbitMQ (15692) and Temporal (9090) |
| `11-servicemonitors.yaml` | scraping of RabbitMQ, Temporal and llama-server |
| `12-network-policies.yaml` | metrics ports ingress from the user workload Prometheus only |
| `20-regles.yaml` | 7 `sophia-alertes` `PrometheusRule`s: dispatcher unavailable, RabbitMQ dead letters and alarms, failed workflows, local model unavailable or saturated, failed scraping, and the common rules |
| `30-alertmanager-config.yaml` | routing to the dispatcher: **ready, not enabled** |
| `40-node-metrics.yaml` | node exporter (Deployment, Service, ServiceMonitor, NetworkPolicy) and its 6 rules: VPN filter removed, check impossible, safeguard silent; GPU not measurable, memory full, temperature |
| `node-metrics/exporteur.py` | exporter code, standard library only |
| `alertmanager-main-ajout.py` | adds the receiver and the leading route to the `alertmanager-main` configuration, removing nothing; replayable |

The VPN filter safeguard is described in [`../host/wireguard/`](../host/wireguard/).

## Variables

| Variable | Role | Example |
|---|---|---|
| `${AGENT_NAMESPACE}` | agents namespace, covered by the common rules | `agents` |
| `${NVIDIA_LIB_DIR}` | node directory holding `libnvidia-ml.so.1`, the same as for llama-server | `/var/lib/nvidia` |

Rule annotations contain `{{ $labels… }}` and `{{ $value }}`. **Substitution is restricted to the file's variable**: `envsubst '${AGENT_NAMESPACE}' < 20-regles.yaml` and `envsubst '${NVIDIA_LIB_DIR}' < 40-node-metrics.yaml`. An `envsubst` without a list would empty the annotations without any error.

| Secret | Namespace | Keys |
|---|---|---|
| `repartiteur-alertes` | `sophia-core` | `jeton` (`openssl rand -hex 32`), read by the dispatcher and by the AlertmanagerConfig; step 6 only |
| `repartiteur-alertes` | `openshift-monitoring` | `jeton` (same value, through a pipe), `service-ca.crt`; for OKD alerts only |

## Procedure (administrator)

From a clean, up-to-date clone of the internal repository. One step at a time, and each `oc apply` is preceded by an `oc diff` **read in full**. No existing service restarts: only new pods are created, monitoring and exporter. Checks are done in the OKD console (**Observe**), or read-only through Thanos.

1. **User workload monitoring**: `00-cluster-monitoring-config.yaml`. Expected, after one to three minutes, in `openshift-user-workload-monitoring`: `prometheus-operator`, `prometheus-user-workload-0` and `thanos-ruler-user-workload-0` `Running`. Rollback: restore the previous ConfigMap (or delete it if it did not exist).
2. **Settings and Alertmanager**: `01-user-workload-config.yaml`. Expected: in addition, `alertmanager-user-workload-0` `Running`; Prometheus restarts once to take its limits. Rollback: delete `user-workload-monitoring-config`.
3. **Scraping**: `10-metrics-services.yaml`, `12-network-policies.yaml`, then `11-servicemonitors.yaml`. Expected, in **Observe → Targets**, "User" filter: `rabbitmq-metrics` (two endpoints), `temporal-metrics` and `llama-server`, all `Up`. Rollback: `oc delete -f` the three files, which only add new objects.
4. **Rules**: `20-regles.yaml` (restricted substitution), then `oc get prometheusrule -A -l sophia=oui`. Expected: seven `sophia-alertes`; in **Observe → Alerting**, the `Sophia…` rules, none in error, none `Firing`. `SophiaLLMLocalIndisponible` may go `Pending` until llama-server's first scrape, without reaching `Firing`. Rollback: `oc delete -f`.
5. **Node.**
   - **5a. VPN filter safeguard as a metric.** It is the only administration path: same care as for the filter itself. **Before any install**, the test bench compares the old and new scripts with fake `crictl`, `podman`, `nft` and `logger`, over 5 OVN scenarios crossed with 3 states of the metric file. It runs **on Linux only**: the safeguard runs on the node with GNU `sed`, and the bench refuses to run with another `sed` (code 2) rather than compare a different behaviour. Expected: `AUCUN ÉCART (15 cas)`; otherwise, do not install. Install outside usage hours, keeping the administration session open: syntax check (`bash -n`), old script set aside on the node, install, then **one run identical to the timer's**, without reloading the filter or restarting any service. Expected: code 0, `sophia_wg_filter_code 0` and a timestamp in the `.prom` file, filter table present; at the next timer run, the timestamp moves on. **One-command rollback**: reinstall the old script set aside and run it once.
   - **5b. Exporter**: `sophia-node-metrics` ConfigMap created from `node-metrics/exporteur.py` (`oc create configmap … --from-file … --dry-run=client -o yaml`, read, then applied), then `40-node-metrics.yaml` (restricted substitution). Expected, on the pod's `/metrics`: `sophia_gpu_nvml_ok 1`, the card's memory, utilisation, temperature and power, then the `sophia_wg_filter_…` lines; in Thanos, the `sophia-node-metrics` target `Up`. If `sophia_gpu_nvml_ok 0`: the pod does not see the GPU devices, read its log. Rollback: `oc delete -f 40-node-metrics.yaml` and the ConfigMap; llama-server is never touched.
6. **Enabling the dispatcher path (planned, not before its prerequisites)**: a dispatcher image containing the `/v1/alertes` receiver, with its token taken from the `repartiteur-alertes` Secret; that Secret; a dispatcher ingress rule from `openshift-user-workload-monitoring` (pods `app.kubernetes.io/name=alertmanager`, port 8443); finally `30-alertmanager-config.yaml`. The receiver only validates and logs each alert.

### OKD alerts through the same path (planned, after step 6)

1. `repartiteur-alertes` Secret in `openshift-monitoring`: the token goes through a pipe from the `sophia-core` one, never displayed, then OKD's service CA (`service-ca.crt`). Check: keys `jeton` and `service-ca.crt`, nothing else.
2. Mount in OKD's Alertmanager: `alertmanagerMain.secrets: [repartiteur-alertes]` in `cluster-monitoring-config`, **only after** the Secret (without it, the `alertmanager-main` pods no longer start). Wait for the rollout to finish.
3. Dispatcher ingress from `openshift-monitoring` (pods `alertmanager`, 8443).
4. Back up the `alertmanager.yaml` key of the `alertmanager-main` Secret outside the repository (it may contain receiver credentials), `alertmanager-main-ajout.py < before > after`, `diff` read: the `repartiteur` receiver added, the route first, nothing else. Then `oc set data` and, in the Alertmanager log, `Completed loading of configuration file` without error. Rollback: write the backup back, remove the mount, delete that Secret.

## Lessons

- **Exposed metrics are not scraped metrics.** RabbitMQ, Temporal and llama-server all exposed their metrics; nobody read them, and no rule existed outside OKD.
- **OKD's node-exporter `textfile` is an `emptyDir`**: the node cannot drop files into it. Hence the separate exporter, reading a node directory.
- **A rule only sees its namespace** in user workload monitoring: a common rule is repeated in each namespace, or it covers nothing.
- **One `# TYPE` line per family.** A single line at the top of the exposition, for a single family, leaves the others untyped.
- **A bench runs where the script runs.** BSD `sed` does not understand `\+` as the node's GNU `sed` does: a bench replayed outside Linux would not have proven the node's behaviour.
- **`envsubst` without a list empties annotations** that contain `$labels` or `$value`, without any error.

## Next

- **Temporal volume**: about 21,000 series, 17,000 of them histogram buckets; Prometheus's working memory stays around 0.1 GiB out of 3 GiB at most. Cardinality follows operations, queues and workflow types, not the number of executions. **No filter for now.** If memory goes beyond about 1.5 GiB at the one-week reading, a `metricRelabelings` dropping only `.+_bucket` series is added to the `temporal` ServiceMonitor endpoint: about 3,800 series remain, and so do the rules and averages (`_sum`, `_count`); only latency percentiles are lost.
- Thresholds are starting values, to be recalibrated over a week of measurements, especially `SophiaLLMLocalSature`.
- The model router exposes no metrics in its version in service: only its OOMs are covered, by the common rule.
- Enabling the dispatcher path, OKD alerts, then the "incident" workflow: collection by the read functions, model diagnosis with constrained output, severity taken from the label, notification and approval, no automatic action.
