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
- **Conversation API**: listens on `127.0.0.1` only, behind nginx; identity comes from the headers set by nginx.
- **Network**: ingress from the OpenShift router only, to oauth2-proxy; egress to the model router, Keycloak, PostgreSQL, Forgejo, the web airlock and DNS.

## Prerequisites (secrets)

| Secret | Content |
|---|---|
| `forgejo-build-credentials` | read access to the front repository, for the build |
| `sophia-interface-litellm` | `LITELLM_API_KEY`: dedicated virtual key |
| `sophia-interface-oauth2` | `client-secret` (Keycloak client) and `cookie-secret` (32 random characters) |
| `sophia-chat-db` | `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`: conversation database |
| `sophia-chat-forgejo` | `FORGEJO_TOKEN` of a Forgejo service account (`write:repository`, `write:organization`, `read:user`) — optional: without it, only the global project exists |

## Note

A `hostNetwork` pod bypasses NetworkPolicies (node traffic is always accepted). Test isolation from a regular pod.
