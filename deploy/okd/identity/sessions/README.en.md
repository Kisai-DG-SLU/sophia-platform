# Server-side oauth2-proxy sessions (Valkey)

The applications protected by oauth2-proxy (the chat and the household's other web applications) store their sessions in a **Valkey reserved for sessions**, next to Keycloak. The browser cookie only carries a ticket of about a hundred bytes. In service for every application behind oauth2-proxy.

## Why

With cookie storage, a session larger than 4,000 bytes is split into chunks (`<cookie>_0`, `<cookie>_1`…). oauth2-proxy (v7.15.5) first reads a **whole** cookie of the same name, and saving chunks does not delete it: an old session keeps being read on every request, next to the new chunks. The `Cookie` header then exceeds the limit of the web server behind oauth2-proxy (8 KB for nginx) and the request fails with a 400, on a device that keeps an old session. The upstream fix is still open.

With server-side storage, the session lives in Valkey, encrypted (AES) with a secret specific to the ticket, which only exists in the browser cookie: without the cookie, what Valkey keeps on disk is unreadable.

## Choices

| Choice | Value | Reason |
|---|---|---|
| Placement | identity namespace, next to Keycloak | the session is part of authentication; the oauth2-proxies already reach this namespace |
| Sharing | one instance for every application, **one ACL user per application** | no cross-reading; one instance per application would mean as many pods and volumes for a few MB |
| Key isolation | each user only sees its own cookie's keys (`~<cookie>-*`) | the pattern covers the sessions (`<cookie>-<ticket>`) and the refresh lock (`<cookie>-<ticket>.lock`), without touching another application's keys |
| Commands | oauth2-proxy's only: `GET`, `SET`, `DEL`, `PING`, `EXISTS`, `EVALSHA` and `EVAL` (refresh lock through Lua scripts), connection (`HELLO`, `AUTH`, `CLIENT SETINFO`) | read in the code of oauth2-proxy, its lock and its Redis client; a real test against a local fake logged no refusal |
| Use | sessions only | a cache may evict keys, a session must never be evicted; any other need gets its own instance |
| Eviction | `maxmemory 64mb`, `noeviction` | when full, Valkey refuses writes (sign-in fails) rather than evicting a session; a session weighs about 8.6 KB |
| Persistence | AOF, `appendfsync everysec`, no snapshot, small local volume | a restart signs nobody out; a node failure loses at most one second of writes |
| Passwords | one per application, in the application's namespace; the ACL file only holds their **SHA-256 digests** (`acl.sh`) | a pod cannot read a Secret from another namespace; no clear-text password on the Valkey side |
| `default` user | disabled | without a password, no command |
| Monitoring | `controle` user: `PING`, `INFO`, `DBSIZE`, no key | the administrator checks memory, persistence and the number of sessions without being able to read a session |
| Network | ingress only from the named applications' pods, on 6379; **no egress** | Valkey reaches nothing, neither DNS nor API |
| Priority | the chat's | the chat depends on it for every request, as on Keycloak |

## Files

| File | Content |
|---|---|
| `01-volume.yaml` | local PV and PVC bound to each other (no other PVC can take it) |
| `02-valkey.yaml` | ServiceAccount without token, Deployment (`Recreate`, image pinned by digest, ACL read from a Secret), Service |
| `03-network.yaml` | ingress limited to the applications' pods, empty egress |
| `acl.sh` | builds the ACL file Secret from the passwords' digests; refuses a missing Secret, a password shorter than 32 characters, a file without `user default reset off` |

## Application side (oauth2-proxy)

```
--session-store-type=redis
--redis-connection-url=redis://valkey-sessions.sophia-identity.svc.cluster.local:6379/0
--redis-username=<application user>
```

Password through the `OAUTH2_PROXY_REDIS_PASSWORD` variable, as a `secretKeyRef` on the `<application>-sessions` Secret (key `password`); network egress to the `app: valkey-sessions` pods of the identity namespace, TCP 6379. Full example: [chat interface](../../apps/chat-interface/sophia-interface.yaml).

**Transition**: switching signs everyone out once, but the old cookie chunks stay in browsers until they expire. The header limit of every server behind oauth2-proxy is therefore raised to **32 KB**: nginx `large_client_header_buffers 4 32k`; uvicorn `--h11-max-incomplete-event-size 32768`. **Pitfall**: h11, uvicorn's HTTP server, caps at 16 KB by default, lower than the OKD router (about 24 KB of headers); nginx is not the only one to raise.

## Procedure (administrator)

**No secret in a terminal variable**: each password is generated then written straight into its Secret through a pipe, never displayed. Every `oc apply` first runs as a dry run (`--dry-run=server`).

1. **On the node**: `sudo mkdir -p` the `${SESSIONS_MOUNT_POINT}` directory (for instance `/var/lib/sophia/valkey-sessions`), then `sudo chcon -t container_file_t` on that directory.
2. **Passwords** (monitoring, then one application):
   ```bash
   openssl rand -hex 32 | tr -d '\n' | oc -n sophia-identity create secret generic valkey-sessions-controle --from-file=password=/dev/stdin
   openssl rand -hex 32 | tr -d '\n' | oc -n sophia-interface create secret generic sophia-interface-sessions --from-file=password=/dev/stdin
   ```
3. **ACL file**: `bash deploy/okd/identity/sessions/acl.sh` (review, digests only), `--a-blanc` (dry run), then `--appliquer` (apply).
4. **Volume, Valkey, network**: `01-volume.yaml` (variables `${NODE_NAME}`, the node carrying the volume, `oc get nodes`, for instance `node-0`, and `${SESSIONS_MOUNT_POINT}`, the directory from step 1; `envsubst '${NODE_NAME} ${SESSIONS_MOUNT_POINT}' < 01-volume.yaml | oc apply -f -`), `02-valkey.yaml`, `03-network.yaml`.
5. **Checks**: without a password, `valkey-cli ping` is refused (`NOAUTH`); with `controle` (password piped into the pod), `aof_enabled:1`, `maxmemory_policy:noeviction`, and `GET` refused (`NOPERM`).
6. Then each application switches to `--session-store-type=redis`, with its network egress; `DBSIZE` grows with each sign-in.

## Adding an application

1. Create its `<application>-sessions` Secret in its namespace (step 2).
2. Add its line to `acl.sh` and its entry to `03-network.yaml` (templates in comments).
3. `acl.sh --a-blanc` then `--appliquer`; `03-network.yaml` as a dry run then for real.
4. **At a quiet time**: `oc -n sophia-identity rollout restart deploy/valkey-sessions`. Valkey only reads the ACL file at startup: no user has the `ACL LOAD` right, on purpose. Sessions survive (AOF); applications already connected return errors for a few seconds.
5. The application switches to `--session-store-type=redis`, with the raised header limit.

## Known limits

- No TLS between oauth2-proxy and Valkey, as for PostgreSQL: the password and the encrypted sessions travel in clear on the pod network, on a single node.
- A single pod: while Valkey restarts, the connected applications return errors for a few seconds.
- No backup: losing the AOF file means everyone signs in again.
