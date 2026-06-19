# RAG 5D : Topologie de la Connaissance

Le **RAG 5D** definit la maniere dont SophIA structure, stocke et retrouve l'information pour alimenter les modeles d'intelligence artificielle en contexte pertinent.

La plupart des systemes RAG (Retrieval-Augmented Generation) reposent sur une seule dimension : la similarite vectorielle. Cette approche atteint ses limites des lors que les connaissances deviennent complexes, interconnectees ou soumises a des regles de gouvernance strictes.

SophIA propose une topologie de la connaissance en cinq dimensions complementaires.

---

## Les cinq dimensions

### 1. Dimension vectorielle (similarite semantique)

La recherche par similarite semantique constitue la couche de base. Les documents sont decoupes en fragments, transformes en vecteurs d'embedding, puis indexes dans une base specialisee.

Cette dimension permet de retrouver des informations par proximite de sens, independamment de la terminologie exacte employee par l'utilisateur. C'est le premier filtre de pertinence.

Technologies possibles : base vectorielle specialisee (Qdrant, Weaviate, Milvus), ou module d'extension d'une base existante.

### 2. Dimension relationnelle (metadonnees et tracabilite)

Les donnees brutes ne suffisent pas. Chaque fragment de connaissance est accompagne de metadonnees structurees : source, date d'acquisition, auteur, niveau de confiance, permissions d'acces.

Ces metadonnees sont stockees dans une base relationnelle et servent a filtrer, ordonner et tracer les informations avant leur injection dans le contexte.

Cette dimension garantit la tracabilite et le respect des regles de gouvernance (RBAC, retention, anonymisation).

Technologies possibles : base relationnelle standard (PostgreSQL, MariaDB).

### 3. Dimension versionnee (source de verite certifiee)

Toute connaissance integree dans le systeme doit pouvoir etre ramenee a une source verifiable. Les documents valides, les decisions d'architecture et les specifications sont versionnes dans un depot Git.

Cette dimension constitue l'ancrage factuel du systeme. En cas de doute sur une information retrieve par voie vectorielle, le systeme peut remonter a la source certifiee.

Technologies possibles : Forgejo, Gitea, GitLab CE, GitHub.

### 4. Dimension structurelle (organisation conceptuelle)

Avant d'etre indexee, la connaissance est organisee selon une structure conceptuelle qui reflete les relations logiques entre les sujets.

Cette organisation prend la forme d'une arborescence de notes interconnectees, permettant un chunking semantique (decoupage par concept, pas par taille de fichier) et une navigation transverse.

Technologies possibles : base de connaissance structuree en graphe de notes (Obsidian, outline, wiki).

### 5. Dimension graphe (interdependances metier)

La dimension la plus sophistiquee modelise les relations metier entre les entites : un document cite une reglementation, une reglementation depend d'une norme, une norme est emise par un organisme, etc.

Cette topologie en graphe permet au systeme de naviguer les interdependances logiques et de detecter les impacts collateraux d'une decision ou d'une modification.

Technologies possibles : base de graphe (Neo4j, ArangoDB), ou module de relation au-dessus d'une base existante.

---

## Fonctionnement integre

Les cinq dimensions ne fonctionnent pas en silo. L'orchestrateur interroge simultanement les couches pertinentes en fonction de la requete :

1. La dimension vectorielle identifie les fragments semantiquement proches.
2. La dimension relationnelle filtre selon les droits et les metadonnees.
3. La dimension versionnee certifie les sources.
4. La dimension structurelle fournit le contexte conceptuel elargi.
5. La dimension graphe revele les interdependances.

Le resultat est assemble en un contexte unique, enrichi et valide, avant d'etre transmis au modele.

---

## Position dans l'architecture

Le RAG 5D s'appuie sur plusieurs composants :

- la memoire vectorielle (`sophia-memory`) pour les dimensions 1 et 2
- le depôt Git (`sophia-git`) pour la dimension 3
- le Brain du projet pour les dimensions 4 et 5

Le Tribunal Semantique valide les informations avant leur entree dans le systeme. Le Sas Paranoiaque alimente le pipeline en donnees brutes.

---

## Objectif

Le RAG 5D transforme la memoire du systeme en un ensemble de donnees certifiees, contextuellement riches et gouvernables. L'objectif est de reduire les hallucinations en donnant au modele non pas un corpus brut, mais une connaissance structuree, filtree et verifiable.
