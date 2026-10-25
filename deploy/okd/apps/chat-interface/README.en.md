# Chat interface — production deployment

Deployment template for a web chat interface in front of the model router, with **no key in the browser** and **mandatory sign-in**. The front-end code is not provided: this directory describes the container, the proxy and the Kubernetes resources.

```
Browser → Route (TLS) → oauth2-proxy :4180 → nginx :8080 ─→ conversation API :8000 ─→ model router (LiteLLM)
                          │ OIDC sign-in          │ static front         │ injected context (persona, profile, date)
                          └→ Keycloak             │ (allow-list)         ├→ PostgreSQL (conversations, profiles, rights)
                                                  │                      ├→ Forgejo (projects = repositories)
                                                  │                      └→ web airlock (search, weather) — ../../dmz/
                                                  └ identity → x-litellm-end-user-id, X-Sophia-User, X-Sophia-Groups
```

| File | Role |
|---|---|
| `Containerfile` | UBI 9 minimal, system nginx and python3, arbitrary UID (OpenShift), logs to stdout/stderr; Python 3.12 and the conversation API's dependencies (same image, sidecar container) |
| `entrypoint.sh` | renders the configuration, refreshes prices in the background (every 30 s while the router is unreachable, then every 10 min), runs nginx in the foreground |
| `render-config.py` | injects the router key into `nginx.conf` (mode 600), never printed; rejects a malformed key |
| `render-pricing.py` | reads the router's prices server-side and writes `pricing.json` (atomic write) for cost display in the front |
| `nginx.conf.in` | template: **allow-list** of served files and of routes relayed to the router, enforced identity headers |
| `sophia-interface.yaml` | ImageStream, BuildConfig, Deployment (oauth2-proxy + nginx + conversation API), Service, Route, NetworkPolicy |

## Safeguards

- **File allow-list**: only `/`, `index.html`, `models.js`, `pricing.json`, `css/`, `js/`, `images/` are served. Without it, the rendered configuration — which holds the key — could be downloaded.
- **Route allow-list**: only `v1/models`, `v1/chat/completions` and `health/liveliness` are relayed. Without it, the router's admin API was reachable with the server's key.
- **Dedicated key**: a router *virtual key*, restricted to the exposed models, with capped budget and rate.
- **Enforced identity**: `x-litellm-end-user-id` comes from oauth2-proxy; headers sent by the client are overwritten. The router tracks spend per person.
- **Server-side context**: in production, `v1/chat/completions` goes through the conversation API, which injects the persona, the person's profile and the date before the router; the browser cannot change them.
- **Web search**: the tool loop (search, page reading, weather) runs in the API, against the `sophia-dmz` airlock. A page can only be read if its address comes from a search result or from the person's message: an address guessed by the model is refused by code.
- **Tools over MCP**: the API is an MCP client; it reads the tool list of every server in `SOPHIA_MCP_URLS` (web airlock, [local tools](../../skills/README.en.md), modules), shows the announcement each tool declares (icon, label), fills reserved parameters itself (protected account) and inserts into the answer, after checking them, the images and maps the tool returns. Adding a tool requires no interface change.
- **Models per role**: `SOPHIA_MODELS_BY_ROLE` (by default, children and guests on the local model only; an account with no known role is treated as a guest). A model sent by the browser outside the list gets an **explicit 403** and nothing goes to the router: no silent substitution. Internal calls (analysis, rephrasing, summary) reuse the already-checked model; the profile only exposes allowed models. Voice uses a separate virtual key (`LITELLM_AUDIO_API_KEY`), limited to the two voice aliases and set by nginx on its routes only: the rule is held by the router, without parsing the form.
- **Slots on the graphics card**: chats take at most 2 of the local server's slots during the day, 1 from 3 a.m. to 7 a.m. (`SOPHIA_LOCAL_CHAT_PLAGES`); school never waits; one more chat waits 60 s at most, then gets a "very busy" message. The browser's background tasks (title, requested summary) carry the `X-Sophia-Tache: fond` header and go to the background alias, as a simple relay, falling back to the main alias if the router or the key refuses it; the compaction summary stays on the main alias, since it is on the path of the person's message.
- **Answer written by the service**: an MCP tool may return `_trace` (a line shown before the answer) and `_fin` (the final answer, shown as is, without calling the model again). The decision stays with the service that knows its data (for instance "nothing planned" for an empty slot): the model can no longer embellish it.
- **Paths declared by tools**: an MCP server declares each tool's path in its metadata (`sophia/parcours`: `express`, `lecture`, `liste`). The chat server picks by rules the tools offered to the model, or calls an express-path tool itself and writes the answer from the service's messages; a server that declares no path keeps the old behavior.
- **Opening an application**: an `application` intent in the analysis, with enumerations built by the server for the person's role; decision in the policy, from a closed, versioned list (`SOPHIA_APPLICATIONS`: identifier, name, base address, allowed pages, roles); the server writes the sentence and a **button**, and the browser only accepts an application button whose address starts with a base from the list. The click opens or reuses a **named tab** per application (a browser blocks opening a tab without a gesture from the person). Reserved for the responsible adults; buttons are removed from the history sent to the model, which must never write an address.
- **Context window**: capped per model (`SOPHIA_CONTEXT_LIMITS`); beyond it, the oldest exchanges are summarised, and an oversized file is refused with a clear message.
- **Conversation API**: listens on `127.0.0.1` only, behind nginx; identity comes from the headers set by nginx.
- **Network**: ingress from the OpenShift router only, to oauth2-proxy; egress to the model router, Keycloak, PostgreSQL, Forgejo, the web airlock, the MCP servers of `sophia-skills` (and of modules) and DNS.

