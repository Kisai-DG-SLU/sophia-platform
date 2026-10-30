# Shopping module — documentation

## What the module does

- **Inputs**: the Cooking module's validated lists (each imported only once, then marked "ordered" in return), free input, **recurring items** (every N days or on given weekdays), favourites.
- **Analysis then choice**: the model understands each line; rules choose the product; a new product chosen automatically carries an "auto" tag.
- **Actions** on a list: choose, search something else, adjust, remove or restore a line, **validate** (by either adult), mark as ordered, delete.
- **Real prices and offers**, read in the remote browser, automatic queued search.
- **Filling the real basket** on request, and an **express basket** from the chat ("add some milk"), one question at a time. Each MCP tool declares its **path** in its metadata (`sophia/parcours`: `express`, `lecture`, `liste`): the chat picks by rules, calls the express tools itself and writes the answer from the service's messages, without the model rephrasing. The service itself refuses an account outside the household.
- **Model per use**: the express purchase, which the chat waits for, stays on the main alias; non-urgent lists go through the background alias, falling back to the main alias if the router refuses it (unknown alias or not allowed for the key).
- **Reference prices** for the Cooking module's ingredient table: **read-only** MCP tool `prix_reference` (see below).

- **New-version notice** (in service): the fallback page shows a "Reload" banner when the image has changed, never during unsent typing, and keeps modified fields across the reload; never inside a frame: in the Cooking module's shopping tab, only Cooking's banner shows.

Planned: several stores, comparison between chains, a signal when a site becomes unreadable.

## Architecture

```
Cooking module ─MCP─┐
chat ───────────MCP─┼→ service (applications namespace)   ──→ shared PostgreSQL 18 (own schema)
fallback page ──────┘    │ LiteLLM (sophia-local, strict JSON)
                         └←── readings ── remote browser extension (airlock, filtered Internet egress)
                                              └──→ store site (session opened by the human)
```

| Item | Choice |
|---|---|
| Service | Python application and **oauth2-proxy** (SSO, group for adults; trust in `X-Forwarded-*` headers limited to the router, on this oauth2-proxy as on the remote browser's); internal MCP server, reached only by the Cooking module and by the interface from its own namespace; a port reserved for readings, open to the browser pod only; a 13-table schema (products, mappings, lists, lines, price readings…) |
| Remote browser | in the **airlock** (`sophia-dmz`): Chromium + Xvfb + noVNC, non-root, no service account token, behind SSO and VPN |
| Browser policies | domain allow-list (the store, its anti-bot service, the service); password, card and address managers **disabled** |
| Extension | Manifest V3, **no stealth**: it reads data the page has already received, keeping a closed list of fields only, and fills the basket through the site's normal call |
| Store session | **credentials are never known** to the service, the repository or the logs: the human signs in in the remote browser (e-mail code, captcha); only the session cookie persists, on a node-local volume (accepted trade-off) |
| Write rights | identity is **injected by the interface** (`sophia/injecte`) and checked against the household's adults; on the page it comes from the proxy header, and a form coming from another site is refused (`Sec-Fetch-Site`) |
| MCP tools | ≈ 25: read (search a product, view basket, favourites, purchase state, recurring items, reference prices) and write (add, import Cooking lists, analyse, choose, brand policy, adjust / remove / restore a line, validate, fill the basket, express purchase…); express tools declare a 60 s timeout |
| Build | Git BuildConfigs; a CronJob only rebuilds an image when its files changed |

## Rules: the model understands, it does not choose

The model gets lines in batches of 20 and returns, in **strict JSON**, for each one: the generic product, quantity, unit, requested brand, search words, 0 to 3 synonyms. Its output is checked: exact identifiers, bounds, known unit, **brand accepted only if written in the line**; a reasoned rejection goes back once to the model, at most 3 invalid answers per line.

The choice is **deterministic**:

1. candidates: a label is kept if it contains all the words of a phrasing; the product family kept is first that of labels starting with a search word, then the largest;
2. the household's brand policy, per product: required, preferred, store brand by default, budget line;
3. then least waste, then **price per kilo or litre**, then price; never comparing weight, volume and pieces;
4. at most 12 items per line, alert beyond 25 % rounding.

## Reference prices (`prix_reference`)

Read-only MCP tool, called once a day by the Cooking module, at most 300 names. For each name, **exactly one** of three keys `prix_kg`, `prix_litre` or `prix_piece` (according to the selling unit), with the item price, its label, its barcode, the source and the reading date; a name without a known price returns no line.

- **No call to the store**: database reading of readings already taken by the browser;
- **regular price**, without offers: a temporary offer would distort a reference;
- **only products already chosen by the household** (remembered choice, otherwise the product of the last validated list): no choice made for the household on a product never bought — the price per kilo depends on the brand taken;
- names matched **without a model**, with the same search words as lists; between two generic products, the most recent choice wins;
- weight, volume and pieces never converted into one another (1 l is not 1 kg); the returned label lets the Cooking module see which product a price comes from.

## Before any action on the basket

- the store basket is **read first**; unreadable, nothing is touched;
- **never lower a quantity**, nothing is sent for a product already present in sufficient quantity;
- every addition is **checked** against the quantity seen on the site; 3 to 6 s per item, at most 60 items, stop at the first refusal;
- never a time slot, a payment or emptying the basket;
- in express mode, "added" is only said after the site confirms;
- **no anti-bot circumvention**: at the first challenge, stop and signal; only a human in a real browser gets through;
- human volume (a few dozen searches a week), personal use; the page shows no deep link nor image from the store site;
- personal fields masked in diagnostic logs.

## Measurements

- 134 tests (real PostgreSQL, real MCP transport, fake model router, fake Cooking module).
- ≈ 200 products read for a common search ("milk"); ≈ 320 usual household products.
- Example choice: the pack of 20 at €1.69/l rather than the pack of 12 at €1.73/l.
- Express purchase served in ≈ 30 s; browser capped at 1 CPU and 2 Gi.

## Lessons

- A store call "same quantity" acted as a **toggle** and removed products from the basket: hence the "read first", "never lower" rules.
- Letting the model filter candidates made it miss the cheapest pack: deterministic filter.
- "The largest family" alone picked tomato purée for tomatoes: first the labels starting with the searched word.
- The extension's background script stayed cached in the kept profile: bump the extension version on every change.
- After a challenge at start-up, the extension stayed silent until a page was reopened: a page is reloaded every 5 min.
- A repeated `ingress:` key in a YAML file silently erases the first one.
- A changing site can break reading or filling: this is accepted, the failure is **visible**, never a silent wrong purchase.
- A reference price inherits past choices: a product chosen by mistake before a fix (a tin for a fresh vegetable) gives a wrong price per kilo until the next right choice. Hence the label returned with every price.
