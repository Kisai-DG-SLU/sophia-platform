# Glossaire

Ce glossaire définit les termes clés utilisés dans la documentation SophIA.

Il inclut à la fois des concepts généraux de l'IA et des termes spécifiques à l'architecture.

---

# Concepts IA

## LLM (Large Language Model)

Modèle de langage entraîné sur de grands ensembles de données textuelles, capable de générer et de comprendre le langage naturel.

Exemples : modèles de type GPT, ou modèles open-source tels que Llama ou Mistral.

---

## RAG (Retrieval-Augmented Generation)

Technique qui améliore les réponses d'un modèle de langage en récupérant des informations pertinentes depuis une base de connaissance externe avant de générer une réponse.

Cela implique généralement une base vectorielle, des embeddings et un pipeline de recherche.

---

## Embeddings

Représentations vectorielles du texte utilisées pour comparer la similarité sémantique entre documents.

Les embeddings permettent aux systèmes de récupérer des informations pertinentes dans de grandes collections de documents.

---

## Base vectorielle

Base de données conque pour stocker et rechercher efficacement des embeddings.

Exemples courants : Qdrant, Weaviate, Milvus.

---

## Agent

Composant logiciel capable d'effectuer des tâches en utilisant des modèles d'IA et des outils externes.

Les agents peuvent écrire du code, interroger des données, interagir avec des API ou orchestrer des flux de travail.

---

# Concepts de l'architecture SophIA

## SophIA

Acronyme de **Sovereign Orchestrator Platform for Holistic Intelligence Architecture**.

Architecture expérimentale conque pour orchestrer des systèmes d'IA dans une infrastructure sécurisée et souveraine.

---

## Brain

Le Brain contient la mémoire et la structure intellectuelle d'un projet. Il inclut généralement les spécifications, la configuration du projet et la mémoire persistante.

Le Brain ne contient pas de code exécutable.

---

## Repository

Le repository contient les artefacts opérationnels d'un projet : code source, notebooks, jeux de données, sorties générées.

Les repositories sont généralement gérés via Git.

---

## Workspace

Environnement d'exécution temporaire utilisé par les agents ou les utilisateurs. Caractéristiques : éphémère, reproductible, isolé.

Les workspaces peuvent fonctionner localement ou dans des environnements conteneurisés.

---

## Projet

Dans SophIA, tout est modélisé comme un projet. Un projet représente une unité de travail qui inclut un Brain, un repository et un ou plusieurs workspaces.

---

## Dashboard

L'interface de discussion devenue la coquille de toutes les interactions : un accueil pour parler à Sophia, un volet des modules permis par le rôle, chaque application affichée au centre dans un cadre, sous sa propre connexion, et un volet « Quoi de neuf ? » fait de résumés déterministes fournis par les applications. Une application signale au dashboard qu'elle est prête par un message `sophia.pret`. Voir [interface de discussion](../deploy/okd/apps/chat-interface/README.md).

Le dashboard s'appelle **cockpit dans le code** et dans le libellé de l'application : les noms de fichiers réels le gardent (`sophia-interface-cockpit-egress.yaml`, `/sophia-cockpit/pret.js`). À ne pas confondre avec le tableau de bord du système (module Visualisation), affiché dans le dashboard.

Adaptable à la demande : ses tuiles et ses pages sont des modules ajoutés au fil des besoins ; l'architecture prévoit que Sophia les développe elle-même (prévu).

## Développement assisté (vibe coding)

Espace prévu où chaque membre du foyer suit les projets qu'il a demandés à Sophia, avec leur maquette visuelle (des pages ouvertes dans un onglet) et leur état chez les agents, en lecture seule ; l'administrateur y confie en plus le développement et le déploiement aux agents et programme avec eux. Étude faite ; rien n'est encore construit. Voir la [feuille de route](roadmap.md).

---

# Concepts de sécurité

## Sas Paranoïaque

Couche d'acquisition isolée responsable de la récupération d'informations depuis Internet tout en protégeant l'infrastructure interne.

Ses responsabilités incluent : isolation de l'accès web, nettoyage du contenu, prévention des fuites de données.

---

## Tribunal Sémantique

Mécanisme de validation qui évalue la crédibilité des informations externes avant leur intégration dans la base de connaissance.

Son objectif est de réduire le risque d'ingestion de contenu non fiable ou gener par IA.

---

# Concepts d'infrastructure

## Namespace

Limite d'isolation logique utilisée dans les environnements Kubernetes.

Les namespaces permettent de séparer et sécuriser les composants au sein d'un même cluster.

---

## DMZ (Demilitarized Zone)

Segment réseau conçu pour isoler les systèmes qui interagissent avec les réseaux externes.

Dans SophIA, la DMZ héberge les services responsables de l'interaction avec Internet.

---

## MCP (Model Context Protocol)

Protocole utilisé pour exposer des outils et des capacités aux modèles d'IA de manière structurée.

MCP permet aux agents de découvrir et d'invoquer des capacités externes.

---

# Concepts de gouvernance

## Gestion de contexte

Processus de construction et de contrôle des informations fournies aux modèles d'IA.

Une gestion de contexte appropriée garantit un comportement prévisible, une utilisation efficace des fenêtres de contexte et une réduction du bruit dans les prompts.

---

## Gestion des espaces de travail

Mécanismes utilisés pour gérer les environnements d'exécution des projets et des agents.

Cela inclut la création d'environnements, l'isolation et la reproductibilité.
