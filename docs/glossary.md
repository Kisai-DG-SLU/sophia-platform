# Glossaire

Ce glossaire definit les termes cles utilises dans la documentation SophIA.

Il inclut a la fois des concepts generaux de l'IA et des termes specifiques a l'architecture.

---

# Concepts IA

## LLM (Large Language Model)

Modele de langage entraine sur de grands ensembles de donnees textuelles, capable de generer et de comprendre le langage naturel.

Exemples : modeles de type GPT, ou modeles open-source tels que Llama ou Mistral.

---

## RAG (Retrieval-Augmented Generation)

Technique qui ameliore les reponses d'un modele de langage en recuperant des informations pertinentes depuis une base de connaissance externe avant de generer une reponse.

Cela implique generalement une base vectorielle, des embeddings et un pipeline de recherche.

---

## Embeddings

Representations vectorielles du texte utilisees pour comparer la similarite semantique entre documents.

Les embeddings permettent aux systemes de recuperer des informations pertinentes dans de grandes collections de documents.

---

## Base vectorielle

Base de donnees conque pour stocker et rechercher efficacement des embeddings.

Exemples courants : Qdrant, Weaviate, Milvus.

---

## Agent

Composant logiciel capable d'effectuer des taches en utilisant des modeles d'IA et des outils externes.

Les agents peuvent ecrire du code, interroger des donnees, interagir avec des API ou orchestrer des flux de travail.

---

# Concepts de l'architecture SophIA

## SophIA

Acronyme de **Sovereign Orchestrator Platform for Holistic Intelligence Architecture**.

Architecture experimentale conque pour orchestrer des systemes d'IA dans une infrastructure securisee et souveraine.

---

## Brain

Le Brain contient la memoire et la structure intellectuelle d'un projet. Il inclut generalement les specifications, la configuration du projet et la memoire persistante.

Le Brain ne contient pas de code executable.

---

## Repository

Le repository contient les artefacts operationnels d'un projet : code source, notebooks, jeux de donnees, sorties generees.

Les repositories sont generalement geres via Git.

---

## Workspace

Environnement d'execution temporaire utilise par les agents ou les utilisateurs. Caracteristiques : ephemere, reproductible, isole.

Les workspaces peuvent fonctionner localement ou dans des environnements conteneurises.

---

## Projet

Dans SophIA, tout est modelise comme un projet. Un projet represente une unite de travail qui inclut un Brain, un repository et un ou plusieurs workspaces.

---

# Concepts de securite

## Sas Paranoiaque

Couche d'acquisition isolee responsable de la recuperation d'informations depuis Internet tout en protegeant l'infrastructure interne.

Ses responsabilites incluent : isolation de l'acces web, nettoyage du contenu, prevention des fuites de donnees.

---

## Tribunal Semantique

Mecanisme de validation qui evalue la credibilite des informations externes avant leur integration dans la base de connaissance.

Son objectif est de reduire le risque d'ingestion de contenu non fiable ou gener par IA.

---

# Concepts d'infrastructure

## Namespace

Limite d'isolation logique utilisee dans les environnements Kubernetes.

Les namespaces permettent de separer et securiser les composants au sein d'un meme cluster.

---

## DMZ (Demilitarized Zone)

Segment reseau concu pour isoler les systemes qui interagissent avec les reseaux externes.

Dans SophIA, la DMZ heberge les services responsables de l'interaction avec Internet.

---

## MCP (Model Context Protocol)

Protocole utilise pour exposer des outils et des capacites aux modeles d'IA de maniere structuree.

MCP permet aux agents de decouvrir et d'invoquer des capacites externes.

---

# Concepts de gouvernance

## Gestion de contexte

Processus de construction et de controle des informations fournies aux modeles d'IA.

Une gestion de contexte appropriee garantit un comportement previsible, une utilisation efficace des fenetres de contexte et une reduction du bruit dans les prompts.

---

## Gestion des espaces de travail

Mecanismes utilises pour gerer les environnements d'execution des projets et des agents.

Cela inclut la creation d'environnements, l'isolation et la reproductibilite.
