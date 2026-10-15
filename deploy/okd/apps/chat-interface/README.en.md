# Chat interface — production deployment

Deployment template for a web chat interface in front of the model router, with **no key in the browser** and **mandatory sign-in**. The front-end code is not provided: this directory describes the container, the proxy and the Kubernetes resources.

```
Browser → Route (TLS) → oauth2-proxy :4180 → nginx :8080 → model router (LiteLLM)
                          │ OIDC sign-in          │ static front (allow-list)
                          └→ Keycloak             │ router key injected server-side
                                                  └ identity → x-litellm-end-user-id
```

| File | Role |
|---|---|
| `Containerfile` | UBI 9 minimal, system nginx and python3, arbitrary UID (OpenShift), logs to stdout/stderr |
| `entrypoint.sh` | renders the configuration, then runs nginx in the foreground |
| `render-config.py` | injects the router key into `nginx.conf` (mode 600), never printed; rejects a malformed key |
| `render-pricing.py` | reads the router's prices server-side and writes `pricing.json` for cost display in the front |
| `nginx.conf.in` | template: **allow-list** of served files and of routes relayed to the router, enforced identity headers |
| `sophia-interface.yaml` | ImageStream, BuildConfig, Deployment (oauth2-proxy + nginx), Service, Route, NetworkPolicy |

## Safeguards

- **File allow-list**: only `/`, `index.html`, `models.js`, `pricing.json`, `css/`, `js/`, `images/` are served. Without it, the rendered configuration — which holds the key — could be downloaded.
- **Route allow-list**: only `v1/models`, `v1/chat/completions` and `health/liveliness` are relayed. Without it, the router's admin API was reachable with the server's key.
- **Dedicated key**: a router *virtual key*, restricted to the exposed models, with capped budget and rate.
- **Enforced identity**: `x-litellm-end-user-id` comes from oauth2-proxy; headers sent by the client are overwritten. The router tracks spend per person.
- **Network**: ingress from the OpenShift router only, to oauth2-proxy; egress to the model router, Keycloak and DNS.

## Prerequisites (secrets)

| Secret | Content |
|---|---|
| `forgejo-build-credentials` | read access to the front repository, for the build |
| `sophia-interface-litellm` | `LITELLM_API_KEY`: dedicated virtual key |
| `sophia-interface-oauth2` | `client-secret` (Keycloak client) and `cookie-secret` (32 random characters) |

## Note

A `hostNetwork` pod bypasses NetworkPolicies (node traffic is always accepted). Test isolation from a regular pod.
