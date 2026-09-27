# Persistent storage: host preparation

The manifests in this repository declare `PersistentVolume` resources of type `local:`. A local volume creates nothing: it points at a path in the node filesystem, which must therefore already exist and be mounted when the manifest is applied.

If the mount point is missing, the pod stays `Pending` indefinitely, and no error points at the actual cause. This is the most common pitfall with this volume type, and the reason host preparation is a separate step.

## What each component needs

Two distinct questions, and the second is the one that gets forgotten. Does the component need persistent storage, and if so, how much. The size is not derived from the need, it is justified.

State verified on 2026-09-27, by reading the cluster.

| Component | Namespace | Persistent | Size | State | Basis for the size |
|---|---|---|---|---|---|
| PostgreSQL | `${NS_CORE}` | yes | 10Gi | bound | 4 users, logs, permissions. Not expandable, starting minimum |
| Forgejo | `${NS_GIT}` | yes | 50Gi | bound | repositories and local SQLite database, 6 MB today |
| Qdrant | `${NS_MEMORY}` | yes | 20Gi | bound | points x dimensions x 4 bytes, to be computed once ingestion produces |
| Neo4j | `${NS_MEMORY}` | yes | 10Gi | bound, not mounted | graph to be built, no data |
| Embedding service | `${NS_MEMORY}` | yes | 5Gi | bound | cache and model, no corpus |
| Workspace | `${NS_APPS}` | yes | 20Gi | bound, consumer down | preproduction, notebooks, webapps, APIs |
| LiteLLM | `${NS_CORE}` | no | `emptyDir` | no storage | configuration and logs, nothing to keep |
| RabbitMQ | `${NS_CORE}` | planned | 5Gi requested | pending | inter-agent queues, to be created |
| Control agent | `${NS_AGENTS}` | planned | 2Gi requested | pending | control rules, to be created |

Namespaces are variables so the example stays reusable:

| Variable | Role |
|---|---|
| `${NS_CORE}` | orchestration, relational database, routing |
| `${NS_MEMORY}` | vector database, graph, embeddings |
| `${NS_GIT}` | code and specification repository |
| `${NS_APPS}` | user interfaces and work environments |
| `${NS_AGENTS}` | agent system |

**These sizes are starting recommendations, not norms.** They suit a proof of concept and are revised as needs change. None of the bases in the right-hand column is verified for a production system, and neither logs nor permissions are in place yet: a ten-table database in a near-empty state says nothing about its size in two years. What matters here is that the size is written down, and that its basis is itself verifiable.

## Check before starting

| Constraint | Consequence |
|---|---|
| `storageClassName: ""` | no StorageClass is selected, the PV is resolved by its name |
| `no-provisioner` StorageClass | no automatic provisioning, the PV is created by hand |
| `ALLOWVOLUMEEXPANSION: false` | a volume cannot be grown, the size is chosen once and for all |

## Procedure

Four steps, on the node that will run the pod.

```bash
# 1. Logical volume in the existing volume group
sudo lvcreate -L ${LV_SIZE} -n ${LV_NAME} ${VG_NAME}

# 2. Format
sudo mkfs.xfs /dev/${VG_NAME}/${LV_NAME}

# 3. Mount point
sudo mkdir -p ${MOUNT_POINT}

# 4. Persist the mount, then mount
echo "/dev/${VG_NAME}/${LV_NAME} ${MOUNT_POINT} xfs defaults 0 0" | sudo tee -a /etc/fstab
sudo mount ${MOUNT_POINT}
```

Variables to supply:

| Variable | Role |
|---|---|
| `${VG_NAME}` | volume group already present on the node |
| `${LV_NAME}` | logical volume name |
| `${LV_SIZE}` | size, for example `200G` |
| `${MOUNT_POINT}` | mount path, reused in the `local.path` field of the PV |

## Verification

```bash
df -h ${MOUNT_POINT}
```

The expected line shows the volume size on the mount point. This is the only useful check: if the size is right, the PV can be applied.

Then apply the `PersistentVolume`, then the `PersistentVolumeClaim`, and read the state:

```bash
oc get pvc
```

`Bound`: storage is in place. `Pending` after the mount: the PV `capacity` is lower than the PVC request, or the `storageClassName` does not match.

## Growing a volume

When expansion is forbidden, growth is not a resize, it is a replacement. The procedure assumes the PV is `Retain`, which is the case in this example.

1. Prepare a second filesystem on the host, larger, at a new mount point
2. Create a second PV pointing at it, with a capacity greater than the PVC request
3. Stop the pod: the PV becomes `Released` and its data stays on the host, thanks to `Retain`
4. Delete the PVC, then recreate it with the larger size: it binds to the new PV
5. Copy the data from the old path to the new one, host side
6. Restart the pod, then release the old volume once the copy is verified

Steps 4 and 5 do not resolve on their own. The copy is done by hand, on the node, and nothing in the cluster checks that it finished. That is the reason for the margin in the table above.

## Sizing a model volume

A model volume is sized on the weight of the file at the chosen quantization, plus the margin for a second variant of the same order of magnitude.

The margin is not a convenience. Since expansion is forbidden, a volume that is too small cannot be fixed by adding space, it has to be replaced, with a stop and a full copy. The computation is therefore done on the actual measured download, never on an estimate.

## What the inventory reveals

An inventory run once reveals accidents that the pod listing never shows: a volume prepared on the host with no manifest, a manifest with no consumer, a volume bound to a path that does not exist, a deleted class still referenced, a name that no longer matches what the resource serves.

None of these states appear in `oc get pods`. They show up as soon as the list of volumes and the list of claims are requested and compared.
