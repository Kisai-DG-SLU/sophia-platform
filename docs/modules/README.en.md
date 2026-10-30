# Private modules — what you can build with SophIA

A **module** is an application for the household or the organisation, built on the platform's bricks instead of reinventing them: single sign-on, model router and local model, shared PostgreSQL database, MCP tools, chat interface. The modules below run in the reference install; their code is **private** (it carries a household's own data and settings), but their architecture and rules are described here so that a third party can build equivalents.

| Module | What it does | Platform bricks |
|---|---|---|
| [Cooking](cuisine/README.en.md) | meal plan, recipe catalogue, rule-bound recipe generation, shopping | SSO, local model, PostgreSQL, `image` tool, web airlock, MCP to the chat and to the Shopping module |
| [Shopping](courses/README.en.md) | choosing a drive-through store's products according to household rules, filling the real basket, express basket from the chat | SSO, local model, PostgreSQL, remote browser in the airlock, MCP |
| [School](ecole/README.en.md) | playful school from primary to lower secondary, hints without the answer, report book, reading photographed homework | SSO and roles, local model with vision, chat interface, content through Git |
| [Office](bureautique/README.en.md) | each person's files, private by default, document editing in the browser, search and reading from the chat | SSO, PostgreSQL 18, common S3, "files" MCP tool under the person's identity |
| [Communication](communication/README.en.md) | persistent chat between household members and video calls, at home only; installed, in acceptance testing | SSO, PostgreSQL 18, dedicated local volume, VPN for video media |
| [Visualisation](visualisation/README.en.md) | measured state of each component and path of a request, hourly check of repository mirrors; compliance planned | SSO, read access to the cluster API and metrics, read access to the event bus, forge |

## The common pattern

| Rule | How it applies |
|---|---|
| **The model analyses, rules decide, a tool executes** | the model proposes (a recipe, the understanding of a shopping line, a hint) in strict JSON; a deterministic validator accepts or rejects with its reasons; only code acts (saving, filling a basket, publishing) |
| **A check around every model output** | cited sources = pages actually read; brand accepted only if written; a hint never contains the answer; an image goes through the classifier |
| **Identity comes from the platform, never from the model** | header set by oauth2-proxy on pages; parameter injected by the interface (`sophia/injecte`) into MCP tools; list of allowed members checked by the server |
| **Protected accounts** | children read, never trigger a purchase or a costly generation; their data never goes to a remote model |
| **Closed-list networking** | each module only opens the flows it needs (ingress from the router and the interface, egress to the model router, identity provider, its database, the tools it uses); Internet access goes through the airlock |
| **One module = one pod, one database, one group** | pod with its oauth2-proxy on its own address (an application served under the interface's origin would have all of the person's rights over the chat), own database and role in the shared PostgreSQL, realm group; build from the internal forge. In the cockpit, the module is shown **in a frame** from its own address: it never shares the interface's origin |
| **The human keeps control of the irreversible** | validating a list, payment, marking a dictation |

To plug a module into the chat: expose an MCP server (see the [tool contract](../../deploy/okd/skills/README.en.md)), add it to the [interface](../../deploy/okd/apps/chat-interface/README.en.md)'s `SOPHIA_MCP_URLS` and open the flow in its NetworkPolicy; to give it a database: a block in [`allow-apps-to-postgres.yaml`](../../deploy/okd/core/postgres/allow-apps-to-postgres.yaml).

## Plugging a module into the cockpit

The chat interface is also the household's **cockpit**: a common frame (module drawer, closed list per role decided by the server) that shows each application in the centre, with its own look (see the [interface](../../deploy/okd/apps/chat-interface/README.en.md)). Hiding a module is not a control: each application keeps its own login and groups. A module joins through five settings, all on its side except the last one; a sixth, optional, gives Sophia the page's context.

