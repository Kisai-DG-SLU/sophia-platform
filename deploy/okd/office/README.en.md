# Office suite — Files and Collabora (`sophia-workspace`)

The reference installation's recipe for the [Office](../../../docs/modules/bureautique/documentation.en.md) module: La Suite Drive ("Files", 0.25.3) and Collabora Online (CODE 26.04), in a dedicated namespace. The choices and their reasons are in the module documentation; here, the components, prerequisites, Secrets and procedure. The reference installation's manifests are not published: they follow Drive's upstream manifests, with the settings below, rendered by Kustomize.

Status: in service; this recipe is a procedure, without the reference installation's manifests; detailed acceptance testing (second account, shares, reading from the chat) still to do.

## Components

| Object | Role |
|---|---|
| `valkey` | Files' task queue and cache, no persistence; password-protected |
| `fichiers-backend`, `-worker`, `-beat` | Files' Django API, background tasks, scheduler |
| `fichiers-frontend` | web interface |
| `fichiers-nginx` | single entry point: Route `${FICHIERS_HOST}`, media through an authorization subrequest, Collabora's interface, internal WOPI port in TLS; a second server on `${API_INTERNAL_PORT}` for the MCP tool (overlay, below) |
| `collabora` | editor, no Linux capability, Landlock isolation, WOPI proof key mounted from a Secret |
| service-ca CA | injected to verify internal TLS: WOPI (Collabora → Files) and the S3 API |
| NetworkPolicies | rules internal to the namespace; Collabora only egresses to the WOPI port and DNS |
| Jobs `migrate`, `configure-wopi` | migrations, then registering Collabora with Files; created with `oc create`, outside Kustomize |

Flow: browser → edge Route → `fichiers-nginx` → interface, API, S3 (media, after authorization by the API), Collabora. Upload: presigned PUT from the browser to `https://${S3_HOST}`. WOPI: Collabora → Service `fichiers-wopi` in TLS (service-ca certificate) → API. Scheme and host are kept all the way to the API, which checks Collabora's signature on the exact URL.

## Prerequisites

| # | Object | Recipe |
|---|---|---|
| 1 | PriorityClass `sophia-workspace-low` (50,000, no preemption) | [`../cluster/`](../cluster/README.en.md) |
| 2 | Namespace, `ResourceQuota` (enough for the Jobs and the extra pod of a rolling update), `LimitRange` | [`../cluster/`](../cluster/README.en.md) |
| 3 | Versioned `fichiers` bucket, CORS for `https://${FICHIERS_HOST}`, its own S3 identity, 30-day trash | [`../storage/`](../storage/README.en.md) |
| 4 | Role and database `fichiers` in PostgreSQL **18** (≥ 16 required), extensions `ltree`, `pg_trgm`, `fuzzystrmatch`, `unaccent` created by the role itself (all "trusted"); database ingress from the `fichiers-*` pods only | [`../core/`](../core/README.en.md) |
| 5 | Confidential OIDC client `fichiers`: standard flow, PKCE S256, redirect `https://${FICHIERS_HOST}/api/v1.0/callback/`, `groups` mapper; identity provider ingress from the API and the worker | [`../identity/`](../identity/README.en.md) |

## Variables

| Variable | Role | Example |
|---|---|---|
| `${FICHIERS_HOST}` | DNS name of Files, resolved to the VPN address; its origin is the `${FILES_ORIGIN}` of [`../storage/`](../storage/README.en.md) | `files.apps.example.org` |
| `${S3_HOST}` | S3 Route, for presigned uploads (same variable as [`../storage/`](../storage/README.en.md)) | `s3.apps.example.org` |
| `${S3_INTERNAL_URL}` | internal S3 API, in service-ca TLS (internal address of [`../storage/`](../storage/README.en.md)) | `https://s3.sophia-storage.svc:9000` |
| `${API_INTERNAL_PORT}` | internal port reserved for the API for relayed tokens | a free port of the pod, distinct from the public port |

## Secrets (names and keys, never a value)

| Secret | Keys |
|---|---|
| `valkey` | `password` |
| `fichiers` | `DJANGO_SECRET_KEY`, `OIDC_RP_CLIENT_SECRET`, `DB_PASSWORD`, `AWS_S3_ACCESS_KEY_ID`, `AWS_S3_SECRET_ACCESS_KEY`, `REDIS_URL`, `DJANGO_CELERY_BROKER_URL` |
| `collabora-proof-key` | `proof_key` (RSA key, generated and passed through a pipe) |
| `fichiers-wopi-tls` | created by OKD's service-ca (Service annotation) |

Values are produced on the spot (role password, OIDC client secret, S3 keys), kept in shell variables without being displayed, and passed through standard input (`printf … | oc create secret generic … --from-env-file=/dev/stdin`), **in a single terminal**. Only lengths are displayed for checking.

## Notable settings

- **Collabora**: `always_save_on_exit=true`, `idle_timeout_secs=1800`, `max_concurrency=2`, `cleanup.limit_dirty_mem_mb=1024`; probe on `/`.
- **nginx**: `X-Forwarded-*` headers cleared towards S3 (otherwise the signature is checked against the public host); `location ~ ^/cool` after the WebSocket regex; a log format that masks WOPI tokens. The internal server copies the public server's `proxy_set_header` lines, `X-Forwarded-Proto: https` included (otherwise the API, in production, answers 301 to https).
- **Pods**: `restricted-v2`, class `sophia-workspace-low`, images pinned by digest.

## "External API" overlay (for the "files" MCP tool)

Once the tool is in place, Files is **always applied through the overlay**, never through the base alone (which would remove the internal port, the API settings and the introspection secret, and the tool would go down):

- a second nginx server on `${API_INTERNAL_PORT}`, serving only `GET` on the external API and, for content reading, a media location authorized by that API's `media_auth` action; the public port answers 404 on that path; no Route;
- API side: OIDC resource server on, introspection by the `fichiers` client, allowed audience = the tool's client, read-only `EXTERNAL_API` allow-list (`list`, `retrieve`, `children`, `search`, `breadcrumb`, `media_auth`; `users.get_me`);
- a NetworkPolicy that opens that port to the tool's pod only.

Tool and identity-provider side: [`../skills/`](../skills/README.en.md) and [Identity Relay](../../../docs/concepts/12-relais-identite.en.md).

## Procedure

1. **Prerequisites in place**: PriorityClass, namespace, quota, S3 Service, bucket versioning and CORS, database and identity-provider ingress. If anything is missing: stop.
2. **Read the rendering**: `oc kustomize`, `oc diff -k`, `oc apply -k … --dry-run=server`. Expected: only creations in the namespace, no quota, SCC or PriorityClass refusal.
3. **Database, OIDC client and Secrets**, in the same terminal (above).
4. **Apply**: `oc apply -k`; Valkey, Collabora and nginx ready; the API restarts until the database is migrated.
5. **Jobs**: `migrate`, then `configure-wopi`; every pod `Running`.
6. **Checks**: SCC `restricted-v2` and priority class of each pod; Landlock active in Collabora's log; nginx started without error; quota under its ceilings; no more proof-key error.
7. **Real path**, through the VPN: SSO login; creating a folder; uploading and previewing an image; a document opened in Collabora from two browsers; new version visible in the bucket; with a second account, the first account's items are invisible (neither list nor direct address), then readable after a "Viewer" share.

## Rollback

`oc delete -k` and deleting the Jobs: the data stays (files in the versioned bucket, schema in the database), so do the Secrets. A single component: `oc scale … --replicas=0`. Database, role and OIDC client: deletions by the administrator, following their recipes.
