# Office suite — Files and Collabora (`sophia-workspace`); persistent chat and video calls

The reference installation's recipe for the [Office](../../../docs/modules/bureautique/documentation.en.md) module: La Suite Drive ("Files", 0.25.3) and Collabora Online (CODE 26.04), in a dedicated namespace. The choices and their reasons are in the module documentation; here, the components, prerequisites, Secrets and procedure. The reference installation's manifests are not published: they follow Drive's upstream manifests, with the settings below, rendered by Kustomize.

Status: in service; this recipe is a procedure, without the reference installation's manifests; detailed acceptance testing (second account, shares, reading from the chat) still to do. Files and Collabora can be displayed in the interface's cockpit: in service, in acceptance testing ([Display in the cockpit](#display-in-the-cockpit)).

The persistent chat and video calls of the [Communication module](../../../docs/modules/communication/documentation.en.md), installed by the same project in two other namespaces, have their recipe at the end of this page: [Persistent chat and video calls](#persistent-chat-and-video-calls).

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
- **Cockpit**: `fichiers-nginx` and Collabora settings for display in the chat only, at the end of this page.

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

## Persistent chat and video calls

Recipe of the [Communication module](../../../docs/modules/communication/documentation.en.md): Matrix (Synapse 1.163.2, MAS, Element Web, ntfy) in `sophia-messagerie`, Jitsi Meet (`stable-11248-2`: web, Prosody, Jicofo, JVB) and an OIDC → token adapter in `sophia-visio`. As for the office suite, this is a procedure, without the reference installation's manifests; the choices and their reasons are in the module documentation.

Status: **in service, in acceptance testing**: chat and video calls installed and checked through the real path (sign-in, room without a padlock, video adapter); tests with the household's devices (first message, multi-party call, guest refusal, child account, nftables rule counter) at the acceptance step. Video calls go **through the browser only** (household decision): Jitsi's mobile app is no longer used.

### Components

| Namespace | Object | Role |
|---|---|---|
| `sophia-messagerie` | `synapse` | Matrix server, federation off, end-to-end encryption off by default (`extra_well_known_client_content` → `io.element.e2ee: {default: false}`), media of 50 MB at most on the dedicated volume |
| | `mas` | Matrix authentication service, OIDC client of the identity provider; the Matrix API's login, logout and refresh paths are routed to it on the server's name |
| | `element` | web client, with no external address in its configuration |
| | `ntfy` | UnifiedPush notifications, without text or sender |
| `sophia-visio` | `web`, `prosody`, `jicofo`, `jvb` | Jitsi Meet with token authentication; Jicofo probed through `exec` (its health API only listens on `127.0.0.1`) |
| | `adaptateur` | OIDC sign-in, then a signed 600 s token for a single room; image built in the cluster from the forge, pinned by digest |
| | `jvb-media` | `ClusterIP` Service with `externalIPs: [${VPN_IP}]`, port `${JVB_UDP_PORT}/UDP`; **no NodePort** |

Jitsi settings to remember: `ENABLE_THIRD_PARTY_REQUESTS=false`, `DISABLE_DEEP_LINKING` (no "Join in the app" page: the call stays in the browser), peer-to-peer off, `JVB_ADVERTISE_PRIVATE_CANDIDATES=false`, `ENABLE_COLIBRI_WEBSOCKET=0` (bridge channel over SCTP), `S6_YES_I_WANT_A_WORLD_WRITABLE_RUN_BECAUSE_KUBERNETES=1` for the arbitrary UID, with neither privilege nor `anyuid`.

### Prerequisites

| # | Object | Recipe |
|---|---|---|
| 0 | **Base** of each namespace, applied first: Namespace, `ResourceQuota`, `LimitRange`, EgressFirewall, `default-deny`, `allow-dns`; no agent RoleBinding | below |
| 1 | The office suite's class for every pod, the voice class for JVB | [`../cluster/`](../cluster/README.en.md) |
| 2 | `synapse` (`C` collation, from `template0`) and `mas` databases, one owner role each; PostgreSQL ingress from `sophia-messagerie` | [`../core/postgres18/`](../core/postgres18/README.en.md) |
| 3 | `matrix` and `jitsi` OIDC clients, access client role, flow refusing the guests group | [`../identity/`](../identity/README.en.md) |
| 4 | Dedicated logical volume for Synapse media (10 GiB), `Retain` PV | [`../../stockage-persistant.en.md`](../../stockage-persistant.en.md) |
| 5 | UDP rule for the media bridge in the VPN's nftables table | [`../host/wireguard/`](../host/wireguard/README.en.md#6-video-call-media) |

### Network

- **Ingress**: from the router for pages and APIs; JVB from `${VPN_NETWORK}` only, over UDP on `${JVB_UDP_PORT}`.
- **Synapse ingress from the interface pod**, on its HTTP port, for the unread-summary route (with the matching egress on the interface side).
- **Egress**: Synapse to MAS and ntfy, and to the identity provider's public name, on 443 through the router, for the realm's public keys (summary module; the existing egress covers it); MAS and the adapter to the identity provider's public name, on 443, through the router; JVB over UDP to `${VPN_NETWORK}` only (replies to devices), in its NetworkPolicy **and** in the base's EgressFirewall, before the deny rule.
- The media bridge uses no NodePort: a NodePort would be reachable from the local network, and the pod would only see OVN-Kubernetes' join address there. The `externalIP` on the VPN address, like the forge, is reachable through the VPN only and keeps the client's real address.

### Variables

| Variable | Role | Example |
|---|---|---|
| `${MATRIX_HOST}` | Matrix server name (API and `.well-known`) | `matrix.apps.example.org` |
| `${MAS_HOST}` | authentication service name | `account.apps.example.org` |
| `${ELEMENT_HOST}` | web client name | `chat.apps.example.org` |
| `${NTFY_HOST}` | notification relay name | `ntfy.apps.example.org` |
| `${VISIO_HOST}` | video service name (pages and adapter) | `meet.apps.example.org` |
| `${VPN_IP}`, `${VPN_NETWORK}` | the node's VPN address, VPN network ([`../host/wireguard/`](../host/wireguard/README.en.md)) | `192.0.2.1`, `192.0.2.0/24` |
| `${JVB_UDP_PORT}` | media UDP port | a free port of the node |

### Secrets (content, never a value)

| Secret | Content |
|---|---|
| `sophia-messagerie/synapse` | database password, secret shared with MAS, Synapse's internal secrets |
| `sophia-messagerie/mas` | database password, OIDC client secret, encryption and signing keys (one RSA, one EC), secret shared with Synapse |
| `sophia-visio/adaptateur-visio` | OIDC client secret (`client-secret` key) |
| `sophia-visio/jitsi` | internal passwords of Jitsi's components, room token signing secret (`jwt-secret` key) |

Each value is generated on the spot and written through a pipe, without a trailing newline; the secret shared between Synapse and MAS is copied from Secret to Secret. Checks: key names, lengths, and **equality of both copies by digest**, never by display. Synapse reads its secrets through file paths and its database password through `PGPASSWORD` (libpq ignores a password file readable by the group, which mounted Secrets are); MAS reads each secret from a file.

### Procedure

1. **Bases** (step 0): `oc diff`, `--dry-run=server`, `oc apply`; field-by-field check; no RoleBinding beyond those created by OKD.
2. **Prerequisites 1 to 5** in place; if one is missing: stop.
3. **Secrets**, written through a pipe, with no variable and nothing displayed (above).
4. **Chat**: `oc diff -k`, server dry-run, `oc apply -k`, wait for the rollouts. Checks through the real path: `.well-known` with `io.element.e2ee` set to `false`, the API's `versions`, sign-in flows served by MAS, MAS OIDC discovery, ntfy, Element. Sign-in of an admitted account (two MAS pages the first time), refusal of a guest, room created without a padlock.
5. **Video**: build the adapter, then `oc apply -k`. Checks: pods ready; JVB advertises the VPN address and is joined by Jicofo; `config.js` without third-party requests, peer-to-peer off; adapter healthy; a test with at least two devices, guest refused, **the nftables rule's counter increasing**.

### Rollback

`oc delete -k` on the chat or the video service: the database, the media volume and the Secrets remain. Bases, databases, OIDC clients and the nftables rule: removed by the administrator, according to their recipes.

## Display in the cockpit

The [interface's cockpit](../apps/chat-interface/README.en.md) displays applications in a frame, in the centre. Each application must accept being displayed **by the chat only**, and signal it. Status: in service, in acceptance testing (actual display on each device at the acceptance step).

| Application | Setting |
|---|---|
| Messages (Element) | the image's nginx template copied into a ConfigMap: `frame-ancestors 'self' ${CHAT_ORIGIN}`, repeated in every `location` (an `add_header` in a location cancels those of the upper level); `sub_filter` injecting `/sophia-cockpit/pret.js`. Without this header, Element could be displayed by any page (clickjacking). The MAS sign-in page stays refused in a frame: "Sign in again" opens Element in a tab |
| Video (Jitsi) | `CSP_HEADER` with `frame-ancestors 'self' ${CHAT_ORIGIN}`, `DISABLE_DEEP_LINKING`, `custom-config.js` (ConfigMap) loading `pret.js`; camera and microphone allowed by the frame's `allow` attribute; only `web` restarts |
| Desk (Files) | in `fichiers-nginx`, **`location /` only**: `proxy_hide_header X-Frame-Options`, then `frame-ancestors 'self' ${CHAT_ORIGIN}`; the API, administration and media keep their refusal. `Accept-Encoding` cleared towards the frontend, so that `sub_filter` can inject `pret.js` |
| Collabora | `content_security_policy` variable, which **adds** `${CHAT_ORIGIN}` to the existing list (Files and the WOPI service): `frame-ancestors` checks the whole chain of frames, and the editor nested in Files is nested in the chat too. Neither `net.frame_ancestors` (deprecated) nor `extra_params` (split on spaces) |

**`sophia.pret` signal**: a small script, `pret.js`, served by each application, posts `{type: "sophia.pret", module: "<identifier>"}` to the chat's origin only, and only inside a frame, when the application is ready (Element with a session, Files when `/api/v1.0/users/me/` answers 200). The identifier must be exactly the module's identifier in the cockpit (`messages`, `visio`, `bureau`): any other is ignored, and the cockpit offers its fallback after 8 s.

**Document opened in the cockpit** (in service, in acceptance testing): Files opens the editor with a `window.open` to `/wopi/<id>`, hence in a new tab. In the cockpit, `pret.js` replaces that single call, when the address is exactly `/wopi/<uuid>` on the same origin, with no parameter or fragment, and the direct parent is the chat: it posts `{type: "sophia.ouvrir", module: "bureau", chemin: "/wopi/<uuid>"}` to the chat, which opens the document in its own frame, with a "← Files" button. Any other address, or any other parent, keeps the tab. Files has no "Close" button: going back goes through the cockpit.

**"What's new?" summaries**: these applications have no oauth2-proxy; their summary route verifies the token relayed by the interface itself. Files: `GET /api/resume` in the MCP tool ([`../skills/`](../skills/README.en.md)). Messages: a Python module mounted in Synapse ([Communication module](../../../docs/modules/communication/documentation.en.md)). In service, checked without a token; the call from the interface is planned.

| Variable | Role | Example |
|---|---|---|
| `${CHAT_ORIGIN}` | origin of the chat interface, the only page allowed to display these applications | `https://sophia.example.org` |

### Procedure (cockpit)

Each step is independent, with `oc diff`, `--dry-run=server`, `oc apply`, and its backup:

1. **Files and Collabora** (`fichiers-nginx`, Collabora): **Collabora restarts and closes open documents**; apply when nobody is editing. Expected: on Files, `frame-ancestors 'self' ${CHAT_ORIGIN}` and no more `X-Frame-Options`; `pret.js` served (200); Collabora's CSP keeps its list and adds the chat.
2. **Element and Synapse's summary module**, **together**: they share the chat's Kustomize rendering. Synapse restarts (about a minute without chat). Expected: Synapse logs that the module is loaded, the route answers 401 without a token; `pret.js` served by Element; MAS and ntfy unchanged.
3. **Video**: only `web` restarts. Expected: the CSP served by the video page, and the `config.js` setting present.
4. **Files summary**: build of the MCP tool, import check inside the built image, new digest committed then applied. Expected: pod ready without restarts, `/health` 200, `/api/resume` 401 without a token.
5. **Opening a document**: the new `pret.js` in the `fichiers-nginx` ConfigMap, **without a restart** (mounted as a directory, re-read by nginx).

Then, on the interface side: the module switches to a frame through the `SOPHIA_MODULES_CADRE` list, and the interface's egress to Synapse is opened ([interface](../apps/chat-interface/README.en.md)).

Rollback: each object's backup, or the previous value; for the Synapse module, a single configuration value (`actif: false`).
