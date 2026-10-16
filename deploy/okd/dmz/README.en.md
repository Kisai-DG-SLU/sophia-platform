# Web airlock — search and weather (`sophia-dmz`)

First building block of the [Paranoid Airlock](../../../docs/concepts/04-sas-paranoiaque.en.md): the platform searches and reads the web **from an isolated zone** that reaches the Internet but **cannot reach any internal address**. A model fooled by a page therefore cannot make the airlock read the inside of the cluster.

```
interface (conversation API) ─┐
agents ───────────────────────┴→ sophia-web :8000 ─→ SearXNG :8080 ─→ search engines
                                 │ MCP /mcp + REST     (self-hosted metasearch)
                                 ├→ web pages: reduced to Markdown, no scripts
                                 └→ weather data (day-by-day forecasts)
                 egress: Internet 80/443 and cluster DNS only
```

| File | Content |
|---|---|
| `00-searxng.yaml` | SearXNG metasearch: selected engines, JSON output, private instance (no limiter), moderate SafeSearch, strict for protected users (per request) |
| `01-sophia-web.yaml` | `sophia-web` MCP + REST server: ImageStream and BuildConfig in the applications namespace, Deployment and Service in the airlock |
| `02-network.yaml` | NetworkPolicies: deny by default; Internet egress on 80/443 outside private ranges, DNS; ingress to `sophia-web` from the interface and the agents only; SearXNG reachable from `sophia-web` only |

## The `sophia-web` service

The service code is not provided; its contract:

| Tool (MCP) | REST | Role |
|---|---|---|
| `web_search` | `POST /search` | metasearch results, **ranked by reliability** (official and encyclopedic sources first) |
| `fetch_page` | `POST /fetch` | page reduced to Markdown, without scripts or active content; internal and private addresses refused |
| `weather_forecast` | `POST /weather` | day-by-day forecasts (up to 16 days) from an open **data** source: weather websites, rendered in JavaScript, are not readable |

Interface-side rules: search is triggered by default for any information request; sources are cited; `fetch_page` only accepts an address coming from a search result or from the person's message; a tool failure is reported as such, with no invented cause.

## Procedure (administrator)

```bash
oc create secret generic searxng -n sophia-dmz --from-literal=SEARXNG_SECRET="$(openssl rand -hex 32)"
oc policy add-role-to-user system:image-puller system:serviceaccount:sophia-dmz:default -n sophia-apps
oc apply -f 02-network.yaml          # close the airlock first
oc apply -f 00-searxng.yaml
oc apply -f 01-sophia-web.yaml
oc start-build sophia-web -n sophia-apps --from-dir=<sophia-web code> --follow
oc rollout status deploy/searxng deploy/sophia-web -n sophia-dmz
```

The image is built outside the airlock and pulled by it: **no forge credentials in the web-facing zone**.

## Note

A `hostNetwork` pod bypasses NetworkPolicies. Test isolation from an ordinary pod, and never test robustness against a production service.
