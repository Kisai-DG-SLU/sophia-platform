# Chat interface — production deployment

Deployment template for a web chat interface in front of the model router, with **no key in the browser** and **mandatory sign-in**. The front-end code is not provided: this directory describes the container, the proxy and the Kubernetes resources.

```
Browser → Route (TLS) → oauth2-proxy :4180 → nginx :8080 ─→ conversation API :8000 ─→ model router (LiteLLM)
                          │ OIDC sign-in          │ static front         │ injected context (persona, profile, date)
                          └→ Keycloak             │ (allow-list)         ├→ PostgreSQL 18 (conversations, profiles, rights)
                                                  │                      ├→ Forgejo (projects = repositories)
                                                  │                      ├→ web airlock (search, weather) — ../../dmz/
                                                  │                      └→ MCP servers (tools, modules; Files with the token)
                                                  └ identity → x-litellm-end-user-id, X-Sophia-User, X-Sophia-Groups;
                                                    access token → X-Sophia-Jeton, on the chat route only
```

| File | Role |
|---|---|
| `Containerfile` | UBI 9 minimal, system nginx and python3, arbitrary UID (OpenShift), logs to stdout/stderr; Python 3.12 and the conversation API's dependencies (same image, sidecar container) |
| `entrypoint.sh` | renders the configuration, refreshes prices in the background (every 30 s while the router is unreachable, then every 10 min), runs nginx in the foreground |
| `render-config.py` | injects the router key and the voice key into `nginx.conf` (mode 600), never printed; rejects a malformed key; without a voice key, falls back to the pod's key and says so |
| `render-pricing.py` | reads the router's prices server-side and writes `pricing.json` (atomic write) for cost display in the front |
| `nginx.conf.in` | template: **allow-list** of served files and of routes relayed to the router, enforced identity headers, the person's token relayed on a single route, CORS for the school's origin only |
| `sophia-interface.yaml` | dedicated `sophia-interface` namespace: ImageStream, BuildConfig (read-only deploy key), Deployment (oauth2-proxy + nginx + conversation API, `sophia-chat` class), Service, NetworkPolicy |
| `sophia-interface-route.yaml` | production Route, applied at switchover |
| `sophia-interface-essai.yaml` | trial Route before switchover, reachable through the VPN only, removed afterwards |

## Safeguards

