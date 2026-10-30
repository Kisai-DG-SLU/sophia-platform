# Chat interface — production deployment

Deployment template for a web chat interface in front of the model router, with **no key in the browser** and **mandatory sign-in**. The front-end code is not provided: this directory describes the container, the proxy and the Kubernetes resources.

The interface is also the **cockpit shell**: a single page that shows, next to the conversation with Sophia, the platform's applications (cooking, school, visualisation, messaging, video calls, office suite) in frames. See the [Cockpit](#cockpit) section.

```
Browser → Route (TLS) → oauth2-proxy :4180 → nginx :8080 ─→ conversation API :8000 ─→ model router (LiteLLM)
                          │ OIDC sign-in          │ static front         │ injected context (persona, profile, date)
                          └→ Keycloak             │ (allow-list)         ├→ PostgreSQL 18 (conversations, profiles, rights)
                                                  │                      ├→ Forgejo (projects = repositories)
                                                  │                      ├→ web airlock (search, weather) — ../../dmz/
                                                  │                      └→ MCP servers (tools, modules; Files with the token)
                                                  └ identity → x-litellm-end-user-id, X-Sophia-User, X-Sophia-Groups;
                                                    access token → X-Sophia-Jeton, on the chat and "What's new?" routes only
```

| File | Role |
|---|---|
| `Containerfile` | UBI 9 minimal, system nginx and python3, arbitrary UID (OpenShift), logs to stdout/stderr; Python 3.12 and the conversation API's dependencies (same image, sidecar container) |
| `entrypoint.sh` | renders the configuration, refreshes prices in the background (every 30 s while the router is unreachable, then every 10 min), runs nginx in the foreground |
| `render-config.py` | injects the router key and the voice key into `nginx.conf` (mode 600), never printed; rejects a malformed key; without a voice key, falls back to the pod's key and says so |
| `render-pricing.py` | reads the router's prices server-side and writes `pricing.json` (atomic write) for cost display in the front |
| `nginx.conf.in` | template: **allow-list** of served files and of routes relayed to the router, enforced identity headers, the person's token relayed on two routes only (chat, "What's new?"), CORS for the school's origin only |
| `sophia-interface.yaml` | dedicated `sophia-interface` namespace: ImageStream, BuildConfig (read-only deploy key), Deployment (oauth2-proxy + nginx + conversation API, `sophia-chat` class), Service, NetworkPolicy |
| `sophia-interface-cockpit-egress.yaml` | cockpit-specific egress, in a separate policy added to the application's own: to the oauth2-proxy of the applications that provide a summary, and to the messaging summary route |
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
- **Places** (weather, place, distance, map): the model extracts the places from the request; deterministic guards check its output before any call:
  - **a place must be said**: a place extracted by the model is kept only if it appears in the current message (compared without accents, case or article) or is the name of a saved place. The rule also applies to the model calling a tool freely, refused without any network call. It prevents a place taken from the history or invented (a misunderstood word geocoded to the other side of the world). In service, under acceptance testing;
  - **a moment is never a place**: a closed list of moments ("tomorrow", weekdays…) is removed from places, as a second net;
  - **without a place, the question is written by the server**, without calling the model again;
  - **expected country**: a result outside the expected countries (`SOPHIA_PAYS_ATTENDUS`) and not named by the person must be confirmed instead of announced;
  - **current place of the conversation**: the server stores in the database the last place **that came from the message** and passed the guards; "and tomorrow?" reuses it until another one is named. The model never rereads the history to find a place. No current place for a distance (two places), nor for a guest account, which always gets the question. In service, verified.
  - **Profile places** (in service, under acceptance testing): household places shared by everyone (a home, the default, and a second residence), set by an administrator in the profile window, and up to five personal places per person, freely named; a guardian sets a child's; nothing for a guest, who only has the places they name. The family reads the household places without their address; another profile's places are never read. The address stays in the chat database; the town is **chosen** among the results of the geography tool, never typed freely; outside the covered country, an Open Location Code is decoded locally and refused if it falls far from the chosen town. The model only receives place **names** (in the analysis prompt), and the announcement shows the name, not the town. A closed alias table ("at home" → the home) applies after the analysis; a country or region that contains only one saved place designates that place. Resolution order: place said, else current place, else home (for a guest: the question).
  - **Place objects inserted by the server only**: for a saved place, the server passes the town and its postcode, or coordinates, to the tools; a place object or coordinates coming from the model are removed. The weather for a saved place goes through the **town centre**, never the address (rounded again on the web service side). In service, under acceptance testing.
  - **Street geocoding** through the national address base, served locally in the namespace of tools without Internet, once when the place is saved: coded, not yet in service. Other requests are still geocoded online through the web airlock.
  - **Weather fallback cache**: the chat sends the web service the anonymous list of the saved places' towns (no place name, owner or address), with a shared token that is never logged (`SOPHIA_WEB_CACHE_JETON`). Ready, inactive until the Secret exists.
