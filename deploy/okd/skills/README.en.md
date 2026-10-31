# Local tools — MCP servers without Internet (`sophia-skills`)

The "tools" zone of the [architecture](../../../docs/architecture.en.md): MCP servers that the interface (and the agents) offer to the model, and that **compute** instead of letting the model guess — positions, distances, maps, images. None has egress to the Internet: their data is prepared from the node and mounted read-only.

| Zone | What goes there | Network egress |
|---|---|---|
| [`sophia-dmz`](../dmz/) | what fetches from outside: web search, page reading, weather | Internet (80/443) only |
| **`sophia-skills`** | **local tools**: geography, images (protection rules), downloaded official sources, the person's files | **none to the Internet** (DNS; image models; for the "files" tool: the identity provider and the internal port of Files) |
| [`sophia-inference`](../inference/) | the models: text, voice, image generator and classifier | none |

```
interface (chat API) ──MCP :8000──→ sophia-geo    (lieu, distance, carte)   ← /data/geo (read-only)
                     └─MCP :8000──→ sophia-image  (image) ──→ sophia-image-gen (sophia-inference)
modules (e.g. cooking) ─MCP :8000──→ sophia-image only        generator :1234, classifier :8001
```

## Files

| File | Content |
|---|---|
| `00-namespace-guardrails.yaml` | `ResourceQuota`, `LimitRange` |
| `01-network.yaml` | deny all; ingress: the interface → 8000 (pods `sophia-mcp: "true"`), a module → `sophia-image` only; egress: DNS, `sophia-image` → `sophia-image-gen` |
| `02-storage.yaml` | local PV `/var/mnt/models/skills` (same volume as the models, separate directory) and PVC `pvc-skills-data`, read-only |
| `03-geo.yaml` | `sophia-geo`: `lieu`, `distance`, `carte` tools |
| `04-image.yaml` | `sophia-image`: `image` tool; models in [`../inference/06-image.yaml`](../inference/06-image.yaml) |
| `fetch-geo-data.sh`, `geo_build.py` | geographic data, prepared on the node in a throw-away container; the previous version stays in place if preparation fails |

Each MCP server carries the label `sophia-mcp: "true"`, listens on 8000 (`/mcp`, stateless *streamable HTTP*) and answers on `/health`; the interface adds it to its list of MCP servers.

## Common contract: announcements and display

The servers' code is not provided; their contract:

- each tool declares **its announcement** in its MCP metadata (`sophia/annonce`: icon, label, argument to show — "📍 Lieu: Lyon"): the interface displays it while answering without knowing the tool in advance;
- `sophia/injecte`: parameters filled in by **the interface** itself, never by the model (e.g. `protected` = protected account, taken from the session);
- `sophia/delai_s`: the tool's timeout (queueing included);
- a result may carry `_affichage` (`image/png` in base64 or `image/svg+xml`, with a title): the interface **checks** the content then inserts it as is in the answer; the model only gets the description, not the image;
- a failure is a readable `error`, which the model reports as is;
- `sophia/jeton`: the tool acts under the person's identity and requires their relayed token; the interface sends it only to the servers on its closed list, and never offers these tools to the model: it calls them itself after the rules have decided ([Identity Relay](../../../docs/concepts/12-relais-identite.en.md));
- `sophia/contenu`: the result contains the content of one of the person's documents; the interface gives it only to a local model and removes it from any other call ([Models by Role](../../../docs/concepts/13-modeles-par-role.en.md)).

## Geography — `sophia-geo`

| Tool | Role |
|---|---|
| `lieu` | town, municipality or French postcode: name, country, region, coordinates, population, source; several results if the name is ambiguous |
| `distance` | great-circle distance between two places; a place may also be given by its coordinates (below) |
| `carte` | **exact** SVG map (real borders, places at their coordinates), optional route and distances, "simple" or "bd" style (old map, comic-book look) |

Open data: French municipalities (official municipalities API), GeoNames (towns over 1,000 inhabitants, French names), Natural Earth country borders. ≈ 230 MB downloaded, ≈ 8 MB kept. Update: rerun `fetch-geo-data.sh`, then restart `sophia-geo`.

Places the tool receives first go through the interface's guards: a place extracted by the model is only kept if it appears in the person's message or is the name of a saved place (see [the interface](../apps/chat-interface/README.en.md)).

**Places by municipality and postcode, or by coordinates** (in service):

- the "Municipality (postcode)" form, the one the interface sends, only keeps the municipalities with that postcode: "Exampletown (00000)" answers "not found" rather than pointing to a namesake elsewhere;
- `distance` and `carte` accept a place of the form `{"nom": …, "latitude": …, "longitude": …}`. It is **the interface server** that inserts it, in place of the name of a saved place, like its other reserved arguments; a place object coming from the model is refused. The answer gives the place's **name** and its municipality, **never its coordinates**, and the map does not label it with an address.

**Local address base** (coded and reviewed, not yet in service), to geocode once the address of a place saved in a profile:

