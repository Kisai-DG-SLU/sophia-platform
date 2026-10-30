# Cooking module — documentation

## What the module does

- **Catalogue** seeded from the household's old spreadsheet (78 recipes: 40 to suggest, 38 archived), recipe card with an adjustable number of diners. By default, only recipes "to suggest" and **in season** are shown (21 days of tolerance at season boundaries).
- **Two ratings**: the recipe's (estimated by the model or taken from the source) and **the household's**, which alone drives rotation — a recipe comes back if rated 8/10 or more and not cooked for 6 weeks; below 6/10, it is excluded; at most 3 rotation slots per week.
- **Per-person meal plan**: several dishes per slot, ready-made or off-catalogue dish, meals eaten out (canteen), holiday mode, children's menus as starter / main / vegetable. A meal becomes "past" after 2 pm or 10 pm.
- **Rule-bound recipe generation**: a permanent pool of new recipes (28), a "with what I have" generation, at most 60 attempts per day; web-inspired recipes cite their sources.
- **Banned** or **downgraded** foods (a weight fading out over 8 weeks), satiety score, sorting.
- **Festive meals**: menu per course, suggestions, shopping; surprise menu, and **secret party** (under acceptance testing): the whole party is hidden from children's accounts, in the meal plan as in the chat.
- **Shopping** aggregated by aisle, ticks shared between household members, undoable history; a tab sends the validated list to the [Shopping module](../courses/README.en.md), which fills a drive-through grocery basket.
- **Import** of a recipe from a link or pasted text: the model turns it into a card, rules check it, the household reviews a preview before saving.
- **Dish photo** generated locally by the platform's `image` MCP tool.
- **Favourite recipes** of the household (in service, under acceptance testing): a star on the recipe card, a search within favourites only (title and ingredients) and adding them straight to the meal plan. Catalogue search ignores accents, case and plurals, and matches the start of words.
- **In the chat**: "what's for dinner tonight?" is answered by the assistant, from the meal plan. The service always announces the chosen slot (`_trace`); if every requested meal is empty, the service writes the answer itself (`_fin`: "Nothing planned… Shall I suggest a dish?"), shown as is: the model can no longer invent a "planned" meal. A secret party hidden from a child gives the empty-slot answer, without a word about the party. From the chat, adults can also open the application on the week's plan or on the shopping tab.

