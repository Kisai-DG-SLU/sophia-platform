# RAG 5D: Knowledge Topology

**RAG 5D** defines how SophIA structures, stores, and retrieves information to feed artificial intelligence models with relevant context.

Most RAG (Retrieval-Augmented Generation) systems rely on a single dimension: vector similarity. This approach reaches its limits when knowledge becomes complex, interconnected, or subject to strict governance rules.

SophIA proposes a knowledge topology in five complementary dimensions.

---

## The five dimensions

### 1. Vector dimension (semantic similarity)

Semantic similarity search forms the base layer. Documents are split into chunks, transformed into embedding vectors, and indexed in a specialized database.

This dimension allows retrieving information by meaning proximity, regardless of the exact terminology used by the user. It is the first relevance filter.

Possible technologies: specialized vector database (Qdrant, Weaviate, Milvus), or extension module of an existing database.

### 2. Relational dimension (metadata and traceability)

Raw data is not enough. Each knowledge chunk is accompanied by structured metadata: source, acquisition date, author, confidence level, access permissions.

This metadata is stored in a relational database and serves to filter, order, and trace information before its injection into context.

This dimension guarantees traceability and compliance with governance rules (RBAC, retention, anonymization).

Possible technologies: standard relational database (PostgreSQL, MariaDB).

### 3. Versioned dimension (certified source of truth)

Any knowledge integrated into the system must be traceable to a verifiable source. Validated documents, architectural decisions, and specifications are versioned in a Git repository.

This dimension provides the system's factual anchor. When doubt arises about vectorially retrieved information, the system can fall back to the certified source.

Possible technologies: Forgejo, Gitea, GitLab CE, GitHub.

### 4. Structural dimension (conceptual organization)

Before being indexed, knowledge is organized according to a conceptual structure reflecting logical relationships between subjects.

This organization takes the form of interconnected note trees, enabling semantic chunking (splitting by concept, not by file size) and transversal navigation.

Possible technologies: structured knowledge base in note graph form (Obsidian, outline, wiki).

### 5. Graph dimension (business interdependencies)

The most sophisticated dimension models business relationships between entities: a document cites a regulation, a regulation depends on a standard, a standard is issued by an organization, and so on.

This graph topology allows the system to navigate logical interdependencies and detect collateral impacts of a decision or modification.

Possible technologies: graph database (Neo4j, ArangoDB), or relationship module on top of an existing database.

---

## Integrated operation

The five dimensions do not operate in silos. The orchestrator queries the relevant layers simultaneously based on the request:

1. The vector dimension identifies semantically close chunks.
2. The relational dimension filters by rights and metadata.
3. The versioned dimension certifies sources.
4. The structural dimension provides broader conceptual context.
5. The graph dimension reveals interdependencies.

The result is assembled into a single enriched and validated context before being transmitted to the model.

---

## Position in the architecture

RAG 5D relies on several components:

- the memory service (`sophia-memory`), only writer: the vector database for dimension 1, a PostgreSQL registry of documents and versions for dimension 2, with the originals in a versioned S3 bucket
- the Git forge (`sophia-git`) for dimension 3: one repository per confidentiality level, one commit per validated version
- the project Brain for dimensions 4 and 5

The Tribunal Semantique validates information before it enters the system. The Sas Paranoiaque feeds the pipeline with raw data.

---

## Status in the reference install

| Brick | Status |
|---|---|
| Embedding (bge-m3, 1,024 dimensions, CPU), through the router's `sophia-embedder` alias | in service |
| Vector collection and its schema: 18 tags in French (owner, type, project, confidentiality, provenance, validation…), 17 metadata indexes, `source` not indexed; idempotent script, without deletion | in service, empty |
| **Memory service** ([recipe](../../deploy/okd/memory/memoire/README.en.md)): proven identity (OIDC token, then a service account token for agents); rights filter set by the service, never by the caller; originals and texts in a versioned S3 bucket (`attente/` erasable, `valide/` protected even against the service), registry of documents and versions in PostgreSQL, validated texts in the forge (one repository per level, one commit per validated version), vector database reduced to a rebuildable index; a new version waits, the previous one stays searchable; validation by a single designated person (the household's administrator), other people's personal and intimate documents reduced to author, level, date and size; file extraction in a pod without secrets or network; audit in the database by a role that can only append | **in service**; the dashboard's "Memory" page deployed, end-to-end check in progress; agents' MCP façade to come |
| Graph database (dimension 5) | image pinned, at 0 replicas for now |
| Ingestion | suspended, to be rebuilt (its image could not be rebuilt) |
| S3 object storage for source files | in service ([`deploy/okd/storage/`](../../deploy/okd/storage/)); memory has its identity and its versioned, never-purged bucket there |
| Default deny in the memory zone | in service, with the vector database key ([security](../security.en.md)) |

Recipe: [`deploy/okd/memory/`](../../deploy/okd/memory/).

---

## Objective

RAG 5D transforms the system's memory into a set of certified, contextually rich, and governable data. The goal is to reduce hallucinations by providing the model not with raw corpus, but with structured, filtered, and verifiable knowledge.
