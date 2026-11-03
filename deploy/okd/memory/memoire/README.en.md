# Memory service (`sophia-memoire`)

The household's memory is a **service**, like the language model: called by the interface and by the agents, each with its own rights, and the **only writer** of knowledge. It receives documents, extracts their text in an isolated pod, stores them as versions, has them validated by a designated person, then makes them searchable. The knowledge model is described in the [RAG 5D](../../../../docs/concepts/03-rag-5d.en.md) page; the dashboard page that uses it, in the [dashboard](../../apps/chat-interface/README.en.md#memory-page).

**State in the reference installation**: **in service**. All the rollout steps below have been done, with both their proofs passing (bucket policy, extraction isolation). The dashboard's "Memory" page is deployed; the first real deposit comes with its end-to-end check. The service code is not provided; this document gives its contract, its rules and its recipe.

## What lives where (RAG 5D)

Each place has a single role. The registry is written **last**: as long as it does not reference an object, that object does not exist for the service.

| Place | What it keeps | Source of truth? |
|---|---|---|
| **S3 object storage**, one versioned bucket, never purged (`${MEMOIRE_SEAU}`) | the **original** of each version and its **extracted text**. Under `attente/` (pending), the pending version, erasable. Under `valide/` (validated), the original of each validated version (its text goes to the forge), **protected against any deletion**, even by the service | yes, for originals |
| **PostgreSQL**, a dedicated schema (`${MEMOIRE_SCHEMA}`) | the **registry**: documents, versions, states, fingerprints, references to S3 and to the forge | yes, for state and references |
| **Git forge** (Forgejo), a private organisation, **one repository per level** | the **validated text** of each version, in Markdown with a header; **one commit per validated version, never before**; a mirror copy on an external host | yes, for validated texts |
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
- **External mirror**: each level repository has a private copy on an external Git host (general rule of the installation: every repository has its mirror). All levels are there, `intime` included, readable by anyone who can access that account, even texts the page presents as readable by their author only. It is also an off-site copy, but **of validated texts only**: the originals (S3) and the registry (PostgreSQL) are not there, and the installation's backup is still to be done. For an installation that does not want this exposure: no mirror on the `personnel` and `intime` repositories, or an encrypted mirror.
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
