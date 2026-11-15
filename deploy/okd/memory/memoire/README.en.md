# Memory service (`sophia-memoire`)

The household's memory is a **service**, like the language model: called by the interface and by the agents, each with its own rights, and the **only writer** of knowledge. It receives documents, extracts their text in an isolated pod, stores them as versions, has them validated by a designated person, then makes them searchable. The knowledge model is described in the [RAG 5D](../../../../docs/concepts/03-rag-5d.en.md) page; the dashboard page that uses it, in the [dashboard](../../apps/chat-interface/README.en.md#memory-page).

**State in the reference installation**: **in service**. All the rollout steps below have been done, with both their proofs passing (bucket policy, extraction isolation). The dashboard's "Memory" page is deployed; the first real deposit comes with its end-to-end check. The service code is not provided; this document gives its contract, its rules and its recipe, manifests included ([Recipe: files and commands](#recipe-files-and-commands)).

## What lives where (RAG 5D)

Each place has a single role. The registry is written **last**: as long as it does not reference an object, that object does not exist for the service.

| Place | What it keeps | Source of truth? |
|---|---|---|
| **S3 object storage**, one versioned bucket, never purged (`${MEMOIRE_SEAU}`) | the **original** of each version and its **extracted text**. Under `attente/` (pending), the pending version, erasable. Under `valide/` (validated), the original of each validated version (its text goes to the forge), **protected against any deletion**, even by the service | yes, for originals |
| **PostgreSQL**, a dedicated schema (`${MEMOIRE_SCHEMA}`) | the **registry**: documents, versions, states, fingerprints, references to S3 and to the forge | yes, for state and references |
| **Git forge** (Forgejo), a private organisation, **one repository per level** | the **validated text** of each version, in Markdown with a header; **one commit per validated version, never before**; an off-site copy is possible (see "Limits to be aware of") | yes, for validated texts |
| **Vector database** (Qdrant) | chunks and their vectors: the validated version of each document, plus the pending version (marked, never returned by a search) | **no**: an index, rebuildable from the registry and the texts |
| Shared **audit table** (`audit_log`) | every write and every refusal, without content | log |

What this gives:
- **A refused version never enters the forge**: deleting it needs no Git history rewrite. While it is pending, its text is in S3, where it can be erased.
- **A compromised service can erase what is pending, never what is validated**: the bucket policy denies it any deletion under `valide/`.
- **The extracted text is kept**: a change of extraction library does not affect documents already deposited, and the index can be rebuilt without re-reading the originals.
- **The forge prepares the next dimensions**: each level repository can be cloned as a notes vault (structural dimension), and the registry will feed the graph (dimension 5). Nothing more needs to be kept today.

### S3 bucket: one bucket, two prefixes

| Prefix | Content | Service rights |
|---|---|---|
| `attente/originaux/<document>`, `attente/textes/<document>.md` | the pending version | write, read, delete, including an S3 version |
| `valide/originaux/<document>`; `valide/textes/<document>.md` only for a level absent from the forge table (none today) | the original of each validated version, as an S3 version of the same key; the validated text goes to the forge | write and read only |

- The service's S3 identity only has read and list on the bucket, and write under both prefixes; no tagging, no administration.
- A **bucket policy** additionally denies it: any deletion (object or version) under `valide/`, suspending versioning, changing the policy, the lifecycle, CORS or locking.
- **Versioning enabled, no lifecycle rule.**
- **One bucket is enough** if the storage evaluates the policy **key by key**, including for a bulk delete. SeaweedFS does (checked in its code, then proven in service). Otherwise: two buckets, one for pending, one for validated, with the same logic.

### Forge: one repository per level

- A private organisation, with one repository per confidentiality level (`public`, `famille` (family), `personnel` (personal), `intime` (intimate), `admin`). The level → repository mapping is **a single table in the code**: a level removed from it would keep its validated text in S3, under `valide/textes/`.
- In each repository, the file is `<person>/<path>.md`, where `<person>` is the person's **technical identifier** (never a first name), or `agent-<name>`. A proposal without a path (chat, agent) goes under `<person>/_propositions/<document>.md`. The person prefix avoids any collision within a repository.
- **YAML header**: document, version, replaced version, level, kind, path, displayable author, fingerprint, deposit and validation dates, and a `source` link to the original in S3 with its version identifier.
- **Commit message**: `document <id>, version <n>`, with no title or path.
- **Replay**: before writing, the service reads the file back; if the header already carries the fingerprint and number of the version, it reuses that commit instead of creating a second one.
- **Service account**: restricted, neither administrator nor owner, with no right to create a repository or an organisation, member of a team that only has code write on the level repositories; a token limited to repository write. In Forgejo, users and organisations share a single namespace: the account cannot have the organisation's name.

## Documents and versions (V1)

- **A document is a person and their full path** (folder and name). The path is compared in normalised Unicode and **case-insensitively**: a clone of the forge on a case-insensitive file system will never mix two files. The displayed path stays the one of the first deposit.
- **A deposit is only a batch**: it groups the versions of one upload, for grouped validation and audit, without being part of the document's identity. A note and a file at the same path are the same document.
- **Level, kind and format belong to the document**: a version at another level is refused (`niveau_different`), another format or kind as well (`type`). Changing a document's level will be a separate action, later.
- **A new version waits, and the previous validated version stays searchable** (V1). There are never two pending versions: a new version **abandons** the one still waiting (its chunks and its objects under `attente/` are deleted, the `abandonnee` state is audited). The validator therefore only sees the latest.
- **Version states**: `en_attente` (pending), `valide` (validated), `remplacee` (validated, then superseded), `rejete` (refused), `abandonnee` (abandoned). In the registry, at most one pending and one validated version per document, guaranteed by two partial unique indexes.
- **Renaming or moving** a document means another path, hence another document; the old one keeps its history.