- **Tools over MCP**: the API is an MCP client; it reads the tool list of every server in `SOPHIA_MCP_URLS` (web airlock, [local tools](../../skills/README.en.md), modules), shows the announcement each tool declares (icon, label), fills reserved parameters itself (protected account) and inserts into the answer, after checking them, the images and maps the tool returns. Adding a tool requires no interface change.
- **Models per role**: `SOPHIA_MODELS_BY_ROLE` (by default, children and guests on the local model only; an account with no known role is treated as a guest). A model sent by the browser outside the list gets an **explicit 403** and nothing goes to the router: no silent substitution. Internal calls (analysis, rephrasing, summary) reuse the already-checked model; the profile only exposes allowed models. Voice uses a separate virtual key (`LITELLM_AUDIO_API_KEY`, in service), limited to the two voice aliases and set by nginx on its routes only: the rule is held by the router, without parsing the form. See [Models by role](../../../../docs/concepts/13-modeles-par-role.en.md).
- **Slots on the graphics card**: chats take at most 2 of the local server's slots during the day, 1 from 3 a.m. to 7 a.m. (`SOPHIA_LOCAL_CHAT_PLAGES`); school never waits; one more chat waits 60 s at most, then gets a "very busy" message. The browser's background tasks (title, requested summary) carry the `X-Sophia-Tache: fond` header and go to the background alias, as a simple relay, falling back to the main alias if the router or the key refuses it; the compaction summary stays on the main alias, since it is on the path of the person's message.
- **Answer written by the service**: an MCP tool may return `_trace` (a line shown before the answer) and `_fin` (the final answer, shown as is, without calling the model again). The decision stays with the service that knows its data (for instance "nothing planned" for an empty slot): the model can no longer embellish it.
- **Paths declared by tools**: an MCP server declares each tool's path in its metadata (`sophia/parcours`: `express`, `lecture`, `liste`). The chat server picks by rules the tools offered to the model, or calls an express-path tool itself and writes the answer from the service's messages; a server that declares no path keeps the old behavior.
- **Opening an application**: an `application` intent in the analysis, with enumerations built by the server for the person's role; decision in the policy, from a closed, versioned list (`SOPHIA_APPLICATIONS`: identifier, name, base address, allowed pages, roles). Allowed roles come from the list (Files: the whole family, each for their own files; never guests); the model never writes an address.
  - **In the cockpit**: no button any more. The server adds to the stream an event that switches the cockpit to the requested module and page, taken from the closed list; the browser re-checks the module, its mode and the path's shape. From the home page and the Sophia module the switch is direct; from "Ask Sophia" inside another application, the cockpit asks first. A "Sophia opened … for you" banner offers a way back. Visualisation for the administrator; for a child, "what are we eating?" opens the meal plan read-only. **In service, under acceptance testing.**
  - **Chat opened alone** (outside the cockpit, or a device that cannot show the application): the server writes the sentence and a **button**, and the browser only accepts an application button whose address starts with a base from the list. The click opens or reuses a **named tab** per application (a browser blocks opening a tab without a gesture from the person). Buttons are removed from the history sent to the model. In service.
