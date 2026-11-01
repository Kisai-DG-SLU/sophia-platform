# Memory — embedding and schema (`sophia-memory`)

The memory (RAG) bricks in service: a service that turns text into vectors, and the schema of the vector collection. Everything runs **inside the cluster, on CPU**: no document leaves to be vectorised. The knowledge model is described in the [RAG 5D](../../../docs/concepts/03-rag-5d.en.md) concept; this directory gives its real state and recipe.

## Choices

| Item | Choice | Reason |
|---|---|---|
| Model | **BAAI/bge-m3** (1,024 dimensions, multilingual), normalised vectors | good in French and across languages; one model for the whole memory |
| Model in the image | downloaded **at build time** (Hugging Face token passed as a build argument), loaded from `/models/bge-m3` | the pod starts without Internet access; the model revision follows the image |
| Server | FastAPI + sentence-transformers, CPU PyTorch | |
| Probes | `/health`: ready after 30 s, alive after 60 s | loading the model takes time at start |
| Resources | 1 CPU and 2 Gi requested, at most 2 CPU and 4 Gi | the model fits in memory without a GPU (the card stays with the language model) |
| Vector database | Qdrant, **image pinned by digest**, `Recreate`, `sophia-agents` class, `enableServiceLinks: false`, on a **dedicated XFS logical volume** (20 GB to start, mounted under `/var/mnt`), PV and PVC bound to each other | outside the node's `/var`, which it shared with other services; grows online (`lvextend -r`); Qdrant's optimisation needs up to twice the space while it runs; fill alert at 80% and 90% ([`../monitoring/`](../monitoring/)) |

**Changing the model changes the vector dimension**: everything already indexed must be re-embedded. The model is therefore chosen before the first ingestion.

## Contract

The service code is not provided; its contract:

| Route | Role |
|---|---|
| `GET /health` | status, model, dimension |
| `POST /v1/embeddings` | OpenAI-compatible API (`input`: text or list) |
| `POST /embed` | batch of texts (historical form) |

Port 8080, without authentication: the service must only be reachable from the router (namespace NetworkPolicy, ready: see "State").

## Files

| File | Content |
|---|---|
| `00-namespace-guardrails.yaml` | namespace quota on limits (8 CPU, 16 Gi, 10 pods) and container defaults |
| `01-embedding-deployment.yaml` | service Deployment; defaults inside `${…:-…}` |
| `01-memory-metadata.sql` | `sophia.memory_metadata` schema: metadata of each memory item (owner, type, project, confidentiality, provenance, validation), next to the point in the vector database |
| `qdrant-schema.py` | collection and payload indexes of the vector database; idempotent, deletes or changes nothing |

## Variables

| Variable | Default |
|---|---|
| `${SOPHIA_MEMORY_NAMESPACE}` | `sophia-memory` |
| `${QDRANT_SERVICE}` | vector database Service |
| `${EMBEDDING_IMAGE}` | image built in the internal registry |
| `${EMBEDDING_MODEL_PATH}` | `/models/bge-m3` |
| `${EMBEDDING_REPLICAS}` | 1 |
| `${EMBEDDING_CPU_REQUEST}`, `${EMBEDDING_CPU_LIMIT}` | 1, 2 |
| `${EMBEDDING_MEM_REQUEST}`, `${EMBEDDING_MEM_LIMIT}` | 2Gi, 4Gi |

## Procedure (administrator)

0. Guardrails: `00-namespace-guardrails.yaml`, `--dry-run=server`, `apply`, then `oc describe quota -n ${SOPHIA_MEMORY_NAMESPACE}`.
1. Image: Docker build of the service, with the Hugging Face token as a build argument (build Secret, never in the repository).
2. `envsubst` on `01-embedding-deployment.yaml` (or defaults), `--dry-run=server`, then `apply`.
3. Check: pod ready, `GET /health` reports dimension 1,024, a `POST /v1/embeddings` from an allowed pod returns a vector.

## Vector collection schema

One collection (1,024 dimensions, cosine distance, those of the embedding model) and one payload index per tag. The schema has **18 tags, under their French names**; 17 are indexed:

| Index type | Tags |
|---|---|
| `keyword` | `utilisateur`, `type_memoire`, `stockage`, `provenance`, `format`, `confidentialite`, `projet`, `theme`, `mots_cles`, `priorite`, `statut_arbitrage` |
| `float` | `confiance` |
| `integer` | `version` |
| `datetime` | `date_creation`, `date_maj`, `date_validation`, `date_expiration` |

`source`, a free field, is not indexed. Qdrant enforces no schema: the index speeds up filtering, it validates nothing. **Value validation** (closed lists, date consistency) belongs to the memory service, the only planned writer.

`qdrant-schema.py` (standard library only) reads first, then, with `--apply`, creates what is missing. An index already present with another type is reported (exit code 1), never changed. It stops if the collection has other dimensions.

```bash
oc -n ${SOPHIA_MEMORY_NAMESPACE} port-forward svc/${QDRANT_SERVICE} 16333:6333
```

In a second terminal:

```bash
python3 qdrant-schema.py --url http://127.0.0.1:16333
python3 qdrant-schema.py --url http://127.0.0.1:16333 --apply
```

Expected: the collection, then 17 `[à faire]` lines; with `--apply`, 17 `(créé)` lines; running it again changes nothing. Rollback, lossless on an empty collection: `DELETE /collections/<collection>/index/<field>` for each field.

## Access through the model router

Ingestion and the memory service call the embedding through the router's **`sophia-embedder`** alias ([`../core/`](../core/)), never the service directly: the same restricted keys and the same logs as the language models. A key that needs it gets the alias through `add-model-to-keys.py`. Check: a `/v1/embeddings` call on the alias returns a 1,024-value vector.