### Flows

| Action | Steps, each replayable without harm |
|---|---|
| **Deposit** (file, note, proposal) | registry read (same fingerprint as the pending or validated version: **resume**, returned as 200 without writing anything); checks (level, version guard, kind, limits); extraction, with the format check; vectors; audit `tentative`; S3 under `attente/` (original, then text); chunks in the index, marked pending; **registry last**, in one transaction that adds the `en_attente` version and sets the one that was waiting to `abandonnee`; audit `ecrit`; then erasure of the abandoned version (chunks and objects under `attente/`) and its audit. What the validator deposits is validated in the same request |
| **Validation** | audit; copy of the original to `valide/`; text read under `attente/` and committed in the forge; in the index, chunks of the previous version deleted and those of the new one set to `valide`; **registry last** (new one `valide`, previous `remplacee`); deletion under `attente/`; audit of the decision |
| **Refusal** | audit; chunks deleted; objects under `attente/` deleted; registry `rejete`, without fingerprint or references; audit. With no validated version, the document also loses its path. The previous validated version stays searchable |
| **Search** | only `valide` chunks, not expired, readable by the caller; the result carries the document and the version number |

**Synchronous analysis**: extraction, chunking (2,000 characters, 200 overlap) and vectors happen during the request, which returns the final state. At worst about four minutes, excluding storage slowness (extraction 90 s, vectors 120 s, vector database 30 s); when slow, add S3 (two writes, 30 s each), the registry (10 s) and the audit (5 s per line), and on validation the forge (read and write, 30 s each). The chat relay must wait longer. Vectors are computed **inside the cluster**, through the model router's embedding alias.

**Failures**: a failure of the audit, S3, the index, the registry or the forge is a closed refusal (503), audited except for the audit itself. The same upload repeated after a cut finds its version by fingerprint and returns 200, without counting anything twice.

## Contract (overview)