- **In the cockpit** of the interface ([integration contract](../README.en.md#plugging-a-module-into-the-cockpit)): the application is shown in the centre (in service, verified), with `frame-ancestors` limited to the interface on every response and the `sophia.pret` signal (identifier `cuisine`, read-only mode included). Children get the meal plan read-only there. Switching without a click to the meal plan or the shopping tab, when asked to Sophia, is ready, being rolled out.
- **Children's reading limited to the meal plan** (in service, under acceptance testing): a protected account can only read the cards of recipes on the household's meal plan, with no limit in weeks; any other card gets 403; surprise parties are still refused. Adults keep the whole catalogue.
- **Summary for "What's new?"** (`GET /api/resume`, deterministic, `no-store`, at most 20 items, stable identifiers): for adults, today's shopping and next week's meal plan to complete (more urgent from Friday); for children, today's menu only. Route in service, not yet called by the interface.

- **Ingredient table** (under acceptance testing): calories, season and price of each ingredient, to **compute** the cost, calories and season months of recipes instead of estimating them (see below).

- **New-version notice** (in service): every response carries the image version (`X-Sophia-Version`, the commit); a page opened before a build shows a "Reload" banner, never during typing or a pending request, never an automatic reload. In the shopping tab, a single banner shows, Cooking's: the Shopping module's version is never relayed there.

Planned: checking generation caps on computed values.

## Architecture

```
browser ─VPN─→ router ─→ [ oauth2-proxy │ application ]   (applications namespace)
                               │            │  dedicated database ─→ shared PostgreSQL 18
                               │            │  LiteLLM (sophia-local, strict JSON)
                               │            │  image MCP tool (sophia-skills)
                               │            │  web airlock (search, page reading)
                               │            └─ Shopping module MCP (closed tool list)
chat interface ─MCP (read)─→ application
interface (server) ─person's token─→ oauth2-proxy ─→ /api/resume
Shopping module ─MCP (limited write)─→ application
```

| Item | Choice |
|---|---|
| Pod | two containers: **oauth2-proxy** (Keycloak SSO, PKCE) and the application (FastAPI, Jinja2 templates, htmx), listening on `127.0.0.1` only; identity arrives through the header set by the proxy, a request without it is refused |
| Image | UBI minimal, Python 3.12, non-root, nothing written to disk, `seccomp` `RuntimeDefault`, capabilities dropped |
| Data | a **dedicated database** in the shared PostgreSQL 18, own role, schema created at start; photos stored in the database; no persistent volume |
| Variety | computed on the recipe's identity fields (cooking method, main ingredient, sides), without a vector database |
| Access | two realm groups: full access, protected accounts (read-only, limited to the recipes on the meal plan, never photo generation). oauth2-proxy also accepts the person's token relayed by the interface's server (`--skip-jwt-bearer-tokens`, the application's audience added by a mapper on the interface's client, never `--extra-jwt-issuers`); a refused token gets 403, without a redirect (`--bearer-token-login-fallback=false`): in service, 403 verified for an invalid token |
| Timeouts | 300 s at the proxy and the Route: the local model takes several tens of seconds |
| Network | closed list: ingress from the router to the proxy, from the interface (from its own namespace only) to the read MCP and to the proxy (summary), from the Shopping module to the write MCP; egress to the model router, the identity provider, PostgreSQL, the `image` tool, the web airlock, the Shopping module, DNS |
| Build | Docker BuildConfig from the internal forge, image trigger on the Deployment; a least-privilege CronJob starts one build per new commit |

### Exposed MCP servers

| Server | Open to | Tools | Rights |
|---|---|---|---|
| read | the chat interface only | `menu_du_jour`, `menu_semaine`, `recette`, `liste_courses` | read; identity is **injected by the interface** (`sophia/injecte`), only household members are served; no health data or settings leave it |
| drive | the Shopping module only | `listes_drive`, `marquer_commandee` | read validated lists, mark a list as ordered |

The other way round, the module calls the Shopping module's MCP with a **closed tool list** and arguments it builds itself.

### Model usage

All through the model router, with a dedicated virtual key and the person's identity (`x-litellm-end-user-id`), in **strict JSON**:

| Use | Temperature |
|---|---|
| recipe generation | 0.9 |
| recipe import (turning a page into a card) | 0.1 |
| short English prompt for the photo, length checked | — |

Generation and the ingredient table are **background tasks**: they use the router's background alias, which leaves priority to chat, falling back to the main alias as long as the background alias is not open to the module's key (re-read every 10 minutes, without restart). Import and photo, started by a click, stay on the main alias. The model actually used is recorded in the generation log.

## Rules: the model proposes, rules decide

A generated recipe is JSON; a deterministic validator decides:

- schema, units, cooking method, protein, season, **a single** main ingredient;
- banned foods, compared **as whole words** (a ban does not fire on a word that contains it);
- caps: 450 to 650 kcal, preparation ≤ 20 min, total ≤ 40 min, ≤ €5 per serving, estimated rating ≥ 6.5;
- new title, at most 7 recipes per protein, and **different on at least 2 criteria out of 4** from every existing recipe;
- downgraded foods taken into account.

A rejection goes back to the model **with its reasons**, at most 3 attempts; every attempt is logged (accepted, rejected, error, duration).

Other checks around the model's output:

- **web search**: the query is built by rules, never by the model; at most 2 pages read, truncated to 2,500 characters, from an **allow-list of recipe sites**, through the web airlock (the only, indirect, path to the Internet); without the airlock, generation goes on without inspiration;
- **cited sources** must be pages actually read;
- on **import**, an ingredient absent from the source is dropped and flagged "to check";
- bans only apply to **invented** recipes, not to dishes entered by hand or imports.

**Health data**: never committed nor sent to the model; only general nutritional constraints go through.

### Secret party

A checkbox when creating a party, which implies the surprise menu. Children's accounts do not see the party in the meal plan; the read MCP server **keeps quiet** about it as soon as the injected identity is a child's **or is missing** (caution) — today's menu, the week, shopping. An identified adult sees it, with "Surprise!" for the menu.

## Ingredient table: open data, the model chooses among candidates

| Data | Source |
|---|---|
| Calories | Ciqual table (ANSES, French food agency, open data), versioned with the module; ≈ 3,100 foods with energy, kcal computed from nutrients per the EU labelling regulation when missing (median gap 0.2 % on foods that have both) |
| Season | ADEME's seasonal fruit and vegetable calendar (73 products, season months) |
| Price | **real drive prices** when the household has already bought the product (the [Shopping module](../courses/documentation.en.md)'s `prix_reference` tool), otherwise estimated by the model; weight of a piece estimated |

- **Rules first**: candidates are found without the model (name words, label before the comma, raw foods first; a small lexicon of compound names: "pomme de terre" (potato) is not "pomme" (apple)); the model (`sophia-local`, temperature 0.1, batches of 8) **chooses among those candidates or none**, and estimates price and weight; an answer outside the candidates is dropped, bounds are checked (€0.2 to €200/kg, 0.1 to 5,000 g).
- A value **corrected by hand** is never overwritten, neither by the model nor by a drive price.
- **Computation**: grams per unit (spoon, clove, bunch, pinch, centilitre…); calories and cost **replace the estimate only if everything that counts is known**, the original estimate is kept and comes back if a value is missing; the card marks an estimated value with "≈".
- **Season**: the months when all the dish's fruit and vegetables are in season; a dish labelled "winter" in the old spreadsheet but made of carrots becomes seasonal in October.
- **Real prices**: `prix_reference` is called once a day with all the recipes' ingredients; checks: a single price key, bounds, a reading less than six months old, and a **processed product** (peeled, tinned, frozen, juice…) **dropped for a fresh fruit or vegetable**. Weight, volume and pieces are **never converted** — a line by volume takes the price per litre, a piece the price per piece, a weight the price per kilo (a piece is weighed with the weight of a piece), otherwise no cost for that line and the recipe's estimate stays. Priority: price entered by hand, then drive price, then estimate.
- A background task fills in new ingredients (seed, imports, generations) and recomputes recipes: ≈ 250 ingredients in about twenty minutes; 5 rare ingredients without a candidate must be entered by hand.

## Measurements

- First real run on the local model: 3 recipes accepted in 5 min.
- Dish photo: ≈ 30 s (CPU); recipe import: 1 to 2 min.
- Application: 20 m CPU and 96 Mi requested, at most 500 m and 256 Mi.
- Tests: pytest against a real PostgreSQL, and a fake Shopping module.

## Lessons

- The previous prototype **left the checks to the model**: banned foods present, caps exceeded, drifting vocabulary. What works: the model proposes, rules decide, and the reasoned rejection goes back to the model.
- A ban list compared as substrings gives false positives: compare whole words.
- The catalogue seed is **versioned** and reapplied by version number: a column mix-up in the normalisation script was fixed by replaying a version.
- A webhook from the forge to the cluster API was blocked by the egress firewall (private addresses refused): replaced by a least-privilege CronJob, one build per new commit, never rebuilding a failed build in a loop.
- Recipe sites rendered in JavaScript cannot be read without a browser: fallback by pasted text; lead, read their structured data (`ld+json`).