## State

| Brick | State |
|---|---|
| Embedding (bge-m3, CPU) and `sophia-embedder` alias | **in service** |
| Vector collection and its 17 indexes | **in service**, empty: nothing ingested yet |
| Vector database on its dedicated volume | **in service**: moved while the collection was still empty (copy checked byte for byte, old directory kept a week for a rollback) |
| Namespace quota and defaults | **in service** |
| Graph (Neo4j) | **at 0 replicas**: it never started. It will come back with an official image pinned by digest and a password in a Secret, never in the manifest |
| Ingestion | **suspended** (CronJob `suspend: true`), to be rebuilt: reproducible build and pinned image, documents read from object storage, no password in a URL, writes through the memory service |
| Memory service | **ready to install**: code proven on the bench and reviewed, procedure reviewed; not applied yet (see below) |
| Namespace network | **target, ready**: the vector database currently answers without a key, and the namespace has no NetworkPolicy yet; closing it (key, default deny, one rule per flow, EgressFirewall) is part of the memory service installation |

## The memory service: designed, ready to install, not yet in service

Memory is a **service**, like the model: called by the interface and by agents according to their rights, and the **only writer**. Its code is written and proven on the test bench (105 tests), reviewed three times; its installation procedure is ready and reviewed. **Nothing is applied on the cluster**: no document is in memory yet, and the chat still answers that memory is not available.

### What it does

| Route | Role |
|---|---|
| `rechercher` (search) | returns the **validated**, unexpired chunks readable by the caller |
| `proposer` (propose) | stores a short document |
| `moi` (me) | levels allowed to the caller, whether they validate, limits |
| `depots`, `depots/{id}/fichiers`, `depots/{id}/notes` | grouped deposit: one deposit receives several files or notes, one per request (the file as a raw body, no multipart) |
| `mes_depots` (my deposits) | what the person has deposited, with its state (pending, validated, refused) |
| `a_valider`, `a_valider/compte`, `valider` | the list to validate, its count for "What's new?", validating or refusing a document or a whole deposit |

A document is split into chunks (2,000 characters, 200 overlap) and embedded through the router's `sophia-embedder` alias, hence **inside the cluster**. Analysis is synchronous (a few minutes at worst): the chat's relay waits accordingly.

### Rules

- **Proven identity**, never declared by the model: relayed OIDC token for a person, service account token for an agent.
- **Confidentiality levels**: `public`, `famille` (family), `personnel` (personal), `intime` (intimate), `admin`. `personnel` and `intime` can only be read by their author; administration reads `admin` on top of the common levels; a guest only reads `public`. Agents are limited to `public` as long as the interface does not pass them the person's identity. The rights filter is **added by the service** to every query; the model cannot widen it.
- **Validation by a single person** (household decision, for now): a document put into memory is only used once **validated by the household's administrator**, designated by their technical identifier in a setting, not by a group: another member of the administration group validates nothing. What this person deposits is validated automatically. The service refuses to start if the setting is missing or malformed. Anything from the web will go through the [Semantic Tribunal](../../../docs/concepts/05-tribunal-semantique.en.md).
- **Confidentiality towards the validator**: for other people's `personnel` and `intime` documents, the list to validate only shows the author, the level, the date and the size: no file name, no excerpt, no content; the validator can validate or refuse, without being able to read afterwards. **Limit**: this rule protects the interface, not technical administration; the audit log links a deposit to its author (without content or file name).
- **Confidence**: 0 as long as a document is not validated (and on refusal), 1 once validated; only the validation state decides use.
- **Refusal**: the vectors are deleted, and the record keeps neither the document's name nor its vector. Originals are not kept.
- **Limits**: size per file and per deposit, number of pending and kept documents per person, text length per document, two uploads and two extractions at a time (beyond that, "busy").
- **Log**: every write and every refusal, with identifiers, size and number of chunks; never content, path or name.

### Isolated extraction

Reading a PDF or an office document means running a parser on an unknown file. The first version did so in a subprocess of the service: the review showed it could read its parent's environment (`/proc/<parent>/environ`), hence the keys of the vector database and of the router, and the pod's token. **Extraction therefore runs in a separate pod**, from the same image, **without Secrets, without a service account token, without network egress** and without a shared process namespace; the service sends it the bytes. In that pod, each file is read by a bounded subprocess (memory, CPU time, duration), with no file writes and no process creation; the type is inferred from the bytes, never from the name; office documents read without DTD; archives bounded in number of entries. Formats: text, Markdown, PDF with text, office documents; images will come later. An isolation test, run from the extraction pod, is part of the installation.

### Zone network

With the service, the memory zone closes: API key on the vector database, telemetry off; default deny for ingress **and** egress, then one rule per flow (vector database open to the memory service only, embedding to the router only, memory service to the chat, extraction to the memory service only); EgressFirewall limited to internal networks. The service uses its own router key, limited to the embedding alias.

### Cockpit side (household decisions)

- **A "Memory" page** to deposit documents, **a whole folder** at once when the device allows it. On iOS, choosing a folder is only possible from iOS 18.4: on an older tablet, several files are picked at once, otherwise one file at a time.
- **The list to validate** is on the same page, with an alert in "What's new?".
- The page is **coded and proven on the bench** against a fake memory service, not in service yet: it switches on with the service (see the [cockpit](../apps/chat-interface/README.en.md)). Level chosen from the service's closed list, nothing preselected; one document per request; for the validator, other people's personal and intimate documents reduced to author, level, date and size; validation through a one-tap confirmation.

### Next

Installing the service and closing the zone; the "Memory" page; rebuilding ingestion (reading from object storage with each document's author, writing through `proposer`); the MCP facade for agents; the graph.