- **Files in the chat** (in service): find one of the person's files in the office suite, then open it. oauth2-proxy relays the access token (`--pass-access-token`, `--cookie-refresh=4m`, below the token's 5-minute lifetime); nginx forwards it to the API on the chat route and the "What's new?" route only (`X-Sophia-Jeton`) and clears it everywhere else, never towards the router; the API sends it only to the servers on the closed list `SOPHIA_MCP_JETON_URLS`, and never to the model. Search is by name; the answer is written by the server, with links it builds: "Open in Collabora" for an editable document, "Open in Files" (preview) for another file, and "View in Files", which opens the **folder** containing the file. **Reading a document's content** ("read me the second one") is deployed, acceptance test pending: reserved to local models (`SOPHIA_MODELES_CONTENU`), content removed from any call to another model, no tool offered after a reading. See [Identity relay](../../../../docs/concepts/12-relais-identite.en.md).
- **School on its own address**: the school button opens the school's own address, with a deep link per level and subject built by the server; in the browser, any link to the school becomes that button (a known route is kept, an invented path leads to the home page, a look-alike address stays an ordinary link), and the model's instructions no longer contain the address. The old `/ecole/` path is no longer relayed: a 302 redirect (not a 301, which the browser keeps forever) leads to the school's address, for bookmarks and the buttons of older answers, fragment included.
- **New-version notice** (in service): the API sets the `X-Sophia-Version` header (the image commit) on every response; the front compares it with the version it loaded, on every response and when the tab regains focus, and shows a "Reload" banner, never during typing or a response; never an automatic reload, the draft is kept.
- **No third-party resources** (in service): the front's libraries (PDF viewer, Markdown rendering, HTML sanitising, ZIP archives) are served by the image under `vendor/<package>@<version>/`, with their licences and an integrity manifest; so are the themes' fonts, under `fonts/`. No CDN left in the content security policy: the browser only reaches the chat's address.
- **Themes** (in service, trials at the acceptance step): six themes to choose from in the profile, each in light and dark, combined with the light / dark / system setting; contrast of at least 4.5:1 checked by a test; twelve OFL-licensed woff2 fonts bundled; a parent sets a child's theme. Calendar themes are offered by a "Try / No thanks" banner, decided by the server in local time: holidays **on the day only** (Halloween on 31 Oct, Christmas on 25 Dec, New Year on 1 Jan, Valentine's Day on 14 Feb, Easter Sunday, 1 May, 14 July) and the person's birthday; seasons on their first day. All remain selectable at any time under "Bonus themes". The conversation and settings panes are closed by default on every screen; on a phone, one at a time, as an overlay.
- **Avatars** (in service): a catalogue of drawings shared by the chat and the school, served by the school and read by the API; the profile keeps a small image (checked PNG: signature, dimensions, size; no SVG).
- **Older browsers** (Safari 15): a build guard rejects syntax newer than ES2021 and APIs missing from Safari 15; the stylesheet has its fallbacks (`color-mix`, `-webkit-` prefixes). An application that needs a newer engine (the office suite) shows inactive text instead of the button, detected by feature, not by User-Agent.
- **Test accounts**: fictitious roles (`enfant-a`, `parent-b`), never the family's first names.
- **Context window**: capped per model (`SOPHIA_CONTEXT_LIMITS`); beyond it, the oldest exchanges are summarised, and an oversized file is refused with a clear message.
- **Conversation API**: listens on `127.0.0.1` only, behind nginx; identity comes from the headers set by nginx.
- **Network**: ingress from the OpenShift router only, to oauth2-proxy; the services it reaches (database, web airlock, tools, modules) admit the interface from its namespace only; egress to the model router, Keycloak, PostgreSQL 18 (the old instance stays open during the hold period after the migration), Forgejo, the web airlock, the MCP servers of `sophia-skills` and of modules, the school and DNS. The cockpit adds a **separate policy** (`sophia-interface-cockpit-egress.yaml`): egress to the oauth2-proxy port of the applications that provide a summary and to the messaging summary route; rules add up, the application's own policy is unchanged. No egress to the applications shown in frames: the browser loads them.

