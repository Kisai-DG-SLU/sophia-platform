
# Workspace Management

Le **Workspace Management** définit la manière dont SOPHIA gère les environnements de travail des agents et des utilisateurs.

L'objectif est de garantir :

- reproductibilité
- isolation
- traçabilité

---

## Problème

Dans les systèmes basés sur des agents, les environnements de travail peuvent devenir chaotiques :

- dépendances implicites
- chemins locaux dépendants de la machine
- mélange entre mémoire, code et runtime

Cela rend les systèmes difficiles à maintenir et à reproduire.

---

## Principe

SOPHIA sépare strictement trois éléments :

### Brain

Le **Brain** contient la mémoire et les spécifications du projet.

Exemples :

- Guesdon-Brain
- SOPHIA-Brain

Contenu :

- specs
- décisions
- configuration projet

---

### Repository

Le repository contient **le travail réel** :

- code
- notebooks
- ressources

---

### Workspace

Le workspace est un **environnement d'exécution temporaire**.

Caractéristiques :

- éphémère
- isolé
- reproductible

Il peut être :

- local
- dans un pod Kubernetes
- dans un environnement sandbox

---

## Règle fondamentale

Le workspace **n'est jamais la source de vérité**.

La source de vérité est toujours :

- le Brain (mémoire)
- le repository (code)

---

## Intégration avec les agents

Les agents comme OpenCode ou d'autres assistants opèrent dans ces workspaces.

Ils peuvent :

- lire les specs dans le Brain
- modifier le repository
- exécuter des tâches dans le workspace

---

## Objectif

Garantir que :

- les projets restent reproductibles
- les environnements restent propres
- les agents ne dépendent pas d'un état local caché

---
