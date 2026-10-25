# Shared S3 object storage (`sophia-storage`)

S3-compatible object storage shared by the platform: first the office suite's file application, then memory (RAG) and modules, each with its own identity and bucket. The software is **SeaweedFS** in `weed mini` mode: master, volume, filer and S3 gateway in a single process, intended for one node in production. MinIO, considered first, is no longer maintained (archived repository, no more published images).

```
browser (VPN) ──presigned PUT──▶ Route (reencrypt) ──┐
file application ────────────────────────────────────┤──▶ Service s3 :9000 (TLS) ──▶ pod s3 :8443
initialization Job ──────────────────────────────────┘        egress: DNS only
```

| Use | Address |
|---|---|
| Internal (services) | `https://s3.sophia-storage.svc:9000`, TLS through the OKD service certificate (authority: ConfigMap annotated `inject-cabundle`, key `service-ca.crt`) |
| External (browser, VPN only) | `https://${S3_HOST}`, reencrypt Route |

## Design

| Element | Choice | Why |
|---|---|---|
| Software | SeaweedFS `weed mini`, **image pinned by digest**, `IfNotPresent` | maintained, one process on one node; a restart never pulls another version |
| Volume | dedicated XFS logical volume, local PV and PVC **naming each other** (`claimRef` + `volumeName`), `Retain` | data survives deleting the objects; no other PVC takes this volume; XFS grows online |
| Deployment | `Recreate`, one replica | `ReadWriteOnce` volume: never two SeaweedFS on the same directory |
| Exposure | the S3 gateway only, over TLS (8443); master, filer, volume, gRPC, administration and the HTTP gateway stay **inside the pod** | weed also listens over HTTP in the pod: the NetworkPolicy only opens the TLS port |
| Closed features | WebDAV, Iceberg, Lance; buckets created by the administrator only (`-s3.autoCreateBucket=false`); a non-empty bucket cannot be deleted | the exposed surface is limited to the useful S3 API |
| Internal administration | kept, password-protected (`WEED_ADMIN_PASSWORD` variable, `s3-admin` Secret) | without it, the maintenance worker (cleanup, rebalancing) loops on a refused connection; a variable rather than an argument, which would show in the node's process list |
| Identities | one `admin` identity, then **one per application, limited to its bucket** (`Read:fichiers`, `Write:fichiers`…); no anonymous identity | an application neither sees nor creates another bucket |
| `fichiers` bucket | versioning enabled, CORS limited to the file application's origin (GET, PUT, HEAD), `ProtegerVersions` policy | the browser uploads directly through presigned PUT; a write or a delete stays reversible |
| Bucket policy | explicit deny, for the application's identity only, of suspending versioning, changing CORS, lifecycle or policy, and deleting a version | without it, SeaweedFS's `Write` right would cover all of this; with the `*` principal, admin would be locked out too, with no way back |
| Network | `default-deny` on **ingress and egress**; 8443 ingress from the router, the workspace namespace and the initialization Job; DNS egress only | storage needs neither the Internet nor any other service |
| Telemetry | `-master.telemetry=false` | 100 % local goal; the closed egress would have stopped it anyway |
| Service links | `enableServiceLinks: false`, on the pod and the Job | see lessons: without it, the pod does not start |
| Resources | 100m and 256 Mi requested, 2 CPU and 2 Gi at most; namespace quota 3 CPU, 3 Gi, 4 pods | storage is a background service, with no expected peak |

## Files

| File | Content |
|---|---|
| `00-namespace.yaml` | namespace, `ResourceQuota`, `LimitRange` |
| `01-storage.yaml` | local PV and PVC naming each other |
| `02-seaweedfs.yaml` | Deployment, TLS Service (service certificate), service authority ConfigMap |
| `03-network.yaml` | default deny on ingress and egress, gateway ingress, DNS, Job egress |
| `04-route.yaml` | reencrypt Route, 900 s timeout for large files |
| `05-init-job.yaml` | replayable bucket setup: versioning, CORS, policy |

## Variables

| Variable | Role | Example |
|---|---|---|
| `${S3_HOST}` | DNS name of the S3 API, resolved to the VPN address | `s3.apps.example.org` |
| `${FILES_ORIGIN}` | exact origin of the file application (CORS) | `https://files.apps.example.org` |
| `${WORKSPACE_NAMESPACE}` | namespace of the file application | `workspace` |
| `${NODE_NAME}` | node carrying the volume (`oc get nodes`) | `node-0` |
| `${S3_MOUNT_POINT}` | mount point of the volume on the node | `/var/mnt/s3` |
| `${S3_SIZE}` | size of the PV and PVC | `200Gi` |
| `${S3_PRIORITY_CLASS}` | priority class of background services | `background` |
| `${SEAWEEDFS_VERSION}`, `${SEAWEEDFS_DIGEST}` | SeaweedFS image version and digest | `4.48`, `sha256:…` |
| `${AWSCLI_VERSION}`, `${AWSCLI_DIGEST}` | version and digest of the Job's S3 client image | `2.37.9`, `sha256:…` |

The Job contains shell variables (`$A`): substitution therefore names its variables, `envsubst '${S3_HOST} ${FILES_ORIGIN} …'`, never a bare `envsubst`, which would also empty `$A`.

## Secrets (never versioned)

| Secret | Namespace | Keys |
|---|---|---|
| `s3-config` | `sophia-storage` | `s3.json`: `admin` identity and one per application, with their keys |
| `s3-admin` | `sophia-storage` | `access-key`, `secret-key` (admin identity, for the Job), `admin-password` (internal administration) |
| `s3-tls` | `sophia-storage` | created by OKD (Service annotation) |

