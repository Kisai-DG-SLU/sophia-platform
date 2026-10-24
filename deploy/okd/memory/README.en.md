# Memory — embedding service (`sophia-memory`)

First brick of memory (RAG): a service that turns text into vectors, for indexing in the vector database and for search. It runs **inside the cluster, on CPU**: no document leaves to be vectorised.

## Choices

| Item | Choice | Reason |
|---|---|---|
| Model | **BAAI/bge-m3** (1,024 dimensions, multilingual), normalised vectors | good in French and across languages; one model for the whole memory |
| Model in the image | downloaded **at build time** (Hugging Face token passed as a build argument), loaded from `/models/bge-m3` | the pod starts without Internet access; the model revision follows the image |
| Server | FastAPI + sentence-transformers, CPU PyTorch | |
| Probes | `/health`: ready after 30 s, alive after 60 s | loading the model takes time at start |
| Resources | 1 CPU and 2 Gi requested, at most 2 CPU and 4 Gi | the model fits in memory without a GPU (the card stays with the language model) |

**Changing the model changes the vector dimension**: everything already indexed must be re-embedded. The model is therefore chosen before the first ingestion.

## Contract

The service code is not provided; its contract:

| Route | Role |
|---|---|
| `GET /health` | status, model, dimension |
| `POST /v1/embeddings` | OpenAI-compatible API (`input`: text or list) |
| `POST /embed` | batch of texts (historical form) |

Port 8080, without authentication: the service must only be reachable from the memory and ingestion components (namespace NetworkPolicy).

## Files

| File | Content |
|---|---|
| `01-embedding-deployment.yaml` | service Deployment; defaults inside `${…:-…}` |
| `01-memory-metadata.sql` | `sophia.memory_metadata` schema: metadata of each memory item (owner, type, project, confidentiality, provenance, validation), next to the point in the vector database |

## Variables

| Variable | Default |
|---|---|
| `${SOPHIA_MEMORY_NAMESPACE}` | `sophia-memory` |
| `${EMBEDDING_IMAGE}` | image built in the internal registry |
| `${EMBEDDING_MODEL_PATH}` | `/models/bge-m3` |
| `${EMBEDDING_REPLICAS}` | 1 |
| `${EMBEDDING_CPU_REQUEST}`, `${EMBEDDING_CPU_LIMIT}` | 1, 2 |
| `${EMBEDDING_MEM_REQUEST}`, `${EMBEDDING_MEM_LIMIT}` | 2Gi, 4Gi |

## Procedure (administrator)

1. Image: Docker build of the service, with the Hugging Face token as a build argument (build Secret, never in the repository).
2. `envsubst` on `01-embedding-deployment.yaml` (or defaults), `--dry-run=server`, then `apply`.
3. Check: pod ready, `GET /health` reports dimension 1,024, a `POST /v1/embeddings` from an allowed pod returns a vector.

**Next**: dedicated storage for the service and document ingestion; any cache volume will be sized on the first real ingestion, not before.