## Prerequisites (secrets)

| Secret | Content |
|---|---|
| `forgejo-build-credentials` | read access to the front repository, for the build |
| `sophia-interface-litellm` | `LITELLM_API_KEY`: dedicated virtual key; `LITELLM_AUDIO_API_KEY` (optional): voice key, limited to its two aliases — when missing, voice uses the pod's key, with a warning at startup |
| `sophia-interface-oauth2` | `client-secret` (Keycloak client) and `cookie-secret` (32 random characters) |
| `sophia-chat-db` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`: conversation database |
| `sophia-chat-forgejo` | `FORGEJO_TOKEN` of a Forgejo service account (`write:repository`, `write:organization`, `read:user`) — optional: without it, only the global project exists |

## Prepared changes

| Change | Content | Status |
|---|---|---|
| **Dedicated namespace** | the interface leaves the applications namespace, where the deployment agent is administrator and could read its Secrets: its own namespace with quota, defaults and closed ingress, ingress of the services it calls **doubled** during the switch (the old source removed a day later), trial through a temporary Route reachable over the VPN only, then the Route switch; the build clones with a **read-only deploy key** over SSH, never with a forge administrator's token | designed, manifests ready, not applied. Limit: the namespace protects from the deployment agent, not from the maintenance agent, which administers the cluster |
| **School on its own address** | a school served under the chat's origin would have all the person's rights on the chat. School moves to its own address, behind its own oauth2-proxy (guests excluded); CORS only covers one API prefix (`/api/store/school/`), for the school's exact origin; dedicated routes for the avatar, reactions and voice, rather than the profile (which would change the persona) or completions (which would open the model); chat cookie without a parent domain; photos with `Cross-Origin-Resource-Policy: same-site` | in three compatible steps: (a) chat side, **in service**; (b) the school, coded; (c) end of the old path |
| **The interface as a requester** | a `deleguer` intent (constrained analysis, rules, confirmation by a click with a single-use token, call to the [dispatcher](../../core/repartiteur/)); the person's token relayed and verified from the start; per-person quotas; approvals of the plan and of commands in the interface; tracking in the chat | designed |

## Note

A `hostNetwork` pod bypasses NetworkPolicies (node traffic is always accepted). Test isolation from a regular pod.