## Cockpit

The chat becomes the single shell for the platform's uses, rather than a chat that sends people to other tabs. Each application keeps its own look and its own sign-in; the frame (panels, header, home page) follows the theme chosen in the profile.

### Shell

- **Module panel** on the left, hidden by default, opened by a menu button. The list is **closed, built by the server and filtered by role** (identifier, name, mode `interne` / `a_part` / `iframe`, address, roles, read-only page, required engine); an address that is not `https://` or an unknown mode is dropped. Hiding a module is not a control: each application keeps its oauth2-proxy and its groups. Without a module list, the chat stays alone.
- **One address per module** (`#/<module>`): the Back button and reloading work.
- **Right-hand panels**, hidden by default, whose button disappears while the panel is open: "What's new?" on the home page, conversations and diary in the Sophia module, "Ask Sophia" in the other applications (see below). On a large screen they take their own space; on a phone they overlay. Their state is kept when switching module and on reload.
- **Theme**: a header button opens the choice (light or dark, profile themes, calendar themes), saved in the profile as in the chat.
- **"Zone Grise" development module**, for the administrator only: manage and supervise development assisted by the development agents, and talk with them; later, a "Pair Programming" button that opens a terminal in the coding tool. **Planned**: absent from the list until it exists.

Status: in service; layout validated on a computer, tests on an old tablet and a phone under acceptance testing.

### Home page

- The cockpit's opening page. People **talk to Sophia** there: the home page uses the same sending path, microphone and voice as the chat, and shows only the person's last sentence and Sophia's last answer, with "See the whole conversation".
- **Active session**, held by the server and shared across devices: the home conversation continues if it dates from today and is less than 3 hours old, otherwise a new one opens; its title and start time are shown, with "Change" and "New".
- **Hologram** of Sophia's avatar: a point cloud taken from the avatar, drawn in 2D in the browser without a library, swaying ±30°, with expressions and blinking. **Adaptive**: three density levels, starting with the lightest on an unknown device, going up or down according to the measured time per frame, falling back to a still image; the chosen level expires after a week and with each new version. Stopped outside the home page and in a hidden tab; fixed head if the device asks for reduced motion.
- **Home page per theme**: scene background, hologram tint and small discreet pictograms from a closed list, per theme; contrasts checked by a test.
- **Sophia's states**: a golden cloud in the head while thinking, lit as soon as the question is sent; the icon of the called tool next to the head, kept for at least 2.5 s; the lips move while the visible text grows and while the voice speaks.

Status: in service; home page text, cloud on sending, tool icon, order of states and home page theme verified by the administrator on the real path; tests on an old tablet and a phone under acceptance testing.

### States in the stream

- The server adds to the (OpenAI-compatible) response stream events **without `choices`**, so other clients ignore them: `sophia_etat` (`reflexion`, `outil` with an icon and a label, `fin`).
- The icon is chosen **by the server** from a closed list (cooking, messages, weather, files, school, web, generic), from the tool's name or its server; never from a model text.
- Tool announcements and traces carry `sophia_annonce` and never count as Sophia's text. The visible text is decided by the browser alone; the model's reasoning (tags or a dedicated field) keeps the "thinking" state.
- **Background tasks** (title, summary) never act on the hologram, neither on the server nor in the browser.
- **Observation mode**, enabled only by an address parameter: a local, timestamped overlay of the received states, with "Copy", to diagnose on a real question. Nothing is sent.

### Voice along the stream

The voice starts while the text is being written: by groups of sentences (the first one from about forty characters, then 80 to 150), chained without gaps with one synthesis ahead, without reading twice at the end, cut cleanly. A group's time limit accounts for the synthesis queue; when it expires, the group is retried then merged into the next one: **no text is lost**, a group is skipped only if the service fails. In service, verified (the voice starts well before the end of the text); sound on an old tablet under acceptance testing. Service side: [`deploy/okd/inference/`](../../inference/README.en.md).

