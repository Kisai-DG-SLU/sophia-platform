# RAG 5D : Topologie de la Connaissance

Le **RAG 5D** définit la manière dont SophIA structure, stocke et retrouve l'information pour alimenter les modèles d'intelligence artificielle en contexte pertinent.

La plupart des systèmes RAG (Retrieval-Augmented Generation) reposent sur une seule dimension : la similarité vectorielle. Cette approche atteint ses limites dès lors que les connaissances deviennent complexes, interconnectées ou soumises à des règles de gouvernance strictes.

SophIA propose une topologie de la connaissance en cinq dimensions complémentaires.

---

## Les cinq dimensions

### 1. Dimension vectorielle (similarité sémantique)

La recherche par similarité sémantique constitue la couche de base. Les documents sont découpés en fragments, transformés en vecteurs d'embedding, puis indexés dans une base spécialisée.

Cette dimension permet de retrouver des informations par proximité de sens, indépendamment de la terminologie exacte employée par l'utilisateur. C'est le premier filtre de pertinence.

Technologies possibles : base vectorielle spécialisée (Qdrant, Weaviate, Milvus), ou module d'extension d'une base existante.

### 2. Dimension relationnelle (métadonnées et traçabilité)

Les données brutes ne suffisent pas. Chaque fragment de connaissance est accompagné de métadonnées structurées : source, date d'acquisition, auteur, niveau de confiance, permissions d'accès.

Ces métadonnées sont stockées dans une base relationnelle et servent à filtrer, ordonner et tracer les informations avant leur injection dans le contexte.

Cette dimension garantit la traçabilité et le respect des règles de gouvernance (RBAC, rétention, anonymisation).

Technologies possibles : base relationnelle standard (PostgreSQL, MariaDB).

### 3. Dimension versionnée (source de vérité certifiée)

Toute connaissance intégrée dans le système doit pouvoir être ramenée à une source vérifiable. Les documents validés, les décisions d'architecture et les spécifications sont versionnés dans un dépôt Git.

Cette dimension constitue l'ancrage factuel du système. En cas de doute sur une information retrouvée par voie vectorielle, le système peut remonter à la source certifiée.

Technologies possibles : Forgejo, Gitea, GitLab CE, GitHub.

### 4. Dimension structurelle (organisation conceptuelle)

Avant d'être indexée, la connaissance est organisée selon une structure conceptuelle qui reflète les relations logiques entre les sujets.

Cette organisation prend la forme d'une arborescence de notes interconnectées, permettant un chunking sémantique (découpage par concept, pas par taille de fichier) et une navigation transverse.

Technologies possibles : base de connaissance structurée en graphe de notes (Obsidian, outline, wiki).

### 5. Dimension graphe (interdépendances métier)

La dimension la plus sophistiquée modélise les relations métier entre les entités : un document cite une réglementation, une réglementation dépend d'une norme, une norme est émise par un organisme, etc.

Cette topologie en graphe permet au système de naviguer les interdépendances logiques et de détecter les impacts collatéraux d'une décision ou d'une modification.

Technologies possibles : base de graphe (Neo4j, ArangoDB), ou module de relation au-dessus d'une base existante.

---

## Fonctionnement intégré

Les cinq dimensions ne fonctionnent pas en silo. L'orchestrateur interroge simultanément les couches pertinentes en fonction de la requête :

1. La dimension vectorielle identifie les fragments sémantiquement proches.
2. La dimension relationnelle filtre selon les droits et les métadonnées.
3. La dimension versionnée certifie les sources.
4. La dimension structurelle fournit le contexte conceptuel élargi.
5. La dimension graphe révèle les interdépendances.

Le résultat est assemblé en un contexte unique, enrichi et validé, avant d'être transmis au modèle.

---

## Position dans l'architecture

Le RAG 5D s'appuie sur plusieurs composants :

- la mémoire vectorielle (`sophia-memory`) pour les dimensions 1 et 2
- le dépôt Git (`sophia-git`) pour la dimension 3
- le Brain du projet pour les dimensions 4 et 5

Le Tribunal Sémantique valide les informations avant leur entrée dans le système. Le Sas Paranoïaque alimente le pipeline en données brutes.

---

## Objectif

Le RAG 5D transforme la mémoire du système en un ensemble de données certifiées, contextuellement riches et gouvernables. L'objectif est de réduire les hallucinations en donnant au modèle non pas un corpus brut, mais une connaissance structurée, filtrée et vérifiable.