| Setting | Content |
|---|---|
| **Shown in the cockpit only** | `Content-Security-Policy: frame-ancestors 'self' <interface origin>` on **every** response of the application (refusals, 401, 404 and static files included), and no more `X-Frame-Options`. The origin is a setting (environment variable or build parameter), never an address written in the repository. Accepted limit: oauth2-proxy's own pages (login, errors) do not carry this header |
| **"Ready" signal** | once the page is usable, `postMessage({type: "sophia.pret", module: "<identifier>"}, <interface origin>)`, only when the page is in a frame, never to `*`. The identifier is **the module's identifier in the interface's list**, not the application's name: a wrong identifier gets the signal ignored, and the cockpit shows its fallback bar after 8 s (real case, fixed in one line). Written in ES5 if old tablets must run it |
| **Summary for "What's new?"** | `GET /api/resume`, **deterministic, no model**, `Cache-Control: no-store`: `{application, version, genere_le, elements: [{id, groupe, titre, detail, date, expire, lien, priorite}]}`, at most 20 items; stable `id`, `groupe` ∈ `a_faire` \| `notification` \| `nouveaute`, `titre` ≤ 80 and `detail` ≤ 160 characters, `lien` = relative path (the interface rebuilds it on the closed list's address), `priorite` 0, 1 or 2 (2 = most urgent). `503 {"etat": "en_attente"}`: the application is simply absent from the panel. The interface validates the schema and never renders this text as HTML |
| **The person's identity** | the interface's **server** calls the route, with the person's access token (`Authorization: Bearer`). Application behind oauth2-proxy: `--skip-jwt-bearer-tokens=true` (the token goes through the main provider's verifier: keys, issuer, audience equal to the application's `client-id`, groups and `--allowed-group`) and `--bearer-token-login-fallback=false` (a refused token gets 403, never a redirect). The application's audience is added to the token by an **audience mapper on the interface's client** (see [identity](../../deploy/okd/identity/README.en.md)), with groups **without path**. **Never `--extra-jwt-issuers`**: it would run OIDC discovery on the identity provider's public address, which pods cannot reach. Application without oauth2-proxy: the route checks the token itself (signature, issuer, dates, audience, issuing client, groups). Static module: the summary is computed by the interface itself, without a token |
| **Network** | ingress to oauth2-proxy (or to the route) from the interface pod only; on the interface side, an egress to that port in a separate egress policy, which adds to its own without cutting anything |
| **Page context** (optional) | `postMessage({type: "sophia.contexte", module: "<identifier>", …}, <interface origin>)` after the "ready" signal, then on each page change, only inside a frame. **Closed-shape fields** only, never free text or personal data (school: subject and topic, identifiers from the index; cooking: page and identifier of the displayed recipe). The interface accepts it only from the module's origin and frame, drops any extra field, and its server re-validates before adding **one line of context** to the application's "Ask Sophia", with no extra right |

Rollout: by **targeted patches** of oauth2-proxy's arguments and of the network rule, guarded by checks of the expected value, a server-side dry run, a check with an invalid token (403 expected) and a two-step rollback. An `apply` of the full manifest would put the image back on a moving tag instead of the built digest. The interface then switches the module to a frame through a setting in its manifest, without a build.

| Module | In the cockpit |
|---|---|
| Cooking | shown in the centre: **in service, verified**; token accepted (403 verified for an invalid token); summary route called by the interface and page context: in service, in acceptance testing |
| School | shown in the centre: **in service, verified** on a computer; logging in again on a phone is under acceptance testing; summary and new items computed by the interface; page context (subject and topic) in service, in acceptance testing |
| Visualisation | shown in the centre, for the administrator only: **in service, verified** on a computer, logging in again on a phone under acceptance testing; token accepted (403 verified); summary route called by the interface: in service, in acceptance testing |
| Office, Communication | shown in the centre: in service, under acceptance testing (see their pages) |
| Shopping | not in the cockpit yet: opened separately |

Sophia opening a module on the right page, without a click (school, cooking, visualisation), and each application's "Ask Sophia" panel, with one conversation per application, are in service, in acceptance testing. Planned: access to applications through the cockpit only, with an exception for the administrator (troubleshooting).
