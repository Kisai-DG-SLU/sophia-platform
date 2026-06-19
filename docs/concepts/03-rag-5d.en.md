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

- vector memory (`sophia-memory`) for dimensions 1 and 2
- Git repository (`sophia-git`) for dimension 3
- the project Brain for dimensions 4 and 5

The Tribunal Semantique validates information before it enters the system. The Sas Paranoiaque feeds the pipeline with raw data.

---

## Objective

RAG 5D transforms the system's memory into a set of certified, contextually rich, and governable data. The goal is to reduce hallucinations by providing the model not with raw corpus, but with structured, filtered, and verifiable knowledge.