Values are generated in place and go **through a pipe**, never through `--from-literal`, which would put them in `oc`'s arguments, visible with `ps`. `printf` is a shell builtin: its arguments are not visible.

## Procedure (administrator)

From a clean, up-to-date clone of the internal repository; paths relative to `deploy/okd/storage/`. One step at a time; each `oc apply` is preceded by an `oc diff` read in full.

1. **Volume on the node**: logical volume, XFS, mount point, `/etc/fstab` line, mount, then the container SELinux context (`chcon -t container_file_t ${S3_MOUNT_POINT}`); procedure and pitfalls in [`../../stockage-persistant.en.md`](../../stockage-persistant.en.md). Expected: `findmnt ${S3_MOUNT_POINT}` shows the volume as `xfs`, `df -h` the planned size.
2. **Namespace and volume**: `00-namespace.yaml`, `01-storage.yaml`. Expected: `s3-data` is `Pending` (`WaitForFirstConsumer`) or `Bound` to `pv-sophia-s3`.
3. **Secrets**, values generated in place, never displayed or written to a file:
   ```bash
   export A_K=$(openssl rand -hex 12) A_S=$(openssl rand -hex 24) F_K=$(openssl rand -hex 12) F_S=$(openssl rand -hex 24) ADM_PW=$(openssl rand -hex 24)
   python3 -c 'import json,os; e=os.environ; print(json.dumps({"identities":[{"name":"admin","credentials":[{"accessKey":e["A_K"],"secretKey":e["A_S"]}],"actions":["Admin","Read","List","Tagging","Write"]},{"name":"fichiers","credentials":[{"accessKey":e["F_K"],"secretKey":e["F_S"]}],"actions":["Read:fichiers","Write:fichiers","List:fichiers","Tagging:fichiers"]}]}))' | oc -n sophia-storage create secret generic s3-config --from-file=s3.json=/dev/stdin
   printf 'access-key=%s\nsecret-key=%s\nadmin-password=%s\n' "$A_K" "$A_S" "$ADM_PW" | oc -n sophia-storage create secret generic s3-admin --from-env-file=/dev/stdin
   unset A_K A_S F_K F_S ADM_PW
   ```
   Expected: two Secrets, with 1 and 3 keys.
4. **Network, then SeaweedFS**: `03-network.yaml`, then `02-seaweedfs.yaml` and `oc -n sophia-storage rollout status deploy/s3`. Expected: pod ready; the log announces the S3 gateway over HTTPS on 8443, with no fatal error. A few "connection refused" from the maintenance worker at startup are normal: it waits for the administration.
5. **Route**: `04-route.yaml`.
6. **Bucket setup**: `05-init-job.yaml`, then `oc -n sophia-storage wait --for=condition=complete job/s3-init` and its log. Expected: `"Status": "Enabled"` for versioning, the CORS rule with `${FILES_ORIGIN}`, then the `ProtegerVersions` policy. To replay: delete the Job, then apply it again.
7. **Check through the real path**, from a VPN client: `curl -s -o /dev/null -w '%{http_code}\n' https://${S3_HOST}/fichiers/`. Expected: **`403`**: the Route, end-to-end TLS and the gateway answer, and anonymous access is refused.

The application identity's keys are copied into the application's own Secret, in its namespace, when it is deployed: read from `s3-config` into shell variables without display, passed through a pipe, then `unset`.

**Checks made before going into service**, on a binary of the same version with the same options: the application identity writes, reads and lists its versions (two writes of one key give two versions); it creates no bucket, touches no other bucket and cannot undo the protections; an anonymous read gets 403; a presigned PUT works; the CORS preflight is accepted for the application's origin and refused for another; a non-empty bucket cannot be deleted.

## Rollback

While nothing depends on the storage: delete the Route, the Job and `02-seaweedfs.yaml`. Data stays on the volume (PV in `Retain`). Afterwards, every consumer has its data in it: a rollback is limited to going back to the previous version of a template, then `oc apply`.

## Lessons

- **Service links**: Kubernetes injects, for each Service in the namespace, variables such as `S3_PORT=tcp://<address>:9000`. SeaweedFS reads environment variables as options (`S3_PORT` → `-s3.port`): the pod went into `CrashLoopBackOff` (`invalid value "tcp://…" for … s3.port`). Fix: `enableServiceLinks: false`. A local test, without a Service, could not show it.
- **An option is checked in the help of the deployed version**: `-telemetry=false`, taken from a log message, does not exist in mini mode ("flag provided but not defined") and caused a second `CrashLoopBackOff`; the option is `-master.telemetry=false`. Every option of the Deployment is now checked against `weed mini -h`.
- **Secrets through a pipe**: a first version created `s3-admin` with `--from-literal`, hence with the values in `oc`'s arguments. Fixed before use.
- **Default deny on egress too**: the telemetry announced at startup could not have left; the closed egress, not the option, is what guarantees 100 % local.

## Next

- **New consumer** (memory, modules): an identity in `s3-config`, limited to its bucket; an ingress rule in `03-network.yaml`; a bucket policy like `ProtegerVersions` if the bucket is versioned.
- **Several nodes**: `weed volume` instances added to the master, or separate components.
- **Upgrade**: a new digest in `02-seaweedfs.yaml`, options re-read in that version's `weed mini -h`, then `oc diff` and `apply`; data stays compatible.
