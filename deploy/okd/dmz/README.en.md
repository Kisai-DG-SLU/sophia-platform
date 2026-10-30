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

**Weather for a saved place** (in service): `weather_forecast` accepts coordinates with a label, and then skips online geocoding. The interface sends **the centre of the place's municipality**, never the address: the accuracy of a forecast does not justify sending a home's location to an external service. As a second safety net, the service **rounds the coordinates itself to 0.01°** (about 1 km) before passing them on. The "Municipality (postcode)" form is also accepted: the postcode is removed before geocoding then used to check the answer, which says "not found" rather than keeping a namesake.

**Weather fallback cache** (coded and reviewed, not yet in service):

- `PUT /cache/communes`: the interface sends the anonymous list of the municipalities of its saved places (label and coordinates, with no place name, owner or address), at most 50, rounded to 0.01° by the service; it replaces the previous one;
- the route requires a **shared token**, compared in constant time: other pods can reach the service, only the interface must be able to replace the list. The token is in a Secret created by the administrator through a single pipe, never displayed, and never logged;
- every 3 hours, the service preloads D to D+3 for each municipality and keeps the last successful answer, **in memory only**: nothing links a municipality to a person, neither on disk nor in a log;
- if the online source fails, the cached forecast is returned with the time it was obtained, so that the answer says so;
- the time zone database is a pinned dependency, checked at build time.

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