### Applications in frames

| Setting | Role |
|---|---|
| `SOPHIA_MODULES_CADRE` | list of modules shown in the centre, read at startup: changing a mode takes an `oc apply`, not a build |
| `frame-src` of the content policy | limited to the closed list's addresses, compared by a test |
| live frames | **two at most**, loaded on first opening; the oldest is unloaded, never the one on screen |
| `allow` | camera and microphone for video calls only; clipboard and full screen for a document |

- **`sophia.pret` signal**: each application posts `{type: "sophia.pret", module: "<identifier>"}` to the chat's origin only when it is ready. The chat accepts a message only if its **origin** is the module's **and** its **source** is that module's frame; a fake signal posted by another page is ignored. The identifier must be exactly the module's in the list (a different identifier is ignored, and the fallback shows up wrongly).
- **Fallback after 8 s** without a signal: "Open separately" (named tab) and "Sign in again" (sign-in in a tab, then the frame reloads on returning to the cockpit).
- **Expired sign-in**: nothing changes in the identity provider's headers, whose sign-in page is still refused in a frame. An application with no session on the device shows the fallback; "Sign in again" once per application and per device is enough (already signed in to the provider, so nothing to type).
- **Each application** sets `frame-ancestors 'self' <chat origin>`: only the chat can show it. `frame-ancestors` checks the whole chain of frames: an editor nested in an application (office suite) must also allow the chat.
- Everything is under one parent domain: the frames' cookies are not third-party cookies.
- An application that needs a more recent engine than the device's shows an explanation instead of the frame.

Status: cooking, school and visualisation in frames, in service, verified; messaging, video calls and office suite in frames, in service, under acceptance testing. Each application's settings: [modules](../../../../docs/modules/README.en.md), [office suite, chat and video calls](../../office/README.en.md).

### Document opened from the office suite