- open data from the national address base, per département, prepared on the node by `fetch-geo-data.sh --ban <départements>`; the list of départements is given at launch and **is written in no versioned file**; SQLite database with a full-text index, opened read-only; the previous base stays in place if the preparation fails;
- **candidates route outside MCP** (`POST /api/adresse/candidats`), called only by the interface server when a place is saved, never by the model: the address is in the request body, never in the URL, a log or an error message;
- deterministic ranking (postcode typed, exact number then the nearest in the street, then the full-text rank); **the person chooses** among the candidates; a département not loaded answers an empty list, and the interface falls back on the municipality;
- updated by hand, at most once a month: a place is only geocoded when it is saved, and its coordinates are kept with it.

Outside the covered country, a *plus code* (Open Location Code) entered by the administrator is decoded locally by the interface, sending nothing out. Tools and weather work on the municipality and its coordinates, never on the address.

## Images — `sophia-image`

`image` tool: the person's request (in French, verbatim) and the English prompt written by the model, a style (`illustration`, `coloriage` (colouring page), `aquarelle` (watercolour), `bd` (comic), `photo`); 512 × 512, one generation at a time on CPU (about ten seconds, a second request waits).

**Deterministic checks, in the server and not in the model:**

1. **before**: rules check **both the request and the prompt** (the model cannot slip in content the person did not ask for); a sexual subject with a child or an underage age: **always refused**; a sexual subject with a named real person: refused; for a **protected account** (child): nothing sexual, no nudity, violence, weapons, horror, drugs, alcohol; a negative prompt is enforced on every generation;
2. **after**: for a protected account, every image goes through the classifier; above the threshold, a new attempt with another seed, then refusal; **if the classifier is unavailable, nothing is shown** to a protected account;
3. **on display**: the interface checks the received content again.

Each image comes with the model's name and licence. SDXL-Turbo licence: **non-commercial** use (see [`../inference/`](../inference/)).

## The person's files — `mcp-fichiers`

Status: in service (search) and deployed (content reading, acceptance test pending); the reference installation's code and manifests are not published, their contract and rules are, here. Module: [Office](../../../docs/modules/bureautique/documentation.en.md).

| Tool | Role |
|---|---|
| `chercher_fichiers` | items found by name (or the most recent ones), with path, date, type, "editable", never a URL |
| `details_fichier` | one item and its readable path |
| `lire_fichier` | a document's text, extracted without execution (bounded XML archives, text-only PDF), truncated, flagged `contenu_sensible` |

HTTP route next to the MCP: `GET /api/resume`, the Files summary for the interface's "What's new?" panel (files shared with the person, modified in the last 14 days, 20 at most; Files does not expose the sharing date). Same relayed token and same audience as the tools; 401 without a valid token. In service, checked without a token; the call from the interface is planned.

- **Read-only, under the person's identity**: token relayed by the interface, verified (signature, issuer, expiry, audience, originating client, groups), then **exchanged** for a token issued to the tool; Files introspects it and applies its own permissions. No service account that reads everything. One MCP session per call; no token logged (the HTTP client's log brought down to WARNING, so that the person's search does not appear in it).
- **Network**: ingress from the interface only; egress to DNS, the identity provider (public keys and exchange) and the reserved internal port of Files (GET only), **nothing else**.
- **Build in a separate namespace** (`sophia-skills-build`): the tool receives the family's tokens, so no agent may change its BuildConfig or its image. That namespace has **no RoleBinding to an agent account**; quota of one build at a time; no ingress.
- **Build EgressFirewall with a final deny**: cluster Services and pods, **the cluster API** (control-plane nodes, on the API port; without this rule the build hangs at clone, unable to update its status), PyPI; nothing else.
- **Lesson: start inside the base image itself.** A minimal image may lack the time-zone database: a named time zone then raises an exception at import, and the pod crash-loops (`Recreate` strategy: the tool is cut off). Remedies: the time-zone database as a pinned dependency, an import that does not break the server (the route concerned answers 503, the rest carries on), an import check in the Containerfile that fails the **build** rather than the pod, and tests without a system database.
- **Base image** that already contains Python, **imported through the internal registry** (ImageStream with `referencePolicy: Local`, pinned by digest): the build pod pulls nothing from the vendor and installs no system package. **Python dependencies pinned by hash** (`--require-hashes`, binary wheels only). Binary source (`git archive` of the commit), no trigger: a new image replaces the pod only after a new digest has been committed and applied.

## Variables

| Variable | Role |
|---|---|
| `${MODULE_APP}` | `app` label of a module allowed to reach the `image` tool (one block per module) |
| `${NODE_ADDR}` | node administration address (data preparation) |
| `${NODE_NAME}` | node carrying the volume (`oc get nodes`), in `02-storage.yaml` |
| `${GEO_SRC_DIR}`, `${IMAGE_SRC_DIR}` | directories with the servers' code (binary builds) |

## Procedure (administrator)

1. Data: copy `fetch-geo-data.sh` and `geo_build.py` to the node, then `sudo bash fetch-geo-data.sh`.
2. Image models: see [`../inference/`](../inference/).
3. `00` to `04`: `--dry-run=server`, then `apply`; builds: `oc start-build sophia-geo` and `sophia-image` (`--from-dir`).
4. Interface: add `http://sophia-geo.sophia-skills.svc:8000/mcp` and `http://sophia-image.sophia-skills.svc:8000/mcp` to its list of MCP servers.
5. Check: `/health` of both servers is `ok`; from the interface, "distance Paris – Lyon" (≈ 392 km, `distance` tool) and an image on a protected account.
