# PostgreSQL 18 — shared instance (`sophia-core`)

Every database of the platform lives in **one PostgreSQL 18 instance**: model router, workflow engine, identity provider, chat interface, modules, the office suite's file management, the memory schema. It replaced a PostgreSQL 15 instance, migrated database by database.

**Why 18**: the office suite's file management stores its items in an `ltree` path whose labels contain hyphens, which PostgreSQL only accepts from version 16; on 15, creating a folder failed (error 500), although the migrations passed. Rather than keep a version debt, every database moved to the latest stable version.

## Choices

| Item | Choice | Reason |
|---|---|---|
| One instance | every database, one owner role per database | a single version upgrade, a single backup, a single volume to watch |
| Roles | **no network superuser**: each database has its owner role (model router, memory, human approvals, each application); `postgres` stays superuser, **through the pod's local socket only** | a compromised application reads only its database; the former shared superuser role is not recreated |
| Image | sclorg PostgreSQL 18, **pinned by digest**, `IfNotPresent`; a build a few days old, not the very latest | a restart never pulls another version; some hindsight on the image |
| Extensions | checked in the image layers before adopting it (`ltree`, `pg_trgm`, `unaccent`, `pgcrypto`, `uuid-ossp`, `btree_gin`, `vector`…); "trusted" extensions are created by the database owner | no upgrade blocked by a missing extension, no superuser to create them |
| Volume | **dedicated XFS logical volume** (20 GB to start), mounted under `/var/mnt`, local PV and PVC bound to each other, `Retain` | outside the node's `/var`; grows online (`lvextend -r`); alert at 80% and 90% ([`../../monitoring/`](../../monitoring/)) |
| Deployment | `Recreate`, `pg_isready` probes, `enableServiceLinks: false`, `sophia-chat` class | `ReadWriteOnce` volume; chat depends on the database |
| Ingress | a single rule (`03-network.yaml`) for every consumer | readable at a glance; the document editor has no access |
| Retention | model router's detailed log: 30 days; workflow engine: 30 days; memory audit: 1 year; conversations, applications and memories: none | technical logs do not grow forever; people's data stays theirs |

## Files

| File | Content |
|---|---|
| `01-storage.yaml` | local PV and PVC, bound to each other |
| `02-instance.yaml` | `postgres-sophia-18` Deployment and Service |
| `03-network.yaml` | 5432 ingress, per consumer |

## Variables

| Variable | Role | Example |
|---|---|---|
| `${PG_MOUNT_POINT}` | mount point of the logical volume | `/var/mnt/postgres-18` |
| `${PG_SIZE}` | declared size (a label, for a local volume) | `20Gi` |
| `${NODE_NAME}` | node carrying the volume | `node-0` |
| `${PG18_DIGEST}` | digest of the chosen image | `sha256:…` |
| `${WORKSPACE_NAMESPACE}` | office suite namespace | `workspace` |

## Secrets (never versioned)

| Secret | Keys |
|---|---|
| `postgres-sophia-18-creds` | `password`: the model router's role, created by the image |
| `postgres-18-<role>` | `password`: one per role created by `psql` (a Secret name has no `_`: `sophia_rag` → `postgres-18-sophia-rag`) |

Each password is drawn on the spot (`openssl rand -hex 24`) and goes through a pipe to `oc create secret … --from-file=password=/dev/stdin`. The Secret is created **before** the role, and the role only if the Secret succeeded (`&&`): a password is never lost.

## Procedure (the administrator)

1. **Volume on the node**: logical volume, XFS, mount point, `/etc/fstab`, mount, `chcon -t container_file_t` ([`../../../stockage-persistant.en.md`](../../../stockage-persistant.en.md)). Expected: `findmnt` shows the volume as `xfs`.
2. **Instance**: the Secret, then `01-storage.yaml`, `03-network.yaml`, `02-instance.yaml`. Expected: PVC `Bound`, pod ready, `select version()` answers `PostgreSQL 18.x`.
3. **Backup** before each step: `pg_dumpall --clean --if-exists` to the administration workstation; the last line must be `PostgreSQL database cluster dump complete`.

### Migrating a database: the ritual

For each database, one at a time:

0. **Check the consumer's egress, before stopping anything.** The new instance's ingress is not enough: if the consumer's namespace restricts its **egress**, its rule must also open 5432 to the new instance. Two checks: the namespace's egress rules, then **a real TCP connection** from the consumer's pod. Otherwise, stop without cutting anything.
1. **Backup** of the old instance.
2. **Role copied with its SCRAM hash** (`pg_dumpall --roles-only`, through a pipe): the consumer keeps its password, only the address changes. For a **new** role (splitting a database, end of the shared superuser), restore with `--no-owner --role=<owner>`.
3. **Stop the consumer**, so it no longer writes to the old instance.
4. **`pg_dump -Fc` then `pg_restore --exit-on-error`**, then `analyze`.
5. **Exact count** of tables and rows on both sides (`count(*)` of each table, through `query_to_xml`). Not `n_live_tup`: those statistics are 0 on a restored database or a restarted instance.
6. **Switch the address** in the consumer's Secret or manifest (only the keys holding the old host change, without display), then restart.
7. **Check through the real path**: the application answers and reads its data.

**Rolling back a database**: put the old address back and restart the consumer; the old instance kept its data, frozen at the moment the consumer stopped.

**Order followed**: applications first (an outage of about two minutes each), then the workflow engine (no execution running), then the model router (with the memory schema and the human-approvals database, under their new roles), and **the identity provider last** (stopped through its CR, `instances: 0`, then restarted with the new address).

### After the migration

- The old instance goes to **0 replicas**, with a full final backup; it stays in place for **7 days** as a fallback.
- Then the administrator deletes: the old instance's Deployment, Service, PVC, PV, Secret and network rules, the node directory, the applications' egress rules to the old instance, intermediate backups. The final backup is kept 30 more days.

## Lessons

- **Check egress as much as ingress.** An application went into `CrashLoopBackOff` (`PoolTimeout`) when switched: the new instance's ingress was ready, but the application's **egress** rule only opened the old one. Hence step 0 and the real TCP connection. Fixed forward (egress widened), without loss: the application had written nothing.
- **"Tested" only covers what was tested**: migrations passed on 15, writes did not.
- **A Secret name is a DNS name**: no `_`. A loop that created the role before the Secret lost a password; the order is now Secret, then role.

## Next version upgrades

PG 18 is maintained until 2030. Chosen method: **`pg_upgrade --link`** in place, through the next version's image (`POSTGRESQL_UPGRADE=hardlink`), which ships the previous version's binaries: a few minutes of outage, whatever the size. The only fallback is the full backup taken just before. Compatibility (identity provider, workflow engine, model router, application drivers) and extensions are checked first.
