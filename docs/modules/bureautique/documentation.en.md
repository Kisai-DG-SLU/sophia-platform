# Office Module — documentation

## What the module does

- **Store and share**: each person has their own file space, with folders, previews and version history. Everything is **private by default**; a share (viewer or editor) takes an explicit action, and a link stays "restricted" until it is opened up.
- **Edit**: office documents (text, spreadsheet, presentation, OpenDocument and Microsoft formats) open in Collabora, with several people at once. Files opens the editor in **a new tab**; in the interface's dashboard, the document opens in its own frame (below).
- **From the chat**: Sophia finds one of the person's files by its name, then offers to open it (in Collabora for an editable document, in Files otherwise) and to view the folder that contains it. She can also read and summarize a document's content, with a local model only.

## Architecture

```
browser (VPN) ──► ingress router ──► Files nginx ──► front end, API, Collabora
                                         │
                                         ├──► common S3 (media, after authorization by the API)
                                         └──► reserved internal port, GET only ◄── "files" MCP tool

Files API ──► shared PostgreSQL 18, identity provider (OIDC), Valkey (task queue, cache)
Collabora ──► Files WOPI API (internal TLS), DNS; nothing else
```

| Item | Choice | Reason |
|---|---|---|
| Namespace | dedicated (`sophia-workspace`), its own quota and LimitRange | isolate the office suite from chat and agents; the quota covers the Jobs and the extra pod of a rolling update |
| Priority | class `sophia-workspace-low`, no preemption | below chat, voice and agents; above images and development ([priorities](../../../deploy/okd/cluster/README.en.md)) |
| Database | shared PostgreSQL 18, its own role and database, no superuser | Drive stores its items in `ltree` paths whose labels contain hyphens, refused before PostgreSQL 16: creating a folder failed on 15 |
| Files | common S3 ([`deploy/okd/storage/`](../../../deploy/okd/storage/README.en.md)), versioned bucket, **30-day trash** for replaced versions | an overwritten or deleted version can be recovered for 30 days, then the space is freed |
| Upload | presigned URL, from the browser to S3 | the file does not go through the API |
| Media | served by nginx after an authorization subrequest to the API | permissions stay those of Files |
| Identity | confidential OIDC client, standard flow with PKCE | single sign-on; no local account |
| Isolation | pods in `restricted-v2`, no capabilities; Collabora isolates documents with **Landlock** | Collabora gets no Linux capability; Landlock is checked active in its log |
| Collabora | `always_save_on_exit=true`, `idle_timeout_secs=1800`, `max_concurrency=2`, `cleanup.limit_dirty_mem_mb=1024`; autosave at 30 s and 5 min; probe on `/` | nothing is lost on close; a forgotten document frees memory; at most two conversions in parallel on a shared node |
| WOPI proof | an RSA proof key in a mounted Secret | without it, Collabora does not sign its calls and Files does not check their origin |
| Images | pinned by digest | an update is a decision |

### Files nginx: three fixes from the go-live

| Finding | Cause | Fix |
|---|---|---|
| Image preview in 403 | nginx forwarded to S3 the `X-Forwarded-*` headers set by the router; SeaweedFS checked the signature against the public host, not the internal host signed by the API | those headers are cleared in the media locations |
| Editor: "failed to establish socket connection" | the `^~ /cool` location stopped the search before the WebSocket regex; Collabora received a GET without `Upgrade` | `location ~ ^/cool` after the `/ws` regex, as in Collabora's reference configuration; both WebSocket URL forms go through |
| WOPI tokens in the access log | default log format | a format that masks the `/cool/` path, drops the query of WOPI calls and masks a Referer that contains a token |

Lesson: a relay is tested with real requests against fake services, headers included, not only with `nginx -t`.

## In the dashboard

