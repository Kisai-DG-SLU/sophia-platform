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

Port 8080, without authentication: the service must only be reachable from the memory and ingestion components (namespace NetworkPolicy, planned: see "State").

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
| Memory service | **being designed** |
| Namespace network | **target**: the vector database currently answers without a key, and the namespace has no NetworkPolicy yet; it will be closed (ingress from the router, the memory service and ingestion) once the memory service exists, so as not to cut an uninventoried flow |

## Planned: the memory service

Memory is a **service**, like the model: called by the interface and by agents according to their rights, and the **only writer**.

- **Two doors, one core**: an internal REST API (search, propose, validate) for the interface and workflows; a thin MCP facade for agents, which calls that API.
- **Caller identity**: proven, never declared by the model: service account token checked through `TokenReview` for agents, OIDC token for the interface.
- **Reading**: the rights filter (`utilisateur`, `confidentialite`) is **added by the service** to every query, on top of the requested filter; the model cannot widen it. The levels each group may read are set by a versioned table.
- **Writing**: `propose` stores a point **pending** (`statut_arbitrage`), with a confidence set **by rule according to provenance**, never by the model; values are checked against the tag list. Anything from the web goes to the [Semantic Tribunal](../../../docs/concepts/05-tribunal-semantique.en.md). `validate` is reserved to authorised humans and the tribunal.
- **Log**: every write and every refusal goes to an audit log.

Then: rebuilding ingestion, which will write through this service; closing the namespace network; the graph.