The files application opens the editor in a new tab. In the cockpit, the small script it serves replaces that one gesture: it posts `{type: "sophia.ouvrir", module: "bureau", chemin: "/wopi/<id>"}` to the chat only, only if its direct parent is the chat and for an exact same-origin path. The chat refuses a path that is too long, contains `..`, `?`, `#` or `\`, or does not match the closed shape; it rebuilds the address on the module's origin and checks it again. The document opens in a frame laid over the list, with a "← Files" button, its own signal and its own fallback, and counts in the two-frame limit. In service, under acceptance testing.

- **"Sophia, open document X"** (in service, under acceptance testing): analysis by the model (intent and terms); decision by rules (search tool called with the person's token, choice by number of results); execution by a server event to the cockpit. **The identifier comes from the tool's result, never from the model**; paths have a closed shape (identifier as a lowercase UUID), checked by the server and then by the browser. One result: the document (the preview on a phone); several: a clickable list, or their common folder; none: "My files".

### Sophia writes into the open document

**In service, verified on the real path** (direct insertion and acknowledgement); cursor detection, corrected, is to be checked again.

- **Editor state**: the files application's relay announces `sophia.editeur_pret` when an editable document is loaded; only then does the chat set the `X-Sophia-Editeur` header on its messages. The header grants no right: it only offers the intent.
- **Analysis → decision → execution**: the `document` intent (write, rephrase) is offered only with that header and for a role that has the office suite; the server decides and marks the reply (`sophia_document`); the browser inserts. The **selection** is read only for a rephrasing, and only goes to a local model; the analysis never sees it.
- **What is inserted**: only the reply's visible text (no thinking, no tool notice), sanitised (control, bidi and zero-width characters removed), capped at 20,000 characters, posted to the document frame only with the files application's exact origin; only that frame's replies, for the expected identifier, are read. Nothing is inserted from a reply reloaded from history: only the "Insert" button allows it.
- **Direct insertion, without a click**, undone with Ctrl+Z; an **acknowledgement** under the reply, with the position: at the cursor if the person clicked or typed in the text, otherwise at the end of the document; otherwise a named error (read-only, document type, timeout).
- **Relay on the files application's side**: closed list of messages to the editor (plain-text insertion, reading the selection, editor announcement, named errors), never a command or a script received from the chat; placing at the cursor is a fixed command of the relay. Word processing only in the first version. A test of the editor's internal selectors is to be rerun with each new image.
- **Observation mode**: document traces (editor announcement, header sent or not and why, insertion, acknowledgement or error).

### Ask Sophia

**In service, under acceptance testing.**

- An "Ask Sophia" panel in each application, except the home page and the Sophia module; **a single state** for the panel, kept from one application to another.
- **One conversation per application** and per person, with the home page's 3-hour rule; these conversations are filed in an "Applications" section of the Sophia module. A single conversation engine, the chat's own.
- **Context**: the `X-Sophia-Module` header, re-validated by the server against the role's modules, only adds **one line of context**; no extra right, and nothing about a child. Tools and rights are the role's, as everywhere.
- **Page context**: an application may post `{type: "sophia.contexte", module, …}`; the message is accepted only from the module's origin and frame, only fields with a closed shape are kept (an extra field is dropped), and the server re-validates. School: the subject and topic only, checked again against the index; cooking: the page and the displayed recipe's identifier. Never for a background task.
- A switch suggested from the panel is **asked** ("Open …?"); from the home page and the Sophia module, it stays direct.

### "What's new?"

- Home page panel, in three groups: to do, notifications, news; each line carries its application's avatar and colour.
- **Computed by the chat server**, so that the panel is complete on a new device: the browser queries no application. The server calls in parallel the summary routes of the role's modules only (cooking, visualisation, messaging, files), 2 s each, with the relayed token; a source that fails, is refused (401, 403), absent (503) or too large is left out. 60 s cache, without the token; the token is never logged, and nginx only forwards it on the chat route and the "What's new?" route.
- **Contract**: each application exposes `GET /api/resume`, deterministic, with no language model, at most 20 items `{id, groupe, titre, detail, date, expire, relative link, priorite}`; `503` means "absent for now". The chat validates the schema, never renders a text as HTML and rebuilds each link on the closed list's base.
- **Identity**: the chat server relays the person's access token (see [Identity relay](../../../../docs/concepts/12-relais-identite.en.md#to-the-summary-routes)).
- An application with no data of its own (the school, a static site) has no route: its summary and the first-appearance date of its news are computed by the chat in its database.

Status: in service, verified by the administrator on the real path: calls to the four summary routes (cooking, visualisation, messaging, files), no source missing; school summary and content news computed by the chat, under acceptance testing.

### Access through the cockpit only (planned)

Last step, after acceptance testing on all devices: an application page opened on its own is sent back to the cockpit, on the right module. Two layers: `frame-ancestors` (already set), then the redirect, on the server by the request's destination header, and in the page by a script for old browsers that do not send that header. An exception for the administrator, for troubleshooting. It is a usage rule, not a security barrier: each application keeps its sign-in. Not concerned: native applications, technical routes (summaries, tools), the sign-in page.

## Prerequisites (secrets)

| Secret | Content |
|---|---|
| `sophia-interface-git` | **read-only** deploy key for the front repository (SSH), for the build; never a forge administrator's token |
| `sophia-interface-litellm` | `LITELLM_API_KEY`: dedicated virtual key; `LITELLM_AUDIO_API_KEY` (optional): voice key, limited to its two aliases — when missing, voice uses the pod's key, with a warning at startup |
| `sophia-interface-oauth2` | `client-secret` (Keycloak client) and `cookie-secret` (32 random characters) |
| `sophia-chat-db` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`: conversation database |
| `sophia-chat-forgejo` | `FORGEJO_TOKEN` of a Forgejo service account (`write:repository`, `write:organization`, `read:user`) — optional: without it, only the global project exists |
| `sophia-web-cache` | `jeton`: token shared with the web service for the weather fallback cache (same value on both sides, created through a pipe, never displayed) — optional: without it, the list of towns is not sent |

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
