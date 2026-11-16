# Encrypted backup (`sophia-sauvegarde`)

The platform's data is backed up **inside the cluster**, encrypted before it is written, into a dedicated bucket of the [shared object storage](../storage/README.en.md). The software is **restic**: dated snapshots, deduplication, authenticated encryption. A dedicated namespace, with no ingress and no Internet access, reads the PostgreSQL databases, the copies prepared by the forge, the XMPP messaging and the vector database, and the namespaces' Secrets. It writes everything into a restic repository. The general framework (client-side encryption, off-site copy, checks) is in [Backup and Storage: Sovereign Solutions](../../../docs/security.en.md#backup-and-storage-sovereign-solutions).

**State in the reference installation**: **in service since 15/11**. The first full cycle was started by hand, the forced alert was received, then the jobs' suspension was lifted. The first **automatic** night cycle was checked on 16/11: the three extractions and the night job succeeded, one night snapshot in the repository, `restic check` without errors, no alert. The restore test has run once, by hand; the first scheduled test is on the following Sunday.

```text
02:45  extraction-forgejo  (sophia-git)         ──▶ bucket export-forge   ──┐
02:50  extraction-prosody  (sophia-messagerie)  ──▶ bucket export-prosody ──┤
02:55  extraction-qdrant   (sophia-memory)      ──▶ bucket export-qdrant  ──┼─▶ 03:30 sauvegarde-nuit ──┐
       cluster API: Secrets of the listed namespaces ───────────────────────┘                           │
PostgreSQL 18 (sophia-core) ──▶ every hour at :05, sauvegarde-bases ─────────────────────────────────────┼─▶ restic, encrypted
                                                                                                         │   ──▶ bucket sauvegardes
Sunday 08:00  essai-restauration: one database restored into an ephemeral PostgreSQL, checked, timed
```

Times are Paris time (the CronJobs' `timeZone: Europe/Paris`).

## Scope

| Data | How | When |
|---|---|---|
| PostgreSQL databases: every one that accepts connections, templates excluded | `pg_dump` of each database by the `sauvegarde` role, plus the global roles and objects, **without the roles' passwords** | every hour, at minute 05 |
| Forge (Forgejo): SQLite database, `app.ini`, attachments, avatars, LFS and other data outside the repositories | extraction in `sophia-git`, dropped into the `export-forge` bucket | extraction at 02:45, encrypted at 03:30 |
| XMPP messaging (Prosody): its data files | archive in `sophia-messagerie`, dropped into `export-prosody` | 02:50, encrypted at 03:30 |
| Vector database (Qdrant): full snapshot | through the Qdrant API, in `sophia-memory`, dropped into `export-qdrant` | 02:55, encrypted at 03:30 |
| Secrets of the listed namespaces (`${SECRETS_NAMESPACES}`) | read through the API, without service account tokens, reduced metadata | 03:30 |

**Not in this restic repository:**
- **the forge's Git repositories.** In the reference installation, the Forgejo export excludes the Git repositories. An installation must plan the copy of its repositories: see [the sovereign solutions](../../../docs/security.en.md#backup-and-storage-sovereign-solutions);
- **the object storage of files and memory**: the backup only reads the export buckets, and its identity has no right on the other buckets. An installation plans their copy the same way;
- **the restic repository password**: the Secrets of `sophia-sauvegarde` are not exported. This password is kept outside the platform, in several copies;
- **the off-site copy**: see "Off-site copy", below.

## Choices

| Choice | Value | Reason |
|---|---|---|
| Software | restic 0.19.1, **image pinned by digest**, served by the internal registry | client-side authenticated encryption, snapshots, deduplication; the namespace has no Internet access |
| Repository | `sauvegardes` bucket of the shared object storage, **without versioning or locking** | `restic prune` must be able to delete forgotten packs. Protection against a malicious deletion belongs to the off-site copy |
| Encryption | inside the cluster, before any write; password in the `restic-mot-de-passe` Secret, mounted read-only (`0400`) | the storage only sees encrypted blocks. Without this password, the repository is unreadable |
| Databases | every hour, at minute 05 | at most one hour of loss |
| Dump format | `pg_dump -Fc -Z0` (no compression), read back by `pg_restore --list`; owners and grants kept (no `--no-owner`) | restic deduplicates from one hour to the next; an unreadable dump stops the backup; a schema returns to its owner |
| PostgreSQL role | `sauvegarde`: login, member of `pg_read_all_data`, `CONNECT` on each database; neither superuser nor row-security bypass (`BYPASSRLS`) | it reads everything and cannot write anything |
| Extractions | in each service's namespace, then dropped into an internal bucket by a write-only identity (`Write`, without `Read` or `List`) | a pod from another namespace cannot read a service's volume: the SCC sets the SELinux level per namespace |
| Forge | pod under Forgejo's uid 1000, through the `lecture-forge` SCC (uid 1000 only, no capability, read-only root, usable by the `export-forge` account only); volume mounted read-only; consistent copy of the SQLite database, then `integrity_check` | `/data` belongs to uid 1000, mode `0700`; no right of the forge is removed or reduced |
| Vector database | snapshot through the API (`POST /snapshots`), deleted on Qdrant even on failure; refused if a collection that has points is missing | no volume mounted; an incomplete archive does not pass |
| Night | 03:30; an export that is not from the current day (UTC date) stops the backup | a stale copy does not pass for a fresh one |
| Secrets | one `Role` and one `RoleBinding` (`get`, `list`) per listed namespace, never a `ClusterRole`; `sophia-sauvegarde` excluded | a right limited to a written list; the restic password does not enter its own repository |
| Retention | databases: 48 hourly, 7 daily, 5 weekly, 12 monthly; night: 7 daily, 5 weekly, 12 monthly; `prune` every night | `restic forget` by tag (`bases`, `nuit`) |
| Integrity | `restic check --read-data-subset 2%` every night | part of the data is read back every night |
| Restore test | Sunday at 08:00: one database restored into an ephemeral PostgreSQL (sidecar container of the pod), roles first, then schema owners and the row count of each table compared with the dump; **600 s at most**. The largest database in the first week of the month, otherwise a database rotating with the week number | a backup only counts if it restores |
| Concurrency | `concurrencyPolicy: Forbid`, `backoffLimit: 0`; `--retry-lock 30m` | the night's `prune` takes an exclusive lock: the next hourly backup waits instead of failing |
| Durations | at most 30 min (databases), 3 h (night), 1 h (test); allowed start delay: 15 min, 1 h, 1 h | a stuck job ends in failure, hence in an alert |
| Network | no ingress; egress: DNS, PostgreSQL (5432), S3 gateway (8443), cluster API (6443); an `EgressFirewall` that denies everything else | nothing leaves the cluster |
| Tokens | `automountServiceAccountToken: false` everywhere, except for the night (the Secrets export goes through the API); `enableServiceLinks: false` | a pod that does not need the API has no token |
| Resources | namespace quota: 4 CPU and 6 Gi in limits, 4 pods; work volume in `emptyDir` (10 Gi, 30 Gi, 20 Gi) | nothing stays in clear after the run |
| Alerts | five per CronJob: failed, late (2 h, 26 h, 8 days), never succeeded, missing, suspended | a backup only counts with an automatic check that alerts |

## Files

| File | Namespace | Content |
|---|---|---|
| `00-namespace.yaml` | `sophia-sauvegarde` | namespace, quota, defaults, default deny and egress, `EgressFirewall`, `sauvegarde` account |
| `01-images.yaml` | `sophia-sauvegarde` | six ImageStreams pinned by digest: restic, rclone, PostgreSQL 18, Python, `oc`, S3 client |
| `02-lecture-secrets.yaml` | one namespace of the list | `Role` and `RoleBinding` to read Secrets; rendered once per namespace |
| `03-scripts.yaml` | `sophia-sauvegarde` | backup and test scripts; ConfigMap of the OKD service CA |
| `04-cronjobs.yaml` | `sophia-sauvegarde` | CronJobs `sauvegarde-bases`, `sauvegarde-nuit`, `essai-restauration` |
| `05-restic-init.yaml` | `sophia-sauvegarde` | Job that creates the restic repository, once |
| `06-scc-lecture-forge.yaml` | cluster, `sophia-git` | `lecture-forge` SCC, its usage `ClusterRole`, the `RoleBinding` of the `export-forge` account |
| `07-extraction-forgejo.yaml` | `sophia-git` | account, image pull right, egress, scripts, `extraction-forgejo` CronJob |
| `08-extraction-prosody.yaml` | `sophia-messagerie` | account, image pull right, egress, scripts, `extraction-prosody` CronJob |
| `09-extraction-qdrant.yaml` | `sophia-memory` | account, image pull right, egress, ingress on Qdrant, scripts, `extraction-qdrant` CronJob |
| `10-seaux.yaml` | `sophia-storage` | Job for the four buckets, replayable |
| `11-alertes.yaml` | the four namespaces | one `PrometheusRule` per namespace, five alerts per CronJob |

## Variables

| Variable | Role | Example |
|---|---|---|
| `${LAN_NODE_IP}` | node address: the `kubernetes` Service ends there, port 6443 | `192.0.2.10` |
| `${SERVICE_NETWORK}`, `${POD_NETWORK}` | cluster Service and pod networks | `172.30.0.0/16`, `10.128.0.0/14` (OKD defaults) |
| `${PG18_DIGEST}` | digest of the [PostgreSQL 18](../core/postgres18/README.en.md) instance image: `pg_dump` must be the same version | `sha256:…` |
| `${OKD_CLI_IMAGE}` | `oc` image of the cluster version, the one of `openshift/cli:latest` | `quay.io/okd/scos-content@sha256:…` |
| `${AWSCLI_VERSION}`, `${AWSCLI_DIGEST}` | version and digest of the S3 client image, as for the [storage](../storage/README.en.md) | `2.37.9`, `sha256:…` |
| `${SECRETS_NAMESPACES}` | namespaces whose Secrets are exported, separated by spaces, **without** `sophia-sauvegarde` | `sophia-core sophia-git sophia-memory sophia-messagerie sophia-storage` |
| `${NAMESPACE_LU}` | one namespace of this list, to render `02-lecture-secrets.yaml` (set by the loop of step 2) | `sophia-core` |
| `${SUSPENDRE}` | `true` at the first rollout, `false` once the first cycle is checked | `true` |
| `${FORGEJO_PVC}` | PVC of Forgejo's `/data` volume, in `sophia-git` | `forgejo-data` |
| `${PROSODY_PVC}` | PVC of Prosody's data, in `sophia-messagerie` | `prosody-data` |

The templates' scripts have their own `$`: each rendering therefore names its variables, `envsubst '${…}'`, never an `envsubst` without a list. `03-scripts.yaml`, `05-restic-init.yaml`, `06-scc-lecture-forge.yaml` and `11-alertes.yaml` have no variable.

## Secrets (never versioned)

| Secret | Namespace | Keys | Created at |
|---|---|---|---|
| `sauvegarde-s3` | `sophia-sauvegarde` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | step 3 |
| `export-forge-s3` | `sophia-git` | same | step 3 |
| `export-prosody-s3` | `sophia-messagerie` | same | step 3 |
| `export-qdrant-s3` | `sophia-memory` | same | step 3 |
| `postgres-sauvegarde` | `sophia-sauvegarde` | `password` (48 hexadecimal characters) | step 4 |
| `restic-mot-de-passe` | `sophia-sauvegarde` | `password` | step 5 |
| `qdrant-cle` | `sophia-memory` | `cle`: the one Qdrant already reads ([memory](../memory/memoire/README.en.md)) | existing |
| `s3-config`, `s3-admin` | `sophia-storage` | those of the [storage](../storage/README.en.md) | existing |

Values are drawn on the spot and go **through a pipe**, never as an argument. The restic password, however, must be kept outside the platform: it is typed through `read -rs`, without being displayed.

## Procedure (administrator)

Prerequisites: the [object storage](../storage/README.en.md), [PostgreSQL 18](../core/postgres18/README.en.md), Forgejo in `sophia-git`, Prosody in `sophia-messagerie`, Qdrant and its `qdrant-cle` Secret in `sophia-memory`, and the [monitoring](../monitoring/README.en.md), which routes the `sophia: oui` alerts. Commands from this folder, with cluster administration rights. One step at a time; each check is read before the next step. On macOS, replace `sha256sum` with `shasum -a 256`.

**Step 0 — Variables.** Read the installation's own values:

```bash
oc -n openshift get istag cli:latest -o jsonpath='{.image.dockerImageReference}{"\n"}'
oc -n sophia-core get deploy postgres-sophia-18 -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
oc -n sophia-git get pvc
oc -n sophia-messagerie get pvc
```

Expected: the `oc` image (that is `${OKD_CLI_IMAGE}`), the PostgreSQL image and its digest (`${PG18_DIGEST}`), then the Forgejo and Prosody PVCs. Then export each variable of the table (`export NAME=value`), with `SUSPENDRE=true`, then:

```bash
env | grep -E '^(LAN_NODE_IP|SERVICE_NETWORK|POD_NETWORK|PG18_DIGEST|OKD_CLI_IMAGE|AWSCLI_VERSION|AWSCLI_DIGEST|SECRETS_NAMESPACES|SUSPENDRE|FORGEJO_PVC|PROSODY_PVC)='
```

Expected: eleven lines, none empty.

**Step 1 — Namespace and images:**

```bash
envsubst '${LAN_NODE_IP} ${SERVICE_NETWORK} ${POD_NETWORK}' < 00-namespace.yaml | oc apply --dry-run=server -f -
envsubst '${LAN_NODE_IP} ${SERVICE_NETWORK} ${POD_NETWORK}' < 00-namespace.yaml | oc apply -f -
envsubst '${PG18_DIGEST} ${OKD_CLI_IMAGE} ${AWSCLI_VERSION} ${AWSCLI_DIGEST}' < 01-images.yaml | oc apply -f -
oc -n sophia-sauvegarde get istag
```

Expected: seven objects `created (server dry run)`, then `created`; six ImageStreams; then six ImageStreamTags, each with its digest. A tag without an image: check its ImageStream's digest.

**Step 2 — Reading Secrets**, one `Role` and one `RoleBinding` per namespace of the list, then the check as the account itself:

```bash
for ns in $(echo "$SECRETS_NAMESPACES"); do NAMESPACE_LU=$ns envsubst '${NAMESPACE_LU}' < 02-lecture-secrets.yaml | oc apply -f -; done
for ns in $(echo "$SECRETS_NAMESPACES"); do echo "$ns : $(oc auth can-i list secrets -n $ns --as=system:serviceaccount:sophia-sauvegarde:sauvegarde)"; done
oc auth can-i list secrets -n sophia-sauvegarde --as=system:serviceaccount:sophia-sauvegarde:sauvegarde
```

Expected: two `created` per namespace; then `yes` for each; then `no` for `sophia-sauvegarde`.

**Step 3 — S3 identities and buckets.** In the reference installation, this step was played in several rounds, as the extractions were added; it is given here as a single final state, which has not been replayed as is. Read each check again before the next command. First a copy of the identities configuration, **inside the cluster**; then the four Secrets, filled by `openssl` in a pipe:

```bash
oc -n sophia-storage get secret s3-config -o json | python3 -c 'import json, sys; d = json.load(sys.stdin); d["metadata"] = {"name": "s3-config-avant-sauvegarde", "namespace": d["metadata"]["namespace"]}; d.pop("status", None); print(json.dumps(d))' | oc create -f -
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-sauvegarde create secret generic sauvegarde-s3 --from-env-file=/dev/stdin
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-git create secret generic export-forge-s3 --from-env-file=/dev/stdin
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-messagerie create secret generic export-prosody-s3 --from-env-file=/dev/stdin
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-memory create secret generic export-qdrant-s3 --from-env-file=/dev/stdin
```

Expected: `secret/s3-config-avant-sauvegarde created`, then four `created`. Then the four identities, drawn from these Secrets and added to `s3-config` through private temporary files, erased in the same block; the new `s3.json` is only sent if the script succeeded. Then a consistency check by truncated fingerprints, never displayed:

```bash
( umask 077; T=$(mktemp -d); oc -n sophia-storage get secret s3-config -o jsonpath='{.data.s3\.json}' | base64 -d > "$T/s3.json" && oc -n sophia-sauvegarde get secret sauvegarde-s3 -o json > "$T/a.json" && oc -n sophia-git get secret export-forge-s3 -o json > "$T/b.json" && oc -n sophia-messagerie get secret export-prosody-s3 -o json > "$T/c.json" && oc -n sophia-memory get secret export-qdrant-s3 -o json > "$T/d.json" && python3 -c 'import base64, json, sys; c = json.load(open(sys.argv[1])); cl = lambda f: tuple(base64.b64decode(json.load(open(f))["data"][x]).decode() for x in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")); cles = [cl(f) for f in sys.argv[2:6]]; assert all(len(k) == 24 and len(s) == 48 for k, s in cles), "clés inattendues"; noms = [i["name"] for i in c["identities"]]; nouveaux = ["sauvegarde", "export-forge", "export-prosody", "export-qdrant"]; assert not set(nouveaux) & set(noms), "identité déjà présente"; lect = [v + ":" + s for s in nouveaux[1:] for v in ("Read", "List")]; droits = [lect + ["Read:sauvegardes", "Write:sauvegardes", "List:sauvegardes"]] + [["Write:" + n] for n in nouveaux[1:]]; [c["identities"].append({"name": n, "credentials": [{"accessKey": k, "secretKey": s}], "actions": a}) for n, (k, s), a in zip(nouveaux, cles, droits)]; json.dump(c, open(sys.argv[6], "w")); print("identités :", noms, "+", ", ".join(nouveaux))' "$T/s3.json" "$T/a.json" "$T/b.json" "$T/c.json" "$T/d.json" "$T/nouveau.json" && oc -n sophia-storage set data secret/s3-config --from-file=s3.json="$T/nouveau.json"; rm -rf "$T" )
( umask 077; T=$(mktemp -d); oc -n sophia-storage get secret s3-config -o jsonpath='{.data.s3\.json}' | base64 -d > "$T/s3.json" && oc -n sophia-sauvegarde get secret sauvegarde-s3 -o json > "$T/a.json" && oc -n sophia-git get secret export-forge-s3 -o json > "$T/b.json" && oc -n sophia-messagerie get secret export-prosody-s3 -o json > "$T/c.json" && oc -n sophia-memory get secret export-qdrant-s3 -o json > "$T/d.json" && python3 -c 'import base64, hashlib, json, sys; c = json.load(open(sys.argv[1])); e = lambda v: hashlib.sha256(v.encode()).hexdigest()[:12]; ok = lambda nom, f: (lambda m, d: (e(m["accessKey"]), e(m["secretKey"])) == (e(base64.b64decode(d["AWS_ACCESS_KEY_ID"]).decode()), e(base64.b64decode(d["AWS_SECRET_ACCESS_KEY"]).decode())))([i for i in c["identities"] if i["name"] == nom][0]["credentials"][0], json.load(open(f))["data"]); print([(i["name"], i["actions"]) for i in c["identities"]]); print("concordance :", "ok" if all(ok(n, f) for n, f in zip(["sauvegarde", "export-forge", "export-prosody", "export-qdrant"], sys.argv[2:6])) else "ÉCART")' "$T/s3.json" "$T/a.json" "$T/b.json" "$T/c.json" "$T/d.json"; rm -rf "$T" )
```

Expected:
- `identités : [...] + sauvegarde, export-forge, export-prosody, export-qdrant`, then `secret/s3-config data updated`;
- all identities with their rights: the previous ones have not changed; `sauvegarde` has 9 rights (`Read` and `List` on the three export buckets, `Read`, `Write` and `List` on `sauvegardes`); each `export-…` has only one, `Write` on its bucket;
- `concordance : ok`. No key is displayed.

The entries on the S3 gateway: the `sophia-sauvegarde` namespace, and the single extraction pod of each of the other three. The [`../storage/03-network.yaml`](../storage/03-network.yaml) template contains them: if `s3-ingress` was applied from its current version, skip the patch and go to the check (the last command of the block). Otherwise, a JSON patch that starts with a `test` of the live state, and only adds these four entries, after a copy of the rule:

```bash
mkdir -p "$HOME/sauvegardes"
oc -n sophia-storage get networkpolicy s3-ingress -o yaml > "$HOME/sauvegardes/s3-ingress-avant-sauvegarde.yaml"
oc -n sophia-storage patch networkpolicy s3-ingress --type=json -p '[{"op":"test","path":"/spec/ingress/0/ports/0/port","value":8443},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-git"}},"podSelector":{"matchLabels":{"app":"export-forge"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-messagerie"}},"podSelector":{"matchLabels":{"app":"export-prosody"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-memory"}},"podSelector":{"matchLabels":{"app":"export-qdrant"}}}}]' --dry-run=server
oc -n sophia-storage patch networkpolicy s3-ingress --type=json -p '[{"op":"test","path":"/spec/ingress/0/ports/0/port","value":8443},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-git"}},"podSelector":{"matchLabels":{"app":"export-forge"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-messagerie"}},"podSelector":{"matchLabels":{"app":"export-prosody"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-memory"}},"podSelector":{"matchLabels":{"app":"export-qdrant"}}}}]'
oc -n sophia-storage get networkpolicy s3-ingress -o json | python3 -c 'import json, sys; d = json.load(sys.stdin); print([(f.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name", "-"), f.get("podSelector", {}).get("matchLabels", {}).get("app", "-")) for f in d["spec"]["ingress"][0]["from"]])'
```

Expected: `patched (server dry run)`, then `patched`, then the list of entries, ending with `('sophia-sauvegarde', '-'), ('sophia-git', 'export-forge'), ('sophia-messagerie', 'export-prosody'), ('sophia-memory', 'export-qdrant')`. If the installation's template is older, carry these four entries into it, so that a later `oc apply` does not remove them.

The storage restart, since it only reads its identities at startup. **It cuts the object storage for about a minute** (files, memory):

```bash
oc -n sophia-storage rollout restart deploy/s3
oc -n sophia-storage rollout status deploy/s3 --timeout=5m
```

Then the buckets:

```bash
envsubst '${AWSCLI_VERSION} ${AWSCLI_DIGEST}' < 10-seaux.yaml | oc apply -f -
oc -n sophia-storage wait --for=condition=complete job/s3-init-sauvegardes --timeout=5m
oc -n sophia-storage logs job/s3-init-sauvegardes
```

Expected: for each of the four buckets, `"Location"` at creation, no versioning, `ObjectLockConfigurationNotFoundError` under "verrouillage" (wanted); then the list of buckets, with `sauvegardes`, `export-forge`, `export-prosody` and `export-qdrant`.

**Step 4 — PostgreSQL role `sauvegarde`.** Nothing must exist:

```bash
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d postgres -Atc "select count(1) from pg_roles where rolname = 'sauvegarde'"
```

Expected: `0`. Then the Secret first, and the role through its SCRAM verifier, computed outside the server by [`role-scram.py`](../memory/memoire/role-scram.py); then its rights; then a reading of what it is:

```bash
openssl rand -hex 24 | tr -d '\n' | oc -n sophia-sauvegarde create secret generic postgres-sauvegarde --from-file=password=/dev/stdin && oc -n sophia-sauvegarde get secret postgres-sauvegarde -o jsonpath='{.data.password}' | base64 -d | python3 ../memory/memoire/role-scram.py sauvegarde | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- psql -d postgres -v ON_ERROR_STOP=1
printf 'GRANT pg_read_all_data TO sauvegarde;\nSELECT format(%sGRANT CONNECT ON DATABASE %%I TO sauvegarde%s, datname) FROM pg_database WHERE datallowconn AND NOT datistemplate ORDER BY datname \\gexec\n' "'" "'" | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- psql -d postgres -v ON_ERROR_STOP=1
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d postgres -Atc "select rolname, rolcanlogin, rolsuper, rolbypassrls, left(rolpassword, 14), pg_has_role('sauvegarde', 'pg_read_all_data', 'member'), (select count(1) from pg_database d where d.datallowconn and not d.datistemplate and not has_database_privilege('sauvegarde', d.datname, 'CONNECT')) from pg_authid where rolname = 'sauvegarde'"
```

Expected, line by line:
1. `secret/postgres-sauvegarde created`, `vérificateur SCRAM-SHA-256 calculé localement`, then `CREATE ROLE`;
2. `GRANT ROLE`, then one `GRANT` per database;
3. `sauvegarde|t|f|f|SCRAM-SHA-256$|t|0`: login allowed, not superuser, no row-security bypass, SCRAM verifier, member of `pg_read_all_data`, no database without `CONNECT`.

The `sophia-sauvegarde` entry on PostgreSQL, which the [`../core/postgres18/03-network.yaml`](../core/postgres18/03-network.yaml) template also contains (if `postgres-18-ingress` comes from its current version, skip this patch), otherwise through a JSON patch that starts with a `test`, after a copy of the rule:

```bash
oc -n sophia-core get networkpolicy postgres-18-ingress -o yaml > "$HOME/sauvegardes/postgres-18-ingress-avant-sauvegarde.yaml"
oc -n sophia-core patch networkpolicy postgres-18-ingress --type=json -p '[{"op":"test","path":"/spec/podSelector/matchLabels/app","value":"postgres-sophia-18"},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}}]' --dry-run=server
oc -n sophia-core patch networkpolicy postgres-18-ingress --type=json -p '[{"op":"test","path":"/spec/podSelector/matchLabels/app","value":"postgres-sophia-18"},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}}]'
```

Expected: `patched (server dry run)`, then `patched`. If the installation's template is older, carry the entry into it.

**Step 5 — restic repository password.** Create it first in a password manager (at least 32 random characters), and keep it in several copies, **outside the platform**: without it, every backup is unreadable. Then paste it at the `read` prompt, which displays nothing:

```bash
read -rs RESTIC_MDP
printf '%s' "$RESTIC_MDP" | oc -n sophia-sauvegarde create secret generic restic-mot-de-passe --from-file=password=/dev/stdin
printf '%s' "$RESTIC_MDP" | sha256sum | cut -c1-12
unset RESTIC_MDP
oc -n sophia-sauvegarde get secret restic-mot-de-passe -o jsonpath='{.data.password}' | base64 -d | sha256sum | cut -c1-12
```

Expected: `secret/restic-mot-de-passe created`, then twice the **same** 12 characters (a fingerprint, never the value). Two different fingerprints: delete the Secret and start again.

**Step 6 — Scripts and restic repository:**

```bash
oc apply -f 03-scripts.yaml
oc apply -f 05-restic-init.yaml
until oc -n sophia-sauvegarde get job restic-init -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/restic-init
```

Expected: two ConfigMaps `created`, the Job `created`, then `created restic repository … at s3:https://s3.sophia-storage.svc:9000/sauvegardes`.

**Step 7 — CronJobs, suspended** (`SUSPENDRE=true`). The SCC first, since the forge extraction pod pins it:

```bash
oc apply -f 06-scc-lecture-forge.yaml
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc apply --dry-run=server -f -
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${FORGEJO_PVC}' < 07-extraction-forgejo.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${PROSODY_PVC}' < 08-extraction-prosody.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION}' < 09-extraction-qdrant.yaml | oc apply -f -
oc get cronjob -A -o custom-columns=NS:.metadata.namespace,NOM:.metadata.name,SUSPENDU:.spec.suspend | grep -E 'sauvegarde|extraction|NOM'
```

Expected: three objects `created` for the SCC; three CronJobs; six, six and seven objects for the extractions; then six lines `SUSPENDU true`.

**Step 8 — Alerts, and forced alert:**

```bash
oc apply -f 11-alertes.yaml
oc get prometheusrule -A -l sophia=oui | grep -E 'NAME|sauvegardes'
```

Expected: four `sophia-sauvegardes`, in `sophia-git`, `sophia-memory`, `sophia-messagerie` and `sophia-sauvegarde`. After one hour, `SophiaSauvegardeSuspendue` (warning) fires for each of the six CronJobs and must reach the administrator: this proves the alert chain.

**Step 9 — First cycle, by hand.** In order, each after the previous check. The three extractions and the night must fall **on the same UTC day**: the night refuses an export from another day. The dumps first:

```bash
oc -n sophia-sauvegarde create job sauvegarde-bases-premier --from=cronjob/sauvegarde-bases
until oc -n sophia-sauvegarde get job sauvegarde-bases-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/sauvegarde-bases-premier --all-containers
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d postgres -Atc "select count(1) from pg_database where datallowconn and not datistemplate"
```

Expected: `vidages : N bases, … Mo`, the restic summary (`Added to the repository: …`) and the kept snapshots; then the same N. The extractions:

```bash
oc -n sophia-git create job extraction-forgejo-premier --from=cronjob/extraction-forgejo
until oc -n sophia-git get job extraction-forgejo-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-git logs job/extraction-forgejo-premier --all-containers
oc -n sophia-messagerie create job extraction-prosody-premier --from=cronjob/extraction-prosody
until oc -n sophia-messagerie get job extraction-prosody-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-messagerie logs job/extraction-prosody-premier --all-containers
oc -n sophia-memory create job extraction-qdrant-premier --from=cronjob/extraction-qdrant
until oc -n sophia-memory get job extraction-qdrant-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-memory logs job/extraction-qdrant-premier --all-containers
```

Expected:
- forge: `dépôts git exclus de l'archive : N`, `Forgejo : base copiée (integrity_check ok), archive de … Mo`, then `déposé : forgejo.tar dans export-forge, … Mo`;
- messaging: `Prosody : archive de … Mo`, then `déposé : prosody.tar dans export-prosody, … Mo`;
- vector database: `Qdrant : N collections, … points avant l'instantané (…)`, `Qdrant : instantané complet … téléchargé, … Ko, … fichiers dans l'archive, supprimé de Qdrant`, then `déposé : qdrant.snapshot dans export-qdrant, … Mo`.

The night, then the restore test:

```bash
oc -n sophia-sauvegarde create job sauvegarde-nuit-premier --from=cronjob/sauvegarde-nuit
until oc -n sophia-sauvegarde get job sauvegarde-nuit-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/sauvegarde-nuit-premier --all-containers
oc -n sophia-sauvegarde create job essai-restauration-premier --from=cronjob/essai-restauration
until oc -n sophia-sauvegarde get job essai-restauration-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/essai-restauration-premier --all-containers
```

Expected:
- night: the size of the three export copies (otherwise `export périmé : …`: then redo the extraction concerned), `Secrets exportés : … dans N namespaces`, the restic summary, the two `forget`, the `prune`, then `no errors were found`;
- test: `base choisie : …`, then `restauration de … : … tables, décomptes égaux, … schémas à leur propriétaire, … s`, under 600 s.

**Step 10 — Review:**

```bash
oc get cronjob -A -o custom-columns=NS:.metadata.namespace,NOM:.metadata.name,SUSPENDU:.spec.suspend,DERNIER_SUCCES:.status.lastSuccessfulTime | grep -E 'sauvegarde|extraction|NOM'
```

Expected: six lines `SUSPENDU true`, each with `DERNIER_SUCCES` filled in: Jobs started with `--from=cronjob` carry their CronJob's ownerReference. With the alert of step 8 received, the first cycle is done.

**Step 11 — Lifting the suspension.** `export SUSPENDRE=false`, then the same rendering, checked by `oc diff`:

```bash
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc diff -f -
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${FORGEJO_PVC}' < 07-extraction-forgejo.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${PROSODY_PVC}' < 08-extraction-prosody.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION}' < 09-extraction-qdrant.yaml | oc apply -f -
oc get cronjob -A -o custom-columns=NS:.metadata.namespace,NOM:.metadata.name,SUSPENDU:.spec.suspend,DERNIER_SUCCES:.status.lastSuccessfulTime | grep -E 'sauvegarde|extraction|NOM'
```

Expected: the diff only shows `suspend: true` turned into `false`, for the three CronJobs; then six `cronjob.batch/… configured` in all (the other objects `unchanged`); then six lines `SUSPENDU false`. `SophiaSauvegardeSuspendue` resolves within the hour; the first automatic dump starts at the next minute 05.

**Step 12 — First automatic cycle**, the next morning: the command of step 10. Expected: a `DERNIER_SUCCES` from the night for the three extractions and for `sauvegarde-nuit`, less than one hour old for `sauvegarde-bases`, and no alert. The restore test follows on Sunday at 08:00.

## Restoring

The only proven path is the weekly test's: one database restored into an ephemeral PostgreSQL, checked, then thrown away (`essai-restaurer.sh`, `essai-verifier.sh` in `03-scripts.yaml`). Its scripts are the model of a restore: roles first (`globales.sql`, without passwords), then the database with its owners. The roles' passwords are not in the dumps; they are in the Secrets, exported every night. Per-database settings (`ALTER DATABASE … SET`) are not in a dump: the rebuild puts them back. The `lecture-forge` SCC is also meant for restoring Forgejo under its uid. Restoring a service in place and rebuilding the server have no written procedure yet.

## Off-site copy

The restic repository is in the object storage of the same server: it protects against a mistake or corrupted data, not against the loss of the server. An installation adds an off-site copy of the `sauvegardes` bucket, which only holds encrypted blocks, pushed by an account that can neither replace nor delete. The options are in [Backup and Storage: Sovereign Solutions](../../../docs/security.en.md#backup-and-storage-sovereign-solutions). These templates contain none.

## Rollback

In reverse order, and only knowingly: without these jobs, nothing is backed up any more. Suspend first (`SUSPENDRE=true`, step 11). Then `oc delete` of the renderings of `11`, `09`, `08`, `07` and `06`; the `Role` and `RoleBinding` of each namespace of the list (`oc -n <namespace> delete role,rolebinding sauvegarde-lecture-secrets`); then the `sophia-sauvegarde` namespace, which takes its CronJobs, images and Secrets with it, **restic password included**: the repository can then only be read with the copies kept outside the platform. On PostgreSQL: `REVOKE CONNECT` on each database (same `\gexec` as in step 4), `REVOKE pg_read_all_data FROM sauvegarde`, `DROP ROLE sauvegarde`; the ingress rule from its copy (`oc apply -f "$HOME/sauvegardes/postgres-18-ingress-avant-sauvegarde.yaml"`). On the storage: `s3-config` from `s3-config-avant-sauvegarde`, then the restart (a cut of about one minute); `s3-ingress` from its copy; the `export-…-s3` Secrets of the three namespaces. Buckets can only be deleted empty, by the administration identity: emptying `sauvegardes` **destroys every backup**. The `s3-config-avant-sauvegarde` copy is deleted once the first automatic cycle is compliant.

## Pitfalls

- **Namespace SELinux level.** A `sophia-sauvegarde` pod cannot read the forge's volume nor the messaging's: the SCC sets the SELinux level per namespace. Hence the extractions, each in its service's namespace, which drop a copy into an internal bucket.
- **Forge under uid 1000, mode `0700`.** `restricted-v2` gives a uid from the namespace's range, which cannot read `/data`. Hence the `lecture-forge` SCC, pinned by annotation. It is only narrow for the pods that pin it: check the other SCCs granted to the accounts of the forge's namespace.
- **SQLite in WAL mode on a read-only volume.** Copying the Forgejo database sometimes needs the `-shm` file. In the reference installation, it works read-only; if it fails for you, mounting the volume read-write is a separate decision.
- **Export of the day, in UTC.** The night refuses an export from another UTC day. By hand, run the extractions and the night on the same UTC day: in Paris, just after midnight, the UTC date is still the previous day.
- **restic lock.** The night's `prune` takes an exclusive lock; without `--retry-lock`, the next hourly dump would fail.
- **CPU quota.** The night, an hourly dump and the test together would exceed the quota's 4 CPU: the test starts on Sunday at 08:00, after the night window (03:30, one hour of allowed delay and three of duration, so 07:30 at the latest).
- **Messaging quota.** The Prosody extraction runs in the messaging namespace: its limits, init container included, must fit in what that namespace's quota leaves.
- **New database.** The `sauvegarde` role only has `CONNECT` on the databases that existed at step 4: for a database created later, replay the `GRANT CONNECT` line (replayable), otherwise the hourly dump fails, and the alert says so.
- **New namespace.** Add it to `${SECRETS_NAMESPACES}`, render `02-lecture-secrets.yaml` for it, then render `04-cronjobs.yaml` again: otherwise its Secrets are not backed up, without an alert.
- **One alert rule per namespace.** Thanos Ruler only shows a `PrometheusRule` the series of its own namespace: a central rule would not see the other namespaces' CronJobs.
- **Test password.** The test's ephemeral PostgreSQL has a fixed password (`POSTGRESQL_ADMIN_PASSWORD` in `04-cronjobs.yaml`). It is not a secret: the instance can only be reached inside the pod and disappears with it.