All routes require a token. A person presents their OIDC access token, verified by the service (RS256 signature with the realm keys, issuer, expiry, **the service's audience**, type, originating client in a closed list, groups as a list). An agent will present a projected service account token, verified by `TokenReview`.

| Route | Who | Role |
|---|---|---|
| `rechercher` (search) | everyone | validated chunks readable by the caller |
| `proposer` (propose) | people, agents | a short text, identified by a stable key: same key and same content, resume; other content, new version |
| `moi` (me) | people | levels where the person can deposit, whether they validate, limits |
| `depots`, `depots/{batch}/fichiers`, `depots/{batch}/notes` | people who deposit | a batch, then **one document per request** (file as raw body, path in an encoded header, version seen as a parameter) |
| `existants` (existing) | people | before uploading: which paths already exist, with their latest version, state, level and format (POST: paths go neither into a URL nor into a log) |
| `connaissances`, `connaissances/historique` (knowledge, history) | people | their documents in folders, search by name, filter by state; the version history of a document |
| `a_valider`, `a_valider/compte`, `valider` (to validate, count, validate) | the validator only | one line per pending version; the count for "What's new?"; the decision on one version, or on **the list as seen** (checked in full before writing) |

**Order of checks on deposit**: resume (same content, whatever the announced version), then level (`niveau_different`), then version guard (`existe_deja` if an existing path arrives with no version seen, `version_changee` if the version seen is no longer the latest: another device got there in between), then kind, then limits, then format, **after extraction**: the format comes from the bytes.

**Closed reasons**: `type`, `taille`, `illisible`, `vide`, `trop_long`, `nom`, `niveau`, `niveau_different`, `existe_deja`, `version_changee`, `deja_decide`, `depot`, `depot_plein`, `trop_en_attente`, `occupe`. The interface only translates these words, never free text from the service. One word per state in the contract: `en_attente`, `valide`, `refuse`.

## Validation

- **A single person validates**: the household's administrator, designated by their **technical identifier** in a setting, **and** a member of the administration group. Another member of that group validates nothing. An empty or malformed setting stops the service at startup.
- **Status set by rule, never by the model**: what the validator deposits is validated automatically; the rest waits, including what other administrators and agents deposit; what comes from the web will always wait for the [Semantic Tribunal](../../../../docs/concepts/05-tribunal-semantique.en.md), even when deposited by the validator. Only the validation state decides use; confidence (0, then 1 once validated) is just a trace.
- **Confidentiality towards the validator**: for other people's `personnel` and `intime` levels, the validation list only shows the author (displayable name taken from their token at deposit), the level, the date and the size: no file name, no path, no excerpt. The validator can validate or refuse, without being able to read afterwards.
- **Replayed decision**: on a document already decided, the same decision and the contrary one both return `deja_decide`, with the `statut`; the page compares it with the decision sent (same value: success; contrary value: failure). `version_changee` covers an abandoned or superseded version. On a list, a line already decided with the same decision is skipped, and a line decided otherwise returns `version_changee` for the whole list, writing nothing.

## Rights per level

The rights filter is **added by the service** to every index search, then each result is checked again (state, rights, expiry). The model cannot widen it.

| Caller | `public` | `famille` | `personnel` | `intime` | `admin` |
|---|---|---|---|---|---|
| administration | yes | yes | their own | their own | yes |
| guardians | yes | yes | their own | their own | — |
| protected users | yes | yes | their own | their own | — |
| guests | yes | — | — | — | — |
| agent | yes | — | — | — | — |

- One only deposits at a level one can read; **guests deposit nothing**.
- **Agents limited to `public`** as long as the dispatcher does not pass on the person being served: otherwise a guest going through an agent would read `famille`. They do not have the deposit routes either.

### Limits to be aware of

The rights above are **the service's**, the only intended read path. They do not protect against whoever administers the places themselves:
- **Forge administrators**: they read all level repositories, `intime` included. In the reference installation, this is a choice made knowingly by the household's head, who knows that a forge administration agent is one of them. The service remains the only holder of a token on these repositories.
- **Off-site copy by mirror**: if the installation copies its repositories elsewhere by mirror, all levels are there, `intime` included, readable by anyone who administers that copy, even texts the page presents as readable by their author only. It is only a copy **of validated texts**: the originals (S3) and the registry (PostgreSQL) belong to the installation's backup. Recommendation: a second forge on a site under your control or at a host in the European Union, and, for the `personnel` and `intime` repositories, no clear-text mirror but the client-side encrypted backup ([sovereign solutions](../../../../docs/security.en.md#backup-and-storage-sovereign-solutions)).
- **Database and storage administrators**: they read the registry (paths included) and the originals.
- **Confidentiality towards the validator is a guarantee of the interface**, not of technical administration: the audit and the pod log carry the caller's identifier, the size and the number of chunks of every deposit, whatever its level. Whoever reads these logs links an intimate document to its author, without its content or name.

## Audit in the database

- Every write and every refusal go to the shared audit table, as **two lines for a write**: `tentative` (attempt), then `ecrit` (written) or `echec_stockage` (storage failure); a validation decision likewise. They carry identifiers, version, outcome, size and number of chunks, **never content, path or author name**.
- **A dedicated PostgreSQL role that only has `INSERT`** on that table: no read, no update, no delete, no other table. The service **checks these rights at startup** and refuses to start with a broader role. A compromised service can therefore add lines, never erase its trail.
- The registry has **its own role**, owner of its schema only, with no right on the rest of the database. The registry tables are created by the service at startup, from a versioned, replayable SQL script.
- Both passwords are generated in place, stored in their Secret **before** the role, and only a **SCRAM verifier**, computed off the server, goes into `CREATE ROLE`: even a failed statement, which PostgreSQL logs, leaves no password there.
- The audit table is tied to the installation's tenant: its identifier is a service setting (exactly one row required). Deleting the tenant would erase the whole audit, by cascade.
- The application log only carries identifiers and numbers; the HTTP client only logs its warnings.

## Isolated extraction (D2)

Reading a PDF or an office document means running a parser on an unknown file. A first version did it in a subprocess of the service: the review showed that the child, with the same UID, could read its parent's environment (`/proc/<parent>/environ`), hence its keys and the pod's token, and had its network.

**Extraction therefore runs in a separate pod** (`sophia-extraction`), same image with another command:
- **no Secret, no sensitive variable, no service account token, no network egress**, no shared process namespace: code execution in the parser finds nothing to steal and no one to reach;
- the memory service sends it the bytes over HTTP; this is the only ingress allowed;
- each file is read there by a `python -I` subprocess with no environment, limited in memory (512 MiB) and CPU time (60 s), writing no file and creating no process or thread, killed after 90 s or if the client disconnects; two at a time at most;
- the **type comes from the bytes** (signature), never from the name, and is decided in the child, including reading an archive's directory (10,000 entries at most);
- output is bounded in the child (200,000 characters) and read with a bound by the parent; plain text that is too large is refused without starting a child;
- the parent only relays a **closed reason**, never text from the child;
- formats: text and Markdown (strict UTF-8), PDF with text (500 pages at most; encrypted or without text: refused), office documents read without DTD or entities. Images will come later, through a vision model; their transcription will always wait for validation.

**In-service proof**, run from the extraction pod: names of the variables present (none sensitive, for any visible process), no token mounted, then connection attempts **by address, without DNS** to every service of the installation (vector database, memory service, identity provider, router, PostgreSQL, S3, forge, cluster API on the node and through its Service, DNS) and to the Internet. Everything must be unreachable; attempts by name prove nothing alone, since DNS fails first. Each resolution is bounded (5 s), so the proof takes about one minute.

## Limits

50 MiB per file; 200 documents and 500 MiB per batch; a note of 50,000 characters; 200,000 characters of text per document; 1,000 pending documents per person (except the validator); 5,000 documents kept per person. A new version does not count as one more document; replaced, abandoned and refused versions do not count. Limits are checked under a per-person lock; at most two uploads processed at a time, the others wait 15 s then receive `occupe` (busy). The path is sanitised: relative, normalised, 240 characters at most, no `..`, no empty segment or one starting with a dot, no control, direction or line-separator character.

## Zone network

With the service, the memory zone closes:
- **vector database**: API key, telemetry off; reachable by the memory service only;
- **default deny on ingress and egress** in the namespace, then one rule per flow: embedding from the model router only; memory service from the chat only; extraction from the memory service only; service egress to DNS, the vector database, extraction, the router, the identity provider (realm keys), PostgreSQL, S3 and the forge;
- on the other side, each destination admits **the service pod only** (ingress rules of PostgreSQL, storage, the forge and the identity provider);
- an **EgressFirewall** as a second barrier: cluster pod and Service networks only, then deny. No egress to a node or to the Internet; verifying agent tokens (`TokenReview`) will later add the cluster API only.

Before closing, inventory what reaches the zone: in the reference installation, the agents received the address of the vector database and the embedding without using them, and a suspended ingestion wrote directly to the vector database; it will go through the service.

## Rollout (generic)

The administrator applies one step at a time; each check is read before the next step. Constant rules: **no secret on screen or in a terminal variable** (generated and stored through a pipe), **a backup of every modified object** before `oc diff`, then `--dry-run=server`, then `apply`.

| Step | Action | Expected check |
|---|---|---|
| 0 | Survey of the shared audit table and the tenants | known columns, a single tenant |
| 1 | Image: ImageStreams, Python base **pinned by digest**, binary build of committed code only, dependencies installed by hash | `Push successful`; image digest written into the manifests |
| 2 | Secrets: vector database key, router key limited to the embedding alias (with a request cap), validator setting (technical identifier read from the identity provider) | expected lengths; router key fingerprint equal on both sides |
| 2 bis | PostgreSQL: tenant setting, Secrets then roles by SCRAM verifier (audit: `INSERT` only; registry: owner of its schema), schema created in its name; service ingress rule | **through the Service, hence with a password**: the audit insert passes (rolled-back transaction), read, update, delete and other tables refused; the registry creates in its schema and nowhere else; a wrong password is refused |
| 2 ter | S3: **backup copy of the identity configuration, inside the cluster**; service Secret, then identity derived from it, never displayed; ingress rule; storage restart (**cuts the file service for about a minute**); Job creating the bucket (versioning, policy, no lifecycle) | key fingerprints match; versioning enabled; no lifecycle; policy set |
| 2 quater | Forge: restricted service account, private organisation, one repository per level, write team, service token poured straight into its Secret, temporary installation token deleted at the end; mirrors if the installation wants them; ingress rule narrowed to the service pod | API codes; token length; last mirror push without error |
| 3 | API key on the vector database (one restart), then registry indexes in the collection (document, batch, rank, version) | 401 without key; indexes present |
| 4 | Identity provider: **the service's audience** added to the access tokens of the chat client; service ingress rule | mapper present; dry rerun "not modified" |
| 5 | Accounts, service, extraction, network rules, EgressFirewall | pods ready with no restart; at startup, the service opens its two PostgreSQL connections, checks the audit role and creates the registry |
| 5 bis | **Bucket policy proof**, with the service's identity, from its pod, **before any deposit** | under `valide/`: version deletion refused, single and bulk, delete marker refused, witness still there; versioning, lifecycle and policy: refused; under `attente/`: write and delete allowed. Otherwise: two buckets |
| 5 ter | Embedding still reachable by the router | 200 |
| 6 | **Extraction isolation proof** (see above) | all addresses unreachable; "conforme" |

Then: the backup copy of the S3 configuration is deleted; the chat receives the service's address and its egress to it (see the [dashboard](../../apps/chat-interface/README.en.md#memory-page)).

**At the first real deposit**, the administrator reads, without content, path or person identifier: the last audit lines (`tentative`, then `ecrit`), the registry (`en_attente`, original and text present, no commit); after validation, the decision's audit, the registry (`valide`, original present, text in the forge, a commit identifier), the commit `document <id>, version 1` in the level's repository, and the last mirror push.

**Rollback**, step by step, from the backups: network rules by `oc diff` then `apply` of the backup; S3 identities from the copy kept in the cluster (storage restart); PostgreSQL roles by `DROP OWNED BY` then `DROP ROLE` (**deletes the whole registry**; audit already written remains); audience mapper in the console. Be aware: a mirror copy deleted at the external host cannot be recovered, and, apart from the mirror, the validated text exists only in the forge; the original stays in S3, from which the text can be re-extracted.

## Recipe: files and commands

The zone's manifests, as they run in the reference installation, made generic. The namespace names (`sophia-memory`, `sophia-core`, `sophia-identity`, `sophia-storage`, `sophia-git`, `sophia-interface`, `sophia-skills-build`) and the Service names are the platform's: the neighbours' ingress rules name them too. Templates that carry `${…}` are rendered by `envsubst` **with the explicit list** of their variables, so a script or SQL inside the block keeps its own `$`.

| File | Namespace | Content |
|---|---|---|
| `00-build.yaml` | `sophia-skills-build` | ImageStreams of the service and of the Python base (pinned by digest), binary BuildConfig with no trigger, image pull right for `sophia-memory` |
| `01-comptes.yaml` | `sophia-memory` | service and extraction accounts, with no rights and no mounted token |
| `02-memoire.yaml` | `sophia-memory` | memory service Deployment and Service; ConfigMap of OKD's service certificate authority (TLS of the S3 gateway) |
| `03-extraction.yaml` | `sophia-memory` | extraction Deployment and Service: same image, no Secret, no token, no egress |
| `04-network.yaml` | `sophia-memory` | default deny on ingress and egress, then one rule per flow |
| `05-egressfirewall.yaml` | `sophia-memory` | second egress barrier: cluster pod and Service networks, then deny |
| `06-seau.yaml` | `sophia-storage` | Job of the `memoire` bucket: versioning, `ProtegerSeau` and `ProtegerValide` policy, no lifecycle |
| `07-forge-network.yaml` | `sophia-git` | ingress of the service's pod alone on the forge |
| [`../qdrant/`](../qdrant/) | `sophia-memory` | dedicated volume, vector database with API key and telemetry off, its Service |
| `role-scram.py` | — | `CREATE ROLE` statement with a SCRAM-SHA-256 verifier computed outside the server |
| `essai-audit.sql`, `essai-registre.sql` | — | check of both roles' rights, over TCP with a password |
| `epreuve-seau.py`, `epreuve-extraction.py` | — | the two proofs, run inside the service and extraction pods |

The zone's ingress entries at the neighbours are already in their files: PostgreSQL ([`../../core/postgres18/03-network.yaml`](../../core/postgres18/03-network.yaml)), S3 gateway ([`../../storage/03-network.yaml`](../../storage/03-network.yaml)), identity provider ([`../../identity/02-network.yaml`](../../identity/02-network.yaml) and the list in [`../../identity/03-keycloak.yaml`](../../identity/03-keycloak.yaml)). The model router already admits `sophia-memory` ([`../../core/litellm/network-policy.yaml`](../../core/litellm/network-policy.yaml)).

Template and command variables (the settings read by the service are under "Variables", below):

| Variable | Role | Example |
|---|---|---|
| `${MEMOIRE_CODE_DIR}` | directory of the service's code in its repository, sent to the build | `services/memoire` |
| `${MEMOIRE_IMAGE_DIGEST}` | digest of the built image, read back after the build | `sha256:…` |
| `${IDP_HOST}` | public name of the identity provider (token issuer) | `auth.apps.example.org` |
| `${SERVICE_NETWORK}`, `${POD_NETWORK}` | cluster Service and pod networks | `172.30.0.0/16`, `10.128.0.0/14` (OKD defaults) |
| `${AWSCLI_VERSION}`, `${AWSCLI_DIGEST}` | image of the Job's S3 client, as for [storage](../../storage/README.en.md) | `2.37.9`, `sha256:…` |
| `${QDRANT_MOUNT_POINT}`, `${QDRANT_SIZE}` | mount point of the vector database's logical volume, and its size | `/var/mnt/qdrant`, `20Gi` |
| `${NODE_NAME}` | node that holds the local volume | `node-1` |
| `${MEMOIRE_FORGEJO_COMPTE}` | the service's account in the forge; it cannot bear the organisation's name | `compte-memoire` |
| `${MEMOIRE_FORGEJO_ORG}` | organisation of the level repositories, the one set by the service's code | `memoire` |
| `${FORGE_MAIL_DOMAIN}` | domain of the email address required to create an account | `git.example.org` |

Commands from this directory. Each check is read before the next step.

**Step 0 — Shared audit table** (read-only):

```bash
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d sophia_rag -c '\d sophia.audit_log'
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d sophia_rag -Atc 'select count(*) from sophia.tenants'
```

Expected: the table's columns, then `1`.

**Step 1 — Image.** Render, check, apply, then build the committed code only:

```bash
envsubst '${MEMOIRE_CODE_DIR}' < 00-build.yaml | oc apply --dry-run=server -f -
envsubst '${MEMOIRE_CODE_DIR}' < 00-build.yaml | oc apply -f -
oc -n sophia-skills-build get istag python:3.13.17-slim-trixie
git archive --format=tar.gz -o /tmp/sophia-memoire.tar.gz HEAD "${MEMOIRE_CODE_DIR}"
oc -n sophia-skills-build start-build sophia-memoire --from-archive=/tmp/sophia-memoire.tar.gz --follow --wait
oc -n sophia-skills-build get istag sophia-memoire:latest -o jsonpath='{.image.metadata.name}{"\n"}'
```

Expected: four `created`, the base's ImageStreamTag (OKD imports the image for the node's architecture), `Push successful`, then the image digest `sha256:…`: that is `${MEMOIRE_IMAGE_DIGEST}`.