The [interface's dashboard](../../../deploy/okd/apps/chat-interface/README.en.md) displays Files in the centre, under the name "Desk". Status: in service, in acceptance testing on each device.

- **Displayable by the chat only**: `frame-ancestors 'self'` plus the chat's origin on Files pages; the API, administration and media keep refusing to be framed. Collabora adds the chat's origin to its own list: `frame-ancestors` checks the whole chain of frames, and the editor is nested. Settings: [`deploy/okd/office/`](../../../deploy/okd/office/README.en.md#display-in-the-dashboard).
- **`sophia.pret` signal**: Files tells the dashboard it is ready when the person's session answers; without a signal after 8 s, the dashboard offers "Open separately" and "Sign in again".
- **A document opens in the dashboard** (in service, in acceptance testing): the small script injected into Files replaces the single tab opening towards the editor (`/wopi/<uuid>`, same origin, no parameter) with a `sophia.ouvrir` message to the chat; the chat checks the source (the Desk frame), the origin and the closed form of the path, rebuilds the address on the module's origin, and opens the document in its own frame, with a "← Files" button. The document counts towards the limit of two live frames.
- **Older tablet**: Files requires a recent engine. For a child, the "Desk" tile opens their [browser workstation](#per-child-browser-workstation); for other accounts, the dashboard shows an explanation instead of the frame.
- **"What's new?" summary**: the MCP tool serves `GET /api/resume` (files shared with the person and modified in the last 14 days), with the same relayed token as its tools. Called by the interface: in service, verified.

### "Sophia, open document X"

In service, in acceptance testing.

- **Analysis by the model**: the "files" intent, with the "open" action and the search terms.
- **Decision by rules**: the server calls `chercher_fichiers` with the person's token and chooses according to the number of results; **the document's identifier comes from the tool's result, never from the model**, and no search word enters an address.
- **Execution**: an event from the server to the dashboard, with a closed-form path (identifier as a lowercase UUID), checked on the server and then in the browser.
- One result: the document (on a phone, its **preview**); several: a clickable list in the dashboard, or the common folder; none: "My files". Drive has no search address and no "all files" view: the dashboard cannot make it display a result list.

### Sophia writes into the open document

**In service, verified on the real path** (direct insertion and acknowledgement); cursor detection, corrected, is to be checked again. It is requested from Sophia's conversation or from the Office's "Ask Sophia" panel.

Through Collabora's PostMessage API, relayed by the script injected into the editor page: plain-text insertion, undoable with Ctrl+Z, refused if the document is read-only. Writing through Drive's API is ruled out: it would conflict with the editing session. Household decision: **Sophia inserts directly, without a click**; an "Insert" button remains to insert again. Deterministic checks, since the model's output leaves the conversation:

- the relay announces the editor (`sophia.editeur_pret`) when an editable document is loaded; only then does the interface offer the intent to write or rephrase;
- insertion only if the analysis asks for it **and** a document is open; only the reply's visible text, never from a reply reloaded from history;
- plain text, sanitised on both sides and capped at 20,000 characters;
- the **selection** (to rephrase) is read for a local model only;
- origins and frame checked at every hop, in both directions;
- **a closed list of relayed messages** (insert, read the selection, editor announcement, named errors), never a UNO command or a script received from the interface;
- **position**: at the cursor if the person clicked or typed in the text, otherwise at the end of the document, through a fixed command of the relay; the acknowledgement says where the text went;
- word processing only in the first version (named error for another document type);
- a test of the editor's internal selectors, to rerun with each new Collabora image.

## Per-child browser workstation

**In service, in acceptance testing.** The household's older tablets cannot run Files and Collabora (engine too old). For the children, the dashboard's "Desk" tile therefore shows a **browser workstation**: a recent browser running in the cluster, opened on Files, of which the tablet only receives the picture (VNC in the page, through noVNC). One workstation per child, with its own browser profile; adults and guests keep Files in the centre of the dashboard.

```
tablet (dashboard, "Desk" frame) ──► router ──► gatekeeper: nginx ─► oauth2-proxy (session, children's group)
                                                  │      └─► portier.py (person → workstation table, wake-up, shutdown)
                                                  └──► the child's workstation (noVNC ─► kiosk browser ─► Files)
```

| Element | Choice | Reason |
|---|---|---|
| Namespace | dedicated (`sophia-postes`), quota, default deny, EgressFirewall | workstations are full browsers: isolate them from the rest |
| Workstation | an image pinned by digest: Chromium in kiosk mode on Files, virtual X server, noVNC and websockify; one Deployment per child (`poste-a`, `poste-b`, never a first name), **without a replica count**: the gatekeeper switches it on and off; browser profile on a `Retain` local volume; no service-account token mounted | each child finds their tabs and session again; nothing runs when nobody uses it |
| Gatekeeper | a single address for everyone, no identifier in the URL; a three-container pod: nginx, oauth2-proxy (pinned by digest), and a small Python program (standard library, fixed rules, no model) | the target is decided server-side, never from the request |
| Routing | two-stage nginx: the first checks the session and sets the person's identifier (header **overwritten**, even when empty, every variant ignored); the second, on loopback, asks the gatekeeper for the target **on every request, WebSocket included** | a child cannot aim at another child's workstation |
| Table | person → workstation, by the identity provider's **technical identifier** (never a name), in a ConfigMap set by the administrator; forms checked, a malformed table refused at startup | no personal data in the cluster |
| Access | reserved to the children's group (`--allowed-group`), then to the table: an adult or a guest is refused twice (refusal page, then 403) | the workstation is a tool for the children |
| Wake-up | on the Desk's first request, the gatekeeper scales the workstation to 1 replica and serves a waiting page; the page declares failure at 55 s, before the dashboard's 60 s timeout, so that there is a single trigger; "Retry" starts again | a workstation that is off costs nothing |
| Idle shutdown | after **30 minutes without a connection** to the remote screen; the gatekeeper polls each workstation's state every 15 s; the noVNC client does not reconnect on its own (otherwise the workstation would never fall asleep) | give memory and CPU back to the rest of the platform |
| Gatekeeper rights | a Role limited to the workstations' Deployments (`get`) and their `scale` subresource (`get`, `patch`), by name; token mounted in the gatekeeper container only | switch on and off, nothing else |
| Signals to the dashboard | `sophia.poste` (`reveil`, `echec`, `veille`, `refuse`), `sophia.connexion_requise`, `sophia.pret`, to the dashboard's origin only and only inside a frame; the dashboard writes the texts itself ("Your desk is getting ready…", "has fallen asleep") | no text coming from the page is displayed |
| Retrieving a document | the workstation tells the gatekeeper which document is open; the dashboard offers to retrieve it, without waking a workstation that is off; sending and retrieving go through the "files" MCP tool | no download onto the tablet |
| Monitoring | gatekeeper metrics (workstation on, wake-up failures); alerts: 3 wake-up failures in 30 min, a failure lasting more than 10 min, missing metrics | a failing wake-up is visible |

**Isolation.** A workstation only accepts ingress from the gatekeeper, and only goes out to the router over HTTPS and to DNS: neither another workstation nor the gatekeeper. The gatekeeper only accepts the router, the chat pod and monitoring (the last two on its state port only); it only goes out to the workstations, the identity provider's pod and the cluster API. The chat reads the state of the person's workstation on a route that verifies the relayed token (its own audience and client, then userinfo; same identifier required). The review tried twelve attacks (forged identifier, doubled header, WebSocket to another child's workstation, modified or unsigned adult token, internal routes): all refused. **Known limit**: an already open WebSocket is not rechecked, for up to an hour; to cut it at once, switch the workstation off.

**Files session on wake-up.** The Files session in the workstation's browser does not last a night: on the next day's wake-up, the child landed on Files' "Sign in" page. Fix (workstation image rebuilt): the workstation's home goes through Files' **silent sign-in** (`prompt=none`), which resumes the identity provider session without a password, and otherwise falls back to Files' home page as before; for that session to last from one day to the next (30 days), the child ticks "Remember me" once on the workstation's sign-in page. Tab restoring is off: a single tab, the home page, instead of one more tab at each wake-up. Proven on the bench: three starts on the same profile, a single tab and the silent sign-in each time.

**Endless "Your desk is getting ready" veil.** The dashboard covers the Desk frame with a veil during wake-up, and lifts it on `sophia.pret`, or declares a failure after 60 s. A `reveil` signal received after falling asleep, a failure or a picture put the veil back **without re-arming the timer**: the veil stayed, while the desk was ready behind it. Fix: the timer is re-armed at each "getting ready"; at worst, the child sees "could not switch on" and "Try again". Observation traces, enabled by an address parameter, are used to record the states on a tablet.

**Stale session cleared.** On a tablet, another account's session cookie stayed in the browser: oauth2-proxy refused it, but the deletion it issued stayed in nginx's subrequest, and sign-in was asked for endlessly. Beyond 4 KB, the session is split into several cookies (`_0`, `_1`…), and nginx only returned the first deletion (it merges a subrequest's `Set-Cookie` headers into one, of which the browser only reads the first). Fix: the no-session page (on 401 only) itself clears the whole cookie and its chunks `_0` to `_3` (`Max-Age=0`, same attributes); a valid cookie is never touched.

**Pitfalls at go-live.**

- **The EgressFirewall cut off the cluster API**: the `kubernetes` Service ends at the node's address, on the API port; the NetworkPolicy allowed it, the namespace's EgressFirewall did not. The gatekeeper could neither read, nor switch on, nor switch off a workstation. Fix: a rule towards the control-plane nodes, on the API port, before the deny. The test bench had no EgressFirewall: cross-check NetworkPolicy **and** EgressFirewall when reviewing.
- **Another account's session left on the tablet** made the gatekeeper see an adult, refused: hence the clearing above, and the **module sign-out** by the dashboard (see the [interface](../../../deploy/okd/apps/chat-interface/README.en.md#dashboard)).

**Status**: in service; both children have their desk; real idle shutdowns observed; first cold wake-up measured: **3 s** until the workstation is ready, image already on the node, noVNC loading not counted; the Files sign-in and veil fixes are in service, to be checked on each tablet. Still to prove: retrieving a document, falling asleep then waking up on each tablet, and the real cost of display at scale 2. **Known limit**: the gatekeeper's refusal page (`sophia.poste` `refuse`) is not handled by the dashboard yet.

## Confidentiality

- **Each person their own files**: an item created by one person is invisible to the others, including through its direct address, until it is shared.
- **No per-person encryption**: files live in the installation's S3 and database. The system administrator can therefore read the raw data; confidentiality rests on the application's permissions, not on a key specific to each person.
- **Protected accounts** (children): they have a space like everyone else; from the chat, their documents' content goes only to the local model, like all their data.

## From the chat: the "files" MCP tool

A read-only MCP server ([`deploy/okd/skills/`](../../../deploy/okd/skills/README.en.md)), under the person's identity: the chat relays their token, the tool verifies it then exchanges it for a token issued to itself, and Files applies its own permissions. The full chain is described in [Identity Relay](../../concepts/12-relais-identite.en.md).

| Tool | What it returns | Status |
|---|---|---|
| `chercher_fichiers` | up to 10 items found **by name** (accent- and case-insensitive), with path, date, type, "editable"; no URL | in service |
| `details_fichier` | one item and its readable path | in service |
| `lire_fichier` | a document's text (odt, docx, ods, xlsx, pdf, txt, md, csv), bounded, flagged "sensitive content" | deployed, acceptance test pending |
| `GET /api/resume` route | summary for "What's new?": files shared with the person, modified in the last 14 days, 20 at most; same token and same audience as the tools; Files does not expose the sharing date | in service, checked without a token; call from the interface planned |

- **Dedicated API**: Files serves its API for relayed tokens on a **reserved internal port**, with no Route, **GET only**; the public port answers 404 on that path. Allowed actions are a read-only allow-list. Reading content goes through the same authorization as media, on that port.
- **Links built by the chat**: the tool returns no address; the chat composes "Open in Collabora" for an item that is editable **and** an office type (by extension **or** MIME type), "Open in Files" (the preview) for the others, and "View in Files" to the folder that contains the item when the person can read it.
- **Local-only content**: the chat calls `lire_fichier` only with a model on the list of local models, removes that content from any call to another model, and offers no tool after a read (see [Models by Role](../../concepts/13-modeles-par-role.en.md)).
- **No full-text search**: Drive does not index file contents without its search engine, which is not installed.

## Browsers

Drive and Collabora use ES2022 `static {}` blocks: at least **Safari 16.4** (or an equivalent browser) is required. On an older device, Files does not start, and no server-side fix is reasonable. The chat detects the engine with a small ES2022 script (not the User-Agent): on an engine that is too old, the buttons to Files become inactive text that says so, and the result list stays visible. In the dashboard, an explanation replaces the Desk frame.

## Planned

- **Unified mail** (decided, **postponed** behind the other projects): a local aggregator that gathers a person's existing mailboxes over IMAP (two-way sync), with sorting, anti-spam and a webmail behind SSO; no server exposed to the Internet. An **MCP tool** will let the model or a workflow search, read, file and draft, never send or delete permanently: sending stays validated by the person.
- **Persistent chat and video**: in service, in acceptance testing, in a separate module ([Communication](../communication/README.en.md)); Jitsi Meet replaced La Suite's Visio, and goes through the browser only. Starting a call from the chat remains planned.

## Lessons

- A database "already tested" by migrations is not tested for writes: the first folder creation revealed the PostgreSQL 16 requirement.
- Before switching a service to a new database, check its network **egress** as much as the database's ingress.
- A token can end up in a log through an unexpected path (access log, error log, a tool's HTTP client): each path gets checked.
- A minimal image may lack the time-zone database: check import and start-up **inside the base image itself**, and make the build fail rather than the pod ([`deploy/okd/skills/`](../../../deploy/okd/skills/README.en.md)).
- For an nginx `sub_filter` to inject a script, the upstream response must not be compressed: clear `Accept-Encoding` towards the frontend.