- **File allow-list**: only `/`, `index.html`, `models.js`, `pricing.json`, `css/`, `js/`, `images/`, `fonts/`, `vendor/` are served. Without it, the rendered configuration — which holds the key — could be downloaded.
- **Route allow-list**: only `v1/models`, `v1/chat/completions` and `health/liveliness` are relayed. Without it, the router's admin API was reachable with the server's key.
- **Dedicated key**: a router *virtual key*, restricted to the exposed models, with capped budget and rate.
- **oauth2-proxy trust limited to the router**: `--trusted-proxy-ip` accepts `X-Forwarded-*` headers only from the address through which the OpenShift router reaches the pods (`ROUTER_POD_SIDE_IP`, read from the oauth2-proxy log, which warns at startup as long as none is given). Limit: every `hostNetwork` process on the node shares that address. In service on every oauth2-proxy of the platform: chat, school, modules (and the shopping remote browser), visualisation, workflow interface.
- **Enforced identity**: `x-litellm-end-user-id` comes from oauth2-proxy; headers sent by the client are overwritten. The router tracks spend per person.
- **Server-side context**: in production, `v1/chat/completions` goes through the conversation API, which injects the persona, the person's profile and the date before the router; the browser cannot change them.
- **Web search**: the tool loop (search, page reading, weather) runs in the API, against the `sophia-dmz` airlock. A page can only be read if its address comes from a search result or from the person's message: an address guessed by the model is refused by code.
- **Tools over MCP**: the API is an MCP client; it reads the tool list of every server in `SOPHIA_MCP_URLS` (web airlock, [local tools](../../skills/README.en.md), modules), shows the announcement each tool declares (icon, label), fills reserved parameters itself (protected account) and inserts into the answer, after checking them, the images and maps the tool returns. Adding a tool requires no interface change.
- **Models per role**: `SOPHIA_MODELS_BY_ROLE` (by default, children and guests on the local model only; an account with no known role is treated as a guest). A model sent by the browser outside the list gets an **explicit 403** and nothing goes to the router: no silent substitution. Internal calls (analysis, rephrasing, summary) reuse the already-checked model; the profile only exposes allowed models. Voice uses a separate virtual key (`LITELLM_AUDIO_API_KEY`, in service), limited to the two voice aliases and set by nginx on its routes only: the rule is held by the router, without parsing the form. See [Models by role](../../../../docs/concepts/13-modeles-par-role.en.md).
- **Slots on the graphics card**: chats take at most 2 of the local server's slots during the day, 1 from 3 a.m. to 7 a.m. (`SOPHIA_LOCAL_CHAT_PLAGES`); school never waits; one more chat waits 60 s at most, then gets a "very busy" message. The browser's background tasks (title, requested summary) carry the `X-Sophia-Tache: fond` header and go to the background alias, as a simple relay, falling back to the main alias if the router or the key refuses it; the compaction summary stays on the main alias, since it is on the path of the person's message.
- **Answer written by the service**: an MCP tool may return `_trace` (a line shown before the answer) and `_fin` (the final answer, shown as is, without calling the model again). The decision stays with the service that knows its data (for instance "nothing planned" for an empty slot): the model can no longer embellish it.
- **Paths declared by tools**: an MCP server declares each tool's path in its metadata (`sophia/parcours`: `express`, `lecture`, `liste`). The chat server picks by rules the tools offered to the model, or calls an express-path tool itself and writes the answer from the service's messages; a server that declares no path keeps the old behavior.
- **Opening an application**: an `application` intent in the analysis, with enumerations built by the server for the person's role; decision in the policy, from a closed, versioned list (`SOPHIA_APPLICATIONS`: identifier, name, base address, allowed pages, roles); the server writes the sentence and a **button**, and the browser only accepts an application button whose address starts with a base from the list. The click opens or reuses a **named tab** per application (a browser blocks opening a tab without a gesture from the person). Allowed roles come from the list (Files: the whole family, each for their own files; never guests); buttons are removed from the history sent to the model, which must never write an address.
- **Files in the chat** (in service): find one of the person's files in the office suite, then open it. oauth2-proxy relays the access token (`--pass-access-token`, `--cookie-refresh=4m`, below the token's 5-minute lifetime); nginx forwards it to the API on the chat route only (`X-Sophia-Jeton`) and clears it everywhere else, never towards the router; the API sends it only to the servers on the closed list `SOPHIA_MCP_JETON_URLS`, and never to the model. Search is by name; the answer is written by the server, with links it builds: "Open in Collabora" for an editable document, "Open in Files" (preview) for another file, and "View in Files", which opens the **folder** containing the file. **Reading a document's content** ("read me the second one") is deployed, acceptance test pending: reserved to local models (`SOPHIA_MODELES_CONTENU`), content removed from any call to another model, no tool offered after a reading. See [Identity relay](../../../../docs/concepts/12-relais-identite.en.md).
- **School on its own address**: the school button opens the school's own address, with a deep link per level and subject built by the server; in the browser, any link to the school becomes that button (a known route is kept, an invented path leads to the home page, a look-alike address stays an ordinary link), and the model's instructions no longer contain the address. The old `/ecole/` path is no longer relayed: a 302 redirect (not a 301, which the browser keeps forever) leads to the school's address, for bookmarks and the buttons of older answers, fragment included.
- **New-version notice** (in service): the API sets the `X-Sophia-Version` header (the image commit) on every response; the front compares it with the version it loaded, on every response and when the tab regains focus, and shows a "Reload" banner, never during typing or a response; never an automatic reload, the draft is kept.
- **No third-party resources** (in service): the front's libraries (PDF viewer, Markdown rendering, HTML sanitising, ZIP archives) are served by the image under `vendor/<package>@<version>/`, with their licences and an integrity manifest; so are the themes' fonts, under `fonts/`. No CDN left in the content security policy: the browser only reaches the chat's address.
- **Themes** (in service, trials at the acceptance step): six themes to choose from in the profile, each in light and dark, combined with the light / dark / system setting; contrast of at least 4.5:1 checked by a test; twelve OFL-licensed woff2 fonts bundled; a parent sets a child's theme. Calendar themes are offered by a "Try / No thanks" banner, decided by the server in local time: holidays **on the day only** (Halloween on 31 Oct, Christmas on 25 Dec, New Year on 1 Jan, Valentine's Day on 14 Feb, Easter Sunday, 1 May, 14 July) and the person's birthday; seasons on their first day. All remain selectable at any time under "Bonus themes". The conversation and settings panes are closed by default on every screen; on a phone, one at a time, as an overlay.
- **Avatars** (in service): a catalogue of drawings shared by the chat and the school, served by the school and read by the API; the profile keeps a small image (checked PNG: signature, dimensions, size; no SVG).
- **Older browsers** (Safari 15): a build guard rejects syntax newer than ES2021 and APIs missing from Safari 15; the stylesheet has its fallbacks (`color-mix`, `-webkit-` prefixes). An application that needs a newer engine (the office suite) shows inactive text instead of the button, detected by feature, not by User-Agent.
- **Test accounts**: fictitious roles (`enfant-a`, `parent-b`), never the family's first names.
- **Context window**: capped per model (`SOPHIA_CONTEXT_LIMITS`); beyond it, the oldest exchanges are summarised, and an oversized file is refused with a clear message.
- **Conversation API**: listens on `127.0.0.1` only, behind nginx; identity comes from the headers set by nginx.
- **Network**: ingress from the OpenShift router only, to oauth2-proxy; the services it reaches (database, web airlock, tools, modules) admit the interface from its namespace only; egress to the model router, Keycloak, PostgreSQL 18 (the old instance stays open during the hold period after the migration), Forgejo, the web airlock, the MCP servers of `sophia-skills` and of modules, the school and DNS.