**Step 2 — Secrets and validator** (`sophia-memory`). No secret on screen or in a terminal variable:

```bash
openssl rand -hex 32 | tr -d '\n' | oc -n sophia-memory create secret generic qdrant-cle --from-file=cle=/dev/stdin
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-memoire --modeles sophia-embedder --rpm 600 --dry-run < ../../core/litellm/create-virtual-key.py
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-memoire --modeles sophia-embedder --rpm 600 --tube < ../../core/litellm/create-virtual-key.py | oc -n sophia-memory create secret generic sophia-memoire-litellm --from-file=cle=/dev/stdin
oc exec -i -n sophia-core deploy/litellm -- python3 - --info sophia-memoire < ../../core/litellm/create-virtual-key.py
oc -n sophia-memory get secret sophia-memoire-litellm -o jsonpath='{.data.cle}' | base64 -d | sha256sum | cut -c1-12
```

Expected: the vector database key's Secret; the router key, limited to the embedding alias and 600 requests per minute; then the same fingerprint on both sides. If the key creation fails, the shell still creates an empty Secret, betrayed by the empty string's fingerprint (`e3b0c44298fc`): delete it before trying again.

The validator is the **technical identifier** (UUID) of an identity provider account, read in its console (the user's page), never a first name. The reference installation reads it with a read-only script, from the login name, and sends it through a pipe:

```bash
printf '%s' "<technical-identifier>" | oc -n sophia-memory create configmap sophia-memoire-valideur --from-file=valideur=/dev/stdin
oc -n sophia-memory get configmap sophia-memoire-valideur -o jsonpath='{.data.valideur}' | wc -c
```

Expected: `36`. An empty or malformed value stops the service at startup, with no other effect.

**Step 2 bis — PostgreSQL 18.** The audit tenant, refused unless there is exactly one row; then, for each role, the Secret first and the role by its verifier afterwards; finally the schema and the grants:

```bash
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d sophia_rag -Atc "select id from sophia.tenants" | python3 -c 'import sys, uuid; l = sys.stdin.read().split(); sys.exit("tenants : %d ligne(s), une seule exigée" % len(l)) if len(l) - 1 else print(uuid.UUID(l[0]), end="")' | oc -n sophia-memory create configmap sophia-memoire-audit-tenant --from-file=tenant=/dev/stdin
openssl rand -hex 24 | tr -d '\n' | oc -n sophia-memory create secret generic sophia-memoire-audit --from-file=password=/dev/stdin && oc -n sophia-memory get secret sophia-memoire-audit -o jsonpath='{.data.password}' | base64 -d | python3 role-scram.py memoire_audit | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- psql -v ON_ERROR_STOP=1
openssl rand -hex 24 | tr -d '\n' | oc -n sophia-memory create secret generic sophia-memoire-registre --from-file=password=/dev/stdin && oc -n sophia-memory get secret sophia-memoire-registre -o jsonpath='{.data.password}' | base64 -d | python3 role-scram.py memoire | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- psql -v ON_ERROR_STOP=1
printf 'GRANT CONNECT ON DATABASE sophia_rag TO memoire_audit, memoire;\nGRANT USAGE ON SCHEMA sophia TO memoire_audit;\nGRANT INSERT ON sophia.audit_log TO memoire_audit;\nCREATE SCHEMA memoire AUTHORIZATION memoire;\n' | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- psql -d sophia_rag -v ON_ERROR_STOP=1
```

Expected: the ConfigMap; twice `vérificateur SCRAM-SHA-256 calculé localement` and `CREATE ROLE`; three `GRANT` and `CREATE SCHEMA`. The check goes **through the Service, hence with a password** (locally, the server may be in `trust` and would prove nothing):

```bash
{ oc -n sophia-memory get secret sophia-memoire-audit -o jsonpath='{.data.password}' | base64 -d; echo; oc -n sophia-memory get configmap sophia-memoire-audit-tenant -o jsonpath='{.data.tenant}'; echo; cat essai-audit.sql; } | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- sh -c 'read -r PGPASSWORD; read -r T; export PGPASSWORD; psql -h postgres-sophia-18 -U memoire_audit -d sophia_rag -At -v t="$T" -f -'
{ oc -n sophia-memory get secret sophia-memoire-registre -o jsonpath='{.data.password}' | base64 -d; echo; cat essai-registre.sql; } | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- sh -c 'read -r PGPASSWORD; export PGPASSWORD; psql -h postgres-sophia-18 -U memoire -d sophia_rag -At -f -'
```

Expected: for the audit, `INSERT 0 1` then `ROLLBACK`, then five `permission denied` refusals; for the registry, `CREATE TABLE` then `ROLLBACK`, then two refusals. The service's ingress on PostgreSQL: `oc diff`, then `oc apply` of [`../../core/postgres18/03-network.yaml`](../../core/postgres18/03-network.yaml).

**Step 2 ter — S3 bucket.** First a backup copy of the identity configuration, **inside the cluster** (never on the workstation); then the service's Secret; then the `memoire` identity derived from that Secret, added to the configuration through private temporary files erased in the same block:

```bash
oc -n sophia-storage get secret s3-config -o json | python3 -c 'import json, sys; d = json.load(sys.stdin); d["metadata"] = {"name": "s3-config-avant-memoire", "namespace": d["metadata"]["namespace"]}; d.pop("status", None); print(json.dumps(d))' | oc create -f -
{ printf 'cle='; openssl rand -hex 12; printf 'secret='; openssl rand -hex 24; } | oc -n sophia-memory create secret generic sophia-memoire-s3 --from-env-file=/dev/stdin
( umask 077; T=$(mktemp -d); oc -n sophia-storage get secret s3-config -o jsonpath='{.data.s3\.json}' | base64 -d > "$T/s3.json" && oc -n sophia-memory get secret sophia-memoire-s3 -o json > "$T/memoire.json" && python3 -c 'import base64, json, sys; c = json.load(open(sys.argv[1])); d = json.load(open(sys.argv[2]))["data"]; k, s = (base64.b64decode(d[x]).decode() for x in ("cle", "secret")); assert len(k) == 24 and len(s) == 48, "clés inattendues"; noms = [i["name"] for i in c["identities"]]; assert "memoire" not in noms, "identité memoire déjà présente"; c["identities"].append({"name": "memoire", "credentials": [{"accessKey": k, "secretKey": s}], "actions": ["Read:memoire/*", "List:memoire", "Write:memoire/attente/*", "Write:memoire/valide/*"]}); json.dump(c, open(sys.argv[3], "w")); print("identités :", noms, "+ memoire")' "$T/s3.json" "$T/memoire.json" "$T/nouveau.json" && oc -n sophia-storage set data secret/s3-config --from-file=s3.json="$T/nouveau.json"; rm -rf "$T" )
```

Expected: the copy, the Secret, then the list of identities followed by `+ memoire` and `data updated`. Then the service's ingress on the S3 gateway ([`../../storage/03-network.yaml`](../../storage/03-network.yaml), `oc diff` then `oc apply`), the storage restart, since it only reads its configuration at startup (**it cuts the file service for about a minute**), and the bucket Job:

```bash
oc -n sophia-storage rollout restart deploy/s3
oc -n sophia-storage rollout status deploy/s3 --timeout=5m
envsubst '${AWSCLI_VERSION} ${AWSCLI_DIGEST}' < 06-seau.yaml | oc apply -f -
oc -n sophia-storage wait --for=condition=complete job/s3-init-memoire --timeout=5m
oc -n sophia-storage logs job/s3-init-memoire
```

Expected in the log: `"Status": "Enabled"`, a `NoSuchLifecycleConfiguration` error (no lifecycle, on purpose), the policy with `ProtegerSeau` and `ProtegerValide`, the `memoire` bucket in the list.

**Step 2 quater — Forge.** The service's account, through Forgejo's CLI in its pod; the random password is thrown away, the account never uses it:

```bash
oc -n sophia-git exec deploy/forgejo -- forgejo admin user create --username "${MEMOIRE_FORGEJO_COMPTE}" --email "${MEMOIRE_FORGEJO_COMPTE}@${FORGE_MAIL_DOMAIN}" --random-password --must-change-password=false > /dev/null
```

Then, through the API, with a **temporary** administration token (scopes `write:admin`, `write:organization`, `write:repository`), read from a private file and deleted at the end in the web interface:
- `PATCH /admin/users/<account>`: `restricted: true`, `max_repo_creation: 0`, `allow_create_organization: false`, `admin: false`;
- `POST /orgs`: the organisation `${MEMOIRE_FORGEJO_ORG}`, private, `repo_admin_change_team_access: false`;
- `POST /orgs/<organisation>/repos`: one private repository per level, `auto_init`, `main` branch (names set by the code's table);
- `POST /orgs/<organisation>/teams`: a `write` team, `repo.code` unit only, `includes_all_repositories: false`, `can_create_org_repo: false`; then the account as a member, and the level repositories.

The service's token, poured straight into its Secret, and the ingress of the service's pod alone on the forge:

```bash
oc -n sophia-git exec deploy/forgejo -- forgejo admin user generate-access-token --username "${MEMOIRE_FORGEJO_COMPTE}" --token-name sophia-memoire --scopes write:repository --raw | tr -d '\n' | oc -n sophia-memory create secret generic sophia-memoire-forgejo --from-file=jeton=/dev/stdin
oc diff -f 07-forge-network.yaml
oc apply -f 07-forge-network.yaml
```

Expected: the Secret, of length `40`; the diff only shows the service's ingress. An off-site copy by mirror is added here if the installation wants one (see "Limits to be aware of").

**Step 3 — Vector database.** For a new installation, the dedicated volume first (XFS logical volume on the node, as for [PostgreSQL 18](../../core/postgres18/README.en.md)), then the database and its Service; otherwise only the API key (one restart):

```bash
envsubst '${QDRANT_MOUNT_POINT} ${QDRANT_SIZE} ${NODE_NAME}' < ../qdrant/01-volume.yaml | oc apply -f -
oc diff -f ../qdrant/02-qdrant.yaml
oc apply -f ../qdrant/02-qdrant.yaml
oc -n sophia-memory rollout status deploy/qdrant --timeout=180s
```

Then, in a second terminal, the tunnel `oc -n sophia-memory port-forward svc/qdrant-svc 16333:6333`, and in the first one:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:16333/collections
oc -n sophia-memory get secret qdrant-cle -o jsonpath='{.data.cle}' | base64 -d | python3 ../qdrant-schema.py --url http://127.0.0.1:16333 --cle-stdin --apply
```

Expected: `401` without a key; then the collection and its indexes (the 17 tags and the registry's three, `document`, `depot`, `rang`), `(créé)` for those that were missing.

**Step 4 — Identity provider.** The service's custom audience in the access tokens of the chat's client ([`../../identity/`](../../identity/README.en.md#audiences-of-the-token-relayed-by-the-interface)):

```bash
python3 ../../identity/ajouter-mappeur-audience.py sophia-interface sophia-memoire --personnalisee --dry-run
python3 ../../identity/ajouter-mappeur-audience.py sophia-interface sophia-memoire --personnalisee
```

Expected: `ajouté`, then `existe, non modifié` when replayed. The service's ingress on the identity provider: `oc diff`, then `oc apply` of `02-network.yaml` and of the rendered `03-keycloak.yaml`; the provider's pod keeps its age.

**Step 5 — Service, extraction, network:**

```bash
oc apply --dry-run=server -f 01-comptes.yaml
envsubst '${MEMOIRE_IMAGE_DIGEST}' < 03-extraction.yaml | oc apply --dry-run=server -f -
envsubst '${IDP_HOST} ${MEMOIRE_IMAGE_DIGEST}' < 02-memoire.yaml | oc apply --dry-run=server -f -
oc apply --dry-run=server -f 04-network.yaml
envsubst '${SERVICE_NETWORK} ${POD_NETWORK}' < 05-egressfirewall.yaml | oc apply --dry-run=server -f -
```

Expected: thirteen `created (server dry run)` (2 accounts, 2 Deployments, 2 Services, 1 ConfigMap, 5 NetworkPolicies, 1 EgressFirewall). Then the same commands without `--dry-run=server`, and:

```bash
oc -n sophia-memory get egressfirewall default -o jsonpath='{.status.status}{"\n"}'
oc -n sophia-memory rollout status deploy/sophia-extraction --timeout=180s
oc -n sophia-memory rollout status deploy/sophia-memoire --timeout=180s
```

Expected: `EgressFirewall Rules applied`, then two `successfully rolled out`. Startup is itself a proof through the real path: the service opens its two connections to PostgreSQL, checks that the audit role only has `INSERT`, and creates the registry. A pod in error points to a missing setting or right; its log contains no value.

**Step 5 bis — Bucket proof**, before any deposit:

```bash
oc -n sophia-memory exec -i deploy/sophia-memoire -- python3 - < epreuve-seau.py
```

Expected: under `valide/`, writing allowed, deleting a version (single and batch) and placing a delete marker refused, witness still there; versioning, lifecycle and policy refused; under `attente/`, writing and deleting allowed; finally `politique du seau : conforme`. Any `ÉCART` line: stop and switch to two buckets.

**Step 5 ter — Embedding still reachable by the router:**

```bash
oc -n sophia-core exec deploy/litellm -- python3 -c 'import urllib.request; print(urllib.request.urlopen("http://sophia-embedding-svc.sophia-memory.svc.cluster.local:8080/health", timeout=5).status)'
```

Expected: `200`.

**Step 6 — Extraction isolation proof.** The addresses to try without DNS are read by `oc` at proof time:

```bash
oc -n sophia-memory exec -i deploy/sophia-extraction -- python3 - $(oc -n sophia-memory get svc qdrant-svc -o jsonpath='{.spec.clusterIP}:6333') $(oc -n sophia-memory get svc sophia-memoire -o jsonpath='{.spec.clusterIP}:8080') $(oc -n sophia-identity get svc sophia-keycloak-service -o jsonpath='{.spec.clusterIP}:8080') $(oc -n sophia-core get svc litellm-svc -o jsonpath='{.spec.clusterIP}:4000') $(oc -n sophia-core get svc postgres-sophia-18 -o jsonpath='{.spec.clusterIP}:5432') $(oc -n sophia-storage get svc s3 -o jsonpath='{.spec.clusterIP}:9000') $(oc -n sophia-git get svc forgejo-svc -o jsonpath='{.spec.clusterIP}:3000') $(oc get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}:6443') $(oc -n default get svc kubernetes -o jsonpath='{.spec.clusterIP}:443') $(oc -n openshift-dns get svc dns-default -o jsonpath='{.spec.clusterIP}:53') < epreuve-extraction.py
```

Expected: variable names with no sensitive name, no mounted token, ten tries by address, each try `injoignable : ok`, and `D2 : conforme`, in about a minute.

**Rollback**, step by step, in reverse: `oc delete` of the step 5 manifests (the zone reopens, only do it knowingly); audience mapper in the console; vector database Deployment from its backup, without the key; `07-forge-network.yaml` rule from the saved rule, the service's token and account, organisation and repositories (validated texts would be lost there, outside a mirror); S3 identities from `s3-config-avant-memoire` then storage restart, the service's Secret, and the bucket, which can only be deleted empty, versions included; PostgreSQL roles by `DROP OWNED BY` then `DROP ROLE` (**deletes the whole registry**; audit already written stays); step 2 Secrets and ConfigMaps, and the router key in its administration interface; finally `00-build.yaml`. The `s3-config-avant-memoire` copy is deleted once step 5 bis is compliant.

## Variables

| Variable | Role |
|---|---|
| `${SOPHIA_MEMORY_NAMESPACE}` | memory zone namespace (`sophia-memory`) |
| `${OIDC_ISSUER}`, `${JWKS_URL}` | public issuer compared with the token; realm keys, through the internal address |
| `${AZP_PERMIS}` | clients whose token is accepted (the chat) |
| `${AGENTS}` | recognised service accounts, for the agents' façade |
| `${VALIDEUR}` | technical identifier of the validator (UUID); empty or malformed: refuses to start |
| `${QDRANT_URL}`, `${QDRANT_CLE}` | vector database and its key (Secret) |
| `${EXTRACTION_URL}` | extraction service |
| `${LITELLM_URL}`, `${LITELLM_CLE}` | model router and the service's key (Secret) |
| `${PG_HOST}`, `${PG_BASE}` | PostgreSQL and the memory database |
| `${PG_AUDIT_ROLE}`, `${PG_AUDIT_MOT_DE_PASSE}` | audit role (`INSERT` only) |
| `${PG_REGISTRE_ROLE}`, `${PG_REGISTRE_MOT_DE_PASSE}` | registry role |
| `${AUDIT_TENANT}` | installation tenant (UUID) |
| `${S3_URL}`, `${S3_CLE}`, `${S3_SECRET}`, `${S3_CA}` | object storage, the service's identity, Service certificate authority |
| `${MEMOIRE_SEAU}` | memory bucket |
| `${FORGEJO_URL}`, `${FORGEJO_JETON}` | forge and the service account's token |
| `${MEMOIRE_FORGEJO_ORG}` | organisation of the level repositories |

## Bench

The whole service is tested in memory against fakes (vector database with filters, router, identity provider with an RSA key, `TokenReview`, audit, registry with the same constraints as the schema, versioned bucket with an imitated policy, forge), with the real S3 and forge clients, the real extraction service and its real subprocess, and the SQL parsed by PostgreSQL's parser: 172 tests. **The main checks are each proven by at least one mutation** that makes it fail (about forty), manifests included (Secret or token in extraction, extraction egress, default deny, vector database open to another namespace). Among other things, the bench found that the real audit table refused two fields the application was passing. PostgreSQL, S3 and the forge are proven at rollout.

## Next

- Administration tool: **rebuilding the index** from the registry and the texts, and listing what remains under `attente/` with no pending version in the registry.
- **MCP façade** for the agents, and the chat's memory tool, under the person's token.
- Agents beyond `public` once the dispatcher passes on the person being served.
- Changing a document's level, through a dedicated action; real renaming.
- Images, through the vision model; ingestion rebuilt, writing through `proposer`.
- Graph (dimension 5) fed by the registry; notes vaults cloned from the forge.
