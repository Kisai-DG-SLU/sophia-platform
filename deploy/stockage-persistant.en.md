# Persistent storage: host preparation

The manifests in this repository declare `PersistentVolume` resources of type `local:`. A local volume creates nothing: it points at a path in the node filesystem, which must therefore already exist and be mounted when the manifest is applied.

If the mount point is missing, the pod stays `Pending` indefinitely, and no error points at the actual cause. This is the most common pitfall with this volume type, and the reason host preparation is a separate step.

## Rule: one dedicated logical volume per growing data set

Data that grows (relational database, vector database, object storage, message bus) gets its **dedicated XFS logical volume**, mounted under `/var/mnt/<name>`, rather than a directory in the node's `/var`:

- it does not fill `/var`, on which the system, the image registry and the node's logs depend;
- it **grows online**, without downtime or copy (see below);
- its usage is **measured and alerted** at 80% then 90% by the node exporter ([`okd/monitoring/`](okd/monitoring/)), which tracks `/var` and every mount under `/var/mnt`.

## What each component needs

Two distinct questions, and the second is the one that gets forgotten: does the component need persistent storage, and if so, how much. The size is not derived from the need, it is justified.

State verified on 2026-10-25, by reading the cluster.

| Component | Namespace | Persistent | Size | Backing | Basis for the size |
|---|---|---|---|---|---|
| PostgreSQL 18 (every database) | `${NS_CORE}` | yes | 20Gi | **dedicated logical volume** | about 190 MB of data at migration; high one-year assumption under 9 GB without retention, about 2 GB with it; see `okd/core/postgres18/` |
| Qdrant | `${NS_MEMORY}` | yes | 20Gi | **dedicated logical volume** | 6 to 8 KB per segment; optimisation needs up to twice the space; collection still empty |
| S3 object storage (SeaweedFS) | `sophia-storage` | yes | 200Gi | **dedicated logical volume** | office suite documents and their versions (30-day trash); see `okd/storage/` |
| RabbitMQ | `${NS_CORE}` | yes | 5Gi | node directory, bound by name (`claimRef` + `volumeName`) | delegation events and dead letters; see `okd/core/rabbitmq/` |
| Forgejo | `${NS_GIT}` | yes | 50Gi | **dedicated logical volume** | repositories and local SQLite database |
| Persistent chat media (Synapse) | `sophia-messagerie` | yes | 10Gi | **dedicated logical volume**, `Retain` PV | files of 50 MB at most; **no backup**, accepted choice (messages are in PostgreSQL); installed, in acceptance testing; see `okd/office/` |
| Neo4j | `${NS_MEMORY}` | yes | 10Gi | node directory, 0 replicas | graph to be built, no data; image pinned, on hold |
| Embedding service | `${NS_MEMORY}` | yes | 5Gi | node directory | cache and model, no corpus |
| Workspace | `${NS_APPS}` | yes | 20Gi | node directory, consumer down | preproduction, notebooks, webapps, APIs |
| LiteLLM | `${NS_CORE}` | no | `emptyDir` | no storage | configuration and logs, nothing to keep (its data is in PostgreSQL) |
| Coding assistant (Dionysos) | `${NS_AGENTS}` | no | `emptyDir` + private Git repository | restored at every pod creation | configuration and history pushed regularly to a dedicated repository (see `okd/hermes-system/`) |

The former PostgreSQL 15 instance lived in a directory of `/var`; so did the vector database, shared with other services. Both were moved to their dedicated volume, and the old directories are kept a week for a rollback before being deleted.

Namespaces are variables so the example stays reusable:

| Variable | Role |
|---|---|
| `${NS_CORE}` | orchestration, relational database, routing |
| `${NS_MEMORY}` | vector database, graph, embeddings |
| `${NS_GIT}` | code and specification repository |
| `${NS_APPS}` | interfaces and work environments |
| `${NS_AGENTS}` | agent system |

**These sizes are starting recommendations, not standards.** They suit a POC and are revised as needs evolve. Growth is estimated **per planned use** (per model call, per exchange, per document), with low, medium and high assumptions, not from the current volume, which is close to zero. What matters is that the size is written down and that its basis is itself verifiable.

## Check before starting

| Constraint | Consequence |
|---|---|
| empty `storageClassName` or `local-storage` without a provisioner | no automatic provisioning: the PV is created by hand |
| PV and PVC bound to each other (`claimRef` + `volumeName`) | no other PVC takes the volume |
| `persistentVolumeReclaimPolicy: Retain` | deleting the PV does not touch the data |

## Procedure

On the node that will carry the pod:

```bash
sudo vgs ${VG_NAME}
sudo lvcreate -L ${LV_SIZE} -n ${LV_NAME} ${VG_NAME}
sudo mkfs.xfs /dev/${VG_NAME}/${LV_NAME}
sudo mkdir -p ${MOUNT_POINT}
echo "/dev/${VG_NAME}/${LV_NAME} ${MOUNT_POINT} xfs defaults 0 0" | sudo tee -a /etc/fstab
sudo systemctl daemon-reload && sudo mount ${MOUNT_POINT}
sudo chcon -t container_file_t ${MOUNT_POINT}
findmnt ${MOUNT_POINT} && df -h ${MOUNT_POINT}
```

The first check gives the volume group's free space. The `chcon` gives the mount point the containers' SELinux context: without it, the pod starts but cannot write.

Variables to provide:

| Variable | Role |
|---|---|
| `${VG_NAME}` | existing volume group on the node |
| `${LV_NAME}` | logical volume name |
| `${LV_SIZE}` | size, for example `20G` |
| `${MOUNT_POINT}` | mount path, under `/var/mnt`, reused in the PV's `local.path` field |

## Verification

`findmnt` must show the volume as `xfs` on the mount point, and `df -h` the planned size. Then apply the `PersistentVolume`, then the `PersistentVolumeClaim`, and read the state:

```bash
oc get pvc
```

`Bound`: the storage is in place. `Pending` after mounting: the PV's `capacity` is lower than the PVC's request, or the `storageClassName` does not match.

## Growing a volume

An XFS logical volume **grows online**, mounted and in service:

```bash
sudo lvextend -r -L +10G ${VG_NAME}/${LV_NAME}
df -h ${MOUNT_POINT}
```

`-r` grows the filesystem in the same step. For a `local` volume, the declared size of the PV and PVC is only a label: the pod sees the real space. The `capacity` in the repository is still updated so it stays accurate; it has no effect on the pod.

A **directory of `/var`**, on the other hand, does not grow: moving it to a dedicated volume takes a stop and a copy (stop the pod, copy preserving permissions, compare sizes, switch the PV, restart, keep the old directory a few days). The time to do it is while the data is small.

## Sizing a model volume

A model volume is sized on the file's weight at the chosen quantisation, plus room for a second variant of the same order of magnitude. The calculation uses the actual measured download, never an estimate.

## What the inventory reveals

An inventory done once reveals accidents that the pod listing never shows: a volume prepared on the host without a manifest, a manifest without a consumer, a volume bound to a non-existent path, a deleted class still referenced, a name that no longer matches what the resource serves.

None of these states appear in `oc get pods`. They appear as soon as you list the volumes and the claims, and compare them.
