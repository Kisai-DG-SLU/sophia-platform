# Cooking module — documentation

## What the module does

- **Catalogue** seeded from the household's old spreadsheet (78 recipes: 40 to suggest, 38 archived), recipe card with an adjustable number of diners. By default, only recipes "to suggest" and **in season** are shown (21 days of tolerance at season boundaries).
- **Two ratings**: the recipe's (estimated by the model or taken from the source) and **the household's**, which alone drives rotation — a recipe comes back if rated 8/10 or more and not cooked for 6 weeks; below 6/10, it is excluded; at most 3 rotation slots per week.
- **Per-person meal plan**: several dishes per slot, ready-made or off-catalogue dish, meals eaten out (canteen), holiday mode, children's menus as starter / main / vegetable. A meal becomes "past" after 2 pm or 10 pm.
- **Rule-bound recipe generation**: a permanent pool of new recipes (28), a "with what I have" generation, at most 60 attempts per day; web-inspired recipes cite their sources.
- **Banned** or **downgraded** foods (a weight fading out over 8 weeks), satiety score, sorting.
- **Festive meals**: menu per course, suggestions, shopping.
- **Shopping** aggregated by aisle, ticks shared between household members, undoable history; a tab sends the validated list to the [Shopping module](../courses/README.en.md), which fills a drive-through grocery basket.
- **Import** of a recipe from a link or pasted text: the model turns it into a card, rules check it, the household reviews a preview before saving.
- **Dish photo** generated locally by the platform's `image` MCP tool.
- **In the chat**: "what's for dinner tonight?" is answered by the assistant, from the meal plan.

Planned: an ingredient table (season per month, price, calories) to **compute** cost, calories and season instead of estimating them.

## Architecture

```
browser ─VPN─→ router ─→ [ oauth2-proxy │ application ]   (applications namespace)
                               │            │  dedicated database ─→ shared PostgreSQL
                               │            │  LiteLLM (sophia-local, strict JSON)
                               │            │  image MCP tool (sophia-skills)
                               │            │  web airlock (search, page reading)
                               │            └─ Shopping module MCP (closed tool list)
chat interface ─MCP (read)─→ application
Shopping module ─MCP (limited write)─→ application
```

| Item | Choice |
|---|---|
| Pod | two containers: **oauth2-proxy** (Keycloak SSO, PKCE) and the application (FastAPI, Jinja2 templates, htmx), listening on `127.0.0.1` only; identity arrives through the header set by the proxy, a request without it is refused |
| Image | UBI minimal, Python 3.12, non-root, nothing written to disk, `seccomp` `RuntimeDefault`, capabilities dropped |
| Data | a **dedicated database** in the shared PostgreSQL, own role, schema created at start; photos stored in the database; no persistent volume |
| Variety | computed on the recipe's identity fields (cooking method, main ingredient, sides), without a vector database |
| Access | two realm groups: full access, protected accounts (read-only, never photo generation) |
| Timeouts | 300 s at the proxy and the Route: the local model takes several tens of seconds |
| Network | closed list: ingress from the router to the proxy, from the interface to the read MCP, from the Shopping module to the write MCP; egress to the model router, the identity provider, PostgreSQL, the `image` tool, the web airlock, the Shopping module, DNS |
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