## Prerequisites (secrets)

| Secret | Content |
|---|---|
| `sophia-interface-git` | **read-only** deploy key for the front repository (SSH), for the build; never a forge administrator's token |
| `sophia-interface-litellm` | `LITELLM_API_KEY`: dedicated virtual key; `LITELLM_AUDIO_API_KEY` (optional): voice key, limited to its two aliases — when missing, voice uses the pod's key, with a warning at startup |
| `sophia-interface-oauth2` | `client-secret` (Keycloak client) and `cookie-secret` (32 random characters) |
| `sophia-chat-db` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`: conversation database |
| `sophia-chat-forgejo` | `FORGEJO_TOKEN` of a Forgejo service account (`write:repository`, `write:organization`, `read:user`) — optional: without it, only the global project exists |

## Dedicated namespace (in service)

The interface has left the applications namespace, where the deployment agent is administrator and could read its Secrets. Limit: the namespace protects from the deployment agent, not from the maintenance agent, which is cluster administrator.

1. **Preparation**, with no effect on what runs: namespace, quota, defaults, closed ingress; the ingress rules of the services the interface calls (router, database, identity, forge, web airlock, tools, modules) admit **both** namespaces during the switchover.
2. **Secrets copied through a pipe** (`oc get … -o yaml | sed | oc create`), with no file and without rotating them; a read-only deploy key added in the forge for the build.
3. **Full trial** on the temporary Route (`sophia-interface-essai.yaml`), reachable through the VPN only: chat, school, modules, voice, Files, web search, with a child account.
4. **Switchover**: `rollout status` required, then the old Route is deleted and the new one created (`sophia-interface-route.yaml`): the outage lasts a few seconds. The old Deployment goes to 0, without deletion; the trial callback address is removed from the Keycloak client.
5. **Clean-up**, after one day without incident, as a separate step (until then, rollback takes four commands): **done**. The old Deployment, its Secrets and the old Route are deleted, and ingress from the applications namespace is removed from the rules of the database, the web airlock, the tools, the school and the modules; that namespace no longer hosts anything of the interface.

## Prepared changes

| Change | Content | Status |
|---|---|---|
| **School on its own address** | a school served under the chat's origin would have all of the person's rights over the chat. The school moves to its own address, behind its own oauth2-proxy (no guests); CORS covers only one API prefix (`/api/store/school/`), for the school's exact origin; dedicated routes for the avatar, reactions and voice, rather than the profile (which would change the persona) or completions (which would open the model); chat cookie without a parent domain; photos with `Cross-Origin-Resource-Policy: same-site` | three compatible steps: (a) on the chat side, **in service**; (b) the school on its address, **in service**; (c) chat links to the new address, **in service**; (d) the old `/ecole/` relay turned into a redirect, **in service** |
| **Avatars as images** | the school's drawings are stored as a small image in the chat profile (checked PNG: signature, dimensions, size; no SVG), existing profiles migrated; then `/ecole/` becomes a redirect to the school's address | **in service** |
| **The interface as a requester** | `deleguer` intent (constrained analysis, rules, confirmation by a click with a single-use token, call to the [dispatcher](../../core/repartiteur/)); the person's token relayed and verified from the start; per-person quotas; plan and command approvals in the interface; follow-up in the conversation | designed |

## Note

A `hostNetwork` pod bypasses NetworkPolicies (node traffic is always accepted). Test isolation from a regular pod.
