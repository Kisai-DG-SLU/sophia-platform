# School module — documentation

## What the module does

- **Paths** per level (from primary to the end of lower secondary) and subject: lessons, practical work at home, challenges, stars and badges; ≈ 800 activities published today.
- **Mental arithmetic drills** on a list of calculations written in the content (`faits:`), with the same spaced repetition, timer and replay of misses as the times tables: 17 drills, 314 calculations, following each sheet's methods and examples. No random generator, to stay faithful to each lesson's numbers.
- **Geometry figures**: 29 SVG figures in 15 lessons, inserted after the passage they illustrate, without changing the text.
- **Review mode** for the administrator: everything is open, nothing is recorded, a banner says so in every place; a child keeps their locks. It is not a security barrier (all the content is already in the page), but the means to validate what one is asked to validate.
- **Avatar** shared by the chat and the school (a drawing, or a small photo). Planned (coded, not deployed): the chosen drawing is stored as a small image in the chat profile, like a photo; the school keeps the catalogue, and the old `/ecole/` path will become a redirect to the school's address.
- The child's **progress log**, and a **read-only record book** for parents.
- **Exercise sheets** (statement, answers, self-assessment) and linked videos.
- **Report book** from the real school, copied in by the child: marks, reports, averages, spreadsheet import, curves; in primary, **skills** (not acquired, partly, acquired, exceeded), without marks or comparison.
- **"Ask Sophia"**: a hint on the current activity, and opening the school from the chat (button in the answer, link built by the server).
- Photographed **slate dictation** and **reading sheet**, read by the local model (vision).
- `carnet_scolaire` tool in the chat: it only reads the log of the child who is talking; the verdict (congratulations, encouragement…) is **computed by the server**.

- **New-version notice**: a tablet stays open for days; the build writes a fingerprint of the engine (`version.json`, served without cache) and each sync a fingerprint of the content. The page compares on load and when the tab regains focus, and shows a "Reload" banner, never during an exercise or a dictation, never reloading by itself. A lesson published without a build also triggers the notice.
- **Older browsers** (Safari 15.4 and later): before writing anything, the build parses the engine as ES2021 and rejects a list of APIs and CSS rules missing from Safari 15; a rejected engine fails the build without erasing the built version, and the image in service stays.
- **Publishing content without rebuilding the image**: the `contenus` container syncs the repositories read-only every minute and keeps the live version if the new one is invalid (incident fixed, see lessons).

Planned: a decimal-point key for decimal and fraction calculations, a sharing version with a recorded open-licence synthetic voice, MCP tools for progress and opening, the report book served over MCP with a signed token limited to the child.

## Architecture

```
browser ─VPN─→ school address (Route, TLS) ──→ school pod (applications namespace)
                                                ├ oauth2-proxy : its own sign-in (the school's SSO client, no guests)
                                                ├ site         : nginx, GET/HEAD only
                                                └ contenus     : Git sync every minute
                                                                   → atomic switch of a "current" link
        └── school calls ──→ chat API, /api/store/school/ prefix only (CORS for the school's exact origin)
            progress, report book, photos (interface database); hints, photo reading and voice by local models
```

