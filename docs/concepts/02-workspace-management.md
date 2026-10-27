# Workspace Management

Le **Workspace Management** définit la manière dont SophIA gère les environnements de travail des agents et des utilisateurs.

L'objectif est de garantir la reproductibilité, l'isolation et la traçabilité.

---

## Problème

Dans les systèmes basés sur des agents, les environnements de travail peuvent devenir chaotiques : dépendances implicites, chemins locaux dépendants de la machine, mélange entre mémoire, code et exécution.

Cela rend les systèmes difficiles à maintenir et à reproduire.

---

## Principe

SophIA sépare strictement trois éléments :

### Brain

Le **Brain** contient la mémoire et les spécifications du projet.

Exemples :

- dépôt Brain d'un projet de développement
- dépôt Brain d'un projet d'architecture

Contenu :

- spécifications
- décisions d'architecture
- configuration du projet

---

### Repository

Le repository contient le travail réel : code, notebooks, ressources.

---

### Workspace

Le workspace est un environnement d'exécution temporaire, éphémère, isolé et reproductible. Il peut être local, dans un pod Kubernetes ou dans un environnement sandbox.

Dans l'installation de référence, les environnements de développement tournent dans un namespace dédié, sans privilège sur le nœud. **Prévu** pour l'agent de développement : un cluster virtuel par projet, dont l'état est éphémère et recréé depuis la forge par un workflow ; pods sans privilège sous un compte propre au projet, images du registre interne seulement, paquets par des relais en lecture seule dans le sas, aucune sortie directe vers Internet.

---

## Règle fondamentale

Le workspace n'est jamais la source de vérité. La source de vérité est toujours le Brain (mémoire) et le repository (code).

---

## Intégration avec les agents

Les agents opèrent dans ces workspaces. Ils peuvent lire les spécifications dans le Brain, modifier le repository et exécuter des tâches dans le workspace.

---

## Objectif

Garantir que les projets restent reproductibles, que les environnements restent propres et que les agents ne dépendent pas d'un état local caché.
