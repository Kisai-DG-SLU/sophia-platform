# School module — documentation

## What the module does

- **Paths** per level (from primary to the end of lower secondary) and subject: lessons, practical work at home, challenges, stars and badges; ≈ 790 activities published today.
- **Avatar** shared by the chat and the school (a drawing, or a small photo).
- The child's **progress log**, and a **read-only record book** for parents.
- **Exercise sheets** (statement, answers, self-assessment) and linked videos.
- **Report book** from the real school, copied in by the child: marks, reports, averages, spreadsheet import, curves; in primary, **skills** (not acquired, partly, acquired, exceeded), without marks or comparison.
- **"Ask Sophia"**: a hint on the current activity, and opening the school from the chat (button in the answer, link built by the server).
- Photographed **slate dictation** and **reading sheet**, read by the local model (vision).
- `carnet_scolaire` tool in the chat: it only reads the log of the child who is talking; the verdict (congratulations, encouragement…) is **computed by the server**.

- **Publishing content without rebuilding the image**: the `contenus` container syncs the repositories read-only every minute and keeps the live version if the new one is invalid (incident fixed, see lessons).

Planned: a sharing version with a recorded open-licence synthetic voice, MCP tools for progress and opening, the report book served over MCP with a signed token limited to the child.

## Architecture

```
browser ─VPN─→ chat interface (SSO) ── /ecole/ ──→ school pod (applications namespace)
                                                     ├ site      : nginx, GET/HEAD only
                                                     └ contenus  : Git sync every minute
                                                                     → atomic switch of a "current" link
Chat API: progress, report book, photos (interface database); hints and photo reading by sophia-local
```

| Item | Choice |
|---|---|
| Pod | one image, **two containers**, no Route nor sign-in of its own: only the interface pods reach it (NetworkPolicy) |
| `site` | unprivileged nginx, `GET`/`HEAD` only, strict headers; serves the engine and a **fallback content built into the image** |
| `contenus` | fetches over SSH (read-only deploy key, the pod's only secret) a public content repository and an optional private one, **checks**, rebuilds, then switches a `current` link at once in a shared volume; invalid content or unreachable repository: the live version stays, the error is published in a status file |
| Build | two-stage Docker (UBI 9, Node.js); only an **engine** change requires a build, content goes through Git |
| Identity | same oauth2-proxy and Keycloak as the chat; roles: administrator, guardians (parents), protected (children) |
| Data | progress and report book in the interface database (event table, profile); nobody writes in someone else's log |
| Opening from the chat | intent analysis (model, JSON schema) recognises "school"; a **deterministic policy** allows the `ouvrir_ecole` action; the link is built by the server from the school index, the browser checks its shape |

### Content format

`contenus/<subject>/<level>/<module>/`, one YAML file per module and level. Activity types: lesson (Markdown with YAML header), practical work, multiple-choice challenge, "click the word", "fill in", slate dictation, reading sheet. Required fields: `id`, `type`, `titre`, `notions`, `source`, `licence`, `redistribuable`.

The build **refuses** any invalid content: correct answer missing from the choices, unknown notion, missing licence. The private repository adds modules without replacing anything; only what is marked `redistribuable: true` goes into the sharing version, which keeps only links to the rest.

## Rules: the model phrases, the server decides

- The server computes verdicts and averages; the model only **phrases**.
- **"A hint, never the answer", enforced twice**: the activity is read server-side from its identifier (never from the request), and the model does not get the answer when it does not need it; then a deterministic check verifies its output does not contain the answer (choice, result in digits or words, dictated word) — otherwise, the hint written in the activity or a generic hint.
- **Vision**: the model copies the slate **without knowing the expected words**, so as not to "correct" the child in their place; output in a JSON schema, checked; on failure, the child types it in.
- **Child protection**: no comparison between children, private report book; photos deleted as soon as a parent has marked them, and at the latest 7 days after upload; practical-work safety written into the content (batteries of 4.5 V at most, no mains socket, no flame, no household product, an adult present for anything that heats).

## Measurements

- ≈ 790 activities published; a physics-chemistry module fully reviewed: 19 lessons, 13 practical works, 19 challenges, ≈ 120 questions checked against reference answers, no contradiction.
- 86 automated tests (content, build, progress, sync, browser journeys).
- Pod: nginx capped at 64 Mi, sync at 256 Mi.

## Lessons

- **PID 1 and zombie processes**: since git 2.47, every `git fetch` starts `git maintenance --auto --detach`. The detached process is reparented to the container's PID 1 — here a Node.js process, which does not reap orphans. One zombie per sync, up to the 4,096 PID limit: "unable to fork", sync stops (the live version keeps being served). Fix at the source: `git -c maintenance.autoDetach=false -c gc.autoDetach=false`, maintenance then runs in place, and a test checks that `--detach` is absent from git's trace (it fails without the fix). Defence in depth proposed, not applied yet: `shareProcessNamespace: true`, so the `pause` container is PID 1 and reaps orphans. A plain restart only postpones the incident.
- **Atomic switch and fallback content**: a broken sync never breaks the site.
- **OpenShift's arbitrary UID**: `ssh` requires an entry in `/etc/passwd` — hence `chmod g+w /etc/passwd` in the image and paths owned by group 0.
- **Separate engine and content**: content evolves through Git, checked before publication, without rebuilding the image.
- **Redistribution rights carried by each resource**: the sharing version builds itself, without manual sorting.
