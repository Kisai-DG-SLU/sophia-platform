# Office Module — documentation

## What the module does

- **Store and share**: each person has their own file space, with folders, previews and version history. Everything is **private by default**; a share (viewer or editor) takes an explicit action, and a link stays "restricted" until it is opened up.
- **Edit**: office documents (text, spreadsheet, presentation, OpenDocument and Microsoft formats) open in Collabora, inside the Files page, with several people at once.
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

- **Dedicated API**: Files serves its API for relayed tokens on a **reserved internal port**, with no Route, **GET only**; the public port answers 404 on that path. Allowed actions are a read-only allow-list. Reading content goes through the same authorization as media, on that port.
- **Links built by the chat**: the tool returns no address; the chat composes "Open in Collabora" for an item that is editable **and** an office type (by extension **or** MIME type), "Open in Files" (the preview) for the others, and "View in Files" to the folder that contains the item when the person can read it.
- **Local-only content**: the chat calls `lire_fichier` only with a model on the list of local models, removes that content from any call to another model, and offers no tool after a read (see [Models by Role](../../concepts/13-modeles-par-role.en.md)).
- **No full-text search**: Drive does not index file contents without its search engine, which is not installed.

## Browsers

Drive and Collabora use ES2022 `static {}` blocks: at least **Safari 16.4** (or an equivalent browser) is required. On an older device, Files does not start, and no server-side fix is reasonable. The chat detects the engine with a small ES2022 script (not the User-Agent): on an engine that is too old, the buttons to Files become inactive text that says so, and the result list stays visible.

## Planned

- **Unified mail** (decided): a local aggregator that gathers a person's existing mailboxes over IMAP (two-way sync), with sorting, anti-spam and a webmail behind SSO; no server exposed to the Internet. An **MCP tool** will let the model or a workflow search, read, file and draft, never send or delete permanently: sending stays validated by the person.
- **Persistent chat and video**: installed, in acceptance testing, in a separate module ([Communication](../communication/README.en.md)); Jitsi Meet replaced La Suite's Visio. Starting a call from the chat remains planned.

## Lessons

- A database "already tested" by migrations is not tested for writes: the first folder creation revealed the PostgreSQL 16 requirement.
- Before switching a service to a new database, check its network **egress** as much as the database's ingress.
- A token can end up in a log through an unexpected path (access log, error log, a tool's HTTP client): each path gets checked.