| Item | Choice |
|---|---|
| Pod | one image, **three containers** (sign-in, site, content), a Route to its oauth2-proxy; the internal Service is reached by the interface pods only (content index, avatar catalogue) |
| `site` | unprivileged nginx, `GET`/`HEAD` only, strict headers; serves the engine and a **fallback content built into the image** |
| `contenus` | fetches over SSH (read-only deploy key, the pod's only secret) a public content repository and an optional private one, **checks**, rebuilds, then switches a `current` link at once in a shared volume; invalid content or unreachable repository: the live version stays, the error is published in a status file |
| Build | two-stage Docker (UBI 9, Node.js); only an **engine** change requires a build, content goes through Git |
| Identity | its **own oauth2-proxy** and its own Keycloak client, same realm as the chat; roles: administrator, guardians (parents), protected (children); no guests. Why: a school served under the chat's origin would have all of the person's rights over the chat. The school's CSP allows only the chat's origin; re-authentication goes through the chat's sign-in, returning to the school. See [the interface](../../../deploy/okd/apps/chat-interface/README.en.md) |
| Data | progress and report book in the interface database (event table, profile); nobody writes in someone else's log |
| Opening from the chat | intent analysis (model, JSON schema) recognises "school"; a **deterministic policy** allows the `ouvrir_ecole` action; the link, to the school's address, is built by the server from the school index; the browser turns it into a button, and the model's instructions contain no address |

### Content format

`contenus/<subject>/<level>/<module>/`, one YAML file per module and level. Activity types: lesson (Markdown with YAML header), practical work, multiple-choice challenge, "click the word", "fill in", slate dictation, reading sheet. Required fields: `id`, `type`, `titre`, `notions`, `source`, `licence`, `redistribuable`.

The build **refuses** any invalid content: correct answer missing from the choices, unknown notion, missing licence. The private repository adds modules without replacing anything; only what is marked `redistribuable: true` goes into the sharing version, which keeps only links to the rest.

## Public version

- **A separate public repository**, which contains only the **built site** (no engine source, no private content), mirrored to a hosted static page; a root that hosts the public courses, filtered by a **versioned list of allowed courses**.
- **Published by a script**, with the administrator's agreement: it builds, then **checks** that no private data is present (a list of forbidden words kept in the private repository, never copied elsewhere; courses outside the list refused), shows the summary, and pushes only on confirmation. A rerun without changes publishes nothing.
- **The public page is frozen**; the chat, an internal tool, never opens it.
- The old public address keeps a redirect that preserves the fragment, then its repository is archived.

## Rules: the model phrases, the server decides

- The server computes verdicts and averages; the model only **phrases**.
- **"A hint, never the answer", enforced twice**: the activity is read server-side from its identifier (never from the request), and the model does not get the answer when it does not need it; then a deterministic check verifies its output does not contain the answer (choice, result in digits or words, dictated word) — otherwise, the hint written in the activity or a generic hint.
- **Vision**: the model copies the slate **without knowing the expected words**, so as not to "correct" the child in their place; output in a JSON schema, checked; on failure, the child types it in.
- **Child protection**: no comparison between children, private report book; photos deleted as soon as a parent has marked them, and at the latest 7 days after upload; practical-work safety written into the content (batteries of 4.5 V at most, no mains socket, no flame, no household product, an adult present for anything that heats).

## Measurements

- ≈ 800 activities published (806); a physics-chemistry module fully reviewed: 19 lessons, 13 practical works, 19 challenges, ≈ 120 questions checked against reference answers, no contradiction.
- 115 automated tests (content, build, progress, sync, browser journeys, review mode, Safari 15 compatibility, new-version notice, publishing).
- Pod: nginx capped at 64 Mi, sync at 256 Mi.
- Tests without real data: fictitious first names in tests, never the children's.

## Lessons

- **PID 1 and zombie processes**: since git 2.47, every `git fetch` starts `git maintenance --auto --detach`. The detached process is reparented to the container's PID 1 — here a Node.js process, which does not reap orphans. One zombie per sync, up to the 4,096 PID limit: "unable to fork", sync stops (the live version keeps being served). Fix at the source: `git -c maintenance.autoDetach=false -c gc.autoDetach=false`, maintenance then runs in place, and a test checks that `--detach` is absent from git's trace (it fails without the fix). Defence in depth proposed, not applied yet: `shareProcessNamespace: true`, so the `pause` container is PID 1 and reaps orphans. A plain restart only postpones the incident.
- **Atomic switch and fallback content**: a broken sync never breaks the site.
- **OpenShift's arbitrary UID**: `ssh` requires an entry in `/etc/passwd` — hence `chmod g+w /etc/passwd` in the image and paths owned by group 0.
- **Separate engine and content**: content evolves through Git, checked before publication, without rebuilding the image.
- **Engine before content**: content using a new field is only published after the build of the engine that understands it; otherwise sync rejects the whole content ("unknown operation") and publishes nothing more, the live version staying served.
- **A written image must become an image**: an unclosed bracket in the text ("[EF)") turned a figure into a link. The build now refuses a lesson image that does not become an `<img>`.
- **The symmetry axis is drawn after the filled shape**, otherwise the shape hides it; before the small markings, which its dashes would hide.
- **Redistribution rights carried by each resource**: the sharing version builds itself, without manual sorting.
